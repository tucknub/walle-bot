import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.claude_client import build_daily_parlay, build_custom_parlay
from utils.formatter import format_parlay_embed
from utils.database import Database

log = logging.getLogger("walle.parlay")


class ParlayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(
        name="parlay",
        description="Auto-build tonight's best parlay from Claude's analysis of the full NBA slate"
    )
    @app_commands.describe(
        legs="Number of legs (2–6, default 4)",
        save="Save these picks to the tracker",
    )
    async def parlay(
        self,
        interaction: discord.Interaction,
        legs: int = 4,
        save: bool = False,
    ):
        if not 2 <= legs <= 6:
            await interaction.response.send_message(
                "❌ Legs must be between 2 and 6.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            parlay = await build_daily_parlay(legs=legs)
            if not parlay or not parlay.get("legs"):
                await interaction.followup.send(
                    "❌ Could not build a parlay right now. Claude may not have enough data on tonight's slate. Try again later or use `/prop` to analyze individual picks."
                )
                return

            if save:
                try:
                    parlay_id = parlay.get("parlay_id", "DAILY")
                    self.db.save_parlay(parlay_id, len(parlay["legs"]), parlay.get("overall_grade"))
                    for leg in parlay["legs"]:
                        self.db.save_pick({**leg, "parlay_id": parlay_id})
                except Exception as e:
                    log.error(f"Parlay save error: {e}")

            username = interaction.user.name
            embed = format_parlay_embed(parlay, saved=save, username=username)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            log.error(f"Parlay command error: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error building parlay: `{e}`")

    @app_commands.command(
        name="analyze",
        description="Grade your own custom 2–3 props as a parlay"
    )
    @app_commands.describe(
        player1="Player 1 name",
        stat1="Stat type (points/assists/rebounds/pra etc)",
        line1="Line for player 1",
        direction1="over or under",
        player2="Player 2 name",
        stat2="Stat type",
        line2="Line for player 2",
        direction2="over or under",
        player3="Player 3 name (optional)",
        stat3="Stat type (optional)",
        line3="Line for player 3 (optional)",
        direction3="over or under (optional)",
        opponent1="Opponent for player 1 (optional)",
        opponent2="Opponent for player 2 (optional)",
        opponent3="Opponent for player 3 (optional)",
    )
    async def analyze(
        self,
        interaction: discord.Interaction,
        player1: str, stat1: str, line1: float, direction1: str,
        player2: str, stat2: str, line2: float, direction2: str,
        player3: str = None, stat3: str = None, line3: float = None, direction3: str = "over",
        opponent1: str = "", opponent2: str = "", opponent3: str = "",
    ):
        await interaction.response.defer(thinking=True)

        direction1 = direction1.lower().strip()
        direction2 = direction2.lower().strip()
        direction3 = direction3.lower().strip()

        if direction1 not in ("over", "under") or direction2 not in ("over", "under"):
            await interaction.followup.send(
                "❌ Direction must be `over` or `under`.", ephemeral=True
            )
            return

        props = [
            {"player_name": player1, "stat_type": stat1.lower(), "line": line1, "direction": direction1, "opponent": opponent1.upper()},
            {"player_name": player2, "stat_type": stat2.lower(), "line": line2, "direction": direction2, "opponent": opponent2.upper()},
        ]
        if player3 and stat3 and line3:
            props.append({"player_name": player3, "stat_type": stat3.lower(), "line": line3, "direction": direction3, "opponent": opponent3.upper()})

        try:
            parlay = await build_custom_parlay(props)
            if not parlay:
                await interaction.followup.send("❌ Could not analyze these props. Try again.")
                return

            username = interaction.user.name
            embed = format_parlay_embed(parlay, username=username)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            log.error(f"Analyze command error: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: `{e}`")


async def setup(bot):
    await bot.add_cog(ParlayCog(bot))
