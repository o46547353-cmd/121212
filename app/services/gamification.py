from typing import Tuple, Optional
from app.db.models import User, LeagueEnum

def calculate_earned_xp(ai_analytics: dict) -> int:
    """
    Calculate XP for completing a quest.
    Base XP is 50. If there are no grammar errors, give a 20 XP bonus.
    """
    xp = 50
    grammar_errors = ai_analytics.get("grammar_errors", [])

    # If it's an empty list or doesn't exist, it means no errors were reported
    if not grammar_errors:
        xp += 20

    return xp

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
