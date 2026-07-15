import logging
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from datetime import datetime
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ КОНФИГУРАЦИЯ ============
TELEGRAM_TOKEN = "8974880543:AAFACeijxOvsMFijBPyHZvyOUx9SaJ_lnRM"
YOUR_CHAT_ID = None

# Мониторируемые каналы
MONITORED_CHANNELS = [
    "air_alert_ua",
    "UAUnderAttackAlert",
    "zsumy_ua",
    "liveua24",
    "kievreal1",
    "monitorwarr"
]

# Ключевые слова
KEYWORDS = {
    "ballistic": ["балістич", "баллистич", "ballistic", "bal", "мр-"],
    "cruise": ["крилата", "cruise", "крейсер", "х-101", "х101"],
    "kyiv": ["киев", "київ", "kyiv", "kiyiv", "столиц"],
    "threat": ["загроза", "угроза", "threat", "атака", "attack", "напрямок", "летять"]
}

# ============ ФУНКЦИИ ============

def is_threat_relevant(text: str) -> bool:
    """Проверяет, релевантно ли сообщение"""
    text_lower = text.lower()
    
    has_ballistic = any(word in text_lower for word in KEYWORDS["ballistic"] + KEYWORDS["cruise"])
    has_kyiv = any(word in text_lower for word in KEYWORDS["kyiv"])
    has_threat = any(word in text_lower for word in KEYWORDS["threat"])
    
    return has_ballistic and (has_kyiv or has_threat)

def extract_time_info(text: str) -> str:
    """Извлекает время из текста"""
    time_pattern = r'\d{1,2}:\d{2}'
    times = re.findall(time_pattern, text)
    return f" Час: {', '.join(set(times))}" if times else ""

# ============ ОБРАБОТЧИКИ ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    global YOUR_CHAT_ID
    YOUR_CHAT_ID = update.effective_chat.id
    
    await update.message.reply_text(
        f"✅ Бот активирован!\n"
        f"ID: {YOUR_CHAT_ID}\n\n"
        f"Команды:\n"
        f"/status - статус\n"
        f"/channels - каналы\n"
    )
    logger.info(f"Бот запущен. Chat ID: {YOUR_CHAT_ID}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    status_text = (
        f"🔍 Мониторинг активен\n"
        f"📡 Каналів: {len(MONITORED_CHANNELS)}\n"
        f"🎯 Поиск: баллистика на Киев\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    await update.message.reply_text(status_text)

async def channels_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /channels"""
    channels_text = "📢 Мониторируемые каналы:\n\n"
    for i, channel in enumerate(MONITORED_CHANNELS, 1):
        channels_text += f"{i}. @{channel}\n"
    await update.message.reply_text(channels_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех сообщений"""
    message = update.message
    
    if not message or not message.text:
        return
    
    # Проверяем если сообщение из чата (для других целей)
    if message.chat.type == "private":
        return
    
    # Проверяем если это из мониторируемого канала
    sender_username = message.chat.username
    if not sender_username or sender_username not in MONITORED_CHANNELS:
        return
    
    # Проверяем релевантность
    if is_threat_relevant(message.text):
        time_info = extract_time_info(message.text)
        alert_message = (
            f"⚠️ АЛЕРТ: Баллистическая угроза на Киев!\n\n"
            f"📢 Источник: @{sender_username}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}{time_info}\n\n"
            f"📝 Сообщение:\n{message.text[:400]}"
        )
        
        if YOUR_CHAT_ID:
            try:
                bot = Bot(token=TELEGRAM_TOKEN)
                await bot.send_message(
                    chat_id=YOUR_CHAT_ID,
                    text=alert_message
                )
                logger.info(f"✅ Алерт отправлен из @{sender_username}")
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(msg="Exception:", exc_info=context.error)

def main():
    """Главная функция"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("channels", channels_list))
    
    # Обработчик сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    logger.info("🚀 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
