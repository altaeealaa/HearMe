from telegram import Update
from telegram.ext import ContextTypes
from database.database_functions import get_user_role, get_preffered_language, get_user_language
from database.database_setup import cursor
from services.tts_service import text_to_speech
from services.stt_service import speech_to_text
from handlers.helper_functions import fuzzy_language_match, normalize_text
from handlers.group_handlers import handle_group_message, handle_after_ask, handle_voice_reply, handle_group_choice, handle_switch_to_command
from handlers.onboarding_handlers import set_role, reply_after_language

# --- Voice Handler ---
async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("[DEBUG] voice_handler triggered")

    try:
        voice = update.message.voice
        if not voice:
            return  # Not a voice message

        user_id = update.message.from_user.id
        chat_type = update.message.chat.type

        transcribed = await speech_to_text(voice)
        print(f"[DEBUG] Voice transcribed: {transcribed}")
        normalized = normalize_text(transcribed)

        #if context.user_data.get("awaiting_language", True):  # Default to True if not set
            #await reply_after_language(update, context, normalized)
            #return

        #if context.user_data.get("awaiting_role", True):  # Default to True if not set
            #await set_role(update, context, normalized)
            #return

        role = get_user_role(user_id)
        # Fuzzy keyword lists for commands (English & Arabic)
        check_keywords = ["check", "شيك", "تحقق", "/check"]
        group_keywords = ["group", "/group", "مجموعة"]
        switch_keywords = ["switch to", "انتقل الى", "حول الى", "انتقل إلى"]
        help_keywords = ["help", "مساعدة"]
        settings_keywords = ["settings", "اعدادات"]


        if context.user_data.get("awaiting_language"):
                await reply_after_language(update, context, normalized)
        elif context.user_data.get("awaiting_role"):
                await set_role(update, context, normalized)


        # Handle commands only for blind users in private chat
        elif role == "blind" and chat_type == "private":
            matched_check = fuzzy_language_match(normalized, check_keywords)
            matched_group = fuzzy_language_match(normalized, group_keywords)
            matched_switch = fuzzy_language_match(normalized, switch_keywords)
            matched_help = fuzzy_language_match(normalized, help_keywords)
            matched_settings = fuzzy_language_match(normalized, settings_keywords)


            
            if matched_check:
                print("[DEBUG] Voice command matched: /check")
                await check_messages(update, context)
                return
            elif context.user_data.get("awaiting_group_choice"):
                await handle_group_choice(update, context)
            elif matched_switch or normalized.startswith("switch to"):
                print("[DEBUG] Voice command matched: switch to")
                handled = await handle_switch_to_command(update, context, normalized)
                if handled:
                    return
            elif matched_group:
                print("[DEBUG] Voice command matched: /group")
                await group_command(update, context)
                return
            elif matched_help:
                print("[DEBUG] Voice command matched: /help")
                await handle_help_command(update, context)
                return
            elif matched_settings:
                print("[DEBUG] Voice command matched: /settings")
                await handle_settings_command(update, context)
                return
            elif context.user_data.get("awaiting_yes_no_reply"):
                context.user_data["awaiting_yes_no_reply"] = False
                await handle_after_ask(update, context)
            elif context.user_data.get("awaiting_group_reply"):
                await handle_voice_reply(update, context)
                context.user_data["awaiting_group_reply"] = False                      
            else:
                print(f"[DEBUG] Unmatched voice command: {normalized}")
                await update.message.reply_voice(
                    await text_to_speech("Unexpected Input. Please use a command or follow the instructions.")
                )

        elif chat_type in ["group", "supergroup"]:
            await handle_group_message(update, context)

        else:
            print("[DEBUG] Voice message from non-blind user in private — ignoring.")

    except Exception as e:
        print(f"[ERROR] Failed in voice_handler: {e}")
        await update.message.reply_voice(
            await text_to_speech("There was a problem understanding your voice. Try again.")
        )


# to get all available groups
async def group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Get user's preferred language
    language = get_preffered_language(user_id) or "english"

    cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if not result or result[0] != 'blind':
        if language == "arabic":
            await update.message.reply_text("هذا الأمر متاح فقط للمستخدمين المكفوفين.")
        else:
            await update.message.reply_text("This command is only for blind users.")
        return
    
    cursor.execute('''SELECT group_name FROM groups''')
    groups = cursor.fetchall()

    if groups:
        group_names_list = [group[0] for group in groups]
        if language == "arabic":
            group_names = "هذه هي المجموعات: " + "، ".join(group_names_list)
        else:
            group_names = "Here are the groups: " + ", ".join(group_names_list)
        print(f"[DEBUG] Available groups: {group_names}")
        
        # Convert the group list into speech and send it
        voice_message = await text_to_speech(group_names)
        await update.message.reply_voice(voice_message)
    else:
        if language == "arabic":
            msg = "لا توجد مجموعات في قاعدة البيانات."
        else:
            msg = "No groups found in the database."
        print("[DEBUG] No groups found in the database.")
        voice_message = await text_to_speech(msg)
        await update.message.reply_voice(voice_message)

    context.user_data["awaiting_group_choice"] = True


