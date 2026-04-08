import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import imagehash
import pytesseract
import asyncio
import numpy as np
from PIL import Image, ImageOps, ImageFilter
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from keep_alive import keep_alive

# --- 1. SETTINGS & CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN')

PROTECTION_ENABLED = True
image_vault = deque(maxlen=2000)

BANNED_WORDS = [
    "bregamb.cc", "withdrawal success", "reward received", "free $", 
    "beast games", "t.me/", "bit.ly/", "promo code", "gift card", "claim now"
]

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True

class RETHBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="rb!", intents=intents, help_command=None)
        
    async def setup_hook(self):
        await self.tree.sync()
        print("✅ [AI-SENTINEL SYNC] Systems & AI Logic Ready!")

bot = RETHBot()

# --- 2. THE AI & VISION ENGINE ---

def ai_visual_analysis(img_bin):
    """
    วิเคราะห์รูปภาพด้วย 3 ระบบ: Multi-Hash + OCR + AI Structural Check
    """
    with Image.open(BytesIO(img_bin)) as img:
        img = img.convert('RGB')
        
        # [AI Step 1] ทำความสะอาดรูปภาพเพื่อดักจับรูป 'เกือบเหมือน'
        # ย่อขนาดลงเล็กน้อยและทำ Gray-scale เพื่อหาโครงสร้างหลัก (Structural Analysis)
        ai_struct_img = img.resize((128, 128)).convert('L')
        struct_hash = imagehash.whash(ai_struct_img)

        # [AI Step 2] Multi-Hashing (ลายนิ้วมือภาพ 3 มิติ)
        hash_prep = img.resize((256, 256), Image.Resampling.LANCZOS)
        hash_prep = hash_prep.filter(ImageFilter.BoxBlur(radius=1)) # AI แนะนำให้ใช้ BoxBlur เพื่อคงขอบภาพ
        
        hashes = {
            'p': imagehash.phash(hash_prep),
            'd': imagehash.dhash(hash_prep),
            'w': struct_hash
        }
        
        # [AI Step 3] OCR Deep Scan (อ่านข้อความ)
        ocr_prep = ImageOps.autocontrast(ImageOps.grayscale(img))
        try:
            extracted_text = pytesseract.image_to_string(ocr_prep, lang='eng+tha').lower()
        except:
            extracted_text = ""
            
        return hashes, extracted_text

def is_duplicate_ai(new_hashes, sensitivity=5):
    """
    ระบบ AI เปรียบเทียบความต่าง: ยิ่งรูปคล้าย ยิ่งดีดไว
    """
    for entry in image_vault:
        saved = entry['hashes']
        # คำนวณความต่างเชิงโครงสร้าง
        diff = (new_hashes['p'] - saved['p']) + \
               (new_hashes['d'] - saved['d']) + \
               (new_hashes['w'] - saved['w'])
        
        if diff <= sensitivity:
            return True
    return False

# --- 3. COMMAND CENTER ---

@bot.tree.command(name="on", description="เปิดระบบป้องกัน AI Omni-Vision")
@app_commands.checks.has_permissions(administrator=True)
async def system_on(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = True
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(name="AI Protection Active"))
    await interaction.response.send_message("🛡️ **RETH Guard AI:** ระบบวิเคราะห์ภาพขั้นสูงเปิดใช้งานแล้ว!", ephemeral=False)

@bot.tree.command(name="off", description="ปิดระบบป้องกัน")
@app_commands.checks.has_permissions(administrator=True)
async def system_off(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = False
    await bot.change_presence(status=discord.Status.do_not_disturb)
    await interaction.response.send_message("⚠️ **RETH Guard AI:** ระบบป้องกันหยุดทำงานชั่วคราว", ephemeral=False)

@bot.tree.command(name="clear", description="Wave Clear: ล้างฐานข้อมูล AI")
@app_commands.checks.has_permissions(administrator=True)
async def clear_wave(interaction: discord.Interaction):
    count = len(image_vault)
    image_vault.clear()
    await interaction.response.send_message(f"🌊 **Wave Clear!** ล้างลายนิ้วมือภาพ {count} รายการสำเร็จ", ephemeral=False)

# --- 4. CORE ENGINE ---

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or not PROTECTION_ENABLED:
        return

    # [📸 AI IMAGE ANALYSIS]
    if message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.jfif']):
                try:
                    img_bytes = await attachment.read()
                    hashes, text_in_img = ai_visual_analysis(img_bytes)

                    # วิเคราะห์ 2 ชั้น: ลายภาพ (Hash) + เนื้อหา (OCR)
                    is_visual_spam = is_duplicate_ai(hashes, sensitivity=6) # ปรับให้ดุขึ้นเป็น 6
                    is_text_spam = any(word in text_in_img for word in BANNED_WORDS)

                    if is_visual_spam or is_text_spam:
                        await message.delete()
                        log_type = "AI Duplicate Match" if is_visual_spam else "AI Content Detection"
                        print(f"🔥 [AI DELETED] {log_type} from {message.author}")
                        await message.channel.send(f"🛡️ **RETH Guard AI:** พบสแปมผ่านการวิเคราะห์ {log_type} ดีดออกทันที!", delete_after=3)
                        return
                    
                    image_vault.append({'hashes': hashes})
                except Exception as e:
                    print(f"❌ [AI ERROR]: {e}")

    # [⌨️ KEYWORD SCAN]
    if any(word in message.content.lower() for word in BANNED_WORDS):
        try: await message.delete(); print(f"🚫 [DELETED] Text spam: {message.author}")
        except: pass

    await bot.process_commands(message)

# --- 5. RUNTIME ---
keep_alive()
if TOKEN:
    bot.run(TOKEN)
