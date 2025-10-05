import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import bcrypt
from datetime import datetime
from database import Database
from config import BOT_TOKEN, ADMIN_PASSWORD_HASH, CHANNELS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

# Для збору альбомів
album_data = {}

class UserStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_post = State()
    confirming_post = State()

class AdminStates(StatesGroup):
    in_admin_panel = State()

def get_channels_keyboard():
    buttons = []
    for channel_name in CHANNELS.keys():
        buttons.append([KeyboardButton(text=channel_name)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_menu_keyboard():
    buttons = [
        [KeyboardButton(text="📋 Заявки на модерацію")],
        [KeyboardButton(text="📊 Історія заявок")],
        [KeyboardButton(text="🚪 Вийти з адмінки")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_confirm_keyboard():
    buttons = [
        [KeyboardButton(text="✅ Відправити на модерацію")],
        [KeyboardButton(text="🔄 Заповнити заново")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_moderation_keyboard(post_id: int):
    buttons = [
        [
            InlineKeyboardButton(text="✅ Опублікувати", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_{post_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "без_ніка"
    db.add_user(user_id, username)
    await message.answer("👋 Вітаю! Оберіть канал:", reply_markup=get_channels_keyboard())
    await state.set_state(UserStates.waiting_for_channel)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 <b>Довідка</b>\n\n"
        "/start - почати\n"
        "/help - довідка",
        parse_mode="HTML"
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not db.is_admin(user_id):
        await message.answer("❌ Немає доступу!")
        return
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("⚠️ Використовуйте: /admin пароль")
        return
    try:
        if bcrypt.checkpw(parts[1].encode('utf-8'), ADMIN_PASSWORD_HASH.encode('utf-8')):
            try:
                await message.delete()
            except:
                pass
            await message.answer("✅ Увійшли в адмінку!", reply_markup=get_admin_menu_keyboard())
            await state.set_state(AdminStates.in_admin_panel)
        else:
            await message.answer("❌ Невірний пароль!")
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")

@dp.message(UserStates.waiting_for_channel)
async def handle_channel_selection(message: Message, state: FSMContext):
    channel = message.text
    if channel not in CHANNELS:
        await message.answer("❌ Оберіть канал зі списку:", reply_markup=get_channels_keyboard())
        return
    await state.update_data(channel=channel)
    await message.answer(
        f"✅ Канал: <b>{channel}</b>\n\nНадішли пост:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(UserStates.waiting_for_post)

@dp.message(UserStates.waiting_for_post)
async def handle_post_content(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Альбом
    if message.media_group_id:
        album_key = f"{user_id}_{message.media_group_id}"
        
        if album_key not in album_data:
            album_data[album_key] = {
                'items': [],
                'caption': '',
                'user_id': user_id,
                'state': state,
                'task': None
            }
        
        if message.photo:
            album_data[album_key]['items'].append({'type': 'photo', 'file_id': message.photo[-1].file_id})
        elif message.video:
            album_data[album_key]['items'].append({'type': 'video', 'file_id': message.video.file_id})
        
        if message.caption:
            album_data[album_key]['caption'] = message.caption
        
        # Скасовуємо попередню задачу
        if album_data[album_key]['task']:
            album_data[album_key]['task'].cancel()
        
        # Створюємо нову задачу з затримкою
        async def finish_album():
            await asyncio.sleep(1.0)
            if album_key in album_data:
                data = album_data[album_key]
                items = data['items']
                photos = sum(1 for m in items if m['type'] == 'photo')
                videos = sum(1 for m in items if m['type'] == 'video')
                media_text = []
                if photos > 0:
                    media_text.append(f"{photos} фото")
                if videos > 0:
                    media_text.append(f"{videos} відео")
                
                await state.update_data(
                    media_group=items,
                    caption=data['caption'],
                    has_content=True
                )
                await bot.send_message(
                    user_id,
                    f"📸 Альбом: {' та '.join(media_text)}\n\nОбери дію:",
                    reply_markup=get_confirm_keyboard()
                )
                await state.set_state(UserStates.confirming_post)
                del album_data[album_key]
        
        album_data[album_key]['task'] = asyncio.create_task(finish_album())
        return
    
    # Одне фото
    if message.photo:
        await state.update_data(photo=message.photo[-1].file_id, caption=message.caption or '', has_content=True)
        await message.answer("📸 Фото отримано!\n\nОбери дію:", reply_markup=get_confirm_keyboard())
        await state.set_state(UserStates.confirming_post)
        return
    
    # Відео
    if message.video:
        await state.update_data(video=message.video.file_id, caption=message.caption or '', has_content=True)
        await message.answer("🎥 Відео отримано!\n\nОбери дію:", reply_markup=get_confirm_keyboard())
        await state.set_state(UserStates.confirming_post)
        return
    
    # Текст
    if message.text:
        await state.update_data(text_content=message.text, has_content=True)
        await message.answer("📝 Текст отримано!\n\nОбери дію:", reply_markup=get_confirm_keyboard())
        await state.set_state(UserStates.confirming_post)
        return

@dp.message(UserStates.confirming_post, F.text == "✅ Відправити на модерацію")
async def confirm_and_send_post(message: Message, state: FSMContext):
    data = await state.get_data()
    channel = data.get('channel')
    user_id = message.from_user.id
    username = message.from_user.username or "без_ніка"
    
    msg_data = {}
    if data.get('media_group'):
        msg_data['media_group'] = data['media_group']
        msg_data['caption'] = data.get('caption', '')
    elif data.get('photo'):
        msg_data['photo'] = data['photo']
        msg_data['caption'] = data.get('caption', '')
    elif data.get('video'):
        msg_data['video'] = data['video']
        msg_data['caption'] = data.get('caption', '')
    elif data.get('text_content'):
        msg_data['text'] = data['text_content']
    
    post_id = db.add_post(user_id, username, channel, msg_data)
    await message.answer(f"✅ Відправлено! Заявка #{post_id}", reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
    await state.clear()

@dp.message(UserStates.confirming_post, F.text == "🔄 Заповнити заново")
async def restart_post_creation(message: Message, state: FSMContext):
    await message.answer("🔄 Заново!\n\nОбери канал:", reply_markup=get_channels_keyboard())
    await state.set_state(UserStates.waiting_for_channel)

@dp.message(AdminStates.in_admin_panel, F.text == "📋 Заявки на модерацію")
async def show_pending_posts(message: Message):
    pending_posts = db.get_pending_posts()
    if not pending_posts:
        await message.answer("Немає заявок.")
        return
    
    from aiogram.types import InputMediaPhoto, InputMediaVideo
    
    for post in pending_posts:
        post_id, user_id, username, channel, msg_data, created_at = post
        text = f"🆔 #{post_id}\n👤 @{username}\n📢 {channel}\n🕒 {created_at}"
        
        if msg_data.get('media_group'):
            # Відправляємо альбом одним повідомленням
            media_group = []
            caption_text = msg_data.get('caption', '')
            
            for idx, item in enumerate(msg_data['media_group']):
                caption = (text + "\n\n" + caption_text) if idx == 0 else None
                if item['type'] == 'photo':
                    media_group.append(InputMediaPhoto(media=item['file_id'], caption=caption))
                elif item['type'] == 'video':
                    media_group.append(InputMediaVideo(media=item['file_id'], caption=caption))
            
            await message.answer_media_group(media=media_group)
            await message.answer("Дії:", reply_markup=get_moderation_keyboard(post_id))
        elif msg_data.get('photo'):
            caption_text = msg_data.get('caption', '')
            full_text = text + ("\n\n" + caption_text if caption_text else "")
            await message.answer_photo(msg_data['photo'], caption=full_text, reply_markup=get_moderation_keyboard(post_id))
        elif msg_data.get('video'):
            caption_text = msg_data.get('caption', '')
            full_text = text + ("\n\n" + caption_text if caption_text else "")
            await message.answer_video(msg_data['video'], caption=full_text, reply_markup=get_moderation_keyboard(post_id))
        else:
            full_text = text + "\n\n" + msg_data.get('text', '')
            await message.answer(full_text, reply_markup=get_moderation_keyboard(post_id))

@dp.message(AdminStates.in_admin_panel, F.text == "📊 Історія заявок")
async def show_history(message: Message):
    history = db.get_posts_history(limit=20)
    if not history:
        await message.answer("Історія порожня.")
        return
    text = "📊 Історія:\n\n"
    for post in history:
        status_emoji = "✅" if post[3] == "approved" else "❌"
        text += f"{status_emoji} #{post[0]} | @{post[1]} → {post[2]}\n"
    await message.answer(text)

@dp.message(AdminStates.in_admin_panel, F.text == "🚪 Вийти з адмінки")
async def exit_admin(message: Message, state: FSMContext):
    await message.answer("👋 Вийшли.", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_post(callback: CallbackQuery):
    from aiogram.types import InputMediaPhoto, InputMediaVideo
    post_id = int(callback.data.split("_")[1])
    post_data = db.get_post_by_id(post_id)
    if not post_data:
        return
    _, user_id, username, channel, msg_data, _ = post_data
    channel_id = CHANNELS.get(channel)
    
    try:
        if msg_data.get('media_group'):
            media_group = []
            caption_text = msg_data.get('caption', '')
            for idx, item in enumerate(msg_data['media_group']):
                if item['type'] == 'photo':
                    media_group.append(InputMediaPhoto(media=item['file_id'], caption=caption_text if idx == 0 else None))
                elif item['type'] == 'video':
                    media_group.append(InputMediaVideo(media=item['file_id'], caption=caption_text if idx == 0 else None))
            await bot.send_media_group(chat_id=channel_id, media=media_group)
        elif msg_data.get('photo'):
            await bot.send_photo(channel_id, msg_data['photo'], caption=msg_data.get('caption', ''))
        elif msg_data.get('video'):
            await bot.send_video(channel_id, msg_data['video'], caption=msg_data.get('caption', ''))
        else:
            await bot.send_message(channel_id, msg_data.get('text', ''))
        
        db.update_post_status(post_id, 'approved')
        await bot.send_message(user_id, f"✅ Пост опубліковано в '{channel}'!")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("✅ Опубліковано!")
    except Exception as e:
        await callback.answer(f"❌ Помилка: {e}")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_post(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[1])
    post_data = db.get_post_by_id(post_id)
    if not post_data:
        return
    _, user_id, _, channel, _, _ = post_data
    db.update_post_status(post_id, 'rejected')
    try:
        await bot.send_message(user_id, f"❌ Пост відхилено.")
    except:
        pass
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("❌ Відхилено!")

async def setup_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Почати"),
        BotCommand(command="help", description="Довідка")
    ])

async def main():
    await db.create_tables()
    await setup_bot_commands()
    logger.info("🚀 Бот запущено!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
