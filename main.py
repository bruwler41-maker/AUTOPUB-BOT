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
ADMIN_ID = 5215754222

CHANNELS = {
    "🌸 Эстетика": -1003716842510,
    "💼 Админы": -1003728156774,
    "⚡ Новости": -1003845949396,
    "😎 Скины": -1003771506128,
    "🎮 Геймер": -1003832618601,
    "🗺️ Гид": -1003513951242,
    "🔑 Инсайдер": -1003621146931,
    "🗞️ Газета": -1003797505789,
    "🌎 Мир": -1003760654806,
    "📱 Роблокс": -1003780188516
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class PostState(StatesGroup):
    selecting = State()
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

# Универсальный хендлер для Фото, Видео и Текста
@dp.message(F.from_user.id == ADMIN_ID, (F.photo | F.video | F.text))
async def handle_message(message: types.Message, state: FSMContext):
    # Если это просто текст, который не является частью процесса создания поста
    current_state = await state.get_state()
    if current_state is not None: return

    file_id = None
    msg_type = "text"
    old_caption = ""

    if message.photo:
        file_id = message.photo[-1].file_id
        msg_type = "photo"
        old_caption = clean_ads(message.caption)
    elif message.video:
        file_id = message.video.file_id
        msg_type = "video"
        old_caption = clean_ads(message.caption)
    else:
        old_caption = clean_ads(message.text)

    await state.update_data(file_id=file_id, msg_type=msg_type, old_caption=old_caption, selected_channels=[])
    await message.reply(f"📥 {msg_type.capitalize()} получено! Выбери каналы:", reply_markup=get_selection_kb([]))
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
    await callback.message.answer("Напиши текст ('.' - старый/текст из сообщения, '-' - без текста):")
    await state.set_state(PostState.typing_text)
    await callback.answer()

@dp.message(PostState.typing_text)
async def process_final(message: types.Message, state: FSMContext):
    data = await state.get_data()
    caption = data['old_caption'] if message.text == "." else ("" if message.text == "-" else message.text)
    file_id = data['file_id']
    msg_type = data['msg_type']
    selected_names = data['selected_channels']

    msg = await message.answer(f"⏳ Рассылаю в {len(selected_names)} кан...")
    for name in selected_names:
        try:
            cid = CHANNELS[name]
            if msg_type == "photo":
                await bot.send_photo(chat_id=cid, photo=file_id, caption=caption)
            elif msg_type == "video":
                await bot.send_video(chat_id=cid, video=file_id, caption=caption)
            else:
                await bot.send_message(chat_id=cid, text=caption)
            await asyncio.sleep(0.4)
        except Exception as e:
            await message.answer(f"❌ Ошибка в {name}: {e}")
    
    await msg.edit_text("✅ Готово! Всё опубликовано.")
    await state.clear()

@dp.callback_query(F.data == "cancel")
async def cancel(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("Отменено.")

async def main_logic():
    Thread(target=run).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main_logic())
