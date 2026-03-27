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

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=MemoryStorage())

class PostState(StatesGroup):
    selecting = State()
    selecting_button = State()
    typing_text = State()
    waiting_giveaway_links = State() # Ожидание списка ссылок

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_selection_kb(selected_names, is_giveaway=False):
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
        action = "🚀 ОПУБЛИКОВАТЬ РОЗЫГРЫШ" if is_giveaway else "🚀 ОПУБЛИКОВАТЬ"
        kb.append([InlineKeyboardButton(text=action, callback_data="confirm_select")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- РОЗЫГРЫШ (GIVEAWAY) С НЕСКОЛЬКИМИ КАНАЛАМИ ---

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith('/giveaway'))
async def start_giveaway(message: types.Message, state: FSMContext):
    prize = message.text[10:].strip() or "Секретный приз"
    await state.update_data(prize=prize, msg_type="giveaway", req_chats=[]) # req_chats - список (id, link, title)
    await message.reply("🔗 <b>Шаг 1:</b> Присылай ссылки на каналы для подписки <b>по одной</b>.\n\nКогда добавишь все нужные каналы, нажми кнопку ниже 👇", 
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ ВСЕ КАНАЛЫ ДОБАВЛЕНЫ", callback_data="finish_links")]]))
    await state.set_state(PostState.waiting_giveaway_links)

@dp.message(PostState.waiting_giveaway_links)
async def process_giveaway_links(message: types.Message, state: FSMContext):
    link = message.text.strip()
    username = link.split('/')[-1].replace('@', '')
    
    try:
        chat = await bot.get_chat(f"@{username}")
        data = await state.get_data()
        req_chats = data.get('req_chats', [])
        
        # Проверяем, нет ли уже этого канала в списке
        if any(c['id'] == chat.id for c in req_chats):
            return await message.answer("Этот канал уже в списке!")

        req_chats.append({'id': chat.id, 'link': link, 'title': chat.title})
        await state.update_data(req_chats=req_chats)
        
        added_list = "\n".join([f"— {c['title']}" for c in req_chats])
        await message.answer(f"✅ Добавлен: <b>{chat.title}</b>\n\n<b>Текущий список:</b>\n{added_list}\n\nПрисылай следующую ссылку или нажми кнопку выше.")
    except Exception:
        await message.reply("❌ Ошибка: Бот не нашел канал или не является там админом.")

@dp.callback_query(F.data == "finish_links", PostState.waiting_giveaway_links)
async def finish_links(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    req_chats = data.get('req_chats', [])
    
    if not req_chats:
        return await callback.answer("Добавь хотя бы один канал!", show_alert=True)

    # Формируем текст поста со списком ссылок
    links_text = "\n".join([f"🔹 <a href='{c['link']}'>{c['title']}</a>" for c in req_chats])
    giveaway_text = f"🎁 <b>РОЗЫГРЫШ!</b>\n\nПриз: <b>{data['prize']}</b>\n\nДля участия подпишись на каналы:\n{links_text}\n\nЗатем жми кнопку! 👇"
    
    await state.update_data(old_caption=giveaway_text, selected_channels=[])
    await callback.message.answer(f"✅ Текст сформирован!\n\n<b>Шаг 2:</b> Выбери, КУДА отправить розыгрыш:", 
                                 reply_markup=get_selection_kb([], is_giveaway=True))
    await state.set_state(PostState.selecting)
    await callback.answer()

# --- ПРОВЕРКА ПОДПИСКИ (ДЛЯ ВСЕХ КАНАЛОВ) ---

@dp.callback_query(F.data.startswith("join_all_"))
async def join_all_handler(callback: types.CallbackQuery):
    # Достаем ID каналов из callback_data (они разделены запятой)
    ids_str = callback.data.replace("join_all_", "")
    chat_ids = [int(i) for i in ids_str.split(",")]
    user_id = callback.from_user.id
    
    for cid in chat_ids:
        try:
            member = await bot.get_chat_member(cid, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return await callback.answer("❌ Ты подписан не на все каналы! Проверь список еще раз.", show_alert=True)
        except Exception:
            return await callback.answer("❌ Ошибка проверки подписки. Сообщи админу!", show_alert=True)
            
    await callback.answer("✅ Ура! Ты выполнил все условия и участвуешь! 🎉", show_alert=True)

# --- ФИНАЛЬНАЯ РАССЫЛКА ---

async def send_posts(message_obj, state: FSMContext):
    data = await state.get_data()
    selected_channels = data.get('selected_channels')
    
    if data.get('msg_type') == "giveaway":
        # Кодируем все ID каналов в одну строку для кнопки
        ids_list = [str(c['id']) for c in data['req_chats']]
        ids_string = ",".join(ids_list)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ УЧАСТВОВАТЬ", callback_data=f"join_all_{ids_string}")]
        ])
        for name in selected_channels:
            await bot.send_message(CHANNELS[name], data['old_caption'], reply_markup=kb)
    else:
        # Обычные посты
        btn_choice = data.get('selected_button')
        reply_markup = None
        if btn_choice == "RANDOM_HACH":
            t = random.choice(list(CHANNELS.keys())); reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 ХАЛЯВА ТУТ 👇", url=f"https://t.me/{t}")]])
        
        for name in selected_channels:
            cid = CHANNELS[name]
            if data['msg_type'] == "photo": await bot.send_photo(cid, data['file_id'], caption=data['old_caption'], reply_markup=reply_markup)
            elif data['msg_type'] == "video": await bot.send_video(cid, data['file_id'], caption=data['old_caption'], reply_markup=reply_markup)
            else: await bot.send_message(cid, data['old_caption'], reply_markup=reply_markup)

    await message_obj.answer("✅ Готово!")
    await state.clear()

# --- СТАНДАРТНЫЕ ФУНКЦИИ (h_media, h_post, h_toggle, h_all, h_confirm, h_btn, h_custom, cancel, main) ---
# (Они остаются такими же, как в предыдущей версии)

@dp.message(F.from_user.id == ADMIN_ID, (F.photo | F.video))
async def h_media(m: types.Message, s: FSMContext):
    fid = m.photo[-1].file_id if m.photo else m.video.file_id
    await s.update_data(file_id=fid, msg_type="photo" if m.photo else "video", old_caption=m.caption or "", selected_channels=[])
    await m.reply("Выбери каналы:", reply_markup=get_selection_kb([])); await s.set_state(PostState.selecting)

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith('/post'))
async def h_post(m: types.Message, s: FSMContext):
    await s.update_data(file_id=None, msg_type="text", old_caption=m.text[6:].strip(), selected_channels=[])
    await m.reply("Выбери каналы:", reply_markup=get_selection_kb([])); await s.set_state(PostState.selecting)

@dp.callback_query(F.data.startswith('toggle_'), PostState.selecting)
async def h_toggle(c: types.CallbackQuery, s: FSMContext):
    n = c.data.replace('toggle_', ''); d = await s.get_data(); sel = d.get('selected_channels', [])
    sel.remove(n) if n in sel else sel.append(n); await s.update_data(selected_channels=sel)
    await c.message.edit_reply_markup(reply_markup=get_selection_kb(sel, d.get('msg_type')=="giveaway")); await c.answer()

@dp.callback_query(F.data == "select_all", PostState.selecting)
async def h_all(c: types.CallbackQuery, s: FSMContext):
    d = await s.get_data(); await s.update_data(selected_channels=list(CHANNELS.keys()))
    await c.message.edit_reply_markup(reply_markup=get_selection_kb(list(CHANNELS.keys()), d.get('msg_type')=="giveaway")); await c.answer()

@dp.callback_query(F.data == "confirm_select", PostState.selecting)
async def h_confirm(c: types.CallbackQuery, s: FSMContext):
    d = await s.get_data()
    if d.get('msg_type') == "giveaway": await send_posts(c.message, s)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 ХАЛЯВА ТУТ 👇", callback_data="btn_RANDOM_HACH")],[InlineKeyboardButton(text="🚫 Нет", callback_data="btn_none")]])
        await c.message.answer("Кнопка?", reply_markup=kb); await s.set_state(PostState.selecting_button)
    await c.answer()

@dp.callback_query(F.data.startswith('btn_'), PostState.selecting_button)
async def h_btn(c: types.CallbackQuery, s: FSMContext):
    await s.update_data(selected_button=c.data.replace('btn_', '')); d = await s.get_data()
    if d['msg_type'] == "text": await send_posts(c.message, s)
    else: await c.message.answer("Текст ('.' - оставить):"); await s.set_state(PostState.typing_text); await c.answer()

@dp.message(PostState.typing_text)
async def h_custom(m: types.Message, s: FSMContext):
    if m.text != ".": await s.update_data(old_caption=m.text if m.text != "-" else "")
    await send_posts(m, s)

@dp.callback_query(F.data == "cancel")
async def cancel(c: types.CallbackQuery, state: FSMContext):
    await state.clear(); await c.message.edit_text("Отменено.")

async def main():
    Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
