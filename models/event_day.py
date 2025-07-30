# models/event_day.py

from extensions import db
from sqlalchemy import CheckConstraint

class EventDay(db.Model):
    __tablename__ = 'event_days'
    id = db.Column(db.Integer, primary_key=True)
    
    # ИЗМЕНЕНИЕ: Добавляем каскадное удаление на уровне БАЗЫ ДАННЫХ
    festival_id = db.Column(db.Integer, db.ForeignKey('festivals.id', ondelete='CASCADE'), nullable=False)
    
    date = db.Column(db.Date, nullable=False)
    day_order = db.Column(db.Integer, nullable=False)

    time_slots = db.relationship('TimeSlot', backref='day', lazy=True, cascade="all, delete-orphan")


    __table_args__ = (
        CheckConstraint("day_order >= 1", name="check_day_order"),
        # Добавим UNIQUE constraint на дату в рамках одного фестиваля, чтобы избежать дублей
        db.UniqueConstraint('festival_id', 'date', name='unique_festival_date'),
    )