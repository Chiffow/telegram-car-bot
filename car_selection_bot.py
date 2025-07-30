import logging
import pickle
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import datetime
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import aiohttp  # pip install aiohttp
import time

# Глобальные переменные для статистики
car_selection_requests = []  # Список заявок на подбор автомобилей
customs_calc_requests = []   # Список запросов калькулятора таможни
total_users = set()          # Множество уникальных пользователей

# Функции для сохранения и загрузки статистики
def save_statistics():
    """Сохраняет статистику в файл."""
    try:
        stats_data = {
            'car_selection_requests': car_selection_requests,
            'customs_calc_requests': customs_calc_requests,
            'total_users': list(total_users)  # set нельзя сериализовать, конвертируем в list
        }
        with open('bot_statistics.pkl', 'wb') as f:
            pickle.dump(stats_data, f)
        logger.info("Статистика успешно сохранена в файл")
    except Exception as e:
        logger.error(f"Ошибка при сохранении статистики: {e}")

def load_statistics():
    """Загружает статистику из файла."""
    global car_selection_requests, customs_calc_requests, total_users
    try:
        if os.path.exists('bot_statistics.pkl'):
            with open('bot_statistics.pkl', 'rb') as f:
                stats_data = pickle.load(f)
            car_selection_requests = stats_data.get('car_selection_requests', [])
            customs_calc_requests = stats_data.get('customs_calc_requests', [])
            total_users = set(stats_data.get('total_users', []))  # конвертируем обратно в set
            logger.info(f"Статистика загружена: {len(car_selection_requests)} заявок, {len(customs_calc_requests)} калькуляций, {len(total_users)} пользователей")
        else:
            logger.info("Файл статистики не найден, начинаем с пустой статистики")
    except Exception as e:
        logger.error(f"Ошибка при загрузке статистики: {e}")
        # Если файл поврежден, начинаем с пустой статистики
        car_selection_requests = []
        customs_calc_requests = []
        total_users = set()

# Включаем логирование, чтобы видеть ошибки
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определяем состояния для нашего диалога
(
    MAIN_MENU,          # новое состояние для главного меню
    BRAND_INPUT,        # ввод марки автомобиля
    MODEL_INPUT,        # ввод модели автомобиля
    YEAR_INPUT,         # ввод года выпуска
    ENGINE_VOLUME_INPUT, # ввод объема двигателя
    BRAND_MODEL,
    YEAR,
    ENGINE_VOLUME,
    FUEL_TYPE,
    DRIVETRAIN,
    MILEAGE,
    COLOR,
    BUDGET,
    CITY,
    CUSTOMS_PRICE,
    CUSTOMS_EXCHANGE_RATE, # новый шаг: курс валюты
    CUSTOMS_AGE,         # новый шаг: возраст авто
    CUSTOMS_ENGINE_TYPE, # новый шаг: тип двигателя
    CUSTOMS_IMPORTER,    # новый шаг: цель ввоза
    CUSTOMS_ENGINE,
    CUSTOMS_CITY,        # новый шаг: город доставки
) = range(21)

# Справочник марок и моделей
CAR_BRANDS = {
    # Немецкие марки
    "BMW": ["1 Series", "2 Series", "3 Series", "4 Series", "5 Series", "6 Series", "7 Series", "8 Series", "X1", "X2", "X3", "X4", "X5", "X6", "X7", "Z4", "i3", "i4", "i7", "iX"],
    "Mercedes-Benz": ["A-Class", "B-Class", "C-Class", "E-Class", "S-Class", "CLA", "CLS", "GLA", "GLB", "GLC", "GLE", "GLS", "G-Class", "AMG GT", "EQS", "EQE", "EQB"],
    "Audi": ["A1", "A3", "A4", "A5", "A6", "A7", "A8", "Q2", "Q3", "Q4", "Q5", "Q7", "Q8", "TT", "RS", "e-tron", "e-tron GT"],
    "Volkswagen": ["Polo", "Golf", "Passat", "Tiguan", "Touareg", "Arteon", "ID.3", "ID.4", "ID.5", "T-Roc", "T-Cross", "Taigo"],
    "Porsche": ["911", "Cayman", "Boxster", "Cayenne", "Macan", "Panamera", "Taycan"],
    
    # Японские марки
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander", "Prius", "C-HR", "Yaris", "Avalon", "Tacoma", "Tundra", "4Runner", "Sequoia", "bZ4X"],
    "Honda": ["Civic", "Accord", "CR-V", "Pilot", "HR-V", "Odyssey", "Ridgeline", "e:Ny1", "CR-Z"],
    "Nissan": ["Altima", "Maxima", "Sentra", "Rogue", "Murano", "Pathfinder", "Armada", "Frontier", "Titan", "Leaf", "Ariya"],
    "Mazda": ["Mazda2", "Mazda3", "Mazda6", "CX-3", "CX-30", "CX-5", "CX-9", "MX-5", "MX-30"],
    "Subaru": ["Impreza", "Legacy", "Outback", "Forester", "Crosstrek", "Ascent", "BRZ", "WRX", "Solterra"],
    "Lexus": ["ES", "IS", "LS", "GS", "LC", "RC", "UX", "NX", "RX", "GX", "LX", "LFA"],
    "Infiniti": ["Q50", "Q60", "Q70", "QX30", "QX50", "QX55", "QX60", "QX80"],
    "Acura": ["ILX", "TLX", "RLX", "RDX", "MDX", "NSX"],
    "Mitsubishi": ["Mirage", "Lancer", "Outlander", "Eclipse Cross", "ASX", "Pajero", "L200"],
    
    # Корейские марки
    "Hyundai": ["Solaris", "Elantra", "Sonata", "Tucson", "Santa Fe", "Palisade", "Venue", "Kona", "IONIQ", "Nexo"],
    "Kia": ["Rio", "Ceed", "Cerato", "Optima", "Sportage", "Sorento", "Telluride", "Stonic", "Soul", "EV6", "Niro"],
    "Genesis": ["G70", "G80", "G90", "GV60", "GV70", "GV80"],
    
    # Американские марки
    "Ford": ["Fiesta", "Focus", "Mondeo", "Mustang", "Explorer", "Escape", "Edge", "Expedition", "F-150", "Ranger", "Bronco", "Mach-E"],
    "Chevrolet": ["Spark", "Aveo", "Cruze", "Malibu", "Impala", "Camaro", "Corvette", "Trax", "Equinox", "Blazer", "Traverse", "Tahoe", "Suburban", "Silverado", "Bolt"],
    "Cadillac": ["CT4", "CT5", "CT6", "XT4", "XT5", "XT6", "Escalade", "Lyriq"],
    "Buick": ["Encore", "Envision", "Enclave", "Regal"],
    "Lincoln": ["Corsair", "Aviator", "Navigator", "Continental"],
    "Dodge": ["Challenger", "Charger", "Durango", "Journey"],
    "Jeep": ["Renegade", "Compass", "Cherokee", "Grand Cherokee", "Gladiator", "Wrangler"],
    "Chrysler": ["300", "Pacifica", "Voyager"],
    "GMC": ["Terrain", "Acadia", "Yukon", "Sierra", "Hummer EV"],
    
    # Французские марки
    "Renault": ["Clio", "Megane", "Captur", "Kadjar", "Koleos", "Duster", "Sandero", "Logan", "Zoe"],
    "Peugeot": ["208", "308", "508", "2008", "3008", "5008", "Partner", "Expert"],
    "Citroen": ["C1", "C3", "C4", "C5", "Berlingo", "C-Elysee", "C4 Cactus"],
    "DS": ["DS 3", "DS 4", "DS 7", "DS 9"],
    
    # Итальянские марки
    "Fiat": ["500", "Panda", "Tipo", "Doblo", "Ducato"],
    "Alfa Romeo": ["Giulietta", "Giulia", "Stelvio", "Tonale"],
    "Lancia": ["Ypsilon"],
    "Ferrari": ["F8", "SF90", "296", "812", "Roma", "Portofino", "Purosangue"],
    "Lamborghini": ["Huracan", "Aventador", "Urus", "Revuelto"],
    "Maserati": ["Ghibli", "Quattroporte", "Levante", "Grecale", "MC20"],
    
    # Шведские марки
    "Volvo": ["S60", "S90", "V60", "V90", "XC40", "XC60", "XC90", "C40"],
    "Saab": ["9-3", "9-5"],
    
    # Британские марки
    "Land Rover": ["Defender", "Discovery", "Range Rover", "Range Rover Sport", "Range Rover Velar", "Range Rover Evoque"],
    "Jaguar": ["XE", "XF", "XJ", "F-Pace", "E-Pace", "I-Pace", "F-Type"],
    "Mini": ["Cooper", "Countryman", "Clubman", "Electric"],
    "Bentley": ["Continental", "Flying Spur", "Bentayga"],
    "Rolls-Royce": ["Phantom", "Ghost", "Wraith", "Dawn", "Cullinan"],
    "Aston Martin": ["DB11", "Vantage", "DBS", "DBX"],
    "McLaren": ["720S", "765LT", "Artura", "GT", "Senna"],
    
    # Китайские марки
    "Geely": ["Coolray", "Atlas", "Tugella", "Monjaro"],
    "Chery": ["Tiggo", "Arrizo", "Exeed"],
    "Haval": ["H6", "H9", "Jolion", "Dargo"],
    "Changan": ["CS35", "CS55", "CS75", "CS95"],
    "BYD": ["Atto 3", "Seal", "Dolphin", "Tang", "Han"],
    "NIO": ["ES6", "ES8", "EC6", "ET7"],
    "XPeng": ["P7", "G3", "P5"],
    
    # Российские марки
    "Lada": ["Granta", "Vesta", "Xray", "Largus", "Niva"],
    "UAZ": ["Patriot", "Hunter", "Pickup", "Profi"],
    "GAZ": ["Volga", "Gazelle", "Sobol"],
    
    # Другие европейские марки
    "Skoda": ["Fabia", "Octavia", "Superb", "Kamiq", "Karoq", "Kodiaq", "Enyaq"],
    "Seat": ["Ibiza", "Leon", "Arona", "Ateca", "Tarraco"],
    "Opel": ["Corsa", "Astra", "Insignia", "Mokka", "Crossland", "Grandland"],
    "Dacia": ["Sandero", "Logan", "Duster", "Spring"],
    "Alpine": ["A110"],
    "Bugatti": ["Chiron", "Veyron", "Divo"],
    "Koenigsegg": ["Jesko", "Gemera", "Regera"],
    "Pagani": ["Huayra", "Zonda"],
    
    # Электромобили
    "Tesla": ["Model S", "Model 3", "Model X", "Model Y", "Cybertruck", "Roadster"],
    "Rivian": ["R1T", "R1S"],
    "Lucid": ["Air", "Gravity"],
    "Polestar": ["1", "2", "3"],
    "Rimac": ["Nevera", "Concept One"],
}

