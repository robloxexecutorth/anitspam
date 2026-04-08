import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import imagehash
import pytesseract
import asyncio
from PIL import Image, ImageOps, ImageFilter
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from keep_alive import keep_alive

# --- 1. SETTINGS & CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN')

# Global States
PROTECTION_ENABLED = True
image_vault = deque(maxlen=2000)

# คำต้องห้าม (ทั้งในแชทและในรูปภาพ)
BANNED_WORDS = [
    "bregamb.cc", "withdrawal success", "reward received", "free $", 
    "beast games", "t.me/", "bit.ly/", "promo code", "gift card"
]

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True

class RETHBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="rb!", intents=intents, help_command=None)
        
    async def setup_hook(self):
        # Sync Slash Commands ไปยัง Discord ทันทีที่รัน
        await self.tree.sync()
        print("✅ [ULTRA SYNC] Commands & Systems Synced!")

bot = RETHBot()

# --- 2. THE VISION ENGINE (HASH + OCR) ---

def scan_visual_content(img_bin):
    """
    วิเคราะห์รูปภาพเชิงลึก: ทำความสะอาดรูปภาพ -> ทำ Hash -> อ่านข้อความ
    """
    with Image.open(BytesIO(img_bin)) as img:
        img = img.convert('RGB')
        
        # ส่วนที่ 1: เตรียมสำหรับการทำ Hash (ลด Noise เพื่อดักจับรูปที่ต่างกันนิดเดียว)
        # ปรับขนาดและเบลอเล็กน้อยเพื่อให้มองข้ามจุดเล็กๆ เช่น เวลาบนจอ
        hash_prep = img.resize((256, 256), Image.Resampling.LANCZOS)
        hash_prep = hash_prep.filter(ImageFilter.GaussianBlur(radius=1))
        
        hashes = {
            'p': imagehash.phash(hash_prep),
            'd': imagehash.dhash(hash_prep),
            'w': imagehash.whash(hash_prep)
        }
        
        # ส่วนที่ 2: เตรียมสำหรับการอ่าน OCR (ทำให้ชัดเพื่อให้บอทอ่านตัวหนังสือได้)
        ocr_prep = ImageOps.grayscale(img)
        ocr_prep = ImageOps.autocontrast(ocr_prep)
        # อ่านข้อความในภาพ
        try:
            extracted_text = pytesseract.image_to_string(ocr_prep).lower()
        except:
            extracted_text = ""
            
        return hashes, extracted_text

def is_duplicate(new_hashes, threshold=5):
    """
    เปรียบเทียบความต่างของภาพสะสม (Threshold 5 = โหดสุด)
    """
    for entry in image_vault:
        saved = entry['hashes']
        diff = (new_hashes['p'] - saved['p']) + \
               (new_hashes['d'] - saved['d']) + \
               (new_hashes['w'] - saved['w'])
        if diff <= threshold:
            return True
    return False

# --- 3. SLASH COMMANDS CONTROL ---

@bot.tree.command(name="on", description="เปิดระบบป้องกันระดับสูงสุด (Zero-Tolerance)")
@app_commands.checks.has_permissions(administrator=True)
async def system_on(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = True
    await bot.change_presence(status=discord.Status.online)
    await interaction.response.send_message("🟢 **RETH Guard:** ระบบ Omni-Vision ออนไลน์แล้ว!", ephemeral=False)

@bot.tree.command(name="off", description="ปิดระบบป้องกันชั่วคราว")
@app_commands.checks.has_permissions(administrator=True)
async def system_off(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = False
    await bot.change_presence(status=discord.Status.do_not_disturb)
    await interaction.response.send_message("🔴 **RETH Guard:** ระบบป้องกันถูกปิดใช้งาน", ephemeral=False)

@bot.tree.command(name="clear", description="Wave Clear: ล้างหน่วยความจำภาพทั้งหมด")
@app_commands.checks.has_permissions(administrator=True)
async def clear_wave(interaction: discord.Interaction):
    count = len(image_vault)
    image_vault.clear()
    await interaction.response.send_message(f"🌊 **Wave Clear!** ล้างลายนิ้วมือภาพสำเร็จ {count} รายการ", ephemeral=False)

# --- 4. CORE EVENTS ---

@bot.event
async def on_ready():
    print(f"🚀 [SYSTEM LIVE] RETH Guard Alpha v5.0")
    print(f"Precision: Zero-Tolerance (Threshold 5)")
    print(f"Vision: OCR + Multi-Hashing Enabled")
    print(f"------------------------------------")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not PROTECTION_ENABLED:
        return

    # 🛡️ ระบบสแกนรูปภาพ (Image Analysis)
    if message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.jfif']):
                try:
                    img_bytes = await attachment.read()
                    hashes, text_in_img = scan_visual_content(img_bytes)

                    # ตรวจสอบ 1: รูปภาพเหมือนกันไหม? (Visual Duplicate)
                    visual_match = is_duplicate(hashes)
                    
                    # ตรวจสอบ 2: มีคำสแกมในรูปไหม? (OCR Detection)
                    text_match = any(word in text_in_img for word in BANNED_WORDS)

                    if visual_match or text_match:
                        await message.delete()
                        log_info = "Visual Duplicate" if visual_match else f"Banned Text in Image: {text_in_img[:20]}..."
                        print(f"🔥 [DELETED] {log_info} from {message.author}")
                        await message.channel.send(f"🛡️ **RETH Guard:** ตรวจพบสแปม ({'รูปซ้ำ' if visual_match else 'ข้อความต้องห้ามในรูป'}) ดีดทิ้งเรียบร้อย!", delete_after=3)
                        return
                    
                    # บันทึกเป็นรูปใหม่
                    image_vault.append({'hashes': hashes})
                except Exception as e:
                    print(f"❌ [SCAN ERROR]: {e}")

    # 🛡️ ระบบสแกนข้อความในแชท (Keyword Filtering)
    msg_clean = message.content.lower()
    if any(word in msg_clean for word in BANNED_WORDS):
        try:
            await message.delete()
            print(f"🚫 [DELETED] Keyword spam from {message.author}")
            return
        except: pass

    await bot.process_commands(message)

# --- 5. RUNTIME ---
keep_alive()
if TOKEN:
    bot.run(TOKEN)
