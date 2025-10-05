import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
from config import DB_CONFIG

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = True
        except Exception as e:
            print(f"Помилка підключення до БД: {e}")
            raise
    
    def get_cursor(self):
        if self.conn is None or self.conn.closed:
            self.connect()
        return self.conn.cursor(cursor_factory=RealDictCursor)
    
    async def create_tables(self):
        cursor = self.get_cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                channel_name VARCHAR(255) UNIQUE NOT NULL,
                channel_id VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username VARCHAR(255),
                channel VARCHAR(255) NOT NULL,
                message_data JSONB NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_mappings (
                id SERIAL PRIMARY KEY,
                channel_name VARCHAR(255) UNIQUE NOT NULL,
                channel_id VARCHAR(255) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(255) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_posts_status 
            ON posts(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_posts_user_id 
            ON posts(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_posts_channel 
            ON posts(channel)
        """)
        
        # Видаляємо стару таблицю settings якщо вона є
        cursor.execute("DROP TABLE IF EXISTS settings")
        
        # Створюємо нову таблицю settings
        cursor.execute("""
            CREATE TABLE settings (
                setting_key VARCHAR(255) PRIMARY KEY,
                setting_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Додаємо дефолтні налаштування
        cursor.execute("""
            INSERT INTO settings (setting_key, setting_value)
            VALUES ('spam_protection_enabled', 'true')
        """)
        
        cursor.execute("""
            INSERT INTO settings (setting_key, setting_value)
            VALUES ('spam_protection_minutes', '15')
        """)
        
        cursor.close()
        print("✅ Таблиці створено успішно!")
    
    def add_user(self, user_id: int, username: str):
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                INSERT INTO users (user_id, username) 
                VALUES (%s, %s) 
                ON CONFLICT (user_id) DO UPDATE 
                SET username = EXCLUDED.username
            """, (user_id, username))
        except Exception as e:
            print(f"Помилка додавання користувача: {e}")
        finally:
            cursor.close()
    
    def add_admin(self, user_id: int, username: str):
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                INSERT INTO admins (user_id, username) 
                VALUES (%s, %s) 
                ON CONFLICT (user_id) DO UPDATE 
                SET username = EXCLUDED.username
            """, (user_id, username))
        except Exception as e:
            print(f"Помилка додавання адміна: {e}")
        finally:
            cursor.close()
    
    def is_admin(self, user_id: int) -> bool:
        """Перевірка чи користувач є адміном"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM admins WHERE user_id = %s
                )
            """, (user_id,))
            result = cursor.fetchone()
            return result['exists'] if result else False
        except Exception as e:
            print(f"Помилка перевірки адміна: {e}")
            return False
        finally:
            cursor.close()
    
    def add_post(self, user_id: int, username: str, channel: str, message_data: dict) -> int:
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                INSERT INTO posts (user_id, username, channel, message_data, status) 
                VALUES (%s, %s, %s, %s, 'pending')
                RETURNING id
            """, (user_id, username, channel, json.dumps(message_data)))
            
            result = cursor.fetchone()
            return result['id']
        except Exception as e:
            print(f"Помилка додавання поста: {e}")
            return 0
        finally:
            cursor.close()
    
    def get_pending_posts(self):
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT id, user_id, username, channel, message_data, created_at
                FROM posts 
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
            
            rows = cursor.fetchall()
            result = []
            for row in rows:
                result.append((
                    row['id'],
                    row['user_id'],
                    row['username'],
                    row['channel'],
                    row['message_data'],
                    row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                ))
            return result
        except Exception as e:
            print(f"Помилка отримання заявок: {e}")
            return []
        finally:
            cursor.close()
    
    def get_pending_posts_by_channel(self, channel: str):
        """Отримати заявки тільки для конкретного каналу"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT id, user_id, username, channel, message_data, created_at
                FROM posts 
                WHERE status = 'pending' AND channel = %s
                ORDER BY created_at ASC
            """, (channel,))
            
            rows = cursor.fetchall()
            result = []
            for row in rows:
                result.append((
                    row['id'],
                    row['user_id'],
                    row['username'],
                    row['channel'],
                    row['message_data'],
                    row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                ))
            return result
        except Exception as e:
            print(f"Помилка отримання заявок по каналу: {e}")
            return []
        finally:
            cursor.close()
    
    def get_channels_with_pending_posts(self):
        """Отримати список каналів, які мають заявки на модерацію"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT channel
                FROM posts 
                WHERE status = 'pending'
                ORDER BY channel
            """)
            
            rows = cursor.fetchall()
            return [row['channel'] for row in rows]
        except Exception as e:
            print(f"Помилка отримання каналів з заявками: {e}")
            return []
        finally:
            cursor.close()
    
    def get_post_by_id(self, post_id: int):
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT id, user_id, username, channel, message_data, created_at
                FROM posts 
                WHERE id = %s
            """, (post_id,))
            
            row = cursor.fetchone()
            if row:
                return (
                    row['id'],
                    row['user_id'],
                    row['username'],
                    row['channel'],
                    row['message_data'],
                    row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                )
            return None
        except Exception as e:
            print(f"Помилка отримання поста: {e}")
            return None
        finally:
            cursor.close()
    
    def update_post_status(self, post_id: int, status: str):
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                UPDATE posts 
                SET status = %s, processed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, post_id))
        except Exception as e:
            print(f"Помилка оновлення статусу: {e}")
        finally:
            cursor.close()
    
    def get_posts_history(self, limit: int = 20):
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT id, username, channel, status, created_at, processed_at
                FROM posts 
                WHERE status IN ('approved', 'rejected')
                ORDER BY processed_at DESC
                LIMIT %s
            """, (limit,))
            
            rows = cursor.fetchall()
            result = []
            for row in rows:
                result.append((
                    row['id'],
                    row['username'],
                    row['channel'],
                    row['status'],
                    row['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    row['processed_at'].strftime('%Y-%m-%d %H:%M:%S') if row['processed_at'] else None
                ))
            return result
        except Exception as e:
            print(f"Помилка отримання історії: {e}")
            return []
        finally:
            cursor.close()
    
    def get_user_stats(self, user_id: int):
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE status = 'approved') as approved,
                    COUNT(*) FILTER (WHERE status = 'rejected') as rejected
                FROM posts 
                WHERE user_id = %s
            """, (user_id,))
            
            return cursor.fetchone()
        except Exception as e:
            print(f"Помилка отримання статистики: {e}")
            return None
        finally:
            cursor.close()
    
    def get_all_channels(self):
        """Отримати всі канали з БД"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT channel_name, channel_id
                FROM channels
                ORDER BY channel_name
            """)
            
            rows = cursor.fetchall()
            channels = {}
            for row in rows:
                channels[row['channel_name']] = row['channel_id']
            return channels
        except Exception as e:
            print(f"Помилка отримання каналів: {e}")
            return {}
        finally:
            cursor.close()
    
    def add_channel(self, channel_name: str, channel_id: str):
        """Додати новий канал"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                INSERT INTO channels (channel_name, channel_id)
                VALUES (%s, %s)
            """, (channel_name, channel_id))
            print(f"✅ Канал '{channel_name}' додано")
            return True
        except Exception as e:
            print(f"Помилка додавання каналу: {e}")
            return False
        finally:
            cursor.close()
    
    def delete_channel(self, channel_name: str):
        """Видалити канал та всі його заявки"""
        cursor = self.get_cursor()
        try:
            # Спочатку видаляємо всі заявки для цього каналу
            cursor.execute("""
                DELETE FROM posts
                WHERE channel = %s
            """, (channel_name,))
            deleted_posts = cursor.rowcount
            
            # Потім видаляємо сам канал
            cursor.execute("""
                DELETE FROM channels
                WHERE channel_name = %s
            """, (channel_name,))
            
            print(f"✅ Канал '{channel_name}' видалено (видалено {deleted_posts} заявок)")
            return True
        except Exception as e:
            print(f"Помилка видалення каналу: {e}")
            return False
        finally:
            cursor.close()
    
    def update_channel(self, channel_name: str, new_channel_id: str):
        """Оновити ID каналу"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                UPDATE channels 
                SET channel_id = %s, updated_at = CURRENT_TIMESTAMP
                WHERE channel_name = %s
            """, (new_channel_id, channel_name))
            print(f"✅ ID каналу '{channel_name}' оновлено на '{new_channel_id}'")
            return True
        except Exception as e:
            print(f"Помилка оновлення ID каналу: {e}")
            return False
        finally:
            cursor.close()
    
    def get_channel_mapping(self, channel_name: str):
        """Отримати актуальне посилання на канал"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT channel_id
                FROM channel_mappings 
                WHERE channel_name = %s
            """, (channel_name,))
            
            row = cursor.fetchone()
            return row['channel_id'] if row else None
        except Exception as e:
            print(f"Помилка отримання маппінгу каналу: {e}")
            return None
        finally:
            cursor.close()
    
    def get_last_post_time(self, user_id: int):
        """Отримати час останнього посту користувача"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT created_at
                FROM posts 
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return row['created_at']
            return None
        except Exception as e:
            print(f"Помилка отримання часу останнього посту: {e}")
            return None
        finally:
            cursor.close()
    
    def rename_channel(self, old_name: str, new_name: str):
        """Перейменувати канал"""
        cursor = self.get_cursor()
        try:
            # Оновлюємо всі пости зі старою назвою на нову
            cursor.execute("""
                UPDATE posts 
                SET channel = %s
                WHERE channel = %s
            """, (new_name, old_name))
            
            # Оновлюємо назву в таблиці channels
            cursor.execute("""
                UPDATE channels 
                SET channel_name = %s, updated_at = CURRENT_TIMESTAMP
                WHERE channel_name = %s
            """, (new_name, old_name))
            
            print(f"✅ Канал '{old_name}' перейменовано на '{new_name}'")
            return True
        except Exception as e:
            print(f"Помилка перейменування каналу: {e}")
            return False
        finally:
            cursor.close()
    
    def get_setting(self, key: str, default=None):
        """Отримати налаштування з БД"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT value FROM settings WHERE key = %s
            """, (key,))
            row = cursor.fetchone()
            return row['value'] if row else default
        except Exception as e:
            print(f"Помилка отримання налаштування {key}: {e}")
            return default
        finally:
            cursor.close()
    
    def set_setting(self, key: str, value: str):
        """Зберегти налаштування в БД"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
            """, (key, value))
            return True
        except Exception as e:
            print(f"Помилка збереження налаштування {key}: {e}")
            return False
        finally:
            cursor.close()
    
    def get_spam_protection_settings(self):
        """Отримати налаштування захисту від спаму"""
        enabled = self.get_setting('spam_protection_enabled', 'true')
        delay = self.get_setting('post_delay_minutes', '15')
        
        return {
            'enabled': enabled.lower() == 'true',
            'delay_minutes': int(delay)
        }
    
    def set_spam_protection_enabled(self, enabled: bool):
        """Увімкнути/вимкнути захист від спаму"""
        return self.set_setting('spam_protection_enabled', 'true' if enabled else 'false')
    
    def set_post_delay_minutes(self, minutes: int):
        """Встановити затримку між постами (в хвилинах)"""
        return self.set_setting('post_delay_minutes', str(minutes))
    
    def get_spam_settings(self):
        """Отримати налаштування захисту від спаму"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                SELECT setting_value 
                FROM settings 
                WHERE setting_key = 'spam_protection_enabled'
            """)
            row = cursor.fetchone()
            enabled = row['setting_value'] == 'true' if row else True
            
            cursor.execute("""
                SELECT setting_value 
                FROM settings 
                WHERE setting_key = 'spam_protection_minutes'
            """)
            row = cursor.fetchone()
            minutes = int(row['setting_value']) if row else 15
            
            return {'enabled': enabled, 'minutes': minutes}
        except Exception as e:
            print(f"Помилка отримання налаштувань спаму: {e}")
            return {'enabled': True, 'minutes': 15}
        finally:
            cursor.close()
    
    def update_spam_setting(self, key: str, value: str):
        """Оновити налаштування спаму"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                INSERT INTO settings (setting_key, setting_value)
                VALUES (%s, %s)
                ON CONFLICT (setting_key) 
                DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = CURRENT_TIMESTAMP
            """, (key, value))
            return True
        except Exception as e:
            print(f"Помилка оновлення налаштування: {e}")
            return False
        finally:
            cursor.close()
    
    def set_spam_protection_enabled(self, enabled: bool):
        """Увімкнути/вимкнути захист від спаму"""
        return self.update_spam_setting('spam_protection_enabled', 'true' if enabled else 'false')
    
    def set_spam_protection_minutes(self, minutes: int):
        """Встановити затримку в хвилинах"""
        return self.update_spam_setting('spam_protection_minutes', str(minutes))
    
    def cleanup_orphaned_posts(self):
        """Видалити заявки для каналів, які більше не існують"""
        cursor = self.get_cursor()
        try:
            # Видаляємо всі заявки, де канал не існує в таблиці channels
            cursor.execute("""
                DELETE FROM posts
                WHERE channel NOT IN (SELECT channel_name FROM channels)
            """)
            deleted_count = cursor.rowcount
            
            if deleted_count > 0:
                print(f"✅ Видалено {deleted_count} сирітських заявок")
            
            return deleted_count
        except Exception as e:
            print(f"Помилка очищення сирітських заявок: {e}")
            return 0
        finally:
            cursor.close()

    def __del__(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
