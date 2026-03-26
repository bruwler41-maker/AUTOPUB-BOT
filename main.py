import os
import re
import logging
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

# --- 1. МИНИ-СЕРВЕР ДЛЯ RENDER (АНТИ-СОН) ---
app = Flask('')

@app.route('/')
def home():
    return "AUTOPUB BOT IS ALIVE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. НАСТРОЙКИ БОТА ---
API_TOKEN = '8699304309:AAGkHhyeGQqzg3KQtzez_5B9a3RcQsTTC7g'
ADMIN_ID = 5215754222   # Твой ID (узнай у @userinfobot)

# Впиши свои ID каналов (узнай их у @userinfobot)
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

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class PostState(StatesGroup):
    choosing_channel = State()
    typing_text = State()

# Очистка текста от чужих ссылок
def clean_ads(text):
    if not text: return ""
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r't\.me/\S+', '', text)
    text = re.sub(r'http\S+', '', text)
    return text.strip()

# Прием видео
@dp.message_handler(content_types=['video'])
async def handle_video(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    clean_text = clean_ads(message.caption)
    await state.update_data(video_id=message.video.file_id, old_caption=clean_text)

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for name in CHANNELS.keys():
        keyboard.add(types.InlineKeyboardButton(name, callback_data=f"chan_{name}"))
    keyboard.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))

    await message.reply("🎥 Видео получено! Выбери канал:", reply_markup=keyboard)
    await PostState.choosing_channel.set()

# Выбор канала
@dp.callback_query_handler(lambda c: c.data.startswith('chan_'), state=PostState.choosing_channel)
async def process_channel(callback_query: types.CallbackQuery, state: FSMContext):
    channel_name = callback_query.data.replace('chan_', '')
    await state.update_data(target_channel=CHANNELS[channel_name])
    
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, f"Выбран: {channel_name}\nНапиши текст ('.' - старый, '-' - без текста):")
    await PostState.typing_text.set()

# Отправка
@dp.message_handler(state=PostState.typing_text)
async def process_final(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    if message.text == ".":
        caption = data.get('old_caption', "")
    elif message.text == "-":
        caption = ""
    else:
        caption = message.text

    try:
        await bot.send_video(chat_id=data['target_channel'], video=data['video_id'], caption=caption)
        await message.answer("✅ Опубликовано!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.finish()

@dp.callback_query_handler(text="cancel", state="*")
async def cancel(c: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.send_message(c.from_user.id, "Отменено")

if __name__ == '__main__':
    keep_alive() # Запуск мини-сервера
    print("Бот запускается...")
    executor.start_polling(dp, skip_updates=True)
