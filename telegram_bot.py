import os
import asyncio
import re
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

user_sessions = defaultdict(lambda: {'url': None, 'options': set(), 'session_id': None})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔰 SQLMap Bot\n\n"
        "Commands:\n"
        "• /sqlmap <URL> - Start scan\n"
    )

async def sqlmap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /sqlmap http://target.com?id=1")
        return
    
    url = context.args[0]
    if not re.match(r'https?://', url):
        await update.message.reply_text("❌ Invalid URL")
        return
    
    session_id = re.sub(r'[^a-zA-Z0-9]', '_', url)[:50]
    user_sessions[user_id] = {'url': url, 'options': set(), 'session_id': session_id}
    
    await update.message.reply_text(f"🌐 Target: `{url}`\n\nReady to scan!", parse_mode='Markdown')

def main():
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        print("Error: TELEGRAM_TOKEN not set")
        exit(1)
    
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sqlmap", sqlmap_cmd))
    
    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
