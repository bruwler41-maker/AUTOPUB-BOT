import os
import asyncio
import logging
import random
import re
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.client.default import DefaultBotProperties
import yt_dlp

# --- 1. ВЕБ-СЕРВЕР (Для Render) ---
app = Flask(__name__)
@app.route('/')
def index(): return "BOT IS ACTIVE"

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

# Хранилище участников розыгрышей {сообщение_id: [список_user_id]}
GIVEAWAY_DATA = {}

class PostState(StatesGroup):
    selecting = State()
    selecting_button = State()
    typing_text = State()
    waiting_giveaway_links = State()
    waiting_cond_val = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_selection_kb(selected_names, is_giveaway=False):
    kb = [[InlineKeyboardButton(text="💎 ВЫБРАТЬ ВСЕ", callback_data="all")]]
    ch_list = list(CHANNELS.keys())
    for i in range(0, len(ch_list), 2):
        row = []
        for n in ch_list[i:i+2]:
            p = "✅ " if n in selected_names else ""
            row.append(InlineKeyboardButton(text=f"{p}{n}", callback_data=f"tg_{n}"))
        kb.append(row)
    if selected_names:
        txt = "🚀 ЗАПУСТИТЬ РОЗЫГРЫШ" if is_giveaway else "🚀 ОПУБЛИКОВАТЬ"
        kb.append([InlineKeyboardButton(text=txt, callback_data="confirm")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- ОБРАБОТЧИКИ ---

# Скачивание видео /tt
@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith('/tt'))
async def tt_download(m: types.Message, s: FSMContext):
    url = m.text[4:].strip()
    if not url: return await m.reply("Введите ссылку!")
    wait = await m.answer("⏳ Скачиваю...")
    try:
        opts = {'format': 'best', 'outtmpl': 'v.mp4', 'quiet': True}
        with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])
        video = types.FSInputFile('v.mp4')
        sent = await m.answer_video(video, caption="Готово! Куда шлем?")
        await s.update_data(file_id=sent.video.file_id, msg_type="video", old_caption="", selected_channels=[])
        await s.set_state(PostState.selecting)
        await sent.reply("Выбери каналы:", reply_markup=get_selection_kb([]))
        os.remove('v.mp4')
    except Exception as e: await wait.edit_text(f"Ошибка: {e}")

# Розыгрыш /giveaway
@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith('/giveaway'))
async def start_give(m: types.Message, s: FSMContext):
    prize = m.text[10:].strip() or "Приз"
    await s.update_data(prize=prize, msg_type="giveaway", req_chats=[])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ ГОТОВО (ССЫЛКИ)", callback_data="done_links")]])
    await m.answer(f"🎁 Розыгрыш: <b>{prize}</b>\nПрисылай ссылки на каналы по одной.\nКогда закончишь — жми кнопку.", reply_markup=kb)
    await s.set_state(PostState.waiting_giveaway_links)

@dp.message(PostState.waiting_giveaway_links)
async def add_link(m: types.Message, s: FSMContext):
    u = m.text.split('/')[-1].replace('@', '')
    try:
        chat = await bot.get_chat(f"@{u}")
        d = await s.get_data(); r = d.get('req_chats', [])
        r.append({'id': chat.id, 'link': m.text.strip(), 'title': chat.title})
        await s.update_data(req_chats=r)
        await m.answer(f"✅ Добавлен: {chat.title}\nВсего: {len(r)}")
    except: await m.answer("Канал не найден или бот не админ!")

@dp.callback_query(F.data == "done_links", PostState.waiting_giveaway_links)
async def links_done(c: types.CallbackQuery, s: FSMContext):
    await c.message.answer("Через сколько МИНУТ завершить?")
    await s.set_state(PostState.waiting_cond_val)

@dp.message(PostState.waiting_cond_val)
async def set_time(m: types.Message, s: FSMContext):
    if not m.text.isdigit(): return await m.reply("Числом!")
    d = await s.get_data(); l_txt = "\n".join([f"🔹 <a href='{x['link']}'>{x['title']}</a>" for x in d['req_chats']])
    cap = f"🎁 <b>РОЗЫГРЫШ!</b>\n\nПриз: <b>{d['prize']}</b>\n⏳ Итоги через: {m.text} мин.\n\nПодпишись:\n{l_txt}\n\nЖми кнопку! 👇"
    await s.update_data(old_caption=cap, timer=int(m.text), selected_channels=[])
    await m.answer(f"Превью:\n{cap}", reply_markup=get_selection_kb([], True))
    await s.set_state(PostState.selecting)

# Кнопка участия
@dp.callback_query(F.data.startswith("join_"))
async def join_give(c: types.CallbackQuery):
    ids = [int(i) for i in c.data.split("_")[1:]]
    uid = c.from_user.id
    for cid in ids:
        m = await bot.get_chat_member(cid, uid)
        if m.status not in ['member', 'administrator', 'creator']:
            return await c.answer("❌ Подпишись на ВСЕ каналы!", show_alert=True)
    
    mid = str(c.message.message_id)
    if mid not in GIVEAWAY_DATA: GIVEAWAY_DATA[mid] = []
    if uid in GIVEAWAY_DATA[mid]: return await c.answer("Ты уже в игре!", show_alert=True)
    
    GIVEAWAY_DATA[mid].append(uid)
    await c.answer("✅ Ты участвуешь!", show_alert=True)

