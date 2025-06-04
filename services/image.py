import os
import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from telegram import Update
from telegram.ext import ContextTypes 
from database.database_functions import save_group, save_group_message

# Load BLIP model once
device = "cuda" if torch.cuda.is_available() else "cpu"
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", use_fast=True)
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        #await update.message.reply_text("⏳ Processing image, please wait...")

        photo_file = await update.message.photo[-1].get_file()
        image_path = f"{update.message.message_id}_image.jpg"
        await photo_file.download_to_drive(image_path)

        # Generate caption
        image = Image.open(image_path).convert("RGB")
        inputs = processor(image, return_tensors="pt").to(device)
        output = model.generate(**inputs)
        caption = processor.decode(output[0], skip_special_tokens=True)
        await update.message.reply_text(f"🖼 Caption: {caption}")

        # Save to DB
        group_name = update.effective_chat.title
        group_id = update.effective_chat.id
        sender = update.message.from_user
        sender_name = sender.full_name
        image_caption = f"sent an image containing {caption}"
        save_group(group_id, group_name)
        save_group_message(group_id, group_name, sender.id, sender_name, image_caption)
        print(f"[SAVED] From {sender_name} in Group {group_name}:{sender_name} sent an image contaning {caption}")

    except Exception as e:
        await update.message.reply_text("⚠️ Sorry, something went wrong processing the image.")
        print(f"[ERROR] {e}")

    finally:
        if os.path.exists(image_path):
            os.remove(image_path)
        #if os.path.exists(voice_path):
            #os.remove(voice_path)


