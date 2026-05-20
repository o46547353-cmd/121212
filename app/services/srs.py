from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import UserMistake

async def process_ai_mistakes(session: AsyncSession, user_id: int, ai_analytics: dict):
    """
    Extracts mistakes from the AI analytics report and updates or creates UserMistake entries.
    Implements a basic Spaced Repetition System (SRS) interval calculation.
    """
    # Look for both grammar errors and misunderstanding patterns from the tutor_analytics JSON
    errors = ai_analytics.get("grammar_errors", [])
    patterns = ai_analytics.get("misunderstanding_patterns", [])

    all_mistake_topics = set(errors + patterns)

    for topic in all_mistake_topics:
        # Avoid empty strings
        if not topic or not isinstance(topic, str):
            continue

        topic = topic.strip()

        # Check if this mistake already exists for the user
        query = select(UserMistake).where(UserMistake.user_id == user_id, UserMistake.topic == topic)
        result = await session.execute(query)
        mistake = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if mistake:
            mistake.mistake_count += 1
            # Interval increases based on how many times they made the mistake (e.g. they clearly don't know it, review sooner)
            # Actually for SRS, if they make a mistake, interval resets. We'll set review date to tomorrow.
            mistake.next_review_date = now + timedelta(days=1)
        else:
            # First time making this mistake, review tomorrow
            new_mistake = UserMistake(
                user_id=user_id,
                topic=topic,
                mistake_count=1,
                next_review_date=now + timedelta(days=1)
            )
            session.add(new_mistake)

    # We don't commit here; let the caller handle the transaction commit

async def get_pending_reviews(session: AsyncSession, user_id: int) -> list[str]:
    """
    Fetches all mistake topics for a user that are due for review.
    """
    now = datetime.now(timezone.utc)
    query = select(UserMistake.topic).where(
        UserMistake.user_id == user_id,
        UserMistake.next_review_date <= now
    )
    result = await session.execute(query)
    topics = result.scalars().all()
    return list(topics)
