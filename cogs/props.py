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


class SaveView(discord.ui.View):
    """Adds a Save button to any prop analysis embed."""
    def __init__(self, prop_result: dict, username: str):
        super().__init__(timeout=300)
        self.prop_result = prop_result
        self.username = username
        self.db = Database()
        self.saved = False

    @discord.ui.button(label="Save pick", style=discord.ButtonStyle.secondary, emoji="💾")
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.saved:
            await interaction.response.send_message("Already saved!", ephemeral=True)
            return
        try:
            pick_id = self.db.save_pick(self.prop_result)
            self.saved = True
            button.label = f"Saved — #{pick_id}"
            button.disabled = True
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
        except Exception as e:
            await interaction.response.send_message(f"❌ Save failed: {e}", ephemeral=True)


class PropsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(
        name="prop",
        description="Analyze a player prop — attach a screenshot or type it manually"
    )
    @app_commands.describe(
        image="Attach a prop slip screenshot (PrizePicks, Underdog, DraftKings etc.)",
        player="Player name — only if not uploading an image",
        stat="Stat type — only if not uploading an image",
        line="The line — only if not uploading an image",
        direction="Over or Under — only if not uploading an image",
        opponent="Opponent team abbreviation e.g. GSW (optional)",
        book_odds="Book's American odds e.g. -115 or +105. Defaults to -110.",
        context="Extra context: injuries, minutes restrictions, recent news",
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
    ):
        await interaction.response.defer(thinking=True)

        try:
            prop_result = None

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
                    "❌ Attach a prop slip screenshot, or fill in `player`, `stat`, `line`, and `direction` manually.",
                    ephemeral=True
                )
                return

            username = interaction.user.name
            embed = format_prop_embed(prop_result, username=username)
            view = SaveView(prop_result, username)
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            log.error(f"Prop command error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error analyzing prop: `{e}`"
            )


async def setup(bot):
    await bot.add_cog(PropsCog(bot))
