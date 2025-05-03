import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from users.models import db, User

logger = logging.getLogger(__name__)
users_bp = Blueprint('users', __name__, template_folder='../templates')

# 🔐 Регистрация
@users_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role", "worker")

        logger.info(f"Регистрация нового пользователя: {username}")

        if not username or not password:
            flash("Введите имя и пароль", "error")
            return redirect(url_for("users.register"))

        if User.query.filter_by(username=username).first():
            flash("❌ Пользователь уже существует", "error")
            return redirect(url_for("users.register"))

        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("✅ Регистрация прошла успешно!", "success")
        return redirect(url_for("index"))

    return render_template("register.html")

# 🔑 Вход
@users_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("✅ Успешный вход", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))

        flash("❌ Неверный логин или пароль", "error")

    return render_template("login.html")

# 🚪 Выход
@users_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("🚪 Вы вышли из аккаунта", "info")
    return redirect(url_for('users.login'))
