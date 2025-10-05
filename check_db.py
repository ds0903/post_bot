#!/usr/bin/env python3
"""
Скрипт для перевірки підключення до бази даних
"""

import asyncio
import sys

try:
    from database import Database
    from config import DB_CONFIG
except ImportError as e:
    print(f"❌ Помилка імпорту: {e}")
    print("Переконайся, що файл config.py існує!")
    sys.exit(1)

async def check_database():
    print("=" * 50)
    print("🔍 Перевірка підключення до бази даних")
    print("=" * 50)
    print()
    
    print("📋 Налаштування БД:")
    print(f"  Host: {DB_CONFIG['host']}")
    print(f"  Database: {DB_CONFIG['database']}")
    print(f"  User: {DB_CONFIG['user']}")
    print(f"  Port: {DB_CONFIG['port']}")
    print()
    
    try:
        print("🔄 Підключення до бази даних...")
        db = Database()
        print("✅ Підключення успішне!")
        print()
        
        print("🔄 Створення таблиць...")
        await db.create_tables()
        print("✅ Таблиці створено!")
        print()
        
        # Перевірка таблиць
        cursor = db.get_cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        cursor.close()
        
        print("📊 Таблиці в базі даних:")
        for table in tables:
            print(f"  ✓ {table['table_name']}")
        print()
        
        # Статистика
        cursor = db.get_cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users")
        users_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM admins")
        admins_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM posts")
        posts_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM posts WHERE status = 'pending'")
        pending_count = cursor.fetchone()['count']
        
        cursor.close()
        
        print("📈 Статистика:")
        print(f"  👥 Користувачів: {users_count}")
        print(f"  👨‍💼 Адмінів: {admins_count}")
        print(f"  📝 Всього постів: {posts_count}")
        print(f"  ⏳ На модерації: {pending_count}")
        print()
        
        print("✅ Все працює відмінно!")
        
    except Exception as e:
        print(f"❌ Помилка: {e}")
        print()
        print("💡 Переконайся, що:")
        print("  1. PostgreSQL запущений")
        print("  2. База даних створена")
        print("  3. Дані для підключення в config.py правильні")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(check_database())
