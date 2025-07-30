# models/festival.py

from extensions import db

class Festival(db.Model):
    __tablename__ = 'festivals'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    # ИЗМЕНЕНИЕ: Добавляем каскадное удаление на уровне ORM
    days = db.relationship('EventDay', backref='festival', lazy=True, cascade="all, delete-orphan")