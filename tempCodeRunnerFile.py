import os
import json
import requests
import subprocess
import random
from datetime import datetime
from threading import Thread
from flask import Flask, render_template, request, jsonify, url_for, redirect, session, flash
from flask_socketio import SocketIO
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv
from openai import OpenAI
from users.models import UserFilter, db, Favorite, User, Job, ChatMessage
from flask_migrate import Migrate  


# 📍 Путь до проекта
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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 🚀 Flask-приложение
app = Flask(__name__)
app.secret_key = os.urandom(24)
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
    return db.session.get(User, int(user_id))

# Инициализация базы данных
db.init_app(app)
with app.app_context():
    db.create_all()

# Инициализация миграций
migrate = Migrate(app, db)  # Добавляем инициализацию Migrate

# Регистрация blueprints
from users.routes import users_bp
app.register_blueprint(users_bp, url_prefix='/auth')


# Инициализация событий чата
online_users = set()

# Вспомогательные функции
def load_global_favorites():
    if hasattr(load_global_favorites, 'cache'):
        return load_global_favorites.cache
    path = os.path.join(basedir, "cache", "favorites.json")
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            load_global_favorites.cache = json.load(f)
    else:
        load_global_favorites.cache = []
    return load_global_favorites.cache

def save_global_favorites(data):
    path = os.path.join(basedir, "cache", "favorites.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    load_global_favorites.cache = data

def extract_budget(task):
    try:
        budget_str = str(task.budget).replace("$", "").replace(",", "").split("-")[0].strip()
        return float(budget_str) if budget_str else 0
    except Exception as e:
        app.logger.error(f"Ошибка парсинга бюджета: {task.budget} — {e}")
        return 0

def get_unsplash_background():
    topics = ["freelance", "coding", "ai", "technology", "cyberpunk", "dark"]
    url = f"https://api.unsplash.com/photos/random?query={random.choice(topics)}&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()["urls"]["full"]
    except Exception as e:
        app.logger.error(f"Ошибка запроса к Unsplash: {e}")
        return url_for('static', filename='default.jpg')

def send_telegram_message(chat_id, title, link):
    if not TELEGRAM_BOT_TOKEN:
        app.logger.warning("Telegram token не найден в .env")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"📢 Новое задание:\n{title}\n🔗 {link}",
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        app.logger.error(f"Ошибка отправки Telegram: {e}")

# Роуты
@app.route('/')
def welcome():
    if not current_user.is_authenticated:
        return redirect(url_for('users.login'))
    return redirect(url_for('index'))

@app.route("/home")
def home():
    if 'username' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))
    return redirect(url_for('users.login'))

@app.route("/index")
@login_required
def index():
    tasks = Job.query.filter_by(user_id=current_user.id, status="new").order_by(Job.budget.desc()).all()
    return render_template(
        "index.html",
        telegram_id=current_user.telegram_id or "",
        background=get_unsplash_background(),
        tasks=tasks
    )

@app.route("/favorites")
@login_required
def favorites():
    favorites_links = load_global_favorites()
    tasks = Job.query.filter(Job.link.in_(favorites_links), Job.user_id == current_user.id).order_by(Job.budget.desc()).all()
    return render_template("favorites.html", tasks=tasks, background=get_unsplash_background())

@app.route("/simplify")
def simplify_page():
    return render_template("simplify.html", background=get_unsplash_background())

@app.route("/simplify_api", methods=["POST"])
def simplify_api():
    data = request.get_json()
    query = data.get("query")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        correction = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Исправляй грамматические и стилистические ошибки в русском тексте."},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            max_tokens=500
        ).choices[0].message.content.strip()

        task = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Составляй полное техническое задание (ТЗ) для исполнителя."},
                {"role": "user", "content": correction}
            ],
            temperature=0.5,
            max_tokens=800
        ).choices[0].message.content.strip()

        return jsonify([{
            "title": "Сформированное Техническое Задание",
            "description": task,
            "budget": "-",
            "link": "#",
            "status": "new"
        }])
    except Exception as e:
        app.logger.error(f"Ошибка OpenAI: {e}")
        return jsonify({"error": "Ошибка обработки запроса"}), 500

@app.route("/my_tasks")
@login_required
def my_tasks():
    tasks = Job.query.filter(
        Job.user_id == current_user.id,
        Job.status == "in_progress"
    ).order_by(Job.budget.desc()).all()
    return render_template("my_tasks.html", tasks=tasks, background=get_unsplash_background())

