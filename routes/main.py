from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from sqlalchemy.orm import joinedload
from models import User, Participation, Score, TimeSlot, Criterion, JudgeNomination, NominationTemplate
from extensions import db
from sqlalchemy import or_, and_
from collections import defaultdict


main_bp = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Для доступа к этой странице необходимо войти в систему.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# routes/main.py

@main_bp.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        flash('Произошла ошибка. Пожалуйста, войдите снова.', 'error')
        return redirect(url_for('auth.login'))

    # --- ИЗМЕНЕНИЕ: Инициализируем schedule_items как пустой список ---
    schedule_items = []
    participant_participations = []
    pending_contests = []
    judged_contests = []
    highlight_slot_ids = set()

    if user.role == 'participant':
        participations = Participation.query.filter_by(user_id=user.id).options(
            joinedload(Participation.contest_slot).joinedload(TimeSlot.nomination_template),
            joinedload(Participation.contest_slot).joinedload(TimeSlot.day)
        ).all()
        participant_participations = participations
        highlight_slot_ids = {p.contest_slot.id for p in participations}

        # --- НОВАЯ ЛОГИКА: Выбираем релевантные награждения ---
        relevant_award_conditions = []
        for p in participations:
            # Ищем награждение того же дня и той же категории
            condition = and_(
                TimeSlot.day_id == p.contest_slot.day_id,
                TimeSlot.category == p.contest_slot.category,
                TimeSlot.type == 'award'
            )
            relevant_award_conditions.append(condition)
        
        # Собираем ID всех нужных слотов: конкурсы + награждения
        all_relevant_slot_ids = highlight_slot_ids.copy()
        if relevant_award_conditions:
            relevant_awards = TimeSlot.query.filter(or_(*relevant_award_conditions)).all()
            for award in relevant_awards:
                all_relevant_slot_ids.add(award.id)
        
        # Загружаем только нужные слоты для расписания
        if all_relevant_slot_ids:
            schedule_items = TimeSlot.query.filter(TimeSlot.id.in_(all_relevant_slot_ids)).options(
                joinedload(TimeSlot.day),
                joinedload(TimeSlot.nomination_template)
            ).order_by(TimeSlot.start_time).all()

    elif user.role == 'judge':
        assigned_slot_ids = {a.time_slot_id for a in JudgeNomination.query.filter_by(judge_id=user.id)}
        highlight_slot_ids = assigned_slot_ids
        
        if assigned_slot_ids:
            all_assigned_contests = TimeSlot.query.filter(
                TimeSlot.id.in_(assigned_slot_ids)
            ).options(
                joinedload(TimeSlot.participants),
                joinedload(TimeSlot.nomination_template).joinedload(NominationTemplate.criteria)
            ).order_by(TimeSlot.start_time).all()

            # --- НОВАЯ ЛОГИКА: Выбираем релевантные награждения для судьи ---
            relevant_award_conditions = []
            for contest in all_assigned_contests:
                condition = and_(
                    TimeSlot.day_id == contest.day_id,
                    TimeSlot.category == contest.category,
                    TimeSlot.type == 'award'
                )
                relevant_award_conditions.append(condition)
            
            all_relevant_slot_ids = highlight_slot_ids.copy()
            if relevant_award_conditions:
                relevant_awards = TimeSlot.query.filter(or_(*relevant_award_conditions)).all()
                for award in relevant_awards:
                    all_relevant_slot_ids.add(award.id)

            if all_relevant_slot_ids:
                 schedule_items = TimeSlot.query.filter(TimeSlot.id.in_(all_relevant_slot_ids)).options(
                    joinedload(TimeSlot.day),
                    joinedload(TimeSlot.nomination_template)
                ).order_by(TimeSlot.start_time).all()


            # Логика для разделения на pending/judged остается без изменений
            all_scores_by_judge = Score.query.filter(
                Score.judge_id == user.id,
                Score.participation_id.in_([p.id for c in all_assigned_contests for p in c.participants])
            ).all()
            
            participation_to_contest_map = {p.id: c.id for c in all_assigned_contests for p in c.participants}
            scores_per_contest = defaultdict(list)
            for score in all_scores_by_judge:
                contest_id = participation_to_contest_map.get(score.participation_id)
                if contest_id:
                    scores_per_contest[contest_id].append(score)

            for contest in all_assigned_contests:
                criteria_count = len(contest.nomination_template.criteria)
                participants_count = len(contest.participants)
                if participants_count == 0 or criteria_count == 0:
                    pending_contests.append(contest)
                    continue
                
                total_expected_scores = participants_count * criteria_count
                scores_count_by_judge = len(scores_per_contest.get(contest.id, []))
                
                if scores_count_by_judge >= total_expected_scores:
                    judged_contests.append(contest)
                else:
                    pending_contests.append(contest)
    else:
        # --- СТАРАЯ ЛОГИКА ДЛЯ АДМИНА: Показываем все ---
        schedule_items = TimeSlot.query.options(
            joinedload(TimeSlot.day),
            joinedload(TimeSlot.nomination_template)
        ).order_by(TimeSlot.start_time).all()


    return render_template('dashboard.html',
                           user=user,
                           schedule_items=schedule_items,
                           participant_participations=participant_participations,
                           pending_contests=pending_contests,
                           judged_contests=judged_contests,
                           highlight_slot_ids=highlight_slot_ids,
                           now=datetime.now(),
                           role=user.role)


