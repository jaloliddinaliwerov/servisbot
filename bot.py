import asyncio
import json
import os
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
DATABASE_URL = os.getenv("DATABASE_URL") # PostgreSQL silkasi

WEB_APP_URL = "https://servisbot.vercel.app" # Vercel silkangizni qo'ying!

KARTA_RAQAM = "5614 6822 1669 5272"
TON_HAMYON = "UQAAEnSurEdRWqgtIpzQTdgHIbF22yGCqaFD31g1Q-pUOevk"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db_pool = None # Baza bilan ulanish hovuzi

class TopUpState(StatesGroup):
    waiting_for_receipt = State()

# ================= BAZA BILAN ISHLASH FUNKSIYALARI =================
async def init_db():
    global db_pool
    # Baza bilan ulanishni o'rnatamiz
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with db_pool.acquire() as conn:
        # Agar jadval yo'q bo'lsa, yaratamiz
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance BIGINT DEFAULT 0
            )
        ''')

async def get_user_balance(user_id):
    async with db_pool.acquire() as conn:
        val = await conn.fetchval('SELECT balance FROM users WHERE user_id = $1', user_id)
        return val if val is not None else 0

async def add_user_balance(user_id, amount):
    async with db_pool.acquire() as conn:
        # Yangi odam bo'lsa qo'shadi, eski bo'lsa balansiga pulni qo'shib qo'yadi
        await conn.execute('''
            INSERT INTO users (user_id, balance) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET balance = users.balance + $2
        ''', user_id, amount)

# ================= 1. START =================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Baza yaratilishi uchun shunchaki 0 so'm qo'shib qo'yamiz (agar bazada yo'q bo'lsa)
    await add_user_balance(user_id, 0)

    web_app_btn = KeyboardButton(
        text="💎 Ilovani ochish", 
        web_app=WebAppInfo(url=WEB_APP_URL)
    )
    keyboard = ReplyKeyboardMarkup(keyboard=[[web_app_btn]], resize_keyboard=True)

    await message.answer(
        "👋 Xush kelibsiz! <b>797 | Level up team</b>\n\n"
        "Xizmatlardan foydalanish va hisob to'ldirish uchun pastdagi tugmani bosing.", 
        reply_markup=keyboard, parse_mode="HTML"
    )

# ================= 2. HTML DAN KELGAN MA'LUMOT =================
@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")

        if action == "topup":
            amount = data.get("amount")
            method = data.get("method")
            
            method_name = "Uzcard / Humo" if method == "uzcard" else "TON Crypto"
            wallet = KARTA_RAQAM if method == "uzcard" else TON_HAMYON

            text = (
                f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
                f"Tanlangan usul: <b>{method_name}</b>\n"
                f"To'lov miqdori: <b>{amount} UZS</b>\n\n"
                f"👇 Quyidagi hisobga o'tkazma qiling:\n"
                f"<code>{wallet}</code>\n\n"
                f"<i>To'lovni amalga oshirgach, chek (skrinshot)ni shu yerga yuboring.</i>"
            )
            
            await message.answer(text, parse_mode="HTML")
            await state.update_data(amount=amount)
            await state.set_state(TopUpState.waiting_for_receipt)

    except Exception as e:
        await message.answer("Tizimda xatolik yuz berdi. Iltimos qayta urinib ko'ring.")

# ================= 3. CHEK QABUL QILISH =================
@dp.message(TopUpState.waiting_for_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    amount = user_data.get("amount", 0)
    user_id = message.from_user.id

    if ADMIN_ID:
        admin_text = (
            f"💰 <b>YANGI TO'LOV CHEKI</b>\n\n"
            f"👤 Mijoz: {message.from_user.mention_html()}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💵 Kutilayotgan summa: <b>{amount} UZS</b>"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user_id}_{amount}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject_{user_id}")
            ]
        ])
        await bot.send_photo(int(ADMIN_ID), message.photo[-1].file_id, caption=admin_text, reply_markup=markup, parse_mode="HTML")
    
    await message.answer("✅ Chek qabul qilindi! Admin tekshirgach, balansingiz to'ldiriladi.")
    await state.clear()

# ================= 4. ADMIN TUGMASI (BAZANI YANGILASH) =================
@dp.callback_query(F.data.startswith("approve_") | F.data.startswith("reject_"))
async def admin_decision_handler(call: types.CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer("Sizga ruxsat etilmagan!", show_alert=True)
        return

    data_parts = call.data.split("_")
    action = data_parts[0]
    client_id = int(data_parts[1])

    if action == "approve":
        amount = int(data_parts[2])
        # BAZAGA PULNI QO'SHAMIZ
        await add_user_balance(client_id, amount)
        new_balance = await get_user_balance(client_id)
        
        await bot.send_message(
            chat_id=client_id, 
            text=f"🎉 <b>Tabriklaymiz!</b> To'lovingiz tasdiqlandi.\nBalansingizga <b>{amount} UZS</b> qo'shildi!\n\nJoriy balans: <b>{new_balance} UZS</b>",
            parse_mode="HTML"
        )
        await call.message.edit_caption(caption=call.message.caption + f"\n\n✅ <b>TASDIQLANDI (+{amount} UZS)</b>", parse_mode="HTML")
        await call.answer("Tasdiqlandi!")

    elif action == "reject":
        await bot.send_message(client_id, "❌ <b>To'lovingiz rad etildi!</b>\nIltimos, chekni to'g'ri yuborganingizga ishonch hosil qiling yoki admin bilan bog'laning.", parse_mode="HTML")
        await call.message.edit_caption(caption=call.message.caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")
        await call.answer("Rad etildi!")

# ================= 5. API (WEB APP UCHUN) VA SERVER =================
async def get_balance_api(request):
    try:
        user_id = int(request.query.get('user_id', 0))
        # BAZADAN PULNI SO'RAYMIZ
        balance = await get_user_balance(user_id)
    except:
        balance = 0
        
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET",
    }
    return web.json_response({"balance": balance}, headers=headers)

async def handle_ping(request):
    return web.Response(text="797 Bot Serveri ishlamoqda!")

async def main():
    # ENG MUHIMI: Avval bazani ishga tushiramiz!
    await init_db()
    
    asyncio.create_task(dp.start_polling(bot))
    
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/api/balance', get_balance_api)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"Bot va Baza ishga tushdi (Port: {port})")
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
