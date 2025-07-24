#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rainbow Towers Conference Room Booking System
Flask Application File with Complete Supabase Integration - ADMIN CLIENT VERSION
WITH QUOTATION AND INVOICE FUNCTIONALITY

This file contains the main application code for the conference room booking system,
including Supabase database integration, authentication, quotation generation, 
invoice creation, and core functionality.
All operations use admin client to bypass RLS while keeping RLS enabled in Supabase.
"""

import os
from datetime import datetime, timedelta, UTC
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, DateTimeField, TextAreaField, IntegerField, DecimalField, SelectMultipleField, HiddenField, FloatField, SubmitField
from wtforms.validators import DataRequired, Email, Length, ValidationError, EqualTo
import json
from decimal import Decimal
from flask_wtf.csrf import CSRFProtect
from supabase import create_client, Client
from dotenv import load_dotenv
import requests
import functools
import traceback
import threading
import pytz
from collections import defaultdict

# Import core functions (will be imported after core.py is available)
# This will be moved after Supabase initialization to avoid circular imports

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Load configuration
try:
    from settings.config import Config, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY
    app.config.from_object(Config)
except ImportError:
    # Fallback configuration if settings/config.py doesn't exist
    print("⚠️  Warning: settings/config.py not found, using fallback configuration")
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key-change-in-production')
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600
    app.config['WTF_CSRF_SSL_STRICT'] = False
    
    # Supabase configuration
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
    SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

# Session configuration
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SUPABASE_TIMEOUT'] = 30
app.config['DATABASE_TIMEOUT'] = 30

# Additional configuration
ACTIVITY_LOG_RETENTION_DAYS = int(os.environ.get('ACTIVITY_LOG_RETENTION_DAYS', 90))
ACTIVITY_LOG_ENABLED = os.environ.get('ACTIVITY_LOG_ENABLED', 'true').lower() == 'true'

# Enhanced Supabase client initialization with better error handling
try:
    print(f"🔍 Initializing Supabase clients...")
    print(f"   URL: {SUPABASE_URL}")
    print(f"   Anon key: {'✅ Set' if SUPABASE_ANON_KEY else '❌ Missing'}")
    print(f"   Service key: {'✅ Set' if SUPABASE_SERVICE_KEY else '❌ Missing'}")
    
    # Initialize regular client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    print("✅ Regular Supabase client initialized")
    
    # Initialize admin client with service key
    if SUPABASE_SERVICE_KEY:
        supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("✅ Admin Supabase client initialized with service key")
    else:
        supabase_admin = supabase
        print("⚠️ Using regular client as admin client (no service key)")
    
    # Test connections
    test_response = supabase_admin.table('rooms').select('count').execute()
    print(f"✅ Database connection test successful")
    
except Exception as e:
    print(f"❌ Supabase initialization failed: {e}")
    print("🔧 Please check your environment variables and Supabase project status")
    # Don't raise here to allow the app to start for debugging
    supabase = None
    supabase_admin = None

# Import core functions after Supabase initialization to avoid circular imports
try:
    from core import (
        authenticate_user, create_user_supabase, 
        supabase_select, supabase_insert, supabase_update, supabase_delete,
        get_clients_with_booking_counts, get_client_by_id_from_db, 
        get_client_bookings_from_db, create_client_in_db, 
        update_client_in_db, delete_client_from_db,
        ActivityTypes, User as CoreUser,
        LoginForm, RegistrationForm, ClientForm
    )
    print("✅ Core functions imported successfully")
    
    # Use core User class instead of local one
    User = CoreUser
    
except ImportError as core_import_error:
    print(f"⚠️  Warning: Could not import core functions: {core_import_error}")
    print("   App will not function properly without core.py")
    
    # Define minimal fallbacks for critical functions to prevent import errors
    class ActivityTypes:
        LOGIN_SUCCESS = 'login_success'
        LOGIN_FAILED = 'login_failed'
        LOGOUT = 'logout'
        CREATE_BOOKING = 'create_booking'
        UPDATE_BOOKING = 'update_booking'
        DELETE_BOOKING = 'delete_booking'
        VIEW_BOOKING = 'view_booking'
        ERROR_OCCURRED = 'error_occurred'
    
    class User:
        def __init__(self, user_data):
            self.id = user_data.get('id')
            self.email = user_data.get('email')
            
        def get_id(self):
            return str(self.id)
    
    def authenticate_user(email, password):
        print("ERROR: Core functions not available - authentication disabled")
        return None
    
    def create_user_supabase(*args, **kwargs):
        print("ERROR: Core functions not available - user creation disabled")
        return False

# Initialize extensions
try:
    csrf = CSRFProtect(app)
    print("✅ CSRF Protection initialized successfully")
except Exception as e:
    print(f"❌ CSRF Protection initialization failed: {e}")
    # Create a dummy csrf object if initialization fails
    class DummyCSRF:
        def exempt(self, f):
            return f
    csrf = DummyCSRF()

login_manager = LoginManager(app)
login_manager.init_app(app)

login_manager.login_view = 'auth.login'

# Register blueprints with error handling
try:
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.clients import clients_bp
    from routes.rooms import rooms_bp
    from routes.bookings import bookings_bp
    from routes.addons import addons_bp
    from routes.reports import reports_bp
    from routes.api import api_bp
    from routes.debug import debug_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(addons_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(debug_bp)
    app.register_blueprint(admin_bp)
    
    print("✅ All blueprints registered successfully")
except ImportError as e:
    print(f"⚠️  Warning: Some blueprints could not be imported: {e}")
    print("   The application will continue but some features may not be available")

# Register template filters with error handling
try:
    from utils import template_filters
    
    app.jinja_env.filters['parse_datetime'] = template_filters.parse_datetime_filter
    app.jinja_env.filters['format_datetime'] = template_filters.format_datetime_filter
    app.jinja_env.filters['format_cat_datetime'] = template_filters.format_cat_datetime_filter
    app.jinja_env.filters['calculate_total'] = template_filters.calculate_total_filter
    app.jinja_env.filters['format_pricing_summary'] = template_filters.format_pricing_summary_filter
    app.jinja_env.filters['money'] = template_filters.money_filter
    app.jinja_env.filters['duration'] = template_filters.duration_filter
    app.jinja_env.filters['booking_status_color'] = template_filters.booking_status_color_filter
    app.jinja_env.filters['nl2br'] = template_filters.nl2br_filter
    app.jinja_env.filters['safe_startswith'] = template_filters.safe_startswith_filter
    app.jinja_env.filters['safe_string'] = template_filters.safe_string_filter
    app.jinja_env.filters['safe_contains'] = template_filters.safe_contains_filter
    app.jinja_env.filters['truncate_safe'] = template_filters.truncate_safe_filter
    app.jinja_env.filters['default_if_none'] = template_filters.default_if_none_filter
    app.jinja_env.filters['format_currency'] = template_filters.format_currency_filter
    app.jinja_env.filters['format_percentage'] = template_filters.format_percentage_filter
    app.jinja_env.filters['time_ago'] = template_filters.time_ago_filter
    app.jinja_env.filters['days_until'] = template_filters.days_until_filter
    
    print("✅ Template filters registered successfully")
except ImportError as e:
    print(f"⚠️  Warning: Template filters could not be imported: {e}")

# Import utility functions with error handling
try:
    from utils.decorators import activity_logged, require_admin_or_manager
    from utils.logging import log_user_activity, log_authentication_activity
    from utils.validation import safe_float_conversion, safe_int_conversion, convert_datetime_strings, validate_booking_times, validate_booking_capacity
except ImportError as e:
    print(f"⚠️  Warning: Some utility functions could not be imported: {e}")
    
    # Create fallback functions
    def activity_logged(activity_type, message):
        def decorator(f):
            return f
        return decorator
    
    def require_admin_or_manager(f):
        return f
    
    def log_user_activity(*args, **kwargs):
        print(f"Activity logged: {args}")
    
    def log_authentication_activity(*args, **kwargs):
        print(f"Auth activity logged: {args}")
    
    def safe_float_conversion(value, default=0.0):
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def safe_int_conversion(value, default=0):
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def convert_datetime_strings(data):
        """Simplified datetime conversion"""
        if isinstance(data, list):
            return [convert_datetime_strings(item) for item in data]
        elif isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if isinstance(value, str) and ('time' in key.lower() or key.endswith('_at')):
                    try:
                        result[key] = datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
                    except:
                        result[key] = value
                else:
                    result[key] = value
            return result
        return data
    
    def validate_booking_times(*args, **kwargs):
        return True
    
    def validate_booking_capacity(*args, **kwargs):
        return True

# Context processors
@app.context_processor
def inject_now():
    """Inject the current datetime into templates."""
    return {'now': datetime.now(UTC)}

@app.context_processor
def utility_processor():
    return {
        'pytz': pytz,
        'timezone': pytz.timezone
    }

# ===============================
# Activity Types
# ===============================

# ActivityTypes class is imported from core.py above

# ===============================
# User Model for Supabase
# ===============================

# User class is imported from core.py above

# ===============================
# Authentication Functions
# ===============================

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        # Try to get user from session first (more reliable)
        if 'user_email' in session and 'user_id' in session and session['user_id'] == user_id:
            # Create user object from session data
            user_dict = {
                'id': session['user_id'],
                'email': session['user_email'],
                'user_metadata': {},
                'app_metadata': {}
            }
            return User(user_dict)
            
        # Fallback: try to get user from users table
        if supabase_admin:
            response = supabase_admin.table('users').select('*').eq('id', user_id).execute()
            if response.data and len(response.data) > 0:
                user_data = response.data[0]
                user_dict = {
                    'id': user_data['id'],
                    'email': user_data['email'],
                    'user_metadata': user_data.get('user_metadata', {}),
                    'app_metadata': user_data.get('app_metadata', {})
                }
                return User(user_dict)
        
        return None
    except Exception as e:
        print(f"Error loading user: {e}")
        return None

# ===============================
# Database Helper Functions and Client Functions
# ===============================

# All database and business logic functions are imported from core.py above
# This eliminates code duplication and ensures consistency across the application

# ===============================
# Forms
# ===============================

# Forms are imported from core.py above (LoginForm, RegistrationForm, ClientForm, etc.)
# This eliminates code duplication and ensures consistency across the application

# ===============================
# Request Handlers
# ===============================

@app.before_request
def production_session_validation():
    """Simplified session validation for production"""
    # Skip validation for static files, debug routes, and auth routes
    if (request.endpoint and 
        (request.endpoint.startswith('static') or 
         request.endpoint.startswith('debug') or
         request.endpoint in ['auth.login', 'auth.logout', 'auth.register', 'health_check'] or
         request.path.startswith('/static/') or
         request.path.startswith('/debug/'))):
        return
    
    # Log basic info in production
    if os.environ.get('FLASK_ENV') == 'production':
        print(f"🔍 PROD: Request to {request.endpoint} by {'authenticated' if current_user.is_authenticated else 'anonymous'} user")
    
    # Simplified validation - only check if user needs to be authenticated
    if not current_user.is_authenticated and request.endpoint not in ['auth.login', 'auth.register', 'health_check']:
        if request.endpoint and not request.endpoint.startswith('static'):
            print(f"🔒 Redirecting unauthenticated user from {request.endpoint} to login")
            return redirect(url_for('auth.login'))

# ===============================
# Error Handlers
# ===============================

@app.errorhandler(400)
def csrf_error(e):
    """Handle CSRF errors"""
    print(f"CSRF Error: {e}")
    if 'CSRF' in str(e) or 'csrf' in str(e).lower():
        flash('Security token expired. Please try again.', 'warning')
        return redirect(request.referrer or url_for('dashboard.dashboard'))
    return render_template('errors/400.html'), 400

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    """Log internal server errors"""
    try:
        log_user_activity(
            ActivityTypes.ERROR_OCCURRED,
            f"Internal server error: {str(e)}",
            status='failed',
            metadata={
                'error_type': '500',
                'url': request.url if request else 'unknown',
                'method': request.method if request else 'unknown'
            }
        )
    except Exception as log_error:
        print(f"Failed to log 500 error: {log_error}")
    
    return render_template('errors/500.html'), 500

# ===============================
# Health Check and Basic Routes
# ===============================

@app.route('/health')
def health_check():
    """Simple health check for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(UTC).isoformat(),
        'database_connected': bool(SUPABASE_URL and SUPABASE_ANON_KEY)
    })

