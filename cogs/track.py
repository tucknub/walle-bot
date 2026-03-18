import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.database import Database

log = logging.getLogger("walle.track")

RESULT_CHOICES = [
    app_commands.Choice(name="Win ✅", value="win"),
    app_commands.Choice(name="Loss ❌", value="loss"),
    app_commands.Choice(name="Push ➡️", value="push"),
]


class TrackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name="result", description="Update the result of a tracked pick")
    @app_commands.describe(
        pick_id="The pick ID shown when you saved it (use /pending to see IDs)",
        result="Win, Loss, or Push",
        actual_value="The actual stat value for the game (optional)",
    )
    @app_commands.choices(result=RESULT_CHOICES)
    async def result(
        self,
        interaction: discord.Interaction,
        pick_id: int,
        result: app_commands.Choice[str],
        actual_value: float = None,
    ):
        try:
            self.db.update_result(pick_id, result.value, actual_value)
        except Exception as e:
            await interaction.response.send_message(f"❌ Database error: `{e}`", ephemeral=True)
            return

        emoji = {"win": "✅", "loss": "❌", "push": "➡️"}.get(result.value, "")
        msg = f"{emoji} Pick **#{pick_id}** marked as **{result.name}**"
        if actual_value is not None:
            msg += f" · actual: **{actual_value}**"
        await interaction.response.send_message(msg)

    @app_commands.command(name="bulk_result", description="Update multiple picks at once")
    @app_commands.describe(
        pick_ids="Comma-separated pick IDs (e.g. 1,2,3)",
        result="Win, Loss, or Push",
    )
    @app_commands.choices(result=RESULT_CHOICES)
    async def bulk_result(
        self,
        interaction: discord.Interaction,
        pick_ids: str,
        result: app_commands.Choice[str],
    ):
        ids = [int(x.strip()) for x in pick_ids.split(",") if x.strip().isdigit()]
        if not ids:
            await interaction.response.send_message("❌ No valid IDs provided.", ephemeral=True)
            return

        failed = []
        for pick_id in ids:
            try:
                self.db.update_result(pick_id, result.value)
            except Exception as e:
                failed.append(str(pick_id))
                log.error(f"Bulk result error for pick #{pick_id}: {e}")

        emoji = {"win": "✅", "loss": "❌", "push": "➡️"}.get(result.value, "")
        msg = f"{emoji} Updated **{len(ids) - len(failed)}** picks as **{result.name}**: {', '.join(f'#{i}' for i in ids)}"
        if failed:
            msg += f"\n⚠️ Failed for: {', '.join(failed)}"
        await interaction.response.send_message(msg)


async def setup(bot):
    await bot.add_cog(TrackCog(bot))
