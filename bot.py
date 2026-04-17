import asyncio
import json
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# ================= RAILWAY/RENDER SOZLAMALARI =================
BOT_TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_ID = os.getenv("ADMIN_ID") # Railwayda kiritishingiz shart

WEB_APP_URL = "https://servisbot.vercel.app" # O'zingizning Vercel silkangizni qo'ying!

KARTA_RAQAM = "5614 6822 1669 5272"
TON_HAMYON = "UQAAEnSurEdRWqgtIpzQTdgHIbF22yGCqaFD31g1Q-pUOevk"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

users_db = {} # Vaqtinchalik ma'lumotlar bazasi (Balanslar)

class TopUpState(StatesGroup):
    waiting_for_receipt = State()

# ================= 1. START VA MENYU =================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = 0 # Yangi odamga 0 so'm balans beramiz

    web_app_btn = KeyboardButton(
        text="💎 Ilovani ochish", 
        web_app=WebAppInfo(url=WEB_APP_URL)
    )
    keyboard = ReplyKeyboardMarkup(keyboard=[[web_app_btn]], resize_keyboard=True)

    await message.answer(
        "👋 Xush kelibsiz! <b>797 | Level up team</b>\n\n"
        "Xizmatlardan foydalanish va hisob to'ldirish uchun pastdagi tugmani bosing.", 
        reply_markup=keyboard,
        parse_mode="HTML"
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

# ================= 3. CHEK QABUL QILISH VA ADMINGA YUBORISH =================
@dp.message(TopUpState.waiting_for_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    amount = user_data.get("amount", "Noma'lum")
    user_id = message.from_user.id

    if ADMIN_ID:
        admin_text = (
            f"💰 <b>YANGI TO'LOV CHEKI</b>\n\n"
            f"👤 Mijoz: {message.from_user.mention_html()}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💵 Kutilayotgan summa: <b>{amount} UZS</b>"
        )
        
        # Adminga tasdiqlash uchun tugmalar yaratamiz
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user_id}_{amount}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject_{user_id}")
            ]
        ])

        await bot.send_photo(
            chat_id=int(ADMIN_ID), 
            photo=message.photo[-1].file_id, 
            caption=admin_text, 
            reply_markup=markup, 
            parse_mode="HTML"
        )
    
    await message.answer("✅ Chek qabul qilindi! Admin tekshirgach, balansingiz to'ldiriladi.")
    await state.clear()

# ================= 4. ADMIN TUGMALARNI BOSGANDA =================
@dp.callback_query(F.data.startswith("approve_") | F.data.startswith("reject_"))
async def admin_decision_handler(call: types.CallbackQuery):
    # Faqat admin bosa olishi uchun kichik himoya
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer("Sizga ruxsat etilmagan!", show_alert=True)
        return

    data_parts = call.data.split("_")
    action = data_parts[0]
    client_id = int(data_parts[1])

    if action == "approve":
        amount = int(data_parts[2])
        # Mijozning balansiga pul qo'shamiz
        users_db[client_id] = users_db.get(client_id, 0) + amount
        
        # Mijozga xushxabar yuboramiz
        await bot.send_message(
            chat_id=client_id, 
            text=f"🎉 <b>Tabriklaymiz!</b> To'lovingiz tasdiqlandi.\nBalansingizga <b>{amount} UZS</b> qo'shildi!\n\nJoriy balans: <b>{users_db[client_id]} UZS</b>",
            parse_mode="HTML"
        )
        
        # Admindagi chek ostidagi tugmalarni o'chirib, "Tasdiqlandi" deb yozib qo'yamiz
        new_caption = call.message.caption + f"\n\n✅ <b>TASDIQLANDI (+{amount} UZS)</b>"
        await call.message.edit_caption(caption=new_caption, parse_mode="HTML")
        await call.answer("Tasdiqlandi!")

    elif action == "reject":
        # Mijozga rad etilganini aytamiz
        await bot.send_message(
            chat_id=client_id, 
            text="❌ <b>To'lovingiz rad etildi!</b>\nIltimos, chekni to'g'ri yuborganingizga ishonch hosil qiling yoki admin bilan bog'laning.",
            parse_mode="HTML"
        )
        
        # Admindagi xabarni o'zgartiramiz
        new_caption = call.message.caption + "\n\n❌ <b>RAD ETILDI</b>"
        await call.message.edit_caption(caption=new_caption, parse_mode="HTML")
        await call.answer("Rad etildi!")

# ================= 5. SERVER YARATISH (Railway) =================
async def handle_ping(request):
    return web.Response(text="797 Bot Serveri ishlamoqda!")

async def main():
    asyncio.create_task(dp.start_polling(bot))
    
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"Bot ishga tushdi (Port: {port})")
    
    while True:
        await asyncio.sleep(3600)

# ================= 5. API VA SERVER YARATISH (Railway) =================
# Web App balansni bilishi uchun API darcha
async def get_balance(request):
    try:
        user_id = int(request.query.get('user_id', 0))
        balance = users_db.get(user_id, 0)
    except:
        balance = 0
        
    # Vercel'dan keladigan so'rovlarga ruxsat berish (CORS)
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET",
    }
    return web.json_response({"balance": balance}, headers=headers)

async def handle_ping(request):
    return web.Response(text="797 Bot Serveri ishlamoqda!")

async def main():
    asyncio.create_task(dp.start_polling(bot))
    
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/api/balance', get_balance) # YAngi API manzil qo'shildi
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"Bot ishga tushdi (Port: {port})")
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
