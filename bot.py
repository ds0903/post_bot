import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, BotCommand
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from datetime import datetime, timedelta
from database import Database
from config import BOT_TOKEN
from admin_handlers import setup_admin_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

CHANNELS = {}

album_data = {}

def load_channels_from_db():
    """Завантажує канали з БД в глобальний словник"""
    global CHANNELS
    CHANNELS = db.get_all_channels()
    logger.info(f"📡 Завантажено {len(CHANNELS)} каналів з БД")

class UserStates(StatesGroup):
    waiting_for_post = State()
    confirming_post = State()

def get_write_another_post_keyboard():
    buttons = [
        [KeyboardButton(text="✍️ Написати ще 1 пост")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_confirm_keyboard():
    buttons = [
        [KeyboardButton(text="✅ Відправити на модерацію")],
        [KeyboardButton(text="🔄 Заповнити заново")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or "без_ніка"
    db.add_user(user_id, username)
    
    if command.args:
        channel_param_raw = command.args.strip()
        channel_found = None
        
        channel_param_name = channel_param_raw.replace('_', ' ')
        for channel_name in CHANNELS.keys():
            if channel_name.lower() == channel_param_name.lower() or channel_param_name.lower() in channel_name.lower():
                channel_found = channel_name
                break
        
        if not channel_found:
            search_id = channel_param_raw if channel_param_raw.startswith('@') else f'@{channel_param_raw}'
            for channel_name, channel_id in CHANNELS.items():
                if channel_id.lower() == search_id.lower():
                    channel_found = channel_name
                    break
        
        if channel_found:
            await state.update_data(channel=channel_found)
            await message.answer(
                f"📢 <b>{channel_found}</b>\n\nНадішліть пост:",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML"
            )
            await state.set_state(UserStates.waiting_for_post)
        else:
            await message.answer(
                "❌ Канал не знайдено.\n\n💡 Зверніться до адміністратора за правильним посиланням.",
                reply_markup=ReplyKeyboardRemove()
            )
    else:
        await message.answer(
            "❌ Доступ заборонено.\n\n💡 Використовуйте спеціальне посилання, яке вам надав адміністратор.",
            reply_markup=ReplyKeyboardRemove()
        )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 <b>Довідка</b>\n\n"
        "/start - почати\n"
        "/help - довідка",
        parse_mode="HTML"
    )

@dp.message(F.text == "✍️ Написати ще 1 пост")
async def write_another_post_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    channel = data.get('channel')
    
    if not channel:
        await message.answer("❌ Помилка: канал не знайдено.")
        return
    
    spam_settings = db.get_spam_settings()
    
    if spam_settings['enabled']:
        last_post_time = db.get_last_post_time(user_id)
        if last_post_time:
            time_diff = datetime.now() - last_post_time
            if time_diff < timedelta(minutes=spam_settings['minutes']):
                remaining = spam_settings['minutes'] - int(time_diff.total_seconds() / 60)
                await message.answer(
                    f"⏳ Зачекайте ще {remaining} хв. перед наступним постом.",
                    reply_markup=get_write_another_post_keyboard()
                )
                return
    
    await message.answer(
        f"📢 <b>{channel}</b>\n\nНадішліть пост:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(UserStates.waiting_for_post)

@dp.message(UserStates.waiting_for_post)
async def handle_post_content(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
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
        
        if album_data[album_key]['task']:
            album_data[album_key]['task'].cancel()
        
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
    
    if message.photo:
        await state.update_data(photo=message.photo[-1].file_id, caption=message.caption or '', has_content=True)
        await message.answer("📸 Фото отримано!\n\nОбери дію:", reply_markup=get_confirm_keyboard())
        await state.set_state(UserStates.confirming_post)
        return
    
    if message.video:
        await state.update_data(video=message.video.file_id, caption=message.caption or '', has_content=True)
        await message.answer("🎥 Відео отримано!\n\nОбери дію:", reply_markup=get_confirm_keyboard())
        await state.set_state(UserStates.confirming_post)
        return
    
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
    
    spam_settings = db.get_spam_settings()
    
    if spam_settings['enabled']:
        last_post_time = db.get_last_post_time(user_id)
        if last_post_time:
            time_diff = datetime.now() - last_post_time
            if time_diff < timedelta(minutes=spam_settings['minutes']):
                remaining = spam_settings['minutes'] - int(time_diff.total_seconds() / 60)
                await message.answer(
                    f"⏳ Зачекайте ще {remaining} хв. перед наступним постом.",
                    reply_markup=get_write_another_post_keyboard()
                )
                await state.clear()
                await state.update_data(channel=channel)
                return
    
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
    await message.answer(
        f"✅ Відправлено! Заявка #{post_id}",
        reply_markup=get_write_another_post_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()
    await state.update_data(channel=channel)

@dp.message(UserStates.confirming_post, F.text == "🔄 Заповнити заново")
async def restart_post_creation(message: Message, state: FSMContext):
    data = await state.get_data()
    channel = data.get('channel')
    await message.answer(
        f"🔄 Заново!\n\n📢 <b>{channel}</b>\n\nНадішліть пост:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(UserStates.waiting_for_post)

async def setup_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Почати"),
        BotCommand(command="help", description="Довідка")
    ])

async def main():
    await db.create_tables()
    
    # Очищення сирітських заявок при запуску
    orphaned_count = db.cleanup_orphaned_posts()
    if orphaned_count > 0:
        logger.info(f"🧹 Очищено {orphaned_count} сирітських заявок")
    
    load_channels_from_db()
    setup_admin_handlers(dp, bot, load_channels_from_db)
    await setup_bot_commands()
    logger.info("🚀 Бот запущено!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
