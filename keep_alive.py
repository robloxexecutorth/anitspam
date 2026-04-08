from flask import Flask
from threading import Thread
import os # เพิ่มอันนี้เข้ามา

app = Flask('')

@app.route('/')
def home():
    return "RETH Guard is awake and monitoring!"

def run():
    # เปลี่ยนจาก 8080 เป็นการดึงค่าจาก Environment Variable ของ Render
    port = int(os.environ.get("PORT", 8080)) 
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
