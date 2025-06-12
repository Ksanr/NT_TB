from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()
engine = create_engine(os.getenv('DB_URL'))
SessionLocal = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    telegram_id = Column(BIGINT, primary_key=True) #id пользователя из телеграмма
    words = relationship("Word", back_populates="user")

class Word(Base):
    __tablename__ = 'words'
    id = Column(Integer, primary_key=True)
    word = Column(String)   # слово на русском языке
    translation = Column(String)    # перевод слова
    freq = Column(Integer, default=10)  # частота вызова слова
    cnt_guessed = Column(Integer, default=0)    # счётчик верных ответов подряд
    cnt_error = Column(Integer, default=0)  # счётчик ошибок подряд
    total_cnt_guessed = Column(Integer, default=0)  # общий счётчик верных ответов
    total_cnt_error = Column(Integer, default=0)    # общий счётчик ошибок
    user_id = Column(BIGINT, ForeignKey('users.telegram_id'))  # id пользователя
    user = relationship("User", back_populates="words")

# Создание таблиц в БД
Base.metadata.create_all(engine)

