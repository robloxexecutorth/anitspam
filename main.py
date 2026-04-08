import discord
from discord import app_commands
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

# ระบบสถานะการทำงาน
PROTECTION_ENABLED = True

# ฐานข้อมูลลายนิ้วมือภาพ (Wave Cache)
image_vault = deque(maxlen=2000)

FORBIDDEN_PHRASES = ["bregamb.cc", "promo code", "free $", "beast games", "t.me/", "bit.ly/"]

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True

class RETHBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        
    async def setup_hook(self):
        # Sync Slash Commands ไปยัง Discord
        await self.tree.sync()
        print("✅ [SYNC] Slash Commands Synced!")

bot = RETHBot()

# --- UTILITY FUNCTIONS ---

def compute_multi_hash(img_bin):
    with Image.open(BytesIO(img_bin)) as img:
        img = img.convert('RGB')
        return {
            'p': imagehash.phash(img),
            'd': imagehash.dhash(img),
            'w': imagehash.whash(img)
        }

def is_spam(new_hashes, threshold=12):
    for entry in image_vault:
        saved = entry['hashes']
        diff = (new_hashes['p'] - saved['p']) + \
               (new_hashes['d'] - saved['d']) + \
               (new_hashes['w'] - saved['w'])
        if diff <= threshold:
            return True
    return False

# --- SLASH COMMANDS ---

@bot.tree.command(name="on", description="เปิดระบบป้องกัน RETH Guard")
@app_commands.checks.has_permissions(administrator=True)
async def system_on(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = True
    await bot.change_presence(status=discord.Status.online)
    await interaction.response.send_message("🟢 **RETH Guard:** ระบบป้องกันเปิดใช้งานแล้ว! (Elite Mode)", ephemeral=False)

@bot.tree.command(name="off", description="ปิดระบบป้องกัน RETH Guard")
@app_commands.checks.has_permissions(administrator=True)
async def system_off(interaction: discord.Interaction):
    global PROTECTION_ENABLED
    PROTECTION_ENABLED = False
    await bot.change_presence(status=discord.Status.do_not_disturb)
    await interaction.response.send_message("🔴 **RETH Guard:** ระบบป้องกันถูกปิดใช้งานชั่วคราว", ephemeral=False)

@bot.tree.command(name="clear", description="Wave Clear: ล้างฐานข้อมูลรูปซ้ำทั้งหมด")
@app_commands.checks.has_permissions(administrator=True)
async def clear_wave(interaction: discord.Interaction):
    count = len(image_vault)
    image_vault.clear()
    await interaction.response.send_message(f"🌊 **Wave Clear!** ล้างข้อมูลลายนิ้วมือภาพสำเร็จ {count} รายการ", ephemeral=False)

# --- EVENTS ---

@bot.event
async def on_ready():
    print(f"--- RETH Guard Alpha v3.0 ---")
    print(f"Status: {'ONLINE' if PROTECTION_ENABLED else 'OFFLINE'}")
    print(f"Slash Commands: Ready")
    print(f"-----------------------------")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # ถ้าปิดระบบอยู่ ไม่ต้องทำอะไรเลย
    if not PROTECTION_ENABLED:
        return

    # 1. ตรวจสอบรูปภาพสแปม
    if message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.jfif']):
                try:
                    img_bytes = await attachment.read()
                    current_hashes = compute_multi_hash(img_bytes)

                    if is_spam(current_hashes):
                        await message.delete()
                        await message.channel.send(f"🛡️ **RETH Guard:** พบรูปภาพซ้ำ/สแปม ดีดทิ้งเรียบร้อย!", delete_after=3)
                        return
                    
                    image_vault.append({'hashes': current_hashes, 'user': message.author.id})
                except Exception as e:
                    print(f"[ERROR] {e}")

    # 2. ตรวจสอบข้อความ
    msg_clean = message.content.lower()
    if any(phrase in msg_clean for phrase in FORBIDDEN_PHRASES):
        try: await message.delete()
        except: pass

    await bot.process_commands(message)

# --- RUN ---
keep_alive()
if TOKEN:
    bot.run(TOKEN)
