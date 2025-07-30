# app.py
# Основной файл Flask-приложения с использованием паттерна Application Factory

from flask import Flask
from config import Config
from extensions import db, migrate

# Важно импортировать модели здесь, чтобы Alembic (Migrate) мог их видеть
from models import User, Festival, EventDay, NominationTemplate, TimeSlot, JudgeNomination, Participation, Criterion, Score, Winner

def create_app(config_class=Config):
    # Создаем экземпляр приложения
    app = Flask(__name__)
    app.config.from_object(config_class)

    @app.context_processor
    def inject_display_maps():
        CATEGORY_MAP = {
            'healed': 'Зажившая',
            'fresh': 'Битва',
            'both': 'ПЮ',
            'pro': 'Про',
            'junior': 'Юниор',
            'participant': 'Участник',
            'judge': 'Судья',
            'admin': 'Администратор'
        }
        # Делаем словарь CATEGORY_MAP доступным во всех шаблонах
        return dict(CATEGORY_MAP=CATEGORY_MAP)   

    # --- Инициализируем расширения С ПРИЛОЖЕНИЕМ ---
    # Мы связываем объекты db и migrate с нашим конкретным экземпляром app
    db.init_app(app)
    migrate.init_app(app, db)

    # --- Регистрируем наши Blueprints (маршруты) ---
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

 # ======= Telegram WebApp ========
    @app.route('/webapp')
    def webapp():
        return render_template('webapp.html')

    @app.route('/api/data', methods=['POST'])
    def handle_telegram_data():
        data = request.json
        # Здесь можно добавить логику обработки данных от Telegram
        return jsonify({"status": "success", "data": data})
    
    return app
