import asyncio
import os
import logging
import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# --- Импорты для RAG ---
from gigachat import GigaChat
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain_community.llms import GigaChat as GigaChatLLM

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GIGA_KEY = os.getenv("GIGACHAT_API_KEY")
ADMIN_IDS = [int(os.getenv("ADMIN_ID", "0"))]

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# Глобальные переменные для базы знаний
vectorstore = None
qa_chain = None
embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🚆 **Привет! Я помощник по электропоезду ЭШ2**\n\n"
        "📄 **Как пользоваться:**\n"
        "• Отправьте мне PDF-файл с инструкцией\n"
        "• Я сохраню её в базу знаний\n"
        "• Задавайте любые вопросы — я найду ответ!\n\n"
        "⚠️ Если бот завис при обработке файла, отправьте его повторно.",
        parse_mode="Markdown"
    )

# --- ОБРАБОТЧИК ДОКУМЕНТОВ С ЗАЩИТОЙ ОТ ЗАВИСАНИЙ ---
@dp.message(lambda message: message.document)
async def handle_document(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Только администратор может загружать документы.")
        return

    if not message.document.file_name.endswith('.pdf'):
        await message.answer("❌ Поддерживаются только PDF-файлы.")
        return

    status_msg = await message.answer(f"📥 Получаю: {message.document.file_name}...")
    
    try:
        file = await bot.get_file(message.document.file_id)
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            await bot.download_file(file.file_path, tmp.name)
            tmp_path = tmp.name
        
        await status_msg.edit_text("🔄 Обрабатываю документ...")

        # --- Обработка документа ---
        loader = PyPDFLoader(tmp_path)
        documents = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents(documents)
        
        # --- Работа с базой знаний ---
        global vectorstore, qa_chain
        if vectorstore is None:
            vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory="/tmp/chroma_db")
        else:
            vectorstore.add_documents(chunks)
        
        # --- Инициализация GigaChat (ПРЯМО ЗДЕСЬ) ---
        # Это ключевой момент: пробуем подключиться к GigaChat прямо во время обработки файла.
        try:
            llm = GigaChatLLM(
                credentials=GIGA_KEY,
                scope="GIGACHAT_API_PERS",
                verify_ssl_certs=False,
                model="GigaChat"
            )
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                retriever=vectorstore.as_retriever(k=3),
                return_source_documents=True
            )
            await status_msg.edit_text(f"✅ **Документ добавлен!**\n📄 {message.document.file_name}\n📊 Разбит на {len(chunks)} фрагментов\n\n🤖 GigaChat готов к вопросам!")
        except Exception as giga_error:
            # Если GigaChat не подключился, сообщим об этом, но документ сохраним
            await status_msg.edit_text(f"⚠️ **Документ сохранен, но GigaChat не отвечает.**\n\nПроверьте API-ключ.\nОшибка: {str(giga_error)[:100]}")
            logging.error(f"GigaChat init error: {giga_error}")

        os.unlink(tmp_path)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Критическая ошибка при обработке: {e}")
        logging.error(f"Document processing error: {e}")

# --- ОБРАБОТЧИК ВОПРОСОВ С ЗАЩИТОЙ ---
@dp.message()
async def ask_question(message: types.Message):
    if qa_chain is None:
        await message.answer(
            "📭 **База знаний пуста или GigaChat не настроен.**\n\n"
            "1. Убедитесь, что вы загрузили PDF-файл.\n"
            "2. Проверьте, что API-ключ GigaChat введен верно (команда `/set_key`).\n"
            "3. Попробуйте загрузить файл еще раз."
        )
        return
    
    thinking_msg = await message.answer("🤔 Ищу ответ в инструкциях...")
    
    try:
        result = qa_chain.invoke({"query": message.text})
        answer = result["result"]
        sources = result.get("source_documents", [])
        
        response = f"**Ответ:**\n{answer}\n\n"
        if sources:
            response += "**Источники:**\n"
            seen = set()
            for doc in sources[:3]:
                source_name = doc.metadata.get('source', 'документ').split('/')[-1]
                if source_name not in seen:
                    seen.add(source_name)
                    response += f"📄 {source_name}\n"
        
        await thinking_msg.edit_text(response, parse_mode="Markdown")
        
    except Exception as e:
        await thinking_msg.edit_text(f"❌ Ошибка при поиске ответа: {e}\n\nПопробуйте перезагрузить документ командой `/start`.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
