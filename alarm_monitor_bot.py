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
# Замените на ваш TOKEN от @BotFather
TELEGRAM_TOKEN = "8974880543:AAFACeijxOvsMFijBPyHZvyOUx9SaJ_lnRM"

# Ваш Chat ID (можно получить от бота)
YOUR_CHAT_ID = None  # Будет установлен при первом старте

# Мониторируемые каналы (username без @)
MONITORED_CHANNELS = [
    "air_alert_ua",           # Національна служба з надзвичайних ситуацій
    "UAUnderAttackAlert",     # Alert про атаки
    "zsumy_ua",              # Сумская область
    "liveua24",              # Новини України
    "kievreal1",             # KievReal
    "monitorwarr"            # Monitor War
]

# Ключевые слова для поиска баллистических угроз на Киев
KEYWORDS = {
    "ballistic": ["балістична", "баллистич", "ballistic", "bal"],
    "cruise": ["крилата", "cruise", "крейсер"],
    "kyiv": ["киев", "київ", "kyiv", "kiyiv"],
    "threat": ["загроза", "угроза", "threat", "атака", "attack"]
}

# ============ ФУНКЦИИ ============

def is_threat_relevant(text: str) -> bool:
    """
    Проверяет, содержит ли сообщение информацию о баллистической угрозе на Киев
    """
    text_lower = text.lower()
    
    # Ищем баллистику или крылатые ракеты
    has_ballistic = any(word in text_lower for word in KEYWORDS["ballistic"] + KEYWORDS["cruise"])
    
    # Ищем упоминание Киева
    has_kyiv = any(word in text_lower for word in KEYWORDS["kyiv"])
    
    # Ищем слова об угрозе
    has_threat = any(word in text_lower for word in KEYWORDS["threat"])
    
    return has_ballistic and (has_kyiv or has_threat)

def extract_time_info(text: str) -> str:
    """
    Пытается найти информацию о времени угрозы в тексте
    """
    # Поиск времени вида HH:MM
    time_pattern = r'\d{1,2}:\d{2}'
    times = re.findall(time_pattern, text)
    return f" Время: {', '.join(set(times))}" if times else ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    global YOUR_CHAT_ID
    YOUR_CHAT_ID = update.effective_chat.id
    
    await update.message.reply_text(
        f"✅ Бот активирован!\n"
        f"ID вашего чата: {YOUR_CHAT_ID}\n\n"
        f"Команды:\n"
        f"/status - статус мониторинга\n"
        f"/channels - мониторируемые каналы\n"
        f"/stop - остановить бот"
    )
    logger.info(f"Бот запущен. Chat ID: {YOUR_CHAT_ID}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    status_text = (
        f"🔍 Мониторинг активен\n"
        f"📡 Мониторируется {len(MONITORED_CHANNELS)} каналов\n"
        f"🎯 Поиск: баллистических угроз на Киев\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await update.message.reply_text(status_text)

async def channels_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /channels"""
    channels_text = "📢 Мониторируемые каналы:\n\n"
    for i, channel in enumerate(MONITORED_CHANNELS, 1):
        channels_text += f"{i}. @{channel}\n"
    await update.message.reply_text(channels_text)

async def handle_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает сообщения из мониторируемых каналов
    """
    message = update.channel_post or update.message
    
    if not message or not message.text:
        return
    
    # Проверяем, из мониторируемого ли канала
    sender_username = None
    if message.chat.username:
        sender_username = message.chat.username
    
    # Если сообщение релевантно - отправляем уведомление
    if is_threat_relevant(message.text):
        # Формируем алерт
        time_info = extract_time_info(message.text)
        alert_message = (
            f"⚠️ АЛЕРТ: Баллистическая угроза на Киев!\n\n"
            f"📢 Источник: @{sender_username}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}{time_info}\n\n"
            f"📝 Сообщение:\n{message.text[:500]}"
        )
        
        # Отправляем в ваш чат если задан
        if YOUR_CHAT_ID:
            try:
                bot = Bot(token=TELEGRAM_TOKEN)
                await bot.send_message(
                    chat_id=YOUR_CHAT_ID,
                    text=alert_message,
                    parse_mode='HTML'
                )
                logger.info(f"Алерт отправлен: {sender_username}")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    """Главная функция"""
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("channels", channels_list))
    
    # Добавляем обработчик для сообщений из каналов
    application.add_handler(
        MessageHandler(filters.UPDATE_CHANNEL_POST, handle_channel_message)
    )
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Бот запущен и готов к работе...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
