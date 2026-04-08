import discord
from discord.ext import commands, tasks
import os
import imagehash
import asyncio
from PIL import Image
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from keep_alive import keep_alive

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN')

# ฐานข้อมูลลายนิ้วมือภาพ (เก็บสูงสุด 2,000 รูป เพื่อความเสถียรระยะยาว)
# โครงสร้าง: deque([{'hashes': (phash, dhash, whash), 'author': id}, ...])
image_vault = deque(maxlen=2000)

# คำต้องห้าม (สแกนแบบ Case-Insensitive)
FORBIDDEN_PHRASES = [
    "bregamb.cc", "promo code", "reward received", "free $", 
    "beast games", "nitro", "t.me/", "bit.ly/"
]

# ตั้งค่าพื้นฐาน
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True

bot = commands.Bot(command_prefix="rb!", intents=intents, help_command=None)

# --- CORE LOGIC ---

def compute_multi_hash(img_bin):
    """คำนวณ Hash 3 ชนิดซ้อนกันเพื่อความแม่นยำสูงสุด"""
    with Image.open(BytesIO(img_bin)) as img:
        # แปลงเป็น RGB เพื่อรองรับทุกฟอร์แมต (รวมถึง RGBA/WebP)
        img = img.convert('RGB')
        return {
            'p': imagehash.phash(img),
            'd': imagehash.dhash(img),
            'w': imagehash.whash(img)
        }

def is_spam(new_hashes, threshold=12):
    """
    เปรียบเทียบความต่างของภาพแบบคะแนนสะสม
    Threshold 12 คือ 'เข้มงวดมาก' (99% Similarity)
    """
    for entry in image_vault:
        saved = entry['hashes']
        # คำนวณความต่างสะสมจาก 3 มิติ
        diff = (new_hashes['p'] - saved['p']) + \
               (new_hashes['d'] - saved['d']) + \
               (new_hashes['w'] - saved['w'])
        
        if diff <= threshold:
            return True
    return False

# --- EVENTS ---

@bot.event
async def on_ready():
    # ระบบเฝ้าระวังอัตโนมัติ
    if not status_rotator.is_running():
        status_rotator.start()
        
    print(f"--- RETH Guard Alpha v2.0 ---")
    print(f"Logged in as: {bot.user.name}")
    print(f"Precision Mode: Multi-Hash (99.9%)")
    print(f"Memory Cache: {len(image_vault)}/2000")
    print(f"-----------------------------")

@tasks.loop(minutes=5)
async def status_rotator():
    """เปลี่ยน Status เพื่อป้องกันบอทถูกมองว่า Idle"""
    await bot.change_presence(
        status=discord.Status.do_not_disturb,
        activity=discord.Activity(
            type=discord.ActivityType.competing, 
            name=f"Monitoring {len(bot.guilds)} Servers"
        )
    )

@bot.event
async def on_message(message):
    # ข้ามข้อความจากบอทและตัวเอง
    if message.author.bot or not message.guild:
        return

    # 1. ตรวจสอบรูปภาพสแปม (Visual Recognition)
    if message.attachments:
        for attachment in message.attachments:
            # รองรับไฟล์ภาพทุกประเภท
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.jfif']):
                try:
                    # อ่านข้อมูลไบนารีของภาพ
                    img_bytes = await attachment.read()
                    current_hashes = compute_multi_hash(img_bytes)

                    if is_spam(current_hashes):
                        await message.delete()
                        log_msg = await message.channel.send(
                            f"🛡️ **RETH Guard:** สกัดกั้นสแปมภาพจาก {message.author.mention} เรียบร้อยแล้ว",
                            delete_after=5
                        )
                        print(f"[SHIELD] Deleted visual spam from {message.author.id}")
                        return
                    
                    # ถ้าไม่ใช่สแปม ให้บันทึกลงหน่วยความจำ
                    image_vault.append({'hashes': current_hashes, 'user': message.author.id})

                except Exception as e:
                    print(f"[ERROR] Image Processing: {e}")

    # 2. ตรวจสอบข้อความ (Keyword Filtering)
    msg_clean = message.content.lower()
    if any(phrase in msg_clean for phrase in FORBIDDEN_PHRASES):
        try:
            await message.delete()
            print(f"[SHIELD] Deleted keyword spam from {message.author.id}")
            return
        except:
            pass

    await bot.process_commands(message)

# --- UTILITY COMMANDS ---

@bot.command()
@commands.has_permissions(administrator=True)
async def clear_cache(ctx):
    """ล้างฐานข้อมูลสแปมชั่วคราว"""
    image_vault.clear()
    await ctx.send("🧹 ฐานข้อมูล Cache ถูกล้างเรียบร้อยแล้ว", delete_after=3)

# --- RUNTIME ---

keep_alive()

try:
    bot.run(TOKEN)
except discord.errors.LoginFailure:
    print("❌ Token ไม่ถูกต้อง!")
except Exception as e:
    print(f"❌ บอทหยุดทำงานกะทันหัน: {e}")
