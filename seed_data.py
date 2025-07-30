from datetime import datetime, date
from app import create_app
from extensions import db
# ИЗМЕНЕНИЕ: Импортируем NominationTemplate вместо Nomination
from models import User, Festival, EventDay, NominationTemplate, TimeSlot, JudgeNomination, Criterion, Participation, Winner, Score

# Создаем экземпляр приложения, чтобы получить контекст
app = create_app()

with app.app_context():
    # --- 1. ОЧИСТКА ДАННЫХ ---
    print("Очистка старых данных...")
    # Идем в обратном порядке зависимостей
    db.session.query(Score).delete()
    db.session.query(Winner).delete()
    db.session.query(Participation).delete()
    db.session.query(JudgeNomination).delete()
    db.session.query(TimeSlot).delete()
    db.session.query(Criterion).delete()
    db.session.query(NominationTemplate).delete() # Очищаем новую таблицу
    db.session.query(EventDay).delete()
    db.session.query(Festival).delete()
    db.session.query(User).delete()
    db.session.commit()
    print("Очистка завершена.")

    # --- 2. СОЗДАНИЕ ДАННЫХ ---
    print("Добавление тестовых данных...")
    
    try:
        # --- Пользователи (без изменений) ---
        admin = User(code='000001', role='admin')
        participant_pro_1 = User(code='100001', role='participant', experience_category='pro')
        participant_pro_2 = User(code='100002', role='participant', experience_category='pro')
        participant_junior = User(code='100003', role='participant', experience_category='junior')
        judge1 = User(code='200001', role='judge')
        judge2 = User(code='200002', role='judge')
        db.session.add_all([admin, participant_pro_1, participant_pro_2, participant_junior, judge1, judge2])
        db.session.commit()

        # --- Фестиваль и Дни (без изменений) ---
        festival = Festival(name='Тату-фестиваль 2025', start_date=date(2025, 7, 10), end_date=date(2025, 7, 12))
        db.session.add(festival)
        db.session.commit()
        day1 = EventDay(festival_id=festival.id, date=date(2025, 7, 10), day_order=1)
        day2 = EventDay(festival_id=festival.id, date=date(2025, 7, 11), day_order=2)
        db.session.add_all([day1, day2])
        db.session.commit()

        # --- ИЗМЕНЕНИЕ: Создаем ШАБЛОНЫ номинаций ---
        template_bw = NominationTemplate(name='Лучшая Ч/Б тату', participant_type='both')
        template_color = NominationTemplate(name='Лучшая цветная тату', participant_type='pro')
        template_oriental = NominationTemplate(name='Ориентальная тату', participant_type='both')
        db.session.add_all([template_bw, template_color, template_oriental])
        db.session.commit()
        
        # --- ИЗМЕНЕНИЕ: Создаем СЛОТЫ-КОНКУРСЫ в расписании, используя шаблоны ---
        contest_bw_fresh = TimeSlot(
            day_id=day1.id, start_time=datetime(2025, 7, 10, 10, 0), end_time=datetime(2025, 7, 10, 12, 0),
            slot_order=1, type='judging', nomination_template_id=template_bw.id, category='fresh', zone='A'
        )
        contest_color_fresh = TimeSlot(
            day_id=day1.id, start_time=datetime(2025, 7, 10, 13, 0), end_time=datetime(2025, 7, 10, 15, 0),
            slot_order=3, type='judging', nomination_template_id=template_color.id, category='fresh', zone='Б'
        )
        contest_bw_healed = TimeSlot(
            day_id=day2.id, start_time=datetime(2025, 7, 11, 10, 0), end_time=datetime(2025, 7, 11, 12, 0),
            slot_order=1, type='judging', nomination_template_id=template_bw.id, category='healed', zone='A'
        )
        # Простой слот-событие
        slot_break = TimeSlot(day_id=day1.id, start_time=datetime(2025, 7, 10, 12, 0), end_time=datetime(2025, 7, 10, 13, 0), slot_order=2, type='event', event_title='Обеденный перерыв')
        db.session.add_all([contest_bw_fresh, contest_color_fresh, contest_bw_healed, slot_break])
        db.session.commit()

        # --- ИЗМЕНЕНИЕ: Регистрируем участников и судей на КОНКРЕТНЫЕ СЛОТЫ ---
        # Участники
        p1 = Participation(user_id=participant_pro_1.id, time_slot_id=contest_bw_fresh.id, entry_number=1)
        p2 = Participation(user_id=participant_junior.id, time_slot_id=contest_bw_fresh.id, entry_number=1)
        p3 = Participation(user_id=participant_pro_2.id, time_slot_id=contest_color_fresh.id, entry_number=1)
        p4 = Participation(user_id=participant_pro_1.id, time_slot_id=contest_bw_healed.id, entry_number=1)
        db.session.add_all([p1, p2, p3, p4])
        
        # Судьи
        j1 = JudgeNomination(judge_id=judge1.id, time_slot_id=contest_bw_fresh.id)
        j2 = JudgeNomination(judge_id=judge2.id, time_slot_id=contest_bw_fresh.id)
        j3 = JudgeNomination(judge_id=judge1.id, time_slot_id=contest_color_fresh.id)
        db.session.add_all([j1, j2, j3])
        db.session.commit()

        # --- Критерии и Оценки (без изменений) ---
        criterion_tech = Criterion(name='Техника', max_score=10, order=1)
        criterion_comp = Criterion(name='Композиция', max_score=10, order=2)
        criterion_orig = Criterion(name='Оригинальность', max_score=10, order=3)
        db.session.add_all([criterion_tech, criterion_comp, criterion_orig])
        db.session.commit()
        
        # Пример оценки
        score1 = Score(judge_id=judge1.id, participation_id=p1.id, criterion_id=criterion_tech.id, score=8)
        db.session.add(score1)
        db.session.commit()

        print("Тестовые данные успешно добавлены!")
    except Exception as e:
        db.session.rollback()
        print(f"Произошла ошибка при добавлении данных: {e}")