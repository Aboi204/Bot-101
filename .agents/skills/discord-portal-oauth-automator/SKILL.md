---
name: discord-portal-oauth-automator
description: >-
  Automates Discord application creation, privileged gateway intent configuration,
  bot token retrieval, and OAuth2 guild invitation via Google Chrome.
  Use when setting up or updating the Discord bot configuration.
---

# Discord Portal OAuth Automator

Setting up a production Discord bot requires interacting with the Discord Developer Portal to configure application metadata, enable privileged gateway intents, obtain bot authentication tokens, and generate OAuth2 bot invitation URLs.

This skill defines the procedures and automated workflows for configuring the bot via Google Chrome sessions.

---

## 1. Application & Intent Configuration

1. **Developer Portal Target**:
   Navigate to [Discord Developer Portal](https://discord.com/developers/applications).
2. **Create/Select Application**:
   - Create a new application named `Free-Music-Bot` or select an existing bot application.
3. **Privileged Gateway Intents**:
   Under the **Bot** tab:
   - Enable **PRESENCE INTENT**
   - Enable **SERVER MEMBERS INTENT**
   - Enable **MESSAGE CONTENT INTENT**
   *(Required for detecting member voice state transitions, command prefixes, and interaction handling).*
4. **Token Generation**:
   - Click **Reset Token** -> Copy token string -> Store securely in `.env` as `DISCORD_TOKEN=...`.

---

## 2. OAuth2 Invitation URL Generation

Generate the bot authorization URL under **OAuth2 -> URL Generator**:
- **Scopes**:
  - `bot`
  - `applications.commands`
- **Bot Permissions** (Integer: `36700160`):
  - View Channels
  - Connect (Voice)
  - Speak (Voice)
  - Use Voice Activity
  - Send Messages
  - Embed Links

Direct invite URL template:
```text
https://discord.com/oauth2/authorize?client_id=<APPLICATION_ID>&permissions=36700160&scope=bot%20applications.commands
```

---

## 3. Chrome Automation / Verification

When running automated browser sessions:
1. Access `https://discord.com/developers/applications` using Chrome user profile.
2. Read application credentials or configure token.
3. Validate bot authorization in test guild.
