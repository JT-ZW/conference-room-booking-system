from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from utils.logging import log_authentication_activity
from core import LoginForm, RegistrationForm, authenticate_user, create_user_supabase, ActivityTypes
from datetime import datetime, UTC

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route with enhanced error handling"""
    try:
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))  # Changed from dashboard.dashboard
        
        form = LoginForm()
        if form.validate_on_submit():
            user = authenticate_user(form.username.data, form.password.data)
            if user:
                log_authentication_activity(ActivityTypes.LOGIN_SUCCESS, user.email, 
                    success=True, 
                    additional_info={'login_time': datetime.now(UTC).isoformat()}
                )
                login_user(user, remember=form.remember_me.data)
                print(f"✅ User {user.email} logged in successfully")
                return redirect(url_for('dashboard.index'))  # Changed from dashboard.dashboard
            else:
                log_authentication_activity(ActivityTypes.LOGIN_FAILED, form.username.data, success=False)
                flash('Invalid email or password', 'danger')
                print(f"⚠️ Failed login attempt for: {form.username.data}")
        
        return render_template('login.html', title='Login', form=form)
        
    except Exception as e:
        print(f"❌ ERROR: Login route failed: {e}")
        flash('An error occurred during login. Please try again.', 'danger')
        return render_template('login.html', title='Login', form=LoginForm())

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout route with logging"""
    try:
        user_email = current_user.email if current_user.is_authenticated else 'Unknown'
        logout_user()
        print(f"✅ User {user_email} logged out successfully")
        flash('You have been logged out.', 'info')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        print(f"❌ ERROR: Logout failed: {e}")
        flash('An error occurred during logout.', 'warning')
        return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route with enhanced error handling"""
    try:
        form = RegistrationForm()
        if form.validate_on_submit():
            print(f"🔍 Processing registration for: {form.email.data}")
            user, error = create_user_supabase(
                form.email.data,
                form.password.data,
                form.first_name.data,
                form.last_name.data,
                form.role.data
            )
            if user:
                log_authentication_activity(ActivityTypes.REGISTRATION, form.email.data, success=True)
                print(f"✅ User {form.email.data} registered successfully")
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                log_authentication_activity(ActivityTypes.REGISTRATION, form.email.data, success=False)
                print(f"❌ Registration failed for {form.email.data}: {error}")
                flash(f'Registration failed: {error}', 'danger')
        
        return render_template('register.html', title='Register', form=form)
        
    except Exception as e:
        print(f"❌ ERROR: Registration route failed: {e}")
        flash('An error occurred during registration. Please try again.', 'danger')
        return render_template('register.html', title='Register', form=RegistrationForm())