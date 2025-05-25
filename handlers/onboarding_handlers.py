from telegram import Update
from telegram.ext import ContextTypes
from database.database_functions import add_user, update_user_role, update_user_language
from services.tts_service import text_to_speech, merge_texts_to_speech
from handlers.helper_functions import fuzzy_language_match
from database.database_setup import cursor
import os


# Handle /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    cursor.execute("""
    SELECT language FROM users
    WHERE user_id = %s
    """, (user_id,))

    result = cursor.fetchone() 

    # Check if the language is set
    if result is not None and result[0] not in (None, ''):
        if result[0] == 'english':
            await update.message.reply_voice(await text_to_speech("You already clicked start and set the language, you can say 'settings' to change it"))
        else:
            await update.message.reply_voice(await text_to_speech("لقد حدّدت اللغة مسبقًا، لتغييرها يمكنك قول settings"))

    else:
        # New user: start with language selection
        file_path = await merge_texts_to_speech("Welcome to HearMe! Please specify your preferred language: Arabic or English.", "أهلًا بكم! الرجاء اختيار اللغة المفضّلة لديكم: العربية أو الانجليزية")  # merging the arabic and english voices
        
        with open(file_path, "rb") as voice:
            await update.message.reply_voice(voice)
        
        # ✅ Clean up temporary file after sending
        try:
            os.remove(file_path)
        except OSError as e:
            print(f"[ERROR] Failed to delete temp voice file: {e}")
            
        context.user_data["awaiting_language"] = True


# Handle language reply
async def reply_after_language(update: Update, context: ContextTypes.DEFAULT_TYPE, normalized_text):
    if not context.user_data.get("awaiting_language"):
        return 
    
    user_id = update.message.from_user.id

    print(f"[DEBUG] Transcribed normalized_text: {normalized_text}")

    matched_language = fuzzy_language_match(normalized_text, ["arabic", "english", "عربية", "انكليزية", "أربك", "Inglisia"])

    if matched_language is None:
        file_path = await merge_texts_to_speech("I didn't understand. Please say Arabic or English.", "لم أفهم، الرجاء قول عربية أو انجليزية ")  # merging the arabic and english voices
        
        with open(file_path, "rb") as voice:
            await update.message.reply_voice(voice)
        return
    
    if matched_language == "عربية" or matched_language == "أربك" or matched_language == "arabic":
        language = "arabic"
    if matched_language == "انكليزية" or matched_language == "Inglisia" or matched_language == "english":
        language = "english"

    # Save language and move to role selection
    context.user_data["language"] = language
    context.user_data["awaiting_language"] = False


    # --- SETTINGS MODE ---
    if context.user_data.get("settings_mode"):
        update_user_language(user_id, language)
        context.user_data.clear()
        if language == "english":
            await update.message.reply_voice(await text_to_speech("Your language has been updated successfully."))
        if language == "arabic":
            await update.message.reply_voice(await text_to_speech("تم تحديث لغتك بنجاح."))
        return
    
    # Save language and move to role selection
    context.user_data["language"] = language
    context.user_data["awaiting_language"] = False

    # New user setup: Add to DB and prompt for role
    user_id = update.message.from_user.id
    name = update.message.from_user.full_name
    username = update.message.from_user.username
    role = ""  # Not set yet
    add_user(user_id, name,username, role, language)

    if language == 'english':
        await update.message.reply_voice(await text_to_speech("Thank you. Now please say if you are blind or sighted."))
    else:
        await update.message.reply_voice(await text_to_speech("شكرًا لكم. الرجاء تحديد الصفة، اذا كنت أعمى أو بصير"))

    context.user_data["awaiting_role"] = True
    





# Handle role reply
async def set_role(update: Update, context: ContextTypes.DEFAULT_TYPE, normalized_text):
    if not context.user_data.get("awaiting_role"):
        return 
    
    user_id = update.message.from_user.id
    language = context.user_data.get("language", "unknown")  # If the key does not exist, "unknown" is returned as a fallback

    cursor.execute("""
    SELECT role FROM users
    WHERE user_id = %s
    """, (user_id,))

    result = cursor.fetchone()

    # Check if the role is already set
    if result is not None and result[0] not in (None, ''):
        if language == "english":
            await update.message.reply_voice(await text_to_speech("You have already clicked start and set the role, you can say 'settings' to change it"))
        else:
            await update.message.reply_voice(await text_to_speech("لقد تمّ تحديد الصفة سابقًا من قبلك. لتغييرها، قل setting "))
   
    print(f"[DEBUG] Transcribed text: {normalized_text}")

    matched_role = fuzzy_language_match(normalized_text, ["blind", "sighted", "أعمى", "بصير", "basir"])

    if matched_role is None:
        if language == "english":
            await update.message.reply_voice(await text_to_speech("I didn't understand. Please say 'blind' or 'sighted'."))
        else:
            await update.message.reply_voice(await text_to_speech("لم أفهم، الرجاء قول أعمى أو بصير"))
        return
    

    # ✅ Assign the role before using it
    if matched_role in ["blind", "sighted"]:
        role = matched_role
    elif matched_role in ["أعمى"]:
        role = "blind"
    else:
        role = "sighted"

    # English confirmation
    if language == "english":
        if role == "blind":
            confirmation = (
                f"Your role is set to {role.capitalize()} and language to {language.capitalize()}.\n"
                f"Here are the voice commands you can use:\n"
                f"- 'group' to hear available groups\n"
                f"- 'check' to listen to your new messages\n"
                f"- 'switch to' + group name to change groups\n"
                f"- 'help' to hear these instructions again\n"
                f"- 'settings' to change your language.\n"
                f"Speak naturally. I’m listening!"
            )
        else:
            confirmation = (
                f"Your role is set to {role.capitalize()} and language to {language.capitalize()}.\n"
                f"If you want to communicate with a blind user, add me to a group with them.\n"
                f"Then, send a message and type the command:\n"
                f"/addblind @username for each blind user in the group.\n"
                f"I will convert your messages to voice and deliver them.\n"
                f"Otherwise, I have no features to offer.\n"
                f"Thanks for trying me!"
            )
    
    # Arabic confirmation
    else:
        if role == "blind":
            confirmation = (
                f"يمكنك استعمال هذه الكلمات المفتاحية:\n"
                f"- 'group' لتعرف المجموعات التي دخلت فيها\n"
                f"- 'check' لتسمع الرسائل الجديدة\n"
                f"- 'switch to' لتغيير المجموعة\n"
                f"- 'help' لسماع هذه الإرشادات\n"
                f"- 'settings' لتغيير اللغة\n"
                f"تحدث كما تشاء، أنا هنا لأساعدك!"
            )
        else:
            confirmation = (
                f"اذا أردت التواصل مع شخص أعمى من خلالي، زدني على مجموعة بينكما.\n"
                f"سأتكفّل بتحويل رسائلك إلى تسجيلات صوتية.\n"
                f"ثم أرسل رسالة في المجموعة واكتب الأمر:\n"
                f"/addblind @username لكل مستخدم أعمى موجود في المجموعة.\n"
                f"غير ذلك، لا أملك ميزات مخصصة لك.\n"
                f"شكرًا لتعاونك!"
            )

    # ✅ Save to database
    update_user_role(user_id, role)

    # ✅ Clear flags
    context.user_data.clear()

    await update.message.reply_voice(await text_to_speech(confirmation))
    