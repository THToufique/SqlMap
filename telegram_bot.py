import os
import asyncio
import re
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

user_sessions = defaultdict(lambda: {'url': None, 'options': set(), 'page': 0, 'session_id': None, 'custom_args': '', 'dump_state': None, 'databases': []})

ALL_OPTIONS = [
    {'Databases': '--dbs', 'Tables': '--tables', 'Columns': '--columns', 'Dump All': '--dump-all'},
    {'Current DB': '--current-db', 'Current User': '--current-user', 'Hostname': '--hostname', 'Passwords': '--passwords'},
    {'Batch': '--batch', 'Risk 3': '--risk=3', 'Level 5': '--level=5', 'Verbose': '-v 3'},
    {'Crawl': '--crawl=2', 'Forms': '--forms', 'Level 2': '--level=2', 'Random Agent': '--random-agent'},
    {'Threads 5': '--threads=5', 'Retry 3': '--retries=3', 'Timeout 30': '--timeout=30', 'Delay 0': '--delay=0'},
    {'Tamper Space2Comment': '--tamper=space2comment', 'Technique BEUST': '--technique=BEUST', 'Fingerprint': '--fingerprint', 'Banner': '--banner'},
    {'Schema': '--schema', 'Count': '--count', 'Search': '--search', 'Comments': '--comments'},
    {'OS Shell': '--os-shell', 'File Read': '--file-read', 'File Write': '--file-write', 'Privileges': '--privileges'},
    {'Union Cols': '--union-cols=12', 'Time Sec 5': '--time-sec=5', 'Auth Type': '--auth-type=Basic', 'Proxy': '--proxy'},
    {'Test Filter': '--test-filter', 'Skip Static': '--skip-static', 'Randomize': '--randomize', 'Keep Alive': '--keep-alive'},
    {'Dump Table': '--dump -T', 'Database': '-D', 'Exclude SysDB': '--exclude-sysdbs', 'Where': '--where'},
    {'DBMS': '--dbms', 'OS': '--os', 'Tamper': '--tamper', 'SQL Query': '--sql-query'},
    {'Tor': '--tor', 'Force SSL': '--force-ssl', 'Cookie': '--cookie', 'User Agent': '--user-agent'},
    {'All': '-a', 'Is DBA': '--is-dba', 'Users': '--users', 'Roles': '--roles'}
]

def create_keyboard(user_id, page=0):
    keyboard = []
    options = ALL_OPTIONS[page]
    
    row = []
    for label, value in options.items():
        session = user_sessions[user_id]
        prefix = "✅ " if value in session['options'] else ""
        row.append(InlineKeyboardButton(f"{prefix}{label}", callback_data=f"opt_{page}_{label}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_{page-1}"))
    if page < len(ALL_OPTIONS) - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton("✔️ Done", callback_data="done")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔰 SQLMap Bot\n\n"
        "Commands:\n"
        "• /sqlmap <URL> - Start scan with options\n"
        "• /dump - Interactive dump (DB → Table → Columns)\n"
        "• /continue - Add more options to scan"
    )

async def dump_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)
    
    if not session or not session['url']:
        await update.message.reply_text("❌ No active session. Start with /sqlmap <URL>")
        return
    
    await update.message.reply_text("🔍 Fetching databases...")
    
    # Get databases
    cmd = f"python sqlmap.py -u {session['url']} --dbs --batch"
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=os.path.dirname(__file__))
    output, _ = await proc.communicate()
    
    # Parse databases
    dbs = []
    for line in output.decode().split('\n'):
        if line.strip().startswith('[*]'):
            db = line.strip()[4:].strip()
            if db and db not in ['information_schema', 'performance_schema', 'mysql', 'sys']:
                dbs.append(db)
    
    if not dbs:
        await update.message.reply_text("❌ No databases found")
        return
    
    session['databases'] = dbs
    session['dump_state'] = 'select_db'
    
    keyboard = [[InlineKeyboardButton(db, callback_data=f"db_{db}")] for db in dbs]
    await update.message.reply_text("📊 Select database:", reply_markup=InlineKeyboardMarkup(keyboard))

