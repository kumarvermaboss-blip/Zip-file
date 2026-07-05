import os
import asyncio
import zipfile
import time
import shutil
from telethon import TelegramClient, events, types, functions

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_PASSWORD = os.environ.get("BOT_PASSWORD")

# Railway ke liye unique session name
client = TelegramClient('railway_bot', API_ID, API_HASH)

user_files = {}
user_backup = {}
logged_in_users = set()
user_queue = {}
active_downloads = {}
cancel_flags = {}
user_state = {}
MAX_CONCURRENT = 3 # Railway pe 3 kar diya

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024: return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} TB"

def format_speed(bytes_per_sec):
    return f"{format_size(bytes_per_sec)}/s"

def progress_bar(percent):
    bar = "█" * int(percent/10) + "░" * (10 - int(percent/10))
    return f"[{bar}] {percent:.1f}%"

async def set_bot_commands():
    commands = [
        types.BotCommand(command="start", description="Wizard shuru karo"),
        types.BotCommand(command="login", description="Login /login 1234"),
        types.BotCommand(command="current", description="Status check karo"),
        types.BotCommand(command="zipnow", description="Step 2: Zip banao"),
        types.BotCommand(command="cancel", description="1 file cancel /cancel ID"),
        types.BotCommand(command="cancelall", description="SAB CLEAR + BACKUP"),
    ]
    await client(functions.bots.SetBotCommandsRequest(scope=types.BotCommandScopeDefault(), lang_code='en', commands=commands))

async def process_queue(user_id):
    if user_id not in user_queue or not user_queue[user_id]: return
    if active_downloads.get(user_id, 0) >= MAX_CONCURRENT: return
    file_data = user_queue[user_id].pop(0)
    active_downloads[user_id] = active_downloads.get(user_id, 0) + 1
    cancel_flags[file_data['msg'].id] = False
    asyncio.create_task(download_file(file_data['event'], file_data['msg'], user_id, file_data['msg'].id))
    await process_queue(user_id)

async def download_file(event, msg, user_id, msg_id):
    file_name = event.file.name or f"file_{len(user_files[user_id])}.mp4"
    file_path = f"downloads/{user_id}_{file_name}"
    backup_path = f"backup/{user_id}_{file_name}"
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("backup", exist_ok=True)
    start_time = time.time()

    async def progress_callback(current, total):
        if cancel_flags.get(msg_id): raise asyncio.CancelledError
        percent = current * 100 / total
        speed = current / (time.time() - start_time) if time.time() > start_time else 0
        try:
            await msg.edit(
                f"**STEP 1/3: DOWNLOAD**\n"
                f"{progress_bar(percent)}\n"
                f"📄 {file_name}\n"
                f"📦 {format_size(current)} / {format_size(total)}\n"
                f"⚡ {format_speed(speed)}\n\n"
                f"`/cancel {msg_id}` = Is file ko cancel karo"
            )
        except: pass

    try:
        await client.download_media(event.message, file_path, progress_callback=progress_callback)
        shutil.copy(file_path, backup_path)
        user_files[user_id].append(file_path)
        user_backup[user_id].append(backup_path)
        await msg.edit(f"✅ **STEP 1/3: DOWNLOADED**\n📄 `{file_name}`\n\nTotal: {len(user_files[user_id])} files\nAgla step: `/zipnow`")
        user_state[user_id] = "waiting_zip"
        await msg.reply("**STEP 2/3: KYA KARNA HAI?**\n1. `/zipnow` dabao = Zip ban jayegi\n2. Aur file bhejo = Queue me lag jayegi\n3. `/cancelall` = Sab clear")
    except asyncio.CancelledError:
        if os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(backup_path): os.remove(backup_path)
        await msg.edit(f"❌ **CANCELLED**\n📄 `{file_name}`")
    finally:
        if msg_id in cancel_flags: del cancel_flags[msg_id]
        active_downloads[user_id] -= 1
        await process_queue(user_id)

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    user_state[user_id] = "idle"
    await event.reply(f"**🤖 WELCOME TO FILES BOT v12 RAILWAY**\n\n**STEP 1:** `/login {BOT_PASSWORD}`\n**STEP 2:** File bhejo\n**STEP 3:** `/zipnow`\n**STEP 4:** Zip download karo\nSpeed: ULTRA FAST\nMadad ke liye `/current`")

