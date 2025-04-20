from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    full_name = Column(String)
    city = Column(String)
    position = Column(String)
    registered_at = Column(DateTime, default=datetime.utcnow)
    daily_score = Column(Integer, default=0)
    total_score = Column(Integer, default=0)
    
    answers = relationship("UserAnswer", back_populates="user")

class Question(Base):
    __tablename__ = 'questions'
    
    id = Column(Integer, primary_key=True)
    category = Column(String)
    text = Column(Text)
    correct_answer = Column(String)
    explanation = Column(Text)
    
    answers = relationship("UserAnswer", back_populates="question")

class UserAnswer(Base):
    __tablename__ = 'user_answers'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    question_id = Column(Integer, ForeignKey('questions.id'))
    answer = Column(String)
    is_correct = Column(Boolean)
    answered_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="answers")
    question = relationship("Question", back_populates="answers") 