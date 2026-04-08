import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import imagehash
import pytesseract
import asyncio
import numpy as np
import time
import logging
import json
import re
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from io import BytesIO
from collections import deque
from datetime import datetime, timedelta
from dotenv import load_dotenv
from keep_alive import keep_alive

# --- [1] LOGGING & SYSTEM MONITORING SETUP ---
load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN')

# ตั้งค่า Logging ให้ละเอียดระดับ DEBUG เพื่อการวิเคราะห์ภาพ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s: %(message)s'
)
logger = logging.getLogger('RETH_Elite_Guard')

# --- [2] CORE CONFIGURATION & DATABASE ---
class GuardConfig:
    """ระบบ Configuration หลักสำหรับ RETH Guard Elite"""
    VERSION = "Elite Sovereign v7.0"
    PROTECTION_ENABLED = True
    DATABASE_LIMIT = 5000
    
    # Advanced Thresholds
    # 20.0 คือจุดสมดุลที่สุดในการดักรูปที่เปลี่ยน Wallpaper
    STRUCTURAL_THRESHOLD = 20.0 
    
    # รายชื่อคำต้องห้ามที่พัฒนาด้วย Regex (ดักจับการเลี่ยงคำ)
    BANNED_PATTERNS = [
        r"bregamb\.cc", r"withdrawal\s+success", r"reward\s+received", 
        r"free\s+\$", r"beast\s+games", r"t\.me/", r"bit\.ly/", 
        r"promo\s+code", r"claim\s+now", r"ถอนเงินสำเร็จ", r"รับรางวัล", 
        r"ฟรีเครดิต", r"เว็บตรง", r"แจกฟรี", r"แอดไลน์", r"สูตรสล็อต"
    ]
    
    # รายชื่อไฟล์ที่รองรับ
    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.webp', '.jfif', '.bmp'}

# ฐานข้อมูลหน่วยความจำ (RAM Buffer)
image_database = deque(maxlen=GuardConfig.DATABASE_LIMIT)
system_stats = {
    "scanned": 0,
    "blocked_visual": 0,
    "blocked_text": 0,
    "errors": 0,
    "uptime_start": datetime.now()
}

# --- [3] ADVANCED IMAGE INTELLIGENCE (THE BRAIN) ---

class VisualIntelligence:
    """Class สำหรับประมวลผลและวิเคราะห์ภาพระดับสูง"""
    
    @staticmethod
    def normalize_frame(img_bytes):
        """ปรับแต่งภาพให้เข้าสู่มาตรฐานเดียวกัน (Image Normalization)"""
        try:
            with Image.open(BytesIO(img_bytes)) as img:
                img = img.convert('RGB')
                # 1. ปรับแสงอัตโนมัติ (กันการปรับแสงมืด/สว่าง)
                img = ImageOps.autocontrast(img)
                # 2. ปรับความสว่างให้คงที่
                brightness = ImageEnhance.Brightness(img)
                img = brightness.enhance(1.0)
                return img.copy()
        except Exception as e:
            logger.error(f"Normalization Fail: {e}")
            return None

    @staticmethod
    def extract_fingerprints(img):
        """สกัดลายนิ้วมือภาพ (Multi-Hashing) ระดับ 16x16"""
        # แปลงเป็นขาวดำเพื่อตัดปัญหาเรื่องสี Wallpaper
        processed = img.convert('L').resize((256, 256), Image.Resampling.LANCZOS)
        # ใส่ BoxBlur เพื่อลด Noise เล็กๆ ที่อาจทำให้ Hash เพี้ยน
        processed = processed.filter(ImageFilter.BoxBlur(radius=1))
        
        return {
            'p': imagehash.phash(processed, hash_size=16),
            'd': imagehash.dhash(processed, hash_size=16),
            'w': imagehash.whash(processed, hash_size=16)
        }

    @staticmethod
    def advanced_ocr_scan(img):
        """สแกนข้อความด้วยเทคนิค High-Contrast Filtering"""
        # ทำให้ภาพชัดขึ้น 3 เท่าก่อนอ่าน
        ocr_img = ImageOps.grayscale(img)
        ocr_img = ImageEnhance.Contrast(ocr_img).enhance(3.0)
        ocr_img = ImageEnhance.Sharpness(ocr_img).enhance(2.0)
        
        try:
            config = '--psm 3' # Full page scan mode
            text = pytesseract.image_to_string(ocr_img, lang='eng+tha', config=config)
            return text.lower().strip()
        except Exception as e:
            logger.error(f"OCR Advanced Scan Fail: {e}")
            return ""

