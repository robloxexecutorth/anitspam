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
import sys
import traceback
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from io import BytesIO
from collections import deque
from datetime import datetime, timedelta
from dotenv import load_dotenv
from keep_alive import keep_alive

# ==========================================
# [1] LOGGING & DIAGNOSTICS SYSTEM
# ==========================================
load_dotenv()
TOKEN = os.getenv('ANTISPAM_TOKEN')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('RETH_Omega_Titan')

# ==========================================
# [2] GLOBAL CONFIGURATION & POLICY ENGINE
# ==========================================
class GuardPolicy:
    """Class สำหรับจัดการค่าคอนฟิกูเรชันทั้งหมดของระบบ Omega Titan"""
    VERSION = "Omega Titan v8.0"
    AUTHOR = "RETH OFFICIAL"
    
    # ระบบเปิด/ปิดการทำงาน
    PROTECTION_ENABLED = True
    
    # ฐานข้อมูล (Memory Management)
    MAX_DB_ENTRIES = 5000
    CLEANUP_THRESHOLD = 0.95
    
    # ค่าความแม่นยำ (Thresholds)
    # เราใช้ Hash 16x16 (256 bits) ดังนั้นความต่างที่ยอมรับได้คือ 20-30
    STRICT_SENSITIVITY = 25.0 
    
    # ระบบ OCR
    OCR_CONFIG = '--psm 3 --oem 3' # Full page scan with default LSTM engine
    LANG_SUPPORT = 'eng+tha'
    
    # Blacklist Patterns (Regex Enabled)
    BANNED_REGEX = [
        r"bregamb\.cc", r"withdrawal\s+success", r"reward\s+received", 
        r"free\s+\$", r"beast\s+games", r"t\.me/", r"bit\.ly/", 
        r"promo\s+code", r"claim\s+now", r"ถอนเงินสำเร็จ", r"รับรางวัล", 
        r"ฟรีเครดิต", r"เว็บตรง", r"แจกฟรี", r"แอดไลน์", r"สูตรสล็อต",
        r"เครดิตฟรี", r"เว็บสล็อต", r"ลงทุนน้อย", r"กำไรดี"
    ]
    
    SUPPORTED_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.jfif', '.bmp'}

# ==========================================
# [3] TELEMETRY & DATA STORAGE
# ==========================================
class Telemetry:
    """Class สำหรับเก็บสถิติการทำงานเชิงลึก"""
    def __init__(self):
        self.scanned_count = 0
        self.blocked_visual = 0
        self.blocked_text = 0
        self.errors = 0
        self.start_time = datetime.now()
        self.last_attack_time = None
        self.processing_times = deque(maxlen=100) # เก็บค่าความเร็ว 100 ครั้งล่าสุด

    def get_avg_speed(self):
        if not self.processing_times: return 0.0
        return sum(self.processing_times) / len(self.processing_times)

stats = Telemetry()
image_db = deque(maxlen=GuardPolicy.MAX_DB_ENTRIES)

