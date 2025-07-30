# models/winner.py

from extensions import db
from sqlalchemy import CheckConstraint

class Winner(db.Model):
    __tablename__ = 'winners'
    id = db.Column(db.Integer, primary_key=True)
    
    participation_id = db.Column(db.Integer, db.ForeignKey('participations.id', ondelete='CASCADE'), nullable=False)
    time_slot_id = db.Column(db.Integer, db.ForeignKey('time_slots.id', ondelete='CASCADE'), nullable=False)
    
    experience_category = db.Column(db.String, nullable=False)
    place = db.Column(db.Integer, nullable=False)

    # ▼▼▼ УДАЛИ ЭТУ СТРОКУ ▼▼▼
    # participation = db.relationship('Participation')
    # ▲▲▲ КОНЕЦ УДАЛЕНИЯ ▲▲▲

    __table_args__ = (
        db.UniqueConstraint('time_slot_id', 'experience_category', 'place', name='unique_winner_in_contest'),
        CheckConstraint("experience_category IN ('pro', 'junior')", name="check_winner_experience_category"),
        CheckConstraint("place BETWEEN 1 AND 3", name="check_winner_place"),
    )