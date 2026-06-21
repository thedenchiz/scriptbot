import asyncio
import random
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, ADMIN_ID, SCRIPT_NAME
from database import *
from gemini import generate_greeting, generate_random_word

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

logging.basicConfig(level=logging.INFO)

# FSM для админа
class AdminStates(StatesGroup):
    waiting_for_channel_add = State()
    waiting_for_channel_remove = State()

# --- КЛАВИАТУРЫ ---
def get_channels_keyboard(channels):
    kb = []
    for ch in channels:
        kb.append([InlineKeyboardButton(text=f"📢 {ch}", url=f"{ch}")])
    kb.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить канал", callback_data="admin_add")],
        [InlineKeyboardButton(text="➖ Удалить канал", callback_data="admin_remove")],
        [InlineKeyboardButton(text="📋 Список каналов", callback_data="admin_list")]
    ])

# --- ХЭНДЛЕРЫ ПОЛЬЗОВАТЕЛЕЙ ---
@router.message(CommandStart())
async def cmd_start(message: Message):
    await add_user(message.from_user.id)
    channels = await get_all_channels()
    
    greeting = await generate_greeting()
    
    if not channels:
        await message.answer("Привет! Сейчас нет обязательных каналов для подписки. Ты можешь свободно пользоваться ботом.")
        # Здесь можно выдать доступ, но по ТЗ нужен ключ
        return

    kb = get_channels_keyboard(channels)
    await message.answer(greeting, reply_markup=kb)

@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    channels = await get_all_channels()
    
    not_subscribed = []
    for channel in channels:
        try:
            # Извлекаем @username из ссылки (поддержка t.me/ и @)
            ch_id = channel.replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "")
            member = await bot.get_chat_member(chat_id=f"@{ch_id}", user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                not_subscribed.append(channel)
        except Exception as e:
            # Если бот не админ в канале или канал не найден
            logging.error(f"Ошибка проверки {channel}: {e}")
            not_subscribed.append(channel)

    if not_subscribed:
        await callback.answer("Вы не подписались на все каналы!", show_alert=True)
    else:
        status = await get_user_status(user_id)
        if status == "approved":
            # Если уже есть ключ, пытаемся его достать (заглушка, лучше хранить в кэше, но для простоты обновим)
            db = await load_db()
            key = db["users"].get(str(user_id), {}).get("key")
            await callback.message.edit_text(f"✅ Вы уже подписаны!\nВаш ключ:\n\n<code>{key}</code>")
        else:
            # Генерация ключа
            random_word = await generate_random_word()
            random_num = random.randint(10000, 99999)
            key = f"[{SCRIPT_NAME}]<{user_id}>{random_word}{random_num}"
            
            await update_user_key(user_id, key)
            await callback.message.edit_text(
                f"🎉 Спасибо за подписку!\nВаш уникальный ключ доступа:\n\n<code>{key}</code>\n\n"
                "Сохраните его, он потребуется для скрипта."
            )

# --- ХЭНДЛЕРЫ АДМИНА ---
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("⚙️ Админ-панель управления каналами:", reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "admin_add", F.from_user.id == ADMIN_ID)
async def admin_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправьте ссылку на канал (в формате @username или https://t.me/username):")
    await state.set_state(AdminStates.waiting_for_channel_add)
    await callback.answer()

@router.message(AdminStates.waiting_for_channel_add, F.from_user.id == ADMIN_ID)
async def admin_add_process(message: Message, state: FSMContext):
    channel = message.text.strip()
    await add_channel(channel)
    await message.answer(f"✅ Канал {channel} добавлен.", reply_markup=get_admin_keyboard())
    await state.clear()

@router.callback_query(F.data == "admin_remove", F.from_user.id == ADMIN_ID)
async def admin_remove_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправьте ссылку или @username канала, который нужно удалить:")
    await state.set_state(AdminStates.waiting_for_channel_remove)
    await callback.answer()

@router.message(AdminStates.waiting_for_channel_remove, F.from_user.id == ADMIN_ID)
async def admin_remove_process(message: Message, state: FSMContext):
    channel = message.text.strip()
    await remove_channel(channel)
    await message.answer(f"🗑 Канал {channel} удален.", reply_markup=get_admin_keyboard())
    await state.clear()

@router.callback_query(F.data == "admin_list", F.from_user.id == ADMIN_ID)
async def admin_list(callback: CallbackQuery):
    channels = await get_all_channels()
    text = "📋 Список каналов:\n\n" + "\n".join(channels) if channels else "Список каналов пуст."
    await callback.message.answer(text)
    await callback.answer()

# --- ФОНОВАЯ ПРОВЕРКА ПОДПИСКИ ---
async def background_sub_checker():
    while True:
        await asyncio.sleep(60)  # Проверяем каждую минуту
        logging.info("Фоновая проверка подписок...")
        channels = await get_all_channels()
        if not channels:
            continue
            
        pending_users = await get_pending_users()
        for user_id in pending_users:
            not_subscribed = []
            for channel in channels:
                try:
                    ch_id = channel.replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "")
                    member = await bot.get_chat_member(chat_id=f"@{ch_id}", user_id=user_id)
                    if member.status not in ["member", "administrator", "creator"]:
                        not_subscribed.append(channel)
                except Exception:
                    not_subscribed.append(channel)
            
            if not not_subscribed:
                # Пользователь подписался, но не нажал кнопку
                random_word = await generate_random_word()
                random_num = random.randint(10000, 99999)
                key = f"[{SCRIPT_NAME}]<{user_id}>{random_word}{random_num}"
                await update_user_key(user_id, key)
                
                try:
                    await bot.send_message(
                        user_id,
                        f"🎉 Мы заметили, что вы подписались на все каналы!\n"
                        f"Ваш уникальный ключ доступа:\n\n<code>{key}</code>"
                    )
                except Exception as e:
                    logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

# --- ЗАПУСК БОТА ---
async def main():
    await init_db()
    # Запускаем фоновую задачу
    asyncio.create_task(background_sub_checker())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())