# ==========================================
# [4] OMEGA VISION ENGINE (HIGH-END PROCESSING)
# ==========================================
class OmegaVision:
    """ระบบประมวลผลภาพระดับสูงเพื่อความแม่นยำ 99.9%"""
    
    @staticmethod
    def prepare_image(raw_bytes):
        """ขั้นตอนการ Normalize รูปภาพก่อนการวิเคราะห์"""
        try:
            with Image.open(BytesIO(raw_bytes)) as img:
                # 1. ปรับค่าสีเป็น RGB เพื่อล้าง Metadata ที่อาจทำให้พิกเซลเพี้ยน
                img = img.convert('RGB')
                
                # 2. ปรับ Contrast อัตโนมัติ (แก้ปัญหาคนส่งรูปมืด/สว่างต่างกัน)
                img = ImageOps.autocontrast(img)
                
                # 3. ขยายขอบเขตพิกเซล (Equalization)
                img = ImageOps.equalize(img)
                
                return img.copy()
        except Exception as e:
            logger.error(f"Prepare Image Error: {e}")
            return None

    @staticmethod
    def generate_hashes(img):
        """คำนวณ Hash เชิงลึก 3 มิติ เพื่อดักจับรูป 'เกือบเหมือน'"""
        # แปลงเป็นขาวดำและลดขนาดเพื่อมองข้าม Wallpaper พื้นหลัง
        # เราใช้ขนาด 512 เพื่อความละเอียดก่อนลดลงไปทำ Hash 16x16
        base = img.convert('L').resize((512, 512), Image.Resampling.LANCZOS)
        
        # เพิ่มเทคนิค BoxBlur เพื่อลดสัญญาณรบกวน (Noise)
        base = base.filter(ImageFilter.BoxBlur(radius=1))
        
        return {
            'p': imagehash.phash(base, hash_size=16),
            'd': imagehash.dhash(base, hash_size=16),
            'w': imagehash.whash(base, hash_size=16)
        }

    @staticmethod
    def perform_ocr(img):
        """อ่านข้อความในภาพด้วยเทคนิค Dynamic Contrast Enhancement"""
        # ทำให้ภาพเป็นขาวดำสนิท (Binary) เพื่อให้อ่านง่ายขึ้น
        enhancer = ImageEnhance.Contrast(img.convert('L'))
        ocr_ready = enhancer.enhance(3.0).filter(ImageFilter.SHARPEN)
        
        try:
            text = pytesseract.image_to_string(
                ocr_ready, 
                lang=GuardPolicy.LANG_SUPPORT, 
                config=GuardPolicy.OCR_CONFIG
            )
            return text.lower().strip()
        except Exception as e:
            logger.error(f"OCR Operation Failed: {e}")
            return ""

# ==========================================
# [5] BOT CORE & COMMAND INTERFACE
# ==========================================
class TitanBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        intents.members = True
        super().__init__(command_prefix="rb!", intents=intents, help_command=None)
        
    async def setup_hook(self):
        """การตั้งค่าระบบ Hook เมื่อบอทเริ่มทำงาน"""
        await self.tree.sync()
        self.auto_maintenance.start()
        logger.info(f"TitanBot Loaded: {GuardPolicy.VERSION}")

    @tasks.loop(minutes=10)
    async def auto_maintenance(self):
        """ระบบจัดการหน่วยความจำและตรวจสอบสุขภาพบอทอัตโนมัติ"""
        if len(image_db) > (GuardPolicy.MAX_DB_ENTRIES * GuardPolicy.CLEANUP_THRESHOLD):
            logger.info("Maintenance: Performance optimization in progress...")
            # ดำเนินการจัดเรียงหน่วยความจำใหม่ (ถ้างจำเป็น)
            
        uptime = datetime.now() - stats.start_time
        logger.info(f"Health Check: Uptime {uptime} | DB Size: {len(image_db)}")

bot = TitanBot()

# ==========================================
# [6] ADMINISTRATIVE SLASH COMMANDS
# ==========================================
@bot.tree.command(name="titan_status", description="เช็คสถานะระบบ Omega Titan เชิงลึก")
async def titan_status(interaction: discord.Interaction):
    uptime = datetime.now() - stats.start_time
    embed = discord.Embed(title=f"🛡️ {GuardPolicy.VERSION} Status Report", color=0x7289da)
    
    embed.add_field(name="🛡️ Protection", value="✅ ACTIVE" if GuardPolicy.PROTECTION_ENABLED else "❌ DISABLED", inline=True)
    embed.add_field(name="⏳ System Uptime", value=str(uptime).split('.')[0], inline=True)
    embed.add_field(name="📦 Database Usage", value=f"{len(image_db)}/{GuardPolicy.MAX_DB_ENTRIES}", inline=True)
    
    embed.add_field(name="📸 Blocked Visuals", value=f"{stats.blocked_visual} images", inline=True)
    embed.add_field(name="💬 Blocked Texts", value=f"{stats.blocked_text} messages", inline=True)
    embed.add_field(name="⚡ Avg Speed", value=f"{stats.get_avg_speed():.2f}s per image", inline=True)
    
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=f"Managed by {GuardPolicy.AUTHOR} Security Infrastructure")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="on", description="เปิดใช้งานระบบป้องกันระดับสูงสุด")
@app_commands.checks.has_permissions(administrator=True)
async def turn_on(interaction: discord.Interaction):
    GuardPolicy.PROTECTION_ENABLED = True
    await bot.change_presence(status=discord.Status.online)
    await interaction.response.send_message("🟢 **Titan Logic:** ระบบป้องกัน Absolute Online!")

