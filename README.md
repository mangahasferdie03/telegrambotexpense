# Expense Tracker Telegram Bot

A Python Telegram bot that parses expense information from images, text, and audio using OpenAI's models.

## Features

- 📷 **Image Processing**: Parse receipts and GCash screenshots
- 🎵 **Audio Processing**: Transcribe and parse spoken expense descriptions
- 💬 **Text Processing**: Parse written expense descriptions
- 🇵🇭 **Philippine Timezone**: Automatic date/time in Philippine time
- 💳 **Payment Detection**: Identifies GCash, debit/credit card payments
- 📊 **Structured Output**: Extracts 7 expense fields

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from template:
```bash
cp .env.example .env
```

3. Add your API keys to `.env`:
- Get Telegram Bot Token from [@BotFather](https://t.me/botfather)
- Get OpenAI API Key from [OpenAI Dashboard](https://platform.openai.com/api-keys)

4. Run the bot:
```bash
python main.py
```

## Parsed Fields

1. **Date** - Current date or extracted from receipt
2. **Time** - Current Philippine time or extracted time
3. **Mode of Payment** - GCash, debit card, credit card, or cash
4. **Source** - Business/merchant name with proper capitalization
5. **Category** - Expense category (Food, Transportation, etc.)
6. **Amount** - Expense amount with comma formatting
7. **Notes** - Summary with proper grammar

## Usage

Send the bot:
- Receipt images or GCash screenshots
- Voice messages describing expenses
- Text descriptions of expenses

The bot will respond with structured expense data.