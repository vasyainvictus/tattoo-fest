from flask import flash
from extensions import db
from models import NominationTemplate, TimeSlot, Participation, Criterion, Score

def check_and_update_nomination_status(nomination_id):
    """
    Проверяет, все ли оценки для номинации выставлены, и обновляет ее статус.
    """
    nomination = NominationTemplate.query.get(nomination_id)
    # Если номинация уже завершена или награждена, ничего не делаем
    if not nomination or nomination.status in ['completed', 'awarded']:
        return

    # 1. Находим все слоты судейства для этой номинации
    judging_slots = TimeSlot.query.filter_by(nomination_id=nomination_id, status='judging').all()
    if not judging_slots:
        return # Нет слотов судейства - нечего проверять

    slot_ids = [slot.id for slot in judging_slots]

    # 2. Считаем, сколько всего должно быть оценок
    participants_count = Participation.query.filter(Participation.slot_id.in_(slot_ids)).count()
    judges_count = nomination.judge_assignments.count() # Используем новую связь
    criteria_count = Criterion.query.count()

    # Если чего-то из этого нет, то и оценок быть не может
    if participants_count == 0 or judges_count == 0 or criteria_count == 0:
        # Если судейство еще не началось, меняем статус на "judging"
        if nomination.status == 'pending':
            nomination.status = 'judging'
            db.session.commit()
        return

    total_expected_scores = participants_count * judges_count * criteria_count

    # 3. Считаем, сколько оценок выставлено по факту
    participation_ids = [p.id for p in Participation.query.filter(Participation.slot_id.in_(slot_ids))]
    actual_scores_count = Score.query.filter(Score.participation_id.in_(participation_ids)).count()

    # 4. Сравниваем и принимаем решение
    if actual_scores_count >= total_expected_scores:
        nomination.status = 'completed'
        print(f"INFO: Судейство по номинации '{nomination.name}' ЗАВЕРШЕНО. Статус обновлен на 'completed'.")
        flash(f'Судейство по номинации "{nomination.name}" завершено! Теперь можно назначить награждение.', 'info')
    else:
        # Если оценок еще не хватает, но номинация была в ожидании, переводим ее в статус "судейство"
        if nomination.status == 'pending':
            nomination.status = 'judging'
            print(f"INFO: Судейство по номинации '{nomination.name}' НАЧАЛОСЬ. Статус обновлен на 'judging'.")

    db.session.commit()