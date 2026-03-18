"""
Core Claude API client.
Claude Sonnet 4.6 reads prop slip images and reasons about them.
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

PROP_SYSTEM_PROMPT = """You are Wall-E, an expert sports betting analyst specializing in player prop analysis.

You will receive images of prop slips from any sportsbook or DFS platform — PrizePicks, Underdog, DraftKings, FanDuel, BetMGM, ESPN Bet, same-game parlays, etc.

STEP 1 — READ THE IMAGE:
Extract every prop you can see. Handle all formats:
- "Over/Under 24.5 Points" → standard over/under
- "To Score 20+ Points" → treat as Over 19.5 Points
- "Double Double — Yes/No" → yes = over, treat line as 1.0 double_double
- "To Record X+ Assists/Rebounds/etc" → over format
- SGP (same game parlay) slips with multiple legs
- Multi-leg DFS slips
- Any American odds shown (+241, -136, etc.)

STEP 2 — ANALYZE EACH PROP:
For each prop, reason about:
- Player's recent form and season averages
- Injury status and load management patterns  
- Matchup quality vs the opponent
- Team pace, usage, game script tendencies
- Whether the line/price looks sharp or has value

STEP 3 — GRADE:
Scoring:
- true_prob > 75%: +4, > 65%: +2, > 55%: +1, < 50%: -2
- EV > 10%: +3, > 5%: +2, > 0%: +1, negative: -2
- Strong favorable matchup: +2, neutral: 0, tough: -1
- Recent form supports: +1, mixed: 0, against: -1

Grades: 🔥 Elite (8+), ✅ Good (4-7), ⚠️ Lean (1-3), ❌ Skip (0 or below)

EV FORMULA (standard):
- If over/under at -110: book_prob = 0.524
- If specific American odds given: book_prob = abs(odds)/(abs(odds)+100) for negative, 100/(odds+100) for positive
- EV% = ((true_prob - book_prob) / book_prob) * 100

HONESTY RULES:
- If you have limited knowledge of a player, say so in knowledge_flag
- Do not fabricate specific recent game stats
- Be calibrated — not everything is Elite
- For exotic props (double double, first basket, etc.) be more conservative

RESPONSE FORMAT:
If the image contains ONE prop, return a single JSON object.
If the image contains MULTIPLE props (SGP, multi-leg slip), return a JSON array of objects.

Single prop JSON:
{
  "player_name": "Full Name",
  "team": "ABBREV",
  "opponent": "ABBREV or empty string",
  "stat_type": "points|assists|rebounds|steals|blocks|turnovers|three_pointers|fg_made|pra|pr|pa|ra|double_double|other",
  "line": 24.5,
  "direction": "over|under|yes|no",
  "platform": "PrizePicks|Underdog|DraftKings|FanDuel|BetMGM|ESPNBet|other|unknown",
  "book_odds": -110,
  "true_prob": 0.65,
  "book_prob": 0.524,
  "ev": 24.1,
  "grade_label": "✅ Good",
  "grade_score": 5,
  "confidence": "high|medium|low",
  "reasoning": "2-3 sentence explanation",
  "watch_out": "Key risk (1 sentence)",
  "knowledge_flag": null
}

Multi-prop JSON array:
[
  { ...same fields as above for prop 1... },
  { ...same fields as above for prop 2... }
]

Respond with valid JSON only. No markdown, no explanation outside the JSON.
"""

DAILY_PARLAY_SYSTEM_PROMPT = """You are Wall-E, an expert NBA sports betting analyst.

Today's date is {today}. Build a {legs}-leg parlay from tonight's NBA slate.

Select the {legs} best player props available tonight based on your knowledge of:
- Tonight's NBA games and matchups
- Current player form, injuries, and load management
- Line value and sharp vs public money tendencies

Prefer: PRA combos, points for high-usage stars, assists for playmakers in fast-paced games.
Avoid: Props where injury status is unclear, blowout-prone matchups, players with minutes restrictions.

