from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from utils.logging import log_authentication_activity
from utils.decorators import activity_logged
from utils.validation import validate_booking_times
from settings.config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY
from core import LoginForm, RegistrationForm, authenticate_user, create_user_supabase, ActivityTypes
from datetime import datetime, UTC

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate_user(form.username.data, form.password.data)
        if user:
            log_authentication_activity(ActivityTypes.LOGIN_SUCCESS, user.email, success=True, additional_info={'login_time': datetime.now(UTC).isoformat()})
            login_user(user, remember=form.remember_me.data)
            return redirect(url_for('dashboard.dashboard'))
        else:
            log_authentication_activity(ActivityTypes.LOGIN_FAILED, form.username.data, success=False)
            flash('Invalid email or password', 'danger')
    return render_template('login.html', title='Login', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user, error = create_user_supabase(
            form.email.data,
            form.password.data,
            form.first_name.data,
            form.last_name.data,
            form.role.data
        )
        if user:
            log_authentication_activity(ActivityTypes.REGISTRATION, form.email.data, success=True)
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            log_authentication_activity(ActivityTypes.REGISTRATION, form.email.data, success=False)
            flash(f'Registration failed: {error}', 'danger')
    return render_template('register.html', title='Register', form=form) 