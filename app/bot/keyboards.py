from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_role_selection_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎒 Ученик", callback_data="role_student")
    builder.button(text="👨‍🏫 Репетитор", callback_data="role_tutor")
    builder.adjust(2)
    return builder.as_markup()

def get_age_group_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧸 Kids (7-11)", callback_data="age_kids")
    builder.button(text="🎧 Teens (12-17)", callback_data="age_teens")
    builder.button(text="💼 Adults (18+)", callback_data="age_adults")
    builder.adjust(1)
    return builder.as_markup()

def get_level_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        builder.button(text=f"📚 {level}", callback_data=f"level_{level.lower()}")
    builder.adjust(2)
    return builder.as_markup()

def get_track_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧠 Vocabulary", callback_data="track_vocabulary")
    builder.button(text="🧩 Grammar", callback_data="track_grammar")
    builder.button(text="📖 Reading", callback_data="track_reading")
    builder.button(text="✍️ Writing", callback_data="track_writing")
    builder.adjust(2)
    return builder.as_markup()

def get_student_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="⚔️ Мои квесты"), KeyboardButton(text="🐉 AI Битва с Боссом")],
        [KeyboardButton(text="📊 Мой прогресс (AI-анализ)"), KeyboardButton(text="👤 Мой профиль")],
        [KeyboardButton(text="🧠 Карточки SRS (Повторение)"), KeyboardButton(text="🎁 Ежедневный бонус")],
        [KeyboardButton(text="🛍️ Магазин питомца"), KeyboardButton(text="🛡️ Мой Клан")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_tutor_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="👥 Мои ученики"), KeyboardButton(text="🎯 Назначить квест")],
        [KeyboardButton(text="🤖 AI-Отчеты по ученикам"), KeyboardButton(text="📈 Лидерборд учеников")],
        [KeyboardButton(text="📢 Рассылка ученикам"), KeyboardButton(text="🏆 Создать Клан")],
        [KeyboardButton(text="💳 Управление подпиской")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_pet_shop_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🍔 Еда (10 🪙)", callback_data="buy_food")
    builder.button(text="🎾 Игрушка (15 🪙)", callback_data="buy_toy")
    builder.button(text="👑 Корона (100 🪙)", callback_data="buy_hat")
    builder.button(text="🕶️ Очки (50 🪙)", callback_data="buy_glasses")
    builder.adjust(2)
    return builder.as_markup()

def get_admin_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🌍 Глобальная статистика")],
        [KeyboardButton(text="📢 Рассылка всем"), KeyboardButton(text="💎 Выдать Premium репетитору")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_skip_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Пропустить", callback_data="skip")
    return builder.as_markup()

def get_quest_creation_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🎲 Сгенерировать квест (Поп-культура)")],
        [KeyboardButton(text="⬅️ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
