from aiogram.fsm.state import State, StatesGroup

class RegistrationState(StatesGroup):
    waiting_for_role = State()

    # Student specific
    waiting_for_age_group = State()
    waiting_for_level = State()
    waiting_for_tutor_id = State()

    # Common
    waiting_for_full_name = State()

class QuestCreationState(StatesGroup):
    waiting_for_student_id = State()
    waiting_for_track = State()
    waiting_for_content = State()

class QuestSolvingState(StatesGroup):
    waiting_for_answer = State()
