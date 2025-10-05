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
