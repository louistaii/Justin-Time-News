import feedparser
import wave
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import pytz
import requests
import base64
from telegram import Bot
import asyncio
from pydub import AudioSegment
import io
import os

# --- CONFIGURATION ---
RSS_URL = "https://news.google.com/rss/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRFZxYUdjU0JXVnVMVWRDR2dKVFJ5Z0FQAQ?hl=en-SG&gl=SG&ceid=SG%3Aen"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:{action}"
API_KEY = os.environ.get("GEMINI_API_KEY")

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")

# Debug mode: Set to True to save audio file instead of sending
DEBUG_MODE = False  # Change to True to save file for testing

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not set. Please set it to your API key.")


# ---------------------------
#  STEP 1: GET RECENT NEWS
# ---------------------------
def get_recent_items(url):
    """Parses an RSS feed and returns items from today and yesterday."""
    feed = feedparser.parse(url)
    sg_tz = pytz.timezone('Asia/Singapore')
    today = datetime.now(sg_tz).date()
    yesterday = today - timedelta(days=1)

    items = []
    for entry in feed.entries:
        if "published" not in entry:
            continue

        published_dt = date_parser.parse(entry.published).date()
        if published_dt < yesterday:
            continue

        items.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published
        })

    return items


# -----------------------------------
#  STEP 2: SUMMARIZE NEWS WITH GEMINI PRO
# -----------------------------------
def summarize_news_with_gemini(news_items):
    """
    Summarizes a list of news titles in a friendly and entertaining way using Gemini 2.5 Pro.
    """
    if not news_items:
        return "There are no recent news updates to summarize."

    # Build a prompt that instructs the model on the desired tone and format.
    prompt_lines = [
        "Your role is to act as 'Justin', the host of a daily news podcast called 'Justin Time News'. Your persona is witty, friendly, and you make the news feel approachable and engaging for a general audience.",
        "Your task is to create a short, conversational monologue summarizing today's top headlines for a voiceover script. The total length should be under 700 words to keep it brief and punchy.",
        "\nHere are the instructions for the script:",
        "- Start with a warm and energetic welcome.",
        "- Transition smoothly between headlines, connecting them where possible.",
        "- Use a conversational, slightly informal tone. Think of how you would tell a friend about the news.",
        "- Do NOT include any text outside of the monologue itself. No 'Sure, here is the script:', no notes, no headers, just the pure script ready for recording.",
        "- Do NOT include any stage directions, sound effects, or music cues like '(Upbeat music)', '(laughs)', or '(pause)'. Only include the spoken words.",
        "- End with a friendly sign-off, like 'That's the latest for now. Catch you tomorrow!'",
        "\nHere are today's headlines to summarize:",
    ]

    for item in news_items:
        prompt_lines.append(f"- {item['title']}")
    
    summarization_prompt = "\n".join(prompt_lines)

    # Set up the API call to Gemini 2.5 Pro for text generation
    model_name = "gemini-2.5-pro"  # Model for text generation
    action = "generateContent"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": summarization_prompt
                    }
                ]
            }
        ]
    }

    url = GEMINI_API_URL.format(model=model_name, action=action) + f"?key={API_KEY}"
    
    headers = {
        'Content-Type': 'application/json'
    }

    print("Sending request to Gemini 2.5 Pro for summarization...")
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Gemini API error ({response.status_code}): {response.text}")

    try:
        response_json = response.json()
        summary = response_json["candidates"][0]["content"]["parts"][0]["text"]
        return summary
    except (KeyError, IndexError) as e:
        raise Exception(f"Could not find summary in the API response: {response.json()}") from e


# ----------------------------------
#  STEP 3: GENERATE TTS WITH GEMINI
# ----------------------------------
def generate_tts(text_prompt): 
    """
    Generates speech from text using the Gemini TTS API and returns the audio bytes.
    """
    # Set up the API call for Text-to-Speech
    model_name = "gemini-2.5-flash-preview-tts" # Model for TTS
    action = "generateContent"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": text_prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Umbriel" #Laomedeia for female
                    }
                }
            }
        }
    }

    url = GEMINI_API_URL.format(model=model_name, action=action) + f"?key={API_KEY}"
    
    headers = {
        'Content-Type': 'application/json'
    }

    print("Sending request to Gemini TTS API...")
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(f"TTS API error ({response.status_code}): {response.text}")

    try:
        response_json = response.json()
        audio_b64 = response_json["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError) as e:
        raise Exception(f"Could not find audio content in the API response: {response.json()}") from e

    audio_bytes = base64.b64decode(audio_b64)
    
    # Convert to WAV first, then to MP3 for smaller size
    sample_rate = 24000
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1) 
        wav_file.setsampwidth(2)  
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_bytes)
    
    # Convert WAV to MP3
    wav_buffer.seek(0)
    audio = AudioSegment.from_wav(wav_buffer)
    
    mp3_buffer = io.BytesIO()
    audio.export(mp3_buffer, format="mp3", bitrate="64k")  # 64kbps is good for speech
    
    mp3_data = mp3_buffer.getvalue()
    size_mb = len(mp3_data) / (1024 * 1024)
    print(f"Audio generated successfully ({size_mb:.2f} MB MP3)")
    return mp3_data


