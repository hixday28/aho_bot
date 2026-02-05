import asyncio
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import db

# --- КОНФИГУРАЦИЯ ---
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(id_str.strip()) for id_str in admin_ids_str.split(",") if id_str.strip()]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- FSM: ДОБАВИЛИ ЭТАП FIO ---
class RequestForm(StatesGroup):
    fio = State()       # <-- Новый шаг
    category = State()
    urgency = State()
    location = State()
    description = State()

# --- КЛАВИАТУРЫ ---

def main_kb(user_id):
    buttons = [
        [KeyboardButton(text="🆕 Создать заявку")],
        [KeyboardButton(text="📂 Мои заявки")]
    ]
    if user_id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="📋 Активные заявки (Админ)")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def category_kb():
    buttons = [[KeyboardButton(text=c)] for c in ["Электрика", "Сантехника", "Мебель", "Уборка", "Другое"]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def urgency_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Обычная"), KeyboardButton(text="Срочно")],
        [KeyboardButton(text="🆘 АВАРИЯ")]
    ], resize_keyboard=True, one_time_keyboard=True)

def admin_actions_kb(req_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Взять в работу", callback_data=f"work_{req_id}")],
        [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done_{req_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{req_id}")]
    ])

def admin_in_work_kb(req_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done_{req_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{req_id}")]
    ])

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я бот для заявок в АХО.\n\n"
        "Нажмите кнопку внизу, чтобы сообщить о проблеме 👇"
    )
    await message.answer(welcome_text, reply_markup=main_kb(message.from_user.id))

# --- ЛОГИКА СОЗДАНИЯ ЗАЯВКИ ---

@dp.message(F.text == "🆕 Создать заявку")
async def start_request(message: types.Message, state: FSMContext):
    # 1. Проверяем, знаем ли мы ФИО этого человека
    known_fio = await db.get_user_fio(message.from_user.id)
    
    if known_fio:
        # Если знаем - сразу сохраняем в память и идем к категории
        await state.update_data(fio=known_fio)
        await state.set_state(RequestForm.category)
        await message.answer(f"Здравствуйте, {known_fio}! Выберите категорию проблемы:", reply_markup=category_kb())
    else:
        # Если не знаем - спрашиваем
        await state.set_state(RequestForm.fio)
        await message.answer("Мы с вами еще не знакомы. Пожалуйста, напишите ваши <b>Фамилию и Имя</b> (например: Иванов Иван):", parse_mode="HTML", reply_markup=types.ReplyKeyboardRemove())

# 2. Обрабатываем ввод ФИО (только для новичков)
@dp.message(RequestForm.fio)
async def process_fio(message: types.Message, state: FSMContext):
    fio = message.text
    # Сохраняем в базу навсегда
    await db.register_user(message.from_user.id, fio)
    # Сохраняем в контекст заявки
    await state.update_data(fio=fio)
    
    await state.set_state(RequestForm.category)
    await message.answer("Приятно познакомиться! Теперь выберите категорию:", reply_markup=category_kb())

# 3. Категория -> Срочность
@dp.message(RequestForm.category)
async def process_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(RequestForm.urgency)
    await message.answer("Укажите срочность:", reply_markup=urgency_kb())

# 4. Срочность -> Локация
@dp.message(RequestForm.urgency)
async def process_urgency(message: types.Message, state: FSMContext):
    await state.update_data(urgency=message.text)
    await state.set_state(RequestForm.location)
    await message.answer("Где это произошло? (№ кабинета / этаж)", reply_markup=types.ReplyKeyboardRemove())

# 5. Локация -> Описание
@dp.message(RequestForm.location)
async def process_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(RequestForm.description)
    await message.answer("Опишите проблему (можно прикрепить 1 фото):")

