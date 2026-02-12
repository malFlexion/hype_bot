# Bluesky Engagement Analytics Bot

A Bluesky bot that analyzes user engagement when mentioned. When you tag the bot, it responds with:
- Top post from the last 30 days
- Top post of all time
- Most ratioed post (controversial - high replies/likes ratio)

## Setup

### 1. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
1. Copy `.env.example` to `.env`
2. Create a Bluesky account for your bot
3. Generate an app password: Settings > Advanced > App Passwords
4. Update `.env` with your bot's credentials

### 4. Run locally
```bash
python -m src.main
```

## Deployment to Fly.io

### 1. Install flyctl
```bash
curl -L https://fly.io/install.sh | sh
```

### 2. Login and initialize
```bash
fly auth login
fly launch --no-deploy
```

### 3. Set secrets
```bash
fly secrets set BLUESKY_HANDLE=yourbot.bsky.social
fly secrets set BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

### 4. Deploy
```bash
fly deploy
```

### 5. Monitor
```bash
fly logs
```

## How it works

1. Bot polls Bluesky notifications every 30 seconds
2. When mentioned, it fetches the tagger's post history
3. Analyzes engagement metrics (likes + reposts + replies)
4. Replies with a thread containing the top posts

## Architecture

- **src/config.py** - Environment configuration
- **src/client.py** - Bluesky API wrapper
- **src/analytics.py** - Engagement analysis engine
- **src/formatter.py** - Response formatting
- **src/bot.py** - Main bot orchestration
- **src/main.py** - Entry point with health check server

## License

MIT
