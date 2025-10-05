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
        """Видалити канал"""
        cursor = self.get_cursor()
        try:
            cursor.execute("""
                DELETE FROM channels
                WHERE channel_name = %s
            """, (channel_name,))
            print(f"✅ Канал '{channel_name}' видалено")
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
    
    def __del__(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
