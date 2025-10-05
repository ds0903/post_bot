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
from datetime import datetime, timedelta
from database import Database
from config import BOT_TOKEN, ADMIN_PASSWORD_HASH, POST_TIME_CHECK_ENABLED, POST_DELAY_MINUTES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

# Глобальний словник каналів - завантажується з БД
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

class AdminStates(StatesGroup):
    in_admin_panel = State()
    selecting_channel_for_requests = State()

class ChannelManageStates(StatesGroup):
    choosing_action = State()
    selecting_channel = State()
    entering_new_channel_id = State()
    entering_new_channel_name = State()
    adding_channel_name = State()
    adding_channel_id = State()

def get_admin_menu_keyboard():
    buttons = [
        [KeyboardButton(text="📋 Заявки на модерацію")],
        [KeyboardButton(text="📊 Історія заявок")],
        [KeyboardButton(text="🔧 Керування каналами")],
        [KeyboardButton(text="🚪 Вийти з адмінки")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

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

def get_moderation_keyboard(post_id: int):
    buttons = [
        [
            InlineKeyboardButton(text="✅ Опублікувати", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_{post_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_channels_with_requests_keyboard():
    channels = db.get_channels_with_pending_posts()
    if not channels:
        return None
    buttons = []
    for channel in channels:
        buttons.append([KeyboardButton(text=channel)])
    buttons.append([KeyboardButton(text="🔙 Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_channel_management_keyboard():
    buttons = [
        [KeyboardButton(text="➕ Додати канал")],
        [KeyboardButton(text="📝 Редагувати канал")],
        [KeyboardButton(text="🗑 Видалити канал")],
        [KeyboardButton(text="📋 Список каналів")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_channel_edit_actions_keyboard():
    buttons = [
        [KeyboardButton(text="📝 Змінити назву")],
        [KeyboardButton(text="🔗 Змінити ID")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_channels_list_keyboard():
    buttons = []
    for channel_name in CHANNELS.keys():
        buttons.append([KeyboardButton(text=channel_name)])
    buttons.append([KeyboardButton(text="🔙 Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_confirm_keyboard_simple():
    buttons = [
        [KeyboardButton(text="✅ Підтвердити")],
        [KeyboardButton(text="❌ Скасувати")]
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

@dp.message(F.text == "✍️ Написати ще 1 пост")
async def write_another_post_button(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    channel = data.get('channel')
    
    if not channel:
        await message.answer("❌ Помилка: канал не знайдено.")
        return
    
    # Перевірка часу (якщо увімкнено)
    if POST_TIME_CHECK_ENABLED:
        last_post_time = db.get_last_post_time(user_id)
        if last_post_time:
            time_diff = datetime.now() - last_post_time
            if time_diff < timedelta(minutes=POST_DELAY_MINUTES):
                remaining = POST_DELAY_MINUTES - int(time_diff.total_seconds() / 60)
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
    
    # Перевірка часу (якщо увімкнено)
    if POST_TIME_CHECK_ENABLED:
        last_post_time = db.get_last_post_time(user_id)
        if last_post_time:
            time_diff = datetime.now() - last_post_time
            if time_diff < timedelta(minutes=POST_DELAY_MINUTES):
                remaining = POST_DELAY_MINUTES - int(time_diff.total_seconds() / 60)
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

# ============= МОДЕРАЦІЯ =============

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

# ============= КЕРУВАННЯ КАНАЛАМИ =============

@dp.message(AdminStates.in_admin_panel, F.text == "🔧 Керування каналами")
async def channel_management_menu(message: Message, state: FSMContext):
    await message.answer(
        "🔧 <b>Керування каналами</b>\n\nОберіть дію:",
        reply_markup=get_channel_management_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ChannelManageStates.choosing_action)

@dp.message(ChannelManageStates.choosing_action, F.text == "🔙 Назад")
async def back_from_channel_management(message: Message, state: FSMContext):
    await message.answer("Адмін панель:", reply_markup=get_admin_menu_keyboard())
    await state.set_state(AdminStates.in_admin_panel)

# ===== ДОДАТИ КАНАЛ =====

@dp.message(ChannelManageStates.choosing_action, F.text == "➕ Додати канал")
async def add_channel_start(message: Message, state: FSMContext):
    await message.answer(
        "➕ <b>Додати новий канал</b>\n\n"
        "Введіть назву каналу:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(ChannelManageStates.adding_channel_name)

@dp.message(ChannelManageStates.adding_channel_name)
async def add_channel_name_entered(message: Message, state: FSMContext):
    channel_name = message.text.strip()
    
    if channel_name in CHANNELS:
        await message.answer("❌ Канал з такою назвою вже існує! Введіть іншу назву:")
        return
    
    await state.update_data(new_channel_name=channel_name)
    await message.answer(
        f"Назва: <b>{channel_name}</b>\n\n"
        f"Тепер введіть ID каналу (наприклад: @channel або https://t.me/):",
        parse_mode="HTML"
    )
    await state.set_state(ChannelManageStates.adding_channel_id)

@dp.message(ChannelManageStates.adding_channel_id)
async def add_channel_id_entered(message: Message, state: FSMContext):
    channel_link = message.text.strip()
    
    if not (channel_link.startswith('@') or 't.me/' in channel_link):
        await message.answer("❌ Невірний формат! Введіть ID у форматі @channel або https://t.me/")
        return
    
    if 't.me/' in channel_link:
        channel_id = '@' + channel_link.split('t.me/')[-1].strip('/')
    else:
        channel_id = channel_link
    
    data = await state.get_data()
    new_channel_name = data['new_channel_name']
    
    # Додаємо в БД
    if db.add_channel(new_channel_name, channel_id):
        # Оновлюємо глобальний словник
        load_channels_from_db()
        
        await message.answer(
            f"✅ <b>Канал додано!</b>\n\n"
            f"Назва: <b>{new_channel_name}</b>\n"
            f"ID: {channel_id}\n\n"
            f"⚠️ <b>ВАЖЛИВО:</b> Додайте бота до каналу та надайте права адміністратора!",
            reply_markup=get_channel_management_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Помилка додавання каналу!",
            reply_markup=get_channel_management_keyboard()
        )
    
    await state.set_state(ChannelManageStates.choosing_action)

# ===== ВИДАЛИТИ КАНАЛ =====

@dp.message(ChannelManageStates.choosing_action, F.text == "🗑 Видалити канал")
async def delete_channel_start(message: Message, state: FSMContext):
    if not CHANNELS:
        await message.answer("❌ Немає каналів для видалення.")
        return
    
    await message.answer(
        "🗑 <b>Видалити канал</b>\n\n"
        "Оберіть канал для видалення:",
        reply_markup=get_channels_list_keyboard(),
        parse_mode="HTML"
    )
    await state.update_data(action_type='delete')
    await state.set_state(ChannelManageStates.selecting_channel)

@dp.message(ChannelManageStates.selecting_channel, F.text == "🔙 Назад")
async def back_from_selecting_channel(message: Message, state: FSMContext):
    await message.answer(
        "🔧 Керування каналами:",
        reply_markup=get_channel_management_keyboard()
    )
    await state.set_state(ChannelManageStates.choosing_action)

@dp.message(ChannelManageStates.selecting_channel)
async def channel_selected(message: Message, state: FSMContext):
    channel_name = message.text
    
    if channel_name not in CHANNELS:
        await message.answer("❌ Оберіть канал зі списку:", reply_markup=get_channels_list_keyboard())
        return
    
    data = await state.get_data()
    action_type = data.get('action_type')
    
    if action_type == 'delete':
        await state.update_data(channel_to_delete=channel_name)
        await message.answer(
            f"❗️ <b>Підтвердження видалення</b>\n\n"
            f"Ви впевнені, що хочете видалити канал:\n"
            f"<b>{channel_name}</b> ({CHANNELS[channel_name]})\n\n"
            f"⚠️ Це не видалить пости з БД, але канал буде недоступний для нових заявок.",
            reply_markup=get_confirm_keyboard_simple(),
            parse_mode="HTML"
        )
    elif action_type == 'edit':
        await state.update_data(channel_to_edit=channel_name)
        await message.answer(
            f"📝 <b>Редагувати канал:</b> {channel_name}\n\n"
            f"Поточний ID: {CHANNELS[channel_name]}\n\n"
            f"Оберіть дію:",
            reply_markup=get_channel_edit_actions_keyboard(),
            parse_mode="HTML"
        )

@dp.message(F.text == "✅ Підтвердити")
async def confirm_delete_channel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()
    
    if current_state == ChannelManageStates.selecting_channel.state:
        channel_name = data.get('channel_to_delete')
        if channel_name:
            if db.delete_channel(channel_name):
                # Оновлюємо глобальний словник
                load_channels_from_db()
                
                await message.answer(
                    f"✅ Канал <b>{channel_name}</b> видалено!",
                    reply_markup=get_channel_management_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "❌ Помилка видалення каналу!",
                    reply_markup=get_channel_management_keyboard()
                )
            await state.set_state(ChannelManageStates.choosing_action)
    elif current_state == ChannelManageStates.entering_new_channel_name.state:
        # Підтвердження зміни назви
        old_name = data.get('channel_to_edit')
        new_name = data.get('new_channel_name')
        
        if db.rename_channel(old_name, new_name):
            load_channels_from_db()
            await message.answer(
                f"✅ Назву каналу змінено!\n\n"
                f"Стара назва: <b>{old_name}</b>\n"
                f"Нова назва: <b>{new_name}</b>",
                reply_markup=get_channel_management_keyboard(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Помилка зміни назви!",
                reply_markup=get_channel_management_keyboard()
            )
        await state.set_state(ChannelManageStates.choosing_action)
    elif current_state == ChannelManageStates.entering_new_channel_id.state:
        # Підтвердження зміни ID
        channel_name = data.get('channel_to_edit')
        new_id = data.get('new_channel_id')
        
        if db.update_channel(channel_name, new_id):
            load_channels_from_db()
            await message.answer(
                f"✅ ID каналу змінено!\n\n"
                f"Канал: <b>{channel_name}</b>\n"
                f"Новий ID: {new_id}\n\n"
                f"⚠️ Не забудьте додати бота до нового каналу!",
                reply_markup=get_channel_management_keyboard(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Помилка зміни ID!",
                reply_markup=get_channel_management_keyboard()
            )
        await state.set_state(ChannelManageStates.choosing_action)

@dp.message(F.text == "❌ Скасувати")
async def cancel_action(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if "ChannelManage" in current_state:
        await message.answer(
            "❌ Скасовано.",
            reply_markup=get_channel_management_keyboard()
        )
        await state.set_state(ChannelManageStates.choosing_action)

# ===== РЕДАГУВАТИ КАНАЛ =====

@dp.message(ChannelManageStates.choosing_action, F.text == "📝 Редагувати канал")
async def edit_channel_start(message: Message, state: FSMContext):
    if not CHANNELS:
        await message.answer("❌ Немає каналів для редагування.")
        return
    
    await message.answer(
        "📝 <b>Редагувати канал</b>\n\n"
        "Оберіть канал:",
        reply_markup=get_channels_list_keyboard(),
        parse_mode="HTML"
    )
    await state.update_data(action_type='edit')
    await state.set_state(ChannelManageStates.selecting_channel)

@dp.message(F.text == "📝 Змінити назву")
async def change_channel_name(message: Message, state: FSMContext):
    data = await state.get_data()
    channel_name = data.get('channel_to_edit')
    
    await message.answer(
        f"Поточна назва: <b>{channel_name}</b>\n\n"
        f"Введіть нову назву:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(ChannelManageStates.entering_new_channel_name)

@dp.message(ChannelManageStates.entering_new_channel_name)
async def new_name_entered(message: Message, state: FSMContext):
    new_name = message.text.strip()
    
    if new_name in CHANNELS:
        await message.answer("❌ Канал з такою назвою вже існує! Введіть іншу назву:")
        return
    
    data = await state.get_data()
    old_name = data.get('channel_to_edit')
    
    await state.update_data(new_channel_name=new_name)
    await message.answer(
        f"📝 <b>Підтвердження зміни назви:</b>\n\n"
        f"Стара назва: <b>{old_name}</b>\n"
        f"➡️ Нова назва: <b>{new_name}</b>\n\n"
        f"ID залишається: {CHANNELS[old_name]}",
        reply_markup=get_confirm_keyboard_simple(),
        parse_mode="HTML"
    )

@dp.message(F.text == "🔗 Змінити ID")
async def change_channel_id(message: Message, state: FSMContext):
    data = await state.get_data()
    channel_name = data.get('channel_to_edit')
    
    await message.answer(
        f"Канал: <b>{channel_name}</b>\n"
        f"Поточний ID: {CHANNELS[channel_name]}\n\n"
        f"Введіть новий ID (наприклад: @new_channel):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(ChannelManageStates.entering_new_channel_id)

@dp.message(ChannelManageStates.entering_new_channel_id)
async def new_id_entered(message: Message, state: FSMContext):
    channel_link = message.text.strip()
    
    if not (channel_link.startswith('@') or 't.me/' in channel_link):
        await message.answer("❌ Невірний формат! Введіть ID у форматі @channel або https://t.me/channel")
        return
    
    if 't.me/' in channel_link:
        channel_id = '@' + channel_link.split('t.me/')[-1].strip('/')
    else:
        channel_id = channel_link
    
    data = await state.get_data()
    channel_name = data.get('channel_to_edit')
    
    await state.update_data(new_channel_id=channel_id)
    await message.answer(
        f"📝 <b>Підтвердження зміни ID:</b>\n\n"
        f"Канал: <b>{channel_name}</b>\n"
        f"Старий ID: {CHANNELS[channel_name]}\n"
        f"➡️ Новий ID: {channel_id}",
        reply_markup=get_confirm_keyboard_simple(),
        parse_mode="HTML"
    )

@dp.message(F.text == "🔙 Назад")
async def back_from_edit_actions(message: Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state == ChannelManageStates.selecting_channel.state or current_state == ChannelManageStates.entering_new_channel_name.state or current_state == ChannelManageStates.entering_new_channel_id.state:
        await message.answer(
            "🔧 Керування каналами:",
            reply_markup=get_channel_management_keyboard()
        )
        await state.set_state(ChannelManageStates.choosing_action)

# ===== СПИСОК КАНАЛІВ =====

@dp.message(ChannelManageStates.choosing_action, F.text == "📋 Список каналів")
async def show_channels_list(message: Message):
    if not CHANNELS:
        await message.answer("❌ Немає каналів у базі даних.")
        return
    
    text = "📋 <b>Список каналів:</b>\n\n"
    for idx, (name, channel_id) in enumerate(CHANNELS.items(), 1):
        text += f"{idx}. <b>{name}</b>\n   ID: {channel_id}\n\n"
    
    await message.answer(text, parse_mode="HTML")

# ============= ВИХІД З АДМІНКИ =============

@dp.message(AdminStates.in_admin_panel, F.text == "🚪 Вийти з адмінки")
async def exit_admin(message: Message, state: FSMContext):
    await message.answer("👋 Вийшли.", reply_markup=ReplyKeyboardRemove())
    await state.clear()

# ============= КОЛБЕКИ МОДЕРАЦІЇ =============

@dp.callback_query(F.data.startswith("approve_"))
async def approve_post(callback: CallbackQuery):
    from aiogram.types import InputMediaPhoto, InputMediaVideo
    post_id = int(callback.data.split("_")[1])
    post_data = db.get_post_by_id(post_id)
    if not post_data:
        return
    _, user_id, username, channel, msg_data, _ = post_data
    
    # Оновлюємо канали з БД перед публікацією
    load_channels_from_db()
    channel_id = CHANNELS.get(channel)
    
    if not channel_id:
        await callback.answer(f"❌ Канал '{channel}' не знайдено в БД!")
        return
    
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
    load_channels_from_db()  # Завантажуємо канали з БД при старті
    await setup_bot_commands()
    logger.info("🚀 Бот запущено!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
