import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Включаем логирование, чтобы видеть ошибки
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Данные по автомобилям ---
# Вы можете легко добавлять сюда новые марки и модели
CAR_DATA = {
    "Audi": ["A3", "A4", "A6", "Q5", "Q7"],
    "BMW": ["3-series", "5-series", "X3", "X5", "X6"],
    "Ford": ["Focus", "Mondeo", "Kuga", "Explorer"],
    "Honda": ["Accord", "Civic", "CR-V"],
    "Hyundai": ["Solaris", "Elantra", "Sonata", "Tucson"],
    "Kia": ["Rio", "Ceed", "Optima", "Sportage"],
    "LADA (ВАЗ)": ["Granta", "Vesta", "Largus", "Niva"],
    "Lexus": ["ES", "GX", "LX", "RX"],
    "Mazda": ["3", "6", "CX-5", "CX-9"],
    "Mercedes-Benz": ["C-Class", "E-Class", "S-Class", "GLC", "GLE"],
    "Mitsubishi": ["Lancer", "Outlander", "Pajero Sport"],
    "Nissan": ["Almera", "Qashqai", "X-Trail", "Murano"],
    "Renault": ["Logan", "Duster", "Kaptur", "Arkana"],
    "Skoda": ["Octavia", "Rapid", "Kodiaq", "Superb"],
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser Prado"],
    "Volkswagen": ["Polo", "Jetta", "Passat", "Tiguan"],
}

# Определяем состояния для нашего диалога
(
    BRAND,
    MODEL,
    YEAR,
    ENGINE_VOLUME,
    FUEL_TYPE,
    DRIVETRAIN,
    MILEAGE,
    COLOR,
    BUDGET,
    CITY,
) = range(10)


def build_menu(buttons: list, n_cols: int, header_buttons=None, footer_buttons=None):
    """Создает меню из кнопок."""
    menu = [buttons[i : i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог и показывает первые марки авто."""
    context.user_data.clear()
    
    brands = sorted(CAR_DATA.keys())
    context.user_data["brands"] = brands
    context.user_data["page"] = 0
    
    keyboard = []
    page_brands = brands[0:8] # 8 кнопок на странице
    for brand in page_brands:
        keyboard.append(InlineKeyboardButton(brand, callback_data=f"brand_{brand}"))

    footer_buttons = [
        InlineKeyboardButton("➡️ Далее", callback_data="nav_brands_next"),
    ]
    
    reply_markup = InlineKeyboardMarkup(build_menu(keyboard, n_cols=2, footer_buttons=footer_buttons))
    
    await update.message.reply_text(
        "Здравствуйте! Я помогу вам подобрать автомобиль.\n\n"
        "Для отмены в любой момент отправьте /cancel.\n\n"
        "Выберите марку автомобиля:",
        reply_markup=reply_markup,
    )
    return BRAND


async def navigate_brands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает навигацию по маркам."""
    query = update.callback_query
    await query.answer()

    page = context.user_data.get("page", 0)
    brands = context.user_data.get("brands", [])
    
    if "next" in query.data:
        page += 1
    elif "prev" in query.data:
        page -= 1
        
    context.user_data["page"] = page
    
    start_offset = page * 8
    end_offset = start_offset + 8
    page_brands = brands[start_offset:end_offset]

    keyboard = []
    for brand in page_brands:
        keyboard.append(InlineKeyboardButton(brand, callback_data=f"brand_{brand}"))

    footer_buttons = []
    if page > 0:
        footer_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="nav_brands_prev"))
    if end_offset < len(brands):
        footer_buttons.append(InlineKeyboardButton("➡️ Далее", callback_data="nav_brands_next"))

    reply_markup = InlineKeyboardMarkup(build_menu(keyboard, n_cols=2, footer_buttons=footer_buttons))
    
    await query.edit_message_text(
        "Выберите марку автомобиля:",
        reply_markup=reply_markup,
    )
    return BRAND


