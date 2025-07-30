# models/criterion.py
# ИЗМЕНЕНИЙ НЕ ТРЕБУЕТСЯ

from extensions import db

class Criterion(db.Model):
    __tablename__ = 'criteria'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    max_score = db.Column(db.Integer, nullable=False, default=5)
    order = db.Column(db.Integer, nullable=False)