@client.on(events.NewMessage(pattern='/login (.*)'))
async def login(event):
    user_id = event.sender_id
    password = event.pattern_match.group(1)
    if password == BOT_PASSWORD:
        logged_in_users.add(user_id)
        user_files[user_id] = []
        user_backup[user_id] = []
        user_queue[user_id] = []
        active_downloads[user_id] = 0
        user_state[user_id] = "logged_in"
        await event.reply("✅ **LOGIN SUCCESS**\n\n**STEP 2:** Ab files bhejna shuru karo. Me khud download kar lunga.")
    else:
        await event.reply("❌ Wrong Password")

@client.on(events.NewMessage(func=lambda e: e.file))
async def handler(event):
    user_id = event.sender_id
    if user_id not in logged_in_users:
        return await event.reply("**STEP 1:** Pehle `/login 1234` karo")
    if user_id not in user_files: user_files[user_id] = []
    if user_id not in user_backup: user_backup[user_id] = []
    msg = await event.reply("⏳ **QUEUE ME LAG GAYI**\nDownload shuru hone wala hai...")
    user_queue[user_id].append({'event': event, 'msg': msg})
    await process_queue(user_id)

@client.on(events.NewMessage(pattern='/current'))
async def current(event):
    user_id = event.sender_id
    if user_id not in logged_in_users: return
    downloading = active_downloads.get(user_id, 0)
    queued = len(user_queue.get(user_id, []))
    ready = len(user_files.get(user_id, []))
    backup = len(user_backup.get(user_id, []))
    state = user_state.get(user_id, "idle")
    next_step = "File bhejo"
    if state == "waiting_zip": next_step = "Ab /zipnow dabao"
    if ready > 0 and state!= "waiting_zip": next_step = "/zipnow se zip banao"
    await event.reply(
        f"**📊 STEP BY STEP STATUS**\n\n"
        f"⬇️ Downloading: {downloading}/3\n"
        f"⏳ Queue me: {queued}\n"
        f"✅ Ready: {ready}\n"
        f"💾 Backup: {backup}\n\n"
        f"**NEXT STEP:** {next_step}\n\n"
        f"Emergency: `/cancelall`"
    )

@client.on(events.NewMessage(pattern='/cancel (\\d+)'))
async def cancel_specific(event):
    user_id = event.sender_id
    if user_id not in logged_in_users: return
    msg_id = int(event.pattern_match.group(1))
    if msg_id in cancel_flags:
        cancel_flags[msg_id] = True
        await event.reply(f"✅ Cancel signal bhej di")
    else:
        await event.reply("Galat ID ya task khatam ho gaya")

@client.on(events.NewMessage(pattern='/cancelall'))
async def cancel_all(event):
    user_id = event.sender_id
    if user_id not in logged_in_users: return
    user_queue[user_id] = []
    for k in list(cancel_flags.keys()): cancel_flags[k] = True
    active_downloads[user_id] = 0
    count = len(user_files[user_id]) + len(user_backup[user_id])
    for file in user_files[user_id]:
        if os.path.exists(file): os.remove(file)
    for file in user_backup[user_id]:
        if os.path.exists(file): os.remove(file)
    user_files[user_id] = []
    user_backup[user_id] = []
    user_state[user_id] = "idle"
    await event.reply(f"💥 **RESET HO GAYA**\n{count} Files Deleted\nWapis `/start` se shuru karo")

