import discord
from discord.ext import commands, tasks
import os
import asyncio
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from utils.database import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("walle")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
AUTO_POST_CHANNEL_ID = int(os.getenv("AUTO_POST_CHANNEL_ID", "0"))

_raw_channels = os.getenv("AUTO_ANALYZE_CHANNELS", "")
AUTO_ANALYZE_CHANNELS = [int(c.strip()) for c in _raw_channels.split(",") if c.strip().isdigit()]

EASTERN = ZoneInfo("America/New_York")
AUTO_POST_TIME_ET = time(9, 0, tzinfo=EASTERN)

SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()


@bot.event
async def on_ready():
    log.info(f"Wall-E is online as {bot.user}")
    await bot.tree.sync()
    log.info("Slash commands synced globally")
    db.init()
    if not daily_parlay_post.is_running():
        daily_parlay_post.start()
    log.info("Scheduler started — daily post at 9:00 AM ET")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    image_attachments = [
        a for a in message.attachments
        if a.content_type and a.content_type.split(";")[0].strip().lower() in SUPPORTED_IMAGE_TYPES
    ]

    if image_attachments:
        if AUTO_ANALYZE_CHANNELS and message.channel.id not in AUTO_ANALYZE_CHANNELS:
            await bot.process_commands(message)
            return
        await _auto_analyze_image(message, image_attachments[0])
        return

    await bot.process_commands(message)


async def _auto_analyze_image(message: discord.Message, attachment: discord.Attachment):
    from utils.claude_client import analyze_prop_from_image
    from utils.formatter import format_prop_embed

    try:
        await message.add_reaction("⏳")
    except Exception:
        pass

    async with message.channel.typing():
        try:
            media_type = attachment.content_type.split(";")[0].strip().lower()
            if media_type == "image/jpg":
                media_type = "image/jpeg"

            image_bytes = await attachment.read()
            extra_context = message.content.strip() if message.content.strip() else ""

            result = await analyze_prop_from_image(image_bytes, media_type, extra_context=extra_context)

            # Handle both single prop (dict) and multi-prop (list) responses
            props = result if isinstance(result, list) else [result]

            try:
                await message.remove_reaction("⏳", bot.user)
                # React based on best grade in the slip
                grades = [p.get("grade_label", "") for p in props]
                if any("Elite" in g for g in grades):
                    await message.add_reaction("🔥")
                elif any("Good" in g for g in grades):
                    await message.add_reaction("✅")
                elif any("Lean" in g for g in grades):
                    await message.add_reaction("⚠️")
                else:
                    await message.add_reaction("❌")
            except Exception:
                pass

            # Send one embed per prop
            for prop in props:
                embed = format_prop_embed(prop, username=message.author.name)
                from cogs.props import SaveView
                view = SaveView(prop, message.author.name)
                await message.reply(embed=embed, view=view, mention_author=False)

        except Exception as e:
            log.error(f"Auto-analyze error: {e}", exc_info=True)
            try:
                await message.remove_reaction("⏳", bot.user)
                await message.add_reaction("❌")
            except Exception:
                pass
            await message.reply(
                f"❌ Couldn't analyze that image: `{e}`\n"
                "Make sure it's a clear prop slip screenshot. "
                "You can also type context alongside the image (e.g. 'he has a knee issue').",
                mention_author=False
            )


@bot.event
async def on_command_error(ctx, error):
    log.error(f"Command error: {error}")


@tasks.loop(time=AUTO_POST_TIME_ET)
async def daily_parlay_post():
    if AUTO_POST_CHANNEL_ID == 0:
        return
    channel = bot.get_channel(AUTO_POST_CHANNEL_ID)
    if not channel:
        log.warning("Scheduler: channel not found — check AUTO_POST_CHANNEL_ID")
        return
    try:
        from utils.claude_client import build_daily_parlay
        from utils.formatter import format_parlay_embed
        log.info("Scheduler: building daily parlay...")
        parlay = await build_daily_parlay(legs=4)
        if parlay:
            embed = format_parlay_embed(parlay)
            await channel.send(content="🌅 Good morning. Tonight's best props:", embed=embed)
            log.info(f"Daily parlay posted at {datetime.now()}")
    except Exception as e:
        log.error(f"Scheduler error: {e}", exc_info=True)


@daily_parlay_post.before_loop
async def before_daily():
    await bot.wait_until_ready()


async def load_cogs():
    for cog_file in ["props", "parlay", "intelligence", "track", "help"]:
        await bot.load_extension(f"cogs.{cog_file}")
        log.info(f"Loaded cog: {cog_file}")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
