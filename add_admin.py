#!/usr/bin/env python3
"""
Скрипт для додавання адміністратора в базу даних
"""

import sys
from database import Database

def add_admin_to_db():
    print("=" * 50)
    print("👨‍💼 Додавання адміністратора")
    print("=" * 50)
    print()
    
    try:
        db = Database()
        print("✅ Підключено до бази даних")
        print()
    except Exception as e:
        print(f"❌ Помилка підключення до БД: {e}")
        sys.exit(1)
    
    print("Як отримати свій Telegram ID:")
    print("  1. Напиши боту @userinfobot")
    print("  2. Він покаже твій ID")
    print()
    
    try:
        user_id = input("Введи Telegram ID адміна: ").strip()
        
        if not user_id.isdigit():
            print("❌ ID має бути числом!")
            sys.exit(1)
        
        user_id = int(user_id)
        
        username = input("Введи username (без @): ").strip()
        if not username:
            username = f"admin_{user_id}"
        
        # Додаємо адміна
        db.add_admin(user_id, username)
        
        print()
        print("✅ Адміністратор успішно доданий!")
        print(f"   ID: {user_id}")
        print(f"   Username: {username}")
        print()
        print("Тепер ти можеш увійти в бота через:")
        print(f"   /admin твій_пароль")
        print()
        
    except KeyboardInterrupt:
        print("\n\n❌ Скасовано")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    add_admin_to_db()
