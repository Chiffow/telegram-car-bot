import sys
import types

# Создаем фиктивный модуль imghdr и добавляем его в sys.modules ДО импорта telegram
imghdr = types.ModuleType('imghdr')
sys.modules['imghdr'] = imghdr

# Добавляем необходимые функции
def what(file, h=None):
    return None

imghdr.what = what

print("Фиктивный модуль imghdr создан успешно!") 