@client.on(events.NewMessage(pattern='/zipnow'))
async def zipnow(event):
    user_id = event.sender_id
    if user_id not in logged_in_users: return
    if active_downloads.get(user_id, 0) > 0:
        return await event.reply("**WAIT:** Pehle downloads complete hone do. `/current` se check karo")
    if user_id not in user_files or not user_files[user_id]:
        return await event.reply("**ERROR:** Pehle koi file bhejo. STEP 2 skip nahi ho sakta")

    user_state[user_id] = "zipping"
    zip_name = f"zip/{user_id}_files.zip"
    os.makedirs("zip", exist_ok=True)
    total_files = len(user_files[user_id])
    zip_msg_id = event.id + 1
    cancel_flags[zip_msg_id] = False

    msg = await event.reply(f"**STEP 2/3: PROCESSING**\n0%\n\n`/cancel {zip_msg_id}` = Zip cancel karo")
    zip_start = time.time()
    try:
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, file in enumerate(user_files[user_id]):
                if cancel_flags.get(zip_msg_id): raise asyncio.CancelledError
                zipf.write(file, os.path.basename(file))
                percent = (i+1) * 100 / total_files
                elapsed = time.time() - zip_start
                speed = os.path.getsize(zip_name) / elapsed if elapsed > 0 else 0
                try:
                    await msg.edit(f"**STEP 2/3: ZIPPING**\n{progress_bar(percent)}\n📄 File {i+1}/{total_files}\n⚡ {format_speed(speed)}\n\n`/cancel {zip_msg_id}` = Zip cancel")
                except: pass
                await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        if os.path.exists(zip_name): os.remove(zip_name)
        await msg.edit(f"❌ **ZIP CANCELLED**\nWapis `/zipnow` se try karo")
        del cancel_flags[zip_msg_id]
        user_state[user_id] = "waiting_zip"
        return

    zip_size = os.path.getsize(zip_name)
    try: await msg.edit(f"✅ **STEP 2/3: PROCESSING COMPLETE**\n📦 {format_size(zip_size)}")
    except: pass
    del cancel_flags[zip_msg_id]
    user_state[user_id] = "uploading"

    upload_msg = await event.reply("**STEP 3/3: UPLOAD**\n0%")
    upload_start = time.time()
    upload_cancel_id = upload_msg.id
    cancel_flags[upload_cancel_id] = False

    async def upload_progress(current, total):
        if cancel_flags.get(upload_cancel_id): raise asyncio.CancelledError
        percent = current * 100 / total
        speed = current / (time.time() - upload_start)
        try:
            await upload_msg.edit(f"**STEP 3/3: UPLOAD**\n{progress_bar(percent)}\n📦 {format_size(current)} / {format_size(total)}\n⚡ {format_speed(speed)}\n\n`/cancel {upload_cancel_id}` = Upload cancel")
        except: pass

    try:
        # RAILWAY FAST UPLOAD - 4MB CHUNK
        await client.send_file(
            event.chat_id,
            zip_name,
            caption=f"✅ **FINAL STEP COMPLETE**\n📦 {format_size(zip_size)}\n📄 Total: {total_files}\n\nPowered by Railway 🚀",
            progress_callback=upload_progress,
            part_size_kb=4096 # 4MB CHUNK
        )
        try: await upload_msg.edit("✅ **STEP 3/3: UPLOAD COMPLETE**\n\nWapis STEP 1 se shuru kar sakte ho")
        except: pass
    except asyncio.CancelledError:
        await upload_msg.edit("❌ **UPLOAD CANCELLED**")
    finally:
        if upload_cancel_id in cancel_flags: del cancel_flags[upload_cancel_id]

    for file in user_files[user_id]:
        if os.path.exists(file): os.remove(file)
    user_files[user_id] = []
    user_state[user_id] = "idle"

async def main():
    await client.start(bot_token=BOT_TOKEN)
    await set_bot_commands()
    print("✅ Bot Online! v12 RAILWAY ULTRA FAST")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
