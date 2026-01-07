import html
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.db import Database

router = Router()
db = Database()

async def is_admin(chat: types.Chat, user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором чата."""
    if chat.type == "private":
        return True  # В ЛС всегда можно
    member = await chat.get_member(user_id)
    return member.status in ("administrator", "creator")

@router.message(Command("settings"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_settings(message: types.Message):
    if not await is_admin(message.chat, message.from_user.id):
        return

    await db.register_chat(message.chat.id, message.chat.title)
    settings = await db.get_chat_settings(message.chat.id)
    chat_title = html.escape(message.chat.title or "чат")
    
    text = (
        f"⚙️ <b>Настройки PhishGuard для чата: {chat_title}</b>\n\n"
        "<b>🛡 Режимы защиты (Mode):</b>\n"
        "• <b>Active:</b> Удаляет угрозы И пишет предупреждение в чат.\n"
        "• <b>Silent:</b> Удаляет угрозы тихо. Отчет только админу.\n\n"
        "<b>🎯 Строгость (Strict Mode):</b>\n"
        "• <b>Выкл:</b> Удаляет только 🔴 ОПАСНОЕ. Предупреждает о 🟡 ПОДОЗРИТЕЛЬНОМ.\n"
        "• <b>Вкл:</b> Удаляет и 🔴, и 🟡. Максимальная зачистка.\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Текущий статус:</b>\n"
        f"• Режим: <b>{settings['mode'].capitalize()}</b>\n"
        f"• Strict: <b>{'Включен' if settings['strict'] else 'Выключен'}</b>"
    )

    await message.answer(
        text,
        reply_markup=get_settings_keyboard(settings),
        parse_mode="HTML"
    )

def get_settings_keyboard(settings):
    builder = InlineKeyboardBuilder()
    
    # Режим защиты
    mode_text = "🌙 Перейти в Silent" if settings['mode'] == 'active' else "☀️ Перейти в Active"
    builder.row(types.InlineKeyboardButton(text=mode_text, callback_data=f"set_mode_{'silent' if settings['mode'] == 'active' else 'active'}"))
    
    # Строгий режим
    strict_text = "❌ Выключить Strict" if settings['strict'] else "🔥 Включить Strict"
    builder.row(types.InlineKeyboardButton(text=strict_text, callback_data=f"set_strict_{'0' if settings['strict'] else '1'}"))
    
    return builder.as_markup()

@router.callback_query(F.data.startswith("set_"))
async def handle_settings_callback(callback: types.CallbackQuery):
    if not callback.message:
        await callback.answer("Сообщение настроек недоступно.", show_alert=True)
        return
    if not await is_admin(callback.message.chat, callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    data = callback.data.split("_")
    action = data[1]
    value = data[2]

    if action == "mode":
        await db.update_chat_setting(callback.message.chat.id, "mode", value)
    elif action == "strict":
        await db.update_chat_setting(callback.message.chat.id, "strict", value == "1")

    settings = await db.get_chat_settings(callback.message.chat.id)
    chat_title = html.escape(callback.message.chat.title or "чат")
    
    text = (
        f"⚙️ <b>Настройки PhishGuard для чата: {chat_title}</b>\n\n"
        "<b>🛡 Режимы защиты (Mode):</b>\n"
        "• <b>Active:</b> Удаляет угрозы И пишет предупреждение в чат.\n"
        "• <b>Silent:</b> Удаляет угрозы тихо. Отчет только админу.\n\n"
        "<b>🎯 Строгость (Strict Mode):</b>\n"
        "• <b>Выкл:</b> Удаляет только 🔴 ОПАСНОЕ. Предупреждает о 🟡 ПОДОЗРИТЕЛЬНОМ.\n"
        "• <b>Вкл:</b> Удаляет и 🔴, и 🟡. Максимальная зачистка.\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Текущий статус:</b>\n"
        f"• Режим: <b>{settings['mode'].capitalize()}</b>\n"
        f"• Strict: <b>{'Включен' if settings['strict'] else 'Выключен'}</b>"
    )
    
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_settings_keyboard(settings),
            parse_mode="HTML"
        )
    except Exception:
        pass # Если текст не изменился
    
    await callback.answer("Настройки обновлены")
