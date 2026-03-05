# 🚀 Quick Start - Mattermost Summary Bot

## Minimal setup (5 minutes)

### 1. Download
```bash
git clone <repository-url>
cd mattermost-summary-bot
```

### 2. Install dependencies
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 3. Configure
```bash
cp env.example .env
# Edit .env with your values
```

### 4. Run
```bash
python main.py
```

### 5. Verify
- Open http://localhost:8080
- Add bot to a channel: `/invite @summary-bot`
- Use command: `!summary`

## Main `.env` settings

```bash
# Mattermost (REQUIRED)
MATTERMOST_URL=https://your-server.com
MATTERMOST_TOKEN=your-bot-token

# LLM (LiteLLM / OpenAI-compatible)
LLM_PROXY_TOKEN=sk-your-token
LLM_BASE_URL=https://litellm.1bitai.ru
LLM_MODEL=gpt-5

# API token for protected endpoints
WEB_API_TOKEN=your-strong-random-token
```

## Bot commands

- `!summary` - create thread summary
- `summary` - simple command
- `саммари` - Russian equivalent of `summary`
- `!саммари` - Russian equivalent with exclamation

**⚠️ Important:** Commands with `/` (for example `/summary`) are reserved in Mattermost for slash commands. Use `!summary` or other alternatives above.

## Monitoring

- **Dashboard**: http://localhost:8080
- **Status** (protected API): `curl -H "X-API-Token: $WEB_API_TOKEN" http://localhost:8080/status`
- **API docs**: http://localhost:8080/docs

---

**Done! 🎉** Mattermost Summary Bot is running and ready to summarize your discussions.
