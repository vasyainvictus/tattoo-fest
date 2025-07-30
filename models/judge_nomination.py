from extensions import db

class JudgeNomination(db.Model):
    __tablename__ = 'judge_nominations'
    id = db.Column(db.Integer, primary_key=True)
    judge_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # ГЛАВНОЕ ИЗМЕНЕНИЕ: Ссылка теперь на TimeSlot (конкурс)
    time_slot_id = db.Column(db.Integer, db.ForeignKey('time_slots.id', ondelete='CASCADE'), nullable=False)

    judge = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint('judge_id', 'time_slot_id', name='unique_judge_slot'),
    )