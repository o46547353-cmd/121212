from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.models import User, RoleEnum, AgeGroupEnum, LevelEnum, TrackEnum, Quest, Subscription, Pet, Progress
from aiogram.types import FSInputFile
from app.bot.states import RegistrationState, QuestCreationState, QuestSolvingState
from app.bot.keyboards import (
    get_role_selection_kb, get_age_group_kb, get_level_kb,
    get_student_menu, get_tutor_menu, get_admin_menu, get_skip_kb, get_track_kb, get_quest_creation_menu, get_pet_shop_kb
)
from app.services.ai import analyze_student_answer
from app.services.gamification import calculate_earned_xp_and_coins, update_user_league, process_daily_bonus, add_xp_to_clan
from app.services.srs import process_ai_mistakes, get_pending_reviews, generate_srs_test
from app.services.quest_library import get_random_pop_culture_quest
from app.services.pet_shop import buy_pet_item
from app.services.tracklist import get_random_track
from app.services.audio import fetch_itunes_preview, generate_listening_audio, get_random_listening_text
from app.services.duolingo import get_random_duolingo_question
from sqlalchemy import update
from app.db.models import Clan
import os

router = Router()

# ================= REGISTRATION & START =================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = user_query.scalar_one_or_none()

    if user:
        if user.role == RoleEnum.admin:
            await message.answer("🔐 <b>Добро пожаловать в Панель Админа!</b>", reply_markup=get_admin_menu())
        elif user.role == RoleEnum.tutor:
            await message.answer("👨‍🏫 <b>Добро пожаловать, Репетитор!</b>", reply_markup=get_tutor_menu())
        else:
            await message.answer("🎒 <b>С возвращением, Ученик!</b>", reply_markup=get_student_menu())
    else:
        await state.set_state(RegistrationState.waiting_for_role)
        await message.answer(
            "👋 <b>Добро пожаловать!</b> Выберите вашу роль, чтобы начать:",
            reply_markup=get_role_selection_kb()
        )

