import os
import re
import asyncio
import logging
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- 1. МИНИ-СЕРВЕР ДЛЯ RENDER ---
app = Flask('')
@app.route('/')
def home(): return "AUTOPUB ALIVE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 2. НАСТРОЙКИ ---
TOKEN = '8699304309:AAGkHhyeGQqzg3KQtzez_5B9a3RcQsTTC7g'
ADMIN_ID = 5215754222  # Твой ID

CHANNELS = {
  "🌸 Эстетика": -1003716842510,
    "💼 Админы": -1003728156774,
    "⚡ Новости": -1003845949396,
    "😎 Скины": -1003771506128,
    "🎮 Геймер": -1003832618601,
    "🗺 ️Гид": -1003513951242,
    "🔑 Инсайдер": -1003621146931,
    "🗞 ️Газета"  :-1003797505789,
    "🌎 Мир" : -1003760654806,
    "📱 Роблокс" : -1003780188516
    
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class PostState(StatesGroup):
    choosing_channel = State()
    typing_text = State()

def clean_ads(text):
    if not text: return ""
    return re.sub(r'@\w+|t\.me/\S+|http\S+', '', text).strip()

@dp.message(F.video)
async def handle_video(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    clean_text = clean_ads(message.caption)
    await state.update_data(video_id=message.video.file_id, old_caption=clean_text)
    
    kb = []
    for name in CHANNELS.keys():
        kb.append([InlineKeyboardButton(text=name, callback_data=f"chan_{name}")])
    
    await message.reply("🎥 Выбери канал:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(PostState.choosing_channel)

@dp.callback_query(F.data.startswith('chan_'))
async def process_channel(callback: types.CallbackQuery, state: FSMContext):
    channel_name = callback.data.replace('chan_', '')
    await state.update_data(target_channel=CHANNELS[channel_name])
    await callback.message.answer(f"Выбран: {channel_name}\nНапиши текст ('.' - старый, '-' - без текста):")
    await state.set_state(PostState.typing_text)
    await callback.answer()

@dp.message(PostState.typing_text)
async def process_final(message: types.Message, state: FSMContext):
    data = await state.get_data()
    caption = data['old_caption'] if message.text == "." else ("" if message.text == "-" else message.text)
    try:
        await bot.send_video(chat_id=data['target_channel'], video=data['video_id'], caption=caption)
        await message.answer("✅ Готово!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

async def main_logic():
    Thread(target=run).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main_logic())
