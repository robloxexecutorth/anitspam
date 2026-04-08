import discord
from discord import app_commands
from discord.ext import commands
import os
import imagehash
import pytesseract
import asyncio
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from keep_alive import keep_alive

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN')

PROTECTION_ENABLED = True
image_vault = deque(maxlen=3000) # ขยายความจำเพิ่มเป็น 3,000 รูป

# คำต้องห้ามครอบคลุมทั้งไทยและอังกฤษ
BANNED_WORDS = [
    "bregamb.cc", "withdrawal success", "reward received", "free $", 
    "beast games", "t.me/", "bit.ly/", "promo code", "claim now", 
    "ถอนเงินสำเร็จ", "รับรางวัล", "ฟรีเครดิต", "เว็บตรง"
]

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True

class RETHBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="rb!", intents=intents, help_command=None)
        
    async def setup_hook(self):
        await self.tree.sync()
        print("✅ [SUPREME SYNC] Omni-Vision AI Ready!")

bot = RETHBot()

# --- THE SUPREME VISION ENGINE ---

def optimize_for_scan(img_bin):
    """
    เตรียมภาพด้วยเทคนิคขั้นสูงเพื่อให้แม่นยำระดับสูงสุด
    """
    with Image.open(BytesIO(img_bin)) as img:
        img = img.convert('RGB')
        
        # 1. ปรับ Contrast ให้ภาพมีระยะที่ชัดเจน (กันพวกสแปมปรับแสงรูป)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        
        # 2. ทำ Structural Preparation
        # ใช้ Gaussian Blur บางๆ เพื่อมองข้าม Noise เล็กๆ แต่รักษาโครงสร้างหลัก
        struct_img = img.resize((512, 512), Image.Resampling.LANCZOS)
        struct_img = struct_img.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        # 3. คำนวณ Hashes แบบ Multi-Core
        hashes = {
            'p': imagehash.phash(struct_img, hash_size=16), # เพิ่มความละเอียดจาก 8 เป็น 16
            'd': imagehash.dhash(struct_img, hash_size=16),
            'w': imagehash.whash(struct_img, hash_size=16)
        }
        
        # 4. OCR Deep Reading (อ่านทั้งไทยและอังกฤษ)
        ocr_img = ImageOps.grayscale(img)
        ocr_img = ImageOps.invert(ocr_img) # กลับสีเพื่อให้ Tesseract อ่านตัวหนังสือขาวบนพื้นดำได้แม่นขึ้น
        try:
            text = pytesseract.image_to_string(ocr_img, lang='eng+tha').lower()
        except:
            text = ""
            
        return hashes, text

def check_supreme_similarity(new_hashes, threshold=25):
    """
    ใช้เกณฑ์ตัดสินแบบ Cumulative Score (คะแนนรวมความต่าง)
    เนื่องจากเราเพิ่มขนาด Hash เป็น 16 ค่า Threshold จึงต้องปรับตาม
    25 คือค่าที่ 'แม่นยำสูงมาก' สำหรับ Hash ขนาด 16x16
    """
    for entry in image_vault:
        saved = entry['hashes']
        diff = (new_hashes['p'] - saved['p']) + \
               (new_hashes['d'] - saved['d']) + \
               (new_hashes['w'] - saved['w'])
        
        if diff <= threshold:
            return True
    return False

# --- COMMANDS ---

@bot.tree.command(name="on", description="เปิดระบบป้องกันระดับสูงสุด")
@app_commands.checks.has_permissions(administrator=True)
async def system_on(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = True
    await bot.change_presence(status=discord.Status.online)
    await interaction.response.send_message("🛡️ **RETH Guard Supreme:** ระบบตรวจจับความแม่นยำสูงออนไลน์!", ephemeral=False)

@bot.tree.command(name="off", description="ปิดระบบป้องกัน")
@app_commands.checks.has_permissions(administrator=True)
async def system_off(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = False
    await bot.change_presence(status=discord.Status.do_not_disturb)
    await interaction.response.send_message("⚠️ **RETH Guard Supreme:** ระบบหยุดการทำงานชั่วคราว", ephemeral=False)

@bot.tree.command(name="clear", description="ล้างฐานข้อมูลภาพทั้งหมด")
@app_commands.checks.has_permissions(administrator=True)
async def clear_wave(interaction: discord.Interaction):
    image_vault.clear()
    await interaction.response.send_message("🌊 **Wave Clear!** ฐานข้อมูลภาพถูกล้างเรียบร้อยแล้ว", ephemeral=False)

# --- ENGINE ---

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not PROTECTION_ENABLED:
        return

    # [📸 SUPREME IMAGE SCAN]
    if message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.jfif']):
                try:
                    img_bytes = await attachment.read()
                    hashes, ocr_text = optimize_for_scan(img_bytes)

                    # วิเคราะห์ 2 ทาง: ลายภาพ และ ข้อความในภาพ
                    is_spam_image = check_supreme_similarity(hashes)
                    is_spam_text = any(word in ocr_text for word in BANNED_WORDS)

                    if is_spam_image or is_spam_text:
                        await message.delete()
                        reason = "พบรูปภาพที่เคยถูกส่งแล้ว" if is_spam_image else "พบข้อความสแปมในรูปภาพ"
                        print(f"🔥 [SUPREME DELETE] Reason: {reason} from {message.author}")
                        await message.channel.send(f"🛡️ **RETH Guard:** สกัดกั้นสแปม ({reason}) เรียบร้อย!", delete_after=4)
                        return
                    
                    image_vault.append({'hashes': hashes})
                except Exception as e:
                    print(f"❌ [ENGINE ERROR] {e}")

    # [⌨️ KEYWORD SCAN]
    if any(word in message.content.lower() for word in BANNED_WORDS):
        try: await message.delete()
        except: pass

    await bot.process_commands(message)

# --- RUNTIME ---
keep_alive()
if TOKEN:
    bot.run(TOKEN)
