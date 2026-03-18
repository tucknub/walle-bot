"""
Core Claude API client.
Replaces balldontlie + The Odds API entirely.
Claude Sonnet 4.6 reads images and reasons about props from training knowledge.
"""
import anthropic
import base64
import os
import json
import logging
import re
import uuid
from datetime import datetime

log = logging.getLogger("walle.claude")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-5"

# System prompt that instructs Claude how to analyze props
PROP_SYSTEM_PROMPT = """You are Wall-E, an expert NBA sports betting analyst specializing in player prop analysis.

Your job is to analyze player props and provide honest, well-reasoned assessments.

When given a prop (either from an image or text), you will:
1. Identify the player, stat type, line, and direction (over/under)
2. Reason about the prop using your knowledge of:
   - The player's recent form and season averages
   - Injury status and load management patterns
   - Matchup quality vs the opponent
   - Team pace, usage, and game script tendencies
   - Whether the line looks sharp or stale
3. Estimate a true probability for the prop hitting
4. Calculate an EV estimate assuming -110 juice (book implied ~52.4%)
5. Identify key risks or watch-out factors

IMPORTANT HONESTY RULES:
- If your knowledge of a player is limited or outdated, say so clearly
- Do not fabricate specific recent game stats — reason from what you reliably know
- If the player is obscure (international, G-League, women's league), flag it
- Be calibrated: not everything is Elite

GRADING SCALE:
- 🔥 Elite (+7 or higher score): true_prob > 68% AND positive EV AND strong matchup
- ✅ Good (+4 to +6): true_prob > 60% AND positive EV
- ⚠️ Lean (+1 to +3): slight edge, meaningful uncertainty
- ❌ Skip (0 or below): no edge, bad matchup, or too uncertain

SCORING:
- true_prob > 75%: +4, > 65%: +2, > 55%: +1, < 50%: -2
- EV > 10%: +3, > 5%: +2, > 0%: +1, negative: -2
- Strong favorable matchup: +2, neutral: 0, tough: -1
- Recent form strongly supports: +1, mixed: 0, against: -1

EV FORMULA (standard, expressed as percentage):
EV% = (true_prob × (100/110)) - ((1 - true_prob) × 1)
Then multiply by 100 to get percentage.
Example: 65% true prob → EV% = (0.65 × 0.909) - (0.35 × 1) = 0.591 - 0.35 = 0.241 → +24.1%

Always respond with valid JSON only. No markdown, no preamble, no explanation outside the JSON.

JSON format:
{
  "player_name": "Full Name",
  "team": "ABBREV",
  "opponent": "ABBREV or empty string",
  "stat_type": "points|assists|rebounds|steals|blocks|turnovers|three_pointers|fg_made|pra|pr|pa|ra|other",
  "line": 24.5,
  "direction": "over|under",
  "platform": "PrizePicks|Underdog|DraftKings|FanDuel|BetMGM|other|unknown",
  "true_prob": 0.65,
  "book_prob": 0.524,
  "ev": 24.1,
  "grade_label": "🔥 Elite",
  "grade_score": 8,
  "confidence": "high|medium|low",
  "reasoning": "2-3 sentence explanation of why you like or dislike this prop",
  "watch_out": "Key risk factor or caveat (1 sentence)",
  "knowledge_flag": null
}

knowledge_flag should be null if you have good knowledge of this player, or a short string like "Limited recent data — WNBA player" if uncertain.
"""

DAILY_PARLAY_SYSTEM_PROMPT = """You are Wall-E, an expert NBA sports betting analyst.

Today's date is {today}. Build a {legs}-leg parlay from tonight's NBA slate using your knowledge of:
- Tonight's NBA games and matchups
- Current player form, injuries, and load management
- Line value and sharp vs public money tendencies

Select the {legs} best player props available tonight. Choose props you have high confidence in.

Prefer: PRA combos, points for high-usage stars, assists for playmakers in fast-paced games.
Avoid: Props where injury status is unclear, blowout-prone matchups, players with minutes restrictions.

Respond with valid JSON only:
{
  "parlay_id": "auto-generated 6-char ID",
  "overall_grade": "🔥 Elite|✅ Good|⚠️ Lean",
  "overall_reasoning": "1-2 sentences on the slate overall",
  "legs": [
    {
      "player_name": "Full Name",
      "team": "ABBREV",
      "opponent": "ABBREV",
      "stat_type": "points|assists|rebounds|three_pointers|pra|pr|pa|ra",
      "line": 24.5,
      "direction": "over|under",
      "true_prob": 0.65,
      "ev": 18.5,
      "grade_label": "🔥 Elite",
      "grade_score": 8,
      "reasoning": "Why this leg",
      "watch_out": "Key risk"
    }
  ]
}
"""


