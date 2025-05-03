import os
import json
import requests
import random
import subprocess
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, url_for, redirect, session
from flask_socketio import SocketIO
from dotenv import load_dotenv
from openai import OpenAI
from flask_login import LoginManager
from flask_login import login_required, current_user
from users.models import UserFilter, db

# 📍 Определяем путь до проекта
basedir = os.path.abspath(os.path.dirname(__file__))

# ✅ Загружаем .env
load_dotenv(dotenv_path=os.path.join(basedir, '.env'))

# 🔐 Инициализация OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY не найден в .env")
client = OpenAI(api_key=OPENAI_API_KEY)

# 📦 Ключи
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# 🚀 Flask-приложение
app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'db.sqlite3')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 💬 SocketIO
socketio = SocketIO(app)

# 🔐 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "users.login"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))  # ✅ Не используй .query.get()

# Инициализация базы данных и моделей
from users.models import db, Favorite, User, Job, ChatMessage
db.init_app(app)

with app.app_context():
    from users.models import db
    db.create_all()

# Регистрация blueprints
from users.routes import users_bp
app.register_blueprint(users_bp, url_prefix='/auth')

# Инициализация событий чата
online_users = set()

# Константы кэширования


# Вспомогательные функции

def load_global_favorites():
    print("Загрузка глобальных избранных")
    path = os.path.join(basedir, "cache", "favorites.json")
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return []

def save_global_favorites(data):
    print("Сохранение глобальных избранных")
    path = os.path.join(basedir, "cache", "favorites.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_unsplash_background():
    topics = ["freelance", "coding", "ai", "technology", "cyberpunk", "dark"]
    query = random.choice(topics)
    url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()["urls"]["full"]
    except Exception as e:
        print(f"Ошибка запроса к Unsplash: {e}")
    return url_for('static', filename='default.jpg')

# Роуты
@app.route('/')
def welcome():
    if not current_user.is_authenticated:
        print("Роут /: Пользователь не аутентифицирован, редирект на /login")
        return redirect(url_for('users.login'))
    return redirect(url_for('index'))

@app.route("/home")
def home():
    print("Переход на home страницу")
    if 'username' in session:
        if session.get('role') == 'admin':
            print("Роут /home: Пользователь - админ, редирект на admin_dashboard")
            return redirect(url_for('admin_dashboard'))
        print("Роут /home: Пользователь не админ, редирект на index")
        return redirect(url_for('index'))
    print("Роут /home: Сессия не активна, редирект на login")
    return redirect(url_for('users.login'))

@app.route("/index")
@login_required
def index():
    telegram_id = current_user.telegram_id if current_user.is_authenticated else ""
    return render_template("index.html", telegram_id=telegram_id, background=get_unsplash_background())

@app.route("/favorites")
@login_required
def favorites():
    print("Переход на favorites страницу")

    favorites_links = load_global_favorites()
    tasks = Job.query.filter(Job.link.in_(favorites_links)).all() if favorites_links else []

    # 🔢 Сортировка по числовому бюджету
    def extract_budget(task):
        try:
            return float(str(task.budget).replace("$", "").replace(",", ""))
        except Exception as e:
            print(f"Ошибка при преобразовании бюджета: {task.budget} — {e}")
            return 0

    tasks.sort(key=extract_budget)

    return render_template("favorites.html", tasks=tasks, background=get_unsplash_background())

@app.route("/simplify")
def simplify_page():
    print("Открыли страницу обработки заказов")
    return render_template("simplify.html", background=get_unsplash_background())

@app.route("/simplify_api", methods=["POST"])
def simplify_api():
    print("Вызван simplify_api")
    data = request.get_json()
    query = data.get("query", "")
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    try:
        # 1. Исправление грамматики
        correction_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты ассистент, который исправляет грамматические и стилистические ошибки в русском тексте."},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            max_tokens=500
        )
        corrected_text = correction_response.choices[0].message.content.strip()
        print(f"Исправленный текст: {corrected_text}")

        # 2. Генерация ТЗ
        task_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты помощник, который на основе текста составляет полное техническое задание (ТЗ) для исполнителя."},
                {"role": "user", "content": corrected_text}
            ],
            temperature=0.5,
            max_tokens=800
        )
        task_text = task_response.choices[0].message.content.strip()
        print(f"Сформированное ТЗ: {task_text}")

        return jsonify([{
            "title": "Сформированное Техническое Задание",
            "description": task_text,
            "budget": "-",
            "link": "#",
            "status": "new"
        }])
    except Exception as e:
        print(f"Ошибка при обращении к OpenAI: {e}")
        return jsonify([])

