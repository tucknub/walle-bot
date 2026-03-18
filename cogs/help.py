import discord
from discord import app_commands
from discord.ext import commands


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all Wall-E commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 Wall-E — Command Reference",
            description="NBA prop analysis powered by Claude Sonnet 4.6.\n*For research only.*",
            color=0x5865F2,
        )

        embed.add_field(
            name="📸 `/prop` — analyze a prop",
            value=(
                "**With image:** Attach any prop slip screenshot (PrizePicks, Underdog, DraftKings, etc.) — Wall-E reads it automatically.\n"
                "**Without image:** Fill in `player`, `stat`, `line`, `direction` manually.\n"
                "Optional: `opponent` · `book_odds` · `context` (injuries, news) · `save`\n"
                "*Example: `/prop context:he's been on a minutes restriction save:True` + attach screenshot*"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎯 `/parlay` — tonight's best picks",
            value=(
                "Wall-E analyzes tonight's full NBA slate and builds the best available parlay.\n"
                "`legs` (2–6, default 4) · `save`\n"
                "*Example: `/parlay legs:4 save:True`*"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔍 `/analyze` — grade your own parlay",
            value=(
                "Type in 2–3 props you're considering and Wall-E grades them together.\n"
                "`player1/stat1/line1/direction1` · `player2/...` · player3 optional\n"
                "*Example: `/analyze player1:Pritchard stat1:pra line1:24.5 direction1:over player2:SGA stat2:points line2:29.5 direction2:over`*"
            ),
            inline=False,
        )

        embed.add_field(
            name="🧠 `/intelligence`",
            value="Wall-E's full performance report — overall record, win rate by grade tier, best stat types, top players.",
            inline=False,
        )

        embed.add_field(
            name="⏳ `/pending`",
            value="View all saved picks awaiting results. Shows IDs for use with `/result`.",
            inline=False,
        )

        embed.add_field(
            name="✅ `/result`",
            value=(
                "Mark a saved pick as Win, Loss, or Push.\n"
                "`pick_id` · `result` · `actual_value` (optional)\n"
                "*Example: `/result pick_id:42 result:Win actual_value:28`*"
            ),
            inline=False,
        )

        embed.add_field(
            name="📋 `/bulk_result`",
            value=(
                "Update multiple picks at once.\n"
                "`pick_ids` (comma-separated) · `result`\n"
                "*Example: `/bulk_result pick_ids:42,43,44 result:Win`*"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚙️ How it works",
            value=(
                "Wall-E uses **Claude Sonnet 4.6** (vision + reasoning) — no external stats API.\n"
                "Upload a screenshot and Claude reads the player, line, and stat directly from the image.\n"
                "Analysis is based on Claude's training knowledge: form, matchups, injuries, line value.\n"
                "For very recent injuries or trades, add them in the `context` field."
            ),
            inline=False,
        )

        embed.set_footer(text="Wall-E · Powered by Claude Sonnet 4.6 · For research only")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
