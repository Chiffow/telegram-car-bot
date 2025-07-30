import sys
import os

# Патч для удаления импорта imghdr из python-telegram-bot
def patch_telegram():
    try:
        import telegram.files.inputfile
        # Заменяем импорт imghdr на пустую функцию
        if hasattr(telegram.files.inputfile, 'imghdr'):
            delattr(telegram.files.inputfile, 'imghdr')
    except:
        pass

# Применяем патч
patch_telegram() 