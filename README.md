# Auto Bot: Telegram -> LinkedIn AI Post Generator

## Quick start

1. Create virtual environment and install deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment:

```bash
cp .env.example .env
```

3. Run bot:

```bash
python3 main.py
```

## Telegram commands

- `/start` - fetch IT news and generate LinkedIn post
- `/help` - show available commands
- `/linkedin_auth` - start LinkedIn OAuth 2.0 flow
- `/linkedin_code <code | callback_url>` - exchange code and store OAuth token
- `/linkedin_status` - check current token source

## LinkedIn OAuth notes

- Set `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`.
- Run `/linkedin_auth` in Telegram.
- Complete authorization in browser.
- Copy `code` from callback URL and send `/linkedin_code <code>`.
- Stored OAuth token is saved to `.data/linkedin_token.json` by default.

## Required env vars

- `TELEGRAM_BOT_TOKEN`
- `QWEN_API_KEY`
- `LINKEDIN_PERSON_ID`

Use either:
- `LINKEDIN_ACCESS_TOKEN` (static token), or
- OAuth flow commands above.
# auto_bot
