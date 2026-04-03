import asyncio
import os
import logging
import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# GigaChat
from gigachat import GigaChat

# LangChain (облегчённая версия)
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

# Глобальные переменные
vectorstore = None
qa_chain = None

# Эмбеддинги (лёгкая модель)
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🚆 **Привет! Я помощник по электропоезду ЭШ2**\n\n"
        "Я работаю с документацией и отвечаю на вопросы.\n\n"
        "📄 **Как пользоваться:**\n"
        "• Отправьте мне PDF-файл с инструкцией\n"
        "• Я сохраню её в базу знаний\n"
        "• Задавайте любые вопросы — я найду ответ!\n\n"
        "📖 /help — помощь\n"
        "📊 /stats — статистика",
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "📖 **Помощь**\n\n"
        "1. Отправьте PDF с инструкцией по электропоезду\n"
        "2. Я обработаю и сохраню документ\n"
        "3. Задавайте вопросы — я ищу ответ в базе знаний\n\n"
        "Примеры:\n"
        "• Какое давление в тормозной системе ЭШ2?\n"
        "• Как проверить уровень масла?\n"
        "• Что делать при срабатывании защиты БВ?",
        parse_mode="Markdown"
    )

@dp.message(Command("stats"))
async def stats_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Только администратор.")
        return
    
    if vectorstore is None:
        await message.answer("📭 База знаний пуста. Загрузите PDF-документы.")
    else:
        await message.answer("✅ База знаний активна. Можно задавать вопросы!")

@dp.message(lambda message: message.document)
async def handle_document(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Только администратор может загружать документы.")
        return
    
    if not message.document.file_name.endswith('.pdf'):
        await message.answer("❌ Поддерживаются только PDF-файлы.")
        return
    
    await message.answer(f"📥 Получаю: {message.document.file_name}...")
    
    try:
        file = await bot.get_file(message.document.file_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            await bot.download_file(file.file_path, tmp.name)
            tmp_path = tmp.name
        
        await message.answer("🔄 Обрабатываю документ...")
        
        # Загрузка PDF
        loader = PyPDFLoader(tmp_path)
        documents = loader.load()
        
        # Разбивка на части
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents(documents)
        
        # Добавление в базу
        global vectorstore, qa_chain
        if vectorstore is None:
            vectorstore = Chroma.from_documents(
                chunks, 
                embeddings, 
                persist_directory="/tmp/chroma_db"
            )
        else:
            vectorstore.add_documents(chunks)
        
        # Создание RAG цепочки с GigaChat
        llm = GigaChatLLM(
            credentials=GIGA_KEY,
            verify_ssl_certs=False,
            model="GigaChat:latest"
        )
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=vectorstore.as_retriever(k=3),
            return_source_documents=True
        )
        
        await message.answer(
            f"✅ **Документ добавлен!**\n"
            f"📄 {message.document.file_name}\n"
            f"📊 Разбит на {len(chunks)} фрагментов\n\n"
            f"Теперь задавайте вопросы!",
            parse_mode="Markdown"
        )
        
        os.unlink(tmp_path)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message()
async def ask_question(message: types.Message):
    if qa_chain is None:
        await message.answer(
            "📭 База знаний пуста.\n"
            "Сначала отправьте PDF-документ с инструкцией."
        )
        return
    
    await message.answer("🤔 Ищу ответ...")
    
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
        
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🤖 Бот с GigaChat запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
