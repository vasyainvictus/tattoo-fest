# models/participation.py

from extensions import db
from datetime import datetime
from sqlalchemy import UniqueConstraint

class Participation(db.Model):
    __tablename__ = 'participations'
    
    id = db.Column(db.Integer, primary_key=True) 
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    time_slot_id = db.Column(db.Integer, db.ForeignKey('time_slots.id', ondelete='CASCADE'), nullable=False)
    entry_number = db.Column(db.Integer, nullable=False, default=1)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    scores = db.relationship('Score', backref='participation', lazy=True, cascade="all, delete-orphan")
    
    # Эта связь является главной. Она создает winner.participation
    winner = db.relationship('Winner', backref='participation', uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('user_id', 'time_slot_id', 'entry_number', name='unique_user_slot_entry'),
    )