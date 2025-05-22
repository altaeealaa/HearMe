import os
import uuid
import whisper
from telegram import Update
from telegram.ext import ContextTypes
from config import model


async def speech_to_text(voice):
    file = await voice.get_file()

    filename = uuid.uuid4().hex # Creating unique filename for each voice message
    ogg_path = f"{filename}.ogg"
    wav_path = f"{filename}.wav"

    try:
        # Download OGG voice message
        await file.download_to_drive(ogg_path)

        # Convert .ogg to .wav
        os.system(f"ffmpeg -i {ogg_path} -ar 16000 -ac 1 -c:a pcm_s16le {wav_path}")

        # Transcribe audio
        result = model.transcribe(wav_path)
        return result["text"]

    except Exception as e:
        text = f"Error happened in converting the text: {e}"
        return text

    finally:
        # Cleanup
        if os.path.exists(ogg_path): os.remove(ogg_path)
        if os.path.exists(wav_path): os.remove(wav_path)


'''async def speech_to_text_when_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    file = await voice.get_file()

    filename = uuid.uuid4().hex # Creating unique filename for each voice message
    ogg_path = f"{filename}.ogg"
    wav_path = f"{filename}.wav"

    try:
        # Download OGG voice message
        await file.download_to_drive(ogg_path)

        # Convert .ogg to .wav
        os.system(f"ffmpeg -i {ogg_path} -ar 16000 -ac 1 -c:a pcm_s16le {wav_path}")

        # Transcribe audio
        result = transcribe(wav_path)
        return result["text"]

    except Exception as e:
        text = "Error happened in converting the text: {e}"
        return None

    finally:
        # Cleanup
        if os.path.exists(ogg_path): os.remove(ogg_path)
        if os.path.exists(wav_path): os.remove(wav_path)
'''