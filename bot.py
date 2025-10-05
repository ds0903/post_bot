import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
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
    selecting_channel_for_requests = State()

class ChannelReplaceStates(StatesGroup):
    selecting_channel_to_replace = State()
    entering_new_channel = State()

def get_channels_keyboard():
    buttons = []
    for channel_name in CHANNELS.keys():
        buttons.append([KeyboardButton(text=channel_name)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_menu_keyboard():
    buttons = [
        [KeyboardButton(text="📋 Заявки на модерацію")],
        [KeyboardButton(text="📊 Історія заявок")],
        [KeyboardButton(text="🔄 Замінити канал")],
        [KeyboardButton(text="🚪 Вийти з адмінки")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_main_menu_keyboard():
    buttons = [
        [KeyboardButton(text="✍️ Написати пост")],
        [KeyboardButton(text="🔄 Замінити канал")]
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

def get_channels_with_requests_keyboard():
    """Клавіатура з каналами, що мають заявки"""
    channels = db.get_channels_with_pending_posts()
    if not channels:
        return None
    buttons = []
    for channel in channels:
        buttons.append([KeyboardButton(text=channel)])
    buttons.append([KeyboardButton(text="🔙 Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_replace_channel_keyboard():
    """Клавіатура для вибору каналу для заміни"""
    buttons = []
    for channel_name in CHANNELS.keys():
        buttons.append([KeyboardButton(text=channel_name)])
    buttons.append([KeyboardButton(text="🔙 Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_confirm_replace_keyboard():
    """Клавіатура підтвердження заміни каналу"""
    buttons = [
        [KeyboardButton(text="✅ Підтвердити заміну")],
        [KeyboardButton(text="❌ Скасувати")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or "без_ніка"
    db.add_user(user_id, username)
    
    # Перевіряємо чи є параметр з каналом
    if command.args:
        channel_param_raw = command.args.strip()
        
        # Шукаємо канал за назвою або ID
        channel_found = None
        
        # 1. Спочатку шукаємо за назвою каналу (з заміною _ на пробіли)
        channel_param_name = channel_param_raw.replace('_', ' ')
        for channel_name in CHANNELS.keys():
            if channel_name.lower() == channel_param_name.lower() or channel_param_name.lower() in channel_name.lower():
                channel_found = channel_name
                break
        
        # 2. Якщо не знайшли за назвою, шукаємо за ID каналу (БЕЗ заміни підкреслень!)
        if not channel_found:
            # Додаємо @ якщо його немає
            search_id = channel_param_raw if channel_param_raw.startswith('@') else f'@{channel_param_raw}'
            for channel_name, channel_id in CHANNELS.items():
                if channel_id.lower() == search_id.lower():
                    channel_found = channel_name
                    break
        
        if channel_found:
            await state.update_data(channel=channel_found)
            await message.answer(
                f"👋 Вітаю!\n\n✅ Канал встановлено: <b>{channel_found}</b>\n\nОбери дію:",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Канал не знайдено.\n\n💡 Зверніться до адміністратора за правильним посиланням.",
                reply_markup=ReplyKeyboardRemove()
            )
    else:
        # Якщо параметра немає - нічого не показуємо, бо користувач має отримати спец-посилання
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

@dp.message(F.text == "✍️ Написати пост")
async def write_post_button(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get('channel'):
        await message.answer("Оберіть канал спочатку:", reply_markup=get_channels_keyboard())
        await state.set_state(UserStates.waiting_for_channel)
        return
    
    await message.answer(
        f"✅ Канал: <b>{data['channel']}</b>\n\nНадішли пост:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(UserStates.waiting_for_post)

@dp.message(UserStates.waiting_for_channel)
async def handle_channel_selection(message: Message, state: FSMContext):
    channel = message.text
    if channel not in CHANNELS:
        await message.answer("❌ Оберіть канал зі списку:", reply_markup=get_channels_keyboard())
        return
    await state.update_data(channel=channel)
    await message.answer(
        f"✅ Канал: <b>{channel}</b>\n\nОбери дію:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()

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
    await message.answer(
        f"✅ Відправлено! Заявка #{post_id}\n\nОбери дію:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.update_data(channel=channel)

@dp.message(UserStates.confirming_post, F.text == "🔄 Заповнити заново")
async def restart_post_creation(message: Message, state: FSMContext):
    data = await state.get_data()
    channel = data.get('channel')
    await message.answer(
        f"🔄 Заново!\n\n✅ Канал: <b>{channel}</b>\n\nНадішли пост:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(UserStates.waiting_for_post)

# ============= АДМІН: ЗАЯВКИ З ВИБОРОМ КАНАЛУ =============

@dp.message(AdminStates.in_admin_panel, F.text == "📋 Заявки на модерацію")
async def show_pending_posts_channels(message: Message, state: FSMContext):
    keyboard = get_channels_with_requests_keyboard()
    if not keyboard:
        await message.answer("Немає заявок на модерацію.")
        return
    
    await message.answer("Оберіть канал для перегляду заявок:", reply_markup=keyboard)
    await state.set_state(AdminStates.selecting_channel_for_requests)

@dp.message(AdminStates.selecting_channel_for_requests, F.text == "🔙 Назад")
async def back_to_admin_menu_from_channels(message: Message, state: FSMContext):
    await message.answer("Адмін панель:", reply_markup=get_admin_menu_keyboard())
    await state.set_state(AdminStates.in_admin_panel)

@dp.message(AdminStates.selecting_channel_for_requests)
async def show_pending_posts_by_channel(message: Message, state: FSMContext):
    selected_channel = message.text
    
    if selected_channel not in CHANNELS:
        await message.answer("❌ Оберіть канал зі списку:", reply_markup=get_channels_with_requests_keyboard())
        return
    
    pending_posts = db.get_pending_posts_by_channel(selected_channel)
    
    if not pending_posts:
        await message.answer(f"Немає заявок для каналу '{selected_channel}'.", reply_markup=get_channels_with_requests_keyboard())
        return
    
    from aiogram.types import InputMediaPhoto, InputMediaVideo
    
    await message.answer(f"📋 Заявки для каналу: <b>{selected_channel}</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())
    
    for post in pending_posts:
        post_id, user_id, username, channel, msg_data, created_at = post
        text = f"🆔 #{post_id}\n👤 @{username}\n📢 {channel}\n🕒 {created_at}"
        
        if msg_data.get('media_group'):
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
    
    await state.set_state(AdminStates.in_admin_panel)

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

# ============= ЗАМІНА КАНАЛУ =============

@dp.message(F.text == "🔄 Замінити канал")
async def replace_channel_start(message: Message, state: FSMContext):
    await message.answer(
        "Оберіть канал, який хочете замінити:",
        reply_markup=get_replace_channel_keyboard()
    )
    await state.set_state(ChannelReplaceStates.selecting_channel_to_replace)

@dp.message(AdminStates.in_admin_panel, F.text == "🔄 Замінити канал")
async def replace_channel_start_admin(message: Message, state: FSMContext):
    await message.answer(
        "Оберіть канал, який хочете замінити:",
        reply_markup=get_replace_channel_keyboard()
    )
    await state.set_state(ChannelReplaceStates.selecting_channel_to_replace)

@dp.message(ChannelReplaceStates.selecting_channel_to_replace, F.text == "🔙 Назад")
async def back_from_replace(message: Message, state: FSMContext):
    data = await state.get_data()
    # Перевіряємо чи це адмін
    user_id = message.from_user.id
    if db.is_admin(user_id):
        await message.answer("Адмін панель:", reply_markup=get_admin_menu_keyboard())
        await state.set_state(AdminStates.in_admin_panel)
    else:
        await message.answer("Головне меню:", reply_markup=get_main_menu_keyboard())
        await state.clear()

@dp.message(ChannelReplaceStates.selecting_channel_to_replace)
async def channel_selected_for_replace(message: Message, state: FSMContext):
    old_channel_name = message.text
    
    if old_channel_name not in CHANNELS:
        await message.answer("❌ Оберіть канал зі списку:", reply_markup=get_replace_channel_keyboard())
        return
    
    await state.update_data(old_channel_name=old_channel_name, old_channel_id=CHANNELS[old_channel_name])
    await message.answer(
        f"Ви обрали канал: <b>{old_channel_name}</b> ({CHANNELS[old_channel_name]})\n\n"
        f"Введіть нове посилання на канал (наприклад: @new_channel або https://t.me/new_channel):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(ChannelReplaceStates.entering_new_channel)

@dp.message(ChannelReplaceStates.entering_new_channel, F.text == "✅ Підтвердити заміну")
async def confirm_channel_replace(message: Message, state: FSMContext):
    data = await state.get_data()
    old_channel_name = data.get('old_channel_name')
    new_channel_id = data.get('new_channel_id')
    
    if not old_channel_name or not new_channel_id:
        await message.answer("❌ Помилка: дані не знайдено. Спробуйте ще раз.")
        return
    
    # Оновлюємо канал в конфігу
    CHANNELS[old_channel_name] = new_channel_id
    
    # Зберігаємо зміни в БД
    db.update_channel(old_channel_name, new_channel_id)
    
    user_id = message.from_user.id
    is_admin = db.is_admin(user_id)
    
    await message.answer(
        f"✅ <b>Канал успішно замінено!</b>\n\n"
        f"Канал: <b>{old_channel_name}</b>\n"
        f"Нове посилання: {new_channel_id}\n\n"
        f"⚠️ <b>ВАЖЛИВО:</b> Не забудьте додати бота до нового каналу та надати йому права адміністратора!",
        reply_markup=get_admin_menu_keyboard() if is_admin else get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    
    if is_admin:
        await state.set_state(AdminStates.in_admin_panel)
    else:
        await state.clear()

@dp.message(ChannelReplaceStates.entering_new_channel, F.text == "❌ Скасувати")
async def cancel_channel_replace(message: Message, state: FSMContext):
    user_id = message.from_user.id
    is_admin = db.is_admin(user_id)
    
    await message.answer(
        "❌ Заміну скасовано.",
        reply_markup=get_admin_menu_keyboard() if is_admin else get_main_menu_keyboard()
    )
    
    if is_admin:
        await state.set_state(AdminStates.in_admin_panel)
    else:
        await state.clear()

@dp.message(ChannelReplaceStates.entering_new_channel)
async def new_channel_entered(message: Message, state: FSMContext):
    new_channel_link = message.text.strip()
    
    # Перевірка формату
    if not (new_channel_link.startswith('@') or 't.me/' in new_channel_link):
        await message.answer("❌ Невірний формат! Введіть посилання у форматі @channel або https://t.me/channel")
        return
    
    # Нормалізуємо посилання до формату @channel
    if 't.me/' in new_channel_link:
        new_channel_id = '@' + new_channel_link.split('t.me/')[-1].strip('/')
    else:
        new_channel_id = new_channel_link
    
    data = await state.get_data()
    old_channel_name = data['old_channel_name']
    old_channel_id = data['old_channel_id']
    
    await state.update_data(new_channel_id=new_channel_id)
    
    await message.answer(
        f"📝 <b>Підтвердження заміни:</b>\n\n"
        f"Старий канал: <b>{old_channel_name}</b>\n"
        f"Старе посилання: {old_channel_id}\n\n"
        f"➡️ Нове посилання: {new_channel_id}\n\n"
        f"Підтвердіть заміну:",
        reply_markup=get_confirm_replace_keyboard(),
        parse_mode="HTML"
    )

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
