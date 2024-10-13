# models.py

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Boolean, Integer, create_engine, Enum, Text, CHAR
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()

# Enums for roles and trial phases
class UserRole(enum.Enum):
    plaintiff = "plaintiff"
    defendant = "defendant"

class TrialPhase(enum.Enum):
    pre_trial = "pre_trial"
    opening_statements = "opening_statements"
    presentation_of_evidence_plaintiff = "presentation_of_evidence_plaintiff"
    presentation_of_evidence_defendant = "presentation_of_evidence_defendant"
    rebuttal = "rebuttal"
    closing_arguments = "closing_arguments"
    verdict = "verdict"

class User(Base):
    __tablename__ = 'users'
    username = Column(String, primary_key=True)

    # Relationships
    trials_as_plaintiff = relationship("Trial", back_populates="plaintiff", foreign_keys='Trial.plaintiff_id')
    trials_as_defendant = relationship("Trial", back_populates="defendant", foreign_keys='Trial.defendant_id')

class Trial(Base):
    __tablename__ = 'trials'
    trial_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    plaintiff_id = Column(String, ForeignKey('users.username'))
    defendant_id = Column(String, ForeignKey('users.username'))
    current_phase = Column(Enum(TrialPhase), default=TrialPhase.pre_trial)
    current_turn_username = Column(String, ForeignKey('users.username'))
    created_at = Column(DateTime, default=datetime.utcnow)
    motion_to_judgment_called = Column(Boolean, default=False)

    # Relationships
    plaintiff = relationship("User", foreign_keys=[plaintiff_id], back_populates="trials_as_plaintiff")
    defendant = relationship("User", foreign_keys=[defendant_id], back_populates="trials_as_defendant")
    current_turn_user = relationship("User", foreign_keys=[current_turn_username])
    transcript_entries = relationship("TranscriptEntry", back_populates="trial")
    evidence_items = relationship("Evidence", back_populates="trial")
    witnesses = relationship("Witness", back_populates="trial")
    jury_members = relationship("JuryMember", back_populates="trial")

class TranscriptEntry(Base):
    __tablename__ = 'transcript_entries'
    entry_id = Column(String, primary_key=True)
    trial_id = Column(String, ForeignKey('trials.trial_id'))
    timestamp = Column(DateTime, default=datetime.utcnow)
    speaker_username = Column(String, ForeignKey('users.username'), nullable=True)
    speaker_role = Column(String)
    content = Column(Text)
    action_type = Column(String)

    # Relationships
    trial = relationship("Trial", back_populates="transcript_entries")
    speaker = relationship("User")

class Evidence(Base):
    __tablename__ = 'evidence'
    evidence_id = Column(String, primary_key=True)
    trial_id = Column(String, ForeignKey('trials.trial_id'))
    submitted_by_username = Column(String, ForeignKey('users.username'))
    description = Column(String)
    used = Column(Boolean, default=False)

    # Relationships
    trial = relationship("Trial", back_populates="evidence_items")
    submitted_by = relationship("User")

class Witness(Base):
    __tablename__ = 'witnesses'
    witness_id = Column(String, primary_key=True)
    name = Column(String)
    trial_id = Column(String, ForeignKey('trials.trial_id'))
    called_by_username = Column(String, ForeignKey('users.username'))

    # Relationships
    trial = relationship("Trial", back_populates="witnesses")
    called_by = relationship("User")

class JuryMember(Base):
    __tablename__ = "jury_members"

    jurymember_id = Column(String, primary_key=True)
    fullname = Column(String)
    gender = Column(CHAR)
    race = Column(CHAR)
    birth_country = Column(String)
    schools = Column(String)
    political_affiliations = Column(String)
    background = Column(Text)
    hobbies = Column(Text)
    upbringing = Column(Text)
    personality = Column(Text)
    traveled_or_Lived = Column(Text)
    misc_details = Column(Text)
    trial_id = Column(String, ForeignKey('trials.trial_id'))

    # Relationships
    trial = relationship("Trial", back_populates="jury_members")

# Database setup
engine = create_engine('sqlite:///mock_trial.db', connect_args={'check_same_thread': False})
Base.metadata.create_all(engine)
DBSession = sessionmaker(bind=engine)
db_session = DBSession()
