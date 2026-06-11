import json
import os
import random
import asyncio
import base64
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Document
from telegram.error import Forbidden
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ================= CONFIGURATION =================
BOT_TOKEN = "8968673700:AAFXn8leUAbafSlDlWepyFiWWlOG3rzxjak"
ADMIN_ID = 8506228831
DATA_FILE = "bot_data.json"
# =================================================

bot_data = {
    "url_ratios": {
        "https://t.me/JinFileSaverBot/Getlink": 100,
        "https://tectuytiurnews.com/parameterlink": 30
    },
    "users": [],
    "welcome_message": "Welcome! Here is your special link:\n{url}",
    "preview_enabled": True
}

def load_data():
    global bot_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            saved_data = json.load(f)
            bot_data.update(saved_data)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(bot_data, f, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in bot_data["users"]:
        bot_data["users"].append(user_id)
        save_data()

    urls = list(bot_data["url_ratios"].keys())
    weights = list(bot_data["url_ratios"].values())

    chosen_url = None

    # Check start parameter for link number (1 = first link, 2 = second link...)
    if context.args:
        raw_param = context.args[0].strip()
        if raw_param.isdigit():
            index = int(raw_param) - 1  # convert to 0-based index
            if 0 <= index < len(urls):
                chosen_url = urls[index]

    # Fallback: weighted random if no valid number was given
    if chosen_url is None:
        chosen_url = random.choices(urls, weights=weights, k=1)[0]

    # Remove {url} from message text so the raw link is never shown
    final_message = bot_data["welcome_message"].replace("{url}", "").strip()
    if not final_message:
        final_message = "Welcome! Click the button below:"

    # Button opens the link directly on click
    keyboard = [[InlineKeyboardButton("🔗 Open Link", url=chosen_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        final_message,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        reply_markup=reply_markup
    )

async def download_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command - sends bot_data.json as a file in chat."""
    if update.effective_user.id != ADMIN_ID:
        return

    # Always save latest data before sending
    save_data()

    if not os.path.exists(DATA_FILE):
        await update.message.reply_text("❌ No data file found yet.")
        return

    await update.message.reply_text(
        f"📦 Here is your current data file.\n"
        f"👥 Total users saved: {len(bot_data['users'])}\n\n"
        f"⚠️ Keep this file safe — use /upload_data to restore after redeployment."
    )

    with open(DATA_FILE, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="bot_data.json",
            caption="✅ bot_data.json — your full bot data backup"
        )

async def upload_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command - restores bot_data.json from an uploaded file."""
    if update.effective_user.id != ADMIN_ID:
        return

    # Check if a document was attached with the command reply
    if not update.message.document:
        await update.message.reply_text(
            "📤 To restore your data:\n"
            "1. Send this command: /upload_data\n"
            "2. Attach your saved `bot_data.json` file with it\n\n"
            "Or reply to a previously sent json file with /upload_data"
        )
        return

    doc = update.message.document

    # Validate it's a json file
    if not doc.file_name.endswith(".json"):
        await update.message.reply_text("❌ Please send a valid .json file.")
        return

    try:
        # Download the file from Telegram
        file = await context.bot.get_file(doc.file_id)
        downloaded = await file.download_as_bytearray()

        # Parse and validate JSON
        new_data = json.loads(downloaded.decode("utf-8"))

        # Check required keys exist
        required_keys = ["url_ratios", "users", "welcome_message", "preview_enabled"]
        for key in required_keys:
            if key not in new_data:
                await update.message.reply_text(f"❌ Invalid file — missing key: `{key}`", parse_mode="Markdown")
                return

        # Restore data
        global bot_data
        bot_data = new_data
        save_data()

        user_count = len(bot_data["users"])
        await update.message.reply_text(
            f"✅ Data restored successfully!\n"
            f"👥 Users restored: {user_count}\n"
            f"🔗 URL ratios loaded: {len(bot_data['url_ratios'])}\n"
            f"💬 Welcome message: restored\n"
            f"🖼 Preview setting: restored"
        )

    except json.JSONDecodeError:
        await update.message.reply_text("❌ File is not valid JSON. Please send the original bot_data.json file.")
    except Exception as e:
        await update.message.reply_text(f"❌ Something went wrong: {str(e)}")

async def set_ratio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /set_ratio <url1>,<ratio1> <url2>,<ratio2>")
        return

    new_ratios = {}
    try:
        for arg in args:
            url, weight = arg.split(',')
            new_ratios[url] = int(weight)
        bot_data["url_ratios"] = new_ratios
        save_data()
        await update.message.reply_text("✅ Ratios updated successfully!")
    except ValueError:
        await update.message.reply_text("❌ Error: Format must be URL,Number with NO spaces around the comma.")

async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    new_message = " ".join(context.args)
    if not new_message:
        await update.message.reply_text("⚠️ Usage: /set_welcome Hello there! Click here: {url}")
        return

    if "{url}" not in new_message:
        await update.message.reply_text(
            "❌ Error: You must include `{url}` in your message!",
            parse_mode="Markdown"
        )
        return

    bot_data["welcome_message"] = new_message
    save_data()
    await update.message.reply_text("✅ Welcome message updated successfully!")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    preview_status = "🟢 ON" if bot_data["preview_enabled"] else "🔴 OFF"

    keyboard = [
        [InlineKeyboardButton(f"Toggle Link Previews (Currently: {preview_status})", callback_data="toggle_preview")],
        [InlineKeyboardButton("📊 View Stats", callback_data="show_stats")],
        [InlineKeyboardButton("📦 Download Data", callback_data="download_data_btn")],
        [InlineKeyboardButton("ℹ️ Command Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚙️ **Admin Control Panel**\nChoose an option below:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("You are not an admin!", show_alert=True)
        return

    await query.answer()

    if query.data == "toggle_preview":
        bot_data["preview_enabled"] = not bot_data["preview_enabled"]
        save_data()

        preview_status = "🟢 ON" if bot_data["preview_enabled"] else "🔴 OFF"
        keyboard = [
            [InlineKeyboardButton(f"Toggle Link Previews (Currently: {preview_status})", callback_data="toggle_preview")],
            [InlineKeyboardButton("📊 View Stats", callback_data="show_stats")],
            [InlineKeyboardButton("📦 Download Data", callback_data="download_data_btn")],
            [InlineKeyboardButton("ℹ️ Command Help", callback_data="help")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await query.message.reply_text(f"✅ Link Previews are now {preview_status}")

    elif query.data == "show_stats":
        user_count = len(bot_data["users"])
        ratios = "\n".join([f"- {u}: {w}" for u, w in bot_data["url_ratios"].items()])
        await query.message.reply_text(
            f"📊 **Bot Statistics**\n👥 Total Users: {user_count}\n🔗 Current Ratios:\n{ratios}",
            parse_mode="Markdown"
        )

    elif query.data == "download_data_btn":
        save_data()
        if os.path.exists(DATA_FILE):
            await query.message.reply_text(
                f"📦 Sending your data file...\n"
                f"👥 Total users: {len(bot_data['users'])}"
            )
            with open(DATA_FILE, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename="bot_data.json",
                    caption="✅ bot_data.json — your full bot data backup"
                )
        else:
            await query.message.reply_text("❌ No data file found.")

    elif query.data == "help":
        help_text = (
            "🛠️ **Admin Commands Help**\n\n"
            "**1. Change URLs & Ratios:**\n`/set_ratio link1.com,70 link2.com,30`\n\n"
            "**2. Change Welcome Message:**\n`/set_welcome Hello! Check this out: {url}`\n"
            "*(Must include {url})*\n\n"
            "**3. Broadcast Message:**\n`/broadcast Hello everyone!`\n\n"
            "**4. Backup Data:**\n`/download_data` — get json file\n\n"
            "**5. Restore Data:**\n`/upload_data` + attach json file"
        )
        await query.message.reply_text(help_text, parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("⚠️ Usage: /broadcast Hello everyone!")
        return

    await update.message.reply_text("⏳ Starting broadcast...")
    success, fail = 0, 0

    for user_id in bot_data["users"]:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1

    await update.message.reply_text(f"✅ Broadcast complete!\nSuccess: {success}\nFailed: {fail}")

def main():
    load_data()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set_ratio", set_ratio))
    application.add_handler(CommandHandler("set_welcome", set_welcome))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("download_data", download_data))
    application.add_handler(CommandHandler("upload_data", upload_data))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Handle file uploads for restore (when user sends file as reply)
    application.add_handler(MessageHandler(filters.Document.ALL & filters.REPLY, upload_data))

    print("Advanced Admin Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()
