#!/usr/bin/env python3
"""
Простой и надёжный Telegram-бот на Grok (xAI API).
"""

import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

# Загружаем переменные из .env
load_dotenv()

# ====================== НАСТРОЙКИ ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
XAI_API_KEY = os.getenv("XAI_API_KEY")

# Модель Grok (можно менять)
# Популярные: "grok-4", "grok-4-fast", "grok-3" и т.д.
GROK_MODEL = os.getenv("GROK_MODEL", "grok-4")

# Системный промпт — характер бота
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Ты Grok — полезный, прямой и немного с юмором ИИ от xAI. "
    "Отвечай на русском, если пользователь пишет на русском. "
    "Будь конкретным и полезным."
)

# Максимум сообщений в истории (чтобы не раздувать контекст)
MAX_HISTORY = 20
# =======================================================

# Проверка ключей
if not TELEGRAM_TOKEN or not XAI_API_KEY:
    raise ValueError(
        "Не найдены TELEGRAM_TOKEN или XAI_API_KEY.\n"
        "Создай файл .env и добавь туда ключи (см. README)."
    )

# Клиент xAI (OpenAI-совместимый)
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
)

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Хранилище истории диалогов (в памяти)
# Для продакшена лучше заменить на Redis / базу
user_histories: dict[int, list] = {}


def get_history(user_id: int) -> list:
    if user_id not in user_histories:
        user_histories[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    return user_histories[user_id]


def add_to_history(user_id: int, role: str, content: str):
    history = get_history(user_id)
    history.append({"role": role, "content": content})

    # Обрезаем старые сообщения (оставляем system + последние)
    if len(history) > MAX_HISTORY + 1:
        # Оставляем system и последние MAX_HISTORY сообщений
        user_histories[user_id] = [history[0]] + history[-(MAX_HISTORY):]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n\n"
        "Я бот на базе Grok от xAI.\n"
        "Просто напиши мне что угодно.\n\n"
        "Команды:\n"
        "/start — начать заново\n"
        "/clear — очистить историю диалога\n"
        "/model — показать текущую модель"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить историю"""
    user_id = update.effective_user.id
    user_histories[user_id] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    await update.message.reply_text("История диалога очищена.")


async def model_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать модель"""
    await update.message.reply_text(f"Текущая модель: `{GROK_MODEL}`", parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обычных сообщений"""
    user_id = update.effective_user.id
    user_text = update.message.text

    if not user_text:
        return

    # Показываем, что бот печатает
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        # Добавляем сообщение пользователя в историю
        add_to_history(user_id, "user", user_text)

        # Запрос к Grok
        response = client.chat.completions.create(
            model=GROK_MODEL,
            messages=get_history(user_id),
            temperature=0.7,
        )

        answer = response.choices[0].message.content

        # Сохраняем ответ в историю
        add_to_history(user_id, "assistant", answer)

        # Отправляем ответ
        await update.message.reply_text(answer)

    except Exception as e:
        logger.error(f"Ошибка при запросе к Grok: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обращении к Grok.\n"
            "Проверь API-ключ и лимиты."
        )


def main():
    """Запуск бота"""
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("model", model_info))

    # Обычные сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
