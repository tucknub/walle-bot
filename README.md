# 🤖 Wall-E — NBA Prop Bot

Analyzes NBA player props using **Claude Sonnet 4.6** vision and reasoning.
Upload a screenshot from PrizePicks, Underdog, DraftKings, or any sportsbook — Wall-E reads it and gives you a full analysis with grade, EV estimate, matchup context, and reasoning.

No external stats API. No balldontlie. Just Claude.

---

## 🚀 Setup — 3 Steps

### Step 1 — Create your Discord bot

1. Go to https://discord.com/developers/applications
2. Click **New Application** → name it **Wall-E**
3. Go to the **Bot** tab → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable **Message Content Intent**
5. Copy your **Bot Token**
6. Go to **OAuth2 → URL Generator**
   - Check **bot** and **applications.commands**
   - Bot Permissions: Send Messages, Embed Links, Read Message History, Attach Files
7. Open the generated URL → invite Wall-E to your server

### Step 2 — Get your Anthropic API key

1. Go to https://console.anthropic.com
2. Sign up free — you get $5 in free credits (no card needed)
3. Go to **API Keys** → create a new key
4. Copy it for Step 3

### Step 3 — Deploy on Railway

1. Push this code to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub repo
3. Add these environment variables:

```
DISCORD_TOKEN         = your Discord bot token
ANTHROPIC_API_KEY     = your Anthropic API key
AUTO_POST_CHANNEL_ID  = channel ID for daily 9am parlay post (optional, set 0 to disable)
DB_PATH               = /data/walle.db  (if you mount a Railway Volume for persistence)
```

4. (Recommended) Add a Railway Volume mounted at `/data` so pick history survives redeploys
5. Railway auto-deploys. Logs will show:
   ```
   Wall-E is online as Wall-E#1234
   Slash commands synced globally
   Scheduler started
   ```

> **Note:** Global slash commands take up to 1 hour to appear in Discord after first deploy.
> For instant testing, sync to a specific server by adding your guild ID to `bot.tree.sync()`.

---

## 🎮 Commands

| Command | Description |
|---|---|
| `/help` | Show all commands (only visible to you) |
| `/prop` | Analyze a prop — attach screenshot OR type manually |
| `/parlay` | Auto-build tonight's best parlay from the NBA slate |
| `/analyze` | Grade your own custom 2–3 leg parlay |
| `/intelligence` | Full performance report — record, win rates by grade |
| `/pending` | View picks awaiting results |
| `/result` | Mark a pick Win / Loss / Push |
| `/bulk_result` | Update multiple picks at once |

---

## 📸 How to use `/prop` (the main command)

**With a screenshot (recommended):**
```
/prop save:True context:he's been on a minutes restriction
```
Then attach your PrizePicks / Underdog / DraftKings screenshot. Wall-E reads the player, line, and stat from the image automatically.

**Without a screenshot:**
```
/prop player:Payton Pritchard stat:pra line:24.5 direction:over opponent:GSW book_odds:-110 save:True
```

---

## 💰 Cost

Wall-E uses Claude Sonnet 4.6 at ~$0.006 per analysis call.

| Usage | Est. monthly cost |
|---|---|
| Just you (5 calls/day) | ~$0.90 |
| Small group (25 calls/day) | ~$4.50 |
| Active server (100 calls/day) | ~$18 |

New Anthropic accounts get **$5 free credits** — covers ~800 prop analyses before you pay anything.

---

## ⚠️ Disclaimer

For research and entertainment only. Not financial advice.
Claude's knowledge has a training cutoff — for very recent injuries or trades, use the `context` field.
