from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from enum import Enum as PyEnum
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# 🔢 Сложность задачи
class Complexity(PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# 🧑 Пользователь
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default="worker")
    telegram_id = db.Column(db.String(50), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ⚙️ Фильтры пользователя
class UserFilter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    keywords = db.Column(db.String(255))
    min_price = db.Column(db.Integer)
    category = db.Column(db.String(100))

    user = db.relationship("User", backref="filter")

# 📌 Избранное
class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)

    user = db.relationship('User', backref='favorites', lazy='select')
    job = db.relationship('Job', backref='favorited_by', lazy='select')

    __table_args__ = (db.UniqueConstraint('user_id', 'job_id', name='unique_user_job_favorite'),)

# 📝 Сообщения чата
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref='messages', lazy='select')

# 💼 Задание
class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, default="Без названия")
    description = db.Column(db.Text, nullable=False, default="")
    budget = db.Column(db.String(50), nullable=True)
    link = db.Column(db.String(255), unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="new")
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Добавляем поле для владельца задачи

    category = db.Column(db.String(50), nullable=True)
    deadline = db.Column(db.String(50), nullable=True)
    project_type = db.Column(db.String(50), nullable=True)
    complexity = db.Column(db.Enum(Complexity), nullable=True)

    assignee = db.relationship('User', backref='assigned_jobs', lazy='select', foreign_keys=[assigned_to])
    user = db.relationship('User', backref='owned_jobs', lazy='select', foreign_keys=[user_id])  # Связь для владельца задачи

# 📤 Отправленные задачи (например, в телеграм)
class SentJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_url = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))