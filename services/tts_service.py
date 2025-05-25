from gtts import gTTS
from telegram import Update
from telegram.ext import ContextTypes
from telegram import Update
from langdetect import detect
from io import BytesIO
from pydub import AudioSegment #library to concatenate audio files
import io
import string
import os
import uuid

async def text_to_speech_when_update(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Create an in-memory file using BytesIO
    audio = BytesIO()
    try:
        user_text = update.message.text
        lang = detect(user_text)
        if lang not in ['en', 'ar']:
            lang = 'ar'  # Arabic as Default

        # Convert text to speech and write to the in-memory file
        tts = gTTS(text=user_text, lang=lang)
        tts.write_to_fp(audio)

    except Exception:
        lang = locals().get('lang', 'ar') #in case language detection failed
        if lang == 'ar':
            tts = gTTS(text="حدث خطأ. حاولوا مرة أخرى", lang="ar")
        else:
            tts = gTTS(text="Sorry, something went wrong. Please try again.", lang="en")
        tts.write_to_fp(audio)

    audio.seek(0) # to start at the beginning of the BytesIO stream
    await update.message.reply_voice(voice=audio)
        


async def text_to_speech(user_text):
    audio = BytesIO()  # Create buffer first

    try:
        lang = detect(user_text)
        tts = gTTS(text=user_text, lang=lang)
        tts.write_to_fp(audio)

    except Exception as e:
        lang = locals().get('lang', 'ar')
        fallback_text = "Sorry, something went wrong. Please try again." if lang == "en" else "حدث خطأ. حاولوا مرة أخرى"
        tts = gTTS(text=fallback_text, lang=lang)
        tts.write_to_fp(audio)

    audio.seek(0)
    return audio

#async def ask_to_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
 #   audio = await text_to_speech("Do you want to reply? (Say 'yes' or 'no')")
  #  await update.message.reply_voice(audio)

async def merge_texts_to_speech(text_en: str, text_ar: str, pause_ms=1000):
    # Convert texts to voice
    voice_en = await text_to_speech(text_en)
    voice_ar = await text_to_speech(text_ar)

    # Load voices into pydub
    sound_en = AudioSegment.from_file(voice_en, format="mp3")
    sound_ar = AudioSegment.from_file(voice_ar, format="mp3")

    # Add pause and merge
    pause = AudioSegment.silent(duration=pause_ms)
    combined = sound_en + pause + sound_ar

    # Export merged audio as .ogg with OPUS codec
    os.makedirs("temp_audio", exist_ok=True)
    output_path = f"temp_audio/{uuid.uuid4().hex}.ogg"
    combined.export(output_path, format="ogg", codec="libopus")

    return output_path
