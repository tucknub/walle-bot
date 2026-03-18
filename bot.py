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
EASTERN = ZoneInfo("America/New_York")
AUTO_POST_TIME_ET = time(9, 0, tzinfo=EASTERN)

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
        else:
            log.warning("Scheduler: daily parlay returned None")
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
