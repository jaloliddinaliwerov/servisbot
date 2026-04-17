import asyncio
import json
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# ================= SOZLAMALAR =================
BOT_TOKEN = "8408871760:AAFG_X_wHpzG8wffchb6HxfEug7c7Pn8PFE"
ADMIN_ID = 6734269605 # O'zingizning Telegram ID raqamingizni yozing (@the_797)

# To'lov ma'lumotlari
KARTA_RAQAM = "5614 6822 1669 5272"
TON_HAMYON = "UQAAEnSurEdRWqgtIpzQTdgHIbF22yGCqaFD31g1Q-pUOevk"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Vaqtinchalik ma'lumotlar bazasi (Asl loyihada SQLite yoki PostgreSQL ishlatiladi)
users_db = {} # Foydalanuvchilar balansi
active_transactions = {} # Ayni paytda kutilayotgan to'lov summalari {user_id: amount}

# FSM Holatlar (Foydalanuvchi qadamlarini kuzatish uchun)
class TopUpState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()

# ================= ASOSIY MENYU =================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Yangi foydalanuvchini bazaga qo'shish
    if user_id not in users_db:
        users_db[user_id] = 0

    # Web App tugmasini yaratish
    web_app_btn = KeyboardButton(
        text="📱 Ilovani ochish", 
        web_app=WebAppInfo(url="https://servisbot.vercel.app/") # HTML faylingiz manzili
    )
    keyboard = ReplyKeyboardMarkup(keyboard=[[web_app_btn]], resize_keyboard=True)

    await message.answer(
        "👋 Xush kelibsiz! \n\n<b>797 | Level up team</b> xizmatlaridan foydalanish uchun pastdagi tugmani bosing.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ================= WEB APP MA'LUMOTLARINI QABUL QILISH =================
@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)
    action = data.get("action")

    if action == "topup_request":
        await message.answer("Hisobni to'ldirish uchun kerakli summani kiriting (masalan: 50000):")
        await state.set_state(TopUpState.waiting_for_amount)

    elif action == "buy_item":
        item_id = data.get("item_id")
        user_input = data.get("user_input", "Kiritilmadi")
        
        # Bu yerda mahsulot narxi tekshiriladi va balansdan yechiladi
        # Hozircha adminga to'g'ridan-to'g'ri xabar yuboramiz
        await message.answer("⏳ So'rovingiz adminga yuborildi. Tez orada buyurtmangiz bajariladi!")
        
        admin_text = (
            f"🛍 <b>YANGI BUYURTMA</b>\n"
            f"👤 Mijoz: {message.from_user.mention_html()}\n"
            f"📦 Mahsulot ID: <code>{item_id}</code>\n"
            f"📝 Qo'shimcha ma'lumot (ID/User): <b>{user_input}</b>"
        )
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")

# ================= TO'LOV MANTIQI VA BIR XIL SUMMANI BLOKLASH =================
@dp.message(TopUpState.waiting_for_amount)
async def process_topup_amount(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not message.text.isdigit():
        await message.answer("Iltimos, summani faqat raqamlarda kiriting (masalan: 50000).")
        return

    amount = int(message.text)

    # Eng muhim qism: Bir xil summani tekshirish
    if amount in active_transactions.values():
        await message.answer(
            "⚠️ <b>Iltimos, boshqa summa kiriting!</b>\n"
            f"Ayni vaqtda boshqa mijoz {amount} so'm bilan hisob to'ldirmoqda. "
            "To'lovlar chalkashmasligi uchun summaga bir oz o'zgartirish kiriting (masalan: 50001).",
            parse_mode="HTML"
        )
        return

    # Tranzaksiyani band qilish
    active_transactions[user_id] = amount

    payment_text = (
        f"💳 <b>To'lov ma'lumotlari</b>\n\n"
        f"To'lov summasi: <b>{amount} so'm</b>\n\n"
        f"Uzcard: <code>{KARTA_RAQAM}</code>\n"
        f"TON: <code>{TON_HAMYON}</code>\n\n"
        f"To'lovni amalga oshirgach, shu yerga chekni (skrinshot) yuboring."
    )
    
    await message.answer(payment_text, parse_mode="HTML")
    await state.set_state(TopUpState.waiting_for_receipt)

# ================= CHEKNI QABUL QILISH VA ADMINGA YUBORISH =================
@dp.message(TopUpState.waiting_for_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    amount = active_transactions.get(user_id, 0)

    # Adminga tasdiqlash uchun yuborish
    admin_text = (
        f"💰 <b>HISOB TO'LDIRISH SO'ROVI</b>\n"
        f"👤 Mijoz: {message.from_user.mention_html()}\n"
        f"💵 Kutilayotgan summa: <b>{amount} so'm</b>\n\n"
        f"Iltimos, to'lovni tekshirib, mijoz hisobini to'ldiring."
    )
    
    await bot.send_photo(
        chat_id=ADMIN_ID, 
        photo=message.photo[-1].file_id, 
        caption=admin_text, 
        parse_mode="HTML"
    )

    # Tranzaksiyani o'chirish (boshqalar yana bu summani ishlata olishi uchun)
    if user_id in active_transactions:
        del active_transactions[user_id]

    await message.answer("✅ Chek qabul qilindi! Admin tasdiqlagandan so'ng balansingiz to'ldiriladi.")
    await state.clear()

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