CAR_COLORS = [
    ("⚪ Белый", "Белый"),
    ("⚫ Черный", "Черный"),
    ("🟫 Коричневый", "Коричневый"),
    ("🟥 Красный", "Красный"),
    ("🟦 Синий", "Синий"),
    ("🟩 Зеленый", "Зеленый"),
    ("🟨 Желтый", "Желтый"),
    ("🟧 Оранжевый", "Оранжевый"),
    ("🟪 Фиолетовый", "Фиолетовый"),
    ("🪙 Серебристый", "Серебристый"),
    ("⬜ Серый", "Серый"),
]

# Кэш для курсов валют
currency_cache = {"rates": None, "timestamp": 0}

async def get_currency_rates():
    now = time.time()
    # Кэш на 1 час
    if currency_cache["rates"] and now - currency_cache["timestamp"] < 3600:
        return currency_cache["rates"]
    
    # Пробуем несколько API для получения актуальных курсов
    apis = [
        "https://api.exchangerate.host/latest?base=EUR&symbols=USD,RUB,KRW",
        "https://api.exchangerate-api.com/v4/latest/EUR",
        "https://open.er-api.com/v6/latest/EUR"
    ]
    
    for url in apis:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        rates = data.get("rates") or data.get("conversion_rates", {})
                        if rates:
                            rates["EUR"] = 1.0
                            
                            # Рассчитываем курсы KRW к другим валютам
                            eur_to_krw = rates.get("KRW", 1470)  # 1 EUR = X KRW
                            eur_to_usd = rates.get("USD", 1.08)  # 1 EUR = X USD
                            eur_to_rub = rates.get("RUB", 102)   # 1 EUR = X RUB
                            
                            # Добавляем курсы KRW к другим валютам
                            rates["KRW_to_RUB"] = eur_to_rub / eur_to_krw  # 1 KRW = X RUB
                            rates["KRW_to_USD"] = eur_to_usd / eur_to_krw  # 1 KRW = X USD
                            rates["KRW_to_EUR"] = 1.0 / eur_to_krw        # 1 KRW = X EUR
                            
                            currency_cache["rates"] = rates
                            currency_cache["timestamp"] = now
                            return rates
        except Exception as e:
            continue
    
    # Если все API не работают, возвращаем дефолтные курсы
    return {
        "EUR": 1.0,
        "USD": 1.08,
        "RUB": 102,
        "KRW": 1470,
        "KRW_to_RUB": 0.0599,  # 1 KRW = 0.0599 RUB (актуальный курс)
        "KRW_to_USD": 0.000735,  # 1 KRW = 0.000735 USD
        "KRW_to_EUR": 0.00068,   # 1 KRW = 0.00068 EUR
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start - показывает главное меню."""
    # Очищаем все данные пользователя
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("🚗 Подбор автомобиля", callback_data="car_selection")],
        [InlineKeyboardButton("💰 Калькулятор стоимости", callback_data="customs_calc")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🎉 <b>Добро пожаловать в Yumicar - бот подбора автомобилей из Кореи!</b>\n\n"
        "Выберите нужную опцию:\n\n"
        "🚗 <b>Подбор автомобиля</b> - поможем найти идеальный автомобиль по вашим параметрам\n"
        "💰 <b>Калькулятор стоимости</b> - рассчитаем полную стоимость ввоза автомобиля из Кореи\n\n"
        "Выберите действие:"
    )
    
    # Отправляем новое сообщение
    await update.effective_chat.send_message(text, reply_markup=reply_markup, parse_mode="HTML")
    return MAIN_MENU

async def brand_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает ввод марки автомобиля."""
    query = update.callback_query
    await query.answer()
    
    # Проверяем, не является ли это админской кнопкой
    if query.data.startswith("reply_to_") or query.data.startswith("call_"):
        # Это админская кнопка, игнорируем её
        return ConversationHandler.END
    
    if query.data == "to_main_menu":
        return await to_main_menu(update, context)
    elif query.data == "car_selection":
        # Запрашиваем ввод марки
        keyboard = [[InlineKeyboardButton("В главное меню", callback_data="to_main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="🚗 <b>Введите марку автомобиля:</b>\n\n"
                 "Например: Toyota, Hyundai, Kia, BMW, Mercedes, Audi и т.д.\n\n"
                 "💡 <b>Совет:</b> Введите точное название марки, как указано в документах автомобиля.",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return BRAND_INPUT
    
    # Если это не car_selection, возвращаемся в главное меню
    return await to_main_menu(update, context)


async def brand_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод марки автомобиля."""
    # Проверяем, есть ли callback_query (кнопка "В главное меню")
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "to_main_menu":
            return await to_main_menu(update, context)
        return BRAND_INPUT
    
    # Получаем текст от пользователя
    brand = update.message.text.strip()
    
    # Валидация марки
    if len(brand) < 2:
        await update.message.reply_text(
            "❌ Марка автомобиля должна содержать минимум 2 символа.\n"
            "Пожалуйста, введите марку еще раз:"
        )
        return BRAND_INPUT
    
    if len(brand) > 50:
        await update.message.reply_text(
            "❌ Марка автомобиля слишком длинная.\n"
            "Пожалуйста, введите более короткое название:"
        )
        return BRAND_INPUT
    
    # Сохраняем марку
    context.user_data["brand"] = brand
    logger.info("Марка: %s", brand)
    
    # Запрашиваем модель
    keyboard = [[InlineKeyboardButton("В главное меню", callback_data="to_main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ <b>Марка сохранена:</b> {brand}\n\n"
        f"🚗 <b>Теперь введите модель автомобиля:</b>\n\n"
        f"Например: Camry, Sonata, Sportage, X5, C-Class, A4 и т.д.\n\n"
        f"💡 <b>Совет:</b> Введите точное название модели, как указано в документах автомобиля.",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    return MODEL_INPUT


async def model_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод модели автомобиля."""
    # Проверяем, есть ли callback_query (кнопка "В главное меню")
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "to_main_menu":
            return await to_main_menu(update, context)
        return MODEL_INPUT
    
    # Получаем текст от пользователя
    model = update.message.text.strip()
    
    # Валидация модели
    if len(model) < 2:
        await update.message.reply_text(
            "❌ Модель автомобиля должна содержать минимум 2 символа.\n"
            "Пожалуйста, введите модель еще раз:"
        )
        return MODEL_INPUT
    
    if len(model) > 50:
        await update.message.reply_text(
            "❌ Модель автомобиля слишком длинная.\n"
            "Пожалуйста, введите более короткое название:"
        )
        return MODEL_INPUT
    
    # Сохраняем модель
    context.user_data["model"] = model
    logger.info("Модель: %s", model)
    
    # Переходим к вводу года
    keyboard = [[InlineKeyboardButton("В главное меню", callback_data="to_main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ <b>Модель сохранена:</b> {model}\n\n"
        f"📅 <b>Теперь введите год выпуска автомобиля:</b>\n\n"
        f"Например: 2020, 2019, 2018 и т.д.\n\n"
        f"💡 <b>Совет:</b> Введите год выпуска в формате YYYY (4 цифры).",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    return YEAR_INPUT

async def year_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод года выпуска автомобиля."""
    # Проверяем, есть ли callback_query (кнопка "В главное меню")
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "to_main_menu":
            return await to_main_menu(update, context)
        return YEAR_INPUT
    
    # Получаем текст от пользователя
    year_text = update.message.text.strip()
    
    # Валидация года
    if not year_text.isdigit():
        await update.message.reply_text(
            "❌ Год выпуска должен содержать только цифры.\n"
            "Пожалуйста, введите год еще раз (например, 2020):"
        )
        return YEAR_INPUT
    
    year = int(year_text)
    current_year = datetime.datetime.now().year
    
    if year < 1900 or year > current_year + 1:
        await update.message.reply_text(
            f"❌ Год выпуска должен быть между 1900 и {current_year + 1}.\n"
            "Пожалуйста, введите корректный год:"
        )
        return YEAR_INPUT
    
    # Сохраняем год
    context.user_data["year"] = str(year)
    logger.info("Год: %s", year)
    
    # Переходим к выбору объема двигателя
    keyboard = [
        [InlineKeyboardButton("до 1.6 л", callback_data="<1.6")],
        [InlineKeyboardButton("1.6 - 2.0 л", callback_data="1.6-2.0")],
        [InlineKeyboardButton("2.0 - 3.0 л", callback_data="2.0-3.0")],
        [InlineKeyboardButton("более 3.0 л", callback_data=">3.0")],
        [InlineKeyboardButton("Электро", callback_data="EV")],
        [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ <b>Год выпуска сохранен:</b> {year}\n\n"
        f"⚙️ <b>Выберите объем двигателя:</b>",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    return FUEL_TYPE

async def engine_volume_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод объема двигателя."""
    # Проверяем, есть ли callback_query (кнопка "В главное меню")
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "to_main_menu":
            return await to_main_menu(update, context)
        return ENGINE_VOLUME_INPUT
    
    # Получаем текст от пользователя
    engine_text = update.message.text.strip()
    
    # Валидация объема двигателя
    try:
        # Пробуем преобразовать в число
        engine_volume = float(engine_text.replace(',', '.'))
        
        if engine_volume <= 0 or engine_volume > 10:
            await update.message.reply_text(
                "❌ Объем двигателя должен быть больше 0 и меньше 10 литров.\n"
                "Пожалуйста, введите корректный объем (например, 2.0):"
            )
            return ENGINE_VOLUME_INPUT
        
    except ValueError:
        await update.message.reply_text(
            "❌ Объем двигателя должен быть числом.\n"
            "Пожалуйста, введите объем в формате X.X (например, 2.0):"
        )
        return ENGINE_VOLUME_INPUT
    
    # Сохраняем объем двигателя
    context.user_data["engine_volume"] = f"{engine_volume:.1f}"
    logger.info("Объем двигателя: %s", engine_volume)
    
    # Переходим к выбору типа топлива
    keyboard = [
        [InlineKeyboardButton("⛽ Бензин", callback_data="petrol")],
        [InlineKeyboardButton("⛽ Дизель", callback_data="diesel")],
        [InlineKeyboardButton("⚡ Электро", callback_data="electric")],
        [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ <b>Объем двигателя сохранен:</b> {engine_volume:.1f}L\n\n"
        f"⛽ <b>Выберите тип топлива:</b>",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    return FUEL_TYPE


async def fuel_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет объем двигателя и предлагает выбрать тип топлива."""
    query = update.callback_query
    await query.answer()
    data = query.data

    # Проверяем, не является ли это админской кнопкой
    if data.startswith("reply_to_") or data.startswith("call_"):
        # Это админская кнопка, игнорируем её
        return ConversationHandler.END

    if data == "to_main_menu":
        return await to_main_menu(update, context)
    elif data == "back_to_engine_choice":
        keyboard = [
            [InlineKeyboardButton("до 1.6 л", callback_data="<1.6")],
            [InlineKeyboardButton("1.6 - 2.0 л", callback_data="1.6-2.0")],
            [InlineKeyboardButton("2.0 - 3.0 л", callback_data="2.0-3.0")],
            [InlineKeyboardButton("более 3.0 л", callback_data=">3.0")],
            [InlineKeyboardButton("Электро", callback_data="EV")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_model")],
            [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Укажите объем двигателя:", reply_markup=reply_markup)
        return FUEL_TYPE

    # Сохраняем объем двигателя
    context.user_data["engine_volume"] = data
    logger.info("Объем двигателя: %s", data)

    keyboard = [
        [
            InlineKeyboardButton("Бензин", callback_data="Бензин"),
            InlineKeyboardButton("Дизель", callback_data="Дизель"),
            InlineKeyboardButton("Электро", callback_data="Электро"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_engine_choice")],
        [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Понял. Выберите вид топлива:", reply_markup=reply_markup)
    return DRIVETRAIN


async def drivetrain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет тип топлива и предлагает выбрать привод."""
    query = update.callback_query
    await query.answer()
    data = query.data

    # Проверяем, не является ли это админской кнопкой
    if data.startswith("reply_to_") or data.startswith("call_"):
        # Это админская кнопка, игнорируем её
        return ConversationHandler.END

    if data == "to_main_menu":
        return await to_main_menu(update, context)
    elif data == "back_to_fuel_choice":
        keyboard = [
            [
                InlineKeyboardButton("Бензин", callback_data="Бензин"),
                InlineKeyboardButton("Дизель", callback_data="Дизель"),
                InlineKeyboardButton("Электро", callback_data="Электро"),
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_engine_choice")],
            [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите вид топлива:", reply_markup=reply_markup)
        return DRIVETRAIN

    context.user_data["fuel_type"] = data
    logger.info("Тип топлива: %s", data)

    keyboard = [
        [
            InlineKeyboardButton("Передний", callback_data="Передний"),
            InlineKeyboardButton("Задний", callback_data="Задний"),
            InlineKeyboardButton("Полный", callback_data="Полный (4WD)"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_fuel_choice")],
        [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Отлично. Теперь выберите тип привода:", reply_markup=reply_markup
    )
    return MILEAGE


async def mileage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет тип привода и запрашивает пробег."""
    query = update.callback_query
    
    if query:
        await query.answer()
        data = query.data

        # Проверяем, не является ли это админской кнопкой
        if data.startswith("reply_to_") or data.startswith("call_"):
            # Это админская кнопка, игнорируем её
            return ConversationHandler.END

        if data == "to_main_menu":
            return await to_main_menu(update, context)
        elif data == "back_to_drivetrain_choice":
            keyboard = [
                [
                    InlineKeyboardButton("Передний", callback_data="Передний"),
                    InlineKeyboardButton("Задний", callback_data="Задний"),
                    InlineKeyboardButton("Полный", callback_data="Полный (4WD)"),
                ],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_fuel_choice")],
                [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Выберите тип привода:", reply_markup=reply_markup)
            return MILEAGE

        context.user_data["drivetrain"] = data
        logger.info("Привод: %s", data)

        await query.edit_message_text(text="Хорошо. Укажите желаемый максимальный пробег (в км):")
        return MILEAGE
    
    elif update.message:
        # Обработка ввода пробега
        user_text = update.message.text.strip()
        if user_text == "to_main_menu":
            return await to_main_menu(update, context)
        
        # Валидация пробега: только цифры, разумный диапазон
        if not user_text.isdigit():
            await update.message.reply_text("❌ Ошибка! Пробег должен содержать только цифры. Введите максимальный пробег в км:")
            return MILEAGE
        
        mileage_num = int(user_text)
        if mileage_num <= 0 or mileage_num > 1000000:
            await update.message.reply_text("❌ Ошибка! Пробег должен быть больше 0 и меньше 1,000,000 км. Введите корректный пробег:")
            return MILEAGE
        
        context.user_data["mileage"] = user_text
        logger.info("Пробег: %s", user_text)
        await update.message.reply_text("Введите желаемый цвет кузова (например, белый, черный, красный):")
        return COLOR
    
    return ConversationHandler.END


async def color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет цвет и запрашивает бюджет."""
    if update.message:
        user_text = update.message.text.strip()
        if user_text == "to_main_menu":
            return await to_main_menu(update, context)
        
        # Валидация цвета: только буквы, пробелы и дефисы
        if not user_text.replace(' ', '').replace('-', '').replace('ё', 'е').replace('Ё', 'Е').isalpha():
            await update.message.reply_text("❌ Ошибка! Цвет должен содержать только буквы. Введите цвет кузова (например, белый, черный, красный):")
            return COLOR
        
        if len(user_text) < 2 or len(user_text) > 20:
            await update.message.reply_text("❌ Ошибка! Название цвета должно быть от 2 до 20 символов. Введите корректный цвет:")
            return COLOR
        
        context.user_data["color"] = user_text
        logger.info("Цвет: %s", user_text)
        await update.message.reply_text("Почти готово. На какую сумму вы рассчитываете? Укажите сумму и валюту (например: 1000000 руб или 50000 долларов):")
        return BUDGET
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "to_main_menu":
            return await to_main_menu(update, context)
        elif query.data == "back_to_mileage":
            await query.edit_message_text(text="Укажите желаемый максимальный пробег (в км):")
            return MILEAGE
    return ConversationHandler.END


async def budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет бюджет с валютой и запрашивает город доставки."""
    if update.message:
        user_text = update.message.text.strip()
        if user_text == "to_main_menu":
            return await to_main_menu(update, context)
        
        # Это ввод бюджета с валютой
        # Парсим ввод пользователя
        text = user_text.lower().strip()
        
        # Ищем валюту в тексте
        currency = "RUB"  # по умолчанию
        if "руб" in text or "рубл" in text:
            currency = "RUB"
        elif "доллар" in text or "usd" in text or "$" in text:
            currency = "USD"
        elif "евро" in text or "eur" in text or "€" in text:
            currency = "EUR"
        elif "вон" in text or "krw" in text or "₩" in text:
            currency = "KRW"
        
        # Извлекаем число из текста
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            amount = numbers[0]  # берем первое число
            context.user_data["budget"] = amount
            context.user_data["budget_currency"] = currency
            context.user_data["budget_with_currency"] = f"{amount} {currency}"
            logger.info("Бюджет: %s %s", amount, currency)
            
            # Показываем города для выбора
            keyboard = [
                [
                    InlineKeyboardButton("Москва", callback_data="Москва"),
                    InlineKeyboardButton("Санкт-Петербург", callback_data="Санкт-Петербург"),
                ],
                [
                    InlineKeyboardButton("Новосибирск", callback_data="Новосибирск"),
                    InlineKeyboardButton("Екатеринбург", callback_data="Екатеринбург"),
                ],
                [
                    InlineKeyboardButton("Владивосток", callback_data="Владивосток"),
                    InlineKeyboardButton("Находка", callback_data="Находка"),
                ],
                [
                    InlineKeyboardButton("Восточный", callback_data="Восточный"),
                    InlineKeyboardButton("Ванино", callback_data="Ванино"),
                ],
                [
                    InlineKeyboardButton("Советская Гавань", callback_data="Советская Гавань"),
                    InlineKeyboardButton("Петропавловск-Камчатский", callback_data="Петропавловск-Камчатский"),
                ],
                [
                    InlineKeyboardButton("Магадан", callback_data="Магадан"),
                    InlineKeyboardButton("Южно-Сахалинск", callback_data="Южно-Сахалинск"),
                ],
                [
                    InlineKeyboardButton("Хабаровск", callback_data="Хабаровск"),
                    InlineKeyboardButton("Комсомольск-на-Амуре", callback_data="Комсомольск-на-Амуре"),
                ],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_budget")],
                [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Последний шаг. Выберите город доставки:", reply_markup=reply_markup)
            return CITY
        else:
            await update.message.reply_text("Пожалуйста, укажите сумму и валюту (например: 1000000 руб или 50000 долларов):")
            return BUDGET
    
    return ConversationHandler.END


async def city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор города доставки."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        # Проверяем, не является ли это админской кнопкой
        if query.data.startswith("reply_to_") or query.data.startswith("call_"):
            # Это админская кнопка, игнорируем её
            return ConversationHandler.END
            
        if query.data == "to_main_menu":
            return await to_main_menu(update, context)
        elif query.data == "back_to_budget":
            # Возвращаемся к выбору валюты
            keyboard = [
                [
                    InlineKeyboardButton("$ USD", callback_data="USD"),
                    InlineKeyboardButton("€ EUR", callback_data="EUR"),
                ],
                [
                    InlineKeyboardButton("₽ RUB", callback_data="RUB"),
                    InlineKeyboardButton("₩ KRW", callback_data="KRW"),
                ],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_color")],
                [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Выберите валюту для бюджета:", reply_markup=reply_markup)
            return BUDGET
        
        context.user_data["city"] = query.data
        logger.info("Город: %s", query.data)

        # Получаем данные из контекста
        data = context.user_data

        # Сохраняем статистику заявки
        user = update.effective_user
        
        car_request = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'timestamp': datetime.datetime.now(),
            'brand': data.get('brand', 'не указана'),
            'model': data.get('model', 'не указана'),
            'year': data.get('year', 'не указан'),
            'engine_volume': data.get('engine_volume', 'не указан'),
            'fuel_type': data.get('fuel_type', 'не указано'),
            'drivetrain': data.get('drivetrain', 'не указан'),
            'mileage': data.get('mileage', 'не указано'),
            'color': data.get('color', 'не указан'),
            'budget': data.get('budget_with_currency', data.get('budget', 'не указан')),
            'city': query.data
        }
        car_selection_requests.append(car_request)
        total_users.add(user.id)  # Добавляем пользователя в статистику
        save_statistics()  # Сохраняем статистику

        # Формируем сообщения
        brand = data.get('brand', 'не указана')
        model = data.get('model', 'не указана')
        
        # Получаем информацию о пользователе
        user = update.effective_user
        user_info = f"@{user.username}" if user.username else "Без username"
        user_full_name = f"{user.first_name} {user.last_name}" if user.last_name else user.first_name
        user_id = user.id

        # Сообщение для админа
        admin_summary = f"""
🎉 <b>Новая заявка на подбор от Yumicar!</b> 🎉

<b>👤 Информация о клиенте:</b>
🆔 <b>ID пользователя:</b> {user_id}
👤 <b>Имя:</b> {user_full_name}
📱 <b>Username:</b> {user_info}
📅 <b>Дата заявки:</b> {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>🚗 Параметры автомобиля:</b>
🚗 <b>Марка и модель:</b> {brand} {model}
📅 <b>Год выпуска:</b> {data.get('year', 'не указан')}
⚙️ <b>Объем двигателя:</b> {data.get('engine_volume', 'не указан')}
⛽ <b>Топливо:</b> {data.get('fuel_type', 'не указано')}
🏎️ <b>Привод:</b> {data.get('drivetrain', 'не указан')}
🛣️ <b>Пробег до:</b> {data.get('mileage', 'не указано')} км
🎨 <b>Цвет:</b> {data.get('color', 'не указан')}
💰 <b>Бюджет:</b> {data.get('budget_with_currency', data.get('budget', 'не указан'))}
🏙️ <b>Город доставки:</b> {data.get('city', 'не указан')}

<b>💬 Для связи с клиентом:</b>
Прямое сообщение: https://t.me/{user_info.replace('@', '')}
"""
        # Сообщение для пользователя
        user_confirmation = f"""
                ✅ <b>Ваш запрос на подбор автомобиля в Yumicar сформирован:</b>

Наши специалисты скоро свяжутся с вами для уточнения деталей.

Спасибо за обращение!
"""
        # Кнопка возврата в главное меню
        keyboard = [[InlineKeyboardButton("В главное меню", callback_data="to_main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем подтверждение пользователю
        await query.edit_message_text(text=user_confirmation, parse_mode="HTML", reply_markup=reply_markup)

        # Отправка админу в Telegram
        # ЗАМЕНИТЕ ЭТОТ ID НА ВАШ РЕАЛЬНЫЙ ID!
        # Используйте команду /myid в боте, чтобы узнать ваш ID
        admin_chat_id = 493763260  # TODO: Заменить на ваш ID
        
        logger.info(f"Пытаемся отправить сообщение админу {admin_chat_id}")
        logger.info(f"Текст сообщения: {admin_summary}")
        
        try:
            # Проверяем, что админ не заблокировал бота
            try:
                chat_info = await context.bot.get_chat(admin_chat_id)
                logger.info(f"Админ {admin_chat_id} найден: {chat_info.first_name}")
            except Exception as e:
                logger.error(f"Не удается найти админа {admin_chat_id}: {e}")
                # Попробуем отправить сообщение в любом случае
                logger.info("Пробуем отправить сообщение несмотря на ошибку")
            
            # Создаем кнопку для быстрого ответа клиенту
            reply_keyboard = [
                [InlineKeyboardButton(f"💬 Ответить клиенту", callback_data=f"reply_to_{user_id}")],
                [InlineKeyboardButton(f"📞 Позвонить клиенту", callback_data=f"call_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(reply_keyboard)
            
            logger.info(f"Отправляем сообщение админу {admin_chat_id}")
            result = await context.bot.send_message(
                chat_id=admin_chat_id, 
                text=admin_summary, 
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            logger.info(f"Сообщение админу отправлено успешно! Message ID: {result.message_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения админу: {e}")
            # Попробуем отправить без кнопок
            try:
                logger.info("Пробуем отправить сообщение без кнопок")
                result = await context.bot.send_message(
                    chat_id=admin_chat_id, 
                    text=admin_summary, 
                    parse_mode="HTML"
                )
                logger.info(f"Сообщение админу отправлено без кнопок! Message ID: {result.message_id}")
            except Exception as e2:
                logger.error(f"Ошибка при отправке сообщения админу без кнопок: {e2}")
                # Попробуем отправить простой текст
                try:
                    logger.info("Пробуем отправить простой текст")
                    result = await context.bot.send_message(
                        chat_id=admin_chat_id, 
                        text="🎉 Новая заявка от Yumicar!"
                    )
                    logger.info(f"Простое сообщение отправлено! Message ID: {result.message_id}")
                except Exception as e3:
                    logger.error(f"Не удалось отправить даже простое сообщение: {e3}")
        
        # Очищаем данные пользователя после завершения
        context.user_data.clear()
        
        # Завершаем диалог
        return MAIN_MENU
    return MAIN_MENU


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершает диалог после выбора города."""
    query = update.callback_query
    await query.answer()
    context.user_data["city"] = query.data
    logger.info("Город: %s", query.data)
    
    # Логируем вызов функции end для отслеживания
    logger.info(f"Функция end() вызвана пользователем {update.effective_user.id} (@{update.effective_user.username})")
    logger.info(f"Данные пользователя: {context.user_data}")
    
    # Проверяем, что все необходимые данные есть
    required_fields = ['brand', 'model', 'year', 'engine_volume', 'fuel_type', 'drivetrain', 'mileage', 'color', 'budget_with_currency']
    missing_fields = [field for field in required_fields if not context.user_data.get(field)]
    if missing_fields:
        logger.warning(f"Отсутствуют данные: {missing_fields}")
    else:
        logger.info("Все необходимые данные заполнены")

    # Формируем итоговое сообщение
    data = context.user_data
    brand = data.get('brand', 'не указана')
    model = data.get('model', 'не указана')
    
    # Формируем отчет для email
    user_name = update.effective_user.first_name or "не указано"
    username = update.effective_user.username or "не указан"
    current_time = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    
    email_summary = f"""Новая заявка на подбор от Yumicar! 🎉

👤 Информация о клиенте:
🆔 ID пользователя: {update.effective_user.id}
👤 Имя: {user_name}
📱 Username: @{username}
📅 Дата заявки: {current_time}

🚗 Параметры автомобиля:
🚗 Марка и модель: {brand} {model}
📅 Год выпуска: {data.get('year', 'не указан')}
⚙️ Объем двигателя: {data.get('engine_volume', 'не указан')}
⛽ Топливо: {data.get('fuel_type', 'не указано')}
🏎️ Привод: {data.get('drivetrain', 'не указан')}
🛣️ Пробег до: {data.get('mileage', 'не указано')} км
🎨 Цвет: {data.get('color', 'не указан')}
💰 Бюджет: {data.get('budget_with_currency', data.get('budget', 'не указан'))}
🏙️ Город доставки: {data.get('city', 'не указан')}

💬 Для связи с клиентом:
Прямое сообщение: https://t.me/{username}"""
    
    # Формируем сообщение для пользователя
    user_summary = f"""
✅ <b>Ваш запрос на подбор автомобиля сформирован:</b>

- <b>Автомобиль:</b> {brand} {model}
- <b>Год выпуска:</b> {data.get('year', 'не указан')}
- <b>Объем двигателя:</b> {data.get('engine_volume', 'не указан')}
- <b>Топливо:</b> {data.get('fuel_type', 'не указано')}
- <b>Привод:</b> {data.get('drivetrain', 'не указан')}
- <b>Пробег до:</b> {data.get('mileage', 'не указано')} км
- <b>Цвет:</b> {data.get('color', 'не указан')}
- <b>Бюджет:</b> {data.get('budget_with_currency', data.get('budget', 'не указан'))}
- <b>Город доставки:</b> {data.get('city', 'не указан')}

Спасибо! Наши специалисты скоро с вами свяжутся.
    """
    
    # Отправляем сообщение пользователю
    await query.edit_message_text(text=user_summary, parse_mode="HTML")
    
    # Отправляем уведомление администратору в Telegram
    try:
        admin_id = 493763260  # TODO: Укажите ваш Telegram ID
        if admin_id:
            # Создаем кнопки для быстрого ответа
            keyboard = [
                [
                    InlineKeyboardButton("📞 Позвонить", callback_data=f"call_{update.effective_user.id}"),
                    InlineKeyboardButton("💬 Написать", callback_data=f"reply_to_{update.effective_user.id}")
                ],
                [
                    InlineKeyboardButton("✅ Принять заявку", callback_data=f"accept_{update.effective_user.id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{update.effective_user.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            logger.info(f"Отправляем уведомление администратору {admin_id}:")
            logger.info(f"Длина уведомления: {len(email_summary)} символов")
            logger.info(f"Текст уведомления: {email_summary}")
            
            # Проверяем длину сообщения (Telegram ограничение: 4096 символов)
            if len(email_summary) > 4000:
                logger.warning("Уведомление слишком длинное, может быть обрезано")
                # Обрезаем до безопасной длины
                email_summary = email_summary[:4000] + "..."
                logger.info(f"Уведомление обрезано до {len(email_summary)} символов")
            
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=email_summary,
                    reply_markup=reply_markup
                )
                logger.info("Уведомление о новой заявке отправлено администратору")
            except Exception as send_error:
                logger.error("Ошибка при отправке основного уведомления: %s", send_error)
                # Пробуем отправить без кнопок
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=email_summary
                    )
                    logger.info("Уведомление отправлено без кнопок")
                except Exception as simple_error:
                    logger.error("Ошибка при отправке простого уведомления: %s", simple_error)
                    # Пробуем отправить короткое уведомление
                    try:
                        short_message = f"🎉 Новая заявка от {user_name} (@{username})\nАвтомобиль: {brand} {model}\nГород: {data.get('city', 'не указан')}"
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=short_message
                        )
                        logger.info("Короткое уведомление отправлено")
                    except Exception as short_error:
                        logger.error("Ошибка при отправке короткого уведомления: %s", short_error)
    except Exception as e:
        logger.error("Ошибка при отправке уведомления администратору: %s", e)
        logger.error("Тип ошибки: %s", type(e).__name__)
        logger.error("Детали ошибки: %s", str(e))
    
    # Отправляем email-отчет (если настроены данные для email)
    try:
        # Замените на ваш email
        admin_email = "your_admin_email@gmail.com"  # TODO: Укажите ваш email
        if admin_email != "your_admin_email@gmail.com":
            send_summary_email(email_summary, admin_email)
            logger.info("Email-отчет отправлен на %s", admin_email)
    except Exception as e:
        logger.error("Ошибка при отправке email-отчета: %s", e)
    
    context.user_data.clear()
    
    return MAIN_MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет и завершает диалог."""
    await update.message.reply_text("Действие отменено. Чтобы начать заново, введите /start.")
    context.user_data.clear()
    return MAIN_MENU




async def start_customs_calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает калькулятор стоимости."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "customs_calc":
        await query.edit_message_text("Введите стоимость автомобиля в Корее в вонах (₩):")
        return CUSTOMS_PRICE
    else:
        return await to_main_menu(update, context)
    

async def customs_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Проверяем, есть ли callback_query (кнопка "В главное меню")
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "to_main_menu":
            return await to_main_menu(update, context)
    
    user_input = update.message.text.replace(',', '.').strip()
    if user_input == "to_main_menu":
        return await to_main_menu(update, context)
    
    # Валидация цены: только цифры и точки, разумный диапазон
    if not user_input.replace('.', '').isdigit():
        await update.message.reply_text("❌ Ошибка! Стоимость должна содержать только цифры. Введите стоимость автомобиля в вонах (₩):")
        return CUSTOMS_PRICE
    
    try:
        price_krw = float(user_input)
        
        # Проверяем разумный диапазон
        if price_krw <= 0 or price_krw > 1000000000:  # 1 миллиард вон
            await update.message.reply_text("❌ Ошибка! Стоимость должна быть больше 0 и меньше 1,000,000,000 ₩. Введите корректную стоимость:")
            return CUSTOMS_PRICE
        
        context.user_data["customs_price_krw"] = price_krw
        
        # Получаем актуальные курсы валют
        rates = await get_currency_rates()
        current_krw_to_rub = rates.get("KRW_to_RUB", 0.0599)
        context.user_data["current_krw_to_rub"] = current_krw_to_rub
        
        # Переходим к запросу курса валюты
        keyboard = [
            [InlineKeyboardButton(f"Оставить текущий курс ({current_krw_to_rub:.6f} ₽)", callback_data="keep_rate")],
            [InlineKeyboardButton("Изменить курс валюты", callback_data="change_rate")],
            [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        price_rub = price_krw * current_krw_to_rub
        await update.message.reply_text(
            f"💰 <b>Стоимость автомобиля:</b> {price_krw:,.0f} ₩ ({price_rub:,.0f} ₽)\n\n"
            f"💱 <b>Текущий курс:</b> 1 ₩ = {current_krw_to_rub:.6f} ₽\n\n"
            f"Хотите изменить курс валюты или оставить текущий?",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return CUSTOMS_EXCHANGE_RATE
    except Exception as e:
        await update.message.reply_text(
            f"Ошибка при обработке стоимости: {e}\nПожалуйста, введите корректную стоимость автомобиля в вонах (число, больше нуля)."
        )
        return CUSTOMS_PRICE


# Обработчик выбора курса валюты
async def customs_exchange_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "to_main_menu":
        return await to_main_menu(update, context)
    
    if query.data == "keep_rate":
        # Используем текущий курс
        context.user_data["krw_to_rub"] = context.user_data.get("current_krw_to_rub", 0.0599)
        
        # Переходим к возрасту авто
        keyboard = [
            [InlineKeyboardButton("Моложе 3-х лет", callback_data="under_3")],
            [InlineKeyboardButton("3-5 лет", callback_data="3_5")],
            [InlineKeyboardButton("Старше 5 лет", callback_data="over_5")],
            [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите возраст автомобиля:", reply_markup=reply_markup)
        return CUSTOMS_AGE
    
    elif query.data == "change_rate":
        # Запрашиваем новый курс
        await query.edit_message_text(
            "💱 Введите новый курс валюты (1 ₩ = X ₽)\n\n"
            "Например: 0.0599\n\n"
            "⚠️ Внимание: Используйте точку как разделитель десятичных знаков",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("В главное меню", callback_data="to_main_menu")
            ]])
        )
        return CUSTOMS_EXCHANGE_RATE


# Обработчик ввода нового курса валюты
async def customs_exchange_rate_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Проверяем, есть ли callback_query (кнопка "В главное меню")
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "to_main_menu":
            return await to_main_menu(update, context)
    
    user_input = update.message.text.replace(',', '.').strip()
    if user_input == "to_main_menu":
        return await to_main_menu(update, context)
    
    # Валидация курса валюты
    if not user_input.replace('.', '').isdigit():
        await update.message.reply_text("❌ Ошибка! Курс должен содержать только цифры и точку. Введите курс валюты (например: 0.0599):")
        return CUSTOMS_EXCHANGE_RATE
    
    try:
        new_rate = float(user_input)
        
        # Проверяем разумный диапазон курса
        if new_rate <= 0 or new_rate > 1:
            await update.message.reply_text("❌ Ошибка! Курс должен быть больше 0 и меньше 1. Введите корректный курс:")
            return CUSTOMS_EXCHANGE_RATE
        
        context.user_data["krw_to_rub"] = new_rate
        
        # Показываем подтверждение и переходим к возрасту авто
        price_krw = context.user_data["customs_price_krw"]
        price_rub = price_krw * new_rate
        
        keyboard = [
            [InlineKeyboardButton("Моложе 3-х лет", callback_data="under_3")],
            [InlineKeyboardButton("3-5 лет", callback_data="3_5")],
            [InlineKeyboardButton("Старше 5 лет", callback_data="over_5")],
            [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ <b>Курс обновлен!</b>\n\n"
            f"💰 <b>Стоимость автомобиля:</b> {price_krw:,.0f} ₩ ({price_rub:,.0f} ₽)\n"
            f"💱 <b>Новый курс:</b> 1 ₩ = {new_rate:.6f} ₽\n\n"
            f"Выберите возраст автомобиля:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return CUSTOMS_AGE
        
    except Exception as e:
        await update.message.reply_text(
            f"Ошибка при обработке курса: {e}\nПожалуйста, введите корректный курс валюты (например: 0.0599)."
        )
        return CUSTOMS_EXCHANGE_RATE


# Обработчик возраста авто
async def customs_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "to_main_menu":
        return await to_main_menu(update, context)
    
    context.user_data["customs_age"] = query.data
    # Шаг: тип двигателя (как на сайте trust-encar.ru)
    keyboard = [
        [InlineKeyboardButton("Бензин или дизель", callback_data="petrol_diesel")],
        [InlineKeyboardButton("Электро", callback_data="electric")],
        [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите тип двигателя:", reply_markup=reply_markup)
    return CUSTOMS_ENGINE_TYPE

# Обработчик типа двигателя
async def customs_engine_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "to_main_menu":
        return await to_main_menu(update, context)
    
    context.user_data["customs_engine_type"] = query.data
    # Шаг: цель ввоза (как на сайте trust-encar.ru)
    keyboard = [
        [InlineKeyboardButton("Для личного использования", callback_data="personal")],
        [InlineKeyboardButton("Не для личного использования", callback_data="commercial")],
        [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Цель ввоза:", reply_markup=reply_markup)
    return CUSTOMS_IMPORTER

# Обработчик цели ввоза
async def customs_importer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "to_main_menu":
        return await to_main_menu(update, context)
    
    context.user_data["customs_importer"] = query.data
    
    # Определяем текст запроса в зависимости от типа двигателя
    engine_type = context.user_data.get("customs_engine_type", "")
    if engine_type == "electric":
        prompt_text = "Введите мощность двигателя (в л.с.):"
    else:
        prompt_text = "Введите объём двигателя (в куб. см):"
    
    await query.edit_message_text(prompt_text)
    return CUSTOMS_ENGINE

async def customs_engine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Проверяем, есть ли callback_query (кнопка "В главное меню")
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "to_main_menu":
            return await to_main_menu(update, context)
    
    user_input = update.message.text.replace(',', '.').replace(' ', '').strip()
    if user_input == "to_main_menu":
        return await to_main_menu(update, context)
    
    # Определяем тип двигателя для правильных сообщений об ошибках
    engine_type = context.user_data.get("customs_engine_type", "")
    is_electric = engine_type == "electric"
    
    # Валидация объема/мощности двигателя: только цифры и точки, разумный диапазон
    if not user_input.replace('.', '').isdigit():
        if is_electric:
            await update.message.reply_text("❌ Ошибка! Мощность двигателя должна содержать только цифры. Введите мощность (например, 150):")
        else:
            await update.message.reply_text("❌ Ошибка! Объем двигателя должен содержать только цифры и точку. Введите объем (например, 1.6 или 1600):")
        return CUSTOMS_ENGINE
    
    try:
        # Позволяем вводить 1.5 (литра), 1,5, 1500, 1 500 и т.д.
        if '.' in user_input:
            engine_liters = float(user_input)
            engine_cc = int(engine_liters * 1000)
        else:
            engine_cc = int(float(user_input))
        
        # Проверяем разумный диапазон
        if engine_cc <= 0:
            if is_electric:
                await update.message.reply_text("❌ Ошибка! Мощность двигателя должна быть больше 0. Введите корректную мощность:")
            else:
                await update.message.reply_text("❌ Ошибка! Объем двигателя должен быть больше 0. Введите корректный объем:")
            return CUSTOMS_ENGINE
        
        if is_electric and engine_cc > 1000:
            await update.message.reply_text("❌ Ошибка! Мощность двигателя должна быть меньше 1,000 л.с. Введите корректную мощность:")
            return CUSTOMS_ENGINE
        elif not is_electric and engine_cc > 10000:
            await update.message.reply_text("❌ Ошибка! Объем двигателя должен быть меньше 10,000 см³. Введите корректный объем:")
            return CUSTOMS_ENGINE
        
        context.user_data["customs_engine"] = engine_cc
        
        # Переходим к выбору города доставки
        keyboard = [
            [
                InlineKeyboardButton("Москва", callback_data="Москва"),
                InlineKeyboardButton("Санкт-Петербург", callback_data="Санкт-Петербург"),
            ],
            [
                InlineKeyboardButton("Новосибирск", callback_data="Новосибирск"),
                InlineKeyboardButton("Екатеринбург", callback_data="Екатеринбург"),
            ],
            [
                InlineKeyboardButton("Владивосток", callback_data="Владивосток"),
                InlineKeyboardButton("Находка", callback_data="Находка"),
            ],
            [
                InlineKeyboardButton("Восточный", callback_data="Восточный"),
                InlineKeyboardButton("Ванино", callback_data="Ванино"),
            ],
            [
                InlineKeyboardButton("Советская Гавань", callback_data="Советская Гавань"),
                InlineKeyboardButton("Петропавловск-Камчатский", callback_data="Петропавловск-Камчатский"),
            ],
            [
                InlineKeyboardButton("Магадан", callback_data="Магадан"),
                InlineKeyboardButton("Южно-Сахалинск", callback_data="Южно-Сахалинск"),
            ],
            [
                InlineKeyboardButton("Хабаровск", callback_data="Хабаровск"),
                InlineKeyboardButton("Комсомольск-на-Амуре", callback_data="Комсомольск-на-Амуре"),
            ],
            [InlineKeyboardButton("В главное меню", callback_data="to_main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите город доставки:", reply_markup=reply_markup)
        return CUSTOMS_CITY
        
    except Exception as e:
        if is_electric:
            await update.message.reply_text(
                f"Ошибка при обработке: {e}\nПожалуйста, введите корректную мощность двигателя (например, 150, число больше нуля)."
            )
        else:
            await update.message.reply_text(
                f"Ошибка при обработке: {e}\nПожалуйста, введите корректный объём двигателя (например, 1.6 или 1600, число больше нуля)."
            )
        return CUSTOMS_ENGINE


async def customs_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор города доставки и показывает итоговый расчет."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "to_main_menu":
        return await to_main_menu(update, context)
    
    delivery_city = query.data
    context.user_data["customs_city"] = delivery_city
    
    # Получаем данные из контекста
    price_krw = float(context.user_data["customs_price_krw"])
    age_range = context.user_data["customs_age"]
    engine_type = context.user_data["customs_engine_type"]
    importer = context.user_data["customs_importer"]
    engine_cc = int(context.user_data["customs_engine"])
    
    # Сохраняем статистику запроса калькулятора
    user = update.effective_user
    
    customs_request = {
        'user_id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'timestamp': datetime.datetime.now(),
        'price_krw': price_krw,
        'age_range': age_range,
        'engine_type': engine_type,
        'importer': importer,
        'engine_cc': engine_cc,
        'delivery_city': delivery_city
    }
    customs_calc_requests.append(customs_request)
    total_users.add(user.id)  # Добавляем пользователя в статистику
    save_statistics()  # Сохраняем статистику
    
    # Показываем итоговый расчет
    return await show_final_calculation(update, context)





async def show_final_calculation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает итоговый расчет калькулятора."""
    # Получаем данные из контекста
    price_krw = float(context.user_data["customs_price_krw"])
    age_range = context.user_data["customs_age"]
    engine_type = context.user_data["customs_engine_type"]
    importer = context.user_data["customs_importer"]
    engine_cc = int(context.user_data["customs_engine"])
    delivery_city = context.user_data["customs_city"]
    
    # Получаем курсы валют
    rates = await get_currency_rates()
    krw_to_usd = rates.get("KRW_to_USD", 0.000735)  # курс воны к доллару
    krw_to_eur = rates.get("KRW_to_EUR", 0.00068)   # курс воны к евро
    
    # Получаем курс KRW к RUB из контекста пользователя или используем актуальный
    krw_to_rub = context.user_data.get("krw_to_rub", rates.get("KRW_to_RUB", 0.0599))
    
    # Используем новую функцию расчета по формулам drom.ru
    calculation = calc_customs_duty_drom(price_krw, age_range, engine_cc, engine_type, importer, krw_to_rub)
    
    # Извлекаем результаты расчета
    price_rub = calculation['price_rub']
    freight_cost_krw = calculation['freight_cost_krw']
    freight_cost_rub = calculation['freight_cost_rub']
    cfr_rub = calculation['cfr_rub']
    duty_rub = calculation['duty_rub']
    customs_fee_rub = calculation['customs_fee_rub']
    util_fee_rub = calculation['util_fee_rub']
    excise_rub = calculation['excise_rub']
    vat_rub = calculation['vat_rub']
    broker_fee_rub = calculation['broker_fee_rub']
    total_rub = calculation['total_rub']
    additional_payments = calculation['additional_payments']
    
    # Курс вон к рублю из контекста пользователя
    
    result = f"""
💰 <b>Yumicar - Калькулятор стоимости авто из Кореи</b>

<b>📊 Исходные данные:</b>
• Стоимость в Корее: {price_krw:,.0f} ₩ ({price_rub:,.0f} ₽)
• Возраст авто: {age_range.replace('_', '-').replace('under', 'Моложе ').replace('over', 'Старше ')} лет
• Тип двигателя: {engine_type.replace('_', ' ').title()}
• {'Мощность двигателя' if engine_type == 'electric' else 'Объём двигателя'}: {engine_cc} {'л.с.' if engine_type == 'electric' else 'см³'}
• Цель ввоза: {'Личное использование' if importer == 'personal' else 'Коммерческое использование'}
• Город доставки: {delivery_city}

<b>📈 Подробный расчёт:</b>

<b>Стоимость автомобиля в Корее:</b> {price_krw:,.0f} ₩ ({price_rub:,.0f} ₽)

<b>Расходы по Корее и фрахт во Владивосток:</b> {freight_cost_krw:,.0f} ₩ ({freight_cost_rub:,.0f} ₽)

<b>CFR Владивосток:</b> {cfr_rub:,.0f} ₽

<b>Таможенная пошлина:</b> {duty_rub:,.0f} ₽

<b>Таможенный сбор:</b> {customs_fee_rub:,.0f} ₽

<b>Утилизационный сбор:</b> {util_fee_rub:,.0f} ₽

<b>Акциз:</b> {excise_rub:,.0f} ₽

<b>НДС:</b> {vat_rub:,.0f} ₽

<b>Брокерские услуги оформления, лаборатория СБКТС и ЭПТС:</b> {broker_fee_rub:,.0f} ₽

<b>🚚 Логистика (автовоз):</b> рассчитывается отдельно в зависимости от города доставки

<b>💎 Итого:</b> {cfr_rub:,.0f} ₽ + {additional_payments:,.0f} ₽ = <b>{total_rub:,.0f} ₽</b>

<b>📍 Окончательная стоимость автомобиля в {delivery_city}</b> с учетом всех платежей, пошлин, комиссий и сборов.

<b>💱 Курсы валют:</b>
• 1 ₩ = {krw_to_rub:.6f} ₽
• 1 ₩ = {krw_to_usd:.6f} $
• 1 ₩ = {krw_to_eur:.6f} €

<b>💱 Конвертация в рубли</b> основана на курсе Центрального Банка Российской Федерации, действующая на сегодняшний день, и предоставлена исключительно в информационных целях.

<b>📋 Расчет основан на актуальных таможенных ставках Российской Федерации</b>
"""
    
    # Кнопка возврата в главное меню
    keyboard = [[InlineKeyboardButton("В главное меню", callback_data="to_main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            result,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            result,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    
    return MAIN_MENU


async def to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат в главное меню."""
    # Логируем возврат в главное меню
    if update.effective_user:
        logger.info(f"Пользователь {update.effective_user.id} (@{update.effective_user.username}) вернулся в главное меню")
        logger.info(f"Данные перед очисткой: {context.user_data}")
    
    context.user_data.clear()
    
    # Показываем главное меню
    keyboard = [
        [InlineKeyboardButton("🚗 Подбор автомобиля", callback_data="car_selection")],
        [InlineKeyboardButton("💰 Калькулятор стоимости", callback_data="customs_calc")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """
🎉 <b>Добро пожаловать в Yumicar - бот подбора автомобилей из Кореи!</b>

Выберите нужную опцию:

🚗 <b>Подбор автомобиля</b> - поможем найти идеальный автомобиль по вашим параметрам
💰 <b>Калькулятор стоимости</b> - рассчитаем полную стоимость ввоза автомобиля из Кореи

Выберите действие:
"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    
    return MAIN_MENU


async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопок админа для ответа клиентам."""
    query = update.callback_query
    await query.answer()
    
    logger.info(f"Обработка админской кнопки: {query.data}")
    
    # Обрабатываем только админские кнопки
    if query.data.startswith("reply_to_"):
        user_id = query.data.split("_")[2]
        await query.edit_message_text(
            f"💬 Для ответа клиенту с ID {user_id} используйте команду:\n"
            f"`/reply {user_id} ваш текст сообщения`",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    elif query.data.startswith("call_"):
        user_id = query.data.split("_")[1]
        try:
            user = await context.bot.get_chat(user_id)
            username = user.username if user.username else f"user{user_id}"
            await query.edit_message_text(
                f"📞 Для звонка клиенту:\n"
                f"👤 Имя: {user.first_name}\n"
                f"🆔 ID: {user_id}\n"
                f"📱 Username: @{username}\n"
                f"🔗 Ссылка: https://t.me/{username}"
            )
        except Exception as e:
            logger.error(f"Ошибка при получении информации о клиенте {user_id}: {e}")
            await query.edit_message_text(
                f"❌ Ошибка при получении информации о клиенте {user_id}"
            )
    
    elif query.data.startswith("accept_"):
        user_id = query.data.split("_")[1]
        try:
            # Отправляем уведомление клиенту о принятии заявки
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ <b>Ваша заявка принята!</b>\n\nНаши специалисты свяжутся с вами в ближайшее время для обсуждения деталей.",
                parse_mode="HTML"
            )
            await query.edit_message_text(
                f"✅ Заявка от пользователя {user_id} принята.\nУведомление отправлено клиенту."
            )
        except Exception as e:
            logger.error(f"Ошибка при принятии заявки {user_id}: {e}")
            await query.edit_message_text(
                f"❌ Ошибка при принятии заявки от {user_id}"
            )
    
    elif query.data.startswith("reject_"):
        user_id = query.data.split("_")[1]
        try:
            # Отправляем уведомление клиенту об отклонении заявки
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ <b>К сожалению, ваша заявка отклонена.</b>\n\nПожалуйста, свяжитесь с нами для уточнения деталей.",
                parse_mode="HTML"
            )
            await query.edit_message_text(
                f"❌ Заявка от пользователя {user_id} отклонена.\nУведомление отправлено клиенту."
            )
        except Exception as e:
            logger.error(f"Ошибка при отклонении заявки {user_id}: {e}")
            await query.edit_message_text(
                f"❌ Ошибка при отклонении заявки от {user_id}"
            )
        return ConversationHandler.END
    
    # Если это не админская кнопка, не обрабатываем её
    return ConversationHandler.END


async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для ответа клиенту от админа."""
    # Проверяем, что команда от админа
    # ЗАМЕНИТЕ ЭТОТ ID НА ВАШ РЕАЛЬНЫЙ ID!
    if update.effective_user.id != 493763260:  # TODO: Заменить на ваш ID
        await update.message.reply_text("❌ У вас нет прав для использования этой команды.")
        return
    
    # Проверяем аргументы команды
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Неправильный формат команды.\n"
            "Используйте: /reply <user_id> <текст сообщения>"
        )
        return
    
    try:
        user_id = int(context.args[0])
        message_text = " ".join(context.args[1:])
        
        # Отправляем сообщение клиенту
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💬 <b>Сообщение от специалиста Yumicar:</b>\n\n{message_text}",
            parse_mode="HTML"
        )
        
        # Подтверждаем админу
        await update.message.reply_text(
            f"✅ Сообщение от Yumicar отправлено клиенту {user_id}:\n\n{message_text}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке сообщения: {e}")


async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для получения ID пользователя."""
    user = update.effective_user
    logger.info(f"Команда /myid вызвана пользователем {user.id} (@{user.username})")
    
    message_text = f"""🆔 <b>Ваш ID в Telegram:</b>

<b>ID:</b> {user.id}
<b>Имя:</b> {user.first_name}
<b>Username:</b> @{user.username if user.username else 'Не указан'}
<b>Полное имя:</b> {user.first_name} {user.last_name if user.last_name else ''}

💡 <b>Для использования админских команд:</b>
Замените <code>493763260</code> на <code>{user.id}</code> в коде бота."""
    
    await update.message.reply_text(message_text, parse_mode="HTML")


async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для просмотра статистики заявок (только для админа)."""
    # Проверяем, что команда от админа
    # ЗАМЕНИТЕ ЭТОТ ID НА ВАШ РЕАЛЬНЫЙ ID!
    if update.effective_user.id != 493763260:  # TODO: Заменить на ваш ID
        await update.message.reply_text("❌ У вас нет прав для использования этой команды.")
        return
    
    # Подсчитываем статистику
    total_car_requests = len(car_selection_requests)
    total_customs_requests = len(customs_calc_requests)
    unique_users = len(total_users)
    
    # Статистика за сегодня
    today = datetime.datetime.now().date()
    today_car_requests = len([req for req in car_selection_requests if req['timestamp'].date() == today])
    today_customs_requests = len([req for req in customs_calc_requests if req['timestamp'].date() == today])
    
    # Статистика за последние 7 дней
    week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    week_car_requests = len([req for req in car_selection_requests if req['timestamp'] >= week_ago])
    week_customs_requests = len([req for req in customs_calc_requests if req['timestamp'] >= week_ago])
    
    # Популярные города доставки
    city_stats = {}
    for req in car_selection_requests:
        city = req.get('city', 'не указан')
        city_stats[city] = city_stats.get(city, 0) + 1
    
    popular_cities = sorted(city_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Популярные марки автомобилей
    brand_stats = {}
    for req in car_selection_requests:
        brand = req.get('brand', 'не указана')
        brand_stats[brand] = brand_stats.get(brand, 0) + 1
    
    popular_brands = sorted(brand_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Формируем отчет
    stats_text = f"""
📊 <b>Статистика Yumicar Bot</b>

<b>📈 Общая статистика:</b>
• Всего заявок на подбор: <b>{total_car_requests}</b>
• Всего запросов калькулятора: <b>{total_customs_requests}</b>
• Уникальных пользователей: <b>{unique_users}</b>

<b>📅 Статистика за сегодня:</b>
• Заявок на подбор: <b>{today_car_requests}</b>
• Запросов калькулятора: <b>{today_customs_requests}</b>

<b>📅 Статистика за последние 7 дней:</b>
• Заявок на подбор: <b>{week_car_requests}</b>
• Запросов калькулятора: <b>{week_customs_requests}</b>

<b>🏙️ Популярные города доставки:</b>
"""
    
    for city, count in popular_cities:
        stats_text += f"• {city}: <b>{count}</b> заявок\n"
    
    stats_text += "\n<b>🚗 Популярные марки автомобилей:</b>\n"
    
    for brand, count in popular_brands:
        stats_text += f"• {brand}: <b>{count}</b> заявок\n"
    
    # Последние 5 заявок
    if car_selection_requests:
        stats_text += "\n<b>🕐 Последние 5 заявок на подбор:</b>\n"
        for req in car_selection_requests[-5:]:
            username = f"@{req['username']}" if req['username'] else "Без username"
            time_str = req['timestamp'].strftime("%d.%m.%Y %H:%M")
            stats_text += f"• {username} - {req['brand']} {req['model']} ({time_str})\n"
    
    # Последние 5 запросов калькулятора
    if customs_calc_requests:
        stats_text += "\n<b>🕐 Последние 5 запросов калькулятора:</b>\n"
        for req in customs_calc_requests[-5:]:
            username = f"@{req['username']}" if req['username'] else "Без username"
            time_str = req['timestamp'].strftime("%d.%m.%Y %H:%M")
            price_rub = req['price_krw'] * 0.0601
            stats_text += f"• {username} - {req['price_krw']:,.0f} ₩ ({price_rub:,.0f} ₽) - {req['delivery_city']} ({time_str})\n"
    
    await update.message.reply_text(stats_text, parse_mode="HTML")


async def test_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Тестовая команда для проверки отправки сообщения админу."""
    # ЗАМЕНИТЕ ЭТОТ ID НА ВАШ РЕАЛЬНЫЙ ID!
    admin_chat_id = 493763260  # TODO: Заменить на ваш ID
    
    try:
        # Создаем тестовые кнопки админа
        reply_keyboard = [
            [InlineKeyboardButton(f"💬 Ответить клиенту", callback_data=f"reply_to_123456789")],
            [InlineKeyboardButton(f"📞 Позвонить клиенту", callback_data=f"call_123456789")]
        ]
        reply_markup = InlineKeyboardMarkup(reply_keyboard)
        
        test_message = """
🧪 <b>Тестовое сообщение с админскими кнопками!</b>

Это тестовое сообщение для проверки работы отправки уведомлений админу.

Попробуйте нажать на кнопки ниже:
"""
        
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=test_message,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        await update.message.reply_text("✅ Тестовое сообщение с кнопками отправлено админу!")
        logger.info(f"Тестовое сообщение отправлено админу {admin_chat_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке тестового сообщения: {e}")
        logger.error(f"Ошибка тестового сообщения: {e}")


async def test_simple_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Простая тестовая команда для проверки кнопок."""
    logger.info(f"Команда /testsimple вызвана пользователем {update.effective_user.id} (@{update.effective_user.username})")
    
    keyboard = [
        [InlineKeyboardButton("Тестовая кнопка", callback_data="test_button")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🧪 Простая тестовая кнопка:",
        reply_markup=reply_markup
    )


async def test_simple_notification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Простой тест уведомления для всех пользователей."""
    logger.info(f"Команда /test_simple_notification вызвана пользователем {update.effective_user.id} (@{update.effective_user.username})")
    
    try:
        # Отправляем простое тестовое сообщение пользователю
        test_message = f"""🧪 <b>ПРОСТОЙ ТЕСТ УВЕДОМЛЕНИЯ</b>

Это тестовое уведомление для проверки работы бота.

👤 <b>Ваши данные:</b>
🆔 ID: {update.effective_user.id}
👤 Имя: {update.effective_user.first_name}
📱 Username: @{update.effective_user.username if update.effective_user.username else 'Не указан'}

📅 Дата: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}

✅ Если вы видите это сообщение, значит бот работает корректно!"""
        
        await update.message.reply_text(test_message, parse_mode="HTML")
        logger.info("Простое тестовое уведомление отправлено")
        
    except Exception as e:
        error_msg = f"❌ Ошибка при отправке простого тестового уведомления: {e}"
        await update.message.reply_text(error_msg)
        logger.error("Ошибка при отправке простого тестового уведомления: %s", e)





def send_summary_email(summary: str, to_email: str):
    """
    Отправляет email-отчет о заявке на подбор автомобиля
    """
    try:
        # Настройки Gmail (замените на ваши данные)
        from_email = "your_email@gmail.com"  # TODO: Укажите ваш Gmail
        password = "your_app_password"       # TODO: Укажите пароль приложения Gmail
        
        # Если настройки не изменены, пропускаем отправку
        if from_email == "your_email@gmail.com" or password == "your_app_password":
            logger.warning("Email настройки не настроены. Отчет не отправлен.")
            return False
        
        msg = MIMEText(summary, "plain", "utf-8")
        msg["Subject"] = Header("Новая заявка на подбор от Yumicar! 🎉", "utf-8")
        msg["From"] = from_email
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, password)
            server.sendmail(from_email, [to_email], msg.as_string())
        
        logger.info("Email-отчет успешно отправлен на %s", to_email)
        return True
        
    except Exception as e:
        logger.error("Ошибка при отправке email: %s", e)
        return False


def calc_customs_duty(price_eur, year, engine_cc):
    import datetime
    current_year = datetime.datetime.now().year
    age = current_year - year

    # Таблица ставок для авто до 3 лет
    duty_table = [
        (1000, 1.5),
        (1500, 1.7),
        (1800, 2.5),
        (2300, 2.7),
        (3000, 3.0),
        (float('inf'), 3.6),
    ]

    if age < 3:
        # Найти ставку по объёму
        for limit, rate in duty_table:
            if engine_cc <= limit:
                min_duty = engine_cc * rate
                break
        percent_duty = price_eur * 0.15
        duty = max(percent_duty, min_duty)
    else:
        # Для авто старше 3 лет — только ставка за 1 см³
        if engine_cc <= 1000:
            rate = 3.0
        elif engine_cc <= 1500:
            rate = 3.2
        elif engine_cc <= 1800:
            rate = 3.5
        elif engine_cc <= 2300:
            rate = 4.8
        elif engine_cc <= 3000:
            rate = 5.0
        else:
            rate = 5.7
        duty = engine_cc * rate

    return duty


def calc_customs_duty_drom(price_krw, age_range, engine_cc, engine_type, importer, krw_to_rub=0.0599):
    """
    Расчет таможенных пошлин по актуальным ставкам Российской Федерации
    """
    # Конвертация в рубли (курс может быть передан пользователем или использован по умолчанию)
    price_rub = price_krw * krw_to_rub
    
    # Расходы по Корее и фрахт во Владивосток (как на сайте)
    freight_cost_krw = 1800000  # 1,800,000 ₩ (как на сайте)
    freight_cost_rub = freight_cost_krw * krw_to_rub
    
    # CFR Владивосток
    cfr_rub = price_rub + freight_cost_rub
    
    # Таможенная пошлина
    if engine_type == "electric":
        # Для электромобилей - процентная ставка от CFR
        if age_range == "under_3":
            # Для электромобилей моложе 3 лет - 14.54% от CFR (как на сайте)
            duty_rub = cfr_rub * 0.1454
        elif age_range == "3_5":
            # Для электромобилей 3-5 лет - 14.21% от CFR (как на сайте)
            duty_rub = cfr_rub * 0.1421
        else:  # over_5
            # Для электромобилей старше 5 лет - ставка за л.с.
            if engine_cc <= 100:
                rate_per_hp = 180  # 180 ₽ за л.с.
            elif engine_cc <= 150:
                rate_per_hp = 299  # 299 ₽ за л.с.
            elif engine_cc <= 200:
                rate_per_hp = 1795  # 1,795 ₽ за л.с. (как на сайте)
            elif engine_cc <= 250:
                rate_per_hp = 1976  # 1,976 ₽ за л.с. (как на сайте)
            elif engine_cc <= 300:
                rate_per_hp = 1796.67  # 1,796.67 ₽ за л.с. (как на сайте)
            else:
                rate_per_hp = 1796.67  # 1,796.67 ₽ за л.с. (как на сайте)
            duty_rub = engine_cc * rate_per_hp
    elif age_range == "under_3":
        # Для авто моложе 3 лет - процентная ставка от CFR
        # Для бензина/дизеля - 51.01% от CFR (как на сайте)
        duty_rub = cfr_rub * 0.5101
    elif age_range == "3_5":
        # Для авто 3-5 лет - ставка за см³
        if engine_cc <= 1000:
            rate_per_cc = 180  # 180 ₽ за см³
        elif engine_cc <= 1500:
            rate_per_cc = 158.67  # 158.67 ₽ за см³ (как на сайте)
        elif engine_cc <= 1800:
            rate_per_cc = 220  # 220 ₽ за см³
        elif engine_cc <= 2300:
            rate_per_cc = 252  # 252 ₽ за см³
        elif engine_cc <= 2500:
            rate_per_cc = 280  # 280 ₽ за см³
        elif engine_cc <= 3000:
            rate_per_cc = 280  # 280 ₽ за см³ (как на сайте)
        else:
            rate_per_cc = 300  # 300 ₽ за см³
        duty_rub = engine_cc * rate_per_cc
    else:  # over_5
        # Для авто старше 5 лет - ставка за см³
        if engine_cc <= 1000:
            rate_per_cc = 280  # 280 ₽ за см³ (как на сайте)
        elif engine_cc <= 1500:
            rate_per_cc = 299  # 299 ₽ за см³
        elif engine_cc <= 1800:
            rate_per_cc = 220  # 220 ₽ за см³
        elif engine_cc <= 2300:
            rate_per_cc = 252  # 252 ₽ за см³
        elif engine_cc <= 2500:
            rate_per_cc = 280  # 280 ₽ за см³
        elif engine_cc <= 3000:
            rate_per_cc = 466.67  # 466.67 ₽ за см³ (как на сайте для авто старше 5 лет)
        else:
            rate_per_cc = 300  # 300 ₽ за см³
        duty_rub = engine_cc * rate_per_cc
    
    # Таможенный сбор
    if cfr_rub <= 200000:
        customs_fee_rub = 500
    elif cfr_rub <= 450000:
        customs_fee_rub = 1067
    elif cfr_rub <= 1200000:
        customs_fee_rub = 2000
    elif cfr_rub <= 2500000:
        customs_fee_rub = 11746
    elif cfr_rub <= 5000000:
        customs_fee_rub = 16524  # Исправлено: для CFR ~3,129,176 ₽ должно быть 16,524 ₽
    elif cfr_rub <= 10000000:
        customs_fee_rub = 20000
    else:
        customs_fee_rub = 30000
    
    # Утилизационный сбор
    if importer == "personal":
        if age_range in ["3_5", "over_5"]:
            util_fee_rub = 5200  # 5,200 ₽ для личного использования 3+ лет
        else:
            util_fee_rub = 3400  # 3,400 ₽ для личного использования моложе 3 лет
    else:  # commercial
        if age_range == "over_5":
            util_fee_rub = 460000  # 460,000 ₽ для коммерческого старше 5 лет (как на сайте)
        else:
            util_fee_rub = 1174000  # 1,174,000 ₽ для коммерческого 3-5 лет
    
    # Акциз
    if engine_type == "electric":
        if age_range == "under_3":
            # Для электромобилей моложе 3 лет - 955 ₽ за л.с. (как на сайте)
            excise_rub = engine_cc * 955
        elif age_range == "3_5":
            # Для электромобилей 3-5 лет - зависит от мощности
            if engine_cc <= 150:
                excise_rub = engine_cc * 61  # 61 ₽ за л.с.
            else:
                excise_rub = engine_cc * 583  # 583 ₽ за л.с.
        else:  # over_5
            excise_rub = 286500  # 286,500 ₽ для электромобилей старше 5 лет (как на сайте)
    else:
        excise_rub = 0  # 0 для обычных авто
    
    # НДС (20% от базы: CFR + пошлина + акциз)
    if engine_type == "electric":
        vat_base = cfr_rub + duty_rub + excise_rub
        vat_rub = vat_base * 0.20  # 20% (как на сайте)
    else:
        vat_rub = 0  # 0 для обычных авто
    
    # Брокерские услуги оформления, лаборатория СБКТС и ЭПТС
    broker_fee_rub = 100000  # 100,000 ₽
    
    # Итоговая стоимость (без комиссии компании и доставки на стоянку)
    total_rub = cfr_rub + duty_rub + customs_fee_rub + util_fee_rub + excise_rub + vat_rub + broker_fee_rub
    
    return {
        'price_krw': price_krw,
        'price_rub': price_rub,
        'freight_cost_krw': freight_cost_krw,
        'freight_cost_rub': freight_cost_rub,
        'cfr_rub': cfr_rub,
        'duty_rub': duty_rub,
        'customs_fee_rub': customs_fee_rub,
        'util_fee_rub': util_fee_rub,
        'excise_rub': excise_rub,
        'vat_rub': vat_rub,
        'broker_fee_rub': broker_fee_rub,
        'total_rub': total_rub,
        'additional_payments': duty_rub + customs_fee_rub + util_fee_rub + excise_rub + vat_rub + broker_fee_rub
    }


def main() -> None:
    """Запуск бота."""
    # Загружаем сохраненную статистику при запуске
    load_statistics()
    
    # Укажите здесь свой токен
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()
    
    # Добавляем обработчик для простой тестовой кнопки
    async def handle_test_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer("Тестовая кнопка работает!")
        await query.edit_message_text("✅ Простая тестовая кнопка работает!")
    
    application.add_handler(CallbackQueryHandler(handle_test_button, pattern="^test_button$"))
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(brand_model, pattern="^car_selection$"),
                CallbackQueryHandler(start_customs_calc, pattern="^customs_calc$"),
                CallbackQueryHandler(to_main_menu, pattern="^to_main_menu$")
            ],
            BRAND_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, brand_input),
                CallbackQueryHandler(to_main_menu, pattern="^to_main_menu$")
            ],
            MODEL_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, model_input),
                CallbackQueryHandler(to_main_menu, pattern="^to_main_menu$")
            ],
            YEAR_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, year_input),
                CallbackQueryHandler(to_main_menu, pattern="^to_main_menu$")
            ],

            BRAND_MODEL: [CallbackQueryHandler(brand_model)],
            FUEL_TYPE: [CallbackQueryHandler(fuel_type)],
            DRIVETRAIN: [CallbackQueryHandler(drivetrain)],
            MILEAGE: [
                CallbackQueryHandler(mileage),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mileage)
            ],
            COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, color)],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget)],
            CITY: [CallbackQueryHandler(city)],
            CUSTOMS_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, customs_price)],
            CUSTOMS_EXCHANGE_RATE: [
                CallbackQueryHandler(customs_exchange_rate),
                MessageHandler(filters.TEXT & ~filters.COMMAND, customs_exchange_rate_input)
            ],
            CUSTOMS_AGE: [CallbackQueryHandler(customs_age)],
            CUSTOMS_ENGINE_TYPE: [CallbackQueryHandler(customs_engine_type)],
            CUSTOMS_IMPORTER: [CallbackQueryHandler(customs_importer)],
            CUSTOMS_ENGINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, customs_engine)],
            CUSTOMS_CITY: [CallbackQueryHandler(customs_city)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
    )

    application.add_handler(conv_handler)
    
    # Добавляем отдельный обработчик команды start (работает всегда)
    application.add_handler(CommandHandler("start", start))
    
    # Добавляем обработчик команды restart для сброса состояния
    application.add_handler(CommandHandler("restart", start))
    
    # Добавляем обработчик команды help
    application.add_handler(CommandHandler("help", help_command))
    
    # Добавляем обработчик команды статистики (только для админа)
    application.add_handler(CommandHandler("stats", show_statistics))
    
    # Добавляем обработчик команды очистки статистики (только для админа)
    application.add_handler(CommandHandler("clear_stats", clear_statistics))
    
    # Добавляем отдельные обработчики для админских кнопок (работают независимо от состояния диалога)
    application.add_handler(CallbackQueryHandler(handle_admin_buttons, pattern="^(reply_to_|call_)"))
    
    # Добавляем обработчики для админских команд
    application.add_handler(CommandHandler("reply", reply_to_user))
    application.add_handler(CommandHandler("myid", get_my_id))
    application.add_handler(CommandHandler("test", test_admin_message))
    application.add_handler(CommandHandler("testsimple", test_simple_button))
    application.add_handler(CommandHandler("test_simple_notification", test_simple_notification))

    print("Бот запущен...")
    application.run_polling()


async def clear_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для очистки статистики (только для админа)."""
    # Проверяем, что команда от админа
    if update.effective_user.id != 493763260:  # TODO: Заменить на ваш ID
        await update.message.reply_text("❌ У вас нет прав для использования этой команды.")
        return
    
    global car_selection_requests, customs_calc_requests, total_users
    
    # Очищаем статистику
    car_selection_requests = []
    customs_calc_requests = []
    total_users = set()
    
    # Удаляем файл статистики
    try:
        if os.path.exists('bot_statistics.pkl'):
            os.remove('bot_statistics.pkl')
            await update.message.reply_text("✅ Статистика успешно очищена и файл удален.")
        else:
            await update.message.reply_text("✅ Статистика очищена (файл не найден).")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Статистика очищена, но ошибка при удалении файла: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help - показывает справку."""
    help_text = """
<b>🤖 Yumicar Bot - Справка</b>

<b>Основные команды:</b>
/start - Запустить бота и показать главное меню
/restart - Перезапустить бота и сбросить состояние
/help - Показать эту справку
/cancel - Отменить текущую операцию
/myid - Узнать свой Telegram ID
/test_simple_notification - Простой тест бота

<b>Функции бота:</b>
🚗 <b>Подбор автомобиля</b> - помощь в выборе автомобиля по параметрам
💰 <b>Калькулятор стоимости</b> - расчет стоимости ввоза из Кореи

<b>Для администраторов:</b>
/myid - Узнать свой ID в Telegram
/reply [ID] [текст] - Ответить клиенту
/stats - Просмотр статистики заявок
/test - Тест админских функций

<b>Поддержка:</b>
По всем вопросам обращайтесь к администратору.
"""
    
    await update.message.reply_text(help_text, parse_mode="HTML")


if __name__ == "__main__":
    main() 