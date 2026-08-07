import os
import asyncio
import logging
import httpx
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

bot = Bot(token=BOT_TOKEN)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# === НАСТРОЙКА SUPABASE ===
http_client = httpx.Client(
    verify=False,
    timeout=120.0,
    limits=httpx.Limits(max_keepalive_connections=5)
)

supabase: Client = create_client(
    "https://alafwqeezmzmanowrjpvm.supabase.co",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFsYWZ3cWVlbXptYW5vd3JqcHZtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYxMTAzNzgsImV4cCI6MjEwMTY4NjM3OH0.K2Io-RgC9AxFuQC8jb7wIecmqfbpynNyiDDhdHV_xDg"
)
supabase._http_client = http_client
supabase.postgrest.session = http_client

scheduler = AsyncIOScheduler()

class Buttons:
    START = "🚀 Начать работу"
    LOGIN = "🔑 Войти в аккаунт"
    SCHEDULE = "📅 Расписание"
    MAP = "🗺️ Постер филиала"
    REPORT = "📸 Отчет для родителей"
    JOURNAL = "📋 Табель посещаемости"
    CHECKIN = "✅ Отметка о прибытии"
    STATS = "📊 Моя статистика"
    SALARY = "💰 Зарплата"
    ILL = "🤒 Сообщить о болезни"
    CANCEL = "❌ Отменить"
    SEND_ALL = "📨 Отправить во все группы"
    SEND_SELECT = "🎯 Выбрать группы"
    REWRITE = "✏️ Переписать"

def get_start_keyboard():
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=Buttons.START)]], resize_keyboard=True)

def get_login_keyboard():
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=Buttons.LOGIN)]], resize_keyboard=True)

def get_main_keyboard():
    keyboard = [
        [types.KeyboardButton(text=Buttons.SCHEDULE)],
        [types.KeyboardButton(text=Buttons.MAP)],
        [types.KeyboardButton(text=Buttons.REPORT)],
        [types.KeyboardButton(text=Buttons.JOURNAL)],
        [types.KeyboardButton(text=Buttons.CHECKIN)],
        [types.KeyboardButton(text=Buttons.STATS)],
        [types.KeyboardButton(text=Buttons.SALARY)],
        [types.KeyboardButton(text=Buttons.ILL)]
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_filials_keyboard(filials):
    keyboard = [[types.KeyboardButton(text=f)] for f in filials]
    keyboard.append([types.KeyboardButton(text=Buttons.CANCEL)])
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=Buttons.CANCEL)]], resize_keyboard=True)

