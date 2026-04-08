import discord
from discord.ext import commands
import os
from PIL import Image
import imagehash
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from keep_alive import keep_alive  # นำเข้าระบบ Keep Alive

load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN')

# ตั้งค่าความจำ: จำรหัสรูปภาพล่าสุด 200 รูป
spam_image_hashes = deque(maxlen=200)

# รายชื่อคำต้องห้าม
BANNED_KEYWORDS = ["bregamb.cc", "promo code", "reward received", "free $", "beast games"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def check_image_spam(attachment):
    if not attachment.content_type or not attachment.content_type.startswith('image'):
        return False
    try:
        data = await attachment.read()
        img = Image.open(BytesIO(data))
        current_hash = str(imagehash.average_hash(img))
        
        if current_hash in spam_image_hashes:
            return True
        
        spam_image_hashes.append(current_hash)
        return False
    except:
        return False

@bot.event
async def on_ready():
    print(f'🛡️ RETH Guard is Online: {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # 1. ตรวจสอบรูปภาพสแปม
    if message.attachments:
        for attachment in message.attachments:
            if await check_image_spam(attachment):
                try:
                    await message.delete()
                    await message.channel.send(f"⚠️ {message.author.mention}, Stop spamming!", delete_after=5)
                    return
                except: pass

    # 2. ตรวจสอบคำต้องห้าม
    content_lower = message.content.lower()
    if any(word in content_lower for word in BANNED_KEYWORDS):
        try:
            await message.delete()
            return
        except: pass

    await bot.process_commands(message)

# รันระบบ Keep Alive ก่อน Start บอท
keep_alive()

# เริ่มการทำงานของบอท
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"Error starting bot: {e}")
