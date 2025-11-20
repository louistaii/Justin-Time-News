# Justin Time News 📰

An automated daily news podcast generator that fetches Singapore news, creates an AI-powered summary, generates a voiceover, and sends it to Telegram subscribers every day at 8 AM Singapore time!

## Features

- 🗞️ Fetches recent news from Google News RSS feed (Singapore)
- 🤖 AI-powered news summarization using Google's Gemini 2.5 Pro
- 🎙️ Text-to-speech conversion using Gemini TTS with natural voice
- 📱 Automatic delivery to Telegram subscribers
- ⏰ Runs daily at 8 AM Singapore time via GitHub Actions
- 🌏 Timezone-aware for Singapore (UTC+8)

## Technologies Used

- **Python 3.11+**
- **Google Gemini 2.5 Pro** - AI text generation
- **Google Gemini TTS** - Text-to-speech synthesis
- **python-telegram-bot** - Telegram integration
- **feedparser** - RSS feed parsing
- **pydub** - Audio file manipulation
- **GitHub Actions** - Automated scheduling

## License

This project is open source and available under the MIT License.