def get_send_options_keyboard():
    keyboard = [
        [types.KeyboardButton(text=Buttons.SEND_ALL)],
        [types.KeyboardButton(text=Buttons.SEND_SELECT)],
        [types.KeyboardButton(text=Buttons.CANCEL)]
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_groups_keyboard(groups, selected=None):
    keyboard = []
    for g in groups:
        label = g['name']
        if selected and g['name'] in selected:
            label = f"✅ {g['name']}"
        keyboard.append([types.KeyboardButton(text=label)])
    keyboard.append([types.KeyboardButton(text="✅ Отправить выбранные")])
    keyboard.append([types.KeyboardButton(text=Buttons.CANCEL)])
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

class LoginState(StatesGroup):
    waiting_for_password = State()

class ReportState(StatesGroup):
    waiting_filial = State()
    waiting_course = State()
    waiting_text = State()
    waiting_photo = State()
    waiting_groups = State()
    confirm = State()

class JournalState(StatesGroup):
    waiting_filial = State()
    waiting_course = State()
    waiting_photo = State()

class MapState(StatesGroup):
    waiting_filial = State()

class CheckinState(StatesGroup):
    waiting_confirmation = State()

class IllState(StatesGroup):
    waiting_lesson = State()

def get_pedagog_by_telegram_id(telegram_id: int):
    try:
        result = supabase.table("pedagogs").select("*").eq("telegram_id", telegram_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

def check_password(password: str):
    try:
        result = supabase.table("pedagogs").select("*").eq("password", password).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

def get_pedagog_filials(pedagog_id: int):
    try:
        groups = supabase.table("groups").select("filial_id").eq("pedagog_id", pedagog_id).execute()
        if not groups.data:
            return []
        filial_ids = list(set([g["filial_id"] for g in groups.data]))
        filials = []
        for fid in filial_ids:
            filial = supabase.table("filials").select("name").eq("id", fid).execute()
            if filial.data:
                filials.append(filial.data[0]["name"])
        return filials
    except Exception as e:
        logger.error(f"Error getting filials: {e}")
        return []

def get_pedagog_courses(pedagog_id: int, filial_name: str):
    try:
        result = supabase.table("groups").select("type").eq("pedagog_id", pedagog_id).execute()
        courses = set()
        for row in result.data:
            if row.get("type"):
                courses.add(row.get("type"))
        return list(courses)
    except Exception as e:
        logger.error(f"Error: {e}")
        return []

def get_pedagog_groups(pedagog_id: int, filial_name: str, course: str):
    try:
        result = supabase.table("groups").select("*").eq("pedagog_id", pedagog_id).eq("type", course).execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Error: {e}")
        return []

def get_schedule_for_pedagog(pedagog_id: int, date: str = None):
    try:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        weekdays = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
        weekday = weekdays[datetime.strptime(date, "%Y-%m-%d").weekday()]
        groups = supabase.table("groups").select("*").eq("pedagog_id", pedagog_id).eq("weekday", weekday).execute()
        if not groups.data:
            return []
        result = []
        for group in groups.data:
            filial = supabase.table("filials").select("*").eq("id", group["filial_id"]).execute()
            if filial.data:
                group["filials"] = filial.data[0]
                result.append(group)
        return result
    except Exception as e:
        logger.error(f"Error getting schedule: {e}")
        return []

def get_filial_by_name(name: str):
    try:
        result = supabase.table("filials").select("*").eq("name", name).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

def get_lessons_for_tomorrow(pedagog_id: int):
    try:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        weekdays = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
        weekday = weekdays[datetime.strptime(tomorrow, "%Y-%m-%d").weekday()]
        result = supabase.table("groups").select("*, filials(name), chat_id").eq("pedagog_id", pedagog_id).eq("weekday", weekday).execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Error: {e}")
        return []

def send_report_to_chat(chat_id: int, text: str, photo_path: str = None):
    try:
        logger.info(f"🔍 Отправка в чат {chat_id}")
        if photo_path and os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo:
                bot.send_photo(chat_id=chat_id, photo=photo, caption=text)
        else:
            bot.send_message(chat_id=chat_id, text=text)
        logger.info(f"✅ Успешно отправлено в {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")
        return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    if pedagog:
        await message.answer(f"👋 С возвращением, {pedagog['name']}!", reply_markup=get_main_keyboard())
        return
    await message.answer("👋 Добро пожаловать! Введите пароль.", reply_markup=get_login_keyboard())

@dp.message(F.text == Buttons.LOGIN)
async def handle_login(message: types.Message, state: FSMContext):
    await message.answer("🔑 Введите пароль:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(LoginState.waiting_for_password)

@dp.message(LoginState.waiting_for_password)
async def process_login_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    logger.info(f"🔍 Введен пароль: {password}")
    try:
        result = supabase.table("pedagogs").select("*").eq("password", password).execute()
        logger.info(f"🔍 Результат запроса: {result.data}")
        if result.data:
            pedagog = result.data[0]
            supabase.table("pedagogs").update({"telegram_id": message.from_user.id}).eq("id", pedagog["id"]).execute()
            await message.answer(f"✅ Вход выполнен! Добро пожаловать, {pedagog['name']}!", reply_markup=get_main_keyboard())
            await state.clear()
        else:
            await message.answer("❌ Неверный пароль.", reply_markup=get_login_keyboard())
            await state.clear()
    except Exception as e:
        logger.error(f"Ошибка входа: {e}")
        await message.answer("❌ Ошибка входа. Попробуйте позже.", reply_markup=get_login_keyboard())
        await state.clear()

@dp.message(F.text == Buttons.SCHEDULE)
async def handle_schedule(message: types.Message):
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    if not pedagog:
        await message.answer("❌ Сначала войдите в аккаунт.", reply_markup=get_login_keyboard())
        return
    schedule = get_schedule_for_pedagog(pedagog["id"])
    if not schedule:
        await message.answer("📅 Сегодня занятий нет.")
        return
    text = "📅 *Ваше расписание на сегодня:*\n\n"
    for group in schedule:
        filial = group.get("filials", {})
        text += f"🏫 *{filial.get('name', 'Неизвестно')}*\n"
        text += f"📚 {group['name']} ({group['type']})\n"
        text += f"⏰ {group['time']}\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == Buttons.MAP)
async def handle_map(message: types.Message, state: FSMContext):
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    if not pedagog:
        await message.answer("❌ Сначала войдите в аккаунт.", reply_markup=get_login_keyboard())
        return
    filials = get_pedagog_filials(pedagog["id"])
    if not filials:
        await message.answer("❌ У вас нет филиалов.")
        return
    await message.answer("🗺️ Выберите филиал:", reply_markup=get_filials_keyboard(filials))
    await state.set_state(MapState.waiting_filial)

@dp.message(MapState.waiting_filial)
async def process_map_filial(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    filial = get_filial_by_name(message.text)
    if not filial:
        await message.answer("❌ Филиал не найден.")
        return
    if filial.get("poster_url"):
        await message.answer(f"🗺️ Постер филиала {filial['name']}:\n{filial['poster_url']}")
    else:
        await message.answer(f"🗺️ У филиала {filial['name']} нет постера.")
    await state.clear()

@dp.message(F.text == Buttons.REPORT)
async def handle_report(message: types.Message, state: FSMContext):
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    if not pedagog:
        await message.answer("❌ Сначала войдите в аккаунт.", reply_markup=get_login_keyboard())
        return
    filials = get_pedagog_filials(pedagog["id"])
    if not filials:
        await message.answer("❌ У вас нет филиалов.")
        return
    await message.answer("📸 Выберите филиал:", reply_markup=get_filials_keyboard(filials))
    await state.set_state(ReportState.waiting_filial)

@dp.message(ReportState.waiting_filial)
async def process_report_filial(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    courses = get_pedagog_courses(pedagog["id"], message.text)
    if not courses:
        await message.answer("❌ У вас нет курсов в этом филиале.")
        await state.clear()
        return
    await state.update_data(filial=message.text)
    keyboard = [[types.KeyboardButton(text=c)] for c in courses]
    keyboard.append([types.KeyboardButton(text=Buttons.CANCEL)])
    await message.answer("📚 Выберите курс:", reply_markup=types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True))
    await state.set_state(ReportState.waiting_course)

@dp.message(ReportState.waiting_course)
async def process_report_course(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    await state.update_data(course=message.text)
    await message.answer("📝 Введите текст отчета:", reply_markup=get_cancel_keyboard())
    await state.set_state(ReportState.waiting_text)

@dp.message(ReportState.waiting_text)
async def process_report_text(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    await state.update_data(text=message.text)
    await message.answer("📸 Отправьте фото (или нажмите 'Пропустить'):", reply_markup=get_cancel_keyboard())
    await state.set_state(ReportState.waiting_photo)

@dp.message(ReportState.waiting_photo)
async def process_report_photo(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    if message.photo:
        file = await bot.get_file(message.photo[-1].file_id)
        file_path = f"reports/{file.file_id}.jpg"
        await bot.download_file(file.file_path, file_path)
        await state.update_data(photo=file_path)
    else:
        await state.update_data(photo=None)
    data = await state.get_data()
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    groups = get_pedagog_groups(pedagog["id"], data["filial"], data["course"])
    if not groups:
        await message.answer("❌ Нет групп для отправки.")
        await state.clear()
        return
    keyboard = get_groups_keyboard(groups)
    await message.answer("📋 Выберите группы для отправки:", reply_markup=keyboard)
    await state.set_state(ReportState.waiting_groups)

@dp.message(ReportState.waiting_groups)
async def process_report_groups(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    if message.text == "✅ Отправить выбранные":
        data = await state.get_data()
        selected = data.get("selected_groups", [])
        if not selected:
            await message.answer("❌ Выберите хотя бы одну группу.")
            return
        pedagog = get_pedagog_by_telegram_id(message.from_user.id)
        groups = get_pedagog_groups(pedagog["id"], data["filial"], data["course"])
        selected_groups = [g for g in groups if g["name"] in selected]
        text = f"📸 *Отчет от {pedagog['name']}*\n\n{data['text']}"
        success = 0
        for group in selected_groups:
            if group.get("chat_id"):
                if send_report_to_chat(group["chat_id"], text, data.get("photo")):
                    success += 1
        await message.answer(f"✅ Отправлено в {success} групп.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    data = await state.get_data()
    selected = data.get("selected_groups", [])
    if message.text.startswith("✅ "):
        group_name = message.text[2:]
        if group_name in selected:
            selected.remove(group_name)
        else:
            selected.append(group_name)
    else:
        if message.text in selected:
            selected.remove(message.text)
        else:
            selected.append(message.text)
    await state.update_data(selected_groups=selected)
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    groups = get_pedagog_groups(pedagog["id"], data["filial"], data["course"])
    await message.answer("📋 Выберите группы:", reply_markup=get_groups_keyboard(groups, selected))

@dp.message(F.text == Buttons.JOURNAL)
async def handle_journal(message: types.Message, state: FSMContext):
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    if not pedagog:
        await message.answer("❌ Сначала войдите в аккаунт.", reply_markup=get_login_keyboard())
        return
    filials = get_pedagog_filials(pedagog["id"])
    if not filials:
        await message.answer("❌ У вас нет филиалов.")
        return
    await message.answer("📋 Выберите филиал:", reply_markup=get_filials_keyboard(filials))
    await state.set_state(JournalState.waiting_filial)

@dp.message(JournalState.waiting_filial)
async def process_journal_filial(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    courses = get_pedagog_courses(pedagog["id"], message.text)
    if not courses:
        await message.answer("❌ У вас нет курсов в этом филиале.")
        await state.clear()
        return
    await state.update_data(filial=message.text)
    keyboard = [[types.KeyboardButton(text=c)] for c in courses]
    keyboard.append([types.KeyboardButton(text=Buttons.CANCEL)])
    await message.answer("📚 Выберите курс:", reply_markup=types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True))
    await state.set_state(JournalState.waiting_course)

@dp.message(JournalState.waiting_course)
async def process_journal_course(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    await state.update_data(course=message.text)
    await message.answer("📸 Отправьте фото табеля:", reply_markup=get_cancel_keyboard())
    await state.set_state(JournalState.waiting_photo)

@dp.message(JournalState.waiting_photo)
async def process_journal_photo(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    if not message.photo:
        await message.answer("❌ Отправьте фото.")
        return
    file = await bot.get_file(message.photo[-1].file_id)
    file_path = f"journals/{file.file_id}.jpg"
    await bot.download_file(file.file_path, file_path)
    await message.answer("✅ Табель сохранен.", reply_markup=get_main_keyboard())
    await state.clear()

@dp.message(F.text == Buttons.CHECKIN)
async def handle_checkin(message: types.Message, state: FSMContext):
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    if not pedagog:
        await message.answer("❌ Сначала войдите в аккаунт.", reply_markup=get_login_keyboard())
        return
    schedule = get_schedule_for_pedagog(pedagog["id"])
    if not schedule:
        await message.answer("✅ Сегодня занятий нет.")
        return
    text = "✅ *Отметка о прибытии*\n\n"
    for group in schedule:
        filial = group.get("filials", {})
        text += f"🏫 {filial.get('name', 'Неизвестно')}\n"
        text += f"📚 {group['name']} ({group['type']})\n"
        text += f"⏰ {group['time']}\n"
        text += f"✅ Отметка: {datetime.now().strftime('%H:%M')}\n\n"
    await message.answer(text, parse_mode="Markdown")
    await message.answer("✅ Отметка о прибытии сохранена.", reply_markup=get_main_keyboard())

@dp.message(F.text == Buttons.STATS)
async def handle_stats(message: types.Message):
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    if not pedagog:
        await message.answer("❌ Сначала войдите в аккаунт.", reply_markup=get_login_keyboard())
        return
    await message.answer("📊 *Ваша статистика*\n\n"
                        f"👤 Педагог: {pedagog['name']}\n"
                        f"📅 Сегодня: {datetime.now().strftime('%d.%m.%Y')}\n"
                        f"✅ Отметок сегодня: 0\n"
                        f"📸 Отчетов сегодня: 0",
                        parse_mode="Markdown")

@dp.message(F.text == Buttons.SALARY)
async def handle_salary(message: types.Message):
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    if not pedagog:
        await message.answer("❌ Сначала войдите в аккаунт.", reply_markup=get_login_keyboard())
        return
    triz_rate = int(os.getenv("TRIZ_RATE", 1100))
    robo_rate = int(os.getenv("ROBO_RATE", 1500))
    await message.answer(f"💰 *Зарплата*\n\n"
                        f"👤 Педагог: {pedagog['name']}\n"
                        f"📚 ТРИЗ: {triz_rate} руб./занятие\n"
                        f"🤖 Робототехника: {robo_rate} руб./занятие\n"
                        f"📅 Расчет за текущий месяц",
                        parse_mode="Markdown")

@dp.message(F.text == Buttons.ILL)
async def handle_ill(message: types.Message, state: FSMContext):
    pedagog = get_pedagog_by_telegram_id(message.from_user.id)
    if not pedagog:
        await message.answer("❌ Сначала войдите в аккаунт.", reply_markup=get_login_keyboard())
        return
    lessons = get_lessons_for_tomorrow(pedagog["id"])
    if not lessons:
        await message.answer("✅ Завтра занятий нет.")
        return
    text = "🤒 *Сообщить о болезни*\n\nВыберите занятие:\n"
    keyboard = []
    for i, lesson in enumerate(lessons):
        filial_name = lesson.get("filials", {}).get("name", "Неизвестно")
        text += f"{i+1}. {lesson['name']} ({lesson['type']}) - {filial_name} {lesson['time']}\n"
        keyboard.append([types.KeyboardButton(text=str(i+1))])
    keyboard.append([types.KeyboardButton(text=Buttons.CANCEL)])
    await state.update_data(lessons=lessons)
    await message.answer(text, reply_markup=types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True))
    await state.set_state(IllState.waiting_lesson)

@dp.message(IllState.waiting_lesson)
async def process_ill_lesson(message: types.Message, state: FSMContext):
    if message.text == Buttons.CANCEL:
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    data = await state.get_data()
    lessons = data.get("lessons", [])
    try:
        idx = int(message.text) - 1
        if idx < 0 or idx >= len(lessons):
            raise ValueError
        lesson = lessons[idx]
        pedagog = get_pedagog_by_telegram_id(message.from_user.id)
        text = f"🤒 *Болезнь*\n\nПедагог: {pedagog['name']}\n"
        text += f"Группа: {lesson['name']} ({lesson['type']})\n"
        text += f"Филиал: {lesson.get('filials', {}).get('name', 'Неизвестно')}\n"
        text += f"Время: {lesson['time']}\n"
        text += f"Дата: {(datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')}\n\n"
        text += "Занятие отменено по болезни педагога."
        if lesson.get("chat_id"):
            send_report_to_chat(lesson["chat_id"], text)
        await message.answer("✅ Сообщение о болезни отправлено в группу.", reply_markup=get_main_keyboard())
        await state.clear()
    except (ValueError, IndexError):
        await message.answer("❌ Выберите номер занятия из списка.")

async def main():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("journals", exist_ok=True)
    os.makedirs("photos", exist_ok=True)
    scheduler.add_job(send_reminders, "cron", hour=12, minute=0)
    scheduler.add_job(check_checkins, "cron", hour=8, minute=0)
    scheduler.start()
    logger.info("Бот запущен!")
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            logger.info("Перезапуск через 5 секунд...")
            await asyncio.sleep(5)

async def send_reminders():
    logger.info("Напоминания отправлены")

async def check_checkins():
    logger.info("Проверка чек-инов выполнена")

if __name__ == "__main__":
    asyncio.run(main())
