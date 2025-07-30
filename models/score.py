from extensions import db
from sqlalchemy import CheckConstraint

class Score(db.Model):
    tablename = 'scores'
    id = db.Column(db.Integer, primary_key=True)
    judge_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    participation_id = db.Column(db.Integer, db.ForeignKey('participations.id', ondelete='CASCADE'), nullable=False)
    criterion_id = db.Column(db.Integer, db.ForeignKey('criteria.id', ondelete='CASCADE'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    scored_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    # 🔧 Связи для joinedload()
    judge = db.relationship('User')
    criterion = db.relationship('Criterion')

    __table_args__ = (
        db.UniqueConstraint('judge_id', 'participation_id', 'criterion_id', name='unique_score'),
        CheckConstraint("score >= 0", name="check_score"),
    )