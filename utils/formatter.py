import discord
from datetime import datetime, timezone


def stat_display_name(stat_type: str) -> str:
    return {
        "points": "Points",
        "assists": "Assists",
        "rebounds": "Rebounds",
        "steals": "Steals",
        "blocks": "Blocks",
        "turnovers": "Turnovers",
        "three_pointers": "3-Pointers",
        "fg_made": "FG Made",
        "pra": "Pts+Reb+Ast",
        "pr": "Pts+Reb",
        "pa": "Pts+Ast",
        "ra": "Reb+Ast",
    }.get(stat_type, stat_type.replace("_", " ").title())


GRADE_COLORS = {
    "🔥 Elite": 0x00FF88,
    "✅ Good":  0x2ECC71,
    "⚠️ Lean":  0xF39C12,
    "❌ Skip":  0xE74C3C,
}

COLOR_INTEL = 0x5865F2


def _grade_color(grade_label: str) -> int:
    for key, color in GRADE_COLORS.items():
        if key in (grade_label or ""):
            return color
    return 0x2ECC71


def format_prop_embed(prop: dict, pick_id: int = None, username: str = None) -> discord.Embed:
    player = prop.get("player_name", "Unknown")
    team = prop.get("team", "")
    opponent = prop.get("opponent", "")
    stat = stat_display_name(prop.get("stat_type", ""))
    line = prop.get("line", 0)
    direction = prop.get("direction", "over").capitalize()
    grade_label = prop.get("grade_label", "⚠️ Lean")
    grade_score = prop.get("grade_score", 0)
    true_prob = prop.get("true_prob", 0.5)
    book_prob = prop.get("book_prob", 0.524)
    ev = prop.get("ev")
    confidence = prop.get("confidence", "medium").capitalize()
    reasoning = prop.get("reasoning", "")
    watch_out = prop.get("watch_out", "")
    knowledge_flag = prop.get("knowledge_flag")
    platform = prop.get("platform", "")

    vs_str = f" vs {opponent}" if opponent else ""
    title = f"{grade_label} — {player} ({team}) · {direction} {line} {stat}"
    embed = discord.Embed(title=title, color=_grade_color(grade_label), timestamp=datetime.now(timezone.utc))

    if reasoning:
        embed.add_field(name="📋 Reasoning", value=reasoning, inline=False)

    ev_sign = "+" if (ev or 0) > 0 else ""
    true_pct = round(true_prob * 100)
    book_pct = round(book_prob * 100)
    embed.add_field(
        name="💰 Edge",
        value=f"**EV:** {ev_sign}{round(ev, 1) if ev else 'N/A'}% · **True:** {true_pct}% vs **Book:** {book_pct}%",
        inline=True
    )
    embed.add_field(name="🎯 Confidence", value=confidence, inline=True)
    embed.add_field(name="📊 Grade", value=f"{grade_label} (+{grade_score})", inline=True)

    if watch_out:
        embed.add_field(name="⚠️ Watch out for", value=watch_out, inline=False)

    if knowledge_flag:
        embed.add_field(name="ℹ️ Note", value=knowledge_flag, inline=False)

    footer_parts = []
    if pick_id:
        footer_parts.append(f"Pick saved · ID #{pick_id}")
    if username:
        footer_parts.append(username)
    if platform and platform not in ("unknown", "other"):
        footer_parts.append(platform)
    footer_parts.append("For research only · Wall-E")
    embed.set_footer(text=" · ".join(footer_parts))

    return embed