# to check for new messages
async def check_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Get user's preferred language
    language = get_preffered_language(user_id) or "english"

    cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if not result or result[0] != 'blind':
        if language == "arabic":
            await update.message.reply_voice(await text_to_speech("هذا الأمر متاح فقط للمستخدمين المكفوفين."))
        else:
            await update.message.reply_voice(await text_to_speech("This command is only for blind users."))
        return
    
    cursor.execute("""
        SELECT DISTINCT group_name 
        FROM messages 
        WHERE group_name IS NOT NULL 
          AND TRIM(group_name) != '' 
          AND group_name != 'None'
    """)
    group_names = cursor.fetchall()

    if group_names:
        if language == "arabic":
            response = "لديك رسائل جديدة من هذه المجموعات:\n"
            for group in group_names:
                response += f"- {group[0]}\n"
        else:
            response = "You have new messages from these groups:\n"
            for group in group_names:
                response += f"- {group[0]}\n"
    else:
        if language == "arabic":
            response = "ليس لديك رسائل جديدة.\nهل هناك مجموعة تريد إرسال رسالة إليها؟ فقط قل اسم المجموعة."
        else:
            response = "You have no new messages.\nIs there any group you want to send a message to? Just reply with the group name."

    context.user_data["awaiting_group_choice"] = True

    response_voice = await text_to_speech(response)
    await update.message.reply_voice(response_voice)





async def handle_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    if not voice:
        return
    
    user_id = update.message.from_user.id
    language = get_user_language(user_id)

    command_text = normalize_text(await speech_to_text(voice))
    print(f"[DEBUG] Voice command recognized: {command_text}")

    # ✅ Trigger the settings flow
    context.user_data["awaiting_language"] = True
    context.user_data["settings_mode"] = True
    
    if language == "english":
        msg = "Settings activated. Please say your preferred language: Arabic or English."
        await update.message.reply_voice(await text_to_speech(msg))
        return
    elif language == "arabic":
        msg = "الرجاء اختيار اللغة المفضّلة: العربية أو الانجليزية."
        await update.message.reply_voice(await text_to_speech(msg))
        return




async def handle_help_command(update: Update, context:ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    if not voice:
        return
    
    user_id = update.message.from_user.id
    language = get_user_language(user_id)
    role = get_user_role(user_id)


    if role!= "blind":
        if language == "english":
            for_sighted = "The help command is only available for blind users."
            await update.message.reply_voice(await text_to_speech(for_sighted))
        if language == "arabic":
            for_sighted = f"اذا أردت التواصل مع شخص أعمى من خلالي، لطفًا زدني على مجموعة بينك وبينه،"\
                f"وأنا سأتكفّل بتحويل رسائلك إلى تسجيلات صوتية وإرسالها له."\
                f"غير هذه الخاصية، ليس عندي ميزات لك لأطلعك عليها. شكرًا على تعاونك!"
            await update.message.reply_voice(await text_to_speech(for_sighted))

    
    command_text = normalize_text(await speech_to_text(voice))
    print(f"[DEBUG] Voice command recognized: {command_text}")

    if language == "english":
        confirmation = f"Here are the voice commands you can use any time:" \
                    f"Say 'group' to hear all available groups." \
                    f"Say 'check' to listen to your new messages." \
                    f"Say 'switch to' followed by a group name to change groups." \
                    f"Say 'leave group' if you want to exit a group." \
                    f"Say 'help' to hear these instructions again." \
                    f"Say 'settings' to change your language." \
                    f"Just speak naturally. I’m always listening and ready to help."
        
    if language == "arabic":
        confirmation = f"يمكنك استعمال هذه الكلمات المفتاحية:" \
                    f"'group' لتعرف المجموعات التي دخلت فبها." \
                    f"'check' لتسمع الرسائل الجديدة التي وصلتك." \
                    f"'switch to' لتغيير المجموعة التي تود التحدث فيها، مع ذكر اسم المجموعة بعدها." \
                    f" 'leave group' للخروج من مجموعة." \
                    f"'help' لسماع هذه الارشادات مرة أخرى." \
                    f"'settings'لتغيير اللغة  ." \
                    f"تحدث كما تشاء، أنا هنا لأساعدك!"
                
    

    await update.message.reply_voice(await text_to_speech(confirmation))
    return

