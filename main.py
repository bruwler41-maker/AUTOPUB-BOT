import os
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
from aiogram.enums import ParseMode

# --- ВЕБ-СЕРВЕР ---
app = Flask(__name__)
@app.route('/')
def index(): return "AUTOPUB IS READY"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- НАСТРОЙКИ ---
TOKEN = '8699304309:AAGkHhyeGQqzg3KQtzez_5B9a3RcQsTTC7g'
ADMIN_ID = 5215754222

CHANNELS = {
    "🌸 Эстетика": -1003716842510, "💼 Админы": -1003728156774,
    "⚡ Новости": -1003845949396, "😎 Скины": -1003771506128,
    "🎮 Геймер": -1003832618601, "🗺️ Гид": -1003513951242,
    "🔑 Инсайдер": -1003621146931, "🗞️ Газета": -1003797505789,
    "🌎 Мир": -1003760654806, "📱 Роблокс": -1003780188516
}

# Инициализация с учетом новых правил библиотеки
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

GIVEAWAY_USERS = {} # Хранение участников {msg_id: [user_ids]}

class PostState(StatesGroup):
    selecting = State()
    waiting_links = State()
    waiting_time = State()

# --- ФУНКЦИИ ---

def get_kb(selected, is_giveaway=False):
    kb = [[InlineKeyboardButton(text="💎 ВЫБРАТЬ ВСЕ", callback_data="all")]]
    names = list(CHANNELS.keys())
    for i in range(0, len(names), 2):
        row = [InlineKeyboardButton(text=f"{'✅ ' if n in selected else ''}{n}", callback_data=f"tg_{n}") for n in names[i:i+2]]
        kb.append(row)
    if selected:
        kb.append([InlineKeyboardButton(text="🚀 ЗАПУСТИТЬ", callback_data="confirm")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- КОМАНДЫ ---

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith('/giveaway'))
async def start_give(m: types.Message, s: FSMContext):
    prize = m.text[10:].strip() or "Приз"
    await s.update_data(prize=prize, msg_type="giveaway", req_chats=[])
    await m.answer(f"🎁 Розыгрыш: <b>{prize}</b>\n\nПрисылай ссылки на каналы для подписки по одной.\nКогда закончишь, нажми кнопку ниже 👇", 
                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ ГОТОВО", callback_data="links_done")]]))
    await s.set_state(PostState.waiting_links)

@dp.message(PostState.waiting_links)
async def add_link(m: types.Message, s: FSMContext):
    link = m.text.strip()
    u = link.split('/')[-1].replace('@', '')
    try:
        chat = await bot.get_chat(f"@{u}")
        data = await s.get_data()
        chats = data.get('req_chats', [])
        chats.append({'id': chat.id, 'title': chat.title, 'link': link})
        await s.update_data(req_chats=chats)
        await m.answer(f"✅ Добавлен: {chat.title}\nВсего каналов: {len(chats)}")
    except: await m.answer("Бот не нашел канал. Убедись, что он там админ!")

@dp.callback_query(F.data == "links_done", PostState.waiting_links)
async def set_time(c: types.CallbackQuery, s: FSMContext):
    await c.message.answer("Через сколько МИНУТ завершить розыгрыш?")
    await s.set_state(PostState.waiting_time)

@dp.message(PostState.waiting_time)
async def process_time(m: types.Message, s: FSMContext):
    if not m.text.isdigit(): return await m.reply("Введи число!")
    data = await s.get_data()
    links = "\n".join([f"🔹 <a href='{c['link']}'>{c['title']}</a>" for c in data['req_chats']])
    text = f"🎁 <b>РОЗЫГРЫШ!</b>\n\nПриз: <b>{data['prize']}</b>\n⏳ Итоги через: {m.text} мин.\n\nПодпишись:\n{links}\n\nЖми кнопку ниже! 👇"
    await s.update_data(caption=text, time=int(m.text), selected=[])
    await m.answer(f"Превью:\n\n{text}", reply_markup=get_kb([], True))
    await s.set_state(PostState.selecting)

# Кнопка проверки для участников
@dp.callback_query(F.data.startswith("join_"))
async def join_handler(c: types.CallbackQuery):
    ids = [int(i) for i in c.data.split("_")[1:]]
    for cid in ids:
        user = await bot.get_chat_member(cid, c.from_user.id)
        if user.status not in ['member', 'administrator', 'creator']:
            return await c.answer("❌ Ты не подписан на все каналы!", show_alert=True)
    
    mid = str(c.message.message_id)
    if mid not in GIVEAWAY_USERS: GIVEAWAY_USERS[mid] = []
    if c.from_user.id in GIVEAWAY_USERS[mid]: return await c.answer("Ты уже участвуешь!", show_alert=True)
    
    GIVEAWAY_USERS[mid].append(c.from_user.id)
    await c.answer("✅ Ты в списке участников!", show_alert=True)

# --- РАССЫЛКА ---

async def run_giveaway(m_obj, s: FSMContext):
    data = await s.get_data()
    ids_str = "_".join([str(c['id']) for c in data['req_chats']])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ УЧАСТВОВАТЬ", callback_data=f"join_{ids_str}")]])
    
    sent_msgs = []
    for name in data['selected']:
        msg = await bot.send_message(CHANNELS[name], data['caption'], reply_markup=kb)
        sent_msgs.append(msg)
    
    await m_obj.answer("🚀 Розыгрыш запущен!")
    await asyncio.sleep(data['time'] * 60)
    
    # Выбор победителя
    all_participants = []
    for m in sent_msgs:
        if str(m.message_id) in GIVEAWAY_USERS:
            all_participants.extend(GIVEAWAY_USERS[str(m.message_id)])
    
    all_participants = list(set(all_participants))
    if all_participants:
        winner_id = random.choice(all_participants)
        winner = await bot.get_chat(winner_id)
        res = f"🎊 <b>ИТОГИ РОЗЫГРЫША!</b>\n\nПобедитель: <a href='tg://user?id={winner_id}'>{winner.full_name}</a>\nПриз: {data['prize']}"
    else: res = "Победитель не выбран (нет участников)."
    
    for name in data['selected']: await bot.send_message(CHANNELS[name], res)
    await s.clear()

# --- СТАНДАРТНОЕ ---

@dp.callback_query(F.data.startswith('tg_'), PostState.selecting)
async def toggle(c: types.CallbackQuery, s: FSMContext):
    n = c.data.replace('tg_', ''); d = await s.get_data(); sel = d.get('selected', [])
    sel.remove(n) if n in sel else sel.append(n); await s.update_data(selected=sel)
    await c.message.edit_reply_markup(reply_markup=get_kb(sel, d.get('msg_type')=="giveaway"))

@dp.callback_query(F.data == "confirm", PostState.selecting)
async def confirm(c: types.CallbackQuery, s: FSMContext):
    await run_giveaway(c.message, s); await c.answer()

@dp.callback_query(F.data == "cancel")
async def cancel(c: types.CallbackQuery, s: FSMContext):
    await s.clear(); await c.message.edit_text("Отменено.")

async def main():
    Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
