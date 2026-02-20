import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔰 SQLMap Bot\n\n"
        "Commands:\n"
        "• /sqlmap <URL> - Start scan\n"
    )

def main():
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        print("Error: TELEGRAM_TOKEN not set")
        exit(1)
    
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    
    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
