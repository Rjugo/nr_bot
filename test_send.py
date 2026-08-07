import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

load_dotenv()


async def test_all_chats():
    # Настройка прокси
    proxy_url = "socks5://127.0.0.1:12334"
    session = AiohttpSession(proxy=proxy_url)
    bot = Bot(token=os.getenv('BOT_TOKEN'), session=session)

    # Все тестовые чаты
    chats = [
        {"id": -5593170191, "name": "NR_test1"},
        {"id": -5386995868, "name": "NR_test2"},
        {"id": -5593622275, "name": "NR_test3"}
    ]

    print("🔍 Проверяем чаты...")

    for chat in chats:
        try:
            # Пробуем получить информацию о чате
            chat_info = await bot.get_chat(chat["id"])
            print(f"✅ Чат {chat['name']} найден: {chat_info.title}")

            # Пробуем отправить сообщение
            await bot.send_message(
                chat["id"],
                f"✅ Тестовое сообщение для чата {chat['name']} (ID: {chat['id']})\n\nЕсли вы это видите — бот работает!"
            )
            print(f"✅ Сообщение отправлено в {chat['name']}")

        except Exception as e:
            print(f"❌ Ошибка с чатом {chat['name']} (ID: {chat['id']}): {e}")

    await bot.session.close()


asyncio.run(test_all_chats())