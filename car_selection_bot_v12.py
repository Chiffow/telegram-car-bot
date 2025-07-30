import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Filters,
)

# Включаем логирование, чтобы видеть ошибки
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Данные по автомобилям ---
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


def start(update: Update, context):
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
    
    update.message.reply_text(
        "Здравствуйте! Я помогу вам подобрать автомобиль.\n\n"
        "Для отмены в любой момент отправьте /cancel.\n\n"
        "Выберите марку автомобиля:",
        reply_markup=reply_markup,
    )
    return BRAND


def navigate_brands(update: Update, context):
    """Обрабатывает навигацию по маркам."""
    query = update.callback_query
    query.answer()

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
    
    query.edit_message_text(
        "Выберите марку автомобиля:",
        reply_markup=reply_markup,
    )
    return BRAND


def brand_selection(update: Update, context):
    """После выбора марки показывает модели."""
    query = update.callback_query
    query.answer()

    selected_brand = query.data.split("_")[1]
    context.user_data["brand"] = selected_brand
    logger.info("Выбрана марка: %s", selected_brand)
    
    models = CAR_DATA.get(selected_brand, [])
    context.user_data["models"] = models
    context.user_data["page"] = 0

    keyboard = []
    page_models = models[0:8]
    for model in page_models:
        keyboard.append(InlineKeyboardButton(model, callback_data=f"model_{model}"))
    
    footer_buttons = []
    if len(models) > 8:
         footer_buttons.append(InlineKeyboardButton("➡️ Далее", callback_data="nav_models_next"))

    header_button = InlineKeyboardButton("<< Назад к маркам", callback_data="back_to_brands")

    reply_markup = InlineKeyboardMarkup(build_menu(keyboard, n_cols=2, header_buttons=header_button, footer_buttons=footer_buttons))

    query.edit_message_text(
        f"Отлично! Теперь выберите модель **{selected_brand}**:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return MODEL


def model_selection(update: Update, context):
    """Сохраняет модель и запрашивает год."""
    query = update.callback_query
    query.answer()

    selected_model = query.data.split("_")[1]
    context.user_data["model"] = selected_model
    brand = context.user_data.get('brand')
    logger.info("Выбрана модель: %s %s", brand, selected_model)

    query.edit_message_text(
        f"Вы выбрали: **{brand} {selected_model}**.\n\n"
        "Теперь укажите год выпуска:"
    , parse_mode="Markdown")
    return YEAR


def year(update: Update, context):
    """Сохраняет год и запрашивает объем двигателя."""
    user_text = update.message.text
    context.user_data["year"] = user_text
    logger.info("Год выпуска: %s", user_text)

    update.message.reply_text("Принято. Укажите объем двигателя (например, 2.5):")
    return ENGINE_VOLUME


def engine_volume(update: Update, context):
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

    update.message.reply_text("Понял. Выберите вид топлива:", reply_markup=reply_markup)
    return FUEL_TYPE


def fuel_type(update: Update, context):
    """Сохраняет тип топлива и предлагает выбрать привод."""
    query = update.callback_query
    query.answer()
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

    query.edit_message_text(
        text="Отлично. Теперь выберите тип привода:", reply_markup=reply_markup
    )
    return DRIVETRAIN


def drivetrain(update: Update, context):
    """Сохраняет тип привода и запрашивает пробег."""
    query = update.callback_query
    query.answer()
    context.user_data["drivetrain"] = query.data
    logger.info("Привод: %s", query.data)

    query.edit_message_text(text="Хорошо. Укажите желаемый максимальный пробег (в км):")
    return MILEAGE


def mileage(update: Update, context):
    """Сохраняет пробег и запрашивает цвет."""
    user_text = update.message.text
    context.user_data["mileage"] = user_text
    logger.info("Пробег: %s", user_text)

    update.message.reply_text("Какой цвет кузова и салона вас интересует?")
    return COLOR


def color(update: Update, context):
    """Сохраняет цвет и запрашивает бюджет."""
    user_text = update.message.text
    context.user_data["color"] = user_text
    logger.info("Цвет: %s", user_text)

    update.message.reply_text("Почти готово. На какую сумму вы рассчитываете?")
    return BUDGET


def budget(update: Update, context):
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

    update.message.reply_text(
        text="Последний шаг. Выберите город доставки:", reply_markup=reply_markup
    )
    return CITY


def city(update: Update, context):
    """Сохраняет город и выводит итоговую информацию."""
    query = update.callback_query
    query.answer()
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
    query.edit_message_text(text=summary, parse_mode="HTML")
    
    # Очищаем данные пользователя после завершения
    context.user_data.clear()
    
    # Завершаем диалог
    return ConversationHandler.END


def cancel(update: Update, context):
    """Отменяет и завершает диалог."""
    update.message.reply_text("Действие отменено. Чтобы начать заново, введите /start.")
    context.user_data.clear()
    return ConversationHandler.END


def main():
    """Запуск бота."""
    # Получаем токен из переменных окружения
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    try:
        updater = Updater(token=token, use_context=True)

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                BRAND: [
                    CallbackQueryHandler(brand_selection, pattern="^brand_"),
                    CallbackQueryHandler(navigate_brands, pattern="^nav_brands_"),
                ],
                MODEL: [
                    CallbackQueryHandler(model_selection, pattern="^model_"),
                    CallbackQueryHandler(navigate_brands, pattern="^nav_models_"),
                    CallbackQueryHandler(start, pattern="^back_to_brands$"),
                ],
                YEAR: [MessageHandler(Filters.text & ~Filters.command, year)],
                ENGINE_VOLUME: [MessageHandler(Filters.text & ~Filters.command, engine_volume)],
                FUEL_TYPE: [CallbackQueryHandler(fuel_type)],
                DRIVETRAIN: [CallbackQueryHandler(drivetrain)],
                MILEAGE: [MessageHandler(Filters.text & ~Filters.command, mileage)],
                COLOR: [MessageHandler(Filters.text & ~Filters.command, color)],
                BUDGET: [MessageHandler(Filters.text & ~Filters.command, budget)],
                CITY: [CallbackQueryHandler(city)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        updater.dispatcher.add_handler(conv_handler)

        print("Бот запущен...")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        print(f"Ошибка: {e}")
        return


if __name__ == "__main__":
    main() 