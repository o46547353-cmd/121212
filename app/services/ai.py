import os
import json
import httpx
import logging

logger = logging.getLogger(__name__)

AITUNNEL_BASE_URL = "https://api.aitunnel.ru/v1"

async def analyze_student_answer(student_answer: str, quest_content: str, age_group: str, level: str) -> dict:
    api_key = os.getenv("AITUNNEL_API_KEY")
    if not api_key:
        logger.error("AITUNNEL_API_KEY is not set.")
        return {
            "student_feedback": "Отличная работа! (API ключ не настроен)",
            "tutor_analytics": {"error": "API key missing"}
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = f"""
Ты — продвинутый AI-аналитик образовательного сервиса для изучения английского.
Тебе предоставлен ответ ученика на задание.

Возрастная группа: {age_group}
Уровень: {level}
Содержание задания: {quest_content}
Ответ ученика: {student_answer}

Тебе нужно сгенерировать JSON с двумя строго разными ключами:

1. "student_feedback": Эмоциональный, геймифицированный фидбек от лица персонажа (учитывая возраст и уровень). Обязательно похвали и мягко укажи на точки роста.
2. "tutor_analytics": Сухой методический разбор. Включает в себя:
   - "grammar_errors": список ошибок в грамматике
   - "misunderstanding_patterns": паттерны непонимания
   - "next_lesson_advice": совет репетитору на следующий урок

Обязательно верни только валидный JSON, без маркдаун-блоков. Пример формата:
{{
  "student_feedback": "Привет, чумба! Твой ответ просто огонь, но...",
  "tutor_analytics": {{
    "grammar_errors": ["Used 'is' instead of 'are'"],
    "misunderstanding_patterns": ["Present Perfect usage"],
    "next_lesson_advice": "Focus on irregular verbs."
  }}
}}
"""

    payload = {
        "model": "deepseek-chat", # DeepSeek V3 typically called this way or similar
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{AITUNNEL_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]

            # Clean up markdown code blocks if the model still returns them
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]

            return json.loads(content.strip())

    except httpx.HTTPError as e:
        logger.error(f"HTTP error occurred while calling AITunnel: {e}")
        return {
            "student_feedback": "Произошла ошибка при анализе ответа. Но ты всё равно молодец!",
            "tutor_analytics": {"error": f"HTTPError: {str(e)}"}
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from AITunnel: {e}")
        return {
            "student_feedback": "Произошла ошибка при анализе ответа. Но ты всё равно молодец!",
            "tutor_analytics": {"error": "Invalid JSON returned by AI"}
        }
    except Exception as e:
        logger.error(f"Unexpected error in AITunnel service: {e}")
        return {
            "student_feedback": "Произошла ошибка при анализе ответа.",
            "tutor_analytics": {"error": str(e)}
        }