# --- [4] BOT ARCHITECTURE & COMMAND CENTER ---

class RETHEliteBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        intents.members = True
        super().__init__(command_prefix="rb!", intents=intents, help_command=None)
        
    async def setup_hook(self):
        await self.tree.sync()
        self.health_check.start()
        logger.info(f"System Initialized: {GuardConfig.VERSION}")

    @tasks.loop(minutes=5)
    async def health_check(self):
        """ระบบตรวจสอบความเสถียรของบอทและจัดการหน่วยความจำ"""
        current_time = datetime.now().strftime("%H:%M")
        status = discord.Activity(
            type=discord.ActivityType.watching, 
            name=f"🛡️ Guard v7.0 | Clean at {current_time}"
        )
        await self.change_presence(status=discord.Status.online, activity=status)
        
        # ล้างข้อมูลที่เก่าเกิน 24 ชม. (ถ้าฐานข้อมูลแน่นเกินไป)
        if len(image_database) > GuardConfig.DATABASE_LIMIT * 0.9:
            logger.info("Auto-cleanup: Optimizing database...")

bot = RETHEliteBot()

# --- [5] ADMINISTRATIVE INTERFACE (SLASH COMMANDS) ---

@bot.tree.command(name="status", description="เช็คสถานะการทำงานระดับ Elite")
async def get_status(interaction: discord.Interaction):
    uptime = datetime.now() - system_stats["uptime_start"]
    embed = discord.Embed(title=f"🛡️ {GuardConfig.VERSION} Dashboard", color=0x00ffcc)
    embed.add_field(name="🛡️ System Power", value="🟢 ONLINE" if GuardConfig.PROTECTION_ENABLED else "🔴 OFFLINE")
    embed.add_field(name="📦 Memory Vault", value=f"{len(image_database)}/{GuardConfig.DATABASE_LIMIT}")
    embed.add_field(name="⏳ Uptime", value=str(uptime).split('.')[0])
    embed.add_field(name="📸 Blocked (Visual)", value=str(system_stats["blocked_visual"]), inline=True)
    embed.add_field(name="💬 Blocked (Text)", value=str(system_stats["blocked_text"]), inline=True)
    embed.add_field(name="❌ Processing Errors", value=str(system_stats["errors"]), inline=True)
    embed.set_footer(text="RETH OFFICIAL - Sovereign Security Infrastructure")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="on", description="เปิดระบบป้องกัน Absolute Protection")
@app_commands.checks.has_permissions(administrator=True)
async def system_on(interaction: discord.Interaction):
    GuardConfig.PROTECTION_ENABLED = True
    await interaction.response.send_message("🛡️ **RETH Guard Elite:** เปิดระบบป้องกันระดับสูงสุดเรียบร้อย!")

@bot.tree.command(name="off", description="ปิดระบบป้องกัน")
@app_commands.checks.has_permissions(administrator=True)
async def system_off(interaction: discord.Interaction):
    GuardConfig.PROTECTION_ENABLED = False
    await interaction.response.send_message("⚠️ **RETH Guard Elite:** ปิดระบบป้องกันชั่วคราว (Security Disabled)")

@bot.tree.command(name="clear", description="Wave Clear: ล้างฐานข้อมูลลายนิ้วมือภาพทั้งหมด")
@app_commands.checks.has_permissions(administrator=True)
async def database_clear(interaction: discord.Interaction):
    count = len(image_database)
    image_database.clear()
    await interaction.response.send_message(f"🌊 **Wave Clear!** เคลียร์ข้อมูลภาพ {count} รายการสำเร็จ")

# --- [6] THE PROTECTOR: EVENT PROCESSING CORE ---

