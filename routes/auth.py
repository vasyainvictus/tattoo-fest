# routes/auth.py
# Маршруты для авторизации

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.user import User # Импортируем нашу модель User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Если пользователь уже вошел, перенаправляем его на главную страницу
    if 'user_id' in session:
        # Мы создадим 'main.dashboard' на следующем шаге
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        user_code = request.form.get('code')
        if not user_code:
            flash('Пожалуйста, введите ваш код.', 'error')
            return redirect(url_for('auth.login'))

        # Ищем пользователя в базе данных по коду
        user = User.query.filter_by(code=user_code).first()

        # Проверяем, найден ли пользователь
        if user:
            # Пользователь найден! Сохраняем его ID и роль в сессию.
            # Сессия - это защищенное хранилище данных на стороне сервера.
            session.clear() # Очищаем старую сессию для безопасности
            session['user_id'] = user.id
            session['user_role'] = user.role
            flash('Вход выполнен успешно!', 'success')
            # Перенаправляем на главную страницу (создадим ее позже)
            return redirect(url_for('main.dashboard'))
        else:
            # Пользователь не найден. Показываем ошибку.
            flash('Неверный код доступа. Попробуйте еще раз.', 'error')
            return redirect(url_for('auth.login'))

    # Если метод GET, просто показываем страницу входа
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    # Удаляем данные пользователя из сессии
    session.clear()
    flash('Вы успешно вышли из системы.', 'success')
    # Перенаправляем на страницу входа
    return redirect(url_for('auth.login'))