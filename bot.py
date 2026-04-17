

import asyncio
import json
import os
import datetime
import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# ================= SOZLAMALAR =================
BOT_TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_ID = os.getenv("ADMIN_ID")
DATABASE_URL = os.getenv("DATABASE_URL") 
WEB_APP_URL = "https://servisbot.vercel.app" # O'zingiznikiga almashtiring!

KARTA_RAQAM = "5614 6822 1669 5272"
TON_HAMYON = "UQAAEnSurEdRWqgtIpzQTdgHIbF22yGCqaFD31g1Q-pUOevk"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db_pool = None

class TopUpState(StatesGroup):
    waiting_for_receipt = State()

# ================= BAZA LOGIKASI =================
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with db_pool.acquire() as conn:
        # Foydalanuvchilar jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance BIGINT DEFAULT 0,
                total_spent BIGINT DEFAULT 0
            )
        ''')
        # Tranzaksiyalar tarixi jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                type VARCHAR(50), 
                name VARCHAR(255),
                amount BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

async def ensure_user(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute('INSERT INTO users (user_id, balance) VALUES ($1, 0) ON CONFLICT DO NOTHING', user_id)

async def add_transaction(user_id, t_type, name, amount):
    async with db_pool.acquire() as conn:
        await conn.execute('INSERT INTO transactions (user_id, type, name, amount) VALUES ($1, $2, $3, $4)', user_id, t_type, name, amount)

# ================= TELEGRAM HANDLERLAR =================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await ensure_user(message.from_user.id)
    btn = KeyboardButton(text="📱 SERVIS 2.0 ni ochish", web_app=WebAppInfo(url=WEB_APP_URL))
    keyboard = ReplyKeyboardMarkup(keyboard=[[btn]], resize_keyboard=True)
    await message.answer("👋 <b>797 | SERVIS 2.0</b> ga xush kelibsiz!\n\nXizmatlardan foydalanish uchun tugmani bosing.", reply_markup=keyboard, parse_mode="HTML")

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        item_name = data.get("name")
        price = int(data.get("price", 0))

        if action == "topup":
            # Hisob to'ldirish jarayoni
            text = (f"💳 <b>Hisob to'ldirish: {price} UZS</b>\n\n"
                    f"👇 Quyidagi hisobga o'tkazma qiling:\n<code>{KARTA_RAQAM}</code>\n\n"
                    f"<i>To'lovni amalga oshirgach, chekni (skrinshot) yuboring.</i>")
            await message.answer(text, parse_mode="HTML")
            await state.update_data(amount=price)
            await state.set_state(TopUpState.waiting_for_receipt)

        elif action == "buy":
            # Xarid qilish jarayoni
            async with db_pool.acquire() as conn:
                balance = await conn.fetchval('SELECT balance FROM users WHERE user_id = $1', user_id)
                if balance >= price:
                    # Pulni yechish va sarflanganiga qo'shish
                    await conn.execute('UPDATE users SET balance = balance - $1, total_spent = total_spent + $1 WHERE user_id = $2', price, user_id)
                    await add_transaction(user_id, 'purchase', item_name, price)
                    
                    # Mijozga xabar
                    await message.answer(f"✅ <b>Xarid muvaffaqiyatli!</b>\n\nSotib olindi: <b>{item_name}</b>\nBalansdan yechildi: <b>{price} UZS</b>\n\n<i>Buyurtma adminga yuborildi, tez orada bajariladi.</i>", parse_mode="HTML")
                    
                    # Adminga xabar
                    if ADMIN_ID:
                        await bot.send_message(int(ADMIN_ID), f"🛍 <b>YANGI BUYURTMA</b>\n\nMijoz: {message.from_user.mention_html()} (<code>{user_id}</code>)\nMahsulot: <b>{item_name}</b>\nNarx: {price} UZS\n\n✅ <i>Pul tizim orqali yechib olindi. Buyurtmani bajaring.</i>", parse_mode="HTML")
                else:
                    await message.answer("❌ <b>Xatolik:</b> Balansingizda yetarli mablag' yo'q.")

    except Exception as e:
        print("XATO:", e)
        await message.answer("Tizim xatosi yuz berdi.")

@dp.message(TopUpState.waiting_for_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    amount = user_data.get("amount", 0)
    user_id = message.from_user.id

    if ADMIN_ID:
        admin_text = f"💰 <b>PUL TUSHDI (TEKSHIRING)</b>\n👤 {message.from_user.mention_html()}\n🆔 <code>{user_id}</code>\n💵 Summa: <b>{amount} UZS</b>"
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"appr_{user_id}_{amount}"),
            InlineKeyboardButton(text="❌ Bekor", callback_data=f"rej_{user_id}")
        ]])
        await bot.send_photo(int(ADMIN_ID), message.photo[-1].file_id, caption=admin_text, reply_markup=markup, parse_mode="HTML")
    
    await message.answer("⏳ Chek adminga ketdi. Tasdiqlanishini kuting.")
    await state.clear()

@dp.callback_query(F.data.startswith("appr_") | F.data.startswith("rej_"))
async def admin_decision(call: types.CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID): return
    parts = call.data.split("_")
    action, client_id = parts[0], int(parts[1])

    if action == "appr":
        amount = int(parts[2])
        async with db_pool.acquire() as conn:
            await conn.execute('UPDATE users SET balance = balance + $1 WHERE user_id = $2', amount, client_id)
        await add_transaction(client_id, 'topup', "Hisob to'ldirish", amount)
        await bot.send_message(client_id, f"🎉 <b>Tabriklaymiz!</b> Balansingizga {amount} UZS qo'shildi.", parse_mode="HTML")
        await call.message.edit_caption(caption=call.message.caption + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML")
    else:
        await bot.send_message(client_id, "❌ <b>To'lov rad etildi!</b>")
        await call.message.edit_caption(caption=call.message.caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")
    await call.answer()

# ================= API ENDPOINT =================
async def get_user_api(request):
    try:
        user_id = int(request.query.get('user_id', 0))
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow('SELECT balance, total_spent FROM users WHERE user_id = $1', user_id)
            if not user:
                return web.json_response({"balance": 0, "total_spent": 0, "history": []}, headers={"Access-Control-Allow-Origin": "*"})
            
            # Tarixni oxirgi 10 tasini tortib olamiz
            txs = await conn.fetch('SELECT type, name, amount, created_at FROM transactions WHERE user_id = $1 ORDER BY created_at DESC LIMIT 10', user_id)
            history = [{"type": tx['type'], "name": tx['name'], "amount": tx['amount'], "date": tx['created_at'].strftime("%Y-%m-%d %H:%M")} for tx in txs]
            
            return web.json_response({
                "balance": user['balance'],
                "total_spent": user['total_spent'],
                "history": history
            }, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        print("API XATO:", e)
        return web.json_response({"balance": 0, "total_spent": 0, "history": []}, headers={"Access-Control-Allow-Origin": "*"})

async def main():
    await init_db()
    asyncio.create_task(dp.start_polling(bot))
    
    app = web.Application()
    app.router.add_get('/api/user', get_user_api)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print("SERVIS 2.0 Ishga tushdi!")
    
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
