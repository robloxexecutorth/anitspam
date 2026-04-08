import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import imagehash
import asyncio
from PIL import Image, ImageOps, ImageFilter
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from keep_alive import keep_alive

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN')

# สถานะระบบ
PROTECTION_ENABLED = True
# ความจำลายนิ้วมือภาพ (2,000 รายการ)
image_vault = deque(maxlen=2000)

FORBIDDEN_PHRASES = ["bregamb.cc", "promo code", "free $", "beast games", "t.me/", "bit.ly/"]

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True

class RETHBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="rb!", intents=intents, help_command=None)
        
    async def setup_hook(self):
        await self.tree.sync()
        print("✅ [ULTRA SYNC] Slash Commands Ready!")

bot = RETHBot()

# --- ADVANCED IMAGE PROCESSING ---

def prepare_image(img_bin):
    """
    เพิ่มประสิทธิภาพการสแกนโดยการทำ Pre-processing
    ลด Noise และจุดต่างเล็กน้อย (เช่น เวลาบน Taskbar) ก่อนทำ Hash
    """
    with Image.open(BytesIO(img_bin)) as img:
        # 1. แปลงเป็น RGB และปรับขนาดให้มาตรฐาน
        img = img.convert('RGB').resize((256, 256), Image.Resampling.LANCZOS)
        # 2. ลดรายละเอียดเล็กๆ ที่อาจทำให้ Hash เพี้ยน (เช่น ตัวเลขเวลาที่เปลี่ยนไป)
        img = img.filter(ImageFilter.GaussianBlur(radius=1)) 
        # 3. ปรับ Contrast ให้ชัดเจนขึ้นเพื่อให้เห็นโครงสร้างภาพหลัก
        img = ImageOps.autocontrast(img)
        
        return {
            'p': imagehash.phash(img),
            'd': imagehash.dhash(img),
            'w': imagehash.whash(img)
        }

def is_spam(new_hashes, threshold=5):
    """
    Threshold = 5: ระดับโหดเหี้ยม (Zero-Tolerance)
    แม้ภาพจะต่างกันเล็กน้อย บอทจะมองว่าเป็นสแปมทันที
    """
    for entry in image_vault:
        saved = entry['hashes']
        # คำนวณความต่างรวมจาก 3 มิติ
        diff = (new_hashes['p'] - saved['p']) + \
               (new_hashes['d'] - saved['d']) + \
               (new_hashes['w'] - saved['w'])
        
        if diff <= threshold:
            return True
    return False

# --- SLASH COMMANDS ---

@bot.tree.command(name="on", description="เปิดระบบป้องกันระดับสูงสุด")
@app_commands.checks.has_permissions(administrator=True)
async def system_on(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = True
    await bot.change_presence(status=discord.Status.online)
    await interaction.response.send_message("🟢 **RETH Guard:** ระบบป้องกันระดับ **Zero-Tolerance** เปิดใช้งาน!", ephemeral=False)

@bot.tree.command(name="off", description="ปิดระบบป้องกัน")
@app_commands.checks.has_permissions(administrator=True)
async def system_off(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = False
    await bot.change_presence(status=discord.Status.do_not_disturb)
    await interaction.response.send_message("🔴 **RETH Guard:** ปิดระบบป้องกันชั่วคราว", ephemeral=False)

@bot.tree.command(name="clear", description="Wave Clear: ล้างฐานข้อมูลภาพทั้งหมด")
@app_commands.checks.has_permissions(administrator=True)
async def clear_wave(interaction: discord.Interaction):
    count = len(image_vault)
    image_vault.clear()
    await interaction.response.send_message(f"🌊 **Wave Clear!** ล้างลายนิ้วมือภาพ {count} รายการสำเร็จ", ephemeral=False)

# --- CORE EVENTS ---

@bot.event
async def on_ready():
    print(f"--- RETH Guard Ultra v4.0 ---")
    print(f"Status: ONLINE | Precision: ZERO-TOLERANCE")
    print(f"-----------------------------")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not PROTECTION_ENABLED:
        return

    # 1. SCAN IMAGES (ดักจับภาพคล้าย 99.9%)
    if message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.jfif']):
                try:
                    img_bytes = await attachment.read()
                    # ใช้ระบบ Pre-processing ก่อนทำ Hash เพื่อความแม่นยำ
                    current_hashes = prepare_image(img_bytes)

                    if is_spam(current_hashes):
                        await message.delete()
                        await message.channel.send(f"🛡️ **RETH Guard:** ตรวจพบรูปภาพสแปม/ซ้ำ (Similarity Match) ดีดทิ้งเรียบร้อย!", delete_after=3)
                        print(f"[SHIELD] Deleted visual spam from {message.author.id}")
                        return
                    
                    image_vault.append({'hashes': current_hashes, 'user': message.author.id})
                except Exception as e:
                    print(f"[SCAN ERROR] {e}")

    # 2. SCAN KEYWORDS
    msg_clean = message.content.lower()
    if any(phrase in msg_clean for phrase in FORBIDDEN_PHRASES):
        try: await message.delete()
        except: pass

    await bot.process_commands(message)

# --- RUNTIME ---
keep_alive()
if TOKEN:
    bot.run(TOKEN)
