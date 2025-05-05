import os
import requests
import pylint.lint
from sqlalchemy import inspect

# Путь к проекту
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
APP_URL = "http://127.0.0.1:5000"

def check_code_style():
    print("=== Проверка стиля кода с помощью pylint ===")
    files_to_check = [
        os.path.join(BASE_DIR, "app.py"),
        os.path.join(BASE_DIR, "users", "models.py"),
        os.path.join(BASE_DIR, "users", "routes.py")
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"Проверяю файл: {file_path}")
            pylint_opts = ["--disable=missing-module-docstring,missing-class-docstring,missing-function-docstring"]
            pylint.lint.Run([file_path] + pylint_opts)
        else:
            print(f"Файл не найден: {file_path}")

def check_database(app, db):
    print("\n=== Проверка базы данных ===")
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        expected_tables = ["user", "job", "user_filter", "favorite", "chat_message", "sent_job"]
        
        for table in expected_tables:
            if table in tables:
                print(f"Таблица {table} существует")
                columns = [col["name"] for col in inspector.get_columns(table)]
                print(f"Столбцы в {table}: {columns}")
            else:
                print(f"Ошибка: Таблица {table} отсутствует!")

        job_columns = [col["name"] for col in inspector.get_columns("job")]
        if "user_id" not in job_columns:
            print("Ошибка: В таблице job отсутствует столбец user_id!")

def check_requests():
    print("\n=== Проверка HTTP-запросов к приложению ===")
    try:
        session = requests.Session()
        
        login_data = {"username": "admin", "password": "1234"}
        login_response = session.post(f"{APP_URL}/auth/login", data=login_data)
        if login_response.status_code != 302:
            print("Ошибка: Не удалось авторизоваться! Проверьте логин/пароль.")
            return
        
        index_response = session.get(f"{APP_URL}/index")
        if index_response.status_code == 200:
            print("Успех: Страница /index доступна.")
        else:
            print(f"Ошибка: Не удалось загрузить /index. Код ответа: {index_response.status_code}")

        print("Попытка поиска 'AI' с минимальной ценой 50...")
        search_response = session.get(f"{APP_URL}/search", params={"keywords": "AI", "min_price": 50})
        if search_response.status_code == 200:
            print("Успех: Поиск 'AI' выполнен.")
            if "AI" in search_response.text:
                print("Результаты содержат 'AI' — всё работает.")
            else:
                print("Предупреждение: Результаты поиска не содержат 'AI'. Возможно, нет подходящих задач.")
        else:
            print(f"Ошибка: Поиск не удался. Код ответа: {search_response.status_code}")

        print("Попытка поиска 'Python developer'...")
        search_response = session.get(f"{APP_URL}/search", params={"keywords": "Python developer"})
        if search_response.status_code == 200:
            print("Успех: Поиск 'Python developer' выполнен.")
            if "Python" in search_response.text:
                print("Результаты содержат 'Python' — всё работает.")
            else:
                print("Предупреждение: Результаты поиска не содержат 'Python'. Возможно, нет подходящих задач.")
        else:
            print(f"Ошибка: Поиск не удался. Код ответа: {search_response.status_code}")

    except requests.ConnectionError:
        print("Ошибка: Не удалось подключиться к приложению. Убедитесь, что оно запущено на http://127.0.0.1:5000")

def main():
    print("Запуск проверки проекта...\n")
    
    # Создаём приложение
    from app import create_app
    app = create_app()
    
    # Получаем db из контекста приложения
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy(app)

    check_code_style()
    check_database(app, db)
    check_requests()
    print("\nПроверка завершена.")

if __name__ == "__main__":
    main()