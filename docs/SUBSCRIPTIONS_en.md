# 📊 Channel Subscriptions

## Overview

Starting from version 2.1, Mattermost Summary Bot supports **channel subscriptions** - the ability to receive regular activity summaries for selected channels directly in direct messages.

## ✨ Features

- 📅 **Regular summaries** - daily or weekly
- 🎯 **Personalization** - each user manages their own subscriptions
- 📱 **Convenient management** - via direct messages with the bot
- 🔔 **Automatic delivery** - on schedule at the specified time
- 🛡️ **Access validation** - notifications for unavailable channels

## 🚀 Quick Start

### 1. First message to the bot

Send the bot **any direct message** - it will reply with detailed instructions.

### 2. Create a subscription

Send a message using natural language:
```
~channel1, ~channel2 frequency at time
```

**Examples:**
```
~general, ~random every day at 9 AM
~development, ~qa weekly on Tuesdays at 18:00
~marketing every day at 15:30
~support weekly on Fridays at 10:00
```

💡 **Important:** In Mattermost, the `~` symbol is required for channel selection.

### 3. Receive summaries

Summaries will be delivered automatically to direct messages at the specified time.

**For weekly subscriptions:** If you set a weekday (for example, "on Wednesdays at 15:00"), you receive a summary for the whole week from the previous Wednesday 15:00 to the current Wednesday 15:00.

**For daily subscriptions:** You receive a summary for the last 24 hours.

## 📋 Management commands

### In direct messages with the bot:

These command keywords are intentionally shown in Russian because this is the currently supported command set.

| Command | Description |
|---------|-------------|
| `подписки` | "subscriptions" - view current subscriptions |
| `мои подписки` | "my subscriptions" - alternative command |
| `посмотреть подписки` | "show subscriptions" - alternative command |
| `удалить подписку` | "delete subscription" - delete all subscriptions |
| `удалить подписки` | "delete subscriptions" - alternative command |
| `отписаться` | "unsubscribe" - alternative command |
| `создать подписку` | "create subscription" - show setup instructions |

## 📝 Subscription format

```
~channels frequency at time
```

### Parameters:

#### **Channels**
- Use the `~` symbol before each channel name
- Separate multiple channels with commas and spaces
- Examples: `~general`, `~general, ~random, ~development`

#### **Frequency**
- `ежедневно` or `каждый день` (daily / every day)
- `еженедельно` or `каждую неделю` (weekly / every week)
- `еженедельно по средам` or `каждую неделю по пятницам` (weekly on Wednesday / weekly on Friday)

#### **Time**
- `в 9 утра` or `в 09:00` (at 9 AM / at 09:00)
- `в 18:00` or `в 6 вечера` (at 18:00 / at 6 PM)
- `в 15:30` (at 15:30)

#### **Weekdays (for weekly subscriptions)**
- `по понедельникам`, `по вторникам`, `по средам`, `по четвергам` (on Mondays, Tuesdays, Wednesdays, Thursdays)
- `по пятницам`, `по субботам`, `по воскресеньям` (on Fridays, Saturdays, Sundays)

### Command examples:

```bash
# Daily summary at 9 AM
~general, ~development ежедневно в 9 утра

# Weekly summary on Mondays at 18:00
~marketing, ~sales еженедельно по понедельникам в 18:00

# Weekly summary on Wednesdays at noon
~general, ~random, ~development еженедельно по средам в 12:00

# Simple single-channel weekly subscription on Fridays
~support еженедельно по пятницам в 10:00
```

## 🔧 Requirements

### For subscriptions to work:

1. **Use `~` for channels**: In Mattermost, `~` is required for channel autocomplete and proper bot recognition
2. **Bot must be added** to all channels in the subscription
3. **Command to add bot:** `/invite @bot_username`
4. **Access check:** bot validates permissions automatically

### Why `~` matters:

- 🔍 **Autocomplete**: when typing `~general`, Mattermost suggests available channels
- 🎯 **Accurate recognition**: the bot clearly identifies channel names
- ✅ **Mattermost standard**: follows standard channel mention format

### If the bot is not in the channel:

You will get a notification with instructions:
```
❌ Bot cannot access the following channels:
• ~general
• ~random

What to do:
1. Add the bot to these channels using /invite @bot_username
2. Create the subscription again

💡 Important: In Mattermost, the ~ symbol is required for channel selection!
```

## 📊 Summary format

Summaries include:

### 📈 Header
- **Daily channel summary** or **Weekly channel summary**
- List of channels with message counts
- Total number of processed messages

### 🔥 Main sections
- **Most active discussions**
- **Active participants**
- **Key topics and decisions**
- **Interesting links and files**
- **Short conclusions**

### Summary example:
```
📊 Daily channel summary

Channels:
• general (15 messages)
• development (8 messages)

Total messages: 23

---

🔥 Most active discussions:
• Discussion of new API capabilities in #general
• Database issue resolution in #development

👥 Active participants:
• john_doe (10 messages)
• jane_smith (7 messages)

📋 Key topics and decisions:
• Decision made to migrate to a new version
• Team meeting scheduled for tomorrow

💡 Short conclusions:
Active technical discussions, team is ready for upcoming tasks
```

## 🌍 Time zones

- **Default:** Europe/Moscow
- **Support:** timezone customization is planned in future versions

## 🚨 Error handling

### Unavailable channels
If the bot cannot access a channel:
- User receives a notification
- Unavailable channels are listed
- Suggested resolution is provided

### No new messages
If there are no new messages in tracked channels:
```
📊 Channel summary

Channels:
• general
• random

ℹ️ No new messages in tracked channels for the last 24 hours.
```

### Generation errors
If there are issues with the AI service:
```
❌ Failed to generate summary.
Please check AI service availability and try again later.
```
