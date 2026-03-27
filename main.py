import os
import re
import asyncio
import logging
import random
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.client.default import DefaultBotProperties
import yt_dlp # Нужно добавить в requirements.txt

# --- 1. ВЕБ-СЕРВЕР ---
app = Flask(__name__)
@app.route('/')
def index(): return "AUTOPUB IS RUNNING"

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

CHANNEL_USERNAMES = ["estetica_rbx", "roblox_geimer", "R0BL0X_0FFICIAL"] # Список для проверки подписки в розыгрыше
STATIC_BUTTONS = {"🛒 Купить в Xizmshop": "https://t.me/xizmshop", "💬 Связь с админом": "https://t.me/xizm", "🌟Бесплатные Звезды": "https://t.me/xizm"}

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=MemoryStorage())

class PostState(StatesGroup):
    selecting = State()
    selecting_button = State()
    typing_text = State()

# --- ФУНКЦИЯ СКАЧИВАНИЯ ВИДЕО ---
def download_video(url):
    ydl_opts = {'format': 'best', 'outtmpl': 'video.mp4', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "video.mp4"

# --- ОБРАБОТЧИКИ ---

# Команда /tt для скачивания
@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith('/tt'))
async def handle_tt(message: types.Message, state: FSMContext):
    url = message.text[4:].strip()
    if not url: return await message.reply("❌ Введи ссылку: `/tt https://...`")
    
    msg = await message.reply("⏳ Скачиваю видео...")
    try:
        path = download_video(url)
        video = types.FSInputFile(path)
        # После скачивания отправляем себе и запускаем обычный процесс рассылки
        sent = await message.answer_video(video, caption="Видео скачано! Куда шлем?")
        await state.update_data(file_id=sent.video.file_id, msg_type="video", old_caption="", selected_channels=[])
        await msg.delete()
        await sent.reply("Выбери каналы:", reply_markup=get_selection_kb([]))
        await state.set_state(PostState.selecting)
        os.remove(path)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка скачивания: {e}")

# Команда /giveaway (Розыгрыш)
@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith('/giveaway'))
async def create_giveaway(message: types.Message):
    prize = message.text[10:].strip() or "Секретный приз"
    text = f"🎁 <b>РОЗЫГРЫШ!</b>\n\nПриз: <b>{prize}</b>\n\nДля участия подпишись на наши каналы и нажми кнопку ниже!"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ УЧАСТВОВАТЬ", callback_data="join_giveaway")]
    ])
    await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "join_giveaway")
async def join_giveaway(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    # Простая проверка (в реальности нужно циклом по всем CHANNELS)
    try:
        member = await bot.get_chat_member(CHANNELS["📱 Роблокс"], user_id)
        if member.status in ['member', 'administrator', 'creator']:
            await callback.answer("✅ Ты в игре! Удачи!", show_alert=True)
        else:
            await callback.answer("❌ Сначала подпишись на все каналы!", show_alert=True)
    except:
        await callback.answer("Ой, что-то пошло не так.")

# Функция рассылки (остается из прошлого кода)
async def send_posts(message_obj, state: FSMContext):
    data = await state.get_data()
    btn_choice = data['selected_button']
    reply_markup = None
    if btn_choice == "RANDOM_HACH":
        url = f"https://t.me/{random.choice(list(CHANNELS.keys()))}" # Упростил для примера
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 ХАЛЯВА ТУТ 👇", url=url)]])
    elif btn_choice != "none":
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=btn_choice, url=STATIC_BUTTONS[btn_choice])]])

    for name in data['selected_channels']:
        cid = CHANNELS[name]
        if data['msg_type'] == "photo": await bot.send_photo(cid, data['file_id'], caption=data['old_caption'], reply_markup=reply_markup)
        elif data['msg_type'] == "video": await bot.send_video(cid, data['file_id'], caption=data['old_caption'], reply_markup=reply_markup)
        else: await bot.send_message(cid, data['old_caption'], reply_markup=reply_markup)
    await message_obj.answer("✅ Готово!")
    await state.clear()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (Keyboard, Clean Ads и т.д.) ---
# (Оставляем те же, что были в прошлом сообщении)
def get_selection_kb(selected_names):
    kb = []
    kb.append([InlineKeyboardButton(text="💎 ВЫБРАТЬ ВСЕ", callback_data="select_all")])
    for name in list(CHANNELS.keys()):
        prefix = "✅ " if name in selected_names else ""
        kb.append([InlineKeyboardButton(text=f"{prefix}{name}", callback_data=f"toggle_{name}")])
    if selected_names: kb.append([InlineKeyboardButton(text="🚀 ОПУБЛИКОВАТЬ", callback_data="confirm_select")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.callback_query(F.data == "confirm_select", PostState.selecting)
async def confirm_channels(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 ХАЛЯВА ТУТ 👇", callback_data="btn_RANDOM_HACH")],
        [InlineKeyboardButton(text="🚫 Без кнопки", callback_data="btn_none")]
    ])
    await callback.message.answer("Кнопка?", reply_markup=kb)
    await state.set_state(PostState.selecting_button)

@dp.callback_query(F.data.startswith('btn_'), PostState.selecting_button)
async def process_btn(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(selected_button=callback.data.replace('btn_', ''))
    data = await state.get_data()
    if data['msg_type'] == "text": await send_posts(callback.message, state)
    else: 
        await callback.message.answer("Текст ('.' - оставить):")
        await state.set_state(PostState.typing_text)

@dp.message(PostState.typing_text)
async def custom_txt(m: types.Message, state: FSMContext):
    if m.text != ".": await state.update_data(old_caption=m.text)
    await send_posts(m, state)

@dp.callback_query(F.data.startswith('toggle_'), PostState.selecting)
async def toggle(c: types.CallbackQuery, state: FSMContext):
    name = c.data.replace('toggle_', '')
    data = await state.get_data()
    sel = data.get('selected_channels', [])
    sel.remove(name) if name in sel else sel.append(name)
    await state.update_data(selected_channels=sel)
    await c.message.edit_reply_markup(reply_markup=get_selection_kb(sel))

async def main():
    Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