def _get_client():
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set in environment variables")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _encode_image(image_bytes: bytes, media_type: str = "image/png") -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def _parse_json_response(text: str) -> dict:
    """Safely parse JSON from Claude's response, stripping any accidental markdown."""
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def analyze_prop_from_image(image_bytes: bytes, media_type: str, extra_context: str = "") -> dict:
    """
    Main function: send a prop slip image to Claude and get back a full analysis.
    Returns structured prop analysis dict.
    """
    client = _get_client()

    user_content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": _encode_image(image_bytes, media_type),
            },
        },
        {
            "type": "text",
            "text": "Analyze this prop slip. Extract the player, line, stat, and direction from the image, then give your full analysis." +
                    (f"\n\nAdditional context from user: {extra_context}" if extra_context else ""),
        }
    ]

    log.info("Sending prop image to Claude for analysis...")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=PROP_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}]
        )
        result = _parse_json_response(response.content[0].text)
        log.info(f"Claude analyzed: {result.get('player_name')} {result.get('direction')} {result.get('line')} {result.get('stat_type')}")
        return result
    except json.JSONDecodeError as e:
        log.error(f"JSON parse error: {e} — raw: {response.content[0].text[:200]}")
        raise
    except Exception as e:
        log.error(f"Claude API error: {e}", exc_info=True)
        raise


async def analyze_prop_from_text(player: str, stat_type: str, line: float,
                                  direction: str, opponent: str = "",
                                  book_odds: int = -110, extra_context: str = "") -> dict:
    """
    Analyze a prop from text input (no image).
    Used by /prop command when no image is attached.
    """
    client = _get_client()

    book_prob = (abs(book_odds) / (abs(book_odds) + 100)) if book_odds < 0 else (100 / (book_odds + 100))

    user_text = (
        f"Analyze this NBA player prop:\n"
        f"Player: {player}\n"
        f"Stat: {stat_type}\n"
        f"Line: {line}\n"
        f"Direction: {direction}\n"
        f"Opponent: {opponent or 'unknown'}\n"
        f"Book odds: {book_odds} (implied {round(book_prob * 100, 1)}%)"
    )
    if extra_context:
        user_text += f"\n\nAdditional context: {extra_context}"

    log.info(f"Sending text prop to Claude: {player} {direction} {line} {stat_type}")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=PROP_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}]
        )
        result = _parse_json_response(response.content[0].text)
        # Fill in book_prob from actual odds if not set by Claude
        if not result.get("book_prob"):
            result["book_prob"] = round(book_prob, 4)
        return result
    except json.JSONDecodeError as e:
        log.error(f"JSON parse error: {e}")
        raise
    except Exception as e:
        log.error(f"Claude API error: {e}", exc_info=True)
        raise


async def build_daily_parlay(legs: int = 4) -> dict | None:
    """
    Ask Claude to build today's best parlay from tonight's NBA slate.
    No image needed — Claude uses its knowledge of tonight's games.
    """
    client = _get_client()
    today = datetime.now().strftime("%A, %B %d, %Y")
    system = DAILY_PARLAY_SYSTEM_PROMPT.format(today=today, legs=legs)

    log.info(f"Building daily {legs}-leg parlay for {today}...")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=system,
            messages=[{
                "role": "user",
                "content": f"Build the best {legs}-leg parlay for tonight's NBA games ({today})."
            }]
        )
        result = _parse_json_response(response.content[0].text)
        if not result.get("parlay_id"):
            result["parlay_id"] = str(uuid.uuid4())[:6].upper()
        log.info(f"Daily parlay built: {result.get('parlay_id')} — {len(result.get('legs', []))} legs")
        return result
    except Exception as e:
        log.error(f"Daily parlay error: {e}", exc_info=True)
        return None


async def build_custom_parlay(props: list[dict]) -> dict | None:
    """
    Analyze a custom list of props as a parlay.
    props = [{"player_name": ..., "stat_type": ..., "line": ..., "direction": ...}, ...]
    """
    client = _get_client()

    props_text = "\n".join([
        f"- {p['player_name']}: {p['direction']} {p['line']} {p['stat_type']}"
        + (f" vs {p.get('opponent', '')}" if p.get('opponent') else "")
        for p in props
    ])

    user_text = f"Analyze these {len(props)} props as a parlay:\n{props_text}\n\nReturn the same JSON format as a daily parlay."

    log.info(f"Building custom parlay: {len(props)} legs")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=DAILY_PARLAY_SYSTEM_PROMPT.format(
                today=datetime.now().strftime("%A, %B %d, %Y"),
                legs=len(props)
            ),
            messages=[{"role": "user", "content": user_text}]
        )
        result = _parse_json_response(response.content[0].text)
        if not result.get("parlay_id"):
            result["parlay_id"] = "CUSTOM"
        return result
    except Exception as e:
        log.error(f"Custom parlay error: {e}", exc_info=True)
        return None