# ----------------------------------
#  STEP 4: FORMAT NEWS AS TEXT MESSAGE
# ----------------------------------
def format_news_text(news_items):
    """
    Formats news items as a nicely structured text message with hyperlinks.
    """
    if not news_items:
        return "No recent news available."
    
    sg_tz = pytz.timezone('Asia/Singapore')
    sg_date = datetime.now(sg_tz).strftime('%B %d, %Y')
    
    message_lines = [
        "📰 <b>Justin Time News - Latest Headlines</b>",
        f"📅 {sg_date}",
        ""
    ]
    
    for idx, item in enumerate(news_items, 1):
        # Format each news item with hyperlink
        message_lines.append(f"<b>{idx}.</b> <a href='{item['link']}'>{item['title']}</a>")
        message_lines.append("")  # Empty line for spacing
    
    message_lines.append("\n🎙️ Listen to the full audio summary below!")
    
    return "\n".join(message_lines)


# ----------------------------------
#  STEP 5: SEND TEXT AND AUDIO VIA TELEGRAM
# ----------------------------------
async def send_to_subscribers(audio_data, news_items, chat_ids):
    """
    Sends formatted news text and audio data to multiple Telegram chats.
    """
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    news_text = format_news_text(news_items)
    
    print(f"\n📝 Text message to send ({len(news_text)} characters):")
    print("=" * 80)
    print(news_text)
    print("=" * 80)
    
    for chat_id in chat_ids:
        try:
            # First send the text message with news links
            #await bot.send_message(
             #   chat_id=chat_id,
             #   text=news_text,
             #  parse_mode='HTML',
             # disable_web_page_preview=True
            #)
            #print(f"✅ News text sent to chat ID: {chat_id}")
            
            # Then send the audio
            from io import BytesIO
            audio_stream = BytesIO(audio_data)
            audio_stream.name = 'news_update.mp3'
            
            # Format the date for the title (Singapore timezone)
            sg_tz = pytz.timezone('Asia/Singapore')
            date_str = datetime.now(sg_tz).strftime('%B %d, %Y')
            
            await bot.send_audio(
                chat_id=chat_id,
                audio=audio_stream,
                title=f"{date_str} Update",
                performer="Justin Time News",
                caption="🎙️ Here's your daily news update from Justin!",
                read_timeout=60,
                write_timeout=60
            )
            print(f"✅ Audio sent successfully to chat ID: {chat_id}")
        except Exception as e:
            print(f"❌ Failed to send to {chat_id}: {e}")


# ---------------------------
#  MAIN SCRIPT
# ---------------------------
if __name__ == "__main__":
    print("Fetching recent news...")
    news_items = get_recent_items(RSS_URL)

    if news_items:
        # Summarize the news first
        summary = summarize_news_with_gemini(news_items)
        print("\nGenerated summary for TTS:\n")
        print(summary)

        # Generate voiceover from the summary
        print("\nGenerating voiceover with Gemini TTS...")
        audio_data = generate_tts(summary)
        
        # Debug mode: Save file or send via Telegram
        if DEBUG_MODE:
            # Save to file for testing
            output_file = "news_update_debug.mp3"
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"\n✅ Debug mode: Audio saved to {output_file}")
        else:
            # Send audio via Telegram Channel
            if TELEGRAM_CHANNEL_ID:
                print(f"\nSending news to channel {TELEGRAM_CHANNEL_ID}...")
                asyncio.run(send_to_subscribers(audio_data, news_items, [TELEGRAM_CHANNEL_ID]))
            else:
                print("\n⚠️ TELEGRAM_CHANNEL_ID is not set. Please set it in your environment variables.")
    else:
        print("No recent news found to process.")