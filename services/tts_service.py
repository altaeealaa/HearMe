from gtts import gTTS
from telegram import Update
from telegram.ext import ContextTypes
from telegram import Update
from langdetect import detect
from io import BytesIO
from services.stt_service import speech_to_text

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
    try:
        lang = detect(user_text)
        if lang not in ['en', 'ar']:
            lang = 'ar'  

        audio = BytesIO()

        tts = gTTS(text=user_text, lang=lang)
        tts.write_to_fp(audio)

    except Exception as e:
        lang = locals().get('lang', 'ar')
        if lang == "en":
            tts = gTTS(text="Sorry, something went wrong. Please Try again.", lang="en")
        else:
            tts = gTTS(text="حدث خطأ. حاولوا مرة أخرى", lang="ar")
        tts.write_to_fp(audio)
        
    audio.seek(0)
    return audio
    

async def ask_to_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    audio = await text_to_speech("Do you want to reply? (Say 'yes' or 'no')")
    await update.message.reply_voice(audio)

async def handle_after_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    Yesses = ['Yes.', 'yes', 'Yes', 'اجل', 'نعم']
    Nos = ['No.', 'no', 'No', 'لا', 'كلا']
    if update.message.voice:
        user_response = await speech_to_text(update.message.voice) 
        '''        voice_file = await update.message.voice.get_file()
        await voice_file.download_to_drive("user_reply.ogg")'''
        #print(f'{user_response}')

        if any(yes in user_response for yes in Yesses):
            voice_reply = await text_to_speech("Please send a voice message")
            await update.message.reply_voice(voice_reply)
        elif any(no in user_response for no in Nos):
            voice_reply = await text_to_speech("Okay, no reply needed.")
            await update.message.reply_voice(voice_reply)
        else:
            voice_reply = await text_to_speech("Sorry, I didn't understand. Please say 'yes' or 'no'")
            await update.message.reply_voice(voice_reply)