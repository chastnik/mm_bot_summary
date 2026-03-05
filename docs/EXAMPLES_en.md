# 📝 Usage Examples

## Thread example

**Original discussion:**

```
alice: Hi team! We need to discuss a new feature in the project
bob: Hi! What feature are we talking about?
alice: We want to add data export to Excel
charlie: Sounds interesting. What are the requirements?
alice: Users should be able to export tables in .xlsx format
bob: Which tables? All of them or specific ones?
alice: For now, only sales and user reports
charlie: Got it. I can take the backend part
bob: And I'll build the export button UI
alice: Great! Deadline is 2 weeks. Charlie, use openpyxl
charlie: Deal. Let's meet on Friday for review
```

**Command:** `!summary`

**Result:**

```
## 📝 Thread Summary

**👥 Participants:**
alice, bob, charlie

**💬 Main topics:**
Discussion of a new Excel data export feature for the project

**📋 Key points:**
• Need to export tables to .xlsx format
• Export is required for sales and user reports only
• openpyxl will be used for implementation
• Tasks were split between team members

**✅ Tasks and actions:**
• Charlie - backend export implementation
• Bob - UI with export button
• Deadline: 2 weeks
• Friday review meeting

**🎯 Outcome:**
The team agreed on a technical approach for Excel export, distributed responsibilities, and set project timelines.
```

## Supported commands

| Command | Description | Example |
|---------|-------------|---------|
| `!summary` | Main command | `!summary` |
| `summary` | Simple command | `summary` |
| `саммари` | Russian equivalent of `summary` | `саммари` |
| `!саммари` | Russian equivalent with exclamation | `!саммари` |

**⚠️ Important:** Commands with `/` (for example `/summary`) are reserved by Mattermost for system slash commands and return `Command not found`. Use commands with `!` or without symbols.

## When to use

✅ **Good scenarios for summaries:**
- Long project discussions
- Meetings and brainstorming sessions
- Technical discussions
- Task planning
- Decision making

❌ **Not suitable for:**
- Very short threads (1-2 messages)
- Private one-to-one chats
- Spam or meaningless messages

## Summary structure

The bot always creates a structured summary with sections:

1. **👥 Discussion participants** - list of all thread participants
2. **💬 Main discussion topics** - short topic overview
3. **📋 Key points** - important facts and conclusions
4. **✅ Tasks and actions** - concrete tasks and agreements
5. **🎯 Outcome** - overall conclusion

## Usage tips

🎯 **For best results:**
- Use the command at the end of a discussion
- Make sure the thread has meaningful content
- The bot works only in channels where it is added

🔧 **If the summary is inaccurate:**
- Check bot status in the web interface
- Make sure the LLM service is available
- Restart the bot if needed

## Monitoring and debugging

- **Web interface**: http://localhost:8080
- **Health check**: `curl http://localhost:8080/health`
- **Docker logs**: `docker-compose logs -f summary-bot`
