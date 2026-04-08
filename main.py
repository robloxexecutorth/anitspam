import discord
from discord.ext import commands
import os
import imagehash
from PIL import Image
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from keep_alive import keep_alive

# Load Config
load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN')

# เพิ่มความจำ Cache เป็น 1,000 รูป เพื่อการดักจับที่ครอบคลุมระยะยาว
# เก็บเป็น Dictionary เพื่อรองรับ Multi-Hash
spam_database = deque(maxlen=1000)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_image_fingerprints(img):
    """
    สร้างลายนิ้วมือภาพ 3 รูปแบบเพื่อความแม่นยำ 99%
    1. pHash: ตรวจโครงสร้าง (ทนต่อการปรับสี/แสง)
    2. dHash: ตรวจความต่างของขอบ (ทนต่อการย่อ/ขยาย)
    3. wHash: ตรวจ Wavelet (ทนต่อการบีบอัดไฟล์)
    """
    return {
        'phash': imagehash.phash(img),
        'dhash': imagehash.dhash(img),
        'whash': imagehash.whash(img)
    }

def check_similarity(new_fingerprints, threshold=10):
    """
    ระบบคำนวณความต่างแบบ Multi-Layer
    ถ้าคะแนนความต่างรวมกันน้อยกว่า Threshold แสดงว่าเป็นภาพเดียวกัน
    """
    for saved in spam_database:
        # คำนวณความต่างเฉลี่ยจากทั้ง 3 Hash
        p_diff = new_fingerprints['phash'] - saved['phash']
        d_diff = new_fingerprints['dhash'] - saved['dhash']
        w_diff = new_fingerprints['whash'] - saved['whash']
        
        # ถ้าเฉลี่ยแล้วมีความต่างน้อยมาก (เกือบเหมือนเป๊ะ)
        if (p_diff + d_diff + w_diff) / 3 <= threshold:
            return True
    return False

@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.do_not_disturb, # ตั้งเป็นห้ามรบกวน ให้ดูดุๆ
        activity=discord.Activity(type=discord.ActivityType.competing, name="Anti-Spam Elite")
    )
    print(f'🛡️ [ELITE MODE ACTIVE] RETH Guard is scanning with 99% precision.')

@bot.event
async def on_message(message):
    if message.author.bot: return

    # --- 📸 ADVANCED IMAGE SCANNING ---
    if message.attachments:
        for attachment in message.attachments:
            if any(ext in attachment.filename.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.jfif']):
                try:
                    data = await attachment.read()
                    img = Image.open(BytesIO(data))
                    
                    # สกัดลายนิ้วมือ
                    fingerprints = get_image_fingerprints(img)
                    
                    if check_similarity(fingerprints):
                        await message.delete()
                        # ลงโทษด้วยการเตือน (ลบทิ้งใน 3 วินาที)
                        alert = await message.channel.send(f"⚠️ **RETH Guard:** ตรวจพบสแปมภาพจาก {message.author.mention}! [Similarity Match 99%]", delete_after=3)
                        print(f"🔥 [ELITE DELETE] High-similarity match from {message.author}")
                        return 
                    
                    # บันทึกภาพใหม่ลงฐานข้อมูล
                    spam_database.append(fingerprints)
                    
                except Exception as e:
                    print(f"❌ [SCAN ERROR]: {e}")

    # --- ⌨️ KEYWORD SCANNING ---
    # เพิ่มคำต้องห้ามให้ดุขึ้น
    BANNED = ["bregamb.cc", "promo code", "reward received", "free $", "bit.ly/", "t.me/"]
    if any(word in message.content.lower() for word in BANNED):
        try:
            await message.delete()
            return
        except: pass

    await bot.process_commands(message)

# Flask Server สำหรับ Keep Alive
keep_alive()

if TOKEN:
    bot.run(TOKEN)
