# models/nomination_template.py

from extensions import db
from sqlalchemy import CheckConstraint

# Вспомогательная таблица остается без изменений
nomination_template_criteria = db.Table('nomination_template_criteria',
    db.Column('nomination_template_id', db.Integer, db.ForeignKey('nomination_templates.id', ondelete='CASCADE'), primary_key=True),
    db.Column('criterion_id', db.Integer, db.ForeignKey('criteria.id', ondelete='CASCADE'), primary_key=True)
)


class NominationTemplate(db.Model):
    __tablename__ = 'nomination_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    participant_type = db.Column(db.String, nullable=False, default='both')

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    # Убираем lazy='dynamic', чтобы можно было использовать joinedload.
    # Теперь 'criteria' будет обычным списком, а не объектом запроса.
    criteria = db.relationship(
        'Criterion', 
        secondary=nomination_template_criteria,
        # 'backref' также больше не нуждается в lazy='dynamic'
        backref=db.backref('nomination_templates', lazy=True), 
        lazy='select' # 'select' - это поведение по умолчанию, можно даже не указывать
    )

    __table_args__ = (
        CheckConstraint("participant_type IN ('pro', 'junior', 'both')", name="check_participant_type"),
    )