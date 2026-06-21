import json
import os
import asyncio
from config import DB_FILE

# Простая блокировка для асинхронной записи, чтобы не было гонок
db_lock = asyncio.Lock()

async def init_db():
    if not os.path.exists(DB_FILE) or os.stat(DB_FILE).st_size == 0:
        data = {
            "channels": [],
            "users": {}
        }
        await save_db(data)

async def load_db():
    async with db_lock:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

async def save_db(data):
    async with db_lock:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

async def add_channel(channel_link: str):
    db = await load_db()
    if channel_link not in db["channels"]:
        db["channels"].append(channel_link)
        await save_db(db)

async def remove_channel(channel_link: str):
    db = await load_db()
    if channel_link in db["channels"]:
        db["channels"].remove(channel_link)
        await save_db(db)

async def add_user(user_id: int):
    db = await load_db()
    if str(user_id) not in db["users"]:
        db["users"][str(user_id)] = {"status": "pending", "key": None}
        await save_db(db)

async def update_user_key(user_id: int, key: str):
    db = await load_db()
    db["users"][str(user_id)]["status"] = "approved"
    db["users"][str(user_id)]["key"] = key
    await save_db(db)

async def get_pending_users():
    db = await load_db()
    return [int(uid) for uid, data in db["users"].items() if data["status"] == "pending"]

async def get_user_status(user_id: int):
    db = await load_db()
    return db["users"].get(str(user_id), {}).get("status")

async def get_all_channels():
    db = await load_db()
    return db["channels"]