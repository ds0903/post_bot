-- ============================================
-- SQL скрипт для створення бази даних
-- ============================================

-- Створення бази даних (виконай від імені postgres користувача)
CREATE DATABASE telegram_bot_db
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'uk_UA.UTF-8'
    LC_CTYPE = 'uk_UA.UTF-8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1;

-- Підключення до створеної бази даних
\c telegram_bot_db

-- ============================================
-- Таблиця користувачів
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE users IS 'Таблиця всіх користувачів бота';
COMMENT ON COLUMN users.user_id IS 'Telegram ID користувача';
COMMENT ON COLUMN users.username IS 'Username користувача в Telegram';
COMMENT ON COLUMN users.created_at IS 'Дата реєстрації користувача';

-- ============================================
-- Таблиця адміністраторів
-- ============================================
CREATE TABLE IF NOT EXISTS admins (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE admins IS 'Таблиця адміністраторів бота';
COMMENT ON COLUMN admins.user_id IS 'Telegram ID адміністратора';
COMMENT ON COLUMN admins.username IS 'Username адміністратора в Telegram';

-- ============================================
-- Таблиця постів (заявок на модерацію)
-- ============================================
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255),
    channel VARCHAR(255) NOT NULL,
    message_data JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE posts IS 'Таблиця всіх постів та їх статусів';
COMMENT ON COLUMN posts.id IS 'Унікальний ID заявки';
COMMENT ON COLUMN posts.user_id IS 'ID користувача, який відправив пост';
COMMENT ON COLUMN posts.username IS 'Username користувача';
COMMENT ON COLUMN posts.channel IS 'Назва каналу для публікації';
COMMENT ON COLUMN posts.message_data IS 'JSON дані повідомлення (текст, фото, відео тощо)';
COMMENT ON COLUMN posts.status IS 'Статус заявки: pending, approved, rejected';
COMMENT ON COLUMN posts.created_at IS 'Час створення заявки';
COMMENT ON COLUMN posts.processed_at IS 'Час обробки заявки адміністратором';

-- ============================================
-- Індекси для оптимізації запитів
-- ============================================
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_processed_at ON posts(processed_at DESC);

-- ============================================
-- Перегляди (Views) для зручності
-- ============================================

-- Активні заявки на модерацію
CREATE OR REPLACE VIEW pending_posts_view AS
SELECT 
    p.id,
    p.user_id,
    p.username,
    p.channel,
    p.created_at,
    EXTRACT(EPOCH FROM (NOW() - p.created_at))/3600 as hours_pending
FROM posts p
WHERE p.status = 'pending'
ORDER BY p.created_at ASC;

-- Статистика по користувачам
CREATE OR REPLACE VIEW user_stats_view AS
SELECT 
    u.user_id,
    u.username,
    COUNT(p.id) as total_posts,
    COUNT(p.id) FILTER (WHERE p.status = 'pending') as pending,
    COUNT(p.id) FILTER (WHERE p.status = 'approved') as approved,
    COUNT(p.id) FILTER (WHERE p.status = 'rejected') as rejected,
    MAX(p.created_at) as last_post_date
FROM users u
LEFT JOIN posts p ON u.user_id = p.user_id
GROUP BY u.user_id, u.username;

-- Статистика по каналах
CREATE OR REPLACE VIEW channel_stats_view AS
SELECT 
    channel,
    COUNT(*) as total_posts,
    COUNT(*) FILTER (WHERE status = 'approved') as approved,
    COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
    COUNT(*) FILTER (WHERE status = 'pending') as pending
FROM posts
GROUP BY channel
ORDER BY total_posts DESC;

-- ============================================
-- Функції для очищення старих даних
-- ============================================

-- Функція для видалення старих відхилених постів
CREATE OR REPLACE FUNCTION cleanup_old_rejected_posts(days_old INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM posts
    WHERE status = 'rejected' 
    AND processed_at < NOW() - (days_old || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_rejected_posts IS 'Видаляє відхилені пости старші за N днів';

-- ============================================
-- Тригери
-- ============================================

-- Тригер для автоматичного оновлення processed_at
CREATE OR REPLACE FUNCTION update_processed_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status != 'pending' AND OLD.status = 'pending' THEN
        NEW.processed_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_processed_at
    BEFORE UPDATE ON posts
    FOR EACH ROW
    EXECUTE FUNCTION update_processed_at();

-- ============================================
-- Початкові дані (опціонально)
-- ============================================

-- Можна додати тестового користувача для перевірки
-- INSERT INTO users (user_id, username) VALUES (123456789, 'test_user');

-- ============================================
-- Надання прав (якщо потрібно)
-- ============================================

-- GRANT ALL PRIVILEGES ON DATABASE telegram_bot_db TO your_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;

-- ============================================
-- Завершення
-- ============================================

SELECT 'База даних успішно створена!' as result;
