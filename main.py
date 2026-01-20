import asyncio
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import db  # Наш файл db.py

# --- КОНФИГУРАЦИЯ И НАСТРОЙКИ ---

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Загружаем список админов из .env (формат: 12345,67890)
admin_ids_str = os.getenv("ADMIN_IDS", "")
# Превращаем строку в список чисел, убирая пробелы
ADMIN_IDS = [int(id_str.strip()) for id_str in admin_ids_str.split(",") if id_str.strip()]

# Настройка логирования (вывод в консоль)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- FSM: СОСТОЯНИЯ (ЭТАПЫ ЗАЯВКИ) ---
class RequestForm(StatesGroup):
    category = State()
    urgency = State()
    location = State()
    description = State()

# --- КЛАВИАТУРЫ ---

def main_kb(user_id):
    """Главное меню. Показывает кнопку админа только админам."""
    buttons = [
        [KeyboardButton(text="🆕 Создать заявку")],
        [KeyboardButton(text="📂 Мои заявки")]
    ]
    # Проверка: есть ли ID пользователя в списке админов
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

# 1. Полная клавиатура (для новой заявки)
def admin_actions_kb(req_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Взять в работу", callback_data=f"work_{req_id}")],
        [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done_{req_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{req_id}")]
    ])

# 2. Урезанная клавиатура (когда уже взяли в работу)
def admin_in_work_kb(req_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        # Кнопки "Взять в работу" здесь нет, чтобы не нажимать дважды
        [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done_{req_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{req_id}")]
    ])


# --- ОБРАБОТЧИКИ: КОМАНДЫ И МЕНЮ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    # Очищаем состояние (сброс зависших диалогов)
    await state.clear()
    
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я бот для заявок в АХО.\n\n"
        "Чтобы оставить заявку, нажмите кнопку внизу 👇"
    )
    # Отправляем меню, соответствующее правам пользователя
    await message.answer(welcome_text, reply_markup=main_kb(message.from_user.id))


# --- СЦЕНАРИЙ: СОЗДАНИЕ ЗАЯВКИ ---

@dp.message(F.text == "🆕 Создать заявку")
async def start_request(message: types.Message, state: FSMContext):
    await state.set_state(RequestForm.category)
    await message.answer("Выберите категорию:", reply_markup=category_kb())

@dp.message(RequestForm.category)
async def process_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(RequestForm.urgency)
    await message.answer("Укажите срочность:", reply_markup=urgency_kb())

@dp.message(RequestForm.urgency)
async def process_urgency(message: types.Message, state: FSMContext):
    await state.update_data(urgency=message.text)
    await state.set_state(RequestForm.location)
    await message.answer("Где это произошло? (№ кабинета / этаж)", reply_markup=types.ReplyKeyboardRemove())

@dp.message(RequestForm.location)
async def process_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(RequestForm.description)
    await message.answer("Опишите проблему (можно прикрепить 1 фото):")

@dp.message(RequestForm.description)
async def process_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # --- ЗАЩИТА ОТ ДУБЛЕЙ (ФОТОАЛЬБОМЫ) ---
    # Если юзер шлет альбом из 5 фото, обрабатываем только первое
    if data.get("is_processing"):
        return
    await state.update_data(is_processing=True)
    # ----------------------------------------

    photo_id = None
    desc_text = message.text or message.caption or "Без описания"
    
    if message.photo:
        photo_id = message.photo[-1].file_id # Берем лучшее качество
    
    user_data = {
        'user_id': message.from_user.id,
        'username': f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name,
        'category': data['category'],
        'urgency': data['urgency'],
        'location': data['location'],
        'description': desc_text,
        'photo_id': photo_id
    }
    
    # Сохраняем в БД
    req_id = await db.add_request(user_data)
    
    # Ответ пользователю
    await message.answer(
        f"✅ Заявка #{req_id} принята! Исполнители уведомлены.", 
        reply_markup=main_kb(message.from_user.id)
    )
    
    # Сбрасываем состояние
    await state.clear()
    
    # --- РАССЫЛКА ВСЕМ АДМИНАМ ---
    admin_text = (
        f"🆕 <b>НОВАЯ ЗАЯВКА #{req_id}</b>\n"
        f"👤 От: {user_data['username']}\n"
        f"🏢 Где: {user_data['location']}\n"
        f"🔧 Категория: {user_data['category']}\n"
        f"🔥 Срочность: {user_data['urgency']}\n"
        f"📝 Инфо: {user_data['description']}"
    )
    
    # Отправляем каждому админу из списка
    for admin_id in ADMIN_IDS:
        try:
            if photo_id:
                await bot.send_photo(admin_id, photo=photo_id, caption=admin_text, parse_mode="HTML", reply_markup=admin_actions_kb(req_id))
            else:
                await bot.send_message(admin_id, text=admin_text, parse_mode="HTML", reply_markup=admin_actions_kb(req_id))
        except Exception as e:
            logging.error(f"Ошибка отправки админу {admin_id}: {e}")


# --- СЦЕНАРИЙ: МОИ ЗАЯВКИ (ДЛЯ ЮЗЕРА) ---

@dp.message(F.text == "📂 Мои заявки")
async def my_requests(message: types.Message):
    requests = await db.get_user_requests(message.from_user.id)
    if not requests:
        await message.answer("У вас пока нет заявок.")
        return
    
    text = "📋 <b>Ваши последние заявки:</b>\n\n"
    for r in requests:
        # Выбираем иконку
        icon = "🆕"
        if "В работе" in r['status']: icon = "🛠"
        elif "Выполнено" in r['status']: icon = "✅"
        elif "Отклонено" in r['status']: icon = "❌"
        
        # Обрезаем описание, если оно слишком длинное (чтобы не засорять экран)
        desc = r['description']
        if len(desc) > 35:
            desc = desc[:35] + "..."
            
        # Формируем красивый блок
        text += (
            f"<b>#{r['id']} {r['category']}</b>\n"
            f"└ <i>{desc}</i>\n"
            f"└ Статус: {icon} {r['status']}\n\n"
        )
    
    await message.answer(text, parse_mode="HTML")


# --- СЦЕНАРИЙ: ПАНЕЛЬ АДМИНА ---

@dp.message(F.text == "📋 Активные заявки (Админ)")
async def admin_active_requests(message: types.Message):
    # Проверка прав доступа
    if message.from_user.id not in ADMIN_IDS:
        return

    requests = await db.get_active_requests_for_admin()
    
    if not requests:
        await message.answer("Активных заявок нет! Можно пить кофе ☕️")
        return

    await message.answer(f"Найдено заявок: {len(requests)}")

    for req in requests:
        caption = (
            f"⚡️ <b>ЗАЯВКА #{req['id']}</b> ({req['status']})\n"
            f"👤 От: {req['username']}\n"
            f"🏢 Где: {req['location']}\n"
            f"🔧 {req['category']} | 🔥 {req['urgency']}\n"
            f"📝 {req['description']}"
        )

        # ЛОГИКА КНОПОК: Если уже в работе - не показываем кнопку "Взять"
        if "В работе" in req['status']:
            keyboard = admin_in_work_kb(req['id'])
        else:
            keyboard = admin_actions_kb(req['id'])

        try:
            if req['photo_id']:
                await bot.send_photo(message.from_user.id, photo=req['photo_id'], caption=caption, parse_mode="HTML", reply_markup=keyboard)
            else:
                await bot.send_message(message.from_user.id, text=caption, parse_mode="HTML", reply_markup=keyboard)
            await asyncio.sleep(0.3) # Анти-спам задержка
        except Exception as e:
            logging.error(f"Ошибка вывода заявки админу: {e}")


# --- ОБРАБОТЧИКИ КНОПОК (CALLBACKS) ---

@dp.callback_query(F.data.startswith("work_"))
async def admin_work(callback: types.CallbackQuery):
    req_id = callback.data.split("_")[1]
    
    # 1. Меняем статус в БД
    await db.update_status(req_id, "В работе 🛠")
    
    # 2. Меняем клавиатуру на "урезанную" (без кнопки Взять)
    try:
        await callback.message.edit_reply_markup(reply_markup=admin_in_work_kb(req_id))
    except Exception:
        pass

    # Всплывающее уведомление админу
    await callback.answer("Заявка взята в работу!", show_alert=False)
    
    # 3. Уведомляем пользователя
    req_data = await db.get_request(req_id)
    if req_data:
        try:
            await bot.send_message(req_data[0], f"🛠 Ваша заявка #{req_id} взята в работу!")
        except:
            pass # Если юзер заблочил бота

@dp.callback_query(F.data.startswith("done_"))
async def admin_done(callback: types.CallbackQuery):
    req_id = callback.data.split("_")[1]
    await db.update_status(req_id, "Выполнено ✅")
    
    # Убираем кнопки совсем
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"Заявка #{req_id} закрыта.")
    
    req_data = await db.get_request(req_id)
    if req_data:
        try:
            await bot.send_message(req_data[0], f"✅ Заявка #{req_id} выполнена! Спасибо.")
        except:
            pass
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(callback: types.CallbackQuery):
    req_id = callback.data.split("_")[1]
    await db.update_status(req_id, "Отклонено ❌")
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"Заявка #{req_id} отклонена.")
    
    req_data = await db.get_request(req_id)
    if req_data:
        try:
            await bot.send_message(req_data[0], f"❌ Заявка #{req_id} отклонена администратором.")
        except:
            pass
    await callback.answer()


# --- ЗАПУСК ---

async def main():
    await db.init_db()
    print("Бот запущен...")
    # Удаляем старые вебхуки, чтобы бот не отвечал на старые сообщения
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")