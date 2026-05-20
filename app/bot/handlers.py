from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.models import User, RoleEnum, AgeGroupEnum, LevelEnum, TrackEnum, Quest, Subscription, Pet, Progress
from app.bot.states import RegistrationState, QuestCreationState, QuestSolvingState
from app.bot.keyboards import (
    get_role_selection_kb, get_age_group_kb, get_level_kb,
    get_student_menu, get_tutor_menu, get_admin_menu, get_skip_kb, get_track_kb, get_quest_creation_menu
)
from app.services.ai import analyze_student_answer
from app.services.gamification import calculate_earned_xp, update_user_league
from app.services.srs import process_ai_mistakes, get_pending_reviews
from app.services.quest_library import get_random_pop_culture_quest

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

@router.message(F.text == "🤖 AI-Отчеты по ученикам")
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

    # Process Gamification XP and League
    earned_xp = calculate_earned_xp(tutor_analytics)
    student.xp += earned_xp
    student, league_msg = update_user_league(student)

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
    xp_msg = f"\n\n✨ <b>Ты заработал +{earned_xp} XP!</b> Текущий опыт: <code>{student.xp} XP</code>."

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
        f"🔥 <b>Стрейк:</b> {student.streak_days} дней\n\n"
        f"{pet_info}"
    )

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