def format_parlay_embed(parlay: dict, saved: bool = False, username: str = None) -> discord.Embed:
    legs = parlay.get("legs", [])
    n = len(legs)
    overall_grade = parlay.get("overall_grade", "✅ Good")
    parlay_id = parlay.get("parlay_id", "")
    overall_reasoning = parlay.get("overall_reasoning", "")

    color = _grade_color(overall_grade)
    embed = discord.Embed(
        title=f"{overall_grade} — {n}-Leg Parlay · #{parlay_id}",
        description=overall_reasoning or "Wall-E's top picks.",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    for i, leg in enumerate(legs, 1):
        player = leg.get("player_name", "?")
        team = leg.get("team", "")
        opponent = leg.get("opponent", "")
        stat = stat_display_name(leg.get("stat_type", ""))
        line = leg.get("line", 0)
        direction = leg.get("direction", "over").capitalize()
        grade = leg.get("grade_label", "⚠️ Lean")
        ev = leg.get("ev")
        true_p = round(leg.get("true_prob", 0.5) * 100)
        reasoning = leg.get("reasoning", "")
        watch_out = leg.get("watch_out", "")

        vs_str = f" vs {opponent}" if opponent else ""
        ev_str = f"+{round(ev, 1)}%" if ev and ev > 0 else (f"{round(ev, 1)}%" if ev else "")

        lines = []
        if reasoning:
            lines.append(reasoning)
        if watch_out:
            lines.append(f"⚠️ {watch_out}")
        lines.append(f"{grade} · True: {true_p}%" + (f" · EV: {ev_str}" if ev_str else ""))

        field_name = f"Leg {i} — {player} ({team}){vs_str} · {direction} {line} {stat}"
        embed.add_field(name=field_name, value="\n".join(lines), inline=False)

    footer_parts = []
    if saved:
        footer_parts.append(f"Saved · #{parlay_id}")
    if username:
        footer_parts.append(username)
    footer_parts.append(f"{n}/{n} legs · For research only · Wall-E")
    embed.set_footer(text=" · ".join(footer_parts))

    return embed


def format_intelligence_embed(report: dict) -> discord.Embed:
    embed = discord.Embed(
        title="🧠 Wall-E Intelligence Report",
        color=COLOR_INTEL,
        timestamp=datetime.now(timezone.utc)
    )

    total = report.get("total", 0)
    wins = report.get("wins", 0)
    win_rate = report.get("win_rate", 0)
    embed.add_field(
        name="📈 Overall Record",
        value=f"**{wins}/{total}** ({win_rate}%) across {report.get('total_analyzed', 0)} analyzed props",
        inline=False
    )

    elite_total = report.get("elite_total", 0)
    elite_rate = report.get("elite_rate", 0)
    good_total = report.get("good_total", 0)
    good_rate = report.get("good_rate", 0)
    if elite_total > 0:
        embed.add_field(
            name="🔥 Elite picks",
            value=f"**{elite_rate}% win rate** ({elite_total} picks)",
            inline=True
        )
    if good_total > 0:
        embed.add_field(
            name="✅ Good picks",
            value=f"**{good_rate}% win rate** ({good_total} picks)",
            inline=True
        )

    stat_rates = report.get("stat_rates", [])
    if stat_rates:
        lines = [f"**{stat_display_name(r['stat_type'])}:** {int(r['win_pct'])}% ({r['cnt']} picks)" for r in stat_rates]
        embed.add_field(name="🏆 Best stat types", value="\n".join(lines), inline=False)

    top_players = report.get("top_players", [])
    if top_players:
        lines = [f"**{r['player_name']}:** {r['cnt']} picks · {int(r['win_pct'])}%" for r in top_players]
        embed.add_field(name="👤 Most analyzed players", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"{report.get('total_analyzed', 0)} picks tracked · Updated live · Wall-E")
    return embed


def format_pending_embed(picks: list) -> discord.Embed:
    embed = discord.Embed(
        title="⏳ Pending Picks",
        description="Use `/result` to update these picks." if picks else "No pending picks. Use `/prop` or `/parlay` to generate picks.",
        color=0x95A5A6,
        timestamp=datetime.now(timezone.utc)
    )
    for p in picks[:15]:
        platform_str = f" · {p['platform']}" if p.get("platform") and p["platform"] not in ("unknown", "other", None) else ""
        embed.add_field(
            name=f"#{p['id']} — {p['player_name']}",
            value=f"{p['direction'].capitalize()} {p['line']} {stat_display_name(p['stat_type'])}{platform_str} · {p['date']} · {p.get('grade_label', '')}",
            inline=False
        )
    return embed
