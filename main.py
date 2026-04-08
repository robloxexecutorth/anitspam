import discord
from discord.ext import commands
import os
from PIL import Image
import imagehash
from io import BytesIO
from collections import deque
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN') # ใช้ Token แยกจากบอทเดิม

# ตั้งค่าความจำ: จำรหัสรูปภาพล่าสุด 200 รูป
spam_image_hashes = deque(maxlen=200)

# รายชื่อคำต้องห้าม (เพิ่มได้ตามใจชอบ)
BANNED_KEYWORDS = ["bregamb.cc", "promo code", "reward received", "free $", "beast games"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def check_image_spam(attachment):
    """ฟังก์ชันสแกนและคำนวณ Hash ของรูปภาพ"""
    if not attachment.content_type or not attachment.content_type.startswith('image'):
        return False
    try:
        data = await attachment.read()
        img = Image.open(BytesIO(data))
        # คำนวณรหัสลายนิ้วมือของรูป (คล้ายกันจะ Hash ได้เลขเดิม)
        current_hash = str(imagehash.average_hash(img))
        
        if current_hash in spam_image_hashes:
            return True # เจอรูปซ้ำ!
        
        spam_image_hashes.append(current_hash)
        return False
    except:
        return False

@bot.event
async def on_ready():
    print(f'🛡️ Anti-Spam Bot is Online: {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # --- 1. ตรวจสอบรูปภาพ ---
    if message.attachments:
        for attachment in message.attachments:
            if await check_image_spam(attachment):
                try:
                    await message.delete()
                    await message.channel.send(f"⚠️ {message.author.mention}, พบรูปภาพสแปมซ้ำ! (Spam Detected)", delete_after=5)
                    return
                except: pass

    # --- 2. ตรวจสอบคำต้องห้าม ---
    content_lower = message.content.lower()
    if any(word in content_lower for word in BANNED_KEYWORDS):
        try:
            await message.delete()
            await message.channel.send(f"🚫 {message.author.mention}, ห้ามส่งข้อความสแปมหรือลิงก์อันตราย!", delete_after=5)
            return
        except: pass

    await bot.process_commands(message)

bot.run(TOKEN)