@app.route("/admin_dashboard")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        return redirect(url_for("index"))
    users = User.query.all()
    analytics = [
        {
            "username": user.username,
            "taken": Job.query.filter(Job.user_id == user.id).count(),
            "done": Job.query.filter(Job.user_id == user.id, Job.status == "done").count()
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

@app.route("/tasks")
@login_required
def task_list():
    show_free = request.args.get("free") == "1"
    tasks = Job.query.filter_by(user_id=current_user.id, status="new").all() if show_free else Job.query.filter_by(user_id=current_user.id).order_by(Job.budget.desc()).all()
    return render_template("tasks.html", tasks=tasks, background=get_unsplash_background())

@app.route("/task/take/<int:job_id>")
@login_required
def take_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id or job.status != "new":
        flash("❌ Это задание недоступно или уже взято", "error")
        return redirect(url_for("tasks"))
    job.status = "in_progress"
    db.session.commit()
    flash("✅ Задание успешно взято", "success")
    return redirect(url_for("my_tasks"))

@app.route("/task/complete/<int:job_id>", methods=["POST"])
@login_required
def complete_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        return render_template("my_tasks.html", tasks=Job.query.filter(Job.user_id == current_user.id, Job.status == "in_progress").all(), background=get_unsplash_background(), error="Вы не назначены на это задание")
    if job.status == "in_progress":
        job.status = "done"
        db.session.commit()
        socketio.emit("task_completed", {
            "id": job.id,
            "title": job.title,
            "description": job.description
        })
        socketio.emit("chat_message", {
            "msg": f"✅ {current_user.username} завершил задание: {job.title}",
            "time": datetime.now().strftime("%H:%M")
        })
    return redirect(url_for("my_tasks"))

@app.route("/assign", methods=["POST"])
@login_required
def assign_job():
    data = request.get_json()
    link = data.get("link")
    if not link:
        return jsonify({"status": "missing link"}), 400
    job = Job.query.filter_by(link=link).first()
    if not job or job.user_id != current_user.id or job.assigned_to:
        return jsonify({"status": "already assigned or not yours"}), 400
    job.assigned_to = current_user.id
    job.status = "in_progress"
    db.session.commit()
    return jsonify({"status": "assigned"})

@app.route('/search', methods=['POST'])
@login_required
def search():
    data = request.get_json()
    query = data.get("query", "")
    parts = query.split()
    topic = " ".join(parts[:-1]) if parts and parts[-1].isdigit() else query
    min_price = parts[-1] if parts and parts[-1].isdigit() else "0"

    def run_parser(script):
        subprocess.run(["node", script, topic, min_price], check=True)

    try:
        upwork_thread = Thread(target=run_parser, args=("C:/Users/Mane/Desktop/Python/freelance-monitor/parsers/puppeteer_upwork.js",))
        guru_thread = Thread(target=run_parser, args=("C:/Users/Mane/Desktop/Python/freelance-monitor/parsers/puppeteer_guru.js",))
        upwork_thread.start()
        guru_thread.start()
        upwork_thread.join()
        guru_thread.join()
    except Exception as e:
        app.logger.error(f"Ошибка парсеров: {e}")
        return jsonify({"error": "Парсеры не запустились"}), 500

    jobs = []
    base_path = "C:/Users/Mane/Desktop/Python/freelance-monitor/results"
    for filename in ["upwork.json", "guru.json"]:
        full_path = os.path.join(base_path, filename)
        if os.path.exists(full_path):
            with open(full_path, encoding='utf-8') as f:
                jobs.extend(json.load(f))

    for job in jobs:
        if job.get("description") and not Job.query.filter_by(link=job['link']).first():
            new_job = Job(
                title=job.get("title", "Без названия"),
                description=job.get("description", ""),
                budget=job.get("budget", ""),
                link=job.get("link"),
                status="new",
                user_id=current_user.id
            )
            db.session.add(new_job)
    db.session.commit()

    updated_jobs = [{
        "id": job.id,
        "title": job.title,
        "budget": job.budget,
        "description": job.description,
        "link": job.link
    } for job in Job.query.filter(
    Job.user_id == current_user.id,
    Job.link.in_([j['link'] for j in jobs])
)
.all()]
    return jsonify(updated_jobs)

@app.route("/completions")
@login_required
def completions():
    tasks = Job.query.filter(
        Job.user_id == current_user.id,
        Job.status == "done"
    ).order_by(Job.budget.desc()).all()
    return render_template("completions.html", tasks=tasks, background=get_unsplash_background())

@app.route('/api/favorite', methods=['POST'])
def api_favorite():
    data = request.get_json()
    job_id = data.get("job_id")
    if not job_id:
        return jsonify({"status": "error", "message": "ID задания не предоставлен"}), 400
    favorites = load_global_favorites()
    if job_id not in favorites:
        favorites.append(job_id)
        save_global_favorites(favorites)
    return jsonify({"status": "added"})

@app.route("/logout")
def logout():
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

    user_filter = UserFilter.query.filter_by(user_id=current_user.id).first() or UserFilter(user_id=current_user.id)
    user_filter.keywords = keywords
    user_filter.min_price = min_price
    user_filter.category = category
    db.session.add(user_filter)

    if telegram_id:
        current_user.telegram_id = telegram_id
        db.session.add(current_user)
    db.session.commit()
    return jsonify({"status": "saved"})

@app.route('/active_filters')
def get_active_filters():
    results = [{
        "user_id": user.id,
        "telegram_id": user.telegram_id,
        "keywords": filt.keywords.split(',') if filt.keywords else [],
        "min_price": filt.min_price,
        "category": filt.category
    } for user in User.query.filter(User.telegram_id.isnot(None)).all() if (filt := UserFilter.query.filter_by(user_id=user.id).first())]
    return jsonify(results)

@app.route('/add_to_favorites', methods=['POST'])
@login_required
def add_to_favorites():
    data = request.get_json()
    job_link = data.get("job_id")
    job = Job.query.filter_by(link=job_link).first()
    if not job or job.user_id != current_user.id:
        return jsonify({'error': 'Задание не найдено или недоступно'}), 404
    favorites = load_global_favorites()
    if job.link not in favorites:
        favorites.append(job.link)
        save_global_favorites(favorites)
    return jsonify({'message': 'Добавлено в избранное'}), 200

# Запуск приложения
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password(os.urandom(12).hex())
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True, threaded=True)