@app.route('/')
def index():
    """Redirect to appropriate page based on auth status"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))  # Changed from dashboard.dashboard
    return redirect(url_for('auth.login'))

# ===============================
# CLI Commands
# ===============================

@app.cli.command('create-admin')
def create_admin_command():
    """Create admin user in Supabase"""
    email = input('Enter admin email: ')
    password = input('Enter admin password: ')
    first_name = input('Enter first name: ')
    last_name = input('Enter last name: ')
    
    try:
        if create_user_supabase(email, password, first_name, last_name, 'admin'):
            print(f'Admin user created successfully: {email}')
            print('Note: Check your email to confirm the account if email confirmation is enabled.')
        else:
            print('Failed to create admin user')
    except Exception as e:
        print(f'Error creating admin user: {e}')

@app.cli.command('test-connection')
def test_supabase_connection():
    """Test Supabase connection"""
    try:
        print('🔍 Testing Supabase connection...')
        print(f'🔗 Connected to: {SUPABASE_URL}')
        
        if not supabase_admin:
            print('❌ Admin client not available')
            return
        
        # Test database connection
        response = supabase_admin.table('rooms').select('id, name').execute()
        print('✅ Supabase database connection successful')
        print(f'✅ Found {len(response.data)} rooms in database')
        
        if response.data:
            print('   📋 Rooms found:')
            for room in response.data:
                print(f'   - {room["name"]}')
        else:
            print('   ⚠️  No rooms found - make sure sample data is inserted')
        
        # Test other tables
        clients = supabase_admin.table('clients').select('id').execute()
        print(f'✅ Found {len(clients.data)} clients')
        
        print('\n🎉 Connection test completed!')
            
    except Exception as e:
        print(f'❌ Supabase connection failed: {e}')
        print('\n🔧 Troubleshooting:')
        print('- Check your .env file has correct SUPABASE_URL and keys')
        print('- Verify your Supabase project is active')

# ===============================
# Main Entry Point
# ===============================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    if os.environ.get('FLASK_ENV') == 'production':
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['WTF_CSRF_SSL_STRICT'] = True
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        app.run(host='0.0.0.0', port=port, debug=True)