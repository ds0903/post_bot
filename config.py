import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'ds0903')
ADMIN_PASSWORD_HASH = bcrypt.hashpw(ADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'telegram_bot_db'),
    'user': os.getenv('DB_USER', 'danil'),
    'password': os.getenv('DB_PASSWORD', 'danilus15'),
    'port': int(os.getenv('DB_PORT', 5432))
}