@app.route("/my_tasks")
@login_required
def my_tasks():
    print("Переход на страницу Мои Задания")

    tasks = Job.query.filter(
        Job.assigned_to == current_user.id,
        Job.status == "in_progress"
    ).all()

    # Сортировка по числовому значению бюджета
    def extract_budget(task):
        try:
            return float(str(task.budget).replace("$", "").replace(",", ""))
        except Exception as e:
            print(f"Ошибка при обработке бюджета: {task.budget} — {e}")
            return 0

    tasks.sort(key=extract_budget)

    print(f"Найдено {len(tasks)} активных заданий (отсортировано по бюджету)")
    return render_template("my_tasks.html", tasks=tasks, background=get_unsplash_background())

@app.route("/admin_dashboard")
@login_required
def admin_dashboard():
    print("Переход на admin_dashboard страницу")

    if current_user.role != "admin":
        return redirect(url_for("index"))

    users = User.query.all()
    analytics = [
        {
            "username": user.username,
            "taken": Job.query.filter(Job.assigned_to == user.id).count(),
            "done": Job.query.filter(Job.assigned_to == user.id, Job.status == "done").count()
        } for user in users
    ]
    jobs = Job.query.order_by(Job.id.desc()).all()

    return render_template(
        "admin_dashboard.html",
        background=get_unsplash_background(),
        users=users,
        analytics=analytics,
        online_users=list(online_users),
        jobs=jobs
    )

# Операции с заданиями
@app.route("/tasks")
@login_required
def task_list():
    print("Переход на список задач")

    show_free = request.args.get("free") == "1"
    tasks = Job.query.filter_by(status="new").all() if show_free else Job.query.all()

    # Сортировка по бюджету (как float)
    def extract_budget(task):
        try:
            return float(str(task.budget).replace("$", "").replace(",", ""))
        except Exception as e:
            print(f"Ошибка при парсинге бюджета: {task.budget} — {e}")
            return 0

    tasks.sort(key=extract_budget)

    total_count = len(tasks)
    taken_count = sum(1 for job in tasks if job.assigned_to)

    return render_template(
        "tasks.html",
        tasks=tasks,
        username=current_user.username,
        current_user_id=current_user.id,
        background=get_unsplash_background(),
        total_count=total_count,
        taken_count=taken_count,
        show_free=show_free
    )

@app.route("/task/take/<int:job_id>")
@login_required
def take_job(job_id):
    print(f"Взятие задачи: {job_id}")
    job = Job.query.get_or_404(job_id)

    if job.status == "new":
        job.status = "in_progress"
        job.assigned_to = current_user.id
        db.session.commit()
    
    return redirect(url_for("my_tasks"))

@app.route("/task/complete/<int:job_id>", methods=["POST"])
@login_required
def complete_job(job_id):
    print(f"Завершение задачи: {job_id}")
    job = Job.query.get_or_404(job_id)
    
    if job.assigned_to != current_user.id:
        return jsonify({"status": "error", "message": "Вы не назначены на это задание"}), 403
    
    if job.status == "in_progress":
        job.status = "done"
        db.session.commit()
        socketio.emit("task_completed", {
            "id": job.id,
            "title": job.title,
            "description": job.description
        })
        socketio.emit("chat message", {
            "msg": f"✅ {current_user.username} завершил задание: {job.title}",
            "time": datetime.now().strftime("%H:%M")
        }, namespace="/")
        return jsonify({"status": "completed", "task": {
            "id": job.id,
            "title": job.title,
            "description": job.description
        }})
    
    return jsonify({"status": "error", "message": "Задание не в процессе выполнения"}), 400

@app.route("/assign", methods=["POST"])
@login_required
def assign_job():
    data = request.get_json()
    link = data.get("link")

    if not link:
        return jsonify({"status": "missing link"}), 400

    job = Job.query.filter_by(link=link).first()

    if not job:
        return jsonify({"status": "job not found"}), 404
    if job.assigned_to is not None:
        return jsonify({"status": "already assigned"})

    job.assigned_to = current_user.id
    job.status = "in_progress"
    db.session.commit()

    return jsonify({"status": "assigned"})