# Рассылка
async def final_send(m_obj, s: FSMContext):
    d = await s.get_data(); sel = d['selected_channels']; cap = d['old_caption']
    sent_messages = []

    if d.get('msg_type') == "giveaway":
        ids_str = "_".join([str(x['id']) for x in d['req_chats']])
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ УЧАСТВОВАТЬ", callback_data=f"join_{ids_str}")]])
        for name in sel:
            msg = await bot.send_message(CHANNELS[name], cap, reply_markup=kb)
            sent_messages.append(msg)
        
        await m_obj.answer(f"🚀 Розыгрыш запущен! Итоги через {d['timer']} мин.")
        await asyncio.sleep(d['timer'] * 60)
        
        # Выбор победителя
        all_users = []
        for sm in sent_messages:
            mid = str(sm.message_id)
            if mid in GIVEAWAY_DATA: all_users.extend(GIVEAWAY_DATA[mid])
        
        all_users = list(set(all_users))
        if all_users:
            win_id = random.choice(all_users)
            win_user = await bot.get_chat(win_id)
            win_text = f"🎊 <b>ИТОГИ РОЗЫГРЫША!</b>\nПриз: {d['prize']}\n\nПобедитель: <a href='tg://user?id={win_id}'>{win_user.full_name}</a>"
        else: win_text = "😢 Победитель не выбран (нет участников)."
        
        for name in sel: await bot.send_message(CHANNELS[name], win_text)
    else:
        # Обычный пост
        markup = None
        if d.get('btn') == "RANDOM":
            t = random.choice(list(CHANNELS.keys()))
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 ХАЛЯВА ТУТ 👇", url=f"https://t.me/{t}")]])
        
        for name in sel:
            cid = CHANNELS[name]
            if d['msg_type'] == "photo": await bot.send_photo(cid, d['file_id'], caption=cap, reply_markup=markup)
            elif d['msg_type'] == "video": await bot.send_video(cid, d['file_id'], caption=cap, reply_markup=markup)
            else: await bot.send_message(cid, cap, reply_markup=markup)
    
    await m_obj.answer("✅ Готово!")
    await s.clear()

# --- СТАНДАРТНЫЕ ХЕНДЛЕРЫ ---
@dp.message(F.from_user.id == ADMIN_ID, (F.photo | F.video))
async def h_media(m, s):
    await s.update_data(file_id=m.photo[-1].file_id if m.photo else m.video.file_id, msg_type="photo" if m.photo else "video", old_caption=m.caption or "", selected_channels=[])
    await m.reply("Каналы:", reply_markup=get_selection_kb([])); await s.set_state(PostState.selecting)

@dp.callback_query(F.data.startswith('tg_'), PostState.selecting)
async def h_tg(c, s):
    n = c.data.replace('tg_', ''); d = await s.get_data(); sel = d.get('selected_channels', [])
    sel.remove(n) if n in sel else sel.append(n); await s.update_data(selected_channels=sel)
    await c.message.edit_reply_markup(reply_markup=get_selection_kb(sel, d.get('msg_type')=="giveaway"))

@dp.callback_query(F.data == "all", PostState.selecting)
async def h_all(c, s):
    d = await s.get_data(); await s.update_data(selected_channels=list(CHANNELS.keys()))
    await c.message.edit_reply_markup(reply_markup=get_selection_kb(list(CHANNELS.keys()), d.get('msg_type')=="giveaway"))

@dp.callback_query(F.data == "confirm", PostState.selecting)
async def h_conf(c, s):
    d = await s.get_data()
    if d.get('msg_type') == "giveaway": await final_send(c.message, s)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 ХАЛЯВА", callback_data="b_RANDOM")],[InlineKeyboardButton(text="🚫 Нет", callback_data="b_none")]])
        await c.message.answer("Кнопка?", reply_markup=kb); await s.set_state(PostState.selecting_button)

@dp.callback_query(F.data.startswith('b_'), PostState.selecting_button)
async def h_b(c, s):
    await s.update_data(btn=c.data.replace('b_', '')); d = await s.get_data()
    if d['msg_type'] == "text": await final_send(c.message, s)
    else: await c.message.answer("Текст ('.' - оставить):"); await s.set_state(PostState.typing_text)

@dp.message(PostState.typing_text)
async def h_txt(m, s):
    if m.text != ".": await s.update_data(old_caption=m.text if m.text != "-" else "")
    await final_send(m, s)

@dp.callback_query(F.data == "cancel")
async def h_cancel(c, s): await s.clear(); await c.message.edit_text("Отмена.")

async def main():
    Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
