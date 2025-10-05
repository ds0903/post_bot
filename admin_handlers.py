import bcrypt
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from config import ADMIN_PASSWORD_HASH

db = Database()

class AdminStates(StatesGroup):
    in_admin_panel = State()
    selecting_channel_for_requests = State()

class ChannelManageStates(StatesGroup):
    choosing_action = State()
    selecting_channel = State()
    confirming_delete = State()
    entering_new_channel_id = State()
    entering_new_channel_name = State()
    adding_channel_name = State()
    adding_channel_id = State()

class SpamProtectionStates(StatesGroup):
    in_spam_menu = State()
    entering_delay_minutes = State()

def get_admin_menu_keyboard():
    buttons = [
        [KeyboardButton(text="📋 Заявки на модерацію")],
        [KeyboardButton(text="📊 Історія заявок")],
        [KeyboardButton(text="🔧 Керування каналами")],
        [KeyboardButton(text="🛡 Захист від спаму")],
        [KeyboardButton(text="🚪 Вийти з адмінки")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

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
        # [KeyboardButton(text="🧹 Очистити сирітські заявки")],
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
    channels = db.get_all_channels()
    buttons = []
    for channel_name in channels.keys():
        buttons.append([KeyboardButton(text=channel_name)])
    buttons.append([KeyboardButton(text="🔙 Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_confirm_keyboard_simple():
    buttons = [
        [KeyboardButton(text="✅ Підтвердити")],
        [KeyboardButton(text="❌ Скасувати")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_spam_protection_keyboard():
    buttons = [
        [KeyboardButton(text="⏱ Змінити затримку")],
        [KeyboardButton(text="🔄 Увімкнути/Вимкнути")],
        [KeyboardButton(text="📊 Поточний статус")],
        [KeyboardButton(text="🔙 Назад")]
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

def setup_admin_handlers(dp, bot: Bot, load_channels_func):
    
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
        from aiogram.types import InputMediaPhoto, InputMediaVideo
        import logging
        
        selected_channel = message.text
        logger = logging.getLogger(__name__)
        logger.info(f"Обрано канал: '{selected_channel}'")
        
        channels = db.get_all_channels()
        logger.info(f"Всі канали: {list(channels.keys())}")
        
        if selected_channel not in channels:
            logger.warning(f"Канал '{selected_channel}' не знайдено в БД")
            await message.answer("❌ Оберіть канал зі списку:", reply_markup=get_channels_with_requests_keyboard())
            return
        
        pending_posts = db.get_pending_posts_by_channel(selected_channel)
        logger.info(f"Знайдено {len(pending_posts) if pending_posts else 0} заявок")
        
        if not pending_posts:
            await message.answer(f"Немає заявок для каналу '{selected_channel}'.", reply_markup=get_channels_with_requests_keyboard())
            return
        
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
            reply_markup=get_confirm_keyboard_simple(),
            parse_mode="HTML"
        )
        await state.set_state(ChannelManageStates.adding_channel_name)

    @dp.message(ChannelManageStates.adding_channel_name, F.text == "❌ Скасувати")
    async def cancel_add_channel_name(message: Message, state: FSMContext):
        await message.answer("🔧 Керування каналами:", reply_markup=get_channel_management_keyboard())
        await state.set_state(ChannelManageStates.choosing_action)

    @dp.message(ChannelManageStates.adding_channel_name)
    async def add_channel_name_entered(message: Message, state: FSMContext):
        channel_name = message.text.strip()
        channels = db.get_all_channels()
        
        if channel_name in channels:
            await message.answer("❌ Канал з такою назвою вже існує! Введіть іншу назву:")
            return
        
        await state.update_data(new_channel_name=channel_name)
        await message.answer(
            f"Назва: <b>{channel_name}</b>\n\n"
            f"Тепер введіть ID каналу (наприклад: @channel або https://t.me/channel):",
            parse_mode="HTML"
        )
        await state.set_state(ChannelManageStates.adding_channel_id)

    @dp.message(ChannelManageStates.adding_channel_id, F.text == "❌ Скасувати")
    async def cancel_add_channel_id(message: Message, state: FSMContext):
        await message.answer("🔧 Керування каналами:", reply_markup=get_channel_management_keyboard())
        await state.set_state(ChannelManageStates.choosing_action)

    @dp.message(ChannelManageStates.adding_channel_id)
    async def add_channel_id_entered(message: Message, state: FSMContext):
        channel_link = message.text.strip()
        
        if not (channel_link.startswith('@') or 't.me/' in channel_link):
            await message.answer("❌ Невірний формат! Введіть ID у форматі @channel або https://t.me/channel")
            return
        
        if 't.me/' in channel_link:
            channel_id = '@' + channel_link.split('t.me/')[-1].strip('/')
        else:
            channel_id = channel_link
        
        data = await state.get_data()
        new_channel_name = data['new_channel_name']
        
        if db.add_channel(new_channel_name, channel_id):
            load_channels_func()
            
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
        channels = db.get_all_channels()
        if not channels:
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

    # ВАЖЛИВО: Обробники для конкретних кнопок мають йти ПЕРЕД загальним обробником
    @dp.message(ChannelManageStates.selecting_channel, F.text == "📝 Змінити назву")
    async def change_channel_name(message: Message, state: FSMContext):
        data = await state.get_data()
        channel_name = data.get('channel_to_edit')
        
        if not channel_name:
            await message.answer("❌ Помилка: канал не обрано")
            return
        
        await message.answer(
            f"Поточна назва: <b>{channel_name}</b>\n\n"
            f"Введіть нову назву:",
            reply_markup=get_confirm_keyboard_simple(),
            parse_mode="HTML"
        )
        await state.set_state(ChannelManageStates.entering_new_channel_name)

    @dp.message(ChannelManageStates.selecting_channel, F.text == "🔗 Змінити ID")
    async def change_channel_id(message: Message, state: FSMContext):
        data = await state.get_data()
        channel_name = data.get('channel_to_edit')
        
        if not channel_name:
            await message.answer("❌ Помилка: канал не обрано")
            return
            
        channels = db.get_all_channels()
        
        await message.answer(
            f"Канал: <b>{channel_name}</b>\n"
            f"Поточний ID: {channels[channel_name]}\n\n"
            f"Введіть новий ID (наприклад: @new_channel):",
            reply_markup=get_confirm_keyboard_simple(),
            parse_mode="HTML"
        )
        await state.set_state(ChannelManageStates.entering_new_channel_id)

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
        channels = db.get_all_channels()
        
        if channel_name not in channels:
            await message.answer("❌ Оберіть канал зі списку:", reply_markup=get_channels_list_keyboard())
            return
        
        data = await state.get_data()
        action_type = data.get('action_type')
        
        if action_type == 'delete':
            await state.update_data(channel_to_delete=channel_name)
            
            # Перевіряємо кількість заявок
            pending_count = len(db.get_pending_posts_by_channel(channel_name))
            
            warning_text = f"❗️ <b>Підтвердження видалення</b>\n\n" \
                          f"Ви впевнені, що хочете видалити канал:\n" \
                          f"<b>{channel_name}</b> ({channels[channel_name]})\n\n" \
                          f"⚠️ Це не видалить пости з БД, але канал буде недоступний для нових заявок."
            
            if pending_count > 0:
                warning_text += f"\n\n🗑 <b>УВАГА:</b> Буде видалено {pending_count} заявок на модерацію!"
            
            await message.answer(
                warning_text,
                reply_markup=get_confirm_keyboard_simple(),
                parse_mode="HTML"
            )
            # ВАЖЛИВО: Змінюємо стан для підтвердження видалення
            await state.set_state(ChannelManageStates.confirming_delete)
        elif action_type == 'edit':
            await state.update_data(channel_to_edit=channel_name)
            await message.answer(
                f"📝 <b>Редагувати канал:</b> {channel_name}\n\n"
                f"Поточний ID: {channels[channel_name]}\n\n"
                f"Оберіть дію:",
                reply_markup=get_channel_edit_actions_keyboard(),
                parse_mode="HTML"
            )

    @dp.message(F.text == "✅ Підтвердити")
    async def confirm_action(message: Message, state: FSMContext):
        current_state = await state.get_state()
        data = await state.get_data()
        
        if current_state == ChannelManageStates.confirming_delete.state:
            channel_name = data.get('channel_to_delete')
            if channel_name:
                # Перевіряємо кількість заявок для цього каналу
                pending_count = len(db.get_pending_posts_by_channel(channel_name))
                
                if db.delete_channel(channel_name):
                    load_channels_func()
                    
                    message_text = f"✅ Канал <b>{channel_name}</b> видалено!"
                    if pending_count > 0:
                        message_text += f"\n\n🗑 Також видалено {pending_count} заявок на модерацію."
                    
                    await message.answer(
                        message_text,
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
            old_name = data.get('channel_to_edit')
            new_name = data.get('new_channel_name')
            
            if db.rename_channel(old_name, new_name):
                load_channels_func()
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
            channel_name = data.get('channel_to_edit')
            new_id = data.get('new_channel_id')
            
            if db.update_channel(channel_name, new_id):
                load_channels_func()
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
        if current_state == ChannelManageStates.confirming_delete.state:
            await message.answer(
                "❌ Видалення скасовано.",
                reply_markup=get_channel_management_keyboard()
            )
            await state.set_state(ChannelManageStates.choosing_action)
        elif current_state and "ChannelManage" in current_state:
            await message.answer(
                "❌ Скасовано.",
                reply_markup=get_channel_management_keyboard()
            )
            await state.set_state(ChannelManageStates.choosing_action)
        elif current_state and "SpamProtection" in current_state:
            await message.answer(
                "❌ Скасовано.",
                reply_markup=get_spam_protection_keyboard()
            )
            await state.set_state(SpamProtectionStates.in_spam_menu)

    # ===== РЕДАГУВАТИ КАНАЛ =====

    @dp.message(ChannelManageStates.choosing_action, F.text == "📝 Редагувати канал")
    async def edit_channel_start(message: Message, state: FSMContext):
        channels = db.get_all_channels()
        if not channels:
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

    @dp.message(ChannelManageStates.entering_new_channel_name, F.text != "✅ Підтвердити")
    async def new_name_entered(message: Message, state: FSMContext):
        if message.text == "❌ Скасувати":
            return
            
        new_name = message.text.strip()
        channels = db.get_all_channels()
        
        if new_name in channels:
            await message.answer("❌ Канал з такою назвою вже існує! Введіть іншу назву:")
            return
        
        data = await state.get_data()
        old_name = data.get('channel_to_edit')
        
        await state.update_data(new_channel_name=new_name)
        await message.answer(
            f"📝 <b>Підтвердження зміни назви:</b>\n\n"
            f"Стара назва: <b>{old_name}</b>\n"
            f"➡️ Нова назва: <b>{new_name}</b>\n\n"
            f"ID залишається: {channels[old_name]}",
            reply_markup=get_confirm_keyboard_simple(),
            parse_mode="HTML"
        )

    @dp.message(ChannelManageStates.entering_new_channel_id, F.text != "✅ Підтвердити")
    async def new_id_entered(message: Message, state: FSMContext):
        if message.text == "❌ Скасувати":
            return
            
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
        channels = db.get_all_channels()
        
        await state.update_data(new_channel_id=channel_id)
        await message.answer(
            f"📝 <b>Підтвердження зміни ID:</b>\n\n"
            f"Канал: <b>{channel_name}</b>\n"
            f"Старий ID: {channels[channel_name]}\n"
            f"➡️ Новий ID: {channel_id}",
            reply_markup=get_confirm_keyboard_simple(),
            parse_mode="HTML"
        )

    @dp.message(F.text == "🔙 Назад")
    async def back_handler(message: Message, state: FSMContext):
        current_state = await state.get_state()
        
        if current_state == ChannelManageStates.selecting_channel.state:
            await message.answer(
                "🔧 Керування каналами:",
                reply_markup=get_channel_management_keyboard()
            )
            await state.set_state(ChannelManageStates.choosing_action)
        elif current_state in [ChannelManageStates.entering_new_channel_name.state, ChannelManageStates.entering_new_channel_id.state]:
            data = await state.get_data()
            channel_name = data.get('channel_to_edit')
            channels = db.get_all_channels()
            await message.answer(
                f"📝 <b>Редагувати канал:</b> {channel_name}\n\n"
                f"Поточний ID: {channels[channel_name]}\n\n"
                f"Оберіть дію:",
                reply_markup=get_channel_edit_actions_keyboard(),
                parse_mode="HTML"
            )
            await state.set_state(ChannelManageStates.selecting_channel)
        elif current_state == SpamProtectionStates.in_spam_menu.state:
            await message.answer("Адмін панель:", reply_markup=get_admin_menu_keyboard())
            await state.set_state(AdminStates.in_admin_panel)

    # ===== СПИСОК КАНАЛІВ =====

    @dp.message(ChannelManageStates.choosing_action, F.text == "📋 Список каналів")
    async def show_channels_list(message: Message):
        channels = db.get_all_channels()
        if not channels:
            await message.answer("❌ Немає каналів у базі даних.")
            return
        
        text = "📋 <b>Список каналів:</b>\n\n"
        for idx, (name, channel_id) in enumerate(channels.items(), 1):
            text += f"{idx}. <b>{name}</b>\n   ID: {channel_id}\n\n"
        
        await message.answer(text, parse_mode="HTML")

    # ===== ОЧИСТИТИ СИРІТСЬКІ ЗАЯВКИ =====

    @dp.message(ChannelManageStates.choosing_action, F.text == "🧹 Очистити сирітські заявки")
    async def cleanup_orphaned_posts_handler(message: Message):
        orphaned_count = db.cleanup_orphaned_posts()
        
        if orphaned_count > 0:
            await message.answer(
                f"🧹 <b>Очищено!</b>\n\n"
                f"Видалено {orphaned_count} заявок для каналів, які більше не існують.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "✅ Сирітських заявок не знайдено.\n\n"
                "Всі заявки прив'язані до існуючих каналів."
            )

    # ============= ЗАХИСТ ВІД СПАМУ =============

    @dp.message(AdminStates.in_admin_panel, F.text == "🛡 Захист від спаму")
    async def spam_protection_menu(message: Message, state: FSMContext):
        settings = db.get_spam_settings()
        status = "✅ Увімкнено" if settings['enabled'] else "❌ Вимкнено"
        
        await message.answer(
            f"🛡 <b>Захист від спаму</b>\n\n"
            f"Статус: {status}\n"
            f"Затримка: {settings['minutes']} хв.\n\n"
            f"Оберіть дію:",
            reply_markup=get_spam_protection_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(SpamProtectionStates.in_spam_menu)

    @dp.message(SpamProtectionStates.in_spam_menu, F.text == "📊 Поточний статус")
    async def show_spam_status(message: Message):
        settings = db.get_spam_settings()
        status = "✅ Увімкнено" if settings['enabled'] else "❌ Вимкнено"
        
        await message.answer(
            f"📊 <b>Поточний статус</b>\n\n"
            f"Функція: {status}\n"
            f"Затримка між постами: {settings['minutes']} хв.\n\n"
            f"{'Користувачі можуть надсилати пости не частіше ніж раз на ' + str(settings['minutes']) + ' хв.' if settings['enabled'] else 'Користувачі можуть надсилати пости без обмежень.'}",
            parse_mode="HTML"
        )

    @dp.message(SpamProtectionStates.in_spam_menu, F.text == "🔄 Увімкнути/Вимкнути")
    async def toggle_spam_protection(message: Message):
        settings = db.get_spam_settings()
        new_status = not settings['enabled']
        
        if db.set_spam_protection_enabled(new_status):
            status_text = "✅ увімкнено" if new_status else "❌ вимкнено"
            await message.answer(
                f"🔄 Захист від спаму {status_text}!",
                reply_markup=get_spam_protection_keyboard()
            )
        else:
            await message.answer("❌ Помилка зміни статусу!")

    @dp.message(SpamProtectionStates.in_spam_menu, F.text == "⏱ Змінити затримку")
    async def change_spam_delay_start(message: Message, state: FSMContext):
        settings = db.get_spam_settings()
        await message.answer(
            f"⏱ <b>Зміна затримки</b>\n\n"
            f"Поточна затримка: {settings['minutes']} хв.\n\n"
            f"Введіть нову затримку (в хвилинах):",
            reply_markup=get_confirm_keyboard_simple(),
            parse_mode="HTML"
        )
        await state.set_state(SpamProtectionStates.entering_delay_minutes)

    @dp.message(SpamProtectionStates.entering_delay_minutes, F.text != "❌ Скасувати")
    async def change_spam_delay_entered(message: Message, state: FSMContext):
        try:
            minutes = int(message.text.strip())
            if minutes < 1 or minutes > 1440:
                await message.answer("❌ Введіть число від 1 до 1440 (24 години):")
                return
            
            if db.set_spam_protection_minutes(minutes):
                await message.answer(
                    f"✅ Затримку змінено на {minutes} хв.!",
                    reply_markup=get_spam_protection_keyboard()
                )
                await state.set_state(SpamProtectionStates.in_spam_menu)
            else:
                await message.answer("❌ Помилка зміни затримки!")
        except ValueError:
            await message.answer("❌ Введіть коректне число:")

    # ============= ВИХІД З АДМІНКИ =============

    @dp.message(AdminStates.in_admin_panel, F.text == "🚪 Вийти з адмінки")
    async def exit_admin(message: Message, state: FSMContext):
        from aiogram.types import ReplyKeyboardRemove
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
        
        channels = db.get_all_channels()
        channel_id = channels.get(channel)
        
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
