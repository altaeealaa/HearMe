import os
from dotenv import load_dotenv
import whisper

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN") # Configuration for Telegram Bot from ".env"

#Whisper Model
WHISPER_MODEL = "small"  
model = whisper.load_model(WHISPER_MODEL)


'''# Directory to store temporary files
TEMP_DIR = "./temp"  # Make sure this directory exists, or you can create it dynamically in your code

# Log file configuration (optional, for error logging)
LOG_FILE = "./logs/bot_errors.log"  # Path for storing logs'''
       