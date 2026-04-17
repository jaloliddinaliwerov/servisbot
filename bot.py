import asyncio
import json
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# ================= RAILWAY/RENDER SOZLAMALARI =================
BOT_TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_ID = os.getenv("ADMIN_ID") # Railwayda kiritishingiz shart

WEB_APP_URL = "https://sizning-saytingiz.vercel.app" # O'zingizning Vercel silkangizni qo'ying!

KARTA_RAQAM = "5614 6822 1669 5272"
TON_HAMYON = "UQAAEnSurEdRWqgtIpzQTdgHIbF22yGCqaFD31g1Q-pUOevk"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class TopUpState(StatesGroup):
    waiting_for_receipt = State()

# ================= 1. START VA MENYU =================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # DQQAT: Web App albatta shu klaviatura orqali ochilishi kerak, 
    # aks holda tg.sendData() umuman ishlamaydi va yopilib ketadi!
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

# ================= 2. HTML DAN KELGAN MA'LUMOTNI TUTISH =================
@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message, state: FSMContext):
    # Bu log Railway konsolida ko'rinadi. Agar ma'lumot kelsa, shu yozuv chiqadi!
    print(f"WEB APP DAN MA'LUMOT KELDI: {message.web_app_data.data}") 
    
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")

        if action == "topup":
            amount = data.get("amount")
            method = data.get("method")
            
            method_name = "Uzcard / Humo" if method == "uzcard" else "TON Crypto"
            wallet = KARTA_RAQAM if method == "uzcard" else TON_HAMYON

            # Mijozga to'lov rekvizitlarini yuborish
            text = (
                f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
                f"Tanlangan usul: <b>{method_name}</b>\n"
                f"To'lov miqdori: <b>{amount} UZS</b>\n\n"
                f"👇 Quyidagi hisobga o'tkazma qiling:\n"
                f"<code>{wallet}</code>\n\n"
                f"<i>To'lovni amalga oshirgach, chek (skrinshot)ni shu yerga yuboring.</i>"
            )
            
            await message.answer(text, parse_mode="HTML")
            await state.update_data(amount=amount) # Summani xotiraga saqlaymiz
            await state.set_state(TopUpState.waiting_for_receipt)

    except Exception as e:
        print(f"XATOLIK YUZ BERDI: {e}")
        await message.answer("Tizimda xatolik yuz berdi. Iltimos qayta urinib ko'ring.")

# ================= 3. CHEK QABUL QILISH =================
@dp.message(TopUpState.waiting_for_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    amount = user_data.get("amount", "Noma'lum")

    # Adminga yuborish
    if ADMIN_ID:
        admin_text = (
            f"💰 <b>YANGI TO'LOV CHEKI</b>\n\n"
            f"👤 Mijoz: {message.from_user.mention_html()}\n"
            f"💵 Kutilayotgan summa: <b>{amount} UZS</b>"
        )
        await bot.send_photo(chat_id=int(ADMIN_ID), photo=message.photo[-1].file_id, caption=admin_text, parse_mode="HTML")
    
    await message.answer("✅ Chek qabul qilindi! Admin tekshirgach, balansingiz to'ldiriladi.")
    await state.clear()

# ================= 4. SERVER YARATISH (Railway o'chirmasligi uchun) =================
async def handle_ping(request):
    return web.Response(text="797 Bot Serveri ishlamoqda!")

async def main():
    # Botni ishga tushirish
    asyncio.create_task(dp.start_polling(bot))
    
    # HTTP Serverni ishga tushirish
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

if __name__ == "__main__":
    asyncio.run(main())
