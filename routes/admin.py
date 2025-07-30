# routes/admin.py

from sqlalchemy import and_
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta 
from extensions import db
from models import User, Festival, EventDay, NominationTemplate, TimeSlot, JudgeNomination, Participation, Criterion, Score, Winner
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from itertools import groupby
from collections import defaultdict



WORK_TYPES = ['Зажившие', 'Битва']
ZONES = ['A', 'Б', 'Сцена']


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_role' not in session or session['user_role'] != 'admin':
            flash('У вас нет прав для доступа к этой странице.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def assign_winner_status_to_group(participants_group):
    """
    Новая, упрощенная функция. Находит победителей (1 место) в группе.
    """
    if not participants_group:
        return []
    
    max_score = 0
    for p in participants_group:
        if p['final_score'] > max_score:
            max_score = p['final_score']

    if max_score == 0:
        for p_data in participants_group:
            p_data['is_winner'] = False
        return participants_group
        
    for p_data in participants_group:
        if p_data['final_score'] == max_score:
            p_data['is_winner'] = True
        else:
            p_data['is_winner'] = False
            
    return participants_group

# --- БЛОК CRUD для User (без изменений) ---
@admin_bp.route('/users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    if request.method == 'POST':
        code = request.form.get('code')
        nickname = request.form.get('nickname')  # <-- новое поле
        role = request.form.get('role')
        experience = request.form.get('experience_category')

        if not code or not role:
            flash('Код и роль являются обязательными полями.', 'error')
        else:
            if role != 'participant':
                experience = None
            new_user = User(code=code, nickname=nickname, role=role, experience_category=experience)
            db.session.add(new_user)
            try:
                db.session.commit()
                flash(f'Пользователь {nickname or code} успешно создан!', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(f'Ошибка! Пользователь с кодом {code} уже существует.', 'error')
        return redirect(url_for('admin.manage_users'))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.nickname = request.form.get('nickname')  # <-- новое поле
        user.role = request.form.get('role')
        user.telegram_id = request.form.get('telegram_id')
        if user.role == 'participant':
            user.experience_category = request.form.get('experience_category')
        else:
            user.experience_category = None

        try:
            db.session.commit()
            flash('Данные пользователя успешно обновлены.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла ошибка при обновлении: {e}', 'error')

        return redirect(url_for('admin.manage_users'))

    return render_template('admin/edit_user.html', user=user)


@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    if 'user_id' in session and user_id == session['user_id']:
        flash('Вы не можете удалить свою собственную учетную запись.', 'error')
        return redirect(url_for('admin.manage_users'))

    user_to_delete = User.query.get_or_404(user_id)
    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash('Пользователь успешно удален.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Ошибка! Нельзя удалить пользователя, так как он связан с другими данными.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при удалении: {e}', 'error')
        
    return redirect(url_for('admin.manage_users'))


# --- БЛОК CRUD для Festival и EventDay (без изменений) ---
@admin_bp.route('/festivals', methods=['GET', 'POST'])
@admin_required
def manage_festivals():
    if request.method == 'POST':
        name = request.form.get('name')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')

        if not name or not start_date_str or not end_date_str:
            flash('Все поля обязательны для заполнения.', 'error')
            return redirect(url_for('admin.manage_festivals'))
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            # --- НОВАЯ ПРОВЕРКА ---
            if start_date > end_date:
                flash('Дата начала не может быть позже даты окончания.', 'error')
                return redirect(url_for('admin.manage_festivals'))

            # 1. Создаем объект фестиваля, но пока не коммитим
            new_festival = Festival(name=name, start_date=start_date, end_date=end_date)
            db.session.add(new_festival)

            # --- НОВАЯ ЛОГИКА АВТО-СОЗДАНИЯ ДНЕЙ ---
            # 2. В цикле генерируем дни фестиваля
            current_date = start_date
            day_order_counter = 1
            days_created_count = 0
            while current_date <= end_date:
                event_day = EventDay(
                    date=current_date,
                    day_order=day_order_counter
                    # festival_id будет установлен автоматически благодаря связи ниже
                )
                # Привязываем созданный день к нашему новому фестивалю
                new_festival.days.append(event_day)
                
                current_date += timedelta(days=1)
                day_order_counter += 1
                days_created_count += 1

            # 3. Сохраняем все изменения (фестиваль и все его дни) одной транзакцией
            db.session.commit()
            flash(f'Фестиваль "{name}" и его {days_created_count} дней успешно созданы!', 'success')

        except ValueError:
            db.session.rollback()
            flash('Неверный формат даты. Пожалуйста, используйте ДД.ММ.ГГГГ.', 'error')
        except IntegrityError:
            db.session.rollback()
            flash(f'Ошибка! Фестиваль с названием "{name}" уже существует.', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла непредвиденная ошибка: {e}', 'error')

        return redirect(url_for('admin.manage_festivals'))

    # Логика для GET запроса остается без изменений
    festivals = Festival.query.order_by(Festival.start_date.desc()).all()
    return render_template('admin/festivals.html', festivals=festivals)

@admin_bp.route('/festivals/<int:festival_id>', methods=['GET'])
@admin_required
def manage_festival_details(festival_id):
    """
    Эта страница теперь просто показывает список дней фестиваля.
    Вся логика управления днями переехала в edit_festival.
    """
    festival = Festival.query.get_or_404(festival_id)
    days = EventDay.query.filter_by(festival_id=festival.id).order_by(EventDay.day_order).all()
    
    return render_template('admin/festival_details.html', festival=festival, days=days)


@admin_bp.route('/festival/<int:festival_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_festival(festival_id):
    # Загружаем фестиваль и его текущие дни
    festival = Festival.query.options(joinedload(Festival.days)).get_or_404(festival_id)
    
    if request.method == 'POST':
        try:
            # 1. Получаем новые данные из формы
            new_name = request.form.get('name')
            new_start_date_str = request.form.get('start_date')
            new_end_date_str = request.form.get('end_date')

            if not new_name or not new_start_date_str or not new_end_date_str:
                flash('Все поля должны быть заполнены.', 'error')
                return redirect(url_for('admin.edit_festival', festival_id=festival.id))

            new_start_date = datetime.strptime(new_start_date_str, '%Y-%m-%d').date()
            new_end_date = datetime.strptime(new_end_date_str, '%Y-%m-%d').date()

            if new_start_date > new_end_date:
                flash('Дата начала не может быть позже даты окончания.', 'error')
                return redirect(url_for('admin.edit_festival', festival_id=festival.id))
            
            # 2. Определяем изменения в датах
            old_dates = {day.date for day in festival.days}
            new_dates = set()
            current_date = new_start_date
            while current_date <= new_end_date:
                new_dates.add(current_date)
                current_date += timedelta(days=1)

            dates_to_add = new_dates - old_dates
            dates_to_remove = old_dates - new_dates
            
            # 3. Проверка безопасности: ищем расписание на удаляемых днях
            days_to_remove_with_schedule = []
            if dates_to_remove:
                # Находим объекты EventDay, которые соответствуют удаляемым датам
                days_to_check = [day for day in festival.days if day.date in dates_to_remove]
                for day in days_to_check:
                    # Проверяем, есть ли у дня связанные TimeSlot'ы
                    if TimeSlot.query.filter_by(day_id=day.id).first():
                        days_to_remove_with_schedule.append(day.date.strftime('%d.%m.%Y'))
            
            if days_to_remove_with_schedule:
                flash(f"Не удалось изменить даты! Следующие дни будут удалены, но на них уже есть расписание: {', '.join(days_to_remove_with_schedule)}. Сначала очистите их расписание.", 'error')
                return redirect(url_for('admin.edit_festival', festival_id=festival.id))

            # 4. Выполнение изменений, если проверка пройдена
            # Обновляем сам фестиваль
            festival.name = new_name
            festival.start_date = new_start_date
            festival.end_date = new_end_date
            
            # Удаляем старые пустые дни
            if dates_to_remove:
                EventDay.query.filter(EventDay.festival_id == festival.id, EventDay.date.in_(dates_to_remove)).delete(synchronize_session=False)

            # Добавляем новые дни
            for date_to_add in dates_to_add:
                new_day = EventDay(festival_id=festival.id, date=date_to_add, day_order=999) # day_order временный
                db.session.add(new_day)
            
            # Важно! Сначала коммитим удаление и добавление
            db.session.commit()
            
            # 5. Перенумерация всех дней фестиваля
            all_days_for_festival = EventDay.query.filter_by(festival_id=festival.id).order_by(EventDay.date.asc()).all()
            for index, day in enumerate(all_days_for_festival):
                day.day_order = index + 1
            
            db.session.commit()
            flash('Данные фестиваля успешно обновлены!', 'success')
            return redirect(url_for('admin.manage_festivals'))

        except Exception as e:
            db.session.rollback()
            flash(f'Произошла непредвиденная ошибка: {e}', 'error')
            return redirect(url_for('admin.edit_festival', festival_id=festival.id))

    # Для GET запроса просто отображаем страницу с текущими данными
    return render_template('admin/edit_festival.html', festival=festival)


@admin_bp.route('/nomination_templates', methods=['GET', 'POST'])
@admin_required
def manage_nomination_templates():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        participant_type = request.form.get('participant_type')
        # Получаем список ID выбранных критериев из формы
        criteria_ids = request.form.getlist('criteria', type=int)

        if not name or not participant_type:
            flash('Название и тип участников являются обязательными полями.', 'error')
        else:
            new_template = NominationTemplate(
                name=name, 
                description=description, 
                participant_type=participant_type
            )
            
            # Находим объекты Criterion по их ID
            if criteria_ids:
                selected_criteria = Criterion.query.filter(Criterion.id.in_(criteria_ids)).all()
                new_template.criteria = selected_criteria
            
            db.session.add(new_template)
            try:
                db.session.commit()
                flash(f'Шаблон номинации "{name}" успешно создан.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(f'Шаблон номинации с названием "{name}" уже существует.', 'error')
        return redirect(url_for('admin.manage_nomination_templates'))

    # Для GET-запроса передаем в шаблон все шаблоны и все критерии
    templates = NominationTemplate.query.options(joinedload(NominationTemplate.criteria)).order_by(NominationTemplate.name).all()
    all_criteria = Criterion.query.order_by(Criterion.order).all()
    return render_template('admin/nominations.html', templates=templates, all_criteria=all_criteria)


@admin_bp.route('/nomination_template/<int:template_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_nomination_template(template_id):
    template = NominationTemplate.query.options(joinedload(NominationTemplate.criteria)).get_or_404(template_id)
    
    if request.method == 'POST':
        template.name = request.form.get('name')
        template.description = request.form.get('description')
        template.participant_type = request.form.get('participant_type')
        
        # Получаем новые ID и обновляем связь
        criteria_ids = request.form.getlist('criteria', type=int)
        selected_criteria = Criterion.query.filter(Criterion.id.in_(criteria_ids)).all()
        template.criteria = selected_criteria
        
        try:
            db.session.commit()
            flash('Шаблон номинации успешно обновлен.', 'success')
            return redirect(url_for('admin.manage_nomination_templates'))
        except IntegrityError:
            db.session.rollback()
            flash('Ошибка! Шаблон с таким названием уже существует.', 'error')
            return redirect(url_for('admin.edit_nomination_template', template_id=template.id))

    # Для GET-запроса передаем шаблон и все критерии для формы
    all_criteria = Criterion.query.order_by(Criterion.order).all()
    return render_template('admin/edit_nomination.html', template=template, all_criteria=all_criteria)

@admin_bp.route('/nomination_template/<int:template_id>/delete', methods=['POST'])
@admin_required
def delete_nomination_template(template_id):
    template_to_delete = NominationTemplate.query.get_or_404(template_id)
    try:
        db.session.delete(template_to_delete)
        db.session.commit()
        flash('Шаблон номинации успешно удален.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Ошибка! Нельзя удалить шаблон, т.к. он используется в расписании.', 'error')
    return redirect(url_for('admin.manage_nomination_templates'))


@admin_bp.route('/day/<int:day_id>/schedule', methods=['GET', 'POST'])
@admin_required
def manage_day_schedule(day_id):
    day = EventDay.query.get_or_404(day_id)
    
    # Для формы нам нужен список всех шаблонов номинаций
    nomination_templates = NominationTemplate.query.order_by(NominationTemplate.name).all()

    if request.method == 'POST':
        try:
            # Общие поля
            slot_type = request.form.get('type')
            start_t = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
            end_t = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
            
            # Автоматически вычисляем slot_order
            max_order = db.session.query(func.max(TimeSlot.slot_order)).filter_by(day_id=day.id).scalar()
            new_order = (max_order or 0) + 1

            new_slot = TimeSlot(
                day_id=day.id,
                start_time=datetime.combine(day.date, start_t),
                end_time=datetime.combine(day.date, end_t),
                slot_order=new_order,
                type=slot_type
            )

            # Добавляем специфичные для типа поля
            if slot_type == 'judging':
                new_slot.nomination_template_id = request.form.get('nomination_template_id', type=int)
                new_slot.category = request.form.get('category')
                new_slot.zone = request.form.get('zone')
                if not new_slot.nomination_template_id or not new_slot.category:
                    raise ValueError("Для слота судейства необходимо выбрать шаблон номинации и категорию.")
            elif slot_type == 'award':
                # --- ИЗМЕНЕНИЕ: Убираем award_title, добавляем zone ---
                new_slot.category = request.form.get('category')
                new_slot.zone = request.form.get('zone') 
            elif slot_type == 'event':
                new_slot.event_title = request.form.get('event_title')

            db.session.add(new_slot)
            db.session.commit()
            flash('Слот в расписании успешно создан!', 'success')

        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла непредвиденная ошибка: {e}', 'error')
        
        return redirect(url_for('admin.manage_day_schedule', day_id=day_id))

    # GET-логика
    time_slots = TimeSlot.query.filter_by(day_id=day.id).options(
        joinedload(TimeSlot.nomination_template),
        joinedload(TimeSlot.participants),
        joinedload(TimeSlot.judge_assignments)
    ).order_by(TimeSlot.start_time, TimeSlot.slot_order).all()
    
    grouped_slots = []
    if time_slots:
        for time, group in groupby(time_slots, key=lambda s: s.start_time.strftime('%H:%M') + ' - ' + s.end_time.strftime('%H:%M')):
            grouped_slots.append((time, list(group)))
    
    return render_template('admin/day_schedule.html', 
                           day=day, 
                           grouped_slots=grouped_slots,
                           nomination_templates=nomination_templates, # Передаем шаблоны в форму
                           ZONES=ZONES) # Константа ZONES у тебя уже должна быть


@admin_bp.route('/slot/<int:slot_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_slot(slot_id):
    # Загружаем слот и связанные данные дня
    slot = TimeSlot.query.options(joinedload(TimeSlot.day)).get_or_404(slot_id)

    if request.method == 'POST':
        try:
            # 1. Получаем общие данные из формы
            start_t = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
            end_t = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
            
            # Обновляем общие поля слота
            slot.start_time = datetime.combine(slot.day.date, start_t)
            slot.end_time = datetime.combine(slot.day.date, end_t)
            
            # 2. Получаем и обновляем специфичные для типа поля
            slot_type = slot.type # Тип не меняется, берем его из объекта
            
            if slot_type == 'judging':
                slot.nomination_template_id = request.form.get('nomination_template_id', type=int)
                slot.category = request.form.get('category')
                slot.zone = request.form.get('zone')
                # Добавляем проверку на обязательные поля
                if not slot.nomination_template_id or not slot.category:
                    raise ValueError("Для слота судейства необходимо выбрать шаблон номинации и категорию.")

            elif slot_type == 'award':
                # --- ИЗМЕНЕНИЕ: Убираем award_title, обновляем zone ---
                slot.category = request.form.get('category')
                slot.zone = request.form.get('zone')
                
                # Очищаем поля от других типов, чтобы в базе не было мусора
                slot.nomination_template_id = None
                slot.event_title = None
                slot.award_title = None # На всякий случай, если в базе остались старые данные

            elif slot_type == 'event':
                slot.event_title = request.form.get('event_title')
                # Очищаем поля от других типов
                slot.nomination_template_id = None
                slot.category = None
                slot.zone = None
                slot.award_title = None

            db.session.commit()
            flash('Слот успешно обновлен!', 'success')
            return redirect(url_for('admin.manage_day_schedule', day_id=slot.day_id))

        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла непредвиденная ошибка при обновлении: {e}', 'error')
        
        # В случае ошибки остаемся на странице редактирования
        return redirect(url_for('admin.edit_slot', slot_id=slot.id))

    # --- Логика для GET-запроса ---
    # Для формы нам нужен список всех шаблонов номинаций и зон
    nomination_templates = NominationTemplate.query.order_by(NominationTemplate.name).all()
    
    return render_template(
        'admin/edit_slot.html', 
        slot=slot, 
        nomination_templates=nomination_templates,
        ZONES=ZONES # Передаем константу ZONES
    )


@admin_bp.route('/slot/<int:slot_id>/delete', methods=['POST'])
@admin_required
def delete_slot(slot_id):
    slot_to_delete = TimeSlot.query.get_or_404(slot_id)
    day_id = slot_to_delete.day_id
    db.session.delete(slot_to_delete)
    db.session.commit()
    flash('Слот успешно удален.', 'success')
    return redirect(url_for('admin.manage_day_schedule', day_id=day_id))

# routes/admin.py

@admin_bp.route('/slot/<int:slot_id>/participants', methods=['GET', 'POST'])
@admin_required
def manage_slot_participants(slot_id):
    # Загружаем слот-конкурс и связанные с ним данные для отображения
    contest_slot = TimeSlot.query.options(
        joinedload(TimeSlot.nomination_template),
        joinedload(TimeSlot.participants).joinedload(Participation.user),
        joinedload(TimeSlot.day)
    ).get_or_404(slot_id)

    # Убеждаемся, что это действительно слот-конкурс
    if contest_slot.type != 'judging':
        flash('Управлять участниками можно только в слотах типа "Судейство".', 'error')
        return redirect(url_for('admin.manage_day_schedule', day_id=contest_slot.day_id))

    if request.method == 'POST':
        user_id = request.form.get('user_id', type=int)
        if not user_id:
            flash('Нужно выбрать участника для добавления.', 'error')
        else:
            try:
                # Рассчитываем номер заявки для этого участника в этом конкурсе
                existing_entries_count = Participation.query.filter_by(
                    user_id=user_id,
                    time_slot_id=slot_id
                ).count()
                new_entry_number = existing_entries_count + 1
                
                new_participation = Participation(
                    user_id=user_id, 
                    time_slot_id=slot_id,
                    entry_number=new_entry_number
                )
                db.session.add(new_participation)
                db.session.commit()
                
                user_code = User.query.get(user_id).code
                flash(f'Заявка #{new_entry_number} от участника {user_code} успешно добавлена.', 'success')

            except Exception as e:
                db.session.rollback()
                flash(f'Произошла ошибка: {e}', 'error')

        return redirect(url_for('admin.manage_slot_participants', slot_id=slot_id))

    # GET-запрос: Готовим список доступных участников
    participant_type = contest_slot.nomination_template.participant_type
    user_query = User.query.filter(User.role == 'participant')
    
    if participant_type == 'pro':
        user_query = user_query.filter(User.experience_category == 'pro')
    elif participant_type == 'junior':
        user_query = user_query.filter(User.experience_category == 'junior')
    
    available_participants = user_query.order_by(User.code).all()
    
    return render_template('admin/manage_slot_participants.html', 
                           contest_slot=contest_slot, 
                           available_participants=available_participants)

# routes/admin.py

@admin_bp.route('/slot/<int:slot_id>/judges', methods=['GET', 'POST'])
@admin_required
def manage_slot_judges(slot_id):
    # Загружаем слот-конкурс и связанные с ним данные
    contest_slot = TimeSlot.query.options(
        joinedload(TimeSlot.nomination_template),
        joinedload(TimeSlot.judge_assignments).joinedload(JudgeNomination.judge),
        joinedload(TimeSlot.day)
    ).get_or_404(slot_id)

    # Проверка, что это слот-конкурс
    if contest_slot.type != 'judging':
        flash('Управлять судьями можно только в слотах типа "Судейство".', 'error')
        return redirect(url_for('admin.manage_day_schedule', day_id=contest_slot.day_id))

    if request.method == 'POST':
        judge_id = request.form.get('judge_id', type=int)
        if not judge_id:
            flash('Нужно выбрать судью для назначения.', 'error')
        else:
            new_assignment = JudgeNomination(
                judge_id=judge_id,
                time_slot_id=slot_id
            )
            db.session.add(new_assignment)
            try:
                db.session.commit()
                flash('Судья успешно назначен на конкурс.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash('Этот судья уже назначен на данный конкурс.', 'error')
        return redirect(url_for('admin.manage_slot_judges', slot_id=slot_id))

    # GET-запрос: Готовим список доступных судей
    assigned_judge_ids = {a.judge_id for a in contest_slot.judge_assignments}
    available_judges = User.query.filter(
        User.role == 'judge',
        User.id.notin_(assigned_judge_ids)
    ).all()
    
    return render_template('admin/manage_slot_judges.html', 
                           contest_slot=contest_slot, 
                           available_judges=available_judges)



@admin_bp.route('/festival/<int:festival_id>/delete', methods=['POST'])
@admin_required
def delete_festival(festival_id):
    festival_to_delete = Festival.query.get_or_404(festival_id)
    try:
        # Благодаря 'cascade' в моделях, все связанные дни, слоты, номинации и т.д.
        # будут удалены автоматически вместе с фестивалем.
        db.session.delete(festival_to_delete)
        db.session.commit()
        flash(f'Фестиваль "{festival_to_delete.name}" и все связанные с ним данные были успешно удалены.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при удалении фестиваля: {e}', 'error')
        
    return redirect(url_for('admin.manage_festivals'))

# routes/admin.py

@admin_bp.route('/participation/<int:participation_id>/delete', methods=['POST'])
@admin_required
def delete_participation(participation_id):
    participation_to_delete = Participation.query.get_or_404(participation_id)
    # Запоминаем ID слота, чтобы вернуться на нужную страницу
    slot_id = participation_to_delete.time_slot_id
    try:
        db.session.delete(participation_to_delete)
        db.session.commit()
        flash('Заявка участника успешно удалена.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при удалении заявки: {e}', 'error')
        
    return redirect(url_for('admin.manage_slot_participants', slot_id=slot_id))

# routes/admin.py

@admin_bp.route('/judge_assignment/<int:assignment_id>/delete', methods=['POST'])
@admin_required
def delete_judge_assignment(assignment_id):
    assignment_to_delete = JudgeNomination.query.get_or_404(assignment_id)
    slot_id = assignment_to_delete.time_slot_id
    try:
        db.session.delete(assignment_to_delete)
        db.session.commit()
        flash('Судья успешно снят с конкурса.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при снятии судьи: {e}', 'error')
        
    return redirect(url_for('admin.manage_slot_judges', slot_id=slot_id))

@admin_bp.route('/results')
@admin_required
def admin_results_view():
    contests = TimeSlot.query.filter_by(type='judging').options(
        joinedload(TimeSlot.nomination_template).joinedload(NominationTemplate.criteria),
        joinedload(TimeSlot.day),
        joinedload(TimeSlot.participants).joinedload(Participation.user),
        joinedload(TimeSlot.judge_assignments).joinedload(JudgeNomination.judge)
    ).order_by(TimeSlot.day_id, TimeSlot.start_time).all()
    
    # Оптимизация: загружаем оценки только для участников текущих конкурсов
    all_participant_ids = [p.id for contest in contests for p in contest.participants]
    all_scores = Score.query.filter(Score.participation_id.in_(all_participant_ids)).all()
    scores_map = { (s.participation_id, s.judge_id, s.criterion_id): s.score for s in all_scores }

    # --- НОВЫЙ БЛОК: Загружаем всех подтвержденных победителей одним запросом ---
    confirmed_winners = Winner.query.all()
    # Создаем удобную структуру для поиска: {participation_id: place}
    winner_map = {w.participation_id: w.place for w in confirmed_winners}

    results_data = []
    for contest in contests:
        contest_criteria = sorted(contest.nomination_template.criteria, key=lambda c: c.order)
        
        pro_participants = []
        junior_participants = []

        for participation in contest.participants:
            # Логика подсчета final_score остается той же
            judge_evaluations = []
            judge_average_scores = []
            for judge in [a.judge for a in contest.judge_assignments]:
                scores_by_criterion = {c.id: scores_map.get((participation.id, judge.id, c.id)) for c in contest_criteria}
                valid_scores = [s for s in scores_by_criterion.values() if s is not None]
                if valid_scores:
                    judge_avg = sum(valid_scores) / len(valid_scores)
                    judge_average_scores.append(judge_avg)
                else:
                    judge_avg = None
                judge_evaluations.append({'judge': judge, 'scores_by_criterion': scores_by_criterion, 'judge_avg': round(judge_avg, 2) if judge_avg is not None else '-'})
            
            final_score = round(sum(judge_average_scores) / len(judge_average_scores), 2) if judge_average_scores else 0
            
            p_data = {
                # --- ИЗМЕНЕНИЕ: передаем весь объект participation ---
                'participation': participation, 
                'participant': participation.user,
                'entry_number': participation.entry_number,
                'judge_evaluations': judge_evaluations,
                'final_score': final_score,
                # --- НОВОЕ ПОЛЕ: добавляем информацию о подтвержденном месте ---
                'confirmed_place': winner_map.get(participation.id)
            }
            
            if participation.user.experience_category == 'pro':
                pro_participants.append(p_data)
            else:
                junior_participants.append(p_data)
        
        pro_participants.sort(key=lambda x: x['final_score'], reverse=True)
        junior_participants.sort(key=lambda x: x['final_score'], reverse=True)
        
        results_data.append({
            'contest': contest,
            # --- ИЗМЕНЕНИЕ: передаем данные раздельно ---
            'pro_participants_data': pro_participants,
            'junior_participants_data': junior_participants,
            'criteria_list': contest_criteria
        })
        
    results_by_day = defaultdict(list)
    for result in results_data:
        results_by_day[result['contest'].day].append(result)

    return render_template(
        'admin/results.html',
        results_by_day=results_by_day
    )


# --- НОВЫЙ БЛОК: CRUD для Criterion ---
@admin_bp.route('/criteria', methods=['GET', 'POST'])
@admin_required
def manage_criteria():
    if request.method == 'POST':
        name = request.form.get('name')
        max_score = request.form.get('max_score', type=int)
        
        # Автоматически определяем порядок для нового критерия
        max_order = db.session.query(func.max(Criterion.order)).scalar()
        order = (max_order or 0) + 1

        if not name or not max_score:
            flash('Название и максимальный балл являются обязательными полями.', 'error')
        else:
            new_criterion = Criterion(name=name, max_score=max_score, order=order)
            db.session.add(new_criterion)
            try:
                db.session.commit()
                flash(f'Критерий "{name}" успешно создан.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash('Критерий с таким названием уже существует.', 'error')
        return redirect(url_for('admin.manage_criteria'))

    criteria = Criterion.query.order_by(Criterion.order).all()
    return render_template('admin/criteria.html', criteria=criteria)

@admin_bp.route('/criterion/<int:criterion_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_criterion(criterion_id):
    criterion = Criterion.query.get_or_404(criterion_id)
    if request.method == 'POST':
        criterion.name = request.form.get('name')
        criterion.max_score = request.form.get('max_score', type=int)
        # Порядок пока не редактируем, чтобы не усложнять. Можно добавить позже.
        try:
            db.session.commit()
            flash('Критерий успешно обновлен.', 'success')
            return redirect(url_for('admin.manage_criteria'))
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла ошибка: {e}', 'error')
            return redirect(url_for('admin.edit_criterion', criterion_id=criterion.id))
    
    return render_template('admin/edit_criterion.html', criterion=criterion)

@admin_bp.route('/criterion/<int:criterion_id>/delete', methods=['POST'])
@admin_required
def delete_criterion(criterion_id):
    criterion_to_delete = Criterion.query.get_or_404(criterion_id)
    
    # --- НОВАЯ ПРОВЕРКА ---
    # Ищем, есть ли хоть одна оценка, связанная с этим критерием.
    existing_score = Score.query.filter_by(criterion_id=criterion_id).first()
    
    if existing_score:
        flash(f'Невозможно удалить критерий "{criterion_to_delete.name}", так как по нему уже выставлены оценки. '
              'Сначала необходимо удалить связанные оценки.', 'error')
        return redirect(url_for('admin.manage_criteria'))
    
    # Если оценок нет, продолжаем стандартную процедуру удаления.
    try:
        db.session.delete(criterion_to_delete)
        db.session.commit()
        flash(f'Критерий "{criterion_to_delete.name}" успешно удален.', 'success')
    except IntegrityError:
        db.session.rollback()
        # Эта ошибка возникнет, если критерий используется в шаблонах номинаций, но по нему еще нет оценок.
        flash(f'Невозможно удалить критерий "{criterion_to_delete.name}", так как он привязан к одному или нескольким шаблонам номинаций.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла непредвиденная ошибка: {e}', 'error')
        
    return redirect(url_for('admin.manage_criteria'))


# routes/admin.py (добавь эту функцию в конец файла)

@admin_bp.route('/assign_winners', methods=['POST'])
@admin_required
def assign_winners():
    try:
        contest_id = request.form.get('contest_id', type=int)
        experience_category = request.form.get('experience_category')

        if not contest_id or not experience_category:
            flash('Не удалось определить конкурс или категорию.', 'error')
            return redirect(url_for('admin.admin_results_view'))

        with db.session.begin_nested():
            # Удаляем старых победителей для этого конкурса и категории
            Winner.query.filter_by(
                time_slot_id=contest_id, 
                experience_category=experience_category
            ).delete()
            
            # --- ИЗМЕНЕНИЕ: Работаем только с 1-м местом ---
            place = 1
            participation_id = request.form.get(f'place_{place}', type=int)
            
            if participation_id:
                new_winner = Winner(
                    participation_id=participation_id,
                    time_slot_id=contest_id,
                    experience_category=experience_category,
                    place=place
                )
                db.session.add(new_winner)
        
        db.session.commit()
        flash(f'Победитель для категории "{experience_category.capitalize()}" успешно назначен!', 'success')

    except IntegrityError as e:
        db.session.rollback()
        flash(f'Ошибка целостности данных. {e}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла непредвиденная ошибка при назначении победителей: {e}', 'error')

    return redirect(url_for('admin.admin_results_view'))