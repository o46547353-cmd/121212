import random

DUOLINGO_QUESTIONS = [
    {
        "question": "Как переводится слово 'Environment'?",
        "options": ["Окружающая среда", "Развлечение", "Правительство", "Оборудование"],
        "correct_index": 0
    },
    {
        "question": "Выберите правильный перевод: 'Очевидно'",
        "options": ["Exactly", "Obviously", "Probably", "Suddenly"],
        "correct_index": 1
    },
    {
        "question": "Что означает фразовый глагол 'Give up'?",
        "options": ["Продолжать", "Отдавать", "Сдаваться", "Поднимать"],
        "correct_index": 2
    },
    {
        "question": "Вставьте пропущенное слово: I am looking forward ___ seeing you.",
        "options": ["at", "for", "to", "with"],
        "correct_index": 2
    },
    {
        "question": "Выберите синоним к слову 'Enormous'",
        "options": ["Tiny", "Huge", "Normal", "Beautiful"],
        "correct_index": 1
    }
]

def get_random_duolingo_question() -> dict:
    return random.choice(DUOLINGO_QUESTIONS)
