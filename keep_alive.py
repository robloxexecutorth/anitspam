from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    # ข้อความอะไรก็ได้ให้ Render รู้ว่าเว็บทำงาน
    return "RETH Guard: Monitoring Active"

def run():
    # ดึง Port จาก Render (ปกติคือ 10000) ถ้าไม่มีให้ใช้ 8080
    port = int(os.environ.get("PORT", 10000)) 
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
