import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.claude_client import analyze_prop_from_image, analyze_prop_from_text
from utils.formatter import format_prop_embed
from utils.database import Database

log = logging.getLogger("walle.props")

STAT_CHOICES = [
    app_commands.Choice(name="Points", value="points"),
    app_commands.Choice(name="Assists", value="assists"),
    app_commands.Choice(name="Rebounds", value="rebounds"),
    app_commands.Choice(name="Steals", value="steals"),
    app_commands.Choice(name="Blocks", value="blocks"),
    app_commands.Choice(name="Turnovers", value="turnovers"),
    app_commands.Choice(name="3-Pointers Made", value="three_pointers"),
    app_commands.Choice(name="FG Made", value="fg_made"),
    app_commands.Choice(name="Pts+Reb+Ast", value="pra"),
    app_commands.Choice(name="Pts+Reb", value="pr"),
    app_commands.Choice(name="Pts+Ast", value="pa"),
    app_commands.Choice(name="Reb+Ast", value="ra"),
]

DIRECTION_CHOICES = [
    app_commands.Choice(name="Over", value="over"),
    app_commands.Choice(name="Under", value="under"),
]

SUPPORTED_IMAGE_TYPES = {
    "image/png": "image/png",
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/webp": "image/webp",
    "image/gif": "image/gif",
}


class PropsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(
        name="prop",
        description="Analyze a player prop — attach a screenshot or type it manually"
    )
    @app_commands.describe(
        image="Upload a prop slip screenshot (PrizePicks, Underdog, DraftKings, etc.)",
        player="Player name — only needed if not uploading an image",
        stat="Stat type — only needed if not uploading an image",
        line="The line — only needed if not uploading an image",
        direction="Over or Under — only needed if not uploading an image",
        opponent="Opponent team abbreviation (e.g. GSW) — optional",
        book_odds="Book's American odds (e.g. -115 or +105). Defaults to -110.",
        context="Any extra context: injuries, minutes restrictions, recent news",
        save="Save this pick to the tracker",
    )
    @app_commands.choices(stat=STAT_CHOICES, direction=DIRECTION_CHOICES)
    async def prop(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment = None,
        player: str = None,
        stat: app_commands.Choice[str] = None,
        line: float = None,
        direction: app_commands.Choice[str] = None,
        opponent: str = "",
        book_odds: int = -110,
        context: str = "",
        save: bool = False,
    ):
        await interaction.response.defer(thinking=True)

        try:
            prop_result = None

            # Path 1: Image uploaded — send to Claude vision
            if image:
                content_type = image.content_type or "image/png"
                media_type = SUPPORTED_IMAGE_TYPES.get(content_type.split(";")[0].strip())
                if not media_type:
                    await interaction.followup.send(
                        "❌ Unsupported image type. Please upload a PNG, JPG, or WebP screenshot.",
                        ephemeral=True
                    )
                    return
                image_bytes = await image.read()
                prop_result = await analyze_prop_from_image(image_bytes, media_type, extra_context=context)

            # Path 2: Manual text entry
            elif player and stat and line is not None and direction:
                prop_result = await analyze_prop_from_text(
                    player=player,
                    stat_type=stat.value,
                    line=line,
                    direction=direction.value,
                    opponent=opponent.upper() if opponent else "",
                    book_odds=book_odds,
                    extra_context=context,
                )

            else:
                await interaction.followup.send(
                    "❌ Please either attach a prop slip screenshot, or fill in the `player`, `stat`, `line`, and `direction` fields manually.",
                    ephemeral=True
                )
                return

            pick_id = None
            if save and prop_result:
                try:
                    pick_id = self.db.save_pick({
                        **prop_result,
                        "platform": prop_result.get("platform", ""),
                    })
                except Exception as e:
                    log.error(f"DB save failed: {e}")
                    # Don't crash — just note it in the embed

            username = interaction.user.name
            embed = format_prop_embed(prop_result, pick_id=pick_id, username=username)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            log.error(f"Prop command error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error analyzing prop: `{e}`\nPlease try again. If the issue persists, check that your `ANTHROPIC_API_KEY` is set correctly."
            )


async def setup(bot):
    await bot.add_cog(PropsCog(bot))
