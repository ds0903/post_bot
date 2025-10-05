"""
Скрипт для додавання каналів в базу даних
"""

from database import Database

def add_channels():
    db = Database()
    
    # Приклади каналів - змініть на свої
    channels = {
        # "Назва каналу": "@channel_id або https://t.me/channel_id"
    }
    
    print("🔧 Додавання каналів в базу даних...\n")
    
    if not channels:
        print("❌ Немає каналів для додавання!")
        print("📝 Відредагуйте файл sync_channels.py та додайте свої канали\n")
        print("Приклад:")
        print('channels = {')
        print('    "Мій канал": "@my_channel",')
        print('    "Новини": "https://t.me/news_channel"')
        print('}')
        return
    
    for channel_name, channel_id in channels.items():
        # Нормалізуємо ID каналу
        if 't.me/' in channel_id:
            channel_id = '@' + channel_id.split('t.me/')[-1].strip('/')
        
        if db.add_channel(channel_name, channel_id):
            print(f"✅ Додано: {channel_name} → {channel_id}")
        else:
            print(f"❌ Помилка: {channel_name}")
    
    print("\n📋 Всі канали в БД:")
    all_channels = db.get_all_channels()
    for name, ch_id in all_channels.items():
        print(f"   • {name}: {ch_id}")
    
    print("\n✅ Готово!")

if __name__ == "__main__":
    add_channels()
