# 🔧 Troubleshooting

## Dependency issues

### ModuleNotFoundError: No module named 'uvicorn'

**Solution:**
```bash
pip install -r requirements.txt
```

If dependency conflicts appear:
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Package version conflicts

**Cause:** outdated pinned versions in `requirements.txt`.

**Solution:** install dependencies from the current `requirements.txt`:
```
fastapi>=0.100.0
uvicorn>=0.23.0
requests>=2.31.0
websockets>=11.0.0
python-dotenv>=1.0.0
pytz>=2023.3
openai
```

## LLM connection issues

### ❌ Error: "Not allowed"

**Cause:** token or LLM settings issue.

**Check:**
1. LLM token is valid
2. Service URL is correct
3. Service is available

**Update `.env` settings:**
```env
LLM_PROXY_TOKEN=your-actual-token
LLM_BASE_URL=https://litellm.1bitai.ru
LLM_MODEL=gpt-5
```

### ❌ Error: "Connection error"

**Cause:** network issue or unavailable service.

**Check:**
```bash
# Availability check
curl -I https://litellm.1bitai.ru

# curl test
curl -X POST https://litellm.1bitai.ru/chat/completions \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5",
    "messages": [{"role": "user", "content": "test"}],
    "max_tokens": 10
  }'
```

## Mattermost issues

### ❌ Bot does not respond to commands

**Check:**
1. Bot is added to the channel: `/invite @summary-bot`
2. Token in `.env` is correct
3. Bot status in Mattermost Admin Console

**Enable debug mode:**
```env
DEBUG=true
```

### ❌ Mattermost connection error

**DNS resolution error (Failed to resolve 'https'):**
- Problem with URL parsing in `mattermostdriver`
- Ensure URL format is correct
- Check server availability: `ping your-mattermost.com`

**Check `.env`:**
```env
MATTERMOST_URL=https://your-mattermost.com  # without trailing /
MATTERMOST_TOKEN=your-bot-token
```

**Create bot in Mattermost:**
1. System Console → Integrations → Bot Accounts
2. Enable Bot Account Creation = True
3. Create Bot Account
4. Copy Access Token

## Docker issues

### ❌ Container does not start

**Check `.env` file:**
```bash
# Ensure file exists
ls -la .env

# Check content
cat .env
```

**Rebuild container:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**View logs:**
```bash
docker-compose logs -f summary-bot
```

## General issues

### ❌ Web interface is unavailable

**Check:**
- Port 8080 is free: `netstat -tulpn | grep 8080`
- Firewall settings
- Bot is running: `docker-compose ps`

### ❌ Bot creates inaccurate summaries

**Possible causes:**
1. LLM service issues
2. Thread is too short (less than 3 messages)
3. Poor quality source messages

**Solutions:**
- Check LLM status: `curl -H "X-API-Token: $WEB_API_TOKEN" http://localhost:8080/status`
- Use summary command in content-rich threads
- Restart bot: `curl -X POST http://localhost:8080/restart`

## Diagnostic commands

### Status checks
```bash
# Web interface
curl http://localhost:8080/health

# Detailed status
curl -H "X-API-Token: $WEB_API_TOKEN" http://localhost:8080/status

# Logs
docker-compose logs -f summary-bot
```

### Component tests
```bash
# Tests
python -m unittest discover -s tests -p "test*.py"

# Import test
python -c "from main import *; print('OK')"

# Dependency check
pip check
```

### Reset and cleanup
```bash
# Stop and remove containers
docker-compose down --volumes

# Remove images
docker image prune -a

# Reinstall dependencies
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

## Support

If issues persist:

1. **Collect information:**
   - Logs: `docker-compose logs summary-bot > bot-logs.txt`
   - Config: `cat .env` (without tokens!)
   - Python version: `python --version`
   - Status: `curl -H "X-API-Token: $WEB_API_TOKEN" http://localhost:8080/status`

2. **Check known issues** in repository Issues

3. **Create a new Issue** with collected information