@router.callback_query(RegistrationState.waiting_for_role, F.data.startswith("role_"))
async def process_role_selection(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    await state.update_data(role=role)

    if role == "student":
        await state.set_state(RegistrationState.waiting_for_age_group)
        await callback.message.edit_text("🎯 Выберите вашу <b>возрастную группу</b>:", reply_markup=get_age_group_kb())
    else:
        await state.set_state(RegistrationState.waiting_for_full_name)
        await callback.message.edit_text("📝 Введите ваше <b>полное имя</b>:")

@router.callback_query(RegistrationState.waiting_for_age_group, F.data.startswith("age_"))
async def process_age_group(callback: CallbackQuery, state: FSMContext):
    age_group = callback.data.split("_")[1]
    await state.update_data(age_group=age_group)

    await state.set_state(RegistrationState.waiting_for_level)
    await callback.message.edit_text("📈 Выберите ваш <b>уровень английского</b>:", reply_markup=get_level_kb())

@router.callback_query(RegistrationState.waiting_for_level, F.data.startswith("level_"))
async def process_level(callback: CallbackQuery, state: FSMContext):
    level = callback.data.split("_")[1]
    await state.update_data(level=level)

    await state.set_state(RegistrationState.waiting_for_tutor_id)
    await callback.message.edit_text(
        "🔗 Введите <b>ID вашего репетитора</b> (если есть), или нажмите «Пропустить»:",
        reply_markup=get_skip_kb()
    )

@router.message(RegistrationState.waiting_for_tutor_id)
@router.callback_query(RegistrationState.waiting_for_tutor_id, F.data == "skip")
async def process_tutor_id(event: Message | CallbackQuery, state: FSMContext):
    tutor_id = None
    if isinstance(event, Message):
        try:
            tutor_id = int(event.text)
        except ValueError:
            await event.answer("⚠️ Пожалуйста, введите корректный <b>ID репетитора (число)</b> или используйте кнопку «Пропустить».")
            return

    await state.update_data(tutor_id=tutor_id)
    await state.set_state(RegistrationState.waiting_for_full_name)

    if isinstance(event, Message):
        await event.answer("Отлично! Теперь введите ваше <b>полное имя</b>:")
    else:
        await event.message.edit_text("Отлично! Теперь введите ваше <b>полное имя</b>:")

@router.message(RegistrationState.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    role = RoleEnum(data["role"])

    new_user = User(
        telegram_id=message.from_user.id,
        role=role,
        full_name=message.text
    )

    if role == RoleEnum.student:
        new_user.age_group = AgeGroupEnum(data.get("age_group"))
        new_user.level = LevelEnum(data.get("level"))
        new_user.tutor_id = data.get("tutor_id")

        # Add Pet for retention
        pet = Pet(name="Байт", user=new_user)
        session.add(pet)
    elif role == RoleEnum.tutor:
        # Add a default inactive subscription for tutor
        sub = Subscription(user=new_user, is_active=False)
        session.add(sub)

    session.add(new_user)
    await session.commit()
    await state.clear()

    if role == RoleEnum.tutor:
        await message.answer("Регистрация завершена! Вы репетитор.", reply_markup=get_tutor_menu())
    else:
        await message.answer(f"Регистрация завершена! Твой питомец 'Байт' ждет квестов.", reply_markup=get_student_menu())

# ================= ADMIN HANDLERS =================

@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = user_query.scalar_one_or_none()

    if user and user.role == RoleEnum.admin:
        await message.answer("Секретная панель админа активирована.", reply_markup=get_admin_menu())
    else:
        # Secretly ignored or standard response
        await message.answer("Неизвестная команда.")

@router.message(F.text == "Глобальная статистика")
async def admin_stats(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = user_query.scalar_one_or_none()
    if not user or user.role != RoleEnum.admin:
        return

    tutors_count = (await session.execute(select(func.count()).select_from(User).where(User.role == RoleEnum.tutor))).scalar()
    students_count = (await session.execute(select(func.count()).select_from(User).where(User.role == RoleEnum.student))).scalar()

    await message.answer(f"📊 Статистика платформы:\n\nРепетиторов: {tutors_count}\nУчеников: {students_count}")

# (Stub for other admin commands to save space, but functional)
@router.message(F.text.in_(["Рассылка всем", "Выдать Premium репетитору"]))
async def admin_stubs(message: Message):
    await message.answer("Функция в разработке.")

# ================= TUTOR HANDLERS =================

@router.message(F.text == "👥 Мои ученики")
async def tutor_students(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    tutor = user_query.scalar_one_or_none()
    if not tutor or tutor.role != RoleEnum.tutor:
        return

    students_query = await session.execute(select(User).where(User.tutor_id == tutor.id))
    students = students_query.scalars().all()

    if not students:
        await message.answer(f"🔍 У вас пока нет учеников. Пусть они введут ваш ID при регистрации: <code>{tutor.id}</code>")
        return

    text = "🎓 <b>Ваши ученики:</b>\n\n"
    for s in students:
        text += f"🔹 <b>{s.full_name}</b> (ID: <code>{s.id}</code>, Уровень: {s.level.value if s.level else 'N/A'})\n"
    await message.answer(text)

@router.message(F.text == "🎯 Назначить квест")
async def start_quest_creation(message: Message, state: FSMContext, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    tutor = user_query.scalar_one_or_none()
    if not tutor or tutor.role != RoleEnum.tutor:
        return

    await state.set_state(QuestCreationState.waiting_for_student_id)
    await message.answer("📝 Введите <b>ID ученика</b> (число), которому хотите назначить квест:")

@router.message(QuestCreationState.waiting_for_student_id)
async def quest_student_id(message: Message, state: FSMContext, session: AsyncSession):
    try:
        student_id = int(message.text)
    except ValueError:
        await message.answer("⚠️ ID должен быть <b>числом</b>.")
        return

    # Verify student exists and belongs to this tutor
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    tutor = user_query.scalar_one_or_none()

    student_query = await session.execute(select(User).where(User.id == student_id, User.tutor_id == tutor.id))
    student = student_query.scalar_one_or_none()

    if not student:
        await message.answer("❌ Ученик не найден или не привязан к вам.")
        return

    await state.update_data(student_id=student_id)
    await state.set_state(QuestCreationState.waiting_for_track)
    await message.answer("🗂 Выберите <b>трек квеста</b>:", reply_markup=get_track_kb())

@router.callback_query(QuestCreationState.waiting_for_track, F.data.startswith("track_"))
async def quest_track(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    track = callback.data.split("_")[1]
    await state.update_data(track=track)

    data = await state.get_data()
    student_id = data.get("student_id")

    # Check for pending SRS reviews
    pending_reviews = await get_pending_reviews(session, student_id)

    prompt_text = "✍️ <b>Отправьте текст/описание квеста</b> для ученика. Вы также можете сгенерировать случайный поп-культурный квест!"
    if pending_reviews:
        prompt_text += "\n\n⚠️ Ученику необходимо повторить (интервальное повторение):\n"
        for review in pending_reviews:
            prompt_text += f"- <i>{review}</i>\n"
        prompt_text += "\nПожалуйста, включите эти слова/темы в текст задания."

    await state.set_state(QuestCreationState.waiting_for_content)

    # Clean up the inline keyboard and send new message with reply keyboard
    await callback.message.delete()
    await callback.message.answer(prompt_text, reply_markup=get_quest_creation_menu())

@router.message(QuestCreationState.waiting_for_content)
async def quest_content(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "⬅️ Отмена":
        await state.clear()
        await message.answer("❌ Назначение квеста отменено.", reply_markup=get_tutor_menu())
        return

    content = message.text
    if message.text == "🎲 Сгенерировать квест (Поп-культура)":
        content = get_random_pop_culture_quest()
        await message.answer(f"🎲 <i>Сгенерирован квест:</i>\n\n{content}")

    data = await state.get_data()
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    tutor = user_query.scalar_one_or_none()

    quest = Quest(
        tutor_id=tutor.id,
        student_id=data["student_id"],
        track=TrackEnum(data["track"]),
        content=content
    )
    session.add(quest)
    await session.commit()
    await state.clear()

    await message.answer("✅ <b>Квест успешно назначен!</b>", reply_markup=get_tutor_menu())

@router.message(F.text == "💳 Управление подпиской")
async def tutor_subscription(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    tutor = user_query.scalar_one_or_none()
    if not tutor or tutor.role != RoleEnum.tutor:
        return

    sub_query = await session.execute(select(Subscription).where(Subscription.user_id == tutor.id))
    sub = sub_query.scalar_one_or_none()

    if sub and sub.is_active:
        await message.answer("💎 Ваша подписка: <b>АКТИВНА (Premium)</b>.")
    else:
        await message.answer("🔒 Ваша подписка: <b>НЕАКТИВНА</b>.\nСтоимость: 250 руб/мес.")

@router.message(F.text.in_(["🤖 AI-Отчеты по ученикам", "🤖 AI-Аналитика ошибок"]))
async def tutor_ai_reports(message: Message, session: AsyncSession):
    # Fetch recent progresses
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    tutor = user_query.scalar_one_or_none()

    progress_query = await session.execute(
        select(Progress).join(Quest).where(Quest.tutor_id == tutor.id).order_by(Progress.completed_at.desc()).limit(5)
    )
    progresses = progress_query.scalars().all()

    if not progresses:
        await message.answer("📭 <b>Пока нет отчетов.</b> Ученики еще не выполнили квесты.")
        return

    text = "🤖 <b>Последние AI-отчеты:</b>\n\n"
    for p in progresses:
        analytics = p.tutor_analytics or {}
        text += f"🔖 <b>Квест ID:</b> {p.quest_id}\n"
        text += f"❌ <b>Ошибки:</b> {analytics.get('grammar_errors', 'Нет данных')}\n"
        text += f"💡 <b>Совет:</b> <i>{analytics.get('next_lesson_advice', '')}</i>\n"
        text += "〰️〰️〰️\n"

    await message.answer(text)

# ================= STUDENT HANDLERS =================

@router.message(F.text == "⚔️ Мои квесты")
async def student_quests(message: Message, state: FSMContext, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    student = user_query.scalar_one_or_none()
    if not student or student.role != RoleEnum.student:
        return

    quests_query = await session.execute(select(Quest).where(Quest.student_id == student.id, Quest.is_completed == False))
    quests = quests_query.scalars().all()

    if not quests:
        await message.answer("🎉 <b>У тебя пока нет активных квестов! Отдыхай.</b>")
        return

    # Get the first one for simplicity
    q = quests[0]
    await state.update_data(current_quest_id=q.id)
    await state.set_state(QuestSolvingState.waiting_for_answer)

    await message.answer(f"⚔️ <b>Твой активный квест</b> (Трек: <i>{q.track.value}</i>):\n\n<blockquote>{q.content}</blockquote>\n\n✍️ <i>Напиши свой ответ ниже:</i>")

@router.message(QuestSolvingState.waiting_for_answer)
async def solve_quest(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    quest_id = data["current_quest_id"]

    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    student = user_query.scalar_one_or_none()

    quest_query = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = quest_query.scalar_one_or_none()

    if not quest:
        await state.clear()
        return

    # Call AI
    await message.answer("⏳ <b>Анализирую твой ответ с помощью AI...</b>")

    age_group = student.age_group.value if student.age_group else "unknown"
    level = student.level.value if student.level else "unknown"

    ai_result = await analyze_student_answer(message.text, quest.content, age_group, level)

    progress = Progress(
        quest_id=quest.id,
        student_id=student.id,
        student_answer=message.text,
        student_feedback=ai_result.get("student_feedback"),
        tutor_analytics=ai_result.get("tutor_analytics")
    )

    quest.is_completed = True
    student.streak += 1
    student.streak_days += 1

    # Process SRS mistakes
    tutor_analytics = ai_result.get("tutor_analytics", {})
    await process_ai_mistakes(session, student.id, tutor_analytics)

    # Process Gamification XP, Coins, League and Clan
    earned_xp, earned_coins = calculate_earned_xp_and_coins(tutor_analytics)
    student.xp += earned_xp
    student.coins += earned_coins
    student, league_msg = update_user_league(student)

    if student.clan_id:
        await add_xp_to_clan(session, student.clan_id, earned_xp)

    # Increase pet happiness/health
    pet_query = await session.execute(select(Pet).where(Pet.user_id == student.id))
    pet = pet_query.scalar_one_or_none()
    if pet:
        pet.happiness = min(100, pet.happiness + 10)
        pet.health = min(100, pet.health + 5)

    session.add(progress)
    await session.commit()
    await state.clear()

    feedback = ai_result.get('student_feedback', 'Отлично выполнено!')
    xp_msg = f"\n\n✨ <b>Награда:</b> +{earned_xp} XP и +{earned_coins} 🪙!\nТекущий опыт: <code>{student.xp} XP</code> | Монеты: <code>{student.coins} 🪙</code>"

    final_msg = f"✅ <b>Квест сдан!</b>\n\n<b>🤖 AI Фидбек:</b>\n<i>{feedback}</i>{xp_msg}"
    if league_msg:
        final_msg += f"\n\n{league_msg}"

    await message.answer(final_msg)

@router.message(F.text == "📊 Мой прогресс (AI-анализ)")
async def student_progress(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    student = user_query.scalar_one_or_none()
    if not student or student.role != RoleEnum.student:
        return

    await message.answer(f"🔥 <b>Твой стрейк:</b> <code>{student.streak} дней подряд!</code> Так держать!")

@router.message(F.text == "👤 Мой профиль")
async def student_profile(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    student = user_query.scalar_one_or_none()

    pet_query = await session.execute(select(Pet).where(Pet.user_id == student.id))
    pet = pet_query.scalar_one_or_none()

    pet_info = f"🐾 <b>Питомец:</b> {pet.name}\n❤️ <b>Здоровье:</b> {pet.health}%\n😊 <b>Счастье:</b> {pet.happiness}%" if pet else "Нет питомца"

    league_val = student.league.value if student.league else "Бронза"

    await message.answer(
        f"👤 <b>Профиль:</b> {student.full_name}\n"
        f"📈 <b>Уровень:</b> {student.level.value if student.level else '?'}\n"
        f"🏆 <b>Лига:</b> {league_val}\n"
        f"✨ <b>Опыт:</b> {student.xp} XP\n"
        f"🪙 <b>Монеты:</b> {student.coins}\n"
        f"🔥 <b>Стрейк:</b> {student.streak_days} дней\n\n"
        f"{pet_info}"
    )

# ================= NEW FEATURES (STUDENT & TUTOR) =================

@router.message(F.text == "🎁 Ежедневный бонус")
async def student_daily_bonus(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    student = user_query.scalar_one_or_none()
    if not student or student.role != RoleEnum.student:
        return

    student, success, coins = process_daily_bonus(student)
    await session.commit()

    if success:
        await message.answer(f"🎁 <b>Ежедневный бонус получен!</b>\nВам начислено <code>{coins} 🪙</code>. Заходите завтра!")
    else:
        await message.answer("⏳ <b>Бонус уже получен.</b> Возвращайтесь через 24 часа!")

@router.message(F.text == "🛍️ Магазин питомца")
async def student_pet_shop(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    student = user_query.scalar_one_or_none()
    if not student or student.role != RoleEnum.student:
        return

    await message.answer(f"🛍️ <b>Добро пожаловать в Магазин!</b>\nУ вас: <code>{student.coins} 🪙</code>\n\nКупите что-нибудь для своего питомца:", reply_markup=get_pet_shop_kb())

@router.callback_query(F.data.startswith("buy_"))
async def process_pet_shop_buy(callback: CallbackQuery, session: AsyncSession):
    item_id = callback.data.split("_")[1]

    user_query = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    student = user_query.scalar_one_or_none()

    pet_query = await session.execute(select(Pet).where(Pet.user_id == student.id))
    pet = pet_query.scalar_one_or_none()

    if not pet:
        await callback.answer("У вас нет питомца!", show_alert=True)
        return

    success, msg = buy_pet_item(student, pet, item_id)
    if success:
        await session.commit()
        await callback.message.edit_text(f"🛍️ {msg}\nОстаток монет: <code>{student.coins} 🪙</code>")
    else:
        await callback.answer(msg, show_alert=True)

@router.message(F.text == "🧠 Карточки SRS (Повторение)")
async def student_srs_cards(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    student = user_query.scalar_one_or_none()
    if not student or student.role != RoleEnum.student:
        return

    text = await generate_srs_test(session, student.id)
    await message.answer(text)

@router.message(F.text == "🛡️ Мой Клан")
async def student_clan(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    student = user_query.scalar_one_or_none()
    if not student or student.role != RoleEnum.student:
        return

    if not student.clan_id:
        await message.answer("🛡️ <b>У вас пока нет Клана.</b>\nПопросите репетитора добавить вас в клан для участия в Клановых Войнах (Clan Wars)!")
        return

    clan_query = await session.execute(select(Clan).where(Clan.id == student.clan_id))
    clan = clan_query.scalar_one_or_none()

    members_query = await session.execute(select(func.count()).select_from(User).where(User.clan_id == clan.id))
    members_count = members_query.scalar()

    await message.answer(f"🛡️ <b>Клан:</b> {clan.name}\n⭐ <b>Общий опыт клана:</b> {clan.total_xp} XP\n👥 <b>Участников:</b> {members_count}")

@router.message(F.text == "🐉 AI Битва с Боссом")
async def student_boss_battle(message: Message, state: FSMContext, session: AsyncSession):
    # Boss Battle logic utilizes the hardcoded boss quests from the library.
    # We assign one to the student immediately for an epic encounter.
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    student = user_query.scalar_one_or_none()
    if not student or student.role != RoleEnum.student:
        return

    boss_prompt = "🐉 **БОСС: Смауг!** Дракон проснулся. Убеди его не сжигать твой город. Приведи 3 логичных аргумента на английском, используя условные предложения (Если ты сожжешь город, то...)."

    # Create a temporary quest for the boss
    quest = Quest(
        tutor_id=student.tutor_id or student.id,  # fallback if no tutor
        student_id=student.id,
        track=TrackEnum.writing,
        content=boss_prompt
    )
    session.add(quest)
    await session.flush() # Get ID without full commit to keep transaction active for state

    await state.update_data(current_quest_id=quest.id)
    await state.set_state(QuestSolvingState.waiting_for_answer)
    await session.commit()

    await message.answer(f"🔥 <b>AI БОСС БАТТЛ НАЧАЛСЯ!</b> 🔥\n\n<blockquote>{boss_prompt}</blockquote>\n\n⚔️ <i>Напиши свой ответ, чтобы нанести урон боссу:</i>")

@router.message(F.text == "🎵 Музыкальный Вайб")
async def student_music_vibe(message: Message, session: AsyncSession):
    track = get_random_track()
    artist = track["artist"]
    title = track["title"]

    await message.answer(f"🎵 <b>Музыкальный квест!</b>\nИщу отрывок трека: <b>{artist} — {title}</b>...")

    preview_url = await fetch_itunes_preview(artist, title)

    if preview_url:
        await message.answer_audio(
            audio=preview_url,
            caption=f"🎧 Послушай этот трек ({artist} - {title}) и опиши его вайб на английском (используй 3 прилагательных)!"
        )
    else:
        await message.answer(f"😔 Не удалось загрузить отрывок <b>{artist} — {title}</b>. Но ты всё равно можешь описать его вайб на английском!")

@router.message(F.text == "🎧 Аудирование")
async def student_listening(message: Message, session: AsyncSession):
    await message.answer("🎧 <b>Генерирую аудио...</b> Пожалуйста, подождите.")

    text = get_random_listening_text()
    audio_file_path = generate_listening_audio(text)

    # Send the audio file
    audio_file = FSInputFile(audio_file_path)
    await message.answer_voice(
        voice=audio_file,
        caption="📝 <b>Аудирование:</b> Прослушай запись и кратко перескажи ее суть на английском."
    )

    # Clean up the file after sending
    try:
        os.remove(audio_file_path)
    except Exception:
        pass

@router.message(F.text == "🦉 Тренажер слов (Duolingo)")
async def student_duolingo(message: Message, session: AsyncSession):
    question_data = get_random_duolingo_question()

    # Simple poll for Duolingo style
    await message.answer_poll(
        question=f"🦉 {question_data['question']}",
        options=question_data['options'],
        type="quiz",
        correct_option_id=question_data['correct_index'],
        is_anonymous=False
    )

@router.message(F.text == "📈 Лидерборд учеников")
async def tutor_leaderboard(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    tutor = user_query.scalar_one_or_none()
    if not tutor or tutor.role != RoleEnum.tutor:
        return

    students_query = await session.execute(
        select(User).where(User.tutor_id == tutor.id).order_by(User.xp.desc()).limit(10)
    )
    students = students_query.scalars().all()

    if not students:
        await message.answer("🔍 У вас пока нет учеников для формирования лидерборда.")
        return

    text = "🏆 <b>Топ ваших учеников по XP:</b>\n\n"
    for i, s in enumerate(students, 1):
        text += f"{i}. <b>{s.full_name}</b> — <code>{s.xp} XP</code> ({s.league.value})\n"
    await message.answer(text)

@router.message(F.text == "🏆 Создать Клан")
async def tutor_create_clan(message: Message, session: AsyncSession):
    # Minimal stub for creating a clan quickly (real app would use FSM)
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    tutor = user_query.scalar_one_or_none()
    if not tutor or tutor.role != RoleEnum.tutor:
        return

    clan_name = f"Клан Репетитора {tutor.full_name}"

    # Check if exists
    existing = await session.execute(select(Clan).where(Clan.name == clan_name))
    if existing.scalar_one_or_none():
        await message.answer("❌ Вы уже создали клан!")
        return

    new_clan = Clan(name=clan_name)
    session.add(new_clan)
    await session.commit()

    # Auto-assign all tutor's students to this clan
    await session.execute(
        update(User).where(User.tutor_id == tutor.id).values(clan_id=new_clan.id)
    )
    await session.commit()

    await message.answer(f"🏆 <b>Клан «{clan_name}» успешно создан!</b>\nВсе ваши текущие ученики добавлены в него автоматически.")

@router.message(F.text == "🛡️ Топ Кланов")
async def tutor_top_clans(message: Message, session: AsyncSession):
    user_query = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    tutor = user_query.scalar_one_or_none()
    if not tutor or tutor.role != RoleEnum.tutor:
        return

    clans_query = await session.execute(
        select(Clan).order_by(Clan.total_xp.desc()).limit(5)
    )
    clans = clans_query.scalars().all()

    if not clans:
        await message.answer("🔍 Пока нет ни одного клана на платформе.")
        return

    text = "🛡️ <b>Глобальный Топ Кланов:</b>\n\n"
    for i, c in enumerate(clans, 1):
        text += f"{i}. <b>{c.name}</b> — <code>{c.total_xp} XP</code>\n"
    await message.answer(text)

@router.message(F.text.in_(["🎧 Назначить Аудирование", "🎵 Назначить Музыку", "🦉 Назначить Тест (Duolingo)", "📢 Рассылка ученикам"]))
async def tutor_advanced_stubs(message: Message, session: AsyncSession):
    await message.answer("📢 <b>Функция в разработке:</b>\nЭто расширенная функция. Вы можете использовать обычное меню назначения квеста для текстовых заданий, пока эти модули автоматизируются в следующих патчах.")

# ================= TEST COMMAND =================

@router.message(Command("ai_test"))
async def cmd_ai_test(message: Message):
    await message.answer("Тестируем AITunnel API...")
    result = await analyze_student_answer(
        student_answer="I goes to school yesterday.",
        quest_content="Tell me about your past day.",
        age_group="teens",
        level="a2"
    )
    await message.answer(f"Результат:\n{result}")