@main_bp.route('/my-scores')
@login_required
def my_scores():
    user = User.query.get(session['user_id'])
    if user.role != 'participant':
        flash('Доступ запрещён.', 'error')
        return redirect(url_for('main.dashboard'))

    participations = Participation.query.options(
        # Важно! Добавляем joinedload для p.winner, чтобы избежать доп. запросов в цикле
        joinedload(Participation.winner),
        joinedload(Participation.contest_slot).joinedload(TimeSlot.nomination_template),
        joinedload(Participation.contest_slot).joinedload(TimeSlot.day),
        joinedload(Participation.scores).joinedload(Score.criterion),
        joinedload(Participation.scores).joinedload(Score.judge)
    ).filter_by(user_id=user.id).all()

    # --- НОВЫЙ БЛОК: Загружаем все слоты награждений одним запросом ---
    award_slots = TimeSlot.query.filter_by(type='award').all()
    # Создаем карту для быстрого поиска: {(day_id, category): end_time}
    award_map = {(slot.day_id, slot.category): slot.end_time for slot in award_slots}

    results = []

    for p in participations:
        slot = p.contest_slot
        
        # Мы больше не скрываем конкурс, если он еще идет.
        # Мы просто решаем, показывать ли статус победителя.
        
        # --- НОВАЯ ЛОГИКА ОПРЕДЕЛЕНИЯ ПОБЕДИТЕЛЯ ---
        is_winner = False
        winner_place = None
        # Проверяем, есть ли запись о победе (p.winner был загружен через joinedload)
        if p.winner:
            # Находим время окончания награждения для этого конкурса (по дню и категории)
            award_end_time = award_map.get((slot.day_id, slot.category))
            
            # Показываем статус "Победитель" только если награждение найдено и оно уже прошло
            if award_end_time and datetime.now() > award_end_time:
                is_winner = True
                winner_place = p.winner.place
        
        # --- Существующая логика подсчета очков ---
        judge_scores = {}
        for s in p.scores:
            if s.criterion:
                judge_id = s.judge_id
                if judge_id not in judge_scores:
                    judge_scores[judge_id] = {'judge': s.judge, 'criteria': {}, 'total': 0, 'count': 0}
                
                judge_scores[judge_id]['criteria'][s.criterion.name] = s.score
                judge_scores[judge_id]['total'] += s.score
                judge_scores[judge_id]['count'] += 1

        for j in judge_scores.values():
            j['avg'] = round(j['total'] / j['count'], 2) if j['count'] else None

        overall_scores = [j['avg'] for j in judge_scores.values() if j['avg'] is not None]
        overall_avg = round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else None

        results.append({
            'participation_id': p.id,
            'nomination': slot.nomination_template.name,
            'category': slot.category,
            'date': slot.day.date,
            'start_time': slot.start_time,
            'end_time': slot.end_time,
            'judge_scores': judge_scores,
            'overall_avg': overall_avg,
            # --- НОВЫЕ ПОЛЯ для передачи в шаблон ---
            'is_winner': is_winner,
            'winner_place': winner_place
        })
        
    results.sort(key=lambda r: r['date'], reverse=True)

    return render_template('participant_scores.html', results=results, user=user)


