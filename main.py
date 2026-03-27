import os
import re
import asyncio
import logging
import random
import yt_dlp
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
def index(): return "AUTOPUB HYPED ACTIVE"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 2. НАСТРОЙКИ ---
TOKEN = '8699304309:AAGkHhyeGQqzg3KQtzez_5B9a3RcQsTTC7g'
ADMIN_ID = 5215754222

# Список твоих каналов для рандомайзера
CHANNELS_LINKS = [
    "estetica_rbx", "skini_dlya_malchikov_roblox", "R0B0L0XNOVOSTI",
    "roblox_secreti_adminov", "roblox_geimer", "roblox_tvoi_gid",
    "roblox_insaider", "roblox_gazeta", "rbx_mir", "R0BL0X_0FFICIAL"
]

CHANNELS = {
    "🌸 Эстетика": -1003716842510, "💼 Админы": -1003728156774,
    "⚡ Новости": -1003845949396, "😎 Скины": -1003771506128,
    "🎮 Геймер": -1003832618601, "🗺️ Гид": -1003513951242,
    "🔑 Инсайдер": -1003621146931, "🗞️ Газета": -1003797505789,
    "🌎 Мир": -1003760654806, "📱 Роблокс": -1003780188516
}

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

class PostState(StatesGroup):
    selecting = State()
    typing_text = State()

# --- ЛОГИКА КНОПОК ---

def get_post_kb():
    # Кнопка с халявой выбирает рандомный канал из списка
    random_link = f"https://t.me/{random.choice(CHANNELS_LINKS)}"
    kb = [
        [InlineKeyboardButton(text="🎲 Рандомный канал с халявой", url=random_link)],
        [
            InlineKeyboardButton(text="🌟 Бесплатные звезды", url="https://t.me/freegifloli"),
            InlineKeyboardButton(text="🛍️ xizmshop", url="https://t.me/xizmshop")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

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

# --- СКАЧИВАНИЕ ВИДЕО ---
async def download_video(url):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'video.mp4',
        'quiet': True,
        'no_warnings': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "video.mp4"

# --- ОБРАБОТЧИКИ ---

@dp.message(F.from_user.id == ADMIN_ID, F.text.contains("tiktok.com") | F.text.contains("youtube.com/shorts"))
async def handle_link(message: types.Message, state: FSMContext):
    wait_msg = await message.reply("⏳ Скачиваю контент без водяных знаков...")
    try:
        path = await download_video(message.text)
        video = types.FSInputFile(path)
        msg = await message.answer_video(video, caption="🎬 Видео готово! Куда рассылаем?")
        os.remove(path)
        await state.update_data(file_id=msg.video.file_id, msg_type="video", old_caption="", selected_channels=[])
        await state.set_state(PostState.selecting)
        await msg.edit_reply_markup(reply_markup=get_selection_kb([]))
        await wait_msg.delete()
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка скачивания: {e}")

@dp.message(F.from_user.id == ADMIN_ID, (F.photo | F.video))
async def handle_media(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id
    msg_type = "photo" if message.photo else "video"
    await state.update_data(file_id=file_id, msg_type=msg_type, old_caption=re.sub(r'@\w+|t\.me/\S+|http\S+', '', message.caption or "").strip(), selected_channels=[])
    await message.reply(f"📥 {msg_type.capitalize()} получено! Выбери каналы:", reply_markup=get_selection_kb([]))
    await state.set_state(PostState.selecting)

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith('/post'))
async def handle_post_command(message: types.Message, state: FSMContext):
    pure_text = message.text[6:].strip()
    await state.update_data(file_id=None, msg_type="text", old_caption=pure_text, selected_channels=[])
    await message.reply("📝 Текст принят! Куда шлем?", reply_markup=get_selection_kb([]))
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
    data = await state.get_data()
    if data['msg_type'] == "text": await send_posts(callback.message, state)
    else:
        await callback.message.answer("Изменить описание?\nОтправь текст, '.' (оставить) или '-' (без текста).")
        await state.set_state(PostState.typing_text)
    await callback.answer()

@dp.message(PostState.typing_text)
async def process_custom_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    caption = data['old_caption'] if message.text == "." else ("" if message.text == "-" else message.text)
    await state.update_data(old_caption=caption)
    await send_posts(message, state)

async def send_posts(message_obj, state: FSMContext):
    data = await state.get_data()
    caption, file_id, msg_type, selected_channels = data['old_caption'], data['file_id'], data['msg_type'], data['selected_channels']

    status = await message_obj.answer(f"🚀 Рассылка пошла...")
    for name in selected_channels:
        try:
            cid = CHANNELS[name]
            kb = get_post_kb() # Каждый пост получает свою рандомную кнопку "Халява"
            if msg_type == "photo": await bot.send_photo(cid, file_id, caption=caption, reply_markup=kb)
            elif msg_type == "video": await bot.send_video(cid, file_id, caption=caption, reply_markup=kb)
            else: await bot.send_message(cid, caption, reply_markup=kb)
            await asyncio.sleep(0.4)
        except Exception as e:
            await message_obj.answer(f"❌ Ошибка в {name}: {e}")
    await status.edit_text("✅ Готово! Все довольны халявой.")
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
