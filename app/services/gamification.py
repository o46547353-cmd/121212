from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import User, LeagueEnum, Clan

def calculate_earned_xp_and_coins(ai_analytics: dict) -> Tuple[int, int]:
    """
    Calculate XP and Coins for completing a quest.
    Base XP is 50. Base Coins is 10.
    If there are no grammar errors, give a 20 XP bonus and 5 Coins bonus.
    """
    xp = 50
    coins = 10
    grammar_errors = ai_analytics.get("grammar_errors", [])

    if not grammar_errors:
        xp += 20
        coins += 5

    return xp, coins

def process_daily_bonus(user: User) -> Tuple[User, bool, int]:
    """
    Grants a daily bonus of 20 coins if 24 hours have passed since the last bonus.
    Returns (User, success, coins_awarded).
    """
    now = datetime.now(timezone.utc)
    if not user.last_daily_bonus or (now - user.last_daily_bonus) >= timedelta(days=1):
        user.coins += 20
        user.last_daily_bonus = now
        return user, True, 20
    return user, False, 0

async def add_xp_to_clan(session: AsyncSession, clan_id: int, xp_amount: int):
    if not clan_id:
        return
    query = select(Clan).where(Clan.id == clan_id)
    result = await session.execute(query)
    clan = result.scalar_one_or_none()
    if clan:
        clan.total_xp += xp_amount

def update_user_league(user: User) -> Tuple[User, Optional[str]]:
    """
    Recalculates the user's league based on their current XP.
    Returns the updated User object and a congratulatory message if the league changed.
    """
    old_league = user.league

    if user.xp >= 5000:
        new_league = LeagueEnum.diamond
    elif user.xp >= 2500:
        new_league = LeagueEnum.platinum
    elif user.xp >= 1000:
        new_league = LeagueEnum.gold
    elif user.xp >= 500:
        new_league = LeagueEnum.silver
    else:
        new_league = LeagueEnum.bronze

    message = None
    if old_league != new_league:
        user.league = new_league
        # Only congratulate for promotions, not demotions (though XP shouldn't drop normally)
        if new_league != LeagueEnum.bronze:
            message = f"🎉 Поздравляем! Твой опыт достиг {user.xp} XP, и ты перешел в лигу: {new_league.value}!"

    return user, message
