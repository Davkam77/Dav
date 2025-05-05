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

        if username == 'admin':  # Запрещаем регистрацию с username='admin'
            flash("❌ Имя 'admin' зарезервировано", "error")
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
        admin_login = request.form.get("admin_login")  # Проверяем, включён ли чекбокс

        user = User.query.filter_by(username=username).first()

        # Если включён чекбокс "Администратор"
        if admin_login:
            # Вход возможен только с username='admin'
            if username != 'admin':
                flash("❌ Для входа как администратор используйте username 'admin'", "error")
                return render_template('login.html')
            if not user or not user.check_password(password) or user.role != 'admin':
                flash("❌ Неверный логин или пароль администратора", "error")
                return render_template('login.html')
            login_user(user)
            flash("✅ Успешный вход как администратор", "success")
            return redirect(url_for('admin_dashboard'))

        # Обычный вход для пользователей
        if not user or not user.check_password(password):
            flash("❌ Неверный логин или пароль", "error")
            return render_template('login.html')

        login_user(user)
        flash("✅ Успешный вход", "success")
        return redirect(url_for('index'))

    return render_template('login.html')

# 🚪 Выход
@users_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("🚪 Вы вышли из аккаунта", "info")
    return redirect(url_for('users.login'))