"""
Скрипт для синхронізації каналів з БД в config.py
"""
from database import Database

def sync_channels_from_db():
    """Завантажити оновлені канали з БД та оновити config.py"""
    db = Database()
    cursor = db.get_cursor()
    
    try:
        cursor.execute("""
            SELECT channel_name, channel_id 
            FROM channel_mappings
            ORDER BY channel_name
        """)
        
        mappings = cursor.fetchall()
        
        if mappings:
            print("📋 Оновлені канали з БД:")
            for mapping in mappings:
                print(f"  {mapping['channel_name']}: {mapping['channel_id']}")
            
            # Читаємо config.py
            with open('config.py', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Шукаємо секцію CHANNELS
            in_channels = False
            new_lines = []
            
            for line in lines:
                if 'CHANNELS = {' in line:
                    in_channels = True
                    new_lines.append(line)
                    
                    # Вставляємо оновлені канали
                    for mapping in mappings:
                        new_lines.append(f'    "{mapping["channel_name"]}": "{mapping["channel_id"]}",\n')
                    continue
                
                if in_channels and '}' in line and 'CHANNELS' not in line:
                    new_lines.append(line)
                    in_channels = False
                    continue
                
                if not in_channels:
                    new_lines.append(line)
            
            # Записуємо назад
            with open('config.py', 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            
            print("✅ config.py оновлено!")
        else:
            print("ℹ️ Немає змін каналів в БД")
            
    except Exception as e:
        print(f"❌ Помилка: {e}")
    finally:
        cursor.close()

if __name__ == '__main__':
    sync_channels_from_db()
