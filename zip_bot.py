import os
import asyncio
import zipfile
import io
from telethon import TelegramClient, events, Button
from telethon.tl.types import DocumentAttributeFilename

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_PASSWORD = os.environ.get("BOT_PASSWORD")

client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_files = {}
user_state = {}

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond(
        "**🔥 ULTRA FAST ZIP BOT v12**\n\n"
        f"Password: `{BOT_PASSWORD}`\n\n"
        "Bhejo files, phir `/zipnow` likho"
    )

@client.on(events.NewMessage(pattern='/zipnow'))
async def zipnow(event):
    user_id = event.sender_id
    if user_id not in user_files or not user_files[user_id]:
        return await event.respond("❌ Pehle files bhejo")
    
    msg = await event.respond("**STEP 1/3: DOWNLOADING...**")
    await asyncio.sleep(2) # Flood se bachao
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for i, file in enumerate(user_files[user_id]):
            await msg.edit(f"**STEP 1/3: DOWNLOADING**\n`{file.name}`\nFile {i+1}/{len(user_files[user_id])}")
            await asyncio.sleep(2) # Flood se bachao
            
            file_data = await client.download_media(file, bytes)
            zipf.writestr(file.name, file_data)
    
    await msg.edit("**STEP 2/3: ZIPPING...**")
    await asyncio.sleep(2)
    zip_buffer.seek(0)
    
    await msg.edit("**STEP 3/3: UPLOADING...**")
    await asyncio.sleep(2)
    await client.send_file(user_id, zip_buffer, attributes=[DocumentAttributeFilename("files.zip")])
    
    await msg.edit("✅ **DONE!** Zip ready")
    user_files[user_id] = []

@client.on(events.NewMessage)
async def handler(event):
    if event.document:
        user_id = event.sender_id
        if user_id not in user_files:
            user_files[user_id] = []
        user_files[user_id].append(event.document)
        await event.respond(f"✅ Added: `{event.document.attributes[0].file_name}`\nTotal: {len(user_files[user_id])}\n\n`/zipnow` karke zip banao")

print("✅ Bot Online! v12 RAILWAY ULTRA FAST")
client.run_until_disconnected()