async def continue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)
    
    if not session or not session['url']:
        await update.message.reply_text("❌ No active session. Start with /sqlmap <URL>")
        return
    
    await update.message.reply_text(
        f"💠 Continue: `{session['url']}`\n\n**Page 1/{len(ALL_OPTIONS)}**",
        reply_markup=create_keyboard(user_id, 0),
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    session = user_sessions[user_id]
    
    await query.answer()
    
    data = query.data
    
    if data.startswith("opt_"):
        _, page, label = data.split("_", 2)
        page = int(page)
        value = ALL_OPTIONS[page][label]
        
        if value in session['options']:
            session['options'].remove(value)
            await query.answer(f"➖ {label}")
        else:
            session['options'].add(value)
            await query.answer(f"➕ {label}")
        
        try:
            await query.edit_message_reply_markup(reply_markup=create_keyboard(user_id, page))
        except Exception:
            pass
    
    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        session['page'] = page
        await query.edit_message_text(
            f"🌐 Target: `{session['url']}`\n\n**Page {page+1}/{len(ALL_OPTIONS)}**",
            reply_markup=create_keyboard(user_id, page),
            parse_mode='Markdown'
        )
    
    elif data == "done":
        if not session['options']:
            await query.answer("❌ Select at least one option", show_alert=True)
            return
        
        await query.answer("🔰 Starting... 🔰")
        await run_scan(update.effective_chat.id, user_id, context)

async def run_scan(chat_id, user_id, context):
    session = user_sessions[user_id]
    url = session['url']
    opts = ' '.join(session['options'])
    custom = session.get('custom_args', '')
    
    cmd = f"python sqlmap.py -u {url} {custom if custom else opts}"
    
    status_msg = await context.bot.send_message(chat_id, f"⏳ `{cmd[:100]}...`", parse_mode='Markdown')
    
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(__file__)
        )
        
        output = []
        async for line in proc.stdout:
            line_text = line.decode().strip()
            output.append(line_text)
            if len(output) % 10 == 0:
                await status_msg.edit_text(f"⏳ Processing...\n```\n{line_text[:200]}\n```", parse_mode='Markdown')
        
        await proc.wait()
        full_output = '\n'.join(output)
        chunks = [full_output[i:i+3900] for i in range(0, len(full_output), 3900)]
        
        await status_msg.edit_text("✅ Complete! Use /continue for more.")
        for chunk in chunks[:3]:
            await context.bot.send_message(chat_id, f"```\n{chunk}\n```", parse_mode='Markdown')
        
        log_dir = os.path.join(os.path.dirname(__file__), '.sqlmap', 'output')
        if os.path.exists(log_dir):
            for root, dirs, files in os.walk(log_dir):
                for file in files[:5]:
                    path = os.path.join(root, file)
                    if os.path.getsize(path) < 50000000:
                        await context.bot.send_document(chat_id, document=open(path, 'rb'), filename=file, caption=f"📄 {file}")
    except Exception as e:
        await status_msg.edit_text(f"❌ {str(e)}")
    finally:
        session['options'].clear()
        session['custom_args'] = ''

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
    user_sessions[user_id] = {'url': url, 'options': set(), 'page': 0, 'session_id': session_id}
    
    await update.message.reply_text(
        f"🌐 Target: `{url}`\n\n**Page 1/{len(ALL_OPTIONS)}**",
        reply_markup=create_keyboard(user_id, 0),
        parse_mode='Markdown'
    )

def main():
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        print("Error: TELEGRAM_TOKEN not set")
        exit(1)
    
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sqlmap", sqlmap_cmd))
    app.add_handler(CommandHandler("continue", continue_cmd))
    app.add_handler(CommandHandler("dump", dump_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