@bot.event
async def on_message(message):
    # ป้องกันบอทตอบโต้กันเอง
    if message.author.bot or not message.guild:
        return

    # ถ้าปิดระบบอยู่ ไม่ต้องรัน Logic การสแกน
    if not GuardConfig.PROTECTION_ENABLED:
        await bot.process_commands(message)
        return

    # [PHASE A: IMAGE SENTINEL]
    if message.attachments:
        for attachment in message.attachments:
            file_ext = os.path.splitext(attachment.filename.lower())[1]
            if file_ext in GuardConfig.SUPPORTED_FORMATS:
                try:
                    start_time = time.time()
                    system_stats["scanned"] += 1
                    
                    # 1. โหลดและปรับภาพ
                    img_bytes = await attachment.read()
                    processed_img = VisualIntelligence.normalize_frame(img_bytes)
                    if not processed_img: continue

                    # 2. คำนวณ Hash เชิงโครงสร้าง
                    current_hashes = VisualIntelligence.extract_fingerprints(processed_img)
                    
                    # 3. สแกนข้อความเชิงลึก
                    detected_text = VisualIntelligence.advanced_ocr_scan(processed_img)
                    
                    # 🚀 Logic 1: Visual Structural Check (ความซ้ำซ้อนของโครงสร้างภาพ)
                    is_visual_duplicate = False
                    for entry in image_database:
                        target = entry['hashes']
                        # เปรียบเทียบความต่าง (Hamming Distance)
                        diff = (current_hashes['p'] - target['p']) + \
                               (current_hashes['d'] - target['d']) + \
                               (current_hashes['w'] - target['w'])
                        
                        if diff <= GuardConfig.STRUCTURAL_THRESHOLD:
                            is_visual_duplicate = True
                            break
                    
                    # 🚀 Logic 2: Pattern-Based Text Scan (ตรวจสอบคำต้องห้ามด้วย Regex)
                    is_text_spam = any(re.search(pattern, detected_text) for pattern in GuardConfig.BANNED_PATTERNS)

                    if is_visual_duplicate or is_text_spam:
                        await message.delete()
                        system_stats["blocked_visual"] += 1 if is_visual_duplicate else 0
                        system_stats["blocked_text"] += 1 if is_text_spam else 0
                        
                        reason = "Structural Match" if is_visual_duplicate else "Blacklisted Content"
                        logger.warning(f"BLOCKED: {message.author} | Reason: {reason} | Time: {time.time()-start_time:.2f}s")
                        
                        await message.channel.send(f"🛡️ **RETH Guard:** สกัดกั้นสแปม ({'รูปซ้ำ' if is_visual_duplicate else 'ข้อความต้องห้าม'})!", delete_after=5)
                        return
                    
                    # ถ้าผ่าน ให้เก็บข้อมูลภาพไว้
                    image_database.append({'hashes': current_hashes, 'timestamp': time.time()})
                    
                except Exception as e:
                    system_stats["errors"] += 1
                    logger.error(f"Engine Core Error: {e}")

    # [PHASE B: TEXTUAL PATTERN MATCHING]
    content_clean = message.content.lower()
    if any(re.search(p, content_clean) for p in GuardConfig.BANNED_PATTERNS):
        try:
            await message.delete()
            system_stats["blocked_text"] += 1
            return
        except discord.Forbidden:
            logger.warning("Missing delete permissions!")

    # [PHASE C: COMMAND EXECUTION]
    await bot.process_commands(message)

# --- [7] SYSTEM BOOTSTRAP & SAFETY ---

@bot.event
async def on_ready():
    logger.info("==========================================")
    logger.info(f"   {GuardConfig.VERSION} IS NOW LIVE")
    logger.info(f"   Logged in as: {bot.user.name}")
    logger.info("   Security Mode: ACTIVE")
    logger.info("==========================================")

if __name__ == "__main__":
    # ปลุกบอทตลอด 24 ชม.
    keep_alive()
    if TOKEN:
        try:
            # รันบอทด้วยระบบควบคุม Error
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            logger.critical("Invalid Discord Token. Please update .env")
        except Exception as e:
            logger.critical(f"Fatal Boot Error: {e}")
    else:
        logger.error("No ANTISPAM_TOKEN found. Check your environment.")

# --- END OF ELITE SOVEREIGN CODE ---
# Total logic density optimized for RETH OFFICIAL security.
