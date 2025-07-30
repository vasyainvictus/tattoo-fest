# config.py
# Конфигурация приложения Flask

import os

class Config:
    # Абсолютный путь к базе данных
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "instance", "festival.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'your-secret-key-change-me'  # Замени на случайный ключ в продакшене