import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Получаем токен
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

# Настройка бота
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Список администраторов (только эти ID могут загружать файлы)
ADMIN_IDS = [int(os.getenv("ADMIN_ID", "0"))]

# Команда /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🚆 **Привет! Я помощник по электропоезду ЭШ2**\n\n"
        "Я работаю с документацией и отвечаю на вопросы.\n\n"
        "📄 **Как пользоваться:**\n"
        "• Отправьте мне PDF-файл с инструкцией\n"
        "• После загрузки задавайте вопросы\n\n"
        "📖 **Команды:**\n"
        "/start — приветствие\n"
        "/help — помощь\n"
        "/stats — статистика базы знаний\n\n"
        "Готов помочь!",
        parse_mode="Markdown"
    )

# Команда /help
@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "📖 **Помощь**\n\n"
        "1. Отправьте мне PDF-файл с инструкцией по электропоезду\n"
        "2. Я сохраню его в базу знаний\n"
        "3. Задавайте вопросы — я найду ответ в документах\n\n"
        "Примеры вопросов:\n"
        "• Какое давление в тормозной магистрали?\n"
        "• Как проверить уровень масла?\n"
        "• Что делать при срабатывании защиты БВ?",
        parse_mode="Markdown"
    )

# Команда /stats (только для администратора)
@dp.message(Command("stats"))
async def stats_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Только администратор может смотреть статистику.")
        return
    
    await message.answer(
        "📊 **Статистика**\n\n"
        "База знаний: активна\n"
        "Документов: (скоро будет добавлено)\n\n"
        "Нейросеть: GigaChat",
        parse_mode="Markdown"
    )

# Обработка файлов (только для администратора)
@dp.message(lambda message: message.document)
async def handle_document(message: types.Message):
    # Проверка, что пользователь — администратор
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Только администратор может загружать документы.")
        return
    
    # Проверка, что файл PDF
    if not message.document.file_name.endswith('.pdf'):
        await message.answer("❌ Поддерживаются только PDF-файлы.")
        return
    
    await message.answer(f"📥 Получаю файл: {message.document.file_name}...")
    
    try:
        # Скачиваем файл
        file = await bot.get_file(message.document.file_id)
        file_path = f"/tmp/{message.document.file_name}"
        await bot.download_file(file.file_path, file_path)
        
        # Здесь будет обработка файла (пока просто заглушка)
        await message.answer(
            f"✅ **Файл получен:** {message.document.file_name}\n"
            f"📄 Размер: {message.document.file_size} байт\n\n"
            "⚠️ Полноценная обработка документов настраивается.\n"
            "Скоро я смогу отвечать на вопросы по этому документу!",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке: {e}")

# Обработка текстовых сообщений (вопросы)
@dp.message()
async def answer_question(message: types.Message):
    # Пока простая заглушка
    await message.answer(
        f"📚 **Ваш вопрос:**\n{message.text}\n\n"
        "⚠️ Полноценная работа с документами настраивается.\n"
        "Скоро я смогу искать ответы в ваших инструкциях!\n\n"
        "А пока отправьте /help для списка команд.",
        parse_mode="Markdown"
    )

# Запуск бота
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🤖 Бот запущен и работает!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())