Respond with valid JSON only:
{
  "parlay_id": "6-char uppercase ID",
  "overall_grade": "🔥 Elite|✅ Good|⚠️ Lean",
  "overall_reasoning": "1-2 sentences on the slate",
  "legs": [
    {
      "player_name": "Full Name",
      "team": "ABBREV",
      "opponent": "ABBREV",
      "stat_type": "points|assists|rebounds|three_pointers|pra|pr|pa|ra",
      "line": 24.5,
      "direction": "over|under",
      "true_prob": 0.65,
      "book_prob": 0.524,
      "ev": 18.5,
      "grade_label": "✅ Good",
      "grade_score": 5,
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


def _encode_image(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def _parse_json_response(text: str) -> dict | list:
    """Safely parse JSON from Claude's response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def analyze_prop_from_image(image_bytes: bytes, media_type: str, extra_context: str = "") -> dict | list:
    """
    Send a prop slip image to Claude.
    Returns a single dict for one prop, or a list of dicts for multi-leg slips.
    """
    client = _get_client()

    user_content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": _encode_image(image_bytes),
            },
        },
        {
            "type": "text",
            "text": "Analyze this prop slip image. Extract all props you can see and give your full analysis." +
                    (f"\n\nExtra context from user: {extra_context}" if extra_context else ""),
        }
    ]

    log.info("Sending prop image to Claude...")
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=2000,
        system=PROP_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}]
    )
    raw = response.content[0].text
    log.info(f"Claude raw response (first 200): {raw[:200]}")
    result = _parse_json_response(raw)
    return result


async def analyze_prop_from_text(player: str, stat_type: str, line: float,
                                  direction: str, opponent: str = "",
                                  book_odds: int = -110, extra_context: str = "") -> dict:
    """Analyze a prop from text input."""
    client = _get_client()
    book_prob = (abs(book_odds) / (abs(book_odds) + 100)) if book_odds < 0 else (100 / (book_odds + 100))

    user_text = (
        f"Analyze this player prop:\n"
        f"Player: {player}\n"
        f"Stat: {stat_type}\n"
        f"Line: {line}\n"
        f"Direction: {direction}\n"
        f"Opponent: {opponent or 'unknown'}\n"
        f"Book odds: {book_odds} (implied {round(book_prob * 100, 1)}%)"
    )
    if extra_context:
        user_text += f"\n\nAdditional context: {extra_context}"

    log.info(f"Text prop: {player} {direction} {line} {stat_type}")
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=PROP_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_text}]
    )
    raw = response.content[0].text
    log.info(f"Claude raw response (first 200): {raw[:200]}")
    result = _parse_json_response(raw)
    if not result.get("book_prob"):
        result["book_prob"] = round(book_prob, 4)
    return result


async def build_daily_parlay(legs: int = 4) -> dict | None:
    """Build today's best parlay from tonight's NBA slate."""
    client = _get_client()
    today = datetime.now().strftime("%A, %B %d, %Y")
    system = DAILY_PARLAY_SYSTEM_PROMPT.format(today=today, legs=legs)

    log.info(f"Building daily {legs}-leg parlay for {today}...")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": f"Build the best {legs}-leg parlay for tonight's NBA games ({today})."}]
        )
        raw = response.content[0].text
        log.info(f"Daily parlay raw (first 200): {raw[:200]}")
        result = _parse_json_response(raw)
        if not result.get("parlay_id"):
            result["parlay_id"] = str(uuid.uuid4())[:6].upper()
        return result
    except Exception as e:
        log.error(f"Daily parlay error: {e}", exc_info=True)
        return None


async def build_custom_parlay(props: list[dict]) -> dict | None:
    """Analyze a custom list of props as a parlay."""
    client = _get_client()
    props_text = "\n".join([
        f"- {p['player_name']}: {p['direction']} {p['line']} {p['stat_type']}"
        + (f" vs {p.get('opponent', '')}" if p.get('opponent') else "")
        for p in props
    ])

    log.info(f"Building custom parlay: {len(props)} legs")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=DAILY_PARLAY_SYSTEM_PROMPT.format(
                today=datetime.now().strftime("%A, %B %d, %Y"),
                legs=len(props)
            ),
            messages=[{"role": "user", "content": f"Analyze these {len(props)} props as a parlay:\n{props_text}"}]
        )
        raw = response.content[0].text
        result = _parse_json_response(raw)
        if not result.get("parlay_id"):
            result["parlay_id"] = "CUSTOM"
        return result
    except Exception as e:
        log.error(f"Custom parlay error: {e}", exc_info=True)
        return None
