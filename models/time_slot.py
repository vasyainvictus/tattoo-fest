from extensions import db
from sqlalchemy import CheckConstraint, UniqueConstraint

class TimeSlot(db.Model):
    __tablename__ = 'time_slots'
    
    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey('event_days.id', ondelete='CASCADE'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    slot_order = db.Column(db.Integer, nullable=False)
    
    # Тип слота: 'judging', 'award', 'event'
    type = db.Column(db.String(50), nullable=False) 

    # --- Поля для типа 'judging' (теперь это полноценный конкурс) ---
    nomination_template_id = db.Column(db.Integer, db.ForeignKey('nomination_templates.id'), nullable=True)
    category = db.Column(db.String(50), nullable=True) # 'healed' или 'fresh'
    status = db.Column(db.String(50), nullable=True, default='pending') # 'pending', 'judging', 'completed', 'awarded'
    zone = db.Column(db.String(10), nullable=True)

    # --- Поле для типа 'award' ---
    award_title = db.Column(db.String(100), nullable=True)

    # --- Поле для типа 'event' ---
    event_title = db.Column(db.String(100), nullable=True) 
    
    # --- Новые связи ---
    # Этот слот судейства связан с одним шаблоном номинации
    nomination_template = db.relationship('NominationTemplate')
    
    # В этом слоте-конкурсе есть много участников и много судей
    participants = db.relationship('Participation', backref='contest_slot', cascade="all, delete-orphan")
    judge_assignments = db.relationship('JudgeNomination', backref='contest_slot', cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('day_id', 'slot_order', name='unique_day_slot_order'),
        CheckConstraint("category IN ('healed', 'fresh')", name="check_timeslot_category"),
        CheckConstraint("status IN ('pending', 'judging', 'completed', 'awarded')", name="check_timeslot_status")
    )