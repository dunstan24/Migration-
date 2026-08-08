"""
db/models.py
SQLAlchemy ORM models — all tables in migration_db (MySQL)
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base


# ── EOI SkillSelect ──────────────────────────────────────────
class EOIRecord(Base):
    __tablename__ = "eoi_records"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    as_at_str        = Column(String(10), nullable=False, index=True)   # '03/2024'
    as_at_year       = Column(Integer, nullable=False, index=True)
    as_at_month_no   = Column(Integer, nullable=False)
    visa_type        = Column(String(10), nullable=False, index=True)   # '190' | '491'
    visa_type_full   = Column(Text)
    anzsco_code      = Column(String(6), index=True)
    occupation_name  = Column(Text, nullable=False)
    eoi_status       = Column(String(20), nullable=False, index=True)   # SUBMITTED|INVITED|HOLD|CLOSED|LODGED
    points           = Column(Integer, nullable=False)
    count_eois       = Column(Integer, nullable=False)                  # -1 = '<20'
    state            = Column(String(5), nullable=False, index=True)
    ingested_at      = Column(DateTime, server_default=func.now())


# ── OSL Shortage ─────────────────────────────────────────────
class OSLShortage(Base):
    __tablename__ = "osl_shortage"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    year             = Column(Integer, nullable=False, index=True)
    anzsco_code      = Column(String(6), index=True)
    occupation_name  = Column(Text, nullable=False)
    state            = Column(String(5), nullable=False, index=True)
    shortage_status  = Column(String(20))     # Shortage | Recruitment Difficulty | Balance | Metropolitan
    rating           = Column(String(30))
    ingested_at      = Column(DateTime, server_default=func.now())


# ── Employment Projections ───────────────────────────────────
class EmploymentProjection(Base):
    __tablename__ = "employment_projections"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    anzsco_code      = Column(String(6), index=True)
    occupation_name  = Column(Text, nullable=False)
    employment_2024  = Column(Integer)
    projected_2029   = Column(Integer)
    projected_2034   = Column(Integer)
    growth_5yr_pct   = Column(Float)
    growth_10yr_pct  = Column(Float)
    sector           = Column(String(100))
    ingested_at      = Column(DateTime, server_default=func.now())


# ── Migration Grants ─────────────────────────────────────────
class MigrationGrant(Base):
    __tablename__ = "migration_grants"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    financial_year   = Column(String(10), nullable=False, index=True)   # '2023-24'
    stream           = Column(String(50))                                # Skilled|Family|Humanitarian|Student
    visa_subclass    = Column(String(10))
    grants           = Column(Integer)
    planning_level   = Column(Integer)
    ingested_at      = Column(DateTime, server_default=func.now())


# ── Visa Grants ──────────────────────────────────────────────
class VisaGrant(Base):
    __tablename__ = "visa_grants"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    financial_year   = Column(String(10), nullable=False, index=True)
    visa_subclass    = Column(String(10), index=True)
    visa_name        = Column(Text)
    country          = Column(String(100))
    state            = Column(String(5))
    grants           = Column(Integer)
    ingested_at      = Column(DateTime, server_default=func.now())


# ── Occupation Features (ML input) ───────────────────────────
class OccupationFeature(Base):
    __tablename__ = "occupation_features"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    anzsco_code      = Column(String(6), nullable=False, index=True)
    occupation_name  = Column(Text)
    state            = Column(String(5), nullable=False, index=True)
    shortage_count_5yr = Column(Integer)
    shortage_streak  = Column(Integer)
    eoi_pool_size    = Column(Integer)
    invitation_rate  = Column(Float)
    employment_growth= Column(Float)
    jsa_rating       = Column(String(30))
    pr_probability   = Column(Float)
    ingested_at      = Column(DateTime, server_default=func.now())


# ── Shortage Forecast (ML 2026–2030) ─────────────────────────
class ShortageForecast(Base):
    __tablename__ = "shortage_forecast"

    anzsco_code      = Column(String(6), primary_key=True, index=True)
    occupation       = Column(Text, nullable=False)
    state            = Column(String(5), primary_key=True, index=True)
    prob_2026        = Column(Float)
    prob_2027        = Column(Float)
    prob_2028        = Column(Float)
    prob_2029        = Column(Float)
    prob_2030        = Column(Float)
    ingested_at      = Column(DateTime, server_default=func.now())


# ── Shortage Unified (OSL + Forecast) ────────────────────────
class ShortageUnified(Base):
    __tablename__ = "shortage_unified"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    anzsco_code      = Column(String(6), nullable=False, index=True)
    occupation_name  = Column(Text, nullable=False)
    skill_level      = Column(Integer)
    year             = Column(Integer, nullable=False, index=True)
    state            = Column(String(5), nullable=False, index=True)
    is_shortage      = Column(Integer)  # 0/1 from OSL (NULL for forecast-only)
    prob_shortage    = Column(Float)  # from forecast (NULL for OSL-only)
    source           = Column(String(20))  # 'osl' or 'forecast'
    ingested_at      = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        # Unique constraint: one record per anzsco_code, state, year
        # Index for common queries
    )


# ── Conversation Sessions ────────────────────────────────────
class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    session_id       = Column(String(50), nullable=False, unique=True, index=True)
    user_id          = Column(String(100), nullable=True, index=True)  # For multi-user support
    title            = Column(Text, default="New Chat")
    created_at       = Column(DateTime, server_default=func.now(), index=True)
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())
    message_count    = Column(Integer, default=0)


# ── Conversation Messages ────────────────────────────────────
class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    session_id       = Column(String(50), nullable=False, index=True)
    role             = Column(String(20), nullable=False)  # 'user' | 'assistant'
    content          = Column(Text, nullable=False)
    created_at       = Column(DateTime, server_default=func.now())
    tokens_used      = Column(Integer, nullable=True)
    message_metadata = Column(Text, nullable=True)  # JSON for storing rag_results, hallucinations, etc


# ── Users (Authentication) ───────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    username         = Column(String(255), unique=True, nullable=False, index=True)
    password_hash    = Column(String(255), nullable=False)
    role             = Column(String(50), nullable=False, default="user", index=True)  # 'user' | 'admin'
    email            = Column(String(255), unique=True, nullable=False, index=True)
    profile_picture  = Column(Text, nullable=True)
    is_active        = Column(Boolean, default=True, index=True)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationship to activity logs
    activity_logs    = relationship("UserActivityLog", back_populates="user")


# ── Activity Logs (User Activity Tracking) ───────────────────
class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # NULL for failed logins
    action           = Column(String(50), nullable=False)  # 'login', 'logout', 'password_change', etc
    severity         = Column(String(20), default="info", index=True)  # 'info', 'warning', 'critical'
    timestamp        = Column(DateTime, server_default=func.now(), index=True)
    ip_address       = Column(String(45), nullable=True)
    user_agent       = Column(String(500), nullable=True)
    status           = Column(String(50), nullable=True)  # 'success', 'failed'
    details          = Column(Text, nullable=True)
    
    # Relationship to user
    user             = relationship("User", back_populates="activity_logs")
    
    # Composite indexes defined via __table_args__
    __table_args__ = (
        # These are created via SQL schema, defined here for reference
    )
