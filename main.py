import os
import re
import asyncio
import logging
import random
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- 1. ВЕБ-СЕРВЕР ---
app = Flask(__name__)
@app.route('/')
def index(): return "AUTOPUB ACTIVE"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 2. НАСТРОЙКИ ---
TOKEN = '8699304309:AAGkHhyeGQqzg3KQtzez_5B9a3RcQsTTC7g'
ADMIN_ID = 5215754222

CHANNELS = {
    "🌸 Эстетика": -1003716842510, "💼 Админы": -1003728156774,
    "⚡ Новости": -1003845949396, "😎 Скины": -1003771506128,
    "🎮 Геймер": -1003832618601, "🗺️ Гид": -1003513951242,
    "🔑 Инсайдер": -1003621146931, "🗞️ Газета": -1003797505789,
    "🌎 Мир": -1003760654806, "📱 Роблокс": -1003780188516
}

# Красивые фразы для подписей (добавляются случайно)
PROMO_PHRASES = [
    "\n\n✨ <b>Лучшие скины для парней тут:</b> @skini_dlya_malchikov_roblox",
    "\n\n🎀 <b>Эстетика девчачьих игр:</b> @estetica_rbx",
    "\n\n🔥 <b>Горячие новости ROBLOX:</b> @R0B0L0XNOVOSTI",
    "\n\n🕵️ <b>Секреты админов:</b> @roblox_secreti_adminov",
    "\n\n🎮 <b>Стань про-геймером:</b> @roblox_geimer",
    "\n\n🗺️ <b>Твой личный гид по играм:</b> @roblox_tvoi_gid",
    "\n\n🔑 <b>Инсайды, которых нет у других:</b> @roblox_insaider",
    "\n\n🗞️ <b>Свежий выпуск газеты:</b> @roblox_gazeta",
    "\n\n🌍 <b>Весь мир Роблокса здесь:</b> @rbx_mir",
    "\n\n📱 <b>Официальное сообщество:</b> @R0BL0X_0FFICIAL"
]

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

# Счётчик для статистики
stats_data = {"total_posts": 0}

class PostState(StatesGroup):
    selecting = State()
    waiting_time = State()
    typing_text = State()

def clean_ads(text):
    if not text: return ""
    return re.sub(r'@\w+|t\.me/\S+|http\S+', '', text).strip()

def get_selection_kb(selected_names):
    kb = []
    kb.append([InlineKeyboardButton(text="💎 ВЫБРАТЬ ВСЕ", callback_data="select_all")])
    channel_list = list(CHANNELS.keys())
    for i in range(0, len(channel_list), 2):
        row = []
        for name in channel_list[i:i+2]:
            prefix = "✅ " if name in selected_names else ""
            row.append(InlineKeyboardButton(text=f"{prefix}{name}", callback_data=f"toggle_{name}"))
        kb.append(row)
    if selected_names:
        kb.append([InlineKeyboardButton(text=f"🚀 ОПУБЛИКОВАТЬ ({len(selected_names)})", callback_data="confirm_select")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- ОБРАБОТЧИКИ ---

@dp.message(F.text == "/stats", F.from_user.id == ADMIN_ID)
async def show_stats(message: types.Message):
    await message.answer(f"📊 <b>Статистика бота:</b>\nВсего опубликовано постов: <code>{stats_data['total_posts']}</code>")

@dp.message(F.from_user.id == ADMIN_ID, (F.photo | F.video))
async def handle_media(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id
    msg_type = "photo" if message.photo else "video"
    old_caption = clean_ads(message.caption)
    await state.update_data(file_id=file_id, msg_type=msg_type, old_caption=old_caption, selected_channels=[])
    await message.reply(f"📥 {msg_type} получено! Выбери каналы:", reply_markup=get_selection_kb([]))
    await state.set_state(PostState.selecting)

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith('/post'))
async def handle_post_command(message: types.Message, state: FSMContext):
    pure_text = message.text[6:].strip()
    if not pure_text:
        await message.reply("❌ Напиши текст после /post")
        return
    await state.update_data(file_id=None, msg_type="text", old_caption=clean_ads(pure_text), selected_channels=[])
    await message.reply("📝 Текст принят! Выбери каналы:", reply_markup=get_selection_kb([]))
    await state.set_state(PostState.selecting)

@dp.callback_query(F.data.startswith('toggle_'), PostState.selecting)
async def toggle_channel(callback: types.CallbackQuery, state: FSMContext):
    name = callback.data.replace('toggle_', '')
    data = await state.get_data()
    selected = data.get('selected_channels', [])
    if name in selected: selected.remove(name)
    else: selected.append(name)
    await state.update_data(selected_channels=selected)
    await callback.message.edit_reply_markup(reply_markup=get_selection_kb(selected))
    await callback.answer()

@dp.callback_query(F.data == "select_all", PostState.selecting)
async def select_all(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(selected_channels=list(CHANNELS.keys()))
    await callback.message.edit_reply_markup(reply_markup=get_selection_kb(list(CHANNELS.keys())))
    await callback.answer()

@dp.callback_query(F.data == "confirm_select", PostState.selecting)
async def confirm(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Сейчас", callback_data="time_0")],
        [InlineKeyboardButton(text="⏰ Через 15 мин", callback_data="time_15")],
        [InlineKeyboardButton(text="⏰ Через 1 час", callback_data="time_60")]
    ])
    await callback.message.answer("Когда публикуем?", reply_markup=kb)
    await state.set_state(PostState.waiting_time)
    await callback.answer()

@dp.callback_query(F.data.startswith('time_'), PostState.waiting_time)
async def process_time(callback: types.CallbackQuery, state: FSMContext):
    minutes = int(callback.data.replace('time_', ''))
    await state.update_data(delay=minutes)
    
    data = await state.get_data()
    if data['msg_type'] == "text":
        await finalize_post(callback.message, state)
    else:
        await callback.message.answer("Нужно изменить описание?\nОтправь текст, '.' (оставить) или '-' (без текста).")
        await state.set_state(PostState.typing_text)
    await callback.answer()

@dp.message(PostState.typing_text)
async def process_custom_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    caption = data['old_caption'] if message.text == "." else ("" if message.text == "-" else message.text)
    await state.update_data(old_caption=caption)
    await finalize_post(message, state)

async def finalize_post(message_obj, state: FSMContext):
    data = await state.get_data()
    delay = data.get('delay', 0)
    
    if delay > 0:
        await message_obj.answer(f"🕒 Пост запланирован через {delay} мин.")
        await asyncio.sleep(delay * 60)
    
    await send_posts(message_obj, state)

async def send_posts(message_obj, state: FSMContext):
    data = await state.get_data()
    # Добавляем случайную подпись к тексту
    promo = random.choice(PROMO_PHRASES)
    caption = f"{data['old_caption']}{promo}"
    
    file_id, msg_type, selected_channels = data['file_id'], data['msg_type'], data['selected_channels']

    for name in selected_channels:
        try:
            cid = CHANNELS[name]
            if msg_type == "photo": await bot.send_photo(cid, file_id, caption=caption)
            elif msg_type == "video": await bot.send_video(cid, file_id, caption=caption)
            else: await bot.send_message(cid, caption)
            stats_data["total_posts"] += 1
            await asyncio.sleep(0.4)
        except Exception as e:
            await message_obj.answer(f"❌ Ошибка в {name}: {e}")
    
    await message_obj.answer("✅ Публикация завершена!")
    await state.clear()

@dp.callback_query(F.data == "cancel")
async def cancel(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("Отменено.")

async def main():
    Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
