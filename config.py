import os
from pathlib import Path

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{Path(__file__).parent / "db.sqlite3"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CACHE_PATH = 'cache/search_cache.json'
    CACHE_EXPIRATION = 300
    DEBUG = os.getenv('FLASK_ENV') == 'development'