@app.route('/search', methods=['POST'])
@login_required
def search():
    print("[START] /search вызван")
    data = request.get_json()
    print(f"Получены данные запроса: {data}")

    query = data.get("query", "")
    parts = query.split()
    topic = " ".join(parts[:-1]) if parts and parts[-1].isdigit() else query
    min_price = parts[-1] if parts and parts[-1].isdigit() else "0"

    print(f"🔍 Тема поиска: {topic} | Мин. цена: {min_price}")
    print("🚀 Одновременный запуск парсеров Upwork и Guru...")

    # Параллельный запуск двух парсеров
    try:
        from threading import Thread

        def run_parser(script):
            subprocess.run(["node", script, topic, min_price], check=True)

        upwork_thread = Thread(target=run_parser, args=("C:/Users/Mane/Desktop/Python/freelance-monitor/parsers/puppeteer_upwork.js",))
        guru_thread = Thread(target=run_parser, args=("C:/Users/Mane/Desktop/Python/freelance-monitor/parsers/puppeteer_guru.js",))

        upwork_thread.start()
        guru_thread.start()

        upwork_thread.join()
        guru_thread.join()

    except Exception as e:
        print(f"❌ Ошибка при запуске парсеров: {e}")
        return jsonify({"error": "Парсеры не запустились"}), 500

    print("📥 Загрузка результатов парсинга...")
    jobs = []
    base_path = "C:/Users/Mane/Desktop/Python/freelance-monitor/results"

    for filename in ["upwork.json", "guru.json"]:
        full_path = os.path.join(base_path, filename)
        if os.path.exists(full_path):
            with open(full_path, encoding='utf-8') as f:
                part_jobs = json.load(f)
                print(f"✅ Найдено {len(part_jobs)} в {filename}")
                jobs.extend(part_jobs)
        else:
            print(f"⚠️ Файл не найден: {filename}")

    print("💾 Сохраняем задания в БД...")
    saved = 0
    for job in jobs:
        if job.get("description") and not Job.query.filter_by(link=job['link']).first():
            new_job = Job(
                title=job.get("title", "Без названия"),
                description=job.get("description", ""),
                budget=job.get("budget", ""),
                link=job.get("link"),
                status="new",
                assigned_to=None
            )
            db.session.add(new_job)
            saved += 1
    db.session.commit()

    print(f"✅ Сохранено новых задач: {saved}")
    print("[END] Отправляем результат")
    return jsonify(jobs)



@app.route("/completions")
@login_required
def completions():
    print("Переход на страницу завершенных заданий")
    
    tasks = Job.query.filter(
        Job.assigned_to == current_user.id,
        Job.status == "done"
    ).all()
    
    return render_template("completions.html", tasks=tasks, background=get_unsplash_background())

@app.route('/api/favorite', methods=['POST'])
def api_favorite():
    print("Добавление задания в избранное")
    data = request.get_json()
    job_id = data.get("job_id")
    
    if not job_id:
        return jsonify({"status": "error", "message": "ID задания не предоставлен"}), 400
    
    favorites = load_global_favorites()
    if job_id in favorites:
        return jsonify({"status": "already"})
    
    favorites.append(job_id)
    save_global_favorites(favorites)
    return jsonify({"status": "added"})

@app.route("/logout")
def logout():
    print("Выход пользователя")
    session.clear()
    return redirect(url_for("welcome"))

@app.route('/save_filter', methods=['POST'])
@login_required
def save_filter():
    data = request.get_json()

    keywords = ','.join(data.get('keywords', []))
    min_price = data.get('min_price', 0)
    category = data.get('category', '')
    telegram_id = data.get('telegram_id', '').strip()

    # 1. Обновляем/создаём фильтр
    user_filter = UserFilter.query.filter_by(user_id=current_user.id).first()
    if not user_filter:
        user_filter = UserFilter(user_id=current_user.id)

    user_filter.keywords = keywords
    user_filter.min_price = min_price
    user_filter.category = category
    db.session.add(user_filter)

    # 2. Обновляем Telegram ID в User
    if telegram_id:
        current_user.telegram_id = telegram_id
        db.session.add(current_user)

    db.session.commit()

    return jsonify({"status": "saved"})

@app.route('/set_telegram', methods=['POST'])
@login_required
def set_telegram():
    tg_id = request.form.get('telegram_id')
    current_user.telegram_id = tg_id
    db.session.commit()
    return redirect(url_for('profile'))  # или куда хочешь

def send_telegram_to(chat_id, title, link):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❗️ Telegram token не найден в .env")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"📢 Новое задание:\n{title}\n🔗 {link}",
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"❗️ Ошибка отправки Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Telegram send error: {e}")

@app.route('/active_filters')
def get_active_filters():
    from users.models import User, UserFilter
    results = []
    for user in User.query.filter(User.telegram_id.isnot(None)).all():
        filt = UserFilter.query.filter_by(user_id=user.id).first()
        if filt:
            results.append({
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "keywords": filt.keywords.split(',') if filt.keywords else [],
                "min_price": filt.min_price,
                "category": filt.category
            })
    return jsonify(results)

@app.route('/add_to_favorites', methods=['POST'])
@login_required
def add_to_favorites():
    data = request.get_json()
    job_link = data.get("job_id")  # job_id = ссылка

    job = Job.query.filter_by(link=job_link).first()

    if job:
        favorites = load_global_favorites()
        if job.link not in favorites:
            favorites.append(job.link)
            save_global_favorites(favorites)
            return jsonify({'message': 'Добавлено в избранное'}), 200
        return jsonify({'message': 'Уже в избранном'}), 200
    return jsonify({'error': 'Задание не найдено'}), 404


# Запуск приложения
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print("✅ Админ создан: admin/admin")
    socketio.run(app, debug=True)