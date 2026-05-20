import enum
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, BigInteger, ForeignKey, Enum, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    student = "student"
    tutor = "tutor"
    admin = "admin"

class AgeGroupEnum(str, enum.Enum):
    kids = "kids"      # 7-11
    teens = "teens"    # 12-17
    adults = "adults"  # 18+

class LevelEnum(str, enum.Enum):
    a1 = "a1"
    a2 = "a2"
    b1 = "b1"
    b2 = "b2"
    c1 = "c1"
    c2 = "c2"

class TrackEnum(str, enum.Enum):
    vocabulary = "vocabulary"
    grammar = "grammar"
    reading = "reading"
    writing = "writing"

class LeagueEnum(str, enum.Enum):
    bronze = "Бронза"
    silver = "Серебро"
    gold = "Золото"
    platinum = "Платина"
    diamond = "Алмаз"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Specific to students
    age_group: Mapped[Optional[AgeGroupEnum]] = mapped_column(Enum(AgeGroupEnum), nullable=True)
    level: Mapped[Optional[LevelEnum]] = mapped_column(Enum(LevelEnum), nullable=True)
    tutor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    league: Mapped[LeagueEnum] = mapped_column(Enum(LeagueEnum), default=LeagueEnum.bronze)
    clan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clans.id"), nullable=True)
    last_daily_bonus: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    students: Mapped[List["User"]] = relationship("User", back_populates="tutor")
    tutor: Mapped[Optional["User"]] = relationship("User", back_populates="students", remote_side=[id])

    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="user", uselist=False)
    pet: Mapped[Optional["Pet"]] = relationship("Pet", back_populates="user", uselist=False)

    quests_assigned: Mapped[List["Quest"]] = relationship("Quest", back_populates="tutor", foreign_keys="Quest.tutor_id")
    quests_received: Mapped[List["Quest"]] = relationship("Quest", back_populates="student", foreign_keys="Quest.student_id")
    progresses: Mapped[List["Progress"]] = relationship("Progress", back_populates="student")
    mistakes: Mapped[List["UserMistake"]] = relationship("UserMistake", back_populates="user")
    clan: Mapped[Optional["Clan"]] = relationship("Clan", back_populates="members", foreign_keys=[clan_id])

class Clan(Base):
    __tablename__ = "clans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[List["User"]] = relationship("User", back_populates="clan", foreign_keys="User.clan_id")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User", back_populates="subscription")

class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tutor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    track: Mapped[TrackEnum] = mapped_column(Enum(TrackEnum))
    content: Mapped[str] = mapped_column(String)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tutor: Mapped["User"] = relationship("User", back_populates="quests_assigned", foreign_keys=[tutor_id])
    student: Mapped["User"] = relationship("User", back_populates="quests_received", foreign_keys=[student_id])
    progress: Mapped[Optional["Progress"]] = relationship("Progress", back_populates="quest", uselist=False)

class Progress(Base):
    __tablename__ = "progresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"), unique=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    student_answer: Mapped[str] = mapped_column(String)

    # JSON results from AI
    student_feedback: Mapped[Optional[dict]] = mapped_column(JSON)
    tutor_analytics: Mapped[Optional[dict]] = mapped_column(JSON)

    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    quest: Mapped["Quest"] = relationship("Quest", back_populates="progress")
    student: Mapped["User"] = relationship("User", back_populates="progresses")

class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    health: Mapped[int] = mapped_column(Integer, default=100) # Drops if quests are not done
    happiness: Mapped[int] = mapped_column(Integer, default=100)
    inventory: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # E.g., {"hat": "crown", "toy": "ball"}

    user: Mapped["User"] = relationship("User", back_populates="pet")

class UserMistake(Base):
    __tablename__ = "user_mistakes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic: Mapped[str] = mapped_column(String(255))
    mistake_count: Mapped[int] = mapped_column(Integer, default=1)
    next_review_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="mistakes")