async def brand_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """После выбора марки показывает модели."""
    query = update.callback_query
    await query.answer()

    selected_brand = query.data.split("_")[1]
    context.user_data["brand"] = selected_brand
    logger.info("Выбрана марка: %s", selected_brand)
    
    models = CAR_DATA.get(selected_brand, [])
    context.user_data["models"] = models
    context.user_data["page"] = 0 # Сбрасываем пагинацию для моделей

    keyboard = []
    page_models = models[0:8]
    for model in page_models:
        keyboard.append(InlineKeyboardButton(model, callback_data=f"model_{model}"))
    
    footer_buttons = []
    if len(models) > 8:
         footer_buttons.append(InlineKeyboardButton("➡️ Далее", callback_data="nav_models_next"))

    # Кнопка назад к выбору марки
    header_button = InlineKeyboardButton("<< Назад к маркам", callback_data="back_to_brands")

    reply_markup = InlineKeyboardMarkup(build_menu(keyboard, n_cols=2, header_buttons=header_button, footer_buttons=footer_buttons))

    await query.edit_message_text(
        f"Отлично! Теперь выберите модель **{selected_brand}**:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return MODEL

async def navigate_models(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает навигацию по моделям."""
    query = update.callback_query
    await query.answer()

    page = context.user_data.get("page", 0)
    brand = context.user_data.get("brand")
    models = context.user_data.get("models", [])
    
    if "next" in query.data:
        page += 1
    elif "prev" in query.data:
        page -= 1
        
    context.user_data["page"] = page
    
    start_offset = page * 8
    end_offset = start_offset + 8
    page_models = models[start_offset:end_offset]

    keyboard = []
    for model in page_models:
        keyboard.append(InlineKeyboardButton(model, callback_data=f"model_{model}"))

    footer_buttons = []
    if page > 0:
        footer_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="nav_models_prev"))
    if end_offset < len(models):
        footer_buttons.append(InlineKeyboardButton("➡️ Далее", callback_data="nav_models_next"))
    
    header_button = InlineKeyboardButton("<< Назад к маркам", callback_data="back_to_brands")

    reply_markup = InlineKeyboardMarkup(build_menu(keyboard, n_cols=2, header_buttons=header_button, footer_buttons=footer_buttons))
    
    await query.edit_message_text(
        f"Выберите модель **{brand}**:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return MODEL


async def model_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет модель и запрашивает год."""
    query = update.callback_query
    await query.answer()

    selected_model = query.data.split("_")[1]
    context.user_data["model"] = selected_model
    brand = context.user_data.get('brand')
    logger.info("Выбрана модель: %s %s", brand, selected_model)

    await query.edit_message_text(
        f"Вы выбрали: **{brand} {selected_model}**.\n\n"
        "Теперь укажите год выпуска:"
    , parse_mode="Markdown")
    return YEAR


async def year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет год и запрашивает объем двигателя."""
    user_text = update.message.text
    context.user_data["year"] = user_text
    logger.info("Год выпуска: %s", user_text)

    await update.message.reply_text("Принято. Укажите объем двигателя (например, 2.5):")
    return ENGINE_VOLUME


async def engine_volume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет объем двигателя и предлагает выбрать тип топлива."""
    user_text = update.message.text
    context.user_data["engine_volume"] = user_text
    logger.info("Объем двигателя: %s", user_text)

    keyboard = [
        [
            InlineKeyboardButton("Бензин", callback_data="Бензин"),
            InlineKeyboardButton("Дизель", callback_data="Дизель"),
            InlineKeyboardButton("Электро", callback_data="Электро"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Понял. Выберите вид топлива:", reply_markup=reply_markup)
    return FUEL_TYPE


async def fuel_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет тип топлива и предлагает выбрать привод."""
    query = update.callback_query
    await query.answer()
    context.user_data["fuel_type"] = query.data
    logger.info("Тип топлива: %s", query.data)

    keyboard = [
        [
            InlineKeyboardButton("Передний", callback_data="Передний"),
            InlineKeyboardButton("Задний", callback_data="Задний"),
            InlineKeyboardButton("Полный", callback_data="Полный (4WD)"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Отлично. Теперь выберите тип привода:", reply_markup=reply_markup
    )
    return DRIVETRAIN


async def drivetrain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет тип привода и запрашивает пробег."""
    query = update.callback_query
    await query.answer()
    context.user_data["drivetrain"] = query.data
    logger.info("Привод: %s", query.data)

    await query.edit_message_text(text="Хорошо. Укажите желаемый максимальный пробег (в км):")
    return MILEAGE


async def mileage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет пробег и запрашивает цвет."""
    user_text = update.message.text
    context.user_data["mileage"] = user_text
    logger.info("Пробег: %s", user_text)

    await update.message.reply_text("Какой цвет кузова и салона вас интересует?")
    return COLOR


async def color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет цвет и запрашивает бюджет."""
    user_text = update.message.text
    context.user_data["color"] = user_text
    logger.info("Цвет: %s", user_text)

    await update.message.reply_text("Почти готово. На какую сумму вы рассчитываете?")
    return BUDGET


async def budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет бюджет и предлагает выбрать город доставки."""
    user_text = update.message.text
    context.user_data["budget"] = user_text
    logger.info("Бюджет: %s", user_text)

    keyboard = [
        [
            InlineKeyboardButton("Москва", callback_data="Москва"),
            InlineKeyboardButton("Санкт-Петербург", callback_data="Санкт-Петербург"),
        ],
        [
            InlineKeyboardButton("Новосибирск", callback_data="Новосибирск"),
            InlineKeyboardButton("Екатеринбург", callback_data="Екатеринбург"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text="Последний шаг. Выберите город доставки:", reply_markup=reply_markup
    )
    return CITY


async def city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет город и выводит итоговую информацию."""
    query = update.callback_query
    await query.answer()
    context.user_data["city"] = query.data
    logger.info("Город: %s", query.data)

    # Формируем итоговое сообщение
    data = context.user_data
    summary = f"""
✅ **Ваш запрос на подбор автомобиля сформирован:**

- **Автомобиль:** {data.get('brand', 'не указано')} {data.get('model', 'не указано')}
- **Год выпуска:** {data.get('year', 'не указан')}
- **Объем двигателя:** {data.get('engine_volume', 'не указан')}
- **Топливо:** {data.get('fuel_type', 'не указано')}
- **Привод:** {data.get('drivetrain', 'не указан')}
- **Пробег до:** {data.get('mileage', 'не указано')} км
- **Цвет:** {data.get('color', 'не указан')}
- **Бюджет:** {data.get('budget', 'не указан')}
- **Город доставки:** {data.get('city', 'не указан')}

Спасибо! Наши специалисты скоро с вами свяжутся.
    """
    await query.edit_message_text(text=summary, parse_mode="HTML")
    
    # Очищаем данные пользователя после завершения
    context.user_data.clear()
    
    # Завершаем диалог
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет и завершает диалог."""
    await update.message.reply_text("Действие отменено. Чтобы начать заново, введите /start.")
    context.user_data.clear()
    return ConversationHandler.END


def main() -> None:
    """Запуск бота."""
    # Получаем токен из переменных окружения
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    try:
        application = Application.builder().token(token).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                BRAND: [
                    CallbackQueryHandler(brand_selection, pattern="^brand_"),
                    CallbackQueryHandler(navigate_brands, pattern="^nav_brands_"),
                ],
                MODEL: [
                    CallbackQueryHandler(model_selection, pattern="^model_"),
                    CallbackQueryHandler(navigate_models, pattern="^nav_models_"),
                    CallbackQueryHandler(start, pattern="^back_to_brands$"), # Возврат к маркам
                ],
                YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, year)],
                ENGINE_VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, engine_volume)],
                FUEL_TYPE: [CallbackQueryHandler(fuel_type)],
                DRIVETRAIN: [CallbackQueryHandler(drivetrain)],
                MILEAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, mileage)],
                COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, color)],
                BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget)],
                CITY: [CallbackQueryHandler(city)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        application.add_handler(conv_handler)

        print("Бот запущен...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        print(f"Ошибка: {e}")
        return


if __name__ == "__main__":
    main() 