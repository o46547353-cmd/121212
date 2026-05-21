import pytest
from datetime import datetime, timedelta, timezone
from app.db.models import User, LeagueEnum, RoleEnum
from app.services.gamification import calculate_earned_xp_and_coins, process_daily_bonus, update_user_league

def test_calculate_earned_xp_and_coins_with_errors():
    ai_analytics = {"grammar_errors": ["Used 'is' instead of 'are'"]}
    xp, coins = calculate_earned_xp_and_coins(ai_analytics)
    assert xp == 50
    assert coins == 10

def test_calculate_earned_xp_and_coins_without_errors():
    ai_analytics = {"grammar_errors": []}
    xp, coins = calculate_earned_xp_and_coins(ai_analytics)
    assert xp == 70  # 50 base + 20 bonus
    assert coins == 15  # 10 base + 5 bonus

def test_update_user_league():
    user = User(xp=0, role=RoleEnum.student, league=LeagueEnum.bronze)

    # Stay in bronze
    user.xp = 400
    user, msg = update_user_league(user)
    assert user.league == LeagueEnum.bronze
    assert msg is None

    # Promote to silver
    user.xp = 600
    user, msg = update_user_league(user)
    assert user.league == LeagueEnum.silver
    assert "Серебро" in msg

    # Promote to diamond
    user.xp = 5500
    user, msg = update_user_league(user)
    assert user.league == LeagueEnum.diamond
    assert "Алмаз" in msg

def test_process_daily_bonus():
    user = User(coins=0)

    # First time bonus
    user, success, coins = process_daily_bonus(user)
    assert success is True
    assert coins == 20
    assert user.coins == 20
    assert user.last_daily_bonus is not None

    # Too soon
    user, success, coins = process_daily_bonus(user)
    assert success is False
    assert coins == 0
    assert user.coins == 20

    # After a day
    user.last_daily_bonus = datetime.now(timezone.utc) - timedelta(days=1, hours=1)
    user, success, coins = process_daily_bonus(user)
    assert success is True
    assert coins == 20
    assert user.coins == 40
