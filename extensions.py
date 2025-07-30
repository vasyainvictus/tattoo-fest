# extensions.py
# Файл для хранения экземпляров расширений Flask

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()