@main_bp.route('/judging/<int:contest_id>', methods=['GET', 'POST'])
@login_required
def judging_page(contest_id):
    if session.get('user_role') != 'judge':
        flash('Доступ запрещен.', 'error')
        return redirect(url_for('main.dashboard'))
    
    judge_id = session['user_id']

    contest = TimeSlot.query.options(
        joinedload(TimeSlot.participants).joinedload(Participation.user),
        joinedload(TimeSlot.nomination_template).joinedload(NominationTemplate.criteria),
        joinedload(TimeSlot.day)
    ).get_or_404(contest_id)

    is_assigned = JudgeNomination.query.filter_by(
        judge_id=judge_id, 
        time_slot_id=contest.id
    ).first()
    if not is_assigned:
        flash('Вы не назначены судьей на этот конкурс.', 'error')
        return redirect(url_for('main.dashboard'))

    participations = contest.participants
    
    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    # Мы больше не можем использовать .order_by(), так как criteria - это список.
    # Сортируем его с помощью стандартной функции Python sorted().
    criteria = sorted(contest.nomination_template.criteria, key=lambda c: c.order)
    
    is_judging_allowed = datetime.now() >= contest.start_time

    if request.method == 'POST':
        if not is_judging_allowed:
            flash('Судейство для этого конкурса еще не началось.', 'error')
            return redirect(url_for('main.judging_page', contest_id=contest_id))

        participation_id = request.form.get('participation_id', type=int)
        try:
            for c in criteria:
                score_value = request.form.get(f'scores[{participation_id}][{c.id}]', type=int)
                if score_value is None:
                    raise ValueError(f'Необходимо выставить оценку по критерию "{c.name}".')
                
                existing_score = Score.query.filter_by(judge_id=judge_id, participation_id=participation_id, criterion_id=c.id).first()
                if existing_score:
                    existing_score.score = score_value
                else:
                    db.session.add(Score(judge_id=judge_id, participation_id=participation_id, criterion_id=c.id, score=score_value))
            
            db.session.commit()
            flash('Оценки успешно сохранены!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при сохранении оценок: {e}', 'error')
            
        return redirect(url_for('main.judging_page', contest_id=contest_id))

    # --- Остальная часть функции ---
    scores_by_judge = Score.query.filter(
        Score.judge_id == judge_id,
        Score.participation_id.in_([p.id for p in participations])
    ).all()
    scores_map = {(s.participation_id, s.criterion_id): s.score for s in scores_by_judge}

    fully_scored_participation_ids = set()
    criteria_count = len(criteria)
    if criteria_count > 0:
        scores_per_participation = {}
        for score in scores_by_judge:
            scores_per_participation.setdefault(score.participation_id, set()).add(score.criterion_id)
        for p_id, scored_criteria_ids in scores_per_participation.items():
            required_criteria_ids = {c.id for c in criteria}
            if scored_criteria_ids.issuperset(required_criteria_ids):
                fully_scored_participation_ids.add(p_id)

    avg_scores = {}
    for p in participations:
        values = [
            scores_map.get((p.id, c.id))
            for c in criteria
            if scores_map.get((p.id, c.id)) is not None
        ]
        avg_scores[p.id] = round(sum(values) / len(values), 2) if values else None

    return render_template('judging_page.html',
                           contest=contest,
                           participations=participations,
                           criteria=criteria,
                           scores_map=scores_map,
                           fully_scored_participation_ids=fully_scored_participation_ids,
                           is_judging_allowed=is_judging_allowed,
                           avg_scores=avg_scores)
