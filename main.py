import discord
from discord import app_commands, ui
from discord.ext import commands
import os
import aiohttp
import asyncio
from PIL import Image
import imagehash
from io import BytesIO
from collections import deque
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
WEB_LINK = "https://yourwebsite.com"

# เก็บค่า Hash ของรูปภาพที่เคยลบไปแล้ว (จำได้สูงสุด 100 รูป)
spam_image_hashes = deque(maxlen=100)
setup_channels = set()

# --- ฟังก์ชันสแกนรูปภาพ ---
async def is_spam_image(attachment):
    if not attachment.content_type or not attachment.content_type.startswith('image'):
        return False
    
    try:
        # อ่านรูปภาพจาก Discord เข้ามาใน Memory
        img_data = await attachment.read()
        img = Image.open(BytesIO(img_data))
        
        # สร้างรหัส Hash (ลายนิ้วมือรูปภาพ)
        current_hash = str(imagehash.average_hash(img))
        
        # ตรวจสอบว่าเคยมีรูปนี้ส่งมาหรือยัง
        if current_hash in spam_image_hashes:
            return True
        
        # ถ้ายังไม่เคยมี ให้เก็บรหัสไว้ในหน่วยความจำ
        spam_image_hashes.append(current_hash)
        return False
    except Exception as e:
        print(f"Image scan error: {e}")
        return False

# ... (ScriptPaginator และ search_logic เดิมของคุณ) ...

@bot.event
async def on_message(message):
    if message.author == bot.user: return

    # 1. ระบบตรวจจับรูปภาพสแปม
    if message.attachments:
        for attachment in message.attachments:
            if await is_spam_image(attachment):
                try:
                    await message.delete()
                    await message.channel.send(f"🚫 **RETH Shield:** Spam image detected and removed!", delete_after=5)
                    print(f"Blocked spam image from {message.author}")
                    return # หยุดการทำงานทันที
                except:
                    pass

    # 2. ระบบ Search เดิมของคุณ
    if message.channel.id in setup_channels:
        if not message.attachments: # ถ้าไม่ใช่รูปภาพ ค่อยทำการค้นหา
            try: await message.delete()
            except: pass
            await search_logic(message.content, message.channel)

    await bot.process_commands(message)

# ... (ส่วนที่เหลือของโค้ด setup, unset, getscript เหมือนเดิม) ...