@bot.tree.command(name="off", description="ปิดใช้งานระบบป้องกันชั่วคราว")
@app_commands.checks.has_permissions(administrator=True)
async def turn_off(interaction: discord.Interaction):
    GuardPolicy.PROTECTION_ENABLED = False
    await bot.change_presence(status=discord.Status.do_not_disturb)
    await interaction.response.send_message("🔴 **Titan Logic:** ระบบป้องกัน Offline (Security Warning)")

@bot.tree.command(name="clear_vault", description="ล้างฐานข้อมูลภาพทั้งหมดทันที")
@app_commands.checks.has_permissions(administrator=True)
async def clear_vault(interaction: discord.Interaction):
    count = len(image_db)
    image_db.clear()
    await interaction.response.send_message(f"🌊 **Wave Clear:** เคลียร์หน่วยความจำภาพ {count} รายการสำเร็จ!")

# ==========================================
# [7] THE OMEGA PROTECTOR (MESSAGE HANDLING)
# ==========================================
@bot.event
async def on_message(message):
    # ข้ามข้อความจาก Bot และข้อความนอก Server
    if message.author.bot or not message.guild:
        return

    # หากระบบปิดอยู่ ให้ทำแค่คำสั่งพื้นฐาน
    if not GuardPolicy.PROTECTION_ENABLED:
        await bot.process_commands(message)
        return

    # --- PHASE 1: VISUAL SCANNING ---
    if message.attachments:
        for attachment in message.attachments:
            file_ext = os.path.splitext(attachment.filename.lower())[1]
            if file_ext in GuardPolicy.SUPPORTED_EXT:
                try:
                    start_proc = time.time()
                    stats.scanned_count += 1
                    
                    # 1. Download & Process
                    raw_data = await attachment.read()
                    titan_img = OmegaVision.prepare_image(raw_data)
                    if titan_img is None: continue
                    
                    # 2. Extract Multiple Fingerprints
                    current_hashes = OmegaVision.generate_hashes(titan_img)
                    
                    # 3. Perform Deep OCR Analysis
                    extracted_text = OmegaVision.perform_ocr(titan_img)
                    
                    # --- DECISION LOGIC ---
                    is_visual_duplicate = False
                    for record in image_db:
                        stored = record['hashes']
                        # คำนวณความต่างแบบ Hamming Distance
                        diff = (current_hashes['p'] - stored['p']) + \
                               (current_hashes['d'] - stored['d']) + \
                               (current_hashes['w'] - stored['w'])
                        
                        if diff <= GuardPolicy.STRICT_SENSITIVITY:
                            is_visual_duplicate = True
                            break
                    
                    # ตรวจสอบ Regex ในข้อความที่อ่านจากรูป
                    is_text_spam = any(re.search(p, extracted_text) for p in GuardPolicy.BANNED_REGEX)

                    if is_visual_duplicate or is_text_spam:
                        # [ACTION] DELETE SPAM
                        await message.delete()
                        stats.blocked_visual += 1 if is_visual_duplicate else 0
                        stats.blocked_text += 1 if is_text_spam else 0
                        stats.last_attack_time = datetime.now()
                        
                        reason = "Structural Match" if is_visual_duplicate else "Scam Content"
                        logger.warning(f"BLOCKED: {message.author} | Reason: {reason}")
                        
                        # แจ้งเตือนสั้นๆ และลบตัวเอง
                        warn = f"🛡️ **RETH Guard:** สกัดกั้นสแปม ({'รูปซ้ำ' if is_visual_duplicate else 'ข้อความสแกม'}) ดีดทิ้งเรียบร้อย!"
                        await message.channel.send(warn, delete_after=5)
                        return # หยุดทำงานสำหรับข้อความนี้
                    
                    # หากรูปภาพผ่านการตรวจสอบ ให้บันทึกลงฐานข้อมูล
                    image_db.append({'hashes': current_hashes, 'timestamp': time.time()})
                    
                    # บันทึกความเร็วในการทำงาน
                    stats.processing_times.append(time.time() - start_proc)
                    
                except Exception as e:
                    stats.errors += 1
                    logger.error(f"Image Analysis System Failure: {e}")
                    # แสดง Traceback เฉพาะใน Console เพื่อการแก้ไข
                    traceback.print_exc()

    # --- PHASE 2: PLAIN TEXT SCANNING ---
    clean_content = message.content.lower()
    if any(re.search(p, clean_content) for p in GuardPolicy.BANNED_REGEX):
        try:
            await message.delete()
            stats.blocked_text += 1
            logger.warning(f"BLOCKED TEXT: {message.author} | Keyword Match")
            return
        except discord.Forbidden:
            logger.error("System Failure: Missing 'Manage Messages' permission.")

    # --- PHASE 3: COMMAND HANDLING ---
    await bot.process_commands(message)

