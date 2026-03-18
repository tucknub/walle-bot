import discord
from discord import app_commands
from discord.ext import commands
from utils.database import Database
from utils.formatter import format_intelligence_embed, format_pending_embed


class IntelligenceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name="intelligence", description="View Wall-E's full performance report")
    async def intelligence(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        report = self.db.get_intelligence_report()
        embed = format_intelligence_embed(report)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="pending", description="View all picks awaiting results")
    async def pending(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        picks = self.db.get_pending_picks()
        embed = format_pending_embed(picks)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(IntelligenceCog(bot))
