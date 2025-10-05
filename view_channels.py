"""
Скрипт для перегляду всіх каналів у базі даних
"""

from database import Database

def view_channels():
    db = Database()
    
    print("\n" + "="*60)
    print("📋 КАНАЛИ В БАЗІ ДАНИХ")
    print("="*60 + "\n")
    
    channels = db.get_all_channels()
    
    if not channels:
        print("❌ База даних порожня. Немає жодного каналу.\n")
        print("💡 Додайте канали через:")
        print("   1. Адмін-панель бота (/admin)")
        print("   2. Скрипт sync_channels.py\n")
        return
    
    for idx, (name, channel_id) in enumerate(channels.items(), 1):
        print(f"{idx}. {name}")
        print(f"   ID: {channel_id}")
        print(f"   Посилання: https://t.me/{channel_id.replace('@', '')}")
        print()
    
    print(f"Всього каналів: {len(channels)}\n")
    print("="*60 + "\n")

if __name__ == "__main__":
    view_channels()