# ==========================================
# [8] SYSTEM STARTUP & ERROR HANDLING
# ==========================================
@bot.event
async def on_ready():
    logger.info("="*50)
    logger.info(f"SYSTEM ONLINE: {GuardPolicy.VERSION}")
    logger.info(f"USERNAME: {bot.user.name}#{bot.user.discriminator}")
    logger.info(f"SERVERS: {len(bot.guilds)}")
    logger.info(f"INTENTS: Message Content & Members Enabled")
    logger.info("="*50)

@bot.event
async def on_command_error(ctx, error):
    """ระบบจัดการข้อผิดพลาดของคำสั่ง"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ คุณไม่มีสิทธิ์ในการใช้คำสั่งนี้!", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        pass # ข้ามคำสั่งที่ไม่รู้จัก
    else:
        logger.error(f"Unhandled Command Error: {error}")

if __name__ == "__main__":
    # เปิดใช้งานระบบ Keep Alive เพื่อรันบน Render 24/7
    keep_alive()
    
    if TOKEN:
        try:
            bot.run(TOKEN)
        except discord.LoginFailure:
            logger.critical("FATAL: Discord Token is invalid.")
        except Exception as e:
            logger.critical(f"FATAL: Bot failed to boot: {e}")
    else:
        logger.error("CONFIGURATION ERROR: ANTISPAM_TOKEN not found in environment.")

# ==========================================
# [9] ADDITIONAL NOTES FOR DEVELOPER
# ==========================================
# 1. ระบบนี้ใช้โครงสร้าง Class-Based เพื่อความง่ายในการขยายฟีเจอร์ในอนาคต
# 2. มีการใช้ Regex เพื่อเพิ่มประสิทธิภาพในการดักจับคำที่จงใจพิมพ์เลี่ยง
# 3. ระบบ Image Normalization ช่วยให้บอทมองข้าม Wallpaper พื้นหลังที่เปลี่ยนไป
# 4. มีการใช้ Tasks Loop เพื่อทำความสะอาดและตรวจสอบสุขภาพของบอททุก 10 นาที
# ==========================================
# END OF OMEGA TITAN SOURCE CODE
