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

# Список Юзернеймов твоих каналов для кнопки "Халява"
# Убедись, что они написаны верно!
CHANNEL_USERNAMES = [
    "skini_dlya_malchikov_roblox",
    "estetica_rbx",
    "R0B0L0XNOVOSTI",
    "roblox_secreti_adminov",
    "roblox_geimer",
    "roblox_tvoi_gid",
    "roblox_insaider",
    "roblox_gazeta",
    "rbx_mir",
    "R0BL0X_0FFICIAL"
]

# Статические кнопки
STATIC_BUTTONS = {
    "🛒 Купить в xizmshop": "https://t.me/xizmshop",
    "💬 Связаться с админом": "https://t.me/xizmik", # Замени на свой реальный юзернейм
    "🌟 Бесплатные звезды": "https://t.me/freegifloli"
}

# Исправленное создание бота
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=MemoryStorage())

class PostState(StatesGroup):
    selecting = State()
    selecting_button = State()
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
    if not pure_text: return
    await state.update_data(file_id=None, msg_type="text", old_caption=clean_ads(pure_text), selected_channels=[])
    await message.reply("📝 Текст принят! Куда отправляем?", reply_markup=get_selection_kb([]))
    await state.set_state(PostState.selecting)

@dp.callback_query(F.data == "confirm_select", PostState.selecting)
async def confirm_channels(callback: types.CallbackQuery, state: FSMContext):
    # Создаем меню выбора кнопок
    kb_list = []
    # Кнопка "Халява" первой
    kb_list.append([InlineKeyboardButton(text="🎁 ХАЛЯВА ТУТ ", callback_data="btn_RANDOM_HACH")])
    
    # Добавляем статические кнопки
    for b_name in STATIC_BUTTONS.keys():
        kb_list.append([InlineKeyboardButton(text=b_name, callback_data=f"btn_{b_name}")])
        
    kb_list.append([InlineKeyboardButton(text="🚫 Без кнопки", callback_data="btn_none")])
    
    await callback.message.answer("Какую кнопку добавить под пост?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))
    await state.set_state(PostState.selecting_button)
    await callback.answer()

@dp.callback_query(F.data.startswith('btn_'), PostState.selecting_button)
async def process_button(callback: types.CallbackQuery, state: FSMContext):
    btn_choice = callback.data.replace('btn_', '')
    await state.update_data(selected_button=btn_choice)
    
    data = await state.get_data()
    if data['msg_type'] == "text":
        await send_posts(callback.message, state)
    else:
        await callback.message.answer("Текст ('.' - оставить старый, '-' - без текста):")
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
    caption = data['old_caption']
    file_id, msg_type, selected_channels = data['file_id'], data['msg_type'], data['selected_channels']
    btn_choice = data['selected_button']

    # Создаем КНОПКУ-ССЫЛКУ под постом
    reply_markup = None
    if btn_choice == "RANDOM_HACH":
        # Уникальная логика для кнопки Халява
        target_username = random.choice(CHANNEL_USERNAMES)
        random_url = f"https://t.me/{target_username}"
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 ХАЛЯВА ТУТ", url=random_url)]])
    elif btn_choice != "none":
        # Логика для статических кнопок
        btn_url = STATIC_BUTTONS[btn_choice]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=btn_choice, url=btn_url)]])

    status = await message_obj.answer(f"⏳ Рассылаю...")
    for name in selected_channels:
        try:
            cid = CHANNELS[name]
            if msg_type == "photo": await bot.send_photo(cid, file_id, caption=caption, reply_markup=reply_markup)
            elif msg_type == "video": await bot.send_video(cid, file_id, caption=caption, reply_markup=reply_markup)
            else: await bot.send_message(cid, caption, reply_markup=reply_markup)
            await asyncio.sleep(0.4)
        except Exception as e:
            await message_obj.answer(f"❌ Ошибка в {name}: {e}")
    await status.edit_text("✅ Готово!")
    await state.clear()

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