# 6. Финиш
@dp.message(RequestForm.description)
async def process_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    if data.get("is_processing"):
        return
    await state.update_data(is_processing=True)

    photo_id = None
    desc_text = message.text or message.caption or "Без описания"
    if message.photo:
        photo_id = message.photo[-1].file_id
    
    # Собираем данные. Используем FIO из состояния
    user_data = {
        'user_id': message.from_user.id,
        'username': f"@{message.from_user.username}" if message.from_user.username else "No Nickname",
        'user_fio': data['fio'],  # <--- ВОТ НАШЕ ФИО
        'category': data['category'],
        'urgency': data['urgency'],
        'location': data['location'],
        'description': desc_text,
        'photo_id': photo_id
    }
    
    req_id = await db.add_request(user_data)
    
    await message.answer(f"✅ Заявка #{req_id} принята!", reply_markup=main_kb(message.from_user.id))
    await state.clear()
    
    # --- УВЕДОМЛЕНИЕ АДМИНАМ (теперь с ФИО) ---
    admin_text = (
        f"🆕 <b>ЗАЯВКА #{req_id}</b>\n"
        f"👤 Кто: <b>{user_data['user_fio']}</b> ({user_data['username']})\n" # <--- Выводим ФИО жирным
        f"🏢 Где: {user_data['location']}\n"
        f"🔧 {user_data['category']} | 🔥 {user_data['urgency']}\n"
        f"📝 {user_data['description']}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            if photo_id:
                await bot.send_photo(admin_id, photo=photo_id, caption=admin_text, parse_mode="HTML", reply_markup=admin_actions_kb(req_id))
            else:
                await bot.send_message(admin_id, text=admin_text, parse_mode="HTML", reply_markup=admin_actions_kb(req_id))
        except Exception as e:
            logging.error(f"Error sending to admin {admin_id}: {e}")


# --- МОИ ЗАЯВКИ ---
@dp.message(F.text == "📂 Мои заявки")
async def my_requests(message: types.Message):
    requests = await db.get_user_requests(message.from_user.id)
    if not requests:
        await message.answer("Список пуст.")
        return
    
    text = "📋 <b>Ваши последние заявки:</b>\n\n"
    for r in requests:
        icon = "🆕"
        if "В работе" in r['status']: icon = "🛠"
        elif "Выполнено" in r['status']: icon = "✅"
        elif "Отклонено" in r['status']: icon = "❌"
        
        desc = r['description']
        if len(desc) > 35: desc = desc[:35] + "..."
            
        text += f"<b>#{r['id']} {r['category']}</b>\n└ <i>{desc}</i>\n└ Статус: {icon} {r['status']}\n\n"
    
    await message.answer(text, parse_mode="HTML")

# --- ПАНЕЛЬ АДМИНА ---
@dp.message(F.text == "📋 Активные заявки (Админ)")
async def admin_active_requests(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return

    requests = await db.get_active_requests_for_admin()
    if not requests:
        await message.answer("Активных заявок нет ☕️")
        return

    await message.answer(f"Активных заявок: {len(requests)}")

    for req in requests:
        # В панели админа тоже показываем ФИО
        # req['user_fio'] может быть None у старых заявок, поэтому ставим заглушку
        fio = req['user_fio'] if req['user_fio'] else req['username']

        caption = (
            f"⚡️ <b>ЗАЯВКА #{req['id']}</b> ({req['status']})\n"
            f"👤 <b>{fio}</b>\n"
            f"🏢 {req['location']}\n"
            f"🔧 {req['category']} | 🔥 {req['urgency']}\n"
            f"📝 {req['description']}"
        )

        keyboard = admin_in_work_kb(req['id']) if "В работе" in req['status'] else admin_actions_kb(req['id'])

        try:
            if req['photo_id']:
                await bot.send_photo(message.from_user.id, photo=req['photo_id'], caption=caption, parse_mode="HTML", reply_markup=keyboard)
            else:
                await bot.send_message(message.from_user.id, text=caption, parse_mode="HTML", reply_markup=keyboard)
            await asyncio.sleep(0.3)
        except Exception: pass

# --- CALLBACKS ---
@dp.callback_query(F.data.startswith("work_"))
async def admin_work(callback: types.CallbackQuery):
    req_id = callback.data.split("_")[1]
    await db.update_status(req_id, "В работе 🛠")
    try: await callback.message.edit_reply_markup(reply_markup=admin_in_work_kb(req_id))
    except: pass
    await callback.answer("Взято в работу", show_alert=False)
    
    req_data = await db.get_request(req_id)
    if req_data:
        try: await bot.send_message(req_data[0], f"🛠 Ваша заявка #{req_id} («{req_data[1][:30]}...») взята в работу!")
        except: pass

@dp.callback_query(F.data.startswith("done_"))
async def admin_done(callback: types.CallbackQuery):
    req_id = callback.data.split("_")[1]
    await db.update_status(req_id, "Выполнено ✅")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"Заявка #{req_id} закрыта.")
    
    req_data = await db.get_request(req_id)
    if req_data:
        try: await bot.send_message(req_data[0], f"✅ Заявка #{req_id} («{req_data[1][:30]}...») выполнена!")
        except: pass
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(callback: types.CallbackQuery):
    req_id = callback.data.split("_")[1]
    await db.update_status(req_id, "Отклонено ❌")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"Заявка #{req_id} отклонена.")
    
    req_data = await db.get_request(req_id)
    if req_data:
        try: await bot.send_message(req_data[0], f"❌ Заявка #{req_id} («{req_data[1][:30]}...») отклонена.")
        except: pass
    await callback.answer()

async def main():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())