import logging
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from datetime import datetime, timedelta
import sqlite3
import json
import re
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('alarm_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============ КОНФИГУРАЦИЯ ============
TELEGRAM_TOKEN = "8974880543:AAFACeijxOvsMFijBPyHZvyOUx9SaJ_lnRM"
YOUR_CHAT_ID = None
DATABASE_FILE = "alarm_history.db"

# Мониторируемые каналы
MONITORED_CHANNELS = {
    "air_alert_ua": "🚨 Národní služba",
    "UAUnderAttackAlert": "🎯 Alert про атаки",
    "zsumy_ua": "🗺️ Сумська область",
    "liveua24": "📰 Новини України",
    "mvs_official": "🚔 МВС України",
    "unian": "📻 УНІАН",
    "kievreal1": "🔴 KievReal",
    "monitorwarr": "📍 Monitor War"
}

# Ключевые слова
KEYWORDS = {
    "ballistic": ["балістич", "баллистич", "ballistic", "bal", "мр-"],
    "cruise": ["крилата", "cruise", "крейсер", "х-101", "х101"],
    "kyiv": ["киев", "київ", "kyiv", "kiyiv", "столиц"],
    "threat": ["загроза", "угроза", "threat", "атака", "attack", "напрямок", "направлен", "летят"]
}

# ============ БАЗА ДАННЫХ ============

def init_database():
    """Инициализирует базу данных"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            channel TEXT,
            message TEXT,
            threat_type TEXT,
            region TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def save_alert(channel: str, message: str, threat_type: str, region: str = "Киев"):
    """Сохраняет алерт в базу данных"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (channel, message, threat_type, region)
            VALUES (?, ?, ?, ?)
        ''', (channel, message[:500], threat_type, region))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка при сохранении алерта: {e}")

def get_alerts_stats(hours: int = 24) -> dict:
    """Получает статистику алертов за последние N часов"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        time_threshold = datetime.now() - timedelta(hours=hours)
        
        cursor.execute('''
            SELECT threat_type, COUNT(*) as count, region
            FROM alerts
            WHERE timestamp > ?
            GROUP BY threat_type, region
        ''', (time_threshold,))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return []

# ============ ФУНКЦИИ АНАЛИЗА ============

def detect_threat_type(text: str) -> str:
    """Определяет тип угрозы"""
    text_lower = text.lower()
    
    if any(word in text_lower for word in KEYWORDS["ballistic"]):
        if any(word in text_lower for word in ["мр-300", "мр-400", "кинжал"]):
            return "🎯 Баллистическая ракета (Kinzhal/OTRK)"
        return "🎯 Баллистическая ракета"
    
    if any(word in text_lower for word in KEYWORDS["cruise"]):
        if "х-101" in text_lower or "х101" in text_lower:
            return "➡️ Крылатая ракета (Х-101)"
        if "х-47" in text_lower or "х47" in text_lower:
            return "➡️ Крылатая ракета (Х-47)"
        return "➡️ Крылатая ракета"
    
    return "⚠️ Воздушная угроза"

def extract_detailed_info(text: str) -> dict:
    """Извлекает подробную информацию из сообщения"""
    info = {
        "times": [],
        "directions": [],
        "coordinates": []
    }
    
    # Время
    time_pattern = r'(\d{1,2}[:.]\d{2})'
    info["times"] = re.findall(time_pattern, text)
    
    # Направления
    directions = ["північний", "південний", "східний", "західний", 
                  "norte", "sur", "este", "oeste", "north", "south", "east", "west"]
    for direction in directions:
        if direction in text.lower():
            info["directions"].append(direction)
    
    # Координаты или области
    if re.search(r'\d+[,\.]?\d+', text):
        info["coordinates"] = re.findall(r'\d+[,\.]?\d+', text)[:2]
    
    return info

def is_threat_relevant(text: str) -> bool:
    """Проверяет релевантность сообщения"""
    text_lower = text.lower()
    
    has_ballistic = any(word in text_lower for word in KEYWORDS["ballistic"] + KEYWORDS["cruise"])
    has_kyiv = any(word in text_lower for word in KEYWORDS["kyiv"])
    has_threat = any(word in text_lower for word in KEYWORDS["threat"])
    
    return has_ballistic and (has_kyiv or has_threat)

# ============ ОБРАБОТЧИКИ ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    global YOUR_CHAT_ID
    YOUR_CHAT_ID = update.effective_chat.id
    
    welcome_msg = (
        "🚨 <b>Монитор Баллистических Угроз</b>\n\n"
        f"✅ Бот активирован!\n"
        f"🆔 ID чата: <code>{YOUR_CHAT_ID}</code>\n\n"
        f"<b>📋 Доступные команды:</b>\n"
        f"/status - статус мониторинга\n"
        f"/channels - список каналов\n"
        f"/stats - статистика за 24ч\n"
        f"/help - справка\n"
    )
    
    await update.message.reply_text(welcome_msg, parse_mode='HTML')
    logger.info(f"Бот запущен. Chat ID: {YOUR_CHAT_ID}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    status_msg = (
        "🟢 <b>Статус: Активен</b>\n\n"
        f"📡 Мониторируется: {len(MONITORED_CHANNELS)} каналов\n"
        f"🎯 Поиск: Баллистических угроз на Киев\n"
        f"⏰ Время сервера: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📁 БД: {os.path.getsize(DATABASE_FILE) if os.path.exists(DATABASE_FILE) else 0} bytes"
    )
    await update.message.reply_text(status_msg, parse_mode='HTML')

async def channels_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /channels"""
    channels_msg = "📢 <b>Мониторируемые каналы:</b>\n\n"
    for i, (channel, description) in enumerate(MONITORED_CHANNELS.items(), 1):
        channels_msg += f"{i}. <b>@{channel}</b> - {description}\n"
    
    await update.message.reply_text(channels_msg, parse_mode='HTML')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats"""
    stats_data = get_alerts_stats(24)
    
    stats_msg = "📊 <b>Статистика за 24 часа:</b>\n\n"
    
    if not stats_data:
        stats_msg += "Нет данных об алертах за последние 24 часа"
    else:
        total_alerts = sum(count for _, count, _ in stats_data)
        stats_msg += f"<b>Всего алертов: {total_alerts}</b>\n\n"
        
        for threat_type, count, region in stats_data:
            stats_msg += f"{threat_type}: <b>{count}</b> в {region}\n"
    
    await update.message.reply_text(stats_msg, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_msg = (
        "<b>🆘 Справка</b>\n\n"
        "<b>Команды бота:</b>\n"
        "/start - запустить\n"
        "/status - статус\n"
        "/channels - каналы\n"
        "/stats - статистика\n"
        "/help - эта справка\n\n"
        "<b>ℹ️ Информация:</b>\n"
        "Бот мониторит популярные Telegram-каналы с информацией об угрозах и отправляет срочные алерты при обнаружении баллистических ракет, направленных на Киев.\n\n"
        "<b>⚙️ Как работает:</b>\n"
        "• Сканирует сообщения из мониторируемых каналов\n"
        "• Анализирует текст на ключевые слова\n"
        "• Определяет тип угрозы (баллистика/крылатая)\n"
        "• Отправляет срочное уведомление\n"
        "• Сохраняет историю в базу данных\n"
    )
    
    await update.message.reply_text(help_msg, parse_mode='HTML')

async def handle_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений из каналов"""
    message = update.channel_post or update.message
    
    if not message or not message.text:
        return
    
    sender_username = message.chat.username
    if not sender_username:
        return
    
    # Проверяем релевантность
    if is_threat_relevant(message.text):
        threat_type = detect_threat_type(message.text)
        detailed_info = extract_detailed_info(message.text)
        
        # Сохраняем в БД
        save_alert(sender_username, message.text, threat_type)
        
        # Формируем алерт
        alert_msg = (
            f"🚨 <b>СРОЧНОЕ ПРЕДУПРЕЖДЕНИЕ!</b>\n\n"
            f"{threat_type}\n\n"
            f"📢 Источник: @{sender_username}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
        )
        
        if detailed_info["times"]:
            alert_msg += f"🕐 Время угрозы: {', '.join(detailed_info['times'])}\n"
        
        if detailed_info["directions"]:
            alert_msg += f"🧭 Направление: {', '.join(detailed_info['directions'])}\n"
        
        alert_msg += f"\n<b>Полный текст:</b>\n<code>{message.text[:400]}</code>"
        
        # Отправляем уведомление
        if YOUR_CHAT_ID:
            try:
                bot = Bot(token=TELEGRAM_TOKEN)
                await bot.send_message(
                    chat_id=YOUR_CHAT_ID,
                    text=alert_msg,
                    parse_mode='HTML'
                )
                logger.info(f"✅ Алерт отправлен: {threat_type} из @{sender_username}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    """Главная функция"""
    # Инициализируем БД
    init_database()
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("channels", channels_list))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчик сообщений из каналов
    application.add_handler(
        MessageHandler(filters.UPDATE_CHANNEL_POST, handle_channel_message)
    )
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    logger.info("🚀 Монитор запущен и готов к работе...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
