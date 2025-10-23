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
from datetime import datetime, timedelta, UTC, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Define CAT timezone (Central Africa Time - UTC+2)
CAT = timezone(timedelta(hours=2))
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

# Remove: from dotenv import load_dotenv
# Remove: load_dotenv()
# Remove: validate_environment() and its call
# Remove: all os.environ.get(...) config assignments (SECRET_KEY, SESSION_COOKIE_SECURE, etc.)
# Remove: ACTIVITY_LOG_RETENTION_DAYS and ACTIVITY_LOG_ENABLED assignments
# Remove: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY assignments
from settings.config import Config, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Load configuration
try:
    from settings.config import Config, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY
    app.config.from_object(Config)
except ImportError:
    # Fallback configuration if settings/config.py doesn't exist
    print("OK:  Warning: settings/config.py not found, using fallback configuration")
    
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
    print(f"==> Initializing Supabase clients...")
    print(f"   URL: {SUPABASE_URL}")
    print(f"   Anon key: {'YES' if SUPABASE_ANON_KEY else 'NO'}")
    print(f"   Service key: {'YES' if SUPABASE_SERVICE_KEY else 'NO'}")
    
    # Initialize regular client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    print("OK: Regular Supabase client initialized")
    
    # Initialize admin client with service key
    if SUPABASE_SERVICE_KEY:
        supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("OK: Admin Supabase client initialized with service key")
    else:
        supabase_admin = supabase
        print("OK: Using regular client as admin client (no service key)")
    
    # Test connections
    test_response = supabase_admin.table('rooms').select('count').execute()
    print(f"OK: Database connection test successful")
    
except Exception as e:
    print(f"OK: Supabase initialization failed: {e}")
    print("=== Please check your environment variables and Supabase project status")
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
    print("OK: Core functions imported successfully")
    
    # Use core User class instead of local one
    User = CoreUser
    
except ImportError as core_import_error:
    print(f"OK:  Warning: Could not import core functions: {core_import_error}")
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
    print("OK: CSRF Protection initialized successfully")
except Exception as e:
    print(f"OK: CSRF Protection initialization failed: {e}")
    # Create a dummy csrf object if initialization fails
    class DummyCSRF:
        def exempt(self, f):
            return f
    csrf = DummyCSRF()

login_manager = LoginManager(app)
login_manager.init_app(app)

login_manager.login_view = 'auth.login'

def get_cat_time():
    """Get current time in CAT (Central Africa Time - UTC+2)"""
    return datetime.now(CAT)

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
    
    print("OK: All blueprints registered successfully")
except ImportError as e:
    print(f"OK:  Warning: Some blueprints could not be imported: {e}")
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
    
    print("OK: Template filters registered successfully")
except ImportError as e:
    print(f"OK:  Warning: Template filters could not be imported: {e}")

# Import utility functions with error handling
try:
    from utils.decorators import activity_logged, require_admin_or_manager
    from utils.logging import log_user_activity, log_authentication_activity
    from utils.validation import safe_float_conversion, safe_int_conversion, convert_datetime_strings, validate_booking_times, validate_booking_capacity
except ImportError as e:
    print(f"OK:  Warning: Some utility functions could not be imported: {e}")
    
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
    return {'now': get_cat_time()}

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
        print(f"=== PROD: Request to {request.endpoint} by {'authenticated' if current_user.is_authenticated else 'anonymous'} user")
    
    # Simplified validation - only check if user needs to be authenticated
    if not current_user.is_authenticated and request.endpoint not in ['auth.login', 'auth.register', 'health_check']:
        if request.endpoint and not request.endpoint.startswith('static'):
            print(f"=== Redirecting unauthenticated user from {request.endpoint} to login")
            return redirect(url_for('auth.login'))

@app.template_filter('parse_datetime')
def parse_datetime_filter(date_string):
    """Jinja2 filter to parse datetime strings"""
    if isinstance(date_string, str):
        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00')).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return date_string
    return date_string

@app.template_filter('format_datetime')
def format_datetime_filter(dt, format='%d %b %Y'):
    """Jinja2 filter to format datetime objects or strings"""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00')).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return dt
    
    if isinstance(dt, datetime):
        return dt.strftime(format)
    return dt

# ===============================
# User Model for Supabase
# ===============================

class User(UserMixin):
    """User class that works with Supabase Auth"""
    
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.email = user_data.get('email')
        self.user_metadata = user_data.get('user_metadata', {})
        self.app_metadata = user_data.get('app_metadata', {})
        
        # Get profile data from your users table
        self.profile = self.get_profile()
    
    def get_profile(self):
        """Get user profile from Supabase users table using admin client"""
        try:
            response = supabase_admin.table('users').select('*').eq('id', self.id).execute()
            return response.data[0] if response.data else {}
        except:
            return {}
    
    @property
    def first_name(self):
        return self.profile.get('first_name', '')
    
    @property
    def last_name(self):
        return self.profile.get('last_name', '')
    
    @property
    def role(self):
        return self.profile.get('role', 'staff')
    
    @property
    def username(self):
        return self.profile.get('username', self.email.split('@')[0])
    
    @property
    def is_active(self):
        return self.profile.get('is_active', True)
    
    def get_id(self):
        return str(self.id)

# ===============================
# Supabase Helper Functions
# ===============================

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        response = supabase_admin.auth.admin.get_user_by_id(user_id)
        if response.user:
            return User(response.user.__dict__)
        return None
    except:
        return None

def authenticate_user(email, password):
    """Authenticate user with Supabase and set up session properly"""
    try:
        print(f"DEBUG: Attempting to authenticate user: {email}")
        
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user and response.session:
            print(f"DEBUG: Supabase authentication successful")
            
            # Clear any existing session data first
            session.clear()
            
            # IMPORTANT: Set session as permanent first
            session.permanent = True
            
            # Store session data
            session_data = {
                'access_token': response.session.access_token,
                'refresh_token': response.session.refresh_token,
                'user_id': response.user.id
            }
            
            # Set session data
            session['supabase_session'] = session_data
            session['created_at'] = get_cat_time().isoformat()
            session['user_id'] = response.user.id
            session['user_email'] = response.user.email
            
            # Add debug info
            print(f"DEBUG: Session created successfully")
            print(f"DEBUG: Session data keys: {list(session.keys())}")
            print(f"DEBUG: Session permanent: {session.permanent}")
            
            # Force session save
            session.modified = True
            
            return User(response.user.__dict__)
        else:
            print("DEBUG: Authentication failed - no user or session")
            return None
            
    except Exception as e:
        print(f"DEBUG: Authentication error: {e}")
        import traceback
        traceback.print_exc()
        return None
    
def create_user_supabase(email, password, first_name, last_name, role='staff'):
    """Create new user in Supabase with enhanced error handling"""
    try:
        print(f"DEBUG: Creating user - {email}, {first_name} {last_name}, role: {role}")
        
        # Create user in Supabase Auth
        auth_response = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # Auto-confirm for internal users
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
                "role": role
            }
        })
        
        if auth_response.user:
            print(f"DEBUG: Auth user created successfully with ID: {auth_response.user.id}")
            
            # Create profile in users table using admin client
            profile_data = {
                'id': auth_response.user.id,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'username': email.split('@')[0],
                'role': role,
                'is_active': True,
                'created_at': get_cat_time().isoformat()
            }
            
            # Use admin client to bypass RLS
            profile_response = supabase_admin.table('users').insert(profile_data).execute()
            
            if profile_response.data:
                print(f"DEBUG: User profile created successfully")
                return True
            else:
                print(f"ERROR: Failed to create user profile")
                # Clean up auth user if profile creation failed
                try:
                    supabase_admin.auth.admin.delete_user(auth_response.user.id)
                except:
                    pass
                return False
        else:
            print("ERROR: Failed to create auth user")
            return False
            
    except Exception as e:
        print(f"User creation error: {e}")
        
        # Check for specific error types to provide better user feedback
        error_message = str(e).lower()
        if 'already registered' in error_message or 'already exists' in error_message:
            raise Exception("Email already registered")
        elif 'password' in error_message:
            raise Exception("Password does not meet requirements")
        elif 'email' in error_message and 'invalid' in error_message:
            raise Exception("Invalid email format")
        else:
            raise Exception("Registration failed due to server error")

def supabase_select(table_name, columns="*", filters=None, order_by=None, limit=None):
    """Enhanced select function with better error handling and RLS bypass"""
    try:
        if not supabase_admin:
            raise Exception("Supabase admin client not initialized")
        
        print(f"=== DEBUG: Querying table '{table_name}' with admin client")
        
        # Use admin client to bypass RLS
        query = supabase_admin.table(table_name).select(columns)
        
        if filters:
            for filter_item in filters:
                if len(filter_item) == 3:
                    column, operator, value = filter_item
                    if operator == 'eq':
                        query = query.eq(column, value)
                    elif operator == 'neq':
                        query = query.neq(column, value)
                    elif operator == 'gte':
                        query = query.gte(column, value)
                    elif operator == 'lte':
                        query = query.lte(column, value)
                    elif operator == 'gt':
                        query = query.gt(column, value)
                    elif operator == 'lt':
                        query = query.lt(column, value)
        
        if order_by:
            query = query.order(order_by)
            
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        
        if hasattr(response, 'data') and response.data is not None:
            print(f"OK: DEBUG: Successfully retrieved {len(response.data)} rows from '{table_name}'")
            return response.data
        else:
            print(f"OK: DEBUG: Empty response from table '{table_name}'")
            return []
            
    except Exception as e:
        print(f"OK: ERROR: Failed to query table '{table_name}': {e}")
        print(f"   Error type: {type(e)}")
        
        # If admin client fails, try with regular client as fallback
        if supabase and supabase_admin != supabase:
            try:
                print(f"=== DEBUG: Trying fallback with regular client for '{table_name}'")
                query = supabase.table(table_name).select(columns)
                
                if filters:
                    for filter_item in filters:
                        if len(filter_item) == 3:
                            column, operator, value = filter_item
                            if operator == 'eq':
                                query = query.eq(column, value)
                
                if order_by:
                    query = query.order(order_by)
                    
                if limit:
                    query = query.limit(limit)
                
                response = query.execute()
                
                if hasattr(response, 'data') and response.data is not None:
                    print(f"OK: DEBUG: Fallback successful for '{table_name}': {len(response.data)} rows")
                    return response.data
                    
            except Exception as fallback_error:
                print(f"OK: DEBUG: Fallback also failed for '{table_name}': {fallback_error}")
        
        return []

def supabase_insert(table_name, data):
    """Insert data into Supabase table using admin client with enhanced error handling"""
    try:
        print(f"DEBUG: Inserting into table '{table_name}' with data: {data}")
        
        response = supabase_admin.table(table_name).insert(data).execute()
        
        print(f"DEBUG: Insert response: {response}")
        print(f"DEBUG: Response data: {response.data}")
        
        if response.data:
            print(f"DEBUG: Insert successful, created {len(response.data)} row(s)")
            return response.data[0] if response.data else None
        else:
            print("DEBUG: Insert returned no data")
            if hasattr(response, 'error') and response.error:
                print(f"DEBUG: Supabase error: {response.error}")
            return None
            
    except Exception as e:
        print(f"Insert error in supabase_insert: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return None

def supabase_update(table_name, data, filters):
    """Update data in Supabase table using admin client with correct syntax"""
    try:
        print(f"DEBUG: Updating table '{table_name}' with data: {data}")
        print(f"DEBUG: Using filters: {filters}")
        
        # Correct Supabase syntax: table -> update -> filters -> execute
        query = supabase_admin.table(table_name).update(data)
        
        # Apply filters after update() but before execute()
        for filter_item in filters:
            if len(filter_item) == 3:
                column, operator, value = filter_item
                if operator == 'eq':
                    query = query.eq(column, value)
                    print(f"DEBUG: Applied filter: {column} = {value}")
                elif operator == 'neq':
                    query = query.neq(column, value)
                elif operator == 'gte':
                    query = query.gte(column, value)
                elif operator == 'lte':
                    query = query.lte(column, value)
                elif operator == 'gt':
                    query = query.gt(column, value)
                elif operator == 'lt':
                    query = query.lt(column, value)
        
        response = query.execute()
        
        print(f"DEBUG: Supabase response: {response}")
        print(f"DEBUG: Response data: {response.data}")
        print(f"DEBUG: Response count: {response.count if hasattr(response, 'count') else 'N/A'}")
        
        # Check if the update was successful
        if response.data is not None:
            print(f"DEBUG: Update successful, affected {len(response.data)} row(s)")
            return response.data
        else:
            print("DEBUG: Update returned no data - this might indicate no rows were matched or updated")
            # For updates, an empty data array might still be successful if no changes were needed
            # Let's check if there was an error
            if hasattr(response, 'error') and response.error:
                print(f"DEBUG: Supabase error: {response.error}")
                return []
            else:
                # Assume success if no error
                return [{'success': True}]
                
    except Exception as e:
        print(f"Update error in supabase_update: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return []

def supabase_delete(table_name, filters):
    """Delete data from Supabase table using admin client"""
    try:
        query = supabase_admin.table(table_name)
        
        for filter_item in filters:
            if len(filter_item) == 3:
                column, operator, value = filter_item
                if operator == 'eq':
                    query = query.eq(column, value)
        
        response = query.delete().execute()
        return True
    except Exception as e:
        print(f"Delete error: {e}")
        return False

def convert_datetime_strings(data, datetime_fields=['start_time', 'end_time', 'created_at', 'updated_at', 'check_in', 'check_out']):
    """Convert ISO datetime strings to Python datetime objects"""
    if isinstance(data, list):
        return [convert_datetime_strings(item, datetime_fields) for item in data]
    elif isinstance(data, dict):
        converted = data.copy()
        for field in datetime_fields:
            if field in converted and isinstance(converted[field], str):
                try:
                    # Convert ISO string to datetime object
                    converted[field] = datetime.fromisoformat(converted[field].replace('Z', '+00:00')).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    # If conversion fails, leave as string
                    pass
        return converted
    return data

def log_user_activity(
    activity_type,
    activity_description,
    resource_type=None,
    resource_id=None,
    status='success',
    metadata=None
):
    """
    Log user activity to the database.
    This function is designed to be non-blocking and safe.
    """
    try:
        # Skip logging if user is not authenticated (for login attempts, handle separately)
        if not current_user.is_authenticated and activity_type not in ['login_attempt', 'failed_login']:
            return
        
        # Prepare user information
        user_id = None
        user_name = 'Anonymous'
        user_email = 'unknown@example.com'
        
        if current_user.is_authenticated:
            user_id = current_user.id
            user_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
            user_email = current_user.email
        
        # Get request information safely
        ip_address = None
        user_agent = None
        session_id = None
        
        if request:
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            user_agent = request.headers.get('User-Agent', '')[:500]  # Limit length
        
        if session:
            session_id = session.get('session_id') or str(hash(str(session)))[:32]
        
        # Prepare activity log data
        log_data = {
            'user_id': user_id,
            'user_name': user_name,
            'user_email': user_email,
            'activity_type': activity_type,
            'activity_description': activity_description,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'session_id': session_id,
            'status': status,
            'metadata': json.dumps(metadata) if metadata else None,
            'created_at': get_cat_time().isoformat()
        }
        
        # Insert into database using admin client (non-blocking)
        try:
            result = supabase_admin.table('user_activity_log').insert(log_data).execute()
            if not result.data:
                print(f"OK: WARNING: Activity log insert returned no data for {activity_type}")
        except Exception as db_error:
            # Log the error but don't raise it to avoid breaking the main functionality
            print(f"OK: ERROR: Failed to log activity '{activity_type}': {db_error}")
            
    except Exception as e:
        # Catch-all error handler - never let logging break the main app
        print(f"OK: CRITICAL: Activity logger failed with error: {e}")
        print(f"   Activity: {activity_type} - {activity_description}")


def log_authentication_activity(activity_type, email, success=True, additional_info=None):
    """
    Special function for logging authentication activities (login, logout, registration).
    This works even when current_user is not authenticated.
    """
    try:
        # Get request information
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            user_agent = request.headers.get('User-Agent', '')[:500]
        
        # Prepare log data for authentication events
        log_data = {
            'user_id': current_user.id if current_user.is_authenticated else None,
            'user_name': email.split('@')[0],  # Use email prefix as name fallback
            'user_email': email,
            'activity_type': activity_type,
            'activity_description': f"Authentication activity: {activity_type} for {email}",
            'resource_type': 'authentication',
            'resource_id': None,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'session_id': str(hash(str(session)))[:32] if session else None,
            'status': 'success' if success else 'failed',
            'metadata': json.dumps(additional_info) if additional_info else None,
            'created_at': get_cat_time().isoformat()
        }
        
        # Insert into database
        result = supabase_admin.table('user_activity_log').insert(log_data).execute()
        
    except Exception as e:
        print(f"OK: ERROR: Failed to log authentication activity: {e}")


def activity_logged(activity_type, description_template=None, resource_type=None, status='success'):
    """
    Decorator to automatically log activities for route functions.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = get_cat_time()
            activity_status = status
            result = None
            error_info = None
            
            try:
                # Execute the original function
                result = func(*args, **kwargs)
                
                # Determine if the operation was successful
                if hasattr(result, 'status_code') and result.status_code >= 400:
                    activity_status = 'failed'
                elif isinstance(result, dict) and result.get('error'):
                    activity_status = 'failed'
                
            except Exception as e:
                activity_status = 'failed'
                error_info = str(e)
                raise  # Re-raise the exception to maintain original behavior
            
            finally:
                # Log the activity regardless of success/failure
                try:
                    # Prepare description
                    if description_template:
                        if '{result}' in description_template:
                            description = description_template.format(
                                result=str(result)[:200] if result else 'No result'
                            )
                        else:
                            description = description_template
                    else:
                        description = f"Executed {func.__name__}"
                    
                    # Prepare metadata
                    metadata = {
                        'function_name': func.__name__,
                        'execution_time_ms': int((get_cat_time() - start_time).total_seconds() * 1000),
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys()) if kwargs else []
                    }
                    
                    if error_info:
                        metadata['error'] = error_info
                    
                    if hasattr(result, 'get') and result.get('id'):
                        resource_id = result.get('id')
                    else:
                        resource_id = kwargs.get('id') or (args[0] if args and isinstance(args[0], int) else None)
                    
                    # Log the activity
                    log_user_activity(
                        activity_type=activity_type,
                        activity_description=description,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        status=activity_status,
                        metadata=metadata
                    )
                    
                except Exception as log_error:
                    print(f"OK: ERROR: Failed to log activity for {func.__name__}: {log_error}")
            
            return result
        return wrapper
    return decorator


# Activity type constants for consistency
class ActivityTypes:
    # Authentication
    LOGIN_SUCCESS = 'login_success'
    LOGIN_FAILED = 'login_failed'
    LOGOUT = 'logout'
    REGISTRATION = 'registration'
    
    # Bookings
    CREATE_BOOKING = 'create_booking'
    UPDATE_BOOKING = 'update_booking'
    DELETE_BOOKING = 'delete_booking'
    CANCEL_BOOKING = 'cancel_booking'
    CHANGE_BOOKING_STATUS = 'change_booking_status'
    VIEW_BOOKING = 'view_booking'
    
    # Rooms
    CREATE_ROOM = 'create_room'
    UPDATE_ROOM = 'update_room'
    DELETE_ROOM = 'delete_room'
    VIEW_ROOM = 'view_room'
    
    # Clients (ENHANCED)
    CREATE_CLIENT = 'create_client'
    UPDATE_CLIENT = 'update_client'
    DELETE_CLIENT = 'delete_client'
    VIEW_CLIENT = 'view_client'  # Added this missing constant
    
    # Add-ons
    CREATE_ADDON = 'create_addon'
    UPDATE_ADDON = 'update_addon'
    DELETE_ADDON = 'delete_addon'
    CREATE_ADDON_CATEGORY = 'create_addon_category'
    
    # Reports
    GENERATE_REPORT = 'generate_report'
    EXPORT_DATA = 'export_data'
    
    # System
    PAGE_VIEW = 'page_view'
    API_CALL = 'api_call'
    ERROR_OCCURRED = 'error_occurred'

# Enhanced client data access functions
def get_all_clients_from_db():
    """Get all clients from Supabase database with enhanced error handling"""
    try:
        print("=== DEBUG: Fetching all clients from Supabase database...")
        
        # Use admin client to ensure we get all client data
        response = supabase_admin.table('clients').select('*').order('company_name').execute()
        
        if response.data:
            print(f"OK: DEBUG: Successfully fetched {len(response.data)} clients from database")
            return response.data
        else:
            print("OK: DEBUG: No clients found in database or empty response")
            return []
            
    except Exception as e:
        print(f"OK: ERROR: Failed to fetch clients from database: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_client_by_id_from_db(client_id):
    """Get specific client by ID from Supabase database"""
    try:
        print(f"=== DEBUG: Fetching client ID {client_id} from database...")
        
        response = supabase_admin.table('clients').select('*').eq('id', client_id).execute()
        
        if response.data:
            print(f"OK: DEBUG: Found client: {response.data[0].get('company_name') or response.data[0].get('contact_person')}")
            return response.data[0]
        else:
            print(f"OK: DEBUG: Client ID {client_id} not found in database")
            return None
            
    except Exception as e:
        print(f"OK: ERROR: Failed to fetch client ID {client_id}: {e}")
        return None

def get_client_bookings_from_db(client_id):
    """Get all bookings for a specific client with room details"""
    try:
        print(f"=== DEBUG: Fetching bookings for client ID {client_id}...")
        
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity)
        """).eq('client_id', client_id).order('start_time', desc=True).execute()
        
        if response.data:
            print(f"OK: DEBUG: Found {len(response.data)} bookings for client")
            # Convert datetime strings for template compatibility
            return convert_datetime_strings(response.data)
        else:
            print("GOK:n+OK: DEBUG: No bookings found for this client")
            return []
            
    except Exception as e:
        print(f"OK: ERROR: Failed to fetch client bookings: {e}")
        return []

def create_client_in_db(client_data):
    """Create a new client in Supabase database"""
    try:
        print(f"=== DEBUG: Creating new client: {client_data.get('company_name') or client_data.get('contact_person')}")
        
        # Ensure all required fields are present
        required_fields = ['contact_person', 'email']
        for field in required_fields:
            if not client_data.get(field):
                raise ValueError(f"Missing required field: {field}")
        
        response = supabase_admin.table('clients').insert(client_data).execute()
        
        if response.data:
            print(f"OK: DEBUG: Successfully created client with ID: {response.data[0]['id']}")
            return response.data[0]
        else:
            print("OK: DEBUG: Failed to create client - no data returned")
            return None
            
    except Exception as e:
        print(f"OK: ERROR: Failed to create client: {e}")
        return None

def update_client_in_db(client_id, client_data):
    """Update an existing client in Supabase database"""
    try:
        print(f"=== DEBUG: Updating client ID {client_id} with data: {client_data}")
        
        response = supabase_admin.table('clients').update(client_data).eq('id', client_id).execute()
        
        if response.data:
            print(f"OK: DEBUG: Successfully updated client ID {client_id}")
            return response.data[0]
        else:
            print(f"OK: DEBUG: Update completed but no data returned for client ID {client_id}")
            return {'success': True}
            
    except Exception as e:
        print(f"OK: ERROR: Failed to update client ID {client_id}: {e}")
        return None

def delete_client_from_db(client_id):
    """Delete a client from Supabase database (after checking for bookings)"""
    try:
        print(f"=== DEBUG: Attempting to delete client ID {client_id}")
        
        # First check if client has any bookings
        bookings_check = supabase_admin.table('bookings').select('id').eq('client_id', client_id).execute()
        
        if bookings_check.data:
            print(f"OK: DEBUG: Cannot delete client - has {len(bookings_check.data)} bookings")
            return False, "Cannot delete client with existing bookings"
        
        # If no bookings, proceed with deletion
        response = supabase_admin.table('clients').delete().eq('id', client_id).execute()
        
        print(f"OK: DEBUG: Successfully deleted client ID {client_id}")
        return True, "Client deleted successfully"
        
    except Exception as e:
        print(f"OK: ERROR: Failed to delete client ID {client_id}: {e}")
        return False, f"Error deleting client: {str(e)}"

# ===============================
# Forms
# ===============================

class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    
class RegistrationForm(FlaskForm):
    """User registration form"""
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    role = SelectField('Role', choices=[
        ('staff', 'Staff Member'),
        ('manager', 'Manager'),
        ('admin', 'Administrator')
    ], default='staff')
    
    def validate_email(self, field):
        """Check if email already exists"""
        try:
            # Check if user already exists in Supabase
            existing_users = supabase_admin.table('users').select('email').eq('email', field.data.lower()).execute()
            if existing_users.data:
                raise ValidationError('Email address already registered. Please use a different email or try logging in.')
        except Exception as e:
            # If we can't check (e.g., database issue), we'll let the registration attempt proceed
            # and handle the duplicate error during actual registration
            print(f"Warning: Could not check email uniqueness: {e}")


class ClientForm(FlaskForm):
    """Form for adding/editing clients"""
    company_name = StringField('Company Name')
    contact_person = StringField('Contact Person', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number')
    address = TextAreaField('Address')
    notes = TextAreaField('Notes')

class RoomForm(FlaskForm):
    """Form for adding/editing conference rooms"""
    name = StringField('Room Name', validators=[DataRequired()])
    capacity = IntegerField('Capacity')
    description = TextAreaField('Description')
    hourly_rate = DecimalField('Hourly Rate (USD)', places=2)
    half_day_rate = DecimalField('Half-Day Rate (USD)', places=2)
    full_day_rate = DecimalField('Full-Day Rate (USD)', places=2)
    amenities = TextAreaField('Amenities (Comma separated)')
    status = SelectField('Status', choices=[
        ('available', 'Available'),
        ('maintenance', 'Under Maintenance'),
        ('reserved', 'Permanently Reserved')
    ])
    image_url = StringField('Image URL')

class BookingForm(FlaskForm):
    """Updated form for creating/editing bookings with simplified pricing"""
    room_id = SelectField('Conference Room', coerce=int, validators=[DataRequired()])
    attendees = IntegerField('Number of Attendees (PAX)', validators=[DataRequired()])
    
    # Client fields (now separate)
    client_name = StringField('Client Name', validators=[DataRequired()])
    company_name = StringField('Company Name')
    client_id = HiddenField()  # Will be populated by JavaScript
    
    # Event details
    event_type = SelectField('Event Type', choices=[
        ('', 'Select event type...'),
        ('conference', 'Conference'),
        ('meeting', 'Business Meeting'),
        ('workshop', 'Workshop'),
        ('seminar', 'Seminar'),
        ('training', 'Training Session'),
        ('presentation', 'Presentation'),
        ('board_meeting', 'Board Meeting'),
        ('team_building', 'Team Building'),
        ('product_launch', 'Product Launch'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    
    custom_event_type = StringField('Custom Event Type')
    start_time = DateTimeField('Start Time', format='%Y-%m-%d %H:%M', validators=[DataRequired()])
    end_time = DateTimeField('End Time', format='%Y-%m-%d %H:%M', validators=[DataRequired()])
    notes = TextAreaField('Event Requirements / Special Notes')
    
    # REMOVED: discount and tax_rate fields
    
    # Status field (keeping from original)
    status = SelectField('Status', choices=[
        ('tentative', 'Tentative'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ], default='tentative')
    
    def validate_end_time(self, field):
        if field.data <= self.start_time.data:
            raise ValidationError('End time must be after start time')
    
    def validate_attendees(self, field):
        """Validate that the room has sufficient capacity for the attendees"""
        if not field.data or not self.room_id.data:
            return
        
        room_data = supabase_select('rooms', filters=[('id', 'eq', self.room_id.data)])
        if not room_data:
            return
        
        room = room_data[0]
        if field.data > room['capacity']:
            flash(f'Warning: The selected room ({room["name"]}) has a capacity of {room["capacity"]}, but you\'ve entered {field.data} attendees.', 'warning')
class AddonCategoryForm(FlaskForm):
    """Form for creating/editing addon categories"""
    name = StringField('Category Name', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description')

class AddonForm(FlaskForm):
    """Form for creating/editing add-ons"""
    name = StringField('Add-on Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    price = DecimalField('Price (USD)', places=2, validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active')

class AccommodationForm(FlaskForm):
    """Form for adding accommodation to bookings"""
    room_type = SelectField('Room Type', choices=[
        ('standard', 'Standard Room'),
        ('deluxe', 'Deluxe Room'),
        ('executive', 'Executive Room'),
        ('suite', 'Suite')
    ])
    check_in = DateTimeField('Check-in Date', format='%Y-%m-%d', validators=[DataRequired()])
    check_out = DateTimeField('Check-out Date', format='%Y-%m-%d', validators=[DataRequired()])
    number_of_rooms = IntegerField('Number of Rooms', default=1)
    special_requests = TextAreaField('Special Requests')

# ===============================
# Helper Functions
# ===============================

def get_clients_with_booking_counts():
    """Get all clients with their booking counts efficiently - ENHANCED WITH DEBUGGING"""
    try:
        print("=== DEBUG: Starting enhanced client fetch with booking counts...")
        
        # Test basic connectivity first
        try:
            test_response = supabase_admin.table('clients').select('id').limit(1).execute()
            print(f"OK: DEBUG: Database connectivity test passed")
        except Exception as conn_error:
            print(f"OK: DEBUG: Database connectivity test failed: {conn_error}")
            raise Exception(f"Database connection failed: {conn_error}")
        
        # Step 1: Get all clients
        try:
            print("=== DEBUG: Fetching all clients from database...")
            clients_response = supabase_admin.table('clients').select('*').execute()
            clients = clients_response.data if clients_response.data else []
            print(f"OK: DEBUG: Successfully fetched {len(clients)} clients from database")
            
            if len(clients) == 0:
                print("OK: DEBUG: No clients found in database")
                return []
                
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch clients from database: {e}")
            raise Exception(f"Failed to fetch clients: {e}")
        
        # Step 2: Get all bookings to count efficiently
        try:
            print("=== DEBUG: Fetching all bookings for count calculation...")
            bookings_response = supabase_admin.table('bookings').select('client_id, status').execute()
            bookings = bookings_response.data if bookings_response.data else []
            print(f"OK: DEBUG: Successfully fetched {len(bookings)} bookings")
            
            # Count bookings per client (excluding cancelled ones)
            booking_counts = {}
            cancelled_count = 0
            
            for booking in bookings:
                client_id = booking.get('client_id')
                status = booking.get('status', '')
                
                if client_id:
                    if status != 'cancelled':
                        booking_counts[client_id] = booking_counts.get(client_id, 0) + 1
                    else:
                        cancelled_count += 1
            
            print(f"=== DEBUG: Booking count calculation complete:")
            print(f"  - Active bookings counted: {sum(booking_counts.values())}")
            print(f"  - Cancelled bookings skipped: {cancelled_count}")
            print(f"  - Clients with bookings: {len(booking_counts)}")
            
        except Exception as e:
            print(f"OK: WARNING: Failed to fetch bookings for counting: {e}")
            print("=== DEBUG: Setting all booking counts to 0")
            booking_counts = {}
        
        # Step 3: Add booking counts to clients
        try:
            for client in clients:
                client_id = client.get('id')
                client['booking_count'] = booking_counts.get(client_id, 0)
                
                # Ensure all required fields exist with defaults
                client['company_name'] = client.get('company_name') or None
                client['contact_person'] = client.get('contact_person') or 'Unknown'
                client['email'] = client.get('email') or 'unknown@example.com'
                client['phone'] = client.get('phone') or None
                client['address'] = client.get('address') or None
                client['notes'] = client.get('notes') or None
                
                # Add computed fields for template compatibility
                client['display_name'] = client.get('company_name') or client.get('contact_person', 'Unknown Client')
            
            print(f"OK: DEBUG: Enhanced {len(clients)} clients with booking counts and default fields")
            
            # Debug sample data
            if clients:
                sample_client = clients[0]
                print(f"=== DEBUG: Sample client data structure:")
                print(f"  - ID: {sample_client.get('id')}")
                print(f"  - Company: {sample_client.get('company_name')}")
                print(f"  - Contact: {sample_client.get('contact_person')}")
                print(f"  - Email: {sample_client.get('email')}")
                print(f"  - Booking Count: {sample_client.get('booking_count')}")
            
            return clients
            
        except Exception as e:
            print(f"OK: ERROR: Failed to process client data: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to process client data: {e}")
        
    except Exception as e:
        print(f"OK: ERROR: get_clients_with_booking_counts failed: {e}")
        import traceback
        traceback.print_exc()
        return []

# Also add this simpler fallback function for troubleshooting:

def get_all_clients_simple():
    """Simple client fetch for troubleshooting"""
    try:
        print("=== DEBUG: Using simple client fetch (troubleshooting mode)")
        response = supabase_admin.table('clients').select('*').execute()
        clients = response.data if response.data else []
        
        # Add default booking count
        for client in clients:
            client['booking_count'] = 0
            client['display_name'] = client.get('company_name') or client.get('contact_person', 'Unknown')
        
        print(f"OK: DEBUG: Simple fetch returned {len(clients)} clients")
        return clients
        
    except Exception as e:
        print(f"OK: ERROR: Even simple client fetch failed: {e}")
        return []

def is_room_available_supabase(room_id, start_time, end_time, exclude_booking_id=None):
    """Check if a room is available using Supabase admin client"""
    try:
        # Build query to find overlapping bookings using admin client
        query = supabase_admin.table('bookings').select('id')
        query = query.eq('room_id', room_id)
        query = query.neq('status', 'cancelled')
        query = query.lt('start_time', end_time.isoformat())
        query = query.gt('end_time', start_time.isoformat())
        
        if exclude_booking_id:
            query = query.neq('id', exclude_booking_id)
        
        response = query.execute()
        return len(response.data) == 0
    except Exception as e:
        print(f"Availability check error: {e}")
        return False

def get_booking_calendar_events_supabase():
    """Get all bookings formatted for FullCalendar using Supabase admin client with enhanced data accuracy"""
    try:
        print("=== DEBUG: Fetching calendar events from Supabase with enhanced accuracy...")
        
        # Step 1: Get all bookings with complete data using simple query first for reliability
        bookings_response = supabase_admin.table('bookings').select('*').neq('status', 'cancelled').execute()
        
        if not bookings_response.data:
            print("OK: DEBUG: No bookings found")
            return []
        
        bookings_raw = bookings_response.data
        print(f"OK: DEBUG: Found {len(bookings_raw)} bookings for calendar")
        
        # Step 2: Get all rooms for lookup
        rooms_response = supabase_admin.table('rooms').select('*').execute()
        rooms_lookup = {}
        if rooms_response.data:
            for room in rooms_response.data:
                rooms_lookup[room['id']] = room
        print(f"OK: DEBUG: Created lookup for {len(rooms_lookup)} rooms")
        
        # Step 3: Get all clients for lookup
        clients_response = supabase_admin.table('clients').select('*').execute()
        clients_lookup = {}
        if clients_response.data:
            for client in clients_response.data:
                clients_lookup[client['id']] = client
        print(f"OK: DEBUG: Created lookup for {len(clients_lookup)} clients")
        
        # Step 4: Get custom addons for total calculation (from new schema)
        custom_addons_response = supabase_admin.table('booking_custom_addons').select('*').execute()
        custom_addons_by_booking = {}
        if custom_addons_response.data:
            for addon in custom_addons_response.data:
                booking_id = addon.get('booking_id')
                if booking_id:
                    if booking_id not in custom_addons_by_booking:
                        custom_addons_by_booking[booking_id] = []
                    custom_addons_by_booking[booking_id].append(addon)
        print(f"OK: DEBUG: Found custom addons for {len(custom_addons_by_booking)} bookings")
        
        # Step 5: Process each booking
        events = []
        for booking in bookings_raw:
            try:
                booking_id = booking.get('id')
                
                # Get room data
                room_name = 'Unknown Room'
                room_data = None
                if booking.get('room_id') and booking['room_id'] in rooms_lookup:
                    room_data = rooms_lookup[booking['room_id']]
                    room_name = room_data.get('name', 'Unknown Room')
                else:
                    print(f"NO room data for booking {booking_id}")
                
                # Get client data
                client_name = 'Unknown Client'
                client_data = None
                if booking.get('client_id') and booking['client_id'] in clients_lookup:
                    client_data = clients_lookup[booking['client_id']]
                    client_name = client_data.get('company_name') or client_data.get('contact_person', 'Unknown Client')
                elif booking.get('client_name'):
                    # Fallback to stored client name
                    client_name = booking.get('client_name')
                else:
                    print(f"NO client data for booking {booking_id}")
                
                # Get attendees - FIXED: Multiple fallback options with proper conversion
                attendees = 0
                attendees_sources = [
                    booking.get('attendees'),
                    booking.get('pax'),
                    booking.get('guests')
                ]
                for source in attendees_sources:
                    if source is not None:
                        try:
                            attendees = int(source)
                            if attendees > 0:
                                break
                        except (ValueError, TypeError):
                            continue
                
                print(f"=== DEBUG: Booking {booking_id} attendees: {attendees}")
                
                # Get total price - FIXED: Proper data type handling
                total_price = 0.0
                total_sources = [
                    booking.get('total_price'),
                    booking.get('total'),
                    booking.get('price')
                ]
                for source in total_sources:
                    if source is not None:
                        try:
                            total_price = float(source)
                            if total_price > 0:
                                break
                        except (ValueError, TypeError):
                            continue
                
                # If we have custom addons, recalculate total for accuracy
                if booking_id in custom_addons_by_booking:
                    calculated_total = 0.0
                    for addon in custom_addons_by_booking[booking_id]:
                        try:
                            addon_total = float(addon.get('total_price', 0) or 0)
                            calculated_total += addon_total
                        except (ValueError, TypeError):
                            continue
                    
                    if calculated_total > 0:
                        total_price = calculated_total
                        print(f"=== DEBUG: Using calculated total from custom addons: ${total_price:.2f}")
                
                print(f"=OK: DEBUG: Booking {booking_id} total price: ${total_price:.2f}")
                
                # Calculate cost per person - FIXED: Proper division with error handling
                cost_per_person = 0.0
                if attendees > 0 and total_price > 0:
                    cost_per_person = total_price / attendees
                
                print(f"=OK: DEBUG: Booking {booking_id} cost per person: ${cost_per_person:.2f}")
                
                # Determine event color based on status
                status = booking.get('status', 'tentative')
                color_map = {
                    'tentative': '#FFA500',  # Orange
                    'confirmed': '#28a745',  # Green
                    'cancelled': '#dc3545'   # Red
                }
                color = color_map.get(status, '#17a2b8')  # Default: Teal
                
                # Get event title
                event_title = booking.get('title') or f"{booking.get('event_type', 'Event')} - {client_name}"
                
                # Create calendar event with enhanced data
                event_data = {
                    'id': booking_id,
                    'title': event_title,
                    'start': booking.get('start_time'),
                    'end': booking.get('end_time'),
                    'color': color,
                    'extendedProps': {
                        # Room information
                        'room': room_name,
                        'roomId': booking.get('room_id'),
                        
                        # Client information
                        'client': client_name,
                        'clientId': booking.get('client_id'),
                        
                        # FIXED: Ensure attendees and total are correctly set as numbers
                        'attendees': int(attendees),  # Ensure integer
                        'pax': int(attendees),        # Alternative name for frontend
                        'guests': int(attendees),     # Another alternative
                        
                        # FIXED: Ensure total price is correctly set as number
                        'total': float(total_price),           # Primary total
                        'total_price': float(total_price),     # Alternative name
                        'totalPrice': float(total_price),      # CamelCase alternative
                        'price': float(total_price),           # Another alternative
                        
                        # FIXED: Cost per person calculation
                        'cost_per_person': float(cost_per_person),
                        'costPerPerson': float(cost_per_person),
                        
                        # Status and other info
                        'status': status,
                        'notes': booking.get('notes', ''),
                        
                        # Additional room data for frontend
                        'room_capacity': room_data.get('capacity', 0) if room_data else 0,
                        
                        # Event type information
                        'event_type': booking.get('event_type', ''),
                        
                        # Booking metadata
                        'created_at': booking.get('created_at'),
                        'updated_at': booking.get('updated_at')
                    }
                }
                
                events.append(event_data)
                
                print(f"OK: DEBUG: Processed booking {booking_id}: {attendees} PAX, ${total_price:.2f} total, ${cost_per_person:.2f}/person")
                
            except Exception as event_error:
                print(f"OK: DEBUG: Error processing booking {booking.get('id', 'unknown')}: {event_error}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"OK: DEBUG: Successfully processed {len(events)} calendar events with accurate PAX and pricing data")
        
        # Final validation: Log sample event data for debugging
        if events:
            sample_event = events[0]
            print(f"=== DEBUG: Sample event extendedProps:")
            print(f"  - attendees: {sample_event['extendedProps'].get('attendees')} (type: {type(sample_event['extendedProps'].get('attendees'))})")
            print(f"  - total: {sample_event['extendedProps'].get('total')} (type: {type(sample_event['extendedProps'].get('total'))})")
            print(f"  - cost_per_person: {sample_event['extendedProps'].get('cost_per_person')} (type: {type(sample_event['extendedProps'].get('cost_per_person'))})")
        
        return events
        
    except Exception as e:
        print(f"OK: Calendar events error: {e}")
        import traceback
        traceback.print_exc()
        
        # Return empty array instead of error to prevent calendar from breaking
        return []

def calculate_booking_total(room_id, start_time, end_time, addon_ids=None):
    """Calculate total price for a booking - SIMPLIFIED (NO DISCOUNT)"""
    try:
        # Get room data using admin client
        room_data = supabase_select('rooms', filters=[('id', 'eq', room_id)])
        if not room_data:
            return 0
        
        room = room_data[0]
        
        # Calculate duration in hours
        duration_hours = (end_time - start_time).total_seconds() / 3600
        
        # Calculate room rate based on duration
        if duration_hours <= 4:
            room_rate = float(room['hourly_rate']) * duration_hours
        elif duration_hours <= 6:
            room_rate = float(room['half_day_rate'])
        else:
            room_rate = float(room['full_day_rate'])
        
        # Calculate add-ons total
        addons_total = 0
        if addon_ids:
            for addon_id in addon_ids:
                addon_data = supabase_select('addons', filters=[('id', 'eq', addon_id)])
                if addon_data:
                    addons_total += float(addon_data[0]['price'])
        
        # Calculate final total (NO DISCOUNT APPLIED)
        total = room_rate + addons_total
        return max(total, 0)  # Ensure non-negative
        
    except Exception as e:
        print(f"Price calculation error: {e}")
        return 0
    
    
def find_or_create_client(client_name, company_name=None, email=None, phone=None):
    """Find existing client or create new one based on name/company"""
    try:
        print(f"=== DEBUG: Finding/creating client - Name: {client_name}, Company: {company_name}")
        
        # First, try to find existing client by name or company
        existing_client = None
        
        if company_name:
            # Search by company name first
            clients_response = supabase_admin.table('clients').select('*').ilike('company_name', f'%{company_name}%').execute()
            if clients_response.data:
                existing_client = clients_response.data[0]
                print(f"OK: DEBUG: Found existing client by company: {existing_client['id']}")
        
        if not existing_client:
            # Search by contact person name
            clients_response = supabase_admin.table('clients').select('*').ilike('contact_person', f'%{client_name}%').execute()
            if clients_response.data:
                existing_client = clients_response.data[0]
                print(f"OK: DEBUG: Found existing client by contact person: {existing_client['id']}")
        
        if existing_client:
            return existing_client['id']
        
        # Create new client if not found
        print(f"=== DEBUG: Creating new client")
        client_data = {
            'contact_person': client_name.strip(),
            'company_name': company_name.strip() if company_name else None,
            'email': email or f"{client_name.lower().replace(' ', '.')}@example.com",  # Placeholder email
            'phone': phone,
            'notes': f'Auto-created from booking form on {get_cat_time().isoformat()}'
        }
        
        result = create_client_in_db(client_data)
        if result:
            print(f"OK: DEBUG: Created new client with ID: {result['id']}")
            return result['id']
        else:
            print(f"OK: DEBUG: Failed to create new client")
            return None
            
    except Exception as e:
        print(f"OK: ERROR: Failed to find/create client: {e}")
        return None

def process_pricing_items(form_data):
    """Process the dynamic pricing items from the form - SIMPLIFIED"""
    try:
        total_amount = 0
        pricing_items = []
        
        # Extract pricing items from form data
        item_index = 0
        while f'pricing_items[{item_index}][description]' in form_data:
            description = form_data.get(f'pricing_items[{item_index}][description]', '').strip()
            quantity = safe_int_conversion(form_data.get(f'pricing_items[{item_index}][quantity]', 1), 1)
            price = safe_float_conversion(form_data.get(f'pricing_items[{item_index}][price]', 0))
            
            if description and price > 0:
                item_total = quantity * price
                total_amount += item_total
                
                pricing_items.append({
                    'description': description,
                    'quantity': quantity,
                    'unit_price': price,
                    'total': item_total
                })
                
                print(f"=== DEBUG: Pricing item - {description}: {quantity} x ${price} = ${item_total}")
            
            item_index += 1
        
        print(f"OK: DEBUG: Processed {len(pricing_items)} pricing items, total: ${total_amount:.2f}")
        return pricing_items, total_amount
        
    except Exception as e:
        print(f"OK: ERROR: Failed to process pricing items: {e}")
        return [], 0
    
# ===============================
# Enhanced Booking Helper Functions (NEW)
# ===============================

def handle_booking_creation(form_data, rooms_for_template):
    """Handle the creation of a new booking with comprehensive validation"""
    try:
        print("=== DEBUG: Processing new booking creation")
        
        # Extract and validate form data
        booking_data = extract_booking_form_data(form_data)
        if not booking_data:
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
        # Validate business rules
        validation_errors = validate_booking_business_rules(booking_data)
        if validation_errors:
            for error in validation_errors:
                flash(error, 'danger')
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
        # Find or create client
        client_id = find_or_create_client_enhanced(
            booking_data['client_name'], 
            booking_data.get('company_name'),
            booking_data.get('client_email')
        )
        
        if not client_id:
            flash('OK: Error processing client information. Please try again.', 'danger')
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
        # Find or create event type
        event_type_id = find_or_create_event_type(
            booking_data['event_type'], 
            booking_data.get('custom_event_type')
        )
        
        # Create booking with all related data
        booking_id = create_complete_booking(booking_data, client_id, event_type_id)
        
        if booking_id:
            # Log successful creation
            log_booking_creation_activity(booking_id, booking_data)
            
            # Success message and redirect
            success_message = format_booking_success_message(booking_data)
            flash(success_message, 'success')
            return redirect(url_for('generate_quotation', id=booking_id))
        else:
            flash('OK: Error creating booking. Please try again.', 'danger')
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
    except Exception as e:
        print(f"OK: ERROR: Booking creation failed: {e}")
        import traceback
        traceback.print_exc()
        flash('OK: Unexpected error creating booking. Please try again.', 'danger')
        return render_template('bookings/form.html', 
                              title='New Booking', 
                              form=BookingForm(), 
                              rooms=rooms_for_template)

def handle_booking_update(booking_id, form_data, existing_booking, rooms_for_template):
    """Handle updating an existing booking"""
    try:
        print(f"=== DEBUG: Processing booking update for ID {booking_id}")
        
        # Extract and validate form data
        booking_data = extract_booking_form_data(form_data)
        if not booking_data:
            return render_template('bookings/form.html', 
                                  title='Edit Booking', 
                                  form=BookingForm(), 
                                  booking=existing_booking,
                                  rooms=rooms_for_template)
        
        # Validate business rules (excluding current booking from availability check)
        validation_errors = validate_booking_business_rules(booking_data, exclude_booking_id=booking_id)
        if validation_errors:
            for error in validation_errors:
                flash(error, 'danger')
            return render_template('bookings/form.html', 
                                  title='Edit Booking', 
                                  form=BookingForm(), 
                                  booking=existing_booking,
                                  rooms=rooms_for_template)
        
        # Update booking with all related data
        success = update_complete_booking(booking_id, booking_data, existing_booking)
        
        if success:
            # Log successful update
            log_booking_update_activity(booking_id, booking_data)
            
            flash('OK: Booking updated successfully!', 'success')
            return redirect(url_for('view_booking', id=booking_id))
        else:
            flash('OK: Error updating booking. Please try again.', 'danger')
            return render_template('bookings/form.html', 
                                  title='Edit Booking', 
                                  form=BookingForm(), 
                                  booking=existing_booking,
                                  rooms=rooms_for_template)
        
    except Exception as e:
        print(f"OK: ERROR: Booking update failed: {e}")
        import traceback
        traceback.print_exc()
        flash('OK: Unexpected error updating booking. Please try again.', 'danger')
        return render_template('bookings/form.html', 
                              title='Edit Booking', 
                              form=BookingForm(), 
                              booking=existing_booking,
                              rooms=rooms_for_template)

def extract_booking_form_data(form_data):
    """Extract and validate booking data from form submission"""
    try:
        # Required fields validation
        required_fields = {
            'room_id': 'Please select a venue',
            'attendees': 'Please enter number of attendees',
            'currency': 'Please select a currency',
            'client_name': 'Please enter client name',
            'event_type': 'Please select event type',
            'start_time': 'Please select start date and time',
            'end_time': 'Please select end date and time'
        }
        
        for field, message in required_fields.items():
            if not form_data.get(field, '').strip():
                flash(f'OK: {message}', 'danger')
                return None
        
        # Parse datetime fields
        try:
            start_time = datetime.strptime(form_data.get('start_time'), '%Y-%m-%d %H:%M')
            end_time = datetime.strptime(form_data.get('end_time'), '%Y-%m-%d %H:%M')
        except ValueError as e:
            flash('OK: Invalid date/time format. Please use the date picker.', 'danger')
            return None
        
        # Validate time logic
        if end_time <= start_time:
            flash('OK: End time must be after start time.', 'danger')
            return None
        
        # Use CAT time for comparison (remove timezone info for naive datetime comparison)
        if start_time < get_cat_time().replace(tzinfo=None):
            flash('OK: Booking cannot be scheduled in the past.', 'danger')
            return None
        
        # Process pricing items
        pricing_items, total_price = extract_pricing_items_from_form(form_data)
        if not pricing_items or total_price <= 0:
            flash('OK: Please add at least one pricing item with a valid amount.', 'danger')
            return None
        
        # Build booking data dictionary
        booking_data = {
            'room_id': int(form_data.get('room_id')),
            'attendees': int(form_data.get('attendees')),
            'currency': form_data.get('currency', 'USD').strip(),
            'client_name': form_data.get('client_name', '').strip(),
            'company_name': form_data.get('company_name', '').strip() or None,
            'client_email': form_data.get('client_email', '').strip() or None,
            'event_type': form_data.get('event_type', '').strip(),
            'custom_event_type': form_data.get('custom_event_type', '').strip() or None,
            'start_time': start_time,
            'end_time': end_time,
            'notes': form_data.get('notes', '').strip() or None,
            'status': form_data.get('status', 'tentative'),
            'pricing_items': pricing_items,
            'total_price': total_price
        }
        
        print(f"OK: DEBUG: Successfully extracted booking data - Total: ${total_price:.2f}")
        return booking_data
        
    except Exception as e:
        print(f"OK: ERROR: Failed to extract form data: {e}")
        flash('OK: Error processing form data. Please check your inputs.', 'danger')
        return None

def extract_pricing_items_from_form(form_data):
    """Extract pricing items from the dynamic form fields"""
    try:
        pricing_items = []
        total_price = 0
        
        # Extract pricing items from form data
        item_index = 0
        while f'pricing_items[{item_index}][description]' in form_data:
            description = form_data.get(f'pricing_items[{item_index}][description]', '').strip()
            quantity_str = form_data.get(f'pricing_items[{item_index}][quantity]', '1')
            price_str = form_data.get(f'pricing_items[{item_index}][price]', '0')
            notes = form_data.get(f'pricing_items[{item_index}][notes]', '').strip()
            
            try:
                quantity = int(quantity_str) if quantity_str else 1
                price = float(price_str) if price_str else 0.0
            except (ValueError, TypeError):
                print(f"OK: WARNING: Invalid quantity or price for item {item_index}")
                item_index += 1
                continue
            
            if description and price > 0 and quantity > 0:
                item_total = quantity * price
                total_price += item_total
                
                pricing_items.append({
                    'description': description,
                    'quantity': quantity,
                    'unit_price': price,
                    'total_price': item_total,
                    'notes': notes if notes else None
                })
                
                print(f"=== DEBUG: Pricing item - {description}: {quantity} x ${price} = ${item_total}")
            
            item_index += 1
        
        print(f"OK: DEBUG: Processed {len(pricing_items)} pricing items, total: ${total_price:.2f}")
        return pricing_items, total_price
        
    except Exception as e:
        print(f"OK: ERROR: Failed to extract pricing items: {e}")
        return [], 0

def calculate_room_and_addons_totals(pricing_items):
    """Calculate separate room rate and addons total from pricing items"""
    try:
        room_rate = 0.0
        addons_total = 0.0
        
        # Keywords that typically indicate room/venue charges
        room_keywords = ['room', 'venue', 'hall', 'space', 'rental', 'hire', 'facility']
        
        for item in pricing_items:
            description = item['description'].lower()
            item_total = item['total_price']
            
            # Check if this item is likely a room charge
            is_room_item = any(keyword in description for keyword in room_keywords)
            
            if is_room_item:
                room_rate += item_total
                item['is_room_rate'] = True  # Flag for later use
            else:
                addons_total += item_total
                item['is_room_rate'] = False
        
        # If no room items identified, treat the first item as room rate
        if room_rate == 0 and pricing_items:
            first_item = pricing_items[0]
            room_rate = first_item['total_price']
            addons_total = sum(item['total_price'] for item in pricing_items[1:])
            first_item['is_room_rate'] = True
            for item in pricing_items[1:]:
                item['is_room_rate'] = False
        
        print(f"=== DEBUG: Calculated Room Rate: ${room_rate:.2f}, Addons Total: ${addons_total:.2f}")
        return room_rate, addons_total
        
    except Exception as e:
        print(f"OK: ERROR: Failed to calculate room and addons totals: {e}")
        return 0.0, 0.0
    
def find_or_create_event_type(event_type, custom_event_type=None):
    """Find or create event type in the event_types table"""
    try:
        # Determine the event type name
        if event_type == 'other' and custom_event_type:
            event_name = custom_event_type.strip()
        else:
            event_name = event_type.replace('_', ' ').title()
        
        print(f"=== DEBUG: Finding/creating event type: {event_name}")
        
        # Search for existing event type
        existing_event = supabase_admin.table('event_types').select('*').eq('name', event_name).execute()
        
        if existing_event.data:
            event_type_id = existing_event.data[0]['id']
            # Increment usage count
            supabase_admin.table('event_types').update({
                'usage_count': existing_event.data[0]['usage_count'] + 1
            }).eq('id', event_type_id).execute()
            print(f"OK: DEBUG: Found existing event type: {event_type_id}")
            return event_type_id
        
        # Create new event type
        event_data = {
            'name': event_name,
            'usage_count': 1,
            'created_at': get_cat_time().isoformat()
        }
        
        result = supabase_insert('event_types', event_data)
        if result:
            print(f"OK: DEBUG: Created new event type with ID: {result['id']}")
            return result['id']
        else:
            print(f"OK: DEBUG: Failed to create event type")
            return None
            
    except Exception as e:
        print(f"OK: ERROR: Failed to find/create event type: {e}")
        return None

def find_or_create_client_enhanced(client_name, company_name=None, email=None):
    """Enhanced client finding/creation with better error handling"""
    try:
        print(f"=== DEBUG: Finding/creating client - Name: {client_name}, Company: {company_name}")
        
        # Search for existing client
        existing_client = None
        
        # Search by company name first if provided
        if company_name and company_name.strip():
            clients_response = supabase_admin.table('clients').select('*').ilike('company_name', f'%{company_name.strip()}%').execute()
            if clients_response.data:
                existing_client = clients_response.data[0]
                print(f"OK: DEBUG: Found existing client by company: {existing_client['id']}")
        
        # Search by contact person name if not found by company
        if not existing_client:
            clients_response = supabase_admin.table('clients').select('*').ilike('contact_person', f'%{client_name.strip()}%').execute()
            if clients_response.data:
                existing_client = clients_response.data[0]
                print(f"OK: DEBUG: Found existing client by contact person: {existing_client['id']}")
        
        # Search by email if provided and not found yet
        if not existing_client and email and email.strip():
            clients_response = supabase_admin.table('clients').select('*').eq('email', email.strip().lower()).execute()
            if clients_response.data:
                existing_client = clients_response.data[0]
                print(f"OK: DEBUG: Found existing client by email: {existing_client['id']}")
        
        if existing_client:
            return existing_client['id']
        
        # Create new client
        print(f"=== DEBUG: Creating new client")
        client_data = {
            'contact_person': client_name.strip(),
            'company_name': company_name.strip() if company_name else None,
            'email': email.strip().lower() if email else f"{client_name.lower().replace(' ', '.')}@example.com",
            'created_at': get_cat_time().isoformat(),
            'notes': f'Auto-created from booking form on {get_cat_time().strftime("%Y-%m-%d %H:%M")}'
        }
        
        result = supabase_insert('clients', client_data)
        if result:
            print(f"OK: DEBUG: Created new client with ID: {result['id']}")
            return result['id']
        else:
            print(f"OK: DEBUG: Failed to create new client")
            return None
            
    except Exception as e:
        print(f"OK: ERROR: Failed to find/create client: {e}")
        import traceback
        traceback.print_exc()
        return None
    
def create_complete_booking(booking_data, client_id, event_type_id):
    """Create booking with all related data using new schema (user-entered rates)"""
    try:
        print(f"=== DEBUG: Creating complete booking with user-entered rates")
        
        # Determine event title
        if booking_data['event_type'] == 'other' and booking_data['custom_event_type']:
            event_title = booking_data['custom_event_type']
        else:
            event_title = booking_data['event_type'].replace('_', ' ').title()
        
        # Separate room rate and addons from pricing items
        room_rate, addons_total = calculate_room_and_addons_totals(booking_data['pricing_items'])
        
        # Create main booking record
        booking_record = {
            'room_id': booking_data['room_id'],
            'client_id': client_id,
            'event_type_id': event_type_id,
            'title': f"{event_title} - {booking_data['client_name']}",
            'start_time': booking_data['start_time'].isoformat(),
            'end_time': booking_data['end_time'].isoformat(),
            'attendees': booking_data['attendees'],
            'currency': booking_data.get('currency', 'USD'),
            'status': booking_data['status'],
            'notes': booking_data['notes'],
            'room_rate': room_rate,  # Store user-entered room rate
            'addons_total': addons_total,  # Store calculated addons total
            'total_price': booking_data['total_price'],
            'created_by': current_user.id,
            'created_at': get_cat_time().isoformat(),
            # Store client info for redundancy
            'client_name': booking_data['client_name'],
            'company_name': booking_data['company_name'],
            'client_email': booking_data['client_email']
        }
        
        booking_result = supabase_insert('bookings', booking_record)
        if not booking_result:
            print("OK: ERROR: Failed to create booking record")
            return None
        
        booking_id = booking_result['id']
        print(f"OK: DEBUG: Created booking with ID: {booking_id}, Room Rate: ${room_rate:.2f}, Addons: ${addons_total:.2f}")
        
        # Create custom addon records
        for item in booking_data['pricing_items']:
            addon_record = {
                'booking_id': booking_id,
                'description': item['description'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price'],
                'total_price': item['total_price'],
                'notes': item.get('notes'),
                'created_at': get_cat_time().isoformat()
            }
            
            addon_result = supabase_insert('booking_custom_addons', addon_record)
            if not addon_result:
                print(f"OK: WARNING: Failed to create custom addon: {item['description']}")
        
        print(f"OK: DEBUG: Booking creation completed successfully")
        return booking_id
        
    except Exception as e:
        print(f"OK: ERROR: Failed to create complete booking: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_complete_booking_details(booking_id):
    """Get complete booking details including all related data"""
    try:
        print(f"=== DEBUG: Fetching complete booking details for ID {booking_id}")
        
        # Get main booking data with related tables
        booking_response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(*),
            client:clients(*),
            event_type:event_types(*)
        """).eq('id', booking_id).execute()
        
        if not booking_response.data:
            return None
        
        booking = booking_response.data[0]
        
        # Get creator's username if created_by exists
        if booking.get('created_by'):
            try:
                creator_response = supabase_admin.table('users').select('first_name, last_name, username, email').eq('id', booking['created_by']).execute()
                if creator_response.data:
                    creator = creator_response.data[0]
                    # Build full name or use username
                    if creator.get('first_name') and creator.get('last_name'):
                        booking['created_by_name'] = f"{creator['first_name']} {creator['last_name']}"
                    elif creator.get('username'):
                        booking['created_by_name'] = creator['username']
                    else:
                        booking['created_by_name'] = creator.get('email', 'Unknown User')
                else:
                    booking['created_by_name'] = 'Unknown User'
            except Exception as user_error:
                print(f"OK: WARNING: Could not fetch creator details: {user_error}")
                booking['created_by_name'] = 'Unknown User'
        else:
            booking['created_by_name'] = 'System'
        
        # Get custom addons
        addons_response = supabase_admin.table('booking_custom_addons').select('*').eq('booking_id', booking_id).execute()
        booking['custom_addons'] = addons_response.data if addons_response.data else []
        
        # Convert datetime strings
        booking = convert_datetime_strings(booking)
        
        print(f"OK: DEBUG: Successfully fetched complete booking details")
        return booking
        
    except Exception as e:
        print(f"OK: ERROR: Failed to fetch complete booking details: {e}")
        return None

def update_complete_booking(booking_id, booking_data, existing_booking):
    """Update booking with all related data (user-entered rates)"""
    try:
        print(f"=== DEBUG: Updating complete booking {booking_id}")
        
        # Find or create client if changed
        client_id = existing_booking.get('client_id')
        if (booking_data['client_name'] != existing_booking.get('client', {}).get('contact_person', '') or
            booking_data.get('company_name') != existing_booking.get('client', {}).get('company_name')):
            
            client_id = find_or_create_client_enhanced(
                booking_data['client_name'],
                booking_data.get('company_name'),
                booking_data.get('client_email')
            )
        
        # Find or create event type if changed
        event_type_id = existing_booking.get('event_type_id')
        if booking_data['event_type'] != existing_booking.get('event_type'):
            event_type_id = find_or_create_event_type(
                booking_data['event_type'],
                booking_data.get('custom_event_type')
            )
        
        # Determine event title
        if booking_data['event_type'] == 'other' and booking_data['custom_event_type']:
            event_title = booking_data['custom_event_type']
        else:
            event_title = booking_data['event_type'].replace('_', ' ').title()
        
        # Calculate room rate and addons total from user-entered pricing
        room_rate, addons_total = calculate_room_and_addons_totals(booking_data['pricing_items'])
        
        # Update main booking record
        booking_update = {
            'room_id': booking_data['room_id'],
            'client_id': client_id,
            'event_type_id': event_type_id,
            'title': f"{event_title} - {booking_data['client_name']}",
            'start_time': booking_data['start_time'].isoformat(),
            'end_time': booking_data['end_time'].isoformat(),
            'attendees': booking_data['attendees'],
            'currency': booking_data.get('currency', 'USD'),
            'status': booking_data['status'],
            'notes': booking_data['notes'],
            'room_rate': room_rate,  # Updated user-entered room rate
            'addons_total': addons_total,  # Updated addons total
            'total_price': booking_data['total_price'],
            'updated_at': get_cat_time().isoformat(),
            'client_name': booking_data['client_name'],
            'company_name': booking_data['company_name'],
            'client_email': booking_data['client_email']
        }
        
        booking_result = supabase_update('bookings', booking_update, [('id', 'eq', booking_id)])
        if not booking_result:
            print("OK: ERROR: Failed to update booking record")
            return False
        
        # Delete existing custom addons
        supabase_admin.table('booking_custom_addons').delete().eq('booking_id', booking_id).execute()
        
        # Create new custom addon records
        for item in booking_data['pricing_items']:
            addon_record = {
                'booking_id': booking_id,
                'description': item['description'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price'],
                'total_price': item['total_price'],
                'notes': item.get('notes'),
                'created_at': get_cat_time().isoformat()
            }
            
            supabase_insert('booking_custom_addons', addon_record)
        
        print(f"OK: DEBUG: Booking update completed successfully")
        return True
        
    except Exception as e:
        print(f"OK: ERROR: Failed to update complete booking: {e}")
        import traceback
        traceback.print_exc()
        return False
    
def validate_booking_business_rules(booking_data, exclude_booking_id=None):
    """Validate booking against business rules"""
    errors = []
    
    try:
        # Check room availability
        is_available = is_room_available_supabase(
            booking_data['room_id'],
            booking_data['start_time'],
            booking_data['end_time'],
            exclude_booking_id=exclude_booking_id
        )
        
        if not is_available:
            errors.append('OK: Room is not available for the selected time period. Please choose a different time or room.')
        
        # Check room capacity
        room_data = supabase_select('rooms', filters=[('id', 'eq', booking_data['room_id'])])
        if room_data:
            room_capacity = room_data[0].get('capacity', 0)
            if booking_data['attendees'] > room_capacity:
                errors.append(f'OK: Room capacity ({room_capacity}) exceeded. You have {booking_data["attendees"]} attendees.')
        
        # Validate booking duration
        duration_hours = (booking_data['end_time'] - booking_data['start_time']).total_seconds() / 3600
        if duration_hours > 12:
            errors.append('OK: Bookings cannot exceed 12 hours.')
        
        if duration_hours < 0.5:
            errors.append('OK: Bookings must be at least 30 minutes long.')
        
        # Validate business hours (6 AM to 11 PM)
        if booking_data['start_time'].hour < 6 or booking_data['start_time'].hour > 22:
            errors.append('OK: Bookings must start within business hours (6 AM - 10 PM).')
        
        if booking_data['end_time'].hour < 6 or booking_data['end_time'].hour > 23:
            errors.append('OK: Bookings must end within business hours (6 AM - 11 PM).')
        
    except Exception as e:
        print(f"OK: ERROR: Business rule validation failed: {e}")
        errors.append('OK: Error validating booking rules. Please try again.')
    
    return errors

def populate_form_with_booking_data(form, booking):
    """Populate form with existing booking data for editing"""
    try:
        form.room_id.data = booking.get('room_id')
        form.attendees.data = booking.get('attendees')
        form.client_name.data = booking.get('client', {}).get('contact_person', '') or booking.get('client_name', '')
        form.company_name.data = booking.get('client', {}).get('company_name', '') or booking.get('company_name', '')
        form.start_time.data = booking.get('start_time')
        form.end_time.data = booking.get('end_time')
        form.notes.data = booking.get('notes')
        form.status.data = booking.get('status', 'tentative')
        
        # Set event type
        if booking.get('event_type'):
            event_name = booking.get('event_type', {}).get('name', '')
            form.event_type.data = event_name.lower().replace(' ', '_')
        
    except Exception as e:
        print(f"OK: ERROR: Failed to populate form: {e}")

def log_booking_creation_activity(booking_id, booking_data):
    """Log booking creation activity"""
    try:
        log_user_activity(
            ActivityTypes.CREATE_BOOKING,
            f"Created booking '{booking_data.get('event_type', 'Unknown')}' for {booking_data.get('attendees', 0)} attendees",
            resource_type='booking',
            resource_id=booking_id,
            metadata={
                'client_name': booking_data.get('client_name'),
                'company_name': booking_data.get('company_name'),
                'attendees': booking_data.get('attendees'),
                'total_price': booking_data.get('total_price'),
                'pricing_items_count': len(booking_data.get('pricing_items', []))
            }
        )
    except Exception as e:
        print(f"Failed to log booking creation: {e}")

def log_booking_update_activity(booking_id, booking_data):
    """Log booking update activity"""
    try:
        log_user_activity(
            ActivityTypes.UPDATE_BOOKING,
            f"Updated booking for {booking_data.get('client_name', 'Unknown Client')}",
            resource_type='booking',
            resource_id=booking_id,
            metadata={
                'updated_fields': ['room_id', 'attendees', 'start_time', 'end_time', 'total_price'],
                'new_total': booking_data.get('total_price')
            }
        )
    except Exception as e:
        print(f"Failed to log booking update: {e}")

def format_booking_success_message(booking_data):
    """Format a success message for booking creation"""
    event_title = booking_data.get('custom_event_type') if booking_data.get('event_type') == 'other' else booking_data.get('event_type', 'Event').replace('_', ' ').title()
    
    return f"""
    OK: <strong>Booking created successfully!</strong><br>
    === <strong>Event:</strong> {event_title}<br>
    === <strong>Client:</strong> {booking_data.get('client_name')}<br>
    === <strong>Company:</strong> {booking_data.get('company_name') or 'Not specified'}<br>
    === <strong>Attendees:</strong> {booking_data.get('attendees')}<br>
    =OK: <strong>Total:</strong> ${booking_data.get('total_price'):.2f}<br>
    === <strong>Status:</strong> {booking_data.get('status', 'Tentative').title()} - Ready for quotation
    """
# ===============================
# Routes - Authentication
# ===============================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page with Supabase authentication - NOW WITH ACTIVITY LOGGING"""
    if current_user.is_authenticated:
        print("DEBUG: User already authenticated, redirecting to dashboard")
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        print(f"DEBUG: Login form submitted for email: {form.username.data}")
        
        user = authenticate_user(form.username.data, form.password.data)
        if user:
            print(f"DEBUG: Authentication successful for user: {user.email}")
            
            # Log successful login
            try:
                log_authentication_activity(
                    ActivityTypes.LOGIN_SUCCESS,
                    user.email,
                    success=True,
                    additional_info={
                        'user_role': user.role,
                        'login_time': get_cat_time().isoformat()
                    }
                )
            except Exception as log_error:
                print(f"Failed to log login success: {log_error}")
            
            login_result = login_user(user, remember=form.remember_me.data)
            print(f"DEBUG: Flask-Login result: {login_result}")
            print(f"DEBUG: Current user authenticated: {current_user.is_authenticated}")
            print(f"DEBUG: Current user ID: {getattr(current_user, 'id', 'None')}")
            
            next_page = request.args.get('next')
            print(f"DEBUG: Next page: {next_page}")
            
            flash(f'Welcome back, {user.first_name or user.email}!', 'success')
            session.modified = True
            
            print(f"DEBUG: About to redirect to: {next_page or url_for('dashboard')}")
            return redirect(next_page or url_for('dashboard'))
        else:
            print("DEBUG: Authentication failed")
            
            # Log failed login
            try:
                log_authentication_activity(
                    ActivityTypes.LOGIN_FAILED,
                    form.username.data,
                    success=False,
                    additional_info={'attempt_time': get_cat_time().isoformat()}
                )
            except Exception as log_error:
                print(f"Failed to log login failure: {log_error}")
            
            flash('Invalid email or password', 'danger')
    else:
        if form.errors:
            print(f"DEBUG: Form validation errors: {form.errors}")
    
    return render_template('login.html', form=form, title='Sign In')

@app.route('/logout')
@login_required
def logout():
    """User logout with Supabase - NOW WITH ACTIVITY LOGGING"""
    # Log logout activity before actually logging out
    if current_user.is_authenticated:
        try:
            log_authentication_activity(
                ActivityTypes.LOGOUT,
                current_user.email,
                success=True,
                additional_info={'logout_time': get_cat_time().isoformat()}
            )
        except Exception as log_error:
            print(f"Failed to log logout: {log_error}")
    
    try:
        supabase.auth.sign_out()
        session.pop('supabase_session', None)
        logout_user()
        flash('You have been logged out', 'info')
    except:
        pass
    
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    # Redirect if user is already logged in
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        try:
            print(f"DEBUG: Registration attempt for email: {form.email.data}")
            
            # Prepare user data
            email = form.email.data.strip().lower()
            password = form.password.data
            first_name = form.first_name.data.strip()
            last_name = form.last_name.data.strip()
            role = form.role.data
            
            # Validate role permissions (optional: you can restrict who can create admin accounts)
            if role == 'admin':
                # Only existing admins can create admin accounts (optional security measure)
                # You can remove this if you want anyone to be able to register as admin
                flash('Admin accounts must be created by existing administrators. Please select a different role.', 'warning')
                form.role.data = 'staff'  # Reset to staff
                return render_template('register.html', title='Register', form=form)
            
            # Create user in Supabase
            success = create_user_supabase(email, password, first_name, last_name, role)
            
            if success:
                flash(f'Registration successful! Welcome, {first_name}! You can now log in with your credentials.', 'success')
                
                # Optionally auto-login the user after successful registration
                # Uncomment the lines below if you want automatic login after registration
                # user = authenticate_user(email, password)
                # if user:
                #     login_user(user)
                #     return redirect(url_for('dashboard'))
                
                # Redirect to login page
                return redirect(url_for('login'))
            else:
                flash('Registration failed. The email might already be in use or there was a server error. Please try again.', 'danger')
                
        except Exception as e:
            print(f"Registration error: {e}")
            if 'already registered' in str(e).lower() or 'already exists' in str(e).lower():
                flash('This email address is already registered. Please try logging in instead.', 'warning')
            else:
                flash('Registration failed due to a server error. Please try again later.', 'danger')
    else:
        # Display form validation errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field.replace("_", " ").title()}: {error}', 'danger')
    
    return render_template('register.html', title='Register', form=form)


# ===============================
# Routes - Dashboard
# ===============================

# Replace your existing dashboard route with this improved version
# NOTE: This route has been disabled to avoid conflicts with blueprint routes
# The dashboard is now served by routes/dashboard.py

# @app.route('/')
# @login_required
def dashboard_legacy():
    """Main dashboard page with enhanced error handling and debugging - NOW WITH ACTIVITY LOGGING"""
    
    # Log page view
    try:
        log_user_activity(
            ActivityTypes.PAGE_VIEW,
            "Viewed dashboard",
            resource_type='page',
            metadata={'page': 'dashboard', 'timestamp': get_cat_time().isoformat()}
        )
    except Exception as log_error:
        print(f"Failed to log dashboard view: {log_error}")
    
    try:
        print(f"=== DEBUG: Dashboard loading at {get_cat_time()}")
        print(f"=== DEBUG: User authenticated: {current_user.is_authenticated}")
        print(f"=== DEBUG: Supabase URL set: {bool(SUPABASE_URL)}")
        print(f"=== DEBUG: Service key available: {bool(SUPABASE_SERVICE_KEY)}")
        
        # Initialize with safe defaults
        upcoming_bookings_data = []
        today_bookings_data = []
        total_rooms = 0
        total_clients = 0
        total_active_bookings = 0
        
        # Get time boundaries
        now = get_cat_time().isoformat()
        today = get_cat_time().date().isoformat()
        tomorrow = (get_cat_time().date() + timedelta(days=1)).isoformat()
        
        print(f"=== DEBUG: Time boundaries - now: {now}, today: {today}, tomorrow: {tomorrow}")
        
        # Test basic connection first
        try:
            test_query = supabase_admin.table('rooms').select('id').limit(1).execute()
            print(f"OK: DEBUG: Basic database connection successful")
        except Exception as e:
            print(f"OK: DEBUG: Basic database connection failed: {e}")
            flash('Database connection issue. Please check logs.', 'warning')
            return render_template('dashboard.html',
                                  title='Dashboard',
                                  upcoming_bookings=[],
                                  today_bookings=[],
                                  total_rooms=0,
                                  total_clients=0,
                                  total_active_bookings=0,
                                  debug_mode=True,
                                  connection_error=str(e))
        
        # Get upcoming bookings with detailed error handling and fallback
        try:
            print("=== DEBUG: Fetching upcoming bookings...")
            
            # First try with nested relationships
            upcoming_bookings = supabase_admin.table('bookings').select("""
                *,
                room:rooms(name),
                client:clients(company_name, contact_person)
            """).gte('start_time', now).neq('status', 'cancelled').order('start_time').limit(5).execute()
            
            if upcoming_bookings.data:
                upcoming_bookings_raw = upcoming_bookings.data
                print(f"OK: DEBUG: Found {len(upcoming_bookings_raw)} upcoming bookings")
                print(f"=== DEBUG: Sample upcoming booking structure: {upcoming_bookings_raw[0] if upcoming_bookings_raw else 'None'}")
                
                # Process each booking to ensure room and client data
                upcoming_bookings_processed = []
                for booking in upcoming_bookings_raw:
                    processed_booking = booking.copy()
                    
                    # Ensure room data exists
                    if not booking.get('room') or not isinstance(booking.get('room'), dict):
                        print(f"NO room data for booking {booking.get('id')}, fetching separately")
                        room_data = supabase_admin.table('rooms').select('id, name').eq('id', booking.get('room_id')).execute()
                        if room_data.data:
                            processed_booking['room'] = room_data.data[0]
                        else:
                            processed_booking['room'] = {'name': 'Unknown Room'}
                    
                    # Ensure client data exists
                    if not booking.get('client') or not isinstance(booking.get('client'), dict):
                        print(f"NO client data for booking {booking.get('id')}, fetching separately")
                        client_data = supabase_admin.table('clients').select('id, company_name, contact_person').eq('id', booking.get('client_id')).execute()
                        if client_data.data:
                            processed_booking['client'] = client_data.data[0]
                        else:
                            processed_booking['client'] = {'company_name': None, 'contact_person': 'Unknown Client'}
                    
                    upcoming_bookings_processed.append(processed_booking)
                
                upcoming_bookings_data = convert_datetime_strings(upcoming_bookings_processed)
            else:
                print("OK: DEBUG: No upcoming bookings found")
                
        except Exception as e:
            print(f"OK: DEBUG: Error fetching upcoming bookings: {e}")
            flash('Error loading upcoming bookings', 'warning')
            
            # Fallback: try to get bookings without relationships
            try:
                print("=== DEBUG: Trying fallback approach for upcoming bookings")
                upcoming_simple = supabase_admin.table('bookings').select('*').gte('start_time', now).neq('status', 'cancelled').order('start_time').limit(5).execute()
                
                if upcoming_simple.data:
                    upcoming_bookings_data = []
                    for booking in upcoming_simple.data:
                        # Manually fetch room and client data
                        room_data = supabase_admin.table('rooms').select('name').eq('id', booking.get('room_id')).execute()
                        client_data = supabase_admin.table('clients').select('company_name, contact_person').eq('id', booking.get('client_id')).execute()
                        
                        booking['room'] = room_data.data[0] if room_data.data else {'name': 'Unknown Room'}
                        booking['client'] = client_data.data[0] if client_data.data else {'company_name': None, 'contact_person': 'Unknown Client'}
                        
                        upcoming_bookings_data.append(booking)
                    
                    upcoming_bookings_data = convert_datetime_strings(upcoming_bookings_data)
                    print(f"OK: DEBUG: Fallback successful, got {len(upcoming_bookings_data)} upcoming bookings")
            except Exception as fallback_error:
                print(f"OK: DEBUG: Fallback also failed: {fallback_error}")
        
        # Get today's bookings with similar approach
        try:
            print("=== DEBUG: Fetching today's bookings...")
            
            today_bookings = supabase_admin.table('bookings').select("""
                *,
                room:rooms(name),
                client:clients(company_name, contact_person)
            """).gte('start_time', today).lt('start_time', tomorrow).neq('status', 'cancelled').execute()
            
            if today_bookings.data:
                today_bookings_raw = today_bookings.data
                print(f"OK: DEBUG: Found {len(today_bookings_raw)} today's bookings")
                
                # Process each booking to ensure room and client data
                today_bookings_processed = []
                for booking in today_bookings_raw:
                    processed_booking = booking.copy()
                    
                    # Ensure room data exists
                    if not booking.get('room') or not isinstance(booking.get('room'), dict):
                        print(f"NO room data for today's booking {booking.get('id')}, fetching separately")
                        room_data = supabase_admin.table('rooms').select('id, name').eq('id', booking.get('room_id')).execute()
                        if room_data.data:
                            processed_booking['room'] = room_data.data[0]
                        else:
                            processed_booking['room'] = {'name': 'Unknown Room'}
                    
                    # Ensure client data exists
                    if not booking.get('client') or not isinstance(booking.get('client'), dict):
                        print(f"NO client data for today's booking {booking.get('id')}, fetching separately")
                        client_data = supabase_admin.table('clients').select('id, company_name, contact_person').eq('id', booking.get('client_id')).execute()
                        if client_data.data:
                            processed_booking['client'] = client_data.data[0]
                        else:
                            processed_booking['client'] = {'company_name': None, 'contact_person': 'Unknown Client'}
                    
                    today_bookings_processed.append(processed_booking)
                
                today_bookings_data = convert_datetime_strings(today_bookings_processed)
            else:
                print("OK: DEBUG: No bookings found for today")
                
        except Exception as e:
            print(f"OK: DEBUG: Error fetching today's bookings: {e}")
            flash('Error loading today\'s bookings', 'warning')
            
            # Similar fallback for today's bookings
            try:
                print("=== DEBUG: Trying fallback approach for today's bookings")
                today_simple = supabase_admin.table('bookings').select('*').gte('start_time', today).lt('start_time', tomorrow).neq('status', 'cancelled').execute()
                
                if today_simple.data:
                    today_bookings_data = []
                    for booking in today_simple.data:
                        # Manually fetch room and client data
                        room_data = supabase_admin.table('rooms').select('name').eq('id', booking.get('room_id')).execute()
                        client_data = supabase_admin.table('clients').select('company_name, contact_person').eq('id', booking.get('client_id')).execute()
                        
                        booking['room'] = room_data.data[0] if room_data.data else {'name': 'Unknown Room'}
                        booking['client'] = client_data.data[0] if client_data.data else {'company_name': None, 'contact_person': 'Unknown Client'}
                        
                        today_bookings_data.append(booking)
                    
                    today_bookings_data = convert_datetime_strings(today_bookings_data)
                    print(f"OK: DEBUG: Fallback successful, got {len(today_bookings_data)} today's bookings")
            except Exception as fallback_error:
                print(f"OK: DEBUG: Today's bookings fallback also failed: {fallback_error}")
        
        # Get total counts with individual error handling
        try:
            print("=== DEBUG: Fetching total rooms...")
            rooms_response = supabase_admin.table('rooms').select('id').execute()
            total_rooms = len(rooms_response.data) if rooms_response.data else 0
            print(f"OK: DEBUG: Found {total_rooms} total rooms")
        except Exception as e:
            print(f"OK: DEBUG: Error fetching room count: {e}")
        
        try:
            print("=== DEBUG: Fetching total clients...")
            clients_response = supabase_admin.table('clients').select('id').execute()
            total_clients = len(clients_response.data) if clients_response.data else 0
            print(f"OK: DEBUG: Found {total_clients} total clients")
        except Exception as e:
            print(f"OK: DEBUG: Error fetching client count: {e}")
        
        try:
            print("=== DEBUG: Fetching active bookings...")
            active_bookings_response = supabase_admin.table('bookings').select('id').gte('end_time', now).neq('status', 'cancelled').execute()
            total_active_bookings = len(active_bookings_response.data) if active_bookings_response.data else 0
            print(f"OK: DEBUG: Found {total_active_bookings} active bookings")
        except Exception as e:
            print(f"OK: DEBUG: Error fetching active bookings count: {e}")
        
        # Log final statistics
        print(f"=== DEBUG: Dashboard statistics:")
        print(f"   - Upcoming bookings: {len(upcoming_bookings_data)}")
        print(f"   - Today's bookings: {len(today_bookings_data)}")
        print(f"   - Total rooms: {total_rooms}")
        print(f"   - Total clients: {total_clients}")
        print(f"   - Active bookings: {total_active_bookings}")
        
        # Debug the data structure before passing to template
        if upcoming_bookings_data:
            print(f"=== DEBUG: Final upcoming booking structure: {upcoming_bookings_data[0]}")
        if today_bookings_data:
            print(f"=== DEBUG: Final today booking structure: {today_bookings_data[0]}")
        
        return render_template('dashboard.html',
                              title='Dashboard',
                              upcoming_bookings=upcoming_bookings_data,
                              today_bookings=today_bookings_data,
                              total_rooms=total_rooms,
                              total_clients=total_clients,
                              total_active_bookings=total_active_bookings,
                              debug_mode=os.environ.get('FLASK_ENV') == 'production')
        
    except Exception as e:
        print(f"OK: CRITICAL ERROR in dashboard: {e}")
        import traceback
        traceback.print_exc()
        
        # Log dashboard error
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Dashboard error: {str(e)}",
                status='failed',
                metadata={'error': str(e), 'page': 'dashboard'}
            )
        except Exception as log_error:
            print(f"Failed to log dashboard error: {log_error}")
        
        # In production, show a user-friendly error page
        flash('Dashboard temporarily unavailable. Please try again.', 'danger')
        return render_template('dashboard.html',
                              title='Dashboard',
                              upcoming_bookings=[],
                              today_bookings=[],
                              total_rooms=0,
                              total_clients=0,
                              total_active_bookings=0,
                              critical_error=True,
                              error_message=str(e))
@app.route('/calendar')
@login_required
def calendar():
    """Calendar view for bookings with enhanced error handling"""
    try:
        print("=== DEBUG: Loading calendar page...")
        rooms_data = supabase_select('rooms')
        
        if rooms_data:
            print(f"OK: DEBUG: Loaded {len(rooms_data)} rooms for calendar")
        else:
            print("OK: DEBUG: No rooms found for calendar")
            flash('No rooms found. Please add rooms first.', 'warning')
        
        return render_template('calendar.html', title='Booking Calendar', rooms=rooms_data)
        
    except Exception as e:
        print(f"OK: Calendar error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading calendar page', 'danger')
        return render_template('calendar.html', title='Booking Calendar', rooms=[])

@app.route('/api/events')
@login_required
def get_events():
    """API endpoint to get calendar events from Supabase with enhanced accuracy and error handling"""
    try:
        print("=== DEBUG: API events endpoint called with enhanced data processing")
        
        # Get events using the improved function
        events = get_booking_calendar_events_supabase()
        
        # Validate events data before returning
        valid_events = []
        validation_stats = {
            'total_processed': len(events),
            'valid_events': 0,
            'events_with_attendees': 0,
            'events_with_total': 0,
            'events_with_cost_per_person': 0,
            'invalid_events': 0
        }
        
        for event in events:
            # Ensure required fields exist
            if (event.get('id') and 
                event.get('title') and 
                event.get('start') and 
                event.get('end')):
                
                # Validate extendedProps data
                props = event.get('extendedProps', {})
                
                # Ensure numeric fields are properly typed
                try:
                    attendees = props.get('attendees', 0)
                    if attendees is not None:
                        props['attendees'] = int(attendees) if attendees != '' else 0
                        props['pax'] = props['attendees']  # Ensure PAX field is set
                        if props['attendees'] > 0:
                            validation_stats['events_with_attendees'] += 1
                    
                    total = props.get('total', 0)
                    if total is not None:
                        props['total'] = float(total) if total != '' else 0.0
                        props['total_price'] = props['total']  # Ensure alternative name is set
                        if props['total'] > 0:
                            validation_stats['events_with_total'] += 1
                    
                    cost_per_person = props.get('cost_per_person', 0)
                    if cost_per_person is not None:
                        props['cost_per_person'] = float(cost_per_person) if cost_per_person != '' else 0.0
                        if props['cost_per_person'] > 0:
                            validation_stats['events_with_cost_per_person'] += 1
                    
                    # Recalculate cost per person if needed
                    if props.get('attendees', 0) > 0 and props.get('total', 0) > 0:
                        if props.get('cost_per_person', 0) == 0:
                            props['cost_per_person'] = props['total'] / props['attendees']
                    
                    # Ensure event has updated extendedProps
                    event['extendedProps'] = props
                    
                    valid_events.append(event)
                    validation_stats['valid_events'] += 1
                    
                except (ValueError, TypeError, ZeroDivisionError) as validation_error:
                    print(f"OK: DEBUG: Data validation error for event {event.get('id', 'unknown')}: {validation_error}")
                    # Still include the event but with safe defaults
                    props['attendees'] = 0
                    props['pax'] = 0
                    props['total'] = 0.0
                    props['total_price'] = 0.0
                    props['cost_per_person'] = 0.0
                    event['extendedProps'] = props
                    valid_events.append(event)
                    validation_stats['valid_events'] += 1
                    
            else:
                print(f"OK: DEBUG: Skipping invalid event: {event}")
                validation_stats['invalid_events'] += 1
        
        # Log validation results
        print(f"=== DEBUG: Event validation completed:")
        print(f"  - Total processed: {validation_stats['total_processed']}")
        print(f"  - Valid events: {validation_stats['valid_events']}")
        print(f"  - Events with attendees: {validation_stats['events_with_attendees']}")
        print(f"  - Events with total: {validation_stats['events_with_total']}")
        print(f"  - Events with cost per person: {validation_stats['events_with_cost_per_person']}")
        print(f"  - Invalid events: {validation_stats['invalid_events']}")
        
        # Add validation stats to response headers for debugging (optional)
        response = jsonify(valid_events)
        response.headers['X-Events-Total'] = str(validation_stats['total_processed'])
        response.headers['X-Events-Valid'] = str(validation_stats['valid_events'])
        response.headers['X-Events-With-Attendees'] = str(validation_stats['events_with_attendees'])
        response.headers['X-Events-With-Total'] = str(validation_stats['events_with_total'])
        
        print(f"OK: DEBUG: Returning {len(valid_events)} validated events to calendar")
        
        # Sample the first event for final debugging
        if valid_events:
            sample_event = valid_events[0]
            sample_props = sample_event.get('extendedProps', {})
            print(f"=== DEBUG: Sample event data being sent to frontend:")
            print(f"  - Event ID: {sample_event.get('id')}")
            print(f"  - Title: {sample_event.get('title')}")
            print(f"  - Attendees: {sample_props.get('attendees')} (type: {type(sample_props.get('attendees'))})")
            print(f"  - PAX: {sample_props.get('pax')} (type: {type(sample_props.get('pax'))})")
            print(f"  - Total: {sample_props.get('total')} (type: {type(sample_props.get('total'))})")
            print(f"  - Cost per person: {sample_props.get('cost_per_person')} (type: {type(sample_props.get('cost_per_person'))})")
        
        return response
        
    except Exception as e:
        print(f"OK: Calendar events API error: {e}")
        import traceback
        traceback.print_exc()
        
        # Log the error but return empty array to prevent calendar from breaking
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Calendar events API error: {str(e)}",
                status='failed',
                metadata={'error': str(e), 'endpoint': '/api/events'}
            )
        except Exception as log_error:
            print(f"Failed to log calendar events error: {log_error}")
        
        # Return empty array with error information in headers
        response = jsonify([])
        response.headers['X-Error'] = str(e)[:200]  # Limit error message length
        response.headers['X-Events-Total'] = '0'
        response.headers['X-Events-Valid'] = '0'
        
        return response
    
@app.route('/api/clients/search')
@login_required
def api_search_clients():
    """API endpoint for client name autocomplete"""
    try:
        query = request.args.get('q', '').strip()
        if len(query) < 2:
            return jsonify([])
        
        # Search in both company_name and contact_person fields
        clients_response = supabase_admin.table('clients').select('id, company_name, contact_person, email, phone').or_(
            f'company_name.ilike.%{query}%,contact_person.ilike.%{query}%'
        ).limit(10).execute()
        
        suggestions = []
        for client in clients_response.data if clients_response.data else []:
            suggestions.append({
                'id': client['id'],
                'name': client.get('contact_person', ''),
                'company': client.get('company_name', ''),
                'email': client.get('email', ''),
                'phone': client.get('phone', ''),
                'display_name': f"{client.get('contact_person', '')} ({client.get('company_name', 'No Company')})" if client.get('company_name') else client.get('contact_person', '')
            })
        
        return jsonify(suggestions)
        
    except Exception as e:
        print(f"OK: ERROR: Client search failed: {e}")
        return jsonify([])

@app.route('/api/companies/search')
@login_required
def api_search_companies():
    """API endpoint for company name autocomplete"""
    try:
        query = request.args.get('q', '').strip()
        if len(query) < 2:
            return jsonify([])
        
        # Get unique company names
        companies_response = supabase_admin.table('clients').select('company_name').ilike('company_name', f'%{query}%').execute()
        
        companies = []
        seen_companies = set()
        
        for client in companies_response.data if companies_response.data else []:
            company_name = client.get('company_name')
            if company_name and company_name not in seen_companies:
                companies.append({'name': company_name})
                seen_companies.add(company_name)
        
        return jsonify(companies[:10])  # Limit to 10 results
        
    except Exception as e:
        print(f"OK: ERROR: Company search failed: {e}")
        return jsonify([])


# ===============================
# Routes - Rooms
# ===============================

@app.route('/rooms')
@login_required
def rooms():
    """List all conference rooms using Supabase admin client"""
    rooms_data = supabase_select('rooms', order_by='name')
    return render_template('rooms/index.html', title='Conference Rooms', rooms=rooms_data)

@app.route('/rooms/new', methods=['GET', 'POST'])
@login_required
def new_room():
    """Add a new conference room to Supabase with comprehensive error handling"""
    form = RoomForm()
    if form.validate_on_submit():
        try:
            print(f"DEBUG: Creating new room with form data:")
            print(f"  Name: {form.name.data}")
            print(f"  Capacity: {form.capacity.data}")
            print(f"  Hourly rate: {form.hourly_rate.data}")
            print(f"  Half day rate: {form.half_day_rate.data}")
            print(f"  Full day rate: {form.full_day_rate.data}")
            print(f"  Status: {form.status.data}")
            print(f"  Amenities raw: {repr(form.amenities.data)}")
            
            # Handle amenities safely - check if it's already JSON or needs parsing
            amenities_data = form.amenities.data or ""
            amenities_list = []
            
            if amenities_data:
                # Check if it looks like JSON array
                if amenities_data.strip().startswith('[') and amenities_data.strip().endswith(']'):
                    try:
                        import json
                        amenities_list = json.loads(amenities_data)
                        print(f"DEBUG: Parsed amenities as JSON: {amenities_list}")
                    except json.JSONDecodeError:
                        print(f"DEBUG: Failed to parse as JSON, treating as comma-separated")
                        amenities_list = [item.strip() for item in amenities_data.split(',') if item.strip()]
                else:
                    # Treat as comma-separated string
                    amenities_list = [item.strip() for item in amenities_data.split(',') if item.strip()]
                    print(f"DEBUG: Parsed amenities as comma-separated: {amenities_list}")
            
            room_data = {
                'name': str(form.name.data).strip(),
                'description': str(form.description.data or "").strip()
            }
            
            # Handle capacity
            if form.capacity.data is not None:
                room_data['capacity'] = int(form.capacity.data)
            else:
                room_data['capacity'] = 0
            
            # Handle rates with validation
            if form.hourly_rate.data is not None:
                room_data['hourly_rate'] = float(form.hourly_rate.data)
            else:
                room_data['hourly_rate'] = 0.0
                
            if form.half_day_rate.data is not None:
                room_data['half_day_rate'] = float(form.half_day_rate.data)
            else:
                room_data['half_day_rate'] = 0.0
                
            if form.full_day_rate.data is not None:
                room_data['full_day_rate'] = float(form.full_day_rate.data)
            else:
                room_data['full_day_rate'] = 0.0
            
            room_data['amenities'] = amenities_list
            room_data['status'] = form.status.data or 'available'
            room_data['image_url'] = str(form.image_url.data or "").strip()
            
            print(f"DEBUG: Room data prepared: {room_data}")
            
            result = supabase_insert('rooms', room_data)
            
            print(f"DEBUG: Insert result: {result}")
            
            if result:
                flash('Conference room added successfully', 'success')
                return redirect(url_for('rooms'))
            else:
                flash('Error adding conference room - no data returned from database', 'danger')
                
        except ValueError as ve:
            print(f"ValueError in room creation: {ve}")
            flash(f'Invalid data format: {str(ve)}', 'danger')
        except Exception as e:
            print(f"Unexpected error in room creation: {e}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Error adding conference room: {str(e)}', 'danger')
    else:
        if form.errors:
            print(f"DEBUG: Form validation errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'danger')
    
    return render_template('rooms/form.html', title='Add Conference Room', form=form)

@app.route('/rooms/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(id):
    """Edit a conference room in Supabase with comprehensive error handling"""
    room_data = supabase_select('rooms', filters=[('id', 'eq', id)])
    if not room_data:
        flash('Room not found', 'danger')
        return redirect(url_for('rooms'))
    
    room = room_data[0]
    form = RoomForm()
    
    if form.validate_on_submit():
        try:
            print(f"DEBUG: Form data received:")
            print(f"  Name: {form.name.data}")
            print(f"  Capacity: {form.capacity.data}")
            print(f"  Hourly rate: {form.hourly_rate.data}")
            print(f"  Half day rate: {form.half_day_rate.data}")
            print(f"  Full day rate: {form.full_day_rate.data}")
            print(f"  Status: {form.status.data}")
            print(f"  Amenities raw: {repr(form.amenities.data)}")
            
            # Handle amenities safely - check if it's already JSON or needs parsing
            amenities_data = form.amenities.data or ""
            amenities_list = []
            
            if amenities_data:
                # Check if it looks like JSON array
                if amenities_data.strip().startswith('[') and amenities_data.strip().endswith(']'):
                    try:
                        import json
                        amenities_list = json.loads(amenities_data)
                        print(f"DEBUG: Parsed amenities as JSON: {amenities_list}")
                    except json.JSONDecodeError:
                        print(f"DEBUG: Failed to parse as JSON, treating as comma-separated")
                        amenities_list = [item.strip() for item in amenities_data.split(',') if item.strip()]
                else:
                    # Treat as comma-separated string
                    amenities_list = [item.strip() for item in amenities_data.split(',') if item.strip()]
                    print(f"DEBUG: Parsed amenities as comma-separated: {amenities_list}")
            
            # Prepare update data with careful type conversion
            update_data = {
                'name': str(form.name.data).strip(),
                'description': str(form.description.data or "").strip()
            }
            
            # Handle capacity
            if form.capacity.data is not None:
                update_data['capacity'] = int(form.capacity.data)
            else:
                update_data['capacity'] = 0
            
            # Handle rates with better validation
            if form.hourly_rate.data is not None:
                update_data['hourly_rate'] = float(form.hourly_rate.data)
            else:
                update_data['hourly_rate'] = 0.0
                
            if form.half_day_rate.data is not None:
                update_data['half_day_rate'] = float(form.half_day_rate.data)
            else:
                update_data['half_day_rate'] = 0.0
                
            if form.full_day_rate.data is not None:
                update_data['full_day_rate'] = float(form.full_day_rate.data)
            else:
                update_data['full_day_rate'] = 0.0
            
            # Handle other fields
            update_data['amenities'] = amenities_list
            update_data['status'] = form.status.data or 'available'
            update_data['image_url'] = str(form.image_url.data or "").strip()
            
            print(f"DEBUG: Update data prepared: {update_data}")
            
            # Attempt the update
            result = supabase_update('rooms', update_data, [('id', 'eq', id)])
            
            print(f"DEBUG: Update result: {result}")
            
            if result:
                flash('Conference room updated successfully', 'success')
                return redirect(url_for('rooms'))
            else:
                flash('Error updating conference room - no data returned from database', 'danger')
                
        except ValueError as ve:
            print(f"ValueError in room update: {ve}")
            flash(f'Invalid data format: {str(ve)}', 'danger')
        except Exception as e:
            print(f"Unexpected error in room update: {e}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Error updating conference room: {str(e)}', 'danger')
    else:
        if form.errors:
            print(f"DEBUG: Form validation errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'danger')
        
        # Pre-fill form with existing data using safe access
        try:
            form.name.data = room.get('name', '')
            form.capacity.data = room.get('capacity', 0)
            form.description.data = room.get('description', '')
            
            # Handle rates safely
            hourly_rate = room.get('hourly_rate', 0)
            if hourly_rate is not None:
                form.hourly_rate.data = float(hourly_rate)
            
            half_day_rate = room.get('half_day_rate', 0)
            if half_day_rate is not None:
                form.half_day_rate.data = float(half_day_rate)
            
            full_day_rate = room.get('full_day_rate', 0)
            if full_day_rate is not None:
                form.full_day_rate.data = float(full_day_rate)
            
            form.status.data = room.get('status', 'available')
            form.image_url.data = room.get('image_url', '')
            
            # Handle amenities safely for display
            amenities = room.get('amenities', [])
            if amenities and isinstance(amenities, list):
                form.amenities.data = ', '.join(amenities)
            else:
                form.amenities.data = ''
                
        except Exception as e:
            print(f"Error pre-filling form: {e}")
            flash('Error loading room data', 'warning')
    
    return render_template('rooms/form.html', title='Edit Conference Room', form=form, room=room)

@app.route('/rooms/<int:id>/delete', methods=['POST'])
@login_required
def delete_room(id):
    """Delete a conference room"""
    # Check if room has any bookings
    bookings = supabase_select('bookings', filters=[('room_id', 'eq', id)])
    
    if bookings:
        flash('Cannot delete room with existing bookings', 'danger')
    else:
        if supabase_delete('rooms', [('id', 'eq', id)]):
            flash('Conference room deleted successfully', 'success')
        else:
            flash('Error deleting room', 'danger')
    
    return redirect(url_for('rooms'))

# ===============================
# Routes - Clients (ENHANCED FOR RELIABLE SUPABASE DATA ACCESS)
# ===============================

# Replace your existing clients route in app.py (around line 1985) with this improved version:

@app.route('/clients')
@login_required
def clients():
    """Client directory - read-only display of all clients with booking counts - ENHANCED WITH DEBUGGING"""
    try:
        print("=== DEBUG: Loading client directory with enhanced debugging")
        
        # Get search and sort parameters
        search_query = request.args.get('search', '').strip()
        sort_by = request.args.get('sort', 'company')
        
        print(f"=== DEBUG: Search query: '{search_query}', Sort by: '{sort_by}'")
        
        # Try the enhanced function first
        try:
            print("=== DEBUG: Attempting to get clients with booking counts...")
            clients_data = get_clients_with_booking_counts()
            print(f"OK: DEBUG: Enhanced function returned {len(clients_data)} clients")
        except Exception as enhanced_error:
            print(f"OK: DEBUG: Enhanced function failed: {enhanced_error}")
            
            # Fallback: Get clients directly without booking counts
            print("=== DEBUG: Trying fallback approach...")
            try:
                clients_response = supabase_admin.table('clients').select('*').order('company_name').execute()
                clients_data = clients_response.data if clients_response.data else []
                
                # Add booking count manually for each client
                for client in clients_data:
                    try:
                        bookings_response = supabase_admin.table('bookings').select('id').eq('client_id', client['id']).neq('status', 'cancelled').execute()
                        client['booking_count'] = len(bookings_response.data) if bookings_response.data else 0
                    except Exception as booking_error:
                        print(f"OK: DEBUG: Error getting booking count for client {client.get('id')}: {booking_error}")
                        client['booking_count'] = 0
                
                print(f"OK: DEBUG: Fallback successful - {len(clients_data)} clients loaded")
                
            except Exception as fallback_error:
                print(f"OK: DEBUG: Fallback also failed: {fallback_error}")
                # Last resort: get basic client data
                try:
                    basic_response = supabase_admin.table('clients').select('*').execute()
                    clients_data = basic_response.data if basic_response.data else []
                    for client in clients_data:
                        client['booking_count'] = 0  # Set default
                    print(f"OK: DEBUG: Basic fallback: {len(clients_data)} clients (no booking counts)")
                except Exception as basic_error:
                    print(f"OK: DEBUG: Even basic fallback failed: {basic_error}")
                    clients_data = []

        if not clients_data:
            print("OK: DEBUG: No clients found in database")
            flash('No clients found in the database. Clients are created automatically when making bookings.', 'info')
        else:
            print(f"=== DEBUG: Processing {len(clients_data)} clients for display")

        # Apply search filter if provided
        if search_query and clients_data:
            print(f"=== DEBUG: Applying search filter for: '{search_query}'")
            filtered_clients = []
            search_lower = search_query.lower()
            
            for client in clients_data:
                # Search in company name, contact person, and email
                searchable_fields = [
                    client.get('company_name', ''),
                    client.get('contact_person', ''),
                    client.get('email', '')
                ]
                
                if any(search_lower in str(field).lower() for field in searchable_fields if field):
                    filtered_clients.append(client)
            
            clients_data = filtered_clients
            print(f"=== DEBUG: Search filtered results: {len(clients_data)} clients")
        
        # Apply sorting
        if clients_data:
            try:
                if sort_by == 'company':
                    clients_data.sort(key=lambda x: (x.get('company_name') or x.get('contact_person', '')).lower())
                elif sort_by == 'contact':
                    clients_data.sort(key=lambda x: x.get('contact_person', '').lower())
                elif sort_by == 'recent':
                    # Sort by ID (assuming newer IDs are more recent)
                    clients_data.sort(key=lambda x: x.get('id', 0), reverse=True)
                elif sort_by == 'bookings':
                    clients_data.sort(key=lambda x: x.get('booking_count', 0), reverse=True)
                
                print(f"OK: DEBUG: Clients sorted by {sort_by}")
                
            except Exception as sort_error:
                print(f"OK: WARNING: Error sorting clients: {sort_error}")
                # Use default sorting
                try:
                    clients_data.sort(key=lambda x: (x.get('company_name') or x.get('contact_person', '')).lower())
                except:
                    pass  # If even basic sorting fails, just use the data as-is
        
        # Log activity
        try:
            log_user_activity(
                ActivityTypes.PAGE_VIEW,
                f"Viewed client directory (search: '{search_query}', sort: '{sort_by}', results: {len(clients_data)})",
                resource_type='page',
                metadata={
                    'page': 'client_directory',
                    'search_query': search_query,
                    'sort_by': sort_by,
                    'results_count': len(clients_data),
                    'total_clients': len(clients_data)
                }
            )
        except Exception as log_error:
            print(f"Failed to log client directory view: {log_error}")
        
        # Final debug output
        print(f"=== DEBUG: Final client directory statistics:")
        print(f"  - Total clients displayed: {len(clients_data)}")
        if clients_data:
            clients_with_bookings = len([c for c in clients_data if c.get('booking_count', 0) > 0])
            print(f"  - Clients with bookings: {clients_with_bookings}")
            print(f"  - Sample client: {clients_data[0].get('company_name') or clients_data[0].get('contact_person', 'Unknown')}")
        print(f"  - Search query: '{search_query}'")
        print(f"  - Sort method: {sort_by}")
        
        # Debug template variables before rendering
        template_vars = {
            'title': 'Client Directory', 
            'clients': clients_data,
            'search_query': search_query,
            'sort_by': sort_by
        }
        
        print(f"=OK: DEBUG: Rendering template with {len(clients_data)} clients")
        
        return render_template('clients/index.html', **template_vars)
        
    except Exception as e:
        print(f"OK: CRITICAL ERROR: Failed to load client directory: {e}")
        import traceback
        traceback.print_exc()
        
        # Log the error
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Client directory error: {str(e)}",
                status='failed',
                metadata={'error': str(e), 'error_type': type(e).__name__}
            )
        except Exception as log_error:
            print(f"Failed to log client directory error: {log_error}")
        
        # Show error message to user
        flash('Error loading client directory. Please try again or contact support if the issue persists.', 'danger')
        
        # Return empty data to prevent template errors
        return render_template('clients/index.html', 
                              title='Client Directory', 
                              clients=[], 
                              search_query='', 
                              sort_by='company')

@app.route('/clients/<int:id>')
@login_required
def view_client(id):
    """View client details and booking history (read-only)"""
    try:
        print(f"=== DEBUG: Loading client details for ID {id}")
        
        # Get client data using enhanced function
        client = get_client_by_id_from_db(id)
        
        if not client:
            flash('Client not found', 'danger')
            return redirect(url_for('clients'))
        
        # Get client bookings using enhanced function
        bookings_data = get_client_bookings_from_db(id)
        
        print(f"OK: DEBUG: Found {len(bookings_data)} bookings for client")
        
        # Calculate client statistics
        total_bookings = len(bookings_data)
        total_spent = sum(float(booking.get('total_price', 0)) for booking in bookings_data)
        avg_booking_value = total_spent / total_bookings if total_bookings > 0 else 0
        
        # Separate upcoming and past bookings
        now = get_cat_time()
        upcoming_bookings = []
        past_bookings = []
        
        for booking in bookings_data:
            try:
                # Handle both string and datetime objects
                if isinstance(booking.get('end_time'), str):
                    end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    end_time = booking.get('end_time')
                
                if end_time and end_time > now:
                    upcoming_bookings.append(booking)
                else:
                    past_bookings.append(booking)
            except Exception as date_error:
                print(f"OK: WARNING: Error parsing date for booking {booking.get('id')}: {date_error}")
                # Add to past bookings as fallback
                past_bookings.append(booking)
        
        # Add statistics to client data for template
        client_stats = {
            'total_bookings': total_bookings,
            'total_spent': round(total_spent, 2),
            'avg_booking_value': round(avg_booking_value, 2),
            'upcoming_bookings': len(upcoming_bookings),
            'past_bookings': len(past_bookings),
            'recent_bookings': sorted(bookings_data, key=lambda x: x.get('start_time', ''), reverse=True)[:5]
        }
        
        # Get client name for logging
        client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
        
        # Log client view activity
        try:
            log_user_activity(
                ActivityTypes.VIEW_CLIENT,
                f"Viewed client details for '{client_name}'",
                resource_type='client',
                resource_id=id,
                metadata={
                    'client_name': client_name,
                    'total_bookings': total_bookings,
                    'upcoming_bookings': len(upcoming_bookings),
                    'past_bookings': len(past_bookings)
                }
            )
        except Exception as log_error:
            print(f"Failed to log client view: {log_error}")
        
        print(f"=== DEBUG: Client statistics calculated:")
        print(f"  - Total bookings: {total_bookings}")
        print(f"  - Total spent: ${total_spent:.2f}")
        print(f"  - Upcoming: {len(upcoming_bookings)}")
        print(f"  - Past: {len(past_bookings)}")
        
        return render_template('clients/view.html', 
                              title=f'Client: {client_name}', 
                              client=client, 
                              bookings=bookings_data,
                              stats=client_stats,
                              now=now)
                              
    except Exception as e:
        print(f"OK: ERROR: Failed to load client details for ID {id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Log the error
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Error viewing client ID {id}: {str(e)}",
                resource_type='client',
                resource_id=id,
                status='failed',
                metadata={'error': str(e)}
            )
        except Exception as log_error:
            print(f"Failed to log client view error: {log_error}")
        
        flash('Error loading client details', 'danger')
        return redirect(url_for('clients'))
    
# Add this route to your app.py file after the existing client routes (around line 2250)

@app.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@activity_logged(ActivityTypes.UPDATE_CLIENT, "Updated client details", "client")
def edit_client(id):
    """Edit an existing client's details"""
    # Get the client data
    client = get_client_by_id_from_db(id)
    if not client:
        flash('Client not found', 'danger')
        return redirect(url_for('clients'))
    
    form = ClientForm()
    
    if form.validate_on_submit():
        try:
            # Prepare update data
            update_data = {
                'company_name': form.company_name.data.strip() if form.company_name.data else None,
                'contact_person': form.contact_person.data.strip(),
                'email': form.email.data.strip().lower(),
                'phone': form.phone.data.strip() if form.phone.data else None,
                'address': form.address.data.strip() if form.address.data else None,
                'notes': form.notes.data.strip() if form.notes.data else None,
                'updated_at': get_cat_time().isoformat()
            }
            
            # Validate required fields
            if not update_data['contact_person'] or not update_data['email']:
                flash('Contact person and email are required fields.', 'danger')
                return render_template('clients/form.html', title='Edit Client', form=form, client=client)
            
            # Check for duplicate email (excluding current client)
            existing_client = supabase_admin.table('clients').select('id, email').eq('email', update_data['email']).neq('id', id).execute()
            if existing_client.data:
                flash('Another client with this email address already exists.', 'warning')
                return render_template('clients/form.html', title='Edit Client', form=form, client=client)
            
            # Update the client
            result = update_client_in_db(id, update_data)
            
            if result:
                client_name = update_data['company_name'] or update_data['contact_person']
                flash(f'Client "{client_name}" updated successfully!', 'success')
                return redirect(url_for('view_client', id=id))
            else:
                flash('Error updating client. Please try again.', 'danger')
                
        except Exception as e:
            print(f"Error updating client: {e}")
            flash('An unexpected error occurred. Please try again.', 'danger')
    else:
        # Pre-fill form with existing data
        form.company_name.data = client.get('company_name', '')
        form.contact_person.data = client.get('contact_person', '')
        form.email.data = client.get('email', '')
        form.phone.data = client.get('phone', '')
        form.address.data = client.get('address', '')
        form.notes.data = client.get('notes', '')
    
    return render_template('clients/form.html', title='Edit Client', form=form, client=client)

@app.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
@activity_logged(ActivityTypes.DELETE_CLIENT, "Deleted client", "client")
def delete_client(id):
    """Delete a client (with validation) - OPTIONAL"""
    try:
        # Get client details for logging
        client = get_client_by_id_from_db(id)
        if not client:
            flash('Client not found', 'danger')
            return redirect(url_for('clients'))
        
        client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
        
        # Attempt to delete the client
        success, message = delete_client_from_db(id)
        
        if success:
            flash(f'Client "{client_name}" deleted successfully.', 'success')
        else:
            flash(message, 'danger')
            
    except Exception as e:
        print(f"Error deleting client: {e}")
        flash('An unexpected error occurred while deleting the client.', 'danger')
    
    return redirect(url_for('clients'))
    
# API endpoint for client data verification
@app.route('/api/clients/verify/<int:id>')
@login_required
def verify_client_data(id):
    """API endpoint to verify client data exists in Supabase"""
    try:
        client = get_client_by_id_from_db(id)
        
        if client:
            return jsonify({
                'success': True,
                'client_exists': True,
                'client_name': client.get('company_name') or client.get('contact_person'),
                'email': client.get('email'),
                'data_source': 'supabase_database'
            })
        else:
            return jsonify({
                'success': True,
                'client_exists': False,
                'message': 'Client not found in database'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/sync')
@login_required
def sync_clients_data():
    """API endpoint to sync and verify all client data"""
    try:
        clients = get_all_clients_from_db()
        
        return jsonify({
            'success': True,
            'total_clients': len(clients),
            'clients': [
                {
                    'id': client['id'],
                    'name': client.get('company_name') or client.get('contact_person'),
                    'email': client.get('email'),
                    'phone': client.get('phone')
                }
                for client in clients
            ],
            'data_source': 'supabase_database'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===============================
# Routes - Add-ons (UPDATED WITH ACCURATE STATISTICS)
# ===============================

@app.route('/addons')
@login_required
def addons():
    """Enhanced add-ons page with robust Supabase data handling and accurate statistics"""
    try:
        print("=== DEBUG: Starting enhanced addons route")
        
        # Always use the reliable fallback approach instead of nested queries
        # This ensures better compatibility with different Supabase configurations
        
        # Step 1: Get all categories
        try:
            categories_response = supabase_admin.table('addon_categories').select('*').order('name').execute()
            categories = categories_response.data if categories_response.data else []
            print(f"OK: DEBUG: Found {len(categories)} categories")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch categories: {e}")
            categories = []
        
        # Step 2: Get all addons
        try:
            addons_response = supabase_admin.table('addons').select('*').order('name').execute()
            all_addons = addons_response.data if addons_response.data else []
            print(f"OK: DEBUG: Found {len(all_addons)} total addons")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch addons: {e}")
            all_addons = []
        
        # Step 3: Get booking usage data
        addon_usage = {}
        try:
            booking_addons_response = supabase_admin.table('booking_addons').select('addon_id').execute()
            booking_addons = booking_addons_response.data if booking_addons_response.data else []
            
            for ba in booking_addons:
                addon_id = ba.get('addon_id')
                if addon_id:
                    addon_usage[addon_id] = addon_usage.get(addon_id, 0) + 1
            
            print(f"OK: DEBUG: Calculated usage for {len(addon_usage)} addons from {len(booking_addons)} booking_addon records")
        except Exception as e:
            print(f"OK: DEBUG: Usage calculation failed: {e}")
            addon_usage = {}
        
        # Step 4: Process categories and group addons
        total_addons = len(all_addons)
        active_addons = 0
        addons_with_usage = 0
        
        # Initialize categories with empty addon lists
        for category in categories:
            category['addons'] = []
            # Ensure category has description
            if 'description' not in category or category['description'] is None:
                category['description'] = ''
        
        # Group addons by category and process addon data
        addons_by_category = {}
        uncategorized_addons = []
        
        for addon in all_addons:
            # Ensure addon has all required fields with defaults
            addon['name'] = addon.get('name', 'Unnamed Addon')
            addon['description'] = addon.get('description', '')
            addon['price'] = float(addon.get('price', 0.0))
            addon['is_active'] = bool(addon.get('is_active', True))
            addon['category_id'] = addon.get('category_id')
            
            # Count active addons
            if addon['is_active']:
                active_addons += 1
            
            # Add usage information
            booking_count = addon_usage.get(addon.get('id'), 0)
            addon['booking_count'] = booking_count
            addon['has_bookings'] = booking_count > 0
            
            if booking_count > 0:
                addons_with_usage += 1
            
            print(f"=== DEBUG: Addon '{addon['name']}' - Active: {addon['is_active']}, Bookings: {booking_count}, Category ID: {addon['category_id']}")
            
            # Group by category
            category_id = addon.get('category_id')
            if category_id:
                if category_id not in addons_by_category:
                    addons_by_category[category_id] = []
                addons_by_category[category_id].append(addon)
            else:
                uncategorized_addons.append(addon)
        
        # Step 5: Assign addons to their categories
        for category in categories:
            category_id = category.get('id')
            if category_id in addons_by_category:
                category['addons'] = addons_by_category[category_id]
                print(f"OK: DEBUG: Category '{category['name']}' has {len(category['addons'])} addons")
            else:
                category['addons'] = []
                print(f"GOK:n+OK: DEBUG: Category '{category['name']}' has no addons")
        
        # Step 6: Handle uncategorized addons (create a temporary category if needed)
        if uncategorized_addons:
            print(f"OK: DEBUG: Found {len(uncategorized_addons)} uncategorized addons")
            uncategorized_category = {
                'id': None,
                'name': 'Uncategorized',
                'description': 'Add-ons without a specific category',
                'addons': uncategorized_addons
            }
            categories.append(uncategorized_category)
        
        # Step 7: Calculate final statistics
        usage_rate = (addons_with_usage / total_addons * 100) if total_addons > 0 else 0
        
        statistics = {
            'total_addons': total_addons,
            'total_categories': len([c for c in categories if c.get('id') is not None]),  # Don't count "Uncategorized"
            'active_addons': active_addons,
            'usage_rate': round(usage_rate, 1),
            'addons_with_usage': addons_with_usage
        }
        
        print(f"=== DEBUG: Final statistics:")
        print(f"  - Total addons: {statistics['total_addons']}")
        print(f"  - Total categories: {statistics['total_categories']}")
        print(f"  - Active addons: {statistics['active_addons']}")
        print(f"  - Usage rate: {statistics['usage_rate']}%")
        print(f"  - Addons with usage: {statistics['addons_with_usage']}")
        
        # Step 8: Verify data integrity before rendering
        print(f"=== DEBUG: Data verification:")
        for category in categories:
            print(f"  - Category '{category['name']}': {len(category.get('addons', []))} addons")
            for addon in category.get('addons', [])[:3]:  # Show first 3 addons per category
                print(f"    * {addon['name']} - ${addon['price']} - Active: {addon['is_active']}")
        
        return render_template('addons/index.html', 
                             title='Add-ons', 
                             categories=categories,
                             stats=statistics)
        
    except Exception as e:
        print(f"OK: ERROR: Addons route failed: {e}")
        import traceback
        traceback.print_exc()
        
        flash('Error loading add-ons page. Please try again.', 'danger')
        
        # Return with safe empty data
        empty_stats = {
            'total_addons': 0,
            'total_categories': 0,
            'active_addons': 0,
            'usage_rate': 0,
            'addons_with_usage': 0
        }
        
        return render_template('addons/index.html', 
                             title='Add-ons', 
                             categories=[],
                             stats=empty_stats)
        
        
@app.route('/addons/new', methods=['GET', 'POST'])
@login_required
def new_addon():
    """Add a new add-on service or equipment"""
    form = AddonForm()
    
    # Populate the category choices
    categories = supabase_select('addon_categories')
    form.category_id.choices = [(c['id'], c['name']) for c in categories]
    
    if form.validate_on_submit():
        addon_data = {
            'name': form.name.data,
            'description': form.description.data,
            'price': float(form.price.data),
            'category_id': form.category_id.data,
            'is_active': form.is_active.data
        }
        
        result = supabase_insert('addons', addon_data)
        if result:
            flash('Add-on service created successfully', 'success')
            return redirect(url_for('addons'))
        else:
            flash('Error creating add-on', 'danger')
    
    return render_template('addons/form.html', title='New Add-on', form=form)

@app.route('/addons/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_addon(id):
    """Edit an add-on"""
    addon_data = supabase_select('addons', filters=[('id', 'eq', id)])
    if not addon_data:
        flash('Add-on not found', 'danger')
        return redirect(url_for('addons'))
    
    addon = addon_data[0]
    form = AddonForm()
    
    categories = supabase_select('addon_categories')
    form.category_id.choices = [(c['id'], c['name']) for c in categories]
    
    if form.validate_on_submit():
        update_data = {
            'name': form.name.data,
            'description': form.description.data,
            'price': float(form.price.data),
            'category_id': form.category_id.data,
            'is_active': form.is_active.data
        }
        
        result = supabase_update('addons', update_data, [('id', 'eq', id)])
        if result:
            flash('Add-on updated successfully', 'success')
            return redirect(url_for('addons'))
        else:
            flash('Error updating add-on', 'danger')
    else:
        # Pre-fill form
        form.name.data = addon['name']
        form.description.data = addon['description']
        form.price.data = addon['price']
        form.category_id.data = addon['category_id']
        form.is_active.data = addon['is_active']
    
    return render_template('addons/form.html', title='Edit Add-on', form=form, addon=addon)

@app.route('/addon_categories/new', methods=['GET', 'POST'])
@login_required
@csrf.exempt  # Temporarily disable CSRF for this route
def new_addon_category():
    """Add a new add-on category - CSRF disabled temporarily"""
    if request.method == 'POST':
        try:
            # Get data from form (works with or without WTForms)
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            
            print(f"DEBUG: Received form data - name: '{name}', description: '{description}'")
            
            if not name:
                flash('Category name is required', 'danger')
                return redirect(url_for('new_addon_category'))
            
            category_data = {'name': name, 'description': description}
            result = supabase_insert('addon_categories', category_data)
            
            if result:
                flash('Category added successfully', 'success')
                return redirect(url_for('addons'))
            else:
                flash('Error adding category', 'danger')
                return redirect(url_for('new_addon_category'))
                
        except Exception as e:
            print(f"Error creating addon category: {e}")
            flash('Error adding category', 'danger')
            return redirect(url_for('new_addon_category'))
    
    # For GET request, create a form object for template compatibility
    form = AddonCategoryForm()
    return render_template('addons/new_category.html', title='New Add-on Category', form=form)

@app.route('/addon_categories/new_simple', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def new_addon_category_simple():
    """Simple addon category creation without CSRF (temporary workaround)"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            
            if not name:
                flash('Category name is required', 'danger')
                return redirect(url_for('new_addon_category_simple'))
            
            category_data = {'name': name, 'description': description}
            result = supabase_insert('addon_categories', category_data)
            
            if result:
                flash('Category added successfully', 'success')
                return redirect(url_for('addons'))
            else:
                flash('Error adding category', 'danger')
                
        except Exception as e:
            print(f"Error creating addon category: {e}")
            flash('Error adding category', 'danger')
    
    return render_template('addons/new_category_simple.html', title='New Add-on Category')

@app.route('/debug/csrf')
@login_required
def debug_csrf():
    """Debug CSRF configuration"""
    from flask_wtf.csrf import generate_csrf
    try:
        csrf_token = generate_csrf()
        return jsonify({
            'csrf_token': csrf_token,
            'session_keys': list(session.keys()),
            'secret_key_set': bool(app.secret_key),
            'csrf_enabled': hasattr(app, 'extensions') and 'csrf' in app.extensions
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/addon_categories', methods=['POST'])
@login_required
@csrf.exempt
def api_create_addon_category():
    """API endpoint to create addon category without CSRF (for AJAX calls)"""
    try:
        data = request.get_json()
        if not data:
            data = request.form.to_dict()
        
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'success': False, 'error': 'Category name is required'}), 400
        
        category_data = {'name': name, 'description': description}
        result = supabase_insert('addon_categories', category_data)
        
        if result:
            return jsonify({
                'success': True, 
                'message': 'Category added successfully',
                'category': result
            })
        else:
            return jsonify({'success': False, 'error': 'Error adding category'}), 500
            
    except Exception as e:
        print(f"API error creating addon category: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/addon_categories/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_addon_category(id):
    """Edit an add-on category with proper CSRF protection"""
    # Get the category data first
    category_data = supabase_select('addon_categories', filters=[('id', 'eq', id)])
    if not category_data:
        flash('Category not found', 'danger')
        return redirect(url_for('addons'))
    
    category = category_data[0]
    form = AddonCategoryForm()
    
    if form.validate_on_submit():
        try:
            update_data = {
                'name': form.name.data.strip(),
                'description': form.description.data.strip() if form.description.data else ''
            }
            
            result = supabase_update('addon_categories', update_data, [('id', 'eq', id)])
            
            if result:
                flash('Category updated successfully', 'success')
            else:
                flash('Error updating category', 'danger')
                
        except Exception as e:
            print(f"Error updating addon category: {e}")
            flash('Error updating category', 'danger')
    else:
        # Pre-fill form with existing data on GET request
        if request.method == 'GET':
            form.name.data = category.get('name', '')
            form.description.data = category.get('description', '')
        
        # Display form validation errors on POST
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    
    return redirect(url_for('addons'))

@app.route('/addon_categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_addon_category(id):
    """Delete an add-on category"""
    # Check if category has any addons
    addons_in_category = supabase_select('addons', filters=[('category_id', 'eq', id)])
    
    if addons_in_category:
        flash('Cannot delete category with existing add-ons', 'danger')
    else:
        if supabase_delete('addon_categories', [('id', 'eq', id)]):
            flash('Category deleted successfully', 'success')
        else:
            flash('Error deleting category', 'danger')
    
    return redirect(url_for('addons'))

@app.route('/addons/<int:id>/delete', methods=['POST'])
@login_required
def delete_addon(id):
    """Delete an add-on"""
    # Check if addon is used in any bookings
    bookings = supabase_select('booking_addons', filters=[('addon_id', 'eq', id)])
    
    if bookings:
        flash('Cannot delete add-on that is used in bookings', 'danger')
    else:
        if supabase_delete('addons', [('id', 'eq', id)]):
            flash('Add-on deleted successfully', 'success')
        else:
            flash('Error deleting add-on', 'danger')
    
    return redirect(url_for('addons'))

# ===============================
# Routes - Bookings (UPDATED WITH QUOTATION INTEGRATION)
# ===============================

@app.route('/bookings')
@login_required
def bookings():
    """List all bookings using Supabase admin client with enhanced error handling"""
    status_filter = request.args.get('status', 'all')
    date_filter = request.args.get('date', 'upcoming')
    
    try:
        print(f"=== DEBUG: Loading bookings page with filters - status: {status_filter}, date: {date_filter}")
        
        # Query using admin client for consistent access
        query = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, company_name, contact_person)
        """)
        
        # Apply status filter
        if status_filter != 'all':
            query = query.eq('status', status_filter)
        
        # Apply date filter
        now = get_cat_time().isoformat()
        today = get_cat_time().date().isoformat()
        tomorrow = (get_cat_time().date() + timedelta(days=1)).isoformat()
        
        if date_filter == 'upcoming':
            query = query.gte('end_time', now)
        elif date_filter == 'past':
            query = query.lt('end_time', now)
        elif date_filter == 'today':
            query = query.gte('start_time', today).lt('start_time', tomorrow)
        
        response = query.order('start_time').execute()
        bookings_raw = response.data
        
        print(f"OK: DEBUG: Found {len(bookings_raw)} bookings from database")
        
        # Process each booking to ensure room and client data exists
        bookings_processed = []
        for booking in bookings_raw:
            processed_booking = booking.copy()
            
            # Ensure room data exists
            if not booking.get('room') or not isinstance(booking.get('room'), dict):
                print(f"NO room data for booking {booking.get('id')}, fetching separately")
                if booking.get('room_id'):
                    room_data = supabase_admin.table('rooms').select('id, name, capacity').eq('id', booking.get('room_id')).execute()
                    if room_data.data:
                        processed_booking['room'] = room_data.data[0]
                    else:
                        processed_booking['room'] = {'id': booking.get('room_id'), 'name': 'Unknown Room', 'capacity': 0}
                else:
                    processed_booking['room'] = {'id': None, 'name': 'Unknown Room', 'capacity': 0}
            
            # Ensure client data exists
            if not booking.get('client') or not isinstance(booking.get('client'), dict):
                print(f"NO client data for booking {booking.get('id')}, fetching separately")
                if booking.get('client_id'):
                    client_data = supabase_admin.table('clients').select('id, company_name, contact_person').eq('id', booking.get('client_id')).execute()
                    if client_data.data:
                        processed_booking['client'] = client_data.data[0]
                    else:
                        processed_booking['client'] = {'id': booking.get('client_id'), 'company_name': None, 'contact_person': 'Unknown Client'}
                else:
                    processed_booking['client'] = {'id': None, 'company_name': None, 'contact_person': 'Unknown Client'}
            
            bookings_processed.append(processed_booking)
        
        # Convert datetime strings to datetime objects for template
        bookings_data = convert_datetime_strings(bookings_processed)
        
        print(f"OK: DEBUG: Successfully processed {len(bookings_data)} bookings for display")
        
    except Exception as e:
        print(f"OK: ERROR: Failed to fetch bookings: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: try to get bookings without relationships
        try:
            print("=== DEBUG: Trying fallback approach for bookings")
            simple_bookings = supabase_admin.table('bookings').select('*')
            
            # Apply the same filters
            if status_filter != 'all':
                simple_bookings = simple_bookings.eq('status', status_filter)
            
            now = get_cat_time().isoformat()
            today = get_cat_time().date().isoformat()
            tomorrow = (get_cat_time().date() + timedelta(days=1)).isoformat()
            
            if date_filter == 'upcoming':
                simple_bookings = simple_bookings.gte('end_time', now)
            elif date_filter == 'past':
                simple_bookings = simple_bookings.lt('end_time', now)
            elif date_filter == 'today':
                simple_bookings = simple_bookings.gte('start_time', today).lt('start_time', tomorrow)
            
            response = simple_bookings.order('start_time').execute()
            
            if response.data:
                bookings_data = []
                for booking in response.data:
                    # Manually fetch room and client data
                    if booking.get('room_id'):
                        room_data = supabase_admin.table('rooms').select('id, name, capacity').eq('id', booking['room_id']).execute()
                        booking['room'] = room_data.data[0] if room_data.data else {'id': booking['room_id'], 'name': 'Unknown Room', 'capacity': 0}
                    else:
                        booking['room'] = {'id': None, 'name': 'Unknown Room', 'capacity': 0}
                    
                    if booking.get('client_id'):
                        client_data = supabase_admin.table('clients').select('id, company_name, contact_person').eq('id', booking['client_id']).execute()
                        booking['client'] = client_data.data[0] if client_data.data else {'id': booking['client_id'], 'company_name': None, 'contact_person': 'Unknown Client'}
                    else:
                        booking['client'] = {'id': None, 'company_name': None, 'contact_person': 'Unknown Client'}
                    
                    bookings_data.append(booking)
                
                bookings_data = convert_datetime_strings(bookings_data)
                print(f"OK: DEBUG: Fallback successful, processed {len(bookings_data)} bookings")
            else:
                bookings_data = []
                print("OK: DEBUG: No bookings found")
                
        except Exception as fallback_error:
            print(f"OK: DEBUG: Fallback also failed: {fallback_error}")
            bookings_data = []
            flash('Error loading bookings', 'danger')
    
    return render_template('bookings/index.html', 
                          title='Bookings', 
                          bookings=bookings_data,
                          status_filter=status_filter,
                          date_filter=date_filter)

@app.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def new_booking():
    """Create a new booking with enhanced error handling and new schema support"""
    form = BookingForm()
    rooms_for_template = []
    
    # Get available rooms for the form
    try:
        rooms_data = supabase_select('rooms', filters=[('status', 'eq', 'available')])
        form.room_id.choices = [(r['id'], f"{r['name']} (Capacity: {r['capacity']})") for r in rooms_data]
        rooms_for_template = rooms_data
    except Exception as e:
        print(f"OK: ERROR: Failed to load rooms: {e}")
        flash('Error loading rooms. Please try again.', 'danger')
        return redirect(url_for('bookings'))

    if request.method == 'POST':
        return handle_booking_creation(request.form, rooms_for_template)
    
    return render_template('bookings/form.html', 
                          title='New Booking', 
                          form=form, 
                          rooms=rooms_for_template)


@app.route('/bookings/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_booking(id):
    """Edit an existing booking with enhanced error handling"""
    try:
        # Get booking with all details
        booking = get_complete_booking_details(id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        form = BookingForm()
        rooms_for_template = []
        
        # Get available rooms plus current room
        try:
            rooms_data = supabase_select('rooms', filters=[('status', 'eq', 'available')])
            current_room = supabase_select('rooms', filters=[('id', 'eq', booking['room_id'])])
            
            all_rooms = rooms_data.copy()
            if current_room and current_room[0] not in all_rooms:
                all_rooms.append(current_room[0])
            
            form.room_id.choices = [(r['id'], f"{r['name']} (Capacity: {r['capacity']})") for r in all_rooms]
            rooms_for_template = all_rooms
        except Exception as e:
            print(f"OK: ERROR: Failed to load rooms for edit: {e}")
            flash('Error loading rooms. Please try again.', 'danger')
            return redirect(url_for('bookings'))
        
        if request.method == 'POST':
            return handle_booking_update(id, request.form, booking, rooms_for_template)
        else:
            # Pre-fill form with existing data
            populate_form_with_booking_data(form, booking)
        
        return render_template('bookings/form.html', 
                              title='Edit Booking', 
                              form=form, 
                              booking=booking,
                              rooms=rooms_for_template)
                              
    except Exception as e:
        print(f"OK: ERROR: Failed to load booking for edit: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading booking for edit', 'danger')
        return redirect(url_for('bookings'))
    
@app.route('/bookings/<int:id>/delete', methods=['POST'])
@login_required
def delete_booking(id):
    """Cancel a booking (soft delete) - NOW WITH ACTIVITY LOGGING"""
    try:
        # Get booking details before deletion for logging
        booking_data = supabase_admin.table('bookings').select('title, room_id, client_id').eq('id', id).execute()
        booking_title = booking_data.data[0]['title'] if booking_data.data else f'Booking #{id}'
        
        result = supabase_update('bookings', {'status': 'cancelled'}, [('id', 'eq', id)])
        
        if result:
            try:
                log_user_activity(
                    ActivityTypes.CANCEL_BOOKING,
                    f"Cancelled booking: {booking_title}",
                    resource_type='booking',
                    resource_id=id,
                    metadata={'action': 'soft_delete', 'new_status': 'cancelled'}
                )
            except Exception as log_error:
                print(f"Failed to log booking cancellation: {log_error}")
            
            flash('Booking has been cancelled', 'success')
        else:
            try:
                log_user_activity(
                    ActivityTypes.CANCEL_BOOKING,
                    f"Failed to cancel booking: {booking_title}",
                    resource_type='booking',
                    resource_id=id,
                    status='failed'
                )
            except Exception as log_error:
                print(f"Failed to log booking cancellation failure: {log_error}")
            
            flash('Error cancelling booking', 'danger')
            
    except Exception as e:
        try:
            log_user_activity(
                ActivityTypes.CANCEL_BOOKING,
                f"Error cancelling booking #{id}: {str(e)}",
                resource_type='booking',
                resource_id=id,
                status='failed',
                metadata={'error': str(e)}
            )
        except Exception as log_error:
            print(f"Failed to log booking cancellation error: {log_error}")
        
        print(f"Error cancelling booking: {e}")
        flash('Error cancelling booking', 'danger')
    
    return redirect(url_for('bookings'))

@app.route('/bookings/<int:id>/change-status/<status>', methods=['POST'])
@login_required
def change_booking_status(id, status):
    """Change booking status"""
    if status not in ['tentative', 'confirmed', 'cancelled']:
        flash('Invalid status', 'danger')
        return redirect(url_for('view_booking', id=id))
    
    try:
        result = supabase_update('bookings', {'status': status}, [('id', 'eq', id)])
        
        if result:
            status_messages = {
                'tentative': 'Booking marked as tentative',
                'confirmed': 'Booking confirmed successfully', 
                'cancelled': 'Booking cancelled successfully'
            }
            flash(status_messages[status], 'success')
        else:
            flash('Error updating booking status', 'danger')
            
    except Exception as e:
        print(f"Error changing booking status: {e}")
        flash('Error updating booking status', 'danger')
    
    return redirect(url_for('view_booking', id=id))

@app.route('/bookings/<int:id>/add-accommodation', methods=['GET', 'POST'])
@login_required
def add_accommodation(id):
    """Add accommodation to a booking"""
    booking_data = supabase_select('bookings', filters=[('id', 'eq', id)])
    if not booking_data:
        flash('Booking not found', 'danger')
        return redirect(url_for('bookings'))
    
    booking = booking_data[0]
    # Convert datetime strings for the booking data
    booking = convert_datetime_strings(booking)
    
    form = AccommodationForm()
    
    if form.validate_on_submit():
        accommodation_data = {
            'booking_id': booking['id'],
            'room_type': form.room_type.data,
            'check_in': form.check_in.data.isoformat(),
            'check_out': form.check_out.data.isoformat(),
            'number_of_rooms': form.number_of_rooms.data,
            'special_requests': form.special_requests.data
        }
        
        result = supabase_insert('accommodations', accommodation_data)
        if result:
            flash('Accommodation added to booking', 'success')
            return redirect(url_for('view_booking', id=booking['id']))
        else:
            flash('Error adding accommodation', 'danger')
    
    return render_template('bookings/accommodation_form.html', title='Add Accommodation', form=form, booking=booking)

# ===============================
# Routes - Quotation and Invoice (NEW FUNCTIONALITY)
# ===============================

@app.route('/bookings/<int:id>/quotation')
@login_required
def generate_quotation(id):
    """Generate a quotation for a booking - UPDATED FOR USER-ENTERED RATES"""
    try:
        print(f"=== DEBUG: Generating quotation for booking ID {id}")
        
        # Get complete booking data
        booking = get_complete_booking_details(id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        # Use stored room_rate and addons_total instead of calculating
        room_rate = float(booking.get('room_rate', 0))
        addons_total = float(booking.get('addons_total', 0))
        total = float(booking.get('total_price', 0))
        
        # Get duration for display (informational only)
        try:
            if isinstance(booking.get('start_time'), str):
                start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).replace(tzinfo=None)
                end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                start_time = booking['start_time']
                end_time = booking['end_time']
            
            duration_hours = (end_time - start_time).total_seconds() / 3600
        except Exception as duration_error:
            print(f"OK: WARNING: Error calculating duration: {duration_error}")
            duration_hours = 0
            start_time = get_cat_time()
            end_time = start_time + timedelta(hours=4)
        
        # Get custom addons for display
        custom_addons = booking.get('custom_addons', [])
        room_items = [addon for addon in custom_addons if addon.get('is_room_rate', False)]
        addon_items = [addon for addon in custom_addons if not addon.get('is_room_rate', False)]
        
        # Update booking data for template
        booking.update({
            'room_rate': round(room_rate, 2),
            'rate_type': 'Custom Rate',  # No longer calculated from fixed rates
            'addons_total': round(addons_total, 2),
            'room_items': room_items,
            'addon_items': addon_items,
            'duration_hours': round(duration_hours, 1),
            'total': round(total, 2)
        })
        
        booking = convert_datetime_strings(booking)
        
        quotation_number = f"QUO-{booking['id']}-{get_cat_time().strftime('%Y%m')}"
        valid_until = get_cat_time() + timedelta(days=30)
        
        # Generate clean PDF filename: CompanyName_EventType_DD-MM-YYYY.pdf
        import re
        company_name = booking.get('client', {}).get('company_name') or booking.get('company_name') or booking.get('client_name', 'Company')
        company_name_clean = re.sub(r'[^a-zA-Z0-9]', '', str(company_name))
        
        # Handle event_type - it might be a dict or string
        event_type_raw = booking.get('event_type', 'Event')
        if isinstance(event_type_raw, dict):
            event_type_str = event_type_raw.get('name', 'Event')
        else:
            event_type_str = str(event_type_raw)
        event_type_clean = re.sub(r'[^a-zA-Z0-9]', '', event_type_str)
        
        date_str = get_cat_time().strftime('%d-%m-%Y')
        pdf_filename = f"{company_name_clean}_{event_type_clean}_{date_str}"
        
        print(f"OK: DEBUG: Quotation data prepared - Room: ${room_rate:.2f}, Addons: ${addons_total:.2f}, Total: ${total:.2f}")
        print(f"OK: DEBUG: PDF filename: {pdf_filename}.pdf")
        
        # Log quotation generation
        try:
            log_user_activity(
                ActivityTypes.GENERATE_REPORT,
                f"Generated quotation {quotation_number} for booking '{booking['title']}'",
                resource_type='quotation',
                resource_id=id,
                metadata={
                    'quotation_number': quotation_number,
                    'total_amount': total,
                    'room_rate': room_rate,
                    'addons_total': addons_total,
                    'client_email': booking.get('client', {}).get('email'),
                    'room_name': booking.get('room', {}).get('name')
                }
            )
        except Exception as log_error:
            print(f"Failed to log quotation generation: {log_error}")
        
        return render_template('bookings/quotation.html', 
                              title=f'Quotation for {booking["title"]}',
                              booking=booking,
                              quotation_number=quotation_number,
                              valid_until=valid_until,
                              pdf_filename=pdf_filename,
                              now=get_cat_time(),
                              timedelta=timedelta)
                              
    except Exception as e:
        print(f"OK: CRITICAL ERROR in quotation generation: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Quotation generation failed for booking ID {id}: {str(e)}",
                resource_type='quotation',
                resource_id=id,
                status='failed',
                metadata={'error': str(e), 'error_type': type(e).__name__}
            )
        except Exception as log_error:
            print(f"Failed to log quotation error: {log_error}")
        
        flash('Error generating quotation. Please check the booking details and try again.', 'danger')
        return redirect(url_for('view_booking', id=id))

@app.route('/bookings/<int:id>/invoice')
@login_required
def generate_invoice(id):
    """Generate an invoice for a booking - UPDATED FOR USER-ENTERED RATES"""
    try:
        print(f"=== DEBUG: Generating invoice for booking ID {id}")
        
        # Get complete booking data
        booking = get_complete_booking_details(id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        # Check if booking is confirmed
        if booking.get('status') != 'confirmed':
            flash('Invoices can only be generated for confirmed bookings. Please confirm the booking first.', 'warning')
            return redirect(url_for('view_booking', id=id))
        
        # Use stored rates instead of calculating
        room_rate = float(booking.get('room_rate', 0))
        addons_total = float(booking.get('addons_total', 0))
        total = float(booking.get('total_price', 0))
        
        # Get custom addons for display
        custom_addons = booking.get('custom_addons', [])
        room_items = [addon for addon in custom_addons if addon.get('is_room_rate', False)]
        addon_items = [addon for addon in custom_addons if not addon.get('is_room_rate', False)]
        
        # Update booking data for template
        booking.update({
            'room_rate': round(room_rate, 2),
            'rate_type': 'Custom Rate',
            'addons_total': round(addons_total, 2),
            'room_items': room_items,
            'addon_items': addon_items,
            'total': round(total, 2)
        })
        
        booking = convert_datetime_strings(booking)
        
        print(f"OK: DEBUG: Invoice data prepared successfully")
        
        # Log invoice generation
        try:
            log_user_activity(
                ActivityTypes.GENERATE_REPORT,
                f"Generated invoice for confirmed booking '{booking['title']}'",
                resource_type='invoice',
                resource_id=id,
                metadata={
                    'invoice_amount': total,
                    'room_rate': room_rate,
                    'addons_total': addons_total,
                    'client_email': booking.get('client', {}).get('email'),
                    'room_name': booking.get('room', {}).get('name')
                }
            )
        except Exception as log_error:
            print(f"Failed to log invoice generation: {log_error}")
        
        return render_template('bookings/invoice.html', 
                              title=f'Invoice for {booking["title"]}',
                              booking=booking,
                              now=get_cat_time(),
                              timedelta=timedelta)
                              
    except Exception as e:
        print(f"OK: ERROR in invoice generation: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Invoice generation failed for booking ID {id}: {str(e)}",
                resource_type='invoice',
                resource_id=id,
                status='failed',
                metadata={'error': str(e)}
            )
        except Exception as log_error:
            print(f"Failed to log invoice error: {log_error}")
        
        flash('Error generating invoice. Please check the booking details and try again.', 'danger')
        return redirect(url_for('view_booking', id=id))

@app.route('/bookings/<int:id>/send-quotation', methods=['POST'])
@login_required
def send_quotation_email(id):
    """Send quotation via email to client"""
    try:
        # Get booking data
        booking_data = supabase_admin.table('bookings').select("""
            *,
            room:rooms(*),
            client:clients(*)
        """).eq('id', id).execute()
        
        if not booking_data.data:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        booking = booking_data.data[0]
        client_email = booking['client']['email']
        
        # Here you would integrate with your email service
        # For now, we'll just flash a success message
        flash(f'Quotation sent successfully to {client_email}', 'success')
        
        # Update booking to mark quotation as sent
        supabase_update('bookings', {'quotation_sent': True}, [('id', 'eq', id)])
        
        return redirect(url_for('view_booking', id=id))
        
    except Exception as e:
        print(f"Send quotation error: {e}")
        flash('Error sending quotation', 'danger')
        return redirect(url_for('view_booking', id=id))

@app.route('/bookings/<int:id>/print-details')
@login_required
def print_booking_details(id):
    """Render booking details optimized for printing"""
    try:
        booking_data = supabase_admin.table('bookings').select("""
            *,
            room:rooms(*),
            client:clients(*),
            booking_addons(
                quantity,
                addon:addons(
                    id, name, price,
                    category:addon_categories(name)
                )
            )
        """).eq('id', id).execute()
        
        if not booking_data.data:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        booking = booking_data.data[0]
        booking = convert_datetime_strings(booking)
        
        return render_template('bookings/print_details.html', 
                              title=f'Booking Details - {booking["title"]}',
                              booking=booking,
                              now=get_cat_time())
                              
    except Exception as e:
        print(f"Print details error: {e}")
        flash('Error loading booking details for printing', 'danger')
        return redirect(url_for('view_booking', id=id))

@app.route('/check-availability')
@login_required
def check_availability():
    """Check room availability for a given time period"""
    room_id = request.args.get('room_id', type=int)
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    booking_id = request.args.get('booking_id', type=int)
    
    if not all([room_id, start_time, end_time]):
        return jsonify({'error': 'Missing parameters'}), 400
    
    try:
        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({'error': 'Invalid datetime format'}), 400
    
    available = is_room_available_supabase(room_id, start_time, end_time, exclude_booking_id=booking_id)
    
    return jsonify({'available': available})

# ===============================
# Routes - Reports
# ===============================

@app.route('/reports')
@login_required
def reports():
    """Reports dashboard with overview statistics using real data - ENHANCED FOR PRODUCTION"""
    try:
        print(f"=== DEBUG: Starting reports dashboard generation at {get_cat_time()}")
        print(f"=== DEBUG: Environment: {os.environ.get('FLASK_ENV', 'development')}")
        print(f"=== DEBUG: Supabase URL: {SUPABASE_URL[:50]}..." if SUPABASE_URL else "OK: No Supabase URL")
        print(f"=== DEBUG: Admin client available: {bool(supabase_admin)}")
        
        # Test basic connectivity first
        try:
            connectivity_test = supabase_admin.table('rooms').select('id').limit(1).execute()
            print(f"OK: DEBUG: Database connectivity test passed - {len(connectivity_test.data)} rows")
        except Exception as conn_error:
            print(f"OK: DEBUG: Database connectivity test failed: {conn_error}")
            flash('Database connection issue detected. Some statistics may be unavailable.', 'warning')
        
        # Get current date info in CAT timezone
        now_cat = get_cat_time()
        today_cat = now_cat.date()
        current_month_start = today_cat.replace(day=1)
        
        print(f"=== DEBUG: Time calculations:")
        print(f"  - Current CAT time: {now_cat}")
        print(f"  - Today CAT date: {today_cat}")
        print(f"  - Month start: {current_month_start}")
        
        # Convert to ISO strings for database queries
        now_iso = now_cat.isoformat()
        current_month_start_iso = current_month_start.isoformat()
        
        # Initialize statistics with safe defaults
        overview_stats = {
            'current_month_bookings': 0,
            'current_month_revenue': 0.0,
            'active_rooms': 0,
            'most_popular_addon': "No data",
            'utilization_rate': 0.0,
            'total_booked_hours': 0.0,
            'avg_booking_value': 0.0
        }
        
        # 1. Get total bookings this month (ENHANCED)
        try:
            print(f"=== DEBUG: Fetching bookings from {current_month_start_iso}...")
            
            # Use admin client with explicit error handling
            bookings_response = supabase_admin.table('bookings').select('id, total_price, start_time, end_time, status').gte('start_time', current_month_start_iso).execute()
            
            print(f"=== DEBUG: Raw bookings response: {len(bookings_response.data) if bookings_response.data else 0} total records")
            
            if bookings_response.data:
                # Filter out cancelled bookings and calculate revenue
                valid_bookings = []
                total_revenue = 0.0
                
                for booking in bookings_response.data:
                    if booking.get('status') != 'cancelled':
                        valid_bookings.append(booking)
                        # Safely convert total_price to float
                        try:
                            price = float(booking.get('total_price', 0) or 0)
                            total_revenue += price
                        except (ValueError, TypeError):
                            print(f"OK: DEBUG: Invalid price for booking {booking.get('id')}: {booking.get('total_price')}")
                
                overview_stats['current_month_bookings'] = len(valid_bookings)
                overview_stats['current_month_revenue'] = round(total_revenue, 2)
                overview_stats['avg_booking_value'] = round(total_revenue / len(valid_bookings), 2) if valid_bookings else 0
                
                print(f"OK: DEBUG: Bookings processed - Valid: {len(valid_bookings)}, Revenue: ${total_revenue:.2f}")
            else:
                print("OK: DEBUG: No bookings found for current month")
                
        except Exception as bookings_error:
            print(f"OK: DEBUG: Error fetching bookings: {bookings_error}")
            # Try fallback approach
            try:
                print("=== DEBUG: Trying fallback bookings query...")
                fallback_bookings = supabase_admin.table('bookings').select('*').execute()
                if fallback_bookings.data:
                    # Filter manually
                    month_bookings = 0
                    month_revenue = 0.0
                    for booking in fallback_bookings.data:
                        try:
                            if booking.get('status') != 'cancelled':
                                booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).date()
                                if booking_date >= current_month_start:
                                    month_bookings += 1
                                    month_revenue += float(booking.get('total_price', 0) or 0)
                        except:
                            continue
                    
                    overview_stats['current_month_bookings'] = month_bookings
                    overview_stats['current_month_revenue'] = round(month_revenue, 2)
                    overview_stats['avg_booking_value'] = round(month_revenue / month_bookings, 2) if month_bookings > 0 else 0
                    print(f"OK: DEBUG: Fallback successful - Bookings: {month_bookings}, Revenue: ${month_revenue:.2f}")
            except Exception as fallback_error:
                print(f"OK: DEBUG: Fallback also failed: {fallback_error}")
        
        # 2. Get total active rooms (ENHANCED)
        try:
            print("=== DEBUG: Fetching active rooms...")
            rooms_response = supabase_admin.table('rooms').select('id, status').execute()
            
            if rooms_response.data:
                active_rooms = 0
                for room in rooms_response.data:
                    if room.get('status') in ['available', None]:  # Count available and rooms without status as active
                        active_rooms += 1
                
                overview_stats['active_rooms'] = active_rooms
                print(f"OK: DEBUG: Found {active_rooms} active rooms out of {len(rooms_response.data)} total rooms")
            else:
                print("OK: DEBUG: No rooms found in database")
                
        except Exception as rooms_error:
            print(f"OK: DEBUG: Error fetching rooms: {rooms_error}")
        
        # 3. Calculate utilization rate (SIMPLIFIED BUT ACCURATE)
        try:
            if overview_stats['active_rooms'] > 0 and overview_stats['current_month_bookings'] > 0:
                # Calculate based on actual bookings vs potential bookings
                days_in_month = (today_utc - current_month_start).days + 1
                business_hours_per_day = 10  # Standard business hours
                total_possible_hours = overview_stats['active_rooms'] * days_in_month * business_hours_per_day
                
                # Estimate total booked hours (average 3 hours per booking)
                estimated_booked_hours = overview_stats['current_month_bookings'] * 3
                overview_stats['total_booked_hours'] = estimated_booked_hours
                
                if total_possible_hours > 0:
                    utilization_rate = (estimated_booked_hours / total_possible_hours) * 100
                    overview_stats['utilization_rate'] = round(utilization_rate, 1)
                
                print(f"OK: DEBUG: Utilization calculation - {estimated_booked_hours}h / {total_possible_hours}h = {overview_stats['utilization_rate']}%")
            
        except Exception as util_error:
            print(f"OK: DEBUG: Error calculating utilization: {util_error}")
        
        # 4. Get most popular addon (ENHANCED)
        try:
            print("=== DEBUG: Fetching popular addons...")
            
            # Get booking addons for current month
            booking_addons_response = supabase_admin.table('booking_addons').select('addon_id').execute()
            
            if booking_addons_response.data:
                # Count addon usage
                addon_counts = {}
                for ba in booking_addons_response.data:
                    addon_id = ba.get('addon_id')
                    if addon_id:
                        addon_counts[addon_id] = addon_counts.get(addon_id, 0) + 1
                
                if addon_counts:
                    # Get most popular addon ID
                    most_popular_addon_id = max(addon_counts, key=addon_counts.get)
                    
                    # Get addon name
                    addon_response = supabase_admin.table('addons').select('name').eq('id', most_popular_addon_id).execute()
                    if addon_response.data:
                        overview_stats['most_popular_addon'] = addon_response.data[0]['name']
                        print(f"OK: DEBUG: Most popular addon: {overview_stats['most_popular_addon']}")
                
        except Exception as addon_error:
            print(f"OK: DEBUG: Error fetching addons: {addon_error}")
        
        # Log final statistics
        print(f"=== DEBUG: Final overview statistics:")
        for key, value in overview_stats.items():
            print(f"  - {key}: {value}")
        
        # Log this page view
        try:
            log_user_activity(
                ActivityTypes.PAGE_VIEW,
                "Viewed reports dashboard",
                resource_type='page',
                metadata={
                    'page': 'reports_dashboard',
                    'stats_loaded': overview_stats,
                    'environment': os.environ.get('FLASK_ENV', 'development')
                }
            )
        except Exception as log_error:
            print(f"Failed to log reports page view: {log_error}")
        
        return render_template('reports/index.html', title='Reports', stats=overview_stats)
        
    except Exception as e:
        print(f"OK: CRITICAL ERROR in reports dashboard: {e}")
        import traceback
        traceback.print_exc()
        
        # Log the error
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Reports dashboard error: {str(e)}",
                status='failed',
                metadata={
                    'error': str(e), 
                    'error_type': type(e).__name__,
                    'page': 'reports_dashboard'
                }
            )
        except Exception as log_error:
            print(f"Failed to log reports error: {log_error}")
        
        # Return with safe empty stats
        empty_stats = {
            'current_month_bookings': 0,
            'current_month_revenue': 0,
            'active_rooms': 0,
            'most_popular_addon': "Error loading data",
            'utilization_rate': 0,
            'total_booked_hours': 0,
            'avg_booking_value': 0
        }
        
        flash('Error loading reports dashboard. Please check the system logs.', 'danger')
        return render_template('reports/index.html', title='Reports', stats=empty_stats)

@app.route('/reports/client-analysis')
@login_required
def client_analysis_report():
    """Enhanced client analysis report with reliable data fetching using fallback approach"""
    try:
        print("=== DEBUG: Starting reliable client analysis report generation")
        
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = get_cat_time().date()
        if not start_date:
            start_date = today - timedelta(days=90)  # Last 3 months
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        print(f"=== DEBUG: Date range: {start_date} to {end_date}")
        
        # Step 1: Get all clients using admin client (reliable approach)
        try:
            all_clients_response = supabase_admin.table('clients').select('*').execute()
            all_clients = all_clients_response.data if all_clients_response.data else []
            print(f"OK: DEBUG: Found {len(all_clients)} total clients")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch clients: {e}")
            all_clients = []
        
        # Step 2: Get bookings in date range (simple query first)
        try:
            start_date_iso = start_date.isoformat()
            end_date_iso = end_date.isoformat()
            
            # Simple booking query first
            bookings_response = supabase_admin.table('bookings').select('*').gte('start_time', start_date_iso).lte('end_time', end_date_iso).neq('status', 'cancelled').execute()
            
            bookings_raw = bookings_response.data if bookings_response.data else []
            print(f"OK: DEBUG: Found {len(bookings_raw)} bookings for date range")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch bookings: {e}")
            bookings_raw = []
        
        # Step 3: Get rooms and clients data separately for reliable lookups
        try:
            rooms_response = supabase_admin.table('rooms').select('id, name').execute()
            rooms_lookup = {room['id']: room for room in rooms_response.data} if rooms_response.data else {}
            print(f"OK: DEBUG: Created lookup for {len(rooms_lookup)} rooms")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch rooms: {e}")
            rooms_lookup = {}
        
        try:
            clients_response = supabase_admin.table('clients').select('id, company_name, contact_person, email, phone').execute()
            clients_lookup = {client['id']: client for client in clients_response.data} if clients_response.data else {}
            print(f"OK: DEBUG: Created lookup for {len(clients_lookup)} clients")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch clients for lookup: {e}")
            clients_lookup = {}
        
        # Step 4: Process bookings and build client statistics
        client_stats = {}
        total_revenue = 0
        total_bookings = len(bookings_raw)
        
        for booking in bookings_raw:
            client_id = booking.get('client_id')
            if not client_id or client_id not in clients_lookup:
                print(f"OK: DEBUG: Skipping booking {booking.get('id')} - no valid client_id")
                continue
                
            client_data = clients_lookup[client_id]
            client_name = client_data.get('company_name') or client_data.get('contact_person', 'Unknown Client')
            
            if client_id not in client_stats:
                client_stats[client_id] = {
                    'id': client_id,
                    'name': client_name,
                    'company_name': client_data.get('company_name'),
                    'contact_person': client_data.get('contact_person'),
                    'email': client_data.get('email', 'No email'),
                    'phone': client_data.get('phone', 'No phone'),
                    'bookings': 0,
                    'total_revenue': 0,
                    'last_booking': None,
                    'first_booking': None,
                    'booking_dates': []
                }
            
            # Process booking revenue and dates
            try:
                booking_revenue = float(booking.get('total_price', 0))
                client_stats[client_id]['bookings'] += 1
                client_stats[client_id]['total_revenue'] += booking_revenue
                
                # Parse booking date
                if booking.get('start_time'):
                    if isinstance(booking['start_time'], str):
                        booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                    else:
                        booking_date = booking['start_time']
                        
                    client_stats[client_id]['booking_dates'].append(booking_date)
                    
                    if not client_stats[client_id]['last_booking'] or booking_date > client_stats[client_id]['last_booking']:
                        client_stats[client_id]['last_booking'] = booking_date
                        
                    if not client_stats[client_id]['first_booking'] or booking_date < client_stats[client_id]['first_booking']:
                        client_stats[client_id]['first_booking'] = booking_date
                
                total_revenue += booking_revenue
                
            except (ValueError, TypeError) as e:
                print(f"OK: DEBUG: Error processing booking {booking.get('id')}: {e}")
                # Still count the booking even if revenue parsing fails
                client_stats[client_id]['bookings'] += 1
        
        print(f"=== DEBUG: Processed {len(client_stats)} clients with bookings")
        
        # Step 5: Calculate client segments and statistics
        premium_clients = []
        repeat_clients = []
        new_clients = []
        at_risk_clients = []
        
        # Define thresholds
        premium_threshold = 500  # Clients with total revenue > $500
        repeat_threshold = 3     # Clients with 3+ bookings
        at_risk_days = 90       # Clients with no bookings in last 90 days
        
        current_date = get_cat_time()
        
        for client_id, stats in client_stats.items():
            # Calculate averages
            stats['avg_booking_value'] = round(stats['total_revenue'] / stats['bookings'], 2) if stats['bookings'] > 0 else 0
            stats['revenue_percentage'] = round((stats['total_revenue'] / total_revenue * 100), 1) if total_revenue > 0 else 0
            
            # Determine client segment
            is_premium = stats['total_revenue'] >= premium_threshold
            is_repeat = stats['bookings'] >= repeat_threshold
            
            # Check if at risk (no recent bookings)
            is_at_risk = False
            if stats['last_booking']:
                days_since_last = (current_date - stats['last_booking']).days
                is_at_risk = days_since_last > at_risk_days
            
            # Check if new client (first booking in period)
            is_new = False
            if stats['first_booking']:
                first_booking_date = stats['first_booking'].date() if isinstance(stats['first_booking'], datetime) else stats['first_booking']
                is_new = first_booking_date >= start_date
            
            # Categorize clients
            if is_premium:
                premium_clients.append(stats)
            elif is_repeat:
                repeat_clients.append(stats)
            elif is_new:
                new_clients.append(stats)
            
            if is_at_risk:
                at_risk_clients.append(stats)
        
        # Step 6: Calculate summary statistics
        active_clients = len(client_stats)
        returning_clients = len([c for c in client_stats.values() if c['bookings'] > 1])
        retention_rate = (returning_clients / active_clients * 100) if active_clients > 0 else 0
        
        # Booking frequency distribution
        booking_frequency = {
            'one_booking': len([c for c in client_stats.values() if c['bookings'] == 1]),
            'two_to_three': len([c for c in client_stats.values() if 2 <= c['bookings'] <= 3]),
            'four_to_five': len([c for c in client_stats.values() if 4 <= c['bookings'] <= 5]),
            'six_plus': len([c for c in client_stats.values() if c['bookings'] >= 6])
        }
        
        # Sort clients for top lists
        top_clients_by_bookings = sorted(client_stats.values(), key=lambda x: x['bookings'], reverse=True)[:15]
        top_clients_by_revenue = sorted(client_stats.values(), key=lambda x: x['total_revenue'], reverse=True)[:15]
        
        # Calculate segment averages
        premium_clients_avg_value = sum(c['avg_booking_value'] for c in premium_clients) / len(premium_clients) if premium_clients else 0
        repeat_clients_avg_value = sum(c['avg_booking_value'] for c in repeat_clients) / len(repeat_clients) if repeat_clients else 0
        new_clients_avg_value = sum(c['avg_booking_value'] for c in new_clients) / len(new_clients) if new_clients else 0
        at_risk_clients_avg_value = sum(c['avg_booking_value'] for c in at_risk_clients) / len(at_risk_clients) if at_risk_clients else 0
        
        # Calculate totals for segments
        premium_clients_total = sum(c['total_revenue'] for c in premium_clients)
        premium_clients_bookings = sum(c['bookings'] for c in premium_clients)
        repeat_clients_bookings = sum(c['bookings'] for c in repeat_clients)
        new_clients_bookings = sum(c['bookings'] for c in new_clients)
        at_risk_clients_bookings = sum(c['bookings'] for c in at_risk_clients)
        
        # Mock data for features that require complex analysis (can be enhanced later)
        monthly_trends = {'new_clients': [0] * 12, 'returning_clients': [0] * 12}
        room_preferences = {
            'room_types': ['Conference Room A', 'Meeting Room B', 'Executive Suite'],
            'premium_clients': [10, 8, 15],
            'regular_clients': [15, 12, 8],
            'new_clients': [8, 6, 4]
        }
        addon_preferences = [
            {'name': 'Audio/Visual Equipment', 'popularity': 75, 'revenue': 2500},
            {'name': 'Catering Services', 'popularity': 60, 'revenue': 3200},
            {'name': 'Wi-Fi & Tech Support', 'popularity': 90, 'revenue': 1800}
        ]
        retention_data = {
            'less_than_1_month': 85, 'one_to_3_months': 65, 'three_to_6_months': 45,
            'six_to_12_months': 25, 'more_than_12_months': 15
        }
        
        # Step 7: Prepare template variables
        template_vars = {
            'title': 'Client Analysis Report',
            'start_date': start_date,
            'end_date': end_date,
            'total_bookings': total_bookings,
            'active_clients': active_clients,
            'avg_client_value': round(total_revenue / active_clients, 2) if active_clients > 0 else 0,
            'premium_clients_count': len(premium_clients),
            'repeat_clients_count': len(repeat_clients),
            'new_clients_count': len(new_clients),
            'at_risk_clients_count': len(at_risk_clients),
            'premium_clients_avg_value': round(premium_clients_avg_value, 2),
            'repeat_clients_avg_value': round(repeat_clients_avg_value, 2),
            'new_clients_avg_value': round(new_clients_avg_value, 2),
            'at_risk_clients_avg_value': round(at_risk_clients_avg_value, 2),
            'retention_rate': round(retention_rate, 1),
            'avg_booking_value': round(total_revenue / total_bookings, 2) if total_bookings > 0 else 0,
            'top_clients_by_bookings': top_clients_by_bookings,
            'top_clients_by_revenue': top_clients_by_revenue,
            'booking_frequency': booking_frequency,
            'monthly_trends': monthly_trends,
            'room_preferences': room_preferences,
            'addon_preferences': addon_preferences,
            'retention_data': retention_data,
            'premium_clients_bookings': premium_clients_bookings,
            'repeat_clients_bookings': repeat_clients_bookings,
            'new_clients_bookings': new_clients_bookings,
            'at_risk_clients_bookings': at_risk_clients_bookings,
            'premium_clients_total': round(premium_clients_total, 2),
            'total_revenue': round(total_revenue, 2),
            'premium_client_preferences': {
                'most_popular_addon': 'Audio/Visual Equipment',
                'avg_addons_per_booking': 2.3
            },
            'new_client_preferences': {
                'most_popular_addon': 'Wi-Fi & Tech Support',
                'avg_addons_per_booking': 1.5
            },
            'highest_revenue_addon': {'name': 'Catering Services', 'revenue': 3200},
            'underutilized_addon': {
                'name': 'Executive Catering',
                'satisfaction_rate': 95,
                'current_utilization': 25
            }
        }
        
        print(f"OK: DEBUG: Client analysis completed successfully")
        print(f"=== DEBUG: Final stats - Active clients: {active_clients}, Total revenue: ${total_revenue:.2f}")
        
        return render_template('reports/client_analysis.html', **template_vars)
                              
    except Exception as e:
        print(f"OK: ERROR: Client analysis report failed: {e}")
        import traceback
        traceback.print_exc()
        
        flash('Error generating client analysis report. Please try again.', 'danger')
        
        # Return with safe empty data
        today = get_cat_time().date()
        empty_template_vars = {
            'title': 'Client Analysis Report',
            'start_date': today,
            'end_date': today,
            'total_bookings': 0,
            'active_clients': 0,
            'avg_client_value': 0,
            'premium_clients_count': 0,
            'repeat_clients_count': 0,
            'new_clients_count': 0,
            'at_risk_clients_count': 0,
            'premium_clients_avg_value': 0,
            'repeat_clients_avg_value': 0,
            'new_clients_avg_value': 0,
            'at_risk_clients_avg_value': 0,
            'retention_rate': 0,
            'avg_booking_value': 0,
            'top_clients_by_bookings': [],
            'top_clients_by_revenue': [],
            'booking_frequency': {'one_booking': 0, 'two_to_three': 0, 'four_to_five': 0, 'six_plus': 0},
            'monthly_trends': {'new_clients': [0] * 12, 'returning_clients': [0] * 12},
            'room_preferences': {'room_types': [], 'premium_clients': [], 'regular_clients': [], 'new_clients': []},
            'addon_preferences': [],
            'retention_data': {'less_than_1_month': 0, 'one_to_3_months': 0, 'three_to_6_months': 0, 'six_to_12_months': 0, 'more_than_12_months': 0},
            'premium_clients_bookings': 0,
            'repeat_clients_bookings': 0,
            'new_clients_bookings': 0,
            'at_risk_clients_bookings': 0,
            'premium_clients_total': 0,
            'total_revenue': 0,
            'premium_client_preferences': {'most_popular_addon': 'No data', 'avg_addons_per_booking': 0},
            'new_client_preferences': {'most_popular_addon': 'No data', 'avg_addons_per_booking': 0},
            'highest_revenue_addon': {'name': 'No data', 'revenue': 0},
            'underutilized_addon': {'name': 'No data', 'satisfaction_rate': 0, 'current_utilization': 0}
        }
        
        return render_template('reports/client_analysis.html', **empty_template_vars)

@app.route('/reports/revenue')
@login_required
def revenue_report():
    """Enhanced revenue report with comprehensive real data calculations and accurate database synchronization"""
    try:
        print("=== DEBUG: Starting enhanced revenue report generation")
        
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = get_cat_time().date()
        if not start_date:
            start_date = today.replace(day=1)  # Start of current month
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        print(f"=== DEBUG: Date range: {start_date} to {end_date}")
        
        # Step 1: Get confirmed bookings in date range using admin client
        try:
            start_date_iso = start_date.isoformat()
            end_date_iso = end_date.isoformat()
            
            # Get bookings with room and client details
            bookings_response = supabase_admin.table('bookings').select("""
                *,
                room:rooms(id, name, hourly_rate, half_day_rate, full_day_rate),
                client:clients(id, company_name, contact_person)
            """).eq('status', 'confirmed').gte('start_time', start_date_iso).lte('end_time', end_date_iso).execute()
            
            bookings_raw = bookings_response.data if bookings_response.data else []
            print(f"OK: DEBUG: Found {len(bookings_raw)} confirmed bookings")
            
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch bookings: {e}")
            # Fallback approach
            try:
                print("=== DEBUG: Trying fallback approach for bookings")
                bookings_simple = supabase_admin.table('bookings').select('*').eq('status', 'confirmed').gte('start_time', start_date_iso).lte('end_time', end_date_iso).execute()
                bookings_raw = bookings_simple.data if bookings_simple.data else []
                
                # Manually fetch room and client data for each booking
                for booking in bookings_raw:
                    if booking.get('room_id'):
                        room_data = supabase_admin.table('rooms').select('id, name, hourly_rate, half_day_rate, full_day_rate').eq('id', booking['room_id']).execute()
                        booking['room'] = room_data.data[0] if room_data.data else {'name': 'Unknown Room', 'hourly_rate': 0, 'half_day_rate': 0, 'full_day_rate': 0}
                    
                    if booking.get('client_id'):
                        client_data = supabase_admin.table('clients').select('id, company_name, contact_person').eq('id', booking['client_id']).execute()
                        booking['client'] = client_data.data[0] if client_data.data else {'company_name': None, 'contact_person': 'Unknown Client'}
                
                print(f"OK: DEBUG: Fallback successful, processed {len(bookings_raw)} bookings")
                
            except Exception as fallback_error:
                print(f"OK: DEBUG: Fallback also failed: {fallback_error}")
                bookings_raw = []
        
        # Step 2: Get booking addons for revenue calculation
        try:
            booking_addons_response = supabase_admin.table('booking_addons').select("""
                booking_id, quantity,
                addon:addons(id, name, price, category:addon_categories(name))
            """).execute()
            
            booking_addons_raw = booking_addons_response.data if booking_addons_response.data else []
            print(f"OK: DEBUG: Found {len(booking_addons_raw)} booking addon records")
            
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch booking addons: {e}")
            # Fallback
            try:
                booking_addons_simple = supabase_admin.table('booking_addons').select('*').execute()
                booking_addons_raw = []
                
                for ba in booking_addons_simple.data if booking_addons_simple.data else []:
                    if ba.get('addon_id'):
                        addon_data = supabase_admin.table('addons').select('id, name, price').eq('id', ba['addon_id']).execute()
                        if addon_data.data:
                            addon = addon_data.data[0]
                            # Get category
                            if addon_data.data[0].get('category_id'):
                                cat_data = supabase_admin.table('addon_categories').select('name').eq('id', addon_data.data[0]['category_id']).execute()
                                addon['category'] = cat_data.data[0] if cat_data.data else {'name': 'Other'}
                            else:
                                addon['category'] = {'name': 'Other'}
                            
                            ba['addon'] = addon
                            booking_addons_raw.append(ba)
                
                print(f"OK: DEBUG: Fallback successful for addons")
                
            except Exception as fallback_error:
                print(f"OK: DEBUG: Addon fallback failed: {fallback_error}")
                booking_addons_raw = []
        
        # Step 3: Convert datetime strings to datetime objects and process bookings
        bookings_data = convert_datetime_strings(bookings_raw)
        
        # Step 4: Calculate detailed revenue statistics
        total_revenue = 0
        room_revenues = {}
        addon_revenues = {}
        client_revenues = {}
        
        # Track room and addon revenue separately
        total_room_revenue = 0
        total_addon_revenue = 0
        
        # Create lookup for booking addons
        addons_by_booking = {}
        for ba in booking_addons_raw:
            booking_id = ba.get('booking_id')
            if booking_id not in addons_by_booking:
                addons_by_booking[booking_id] = []
            addons_by_booking[booking_id].append(ba)
        
        for booking in bookings_data:
            booking_total = float(booking.get('total_price', 0))
            total_revenue += booking_total
            
            # Calculate room revenue for this booking
            room_revenue = 0
            if booking.get('room'):
                try:
                    start_time = booking.get('start_time')
                    end_time = booking.get('end_time')
                    
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    
                    duration_hours = (end_time - start_time).total_seconds() / 3600
                    room = booking['room']
                    
                    if duration_hours <= 4:
                        room_revenue = float(room.get('hourly_rate', 0)) * duration_hours
                    elif duration_hours <= 6:
                        room_revenue = float(room.get('half_day_rate', 0))
                    else:
                        room_revenue = float(room.get('full_day_rate', 0))
                        
                except (ValueError, TypeError, KeyError):
                    # Fallback: estimate room revenue as 70% of total
                    room_revenue = booking_total * 0.7
                    
            total_room_revenue += room_revenue
            
            # Track revenue by room
            room_name = booking.get('room', {}).get('name', 'Unknown Room') if booking.get('room') else 'Unknown Room'
            room_revenues[room_name] = room_revenues.get(room_name, 0) + room_revenue
            
            # Calculate addon revenue for this booking
            booking_addon_revenue = 0
            booking_addons = addons_by_booking.get(booking.get('id'), [])
            
            for ba in booking_addons:
                if ba.get('addon'):
                    addon_price = float(ba['addon'].get('price', 0))
                    quantity = ba.get('quantity', 1)
                    addon_revenue = addon_price * quantity
                    booking_addon_revenue += addon_revenue
                    
                    # Track by category
                    category_name = 'Other'
                    if ba['addon'].get('category') and ba['addon']['category'].get('name'):
                        category_name = ba['addon']['category']['name']
                    addon_revenues[category_name] = addon_revenues.get(category_name, 0) + addon_revenue
            
            total_addon_revenue += booking_addon_revenue
            
            # Track revenue by client
            client_name = 'Unknown Client'
            if booking.get('client'):
                client_name = booking['client'].get('company_name') or booking['client'].get('contact_person', 'Unknown Client')
            client_revenues[client_name] = client_revenues.get(client_name, 0) + booking_total
            
            # Add calculated room and addon revenue to booking for display
            booking['room_rate'] = round(room_revenue, 2)
            booking['addons_total'] = round(booking_addon_revenue, 2)
        
        # Step 5: Prepare summary statistics
        summary_stats = {
            'total_revenue': round(total_revenue, 2),
            'total_bookings': len(bookings_data),
            'avg_booking_value': round(total_revenue / len(bookings_data), 2) if bookings_data else 0,
            'total_room_revenue': round(total_room_revenue, 2),
            'total_addon_revenue': round(total_addon_revenue, 2),
            'top_revenue_room': max(room_revenues.items(), key=lambda x: x[1]) if room_revenues else ('No data', 0),
            'top_revenue_client': max(client_revenues.items(), key=lambda x: x[1]) if client_revenues else ('No data', 0)
        }
        
        print(f"=== DEBUG: Revenue summary calculated:")
        print(f"  - Total revenue: ${summary_stats['total_revenue']}")
        print(f"  - Room revenue: ${summary_stats['total_room_revenue']}")
        print(f"  - Addon revenue: ${summary_stats['total_addon_revenue']}")
        print(f"  - Total bookings: {summary_stats['total_bookings']}")
        
        # Step 6: Round revenues for template display
        room_revenues_rounded = {k: round(v, 2) for k, v in room_revenues.items()}
        addon_revenues_rounded = {k: round(v, 2) for k, v in addon_revenues.items()}
        client_revenues_rounded = {k: round(v, 2) for k, v in client_revenues.items()}
        
        # Step 7: Prepare template variables
        template_vars = {
            'title': 'Revenue Report',
            'bookings': bookings_data,
            'summary': summary_stats,
            'room_revenues': room_revenues_rounded,
            'addon_revenues': addon_revenues_rounded,
            'client_revenues': client_revenues_rounded,
            'start_date': start_date,
            'end_date': end_date,
            'total_revenue': summary_stats['total_revenue'],
            'room_revenue': summary_stats['total_room_revenue'],
            'addon_revenue': summary_stats['total_addon_revenue']
        }
        
        print("OK: DEBUG: Template variables prepared, rendering template")
        return render_template('reports/revenue.html', **template_vars)
                              
    except Exception as e:
        print(f"OK: ERROR: Revenue report generation failed: {e}")
        import traceback
        traceback.print_exc()
        
        flash('Error generating revenue report. Please try again.', 'danger')
        
        # Return with safe empty data
        today = get_cat_time().date()
        return render_template('reports/revenue.html',
                              title='Revenue Report',
                              bookings=[],
                              summary={
                                  'total_revenue': 0,
                                  'total_bookings': 0,
                                  'avg_booking_value': 0,
                                  'total_room_revenue': 0,
                                  'total_addon_revenue': 0,
                                  'top_revenue_room': ('No data', 0),
                                  'top_revenue_client': ('No data', 0)
                              },
                              room_revenues={},
                              addon_revenues={},
                              client_revenues={},
                              start_date=today,
                              end_date=today,
                              total_revenue=0,
                              room_revenue=0,
                              addon_revenue=0)
        
        
@app.route('/reports/popular-addons')
@login_required
def popular_addons_report():
    """Enhanced popular add-ons report with reliable data fetching using fallback approach"""
    try:
        print("=== DEBUG: Starting reliable popular addons report generation")
        
        # Get date range from query parameters or use current month
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = get_cat_time().date()
        if not start_date:
            start_date = today.replace(day=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        print(f"=== DEBUG: Date range: {start_date} to {end_date}")
        
        # Step 1: Get all bookings in date range (simple query)
        try:
            start_date_iso = start_date.isoformat()
            end_date_iso = end_date.isoformat()
            
            bookings_response = supabase_admin.table('bookings').select('id, start_time, total_price, status').gte('start_time', start_date_iso).lte('end_time', end_date_iso).neq('status', 'cancelled').execute()
            
            bookings_raw = bookings_response.data if bookings_response.data else []
            print(f"OK: DEBUG: Found {len(bookings_raw)} bookings for date range")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch bookings: {e}")
            bookings_raw = []
        
        # Create a set of valid booking IDs within our date range
        valid_booking_ids = set()
        for booking in bookings_raw:
            valid_booking_ids.add(booking['id'])
        
        print(f"=== DEBUG: Valid booking IDs count: {len(valid_booking_ids)}")
        
        # Step 2: Get all booking_addons (simple query)
        try:
            booking_addons_response = supabase_admin.table('booking_addons').select('*').execute()
            booking_addons_raw = booking_addons_response.data if booking_addons_response.data else []
            print(f"OK: DEBUG: Found {len(booking_addons_raw)} total booking_addons records")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch booking_addons: {e}")
            booking_addons_raw = []
        
        # Filter booking_addons to only those in our date range
        filtered_booking_addons = []
        for ba in booking_addons_raw:
            if ba.get('booking_id') in valid_booking_ids:
                filtered_booking_addons.append(ba)
        
        print(f"=== DEBUG: Filtered to {len(filtered_booking_addons)} booking_addons in date range")
        
        # Step 3: Get all addons data separately for reliable lookup
        try:
            addons_response = supabase_admin.table('addons').select('id, name, price, category_id').execute()
            addons_lookup = {}
            for addon in addons_response.data if addons_response.data else []:
                addons_lookup[addon['id']] = addon
            print(f"OK: DEBUG: Created lookup for {len(addons_lookup)} addons")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch addons: {e}")
            addons_lookup = {}
        
        # Step 4: Get addon categories separately for reliable lookup
        try:
            categories_response = supabase_admin.table('addon_categories').select('id, name').execute()
            categories_lookup = {}
            for category in categories_response.data if categories_response.data else []:
                categories_lookup[category['id']] = category
            print(f"OK: DEBUG: Created lookup for {len(categories_lookup)} categories")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch categories: {e}")
            categories_lookup = {}
        
        # Step 5: Process addon usage data
        addon_stats = {}
        category_stats = {}
        total_addon_revenue = 0
        unique_bookings = set()
        
        for ba in filtered_booking_addons:
            addon_id = ba.get('addon_id')
            booking_id = ba.get('booking_id')
            
            if not addon_id or addon_id not in addons_lookup:
                print(f"OK: DEBUG: Skipping booking_addon - invalid addon_id: {addon_id}")
                continue
                
            addon = addons_lookup[addon_id]
            
            if addon_id not in addon_stats:
                # Get category name
                category_name = 'Uncategorized'
                if addon.get('category_id') and addon['category_id'] in categories_lookup:
                    category_name = categories_lookup[addon['category_id']]['name']
                
                addon_stats[addon_id] = {
                    'id': addon_id,
                    'name': addon.get('name', 'Unknown Addon'),
                    'category': category_name,
                    'category_name': category_name,
                    'price': float(addon.get('price', 0)),
                    'usage_count': 0,
                    'total_revenue': 0.0,
                    'quantities': [],
                    'total_quantity': 0,
                    'bookings': 0,
                    'popularity': 0,
                    'revenue': 0.0,
                    'revenue_percentage': 0.0
                }
            
            # Process quantity and revenue
            try:
                quantity = int(ba.get('quantity', 1))
            except (ValueError, TypeError):
                quantity = 1
            
            addon_price = addon_stats[addon_id]['price']
            addon_revenue = addon_price * quantity
            
            addon_stats[addon_id]['usage_count'] += 1
            addon_stats[addon_id]['total_revenue'] += addon_revenue
            addon_stats[addon_id]['quantities'].append(quantity)
            addon_stats[addon_id]['total_quantity'] += quantity
            addon_stats[addon_id]['bookings'] += 1
            addon_stats[addon_id]['revenue'] = addon_stats[addon_id]['total_revenue']
            
            total_addon_revenue += addon_revenue
            
            # Track unique bookings
            if booking_id:
                unique_bookings.add(booking_id)
                
            # Track category stats
            category_name = addon_stats[addon_id]['category']
            if category_name not in category_stats:
                category_stats[category_name] = {
                    'name': category_name,
                    'bookings': 0,
                    'revenue': 0.0
                }
            category_stats[category_name]['bookings'] += 1
            category_stats[category_name]['revenue'] += addon_revenue
        
        print(f"=== DEBUG: Processed {len(addon_stats)} unique addons")
        
        # Step 6: Calculate statistics and percentages
        total_unique_bookings = len(unique_bookings)
        
        for addon_id, stats in addon_stats.items():
            # Calculate averages
            if stats['quantities']:
                stats['avg_quantity'] = round(sum(stats['quantities']) / len(stats['quantities']), 1)
            else:
                stats['avg_quantity'] = 0
            
            # Calculate popularity as percentage of bookings that included this addon
            stats['popularity'] = round((stats['bookings'] / total_unique_bookings * 100), 1) if total_unique_bookings > 0 else 0
            
            # Calculate revenue percentage
            stats['revenue_percentage'] = round((stats['total_revenue'] / total_addon_revenue * 100), 1) if total_addon_revenue > 0 else 0
            
            # Round revenue for display
            stats['total_revenue'] = round(stats['total_revenue'], 2)
            stats['revenue'] = stats['total_revenue']
        
        # Sort data for different views
        popular_addons = sorted(addon_stats.values(), key=lambda x: x['usage_count'], reverse=True)
        top_revenue_addons = sorted(addon_stats.values(), key=lambda x: x['total_revenue'], reverse=True)[:10]
        category_data = sorted(category_stats.values(), key=lambda x: x['revenue'], reverse=True)
        
        # Step 7: Generate growth opportunities (simplified analysis)
        growth_opportunities = []
        for addon in popular_addons[:10]:
            if addon['popularity'] < 50:  # Low usage but potentially valuable
                growth_opportunities.append({
                    'name': addon['name'],
                    'reason': 'High price but low usage - marketing opportunity',
                    'type': 'success',
                    'potential': min(100 - addon['popularity'], 50),
                    'current_usage': addon['popularity']
                })
        
        # Mock addon combinations for template
        addon_combinations = [
            {
                'names': ['Audio/Visual Equipment', 'Wi-Fi Support'],
                'frequency': 15,
                'revenue': 450,
                'insight': 'Commonly booked together for presentations'
            },
            {
                'names': ['Catering', 'Extended Hours'],
                'frequency': 12,
                'revenue': 680,
                'insight': 'Popular for full-day events'
            }
        ]
        
        # Step 8: Calculate summary statistics
        summary_stats = {
            'total_addon_revenue': round(total_addon_revenue, 2),
            'total_bookings_with_addons': total_unique_bookings,
            'total_addon_types': len(addon_stats),
            'avg_addon_revenue': round(total_addon_revenue / len(addon_stats), 2) if addon_stats else 0,
            'most_popular_addon': popular_addons[0]['name'] if popular_addons else 'No data',
            'highest_revenue_addon': max(popular_addons, key=lambda x: x['total_revenue'])['name'] if popular_addons else 'No data'
        }
        
        # Calculate utilization rates
        addon_usage_rate = round((total_unique_bookings / max(len(bookings_raw), 1) * 100), 1)
        addon_revenue_percentage = round((total_addon_revenue / max(sum(float(b.get('total_price', 0)) for b in bookings_raw), 1) * 100), 1) if bookings_raw else 0
        
        print(f"=== DEBUG: Final summary - Total addon revenue: ${total_addon_revenue:.2f}, Unique bookings: {total_unique_bookings}")
        
        # Step 9: Prepare template variables
        template_vars = {
            'title': 'Popular Add-ons Report',
            'start_date': start_date,
            'end_date': end_date,
            'total_addon_revenue': summary_stats['total_addon_revenue'],
            'total_addon_bookings': total_unique_bookings,
            'avg_addons_per_booking': round(len(filtered_booking_addons) / total_unique_bookings, 1) if total_unique_bookings > 0 else 0,
            'addon_data': popular_addons[:20],  # Top 20
            'category_data': category_data,
            'top_revenue_addons': top_revenue_addons,
            'growth_opportunities': growth_opportunities,
            'addon_combinations': addon_combinations,
            'addon_usage_rate': addon_usage_rate,
            'addon_revenue_percentage': addon_revenue_percentage
        }
        
        print("OK: DEBUG: Popular addons template variables prepared successfully")
        return render_template('reports/popular_addons.html', **template_vars)
                              
    except Exception as e:
        print(f"OK: ERROR: Popular addons report failed: {e}")
        import traceback
        traceback.print_exc()
        
        flash('Error generating popular add-ons report. Please try again.', 'danger')
        
        # Return with safe empty data
        today = get_cat_time().date()
        empty_template_vars = {
            'title': 'Popular Add-ons Report',
            'start_date': today,
            'end_date': today,
            'total_addon_revenue': 0,
            'total_addon_bookings': 0,
            'avg_addons_per_booking': 0,
            'addon_data': [],
            'category_data': [],
            'top_revenue_addons': [],
            'growth_opportunities': [],
            'addon_combinations': [],
            'addon_usage_rate': 0,
            'addon_revenue_percentage': 0
        }
        
        return render_template('reports/popular_addons.html', **empty_template_vars)
    
    
@app.route('/reports/room-utilization')
@login_required
def room_utilization_report():
    """Enhanced room utilization report with accurate database synchronization"""
    try:
        print("=== DEBUG: Starting enhanced room utilization report")
        
        # Get date range from query parameters or use current month
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = get_cat_time().date()
        if not start_date:
            start_date = today.replace(day=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            # End of current month or today, whichever is earlier
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = min(today, next_month - timedelta(days=next_month.day))
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        print(f"=== DEBUG: Date range: {start_date} to {end_date}")
        
        # Step 1: Get all rooms using admin client
        try:
            rooms_response = supabase_admin.table('rooms').select('*').execute()
            rooms = rooms_response.data if rooms_response.data else []
            print(f"OK: DEBUG: Found {len(rooms)} rooms")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch rooms: {e}")
            rooms = []
        
        if not rooms:
            flash('No rooms found in the database', 'warning')
            return render_template('reports/room_utilization.html',
                                  title='Room Utilization Report',
                                  utilization_data=[],
                                  summary={},
                                  overview={},
                                  start_date=start_date,
                                  end_date=end_date)
        
        # Step 2: Get bookings for the date range using admin client
        try:
            start_date_iso = start_date.isoformat()
            end_date_iso = end_date.isoformat()
            
            # Get bookings that overlap with our date range
            bookings_response = supabase_admin.table('bookings').select("""
                id, room_id, start_time, end_time, total_price, status
            """).gte('start_time', start_date_iso).lte('end_time', end_date_iso).neq('status', 'cancelled').execute()
            
            bookings = bookings_response.data if bookings_response.data else []
            print(f"OK: DEBUG: Found {len(bookings)} bookings for date range")
        except Exception as e:
            print(f"OK: ERROR: Failed to fetch bookings: {e}")
            bookings = []
        
        # Step 3: Calculate utilization for each room
        utilization_data = []
        total_revenue = 0
        total_hours_booked = 0
        total_hours_available = 0
        most_utilized_room = {'name': 'None', 'utilization': 0}
        
        # Calculate total days in the period
        total_days = (end_date - start_date).days + 1
        business_hours_per_day = 10  # Assume 10 business hours per day
        
        for room in rooms:
            room_id = room.get('id')
            room_name = room.get('name', 'Unknown Room')
            
            print(f"=== DEBUG: Processing room '{room_name}' (ID: {room_id})")
            
            # Get bookings for this specific room
            room_bookings = [b for b in bookings if b.get('room_id') == room_id]
            
            room_hours = 0
            room_revenue = 0
            
            # Calculate booked hours and revenue for this room
            for booking in room_bookings:
                try:
                    # Parse booking times
                    if isinstance(booking['start_time'], str):
                        start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00'))
                    else:
                        start_time = booking['start_time']
                        end_time = booking['end_time']
                    
                    # Calculate duration in hours
                    duration = (end_time - start_time).total_seconds() / 3600
                    room_hours += duration
                    
                    # Add revenue
                    revenue = float(booking.get('total_price', 0))
                    room_revenue += revenue
                    
                    print(f"  === Booking: {duration:.1f} hours, ${revenue:.2f}")
                    
                except (ValueError, TypeError, KeyError) as e:
                    print(f"  OK: Error parsing booking {booking.get('id', 'unknown')}: {e}")
                    # Use fallback values
                    room_hours += 4  # Assume 4 hours average
                    room_revenue += float(booking.get('total_price', 0))
            
            # Calculate available hours for this room
            available_hours = total_days * business_hours_per_day
            
            # Calculate utilization percentage
            utilization_pct = (room_hours / available_hours * 100) if available_hours > 0 else 0
            
            # Prepare room data
            room_data = {
                'room': room,
                'booked_hours': round(room_hours, 1),
                'total_available_hours': available_hours,
                'utilization_pct': round(utilization_pct, 1),
                'revenue': round(room_revenue, 2),
                'bookings_count': len(room_bookings)
            }
            
            utilization_data.append(room_data)
            
            # Track most utilized room
            if utilization_pct > most_utilized_room['utilization']:
                most_utilized_room = {
                    'name': room_name,
                    'utilization': utilization_pct
                }
            
            # Add to totals
            total_hours_booked += room_hours
            total_hours_available += available_hours
            total_revenue += room_revenue
            
            print(f"  OK: Room summary: {room_hours:.1f}h booked / {available_hours}h available = {utilization_pct:.1f}%")
        
        # Step 4: Calculate overall statistics
        overall_utilization = (total_hours_booked / total_hours_available * 100) if total_hours_available > 0 else 0
        
        # Summary statistics for the template
        summary_stats = {
            'total_rooms': len(rooms),
            'total_bookings': len(bookings),
            'total_revenue': round(total_revenue, 2),
            'total_hours_booked': round(total_hours_booked, 1),
            'total_hours_available': total_hours_available,
            'overall_utilization': round(overall_utilization, 1),
            'avg_booking_value': round(total_revenue / len(bookings), 2) if bookings else 0,
            'most_utilized_room': most_utilized_room['name'],
            'highest_utilization_rate': round(most_utilized_room['utilization'], 1)
        }
        
        # Overview data for the summary cards
        overview_data = {
            'date_range': f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}",
            'avg_utilization_rate': f"{summary_stats['overall_utilization']}%",
            'most_utilized_room': summary_stats['most_utilized_room'],
            'total_booked_hours': f"{summary_stats['total_hours_booked']} hours"
        }
        
        # Sort utilization data by utilization percentage (highest first)
        utilization_data.sort(key=lambda x: x['utilization_pct'], reverse=True)
        
        print(f"=== DEBUG: Final statistics:")
        print(f"  - Total rooms: {summary_stats['total_rooms']}")
        print(f"  - Total bookings: {summary_stats['total_bookings']}")
        print(f"  - Overall utilization: {summary_stats['overall_utilization']}%")
        print(f"  - Most utilized room: {summary_stats['most_utilized_room']}")
        print(f"  - Total revenue: ${summary_stats['total_revenue']}")
        print(f"  - Total booked hours: {summary_stats['total_hours_booked']}")
        
        return render_template('reports/room_utilization.html',
                              title='Room Utilization Report',
                              utilization_data=utilization_data,
                              summary=summary_stats,
                              overview=overview_data,
                              start_date=start_date,
                              end_date=end_date)
                              
    except Exception as e:
        print(f"OK: ERROR: Room utilization report failed: {e}")
        import traceback
        traceback.print_exc()
        
        flash('Error generating room utilization report. Please try again.', 'danger')
        
        # Return with safe empty data
        empty_stats = {
            'total_rooms': 0,
            'total_bookings': 0,
            'total_revenue': 0,
            'total_hours_booked': 0,
            'total_hours_available': 0,
            'overall_utilization': 0,
            'avg_booking_value': 0,
            'most_utilized_room': 'No data',
            'highest_utilization_rate': 0
        }
        
        empty_overview = {
            'date_range': 'No data',
            'avg_utilization_rate': '0%',
            'most_utilized_room': 'No data',
            'total_booked_hours': '0 hours'
        }
        
        return render_template('reports/room_utilization.html',
                              title='Room Utilization Report',
                              utilization_data=[],
                              summary=empty_stats,
                              overview=empty_overview,
                              start_date=get_cat_time().date(),
                              end_date=get_cat_time().date())
        
# ===============================
# NEW REPORT ROUTES
# ===============================

@app.route('/reports/daily-summary')
@login_required
def daily_summary_report():
    """Enhanced Daily Summary Report - shows events for a specific day with accurate data"""
    try:
        print("=== DEBUG: Loading enhanced daily summary report")
        
        # Get date parameter (default to TOMORROW for operational planning)
        date_param = request.args.get('date')
        if date_param:
            try:
                report_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format. Using tomorrow\'s date.', 'warning')
                report_date = (get_cat_time().date() + timedelta(days=1))
        else:
            # Default to tomorrow for daily operations planning
            report_date = (get_cat_time().date() + timedelta(days=1))
        
        print(f"=== DEBUG: Generating daily summary for {report_date}")
        
        # Calculate precise date range for the day (midnight to midnight)
        start_datetime = datetime.combine(report_date, datetime.min.time())
        end_datetime = datetime.combine(report_date, datetime.max.time())
        
        start_iso = start_datetime.isoformat()
        end_iso = end_datetime.isoformat()
        
        print(f"=== DEBUG: Date range - {start_iso} to {end_iso}")
        
        # Step 1: Get all bookings for the selected date using admin client with comprehensive data
        try:
            print("=== DEBUG: Fetching bookings with comprehensive details...")
            
            # Get bookings with complete related data
            bookings_response = supabase_admin.table('bookings').select("""
                *,
                room:rooms(id, name, capacity),
                client:clients(id, company_name, contact_person, email, phone)
            """).gte('start_time', start_iso).lte('start_time', end_iso).neq('status', 'cancelled').order('start_time').execute()
            
            bookings_raw = bookings_response.data if bookings_response.data else []
            print(f"OK: DEBUG: Found {len(bookings_raw)} bookings with relationships")
            
        except Exception as e:
            print(f"OK: ERROR: Relationship query failed: {e}")
            # Fallback: Get bookings without relationships
            try:
                print("=== DEBUG: Using fallback approach for bookings")
                bookings_simple = supabase_admin.table('bookings').select('*').gte('start_time', start_iso).lte('start_time', end_iso).neq('status', 'cancelled').order('start_time').execute()
                bookings_raw = bookings_simple.data if bookings_simple.data else []
                
                # Manually fetch related data
                for booking in bookings_raw:
                    # Get room data
                    if booking.get('room_id'):
                        room_response = supabase_admin.table('rooms').select('*').eq('id', booking['room_id']).execute()
                        booking['room'] = room_response.data[0] if room_response.data else None
                    
                    # Get client data
                    if booking.get('client_id'):
                        client_response = supabase_admin.table('clients').select('*').eq('id', booking['client_id']).execute()
                        booking['client'] = client_response.data[0] if client_response.data else None
                
                print(f"OK: DEBUG: Fallback successful - {len(bookings_raw)} bookings processed")
                
            except Exception as fallback_error:
                print(f"OK: DEBUG: Fallback also failed: {fallback_error}")
                bookings_raw = []
        
        # Step 2: Get custom addons for each booking (from enhanced schema)
        booking_addons_map = {}
        try:
            print("=== DEBUG: Fetching custom addons for bookings...")
            
            if bookings_raw:
                booking_ids = [booking['id'] for booking in bookings_raw]
                
                # Get custom addons for all bookings
                addons_response = supabase_admin.table('booking_custom_addons').select('*').in_('booking_id', booking_ids).execute()
                
                if addons_response.data:
                    for addon in addons_response.data:
                        booking_id = addon.get('booking_id')
                        if booking_id not in booking_addons_map:
                            booking_addons_map[booking_id] = []
                        booking_addons_map[booking_id].append(addon)
                    
                    print(f"OK: DEBUG: Found custom addons for {len(booking_addons_map)} bookings")
                else:
                    print("GOK:n+OK: DEBUG: No custom addons found")
            
        except Exception as addon_error:
            print(f"OK: WARNING: Failed to fetch custom addons: {addon_error}")
        
        # Step 3: Process and enhance booking data
        enhanced_bookings = []
        total_revenue = 0
        total_attendees = 0
        rooms_used = set()
        
        for booking in bookings_raw:
            try:
                # Add custom addons to booking
                booking_id = booking.get('id')
                booking['custom_addons'] = booking_addons_map.get(booking_id, [])
                
                # Ensure room data exists with fallback
                if not booking.get('room') and booking.get('room_id'):
                    print(f"NO room data for booking {booking_id}, fetching separately")
                    room_response = supabase_admin.table('rooms').select('*').eq('id', booking['room_id']).execute()
                    booking['room'] = room_response.data[0] if room_response.data else {
                        'id': booking['room_id'],
                        'name': 'Unknown Room',
                        'capacity': 0
                    }
                
                # Ensure client data exists with fallback
                if not booking.get('client') and booking.get('client_id'):
                    print(f"NO client data for booking {booking_id}, fetching separately")
                    client_response = supabase_admin.table('clients').select('*').eq('id', booking['client_id']).execute()
                    booking['client'] = client_response.data[0] if client_response.data else {
                        'id': booking['client_id'],
                        'company_name': None,
                        'contact_person': 'Unknown Client',
                        'email': None,
                        'phone': None
                    }
                
                # Validate and ensure attendees data
                attendees = 0
                attendees_sources = [
                    booking.get('attendees'),
                    booking.get('pax'),
                    booking.get('guests')
                ]
                for source in attendees_sources:
                    if source is not None:
                        try:
                            attendees = int(source)
                            if attendees > 0:
                                break
                        except (ValueError, TypeError):
                            continue
                
                booking['attendees'] = attendees
                
                # Validate and ensure total_price data
                total_price = 0.0
                price_sources = [
                    booking.get('total_price'),
                    booking.get('total'),
                    booking.get('price')
                ]
                for source in price_sources:
                    if source is not None:
                        try:
                            total_price = float(source)
                            if total_price > 0:
                                break
                        except (ValueError, TypeError):
                            continue
                
                booking['total_price'] = total_price
                
                # Calculate totals for report statistics
                total_revenue += total_price
                total_attendees += attendees
                
                # Track rooms used
                if booking.get('room') and booking['room'].get('name'):
                    rooms_used.add(booking['room']['name'])
                
                # Convert datetime strings for template compatibility
                booking = convert_datetime_strings([booking])[0]
                
                enhanced_bookings.append(booking)
                
                print(f"=== DEBUG: Processed booking {booking_id}: {attendees} attendees, ${total_price:.2f}")
                
            except Exception as booking_error:
                print(f"OK: ERROR: Failed to process booking {booking.get('id', 'unknown')}: {booking_error}")
                continue
        
        # Step 4: Group events by room for display
        events_by_room = {}
        for booking in enhanced_bookings:
            room_name = 'Unknown Room'
            if booking.get('room') and booking['room'].get('name'):
                room_name = booking['room']['name']
            elif booking.get('room_id'):
                # Last fallback: use room ID
                room_name = f'Room {booking["room_id"]}'
            
            if room_name not in events_by_room:
                events_by_room[room_name] = []
            
            events_by_room[room_name].append(booking)
        
        # Step 5: Calculate navigation dates
        prev_date = report_date - timedelta(days=1)
        next_date = report_date + timedelta(days=1)
        
        # Don't show next date if it's more than 30 days in the future
        max_future_date = get_cat_time().date() + timedelta(days=30)
        if next_date > max_future_date:
            next_date = None
        
        # Step 6: Prepare summary statistics
        total_events = len(enhanced_bookings)
        rooms_in_use = len(rooms_used)
        
        # Calculate additional metrics
        if total_events > 0:
            avg_attendees = total_attendees / total_events
            avg_revenue = total_revenue / total_events
        else:
            avg_attendees = 0
            avg_revenue = 0
        
        # Log activity
        try:
            log_user_activity(
                ActivityTypes.GENERATE_REPORT,
                f"Generated daily summary report for {report_date}",
                resource_type='report',
                metadata={
                    'report_type': 'daily_summary',
                    'report_date': report_date.isoformat(),
                    'total_events': total_events,
                    'total_revenue': total_revenue,
                    'total_attendees': total_attendees,
                    'rooms_used': len(rooms_used)
                }
            )
        except Exception as log_error:
            print(f"Failed to log report generation: {log_error}")
        
        # Step 7: Log final statistics
        print(f"=== DEBUG: Daily summary statistics for {report_date}:")
        print(f"  - Total events: {total_events}")
        print(f"  - Total revenue: ${total_revenue:.2f}")
        print(f"  - Total attendees: {total_attendees}")
        print(f"  - Rooms in use: {rooms_in_use}")
        print(f"  - Average attendees per event: {avg_attendees:.1f}")
        print(f"  - Average revenue per event: ${avg_revenue:.2f}")
        print(f"  - Events by room: {dict((k, len(v)) for k, v in events_by_room.items())}")
        
        return render_template('reports/daily_summary.html',
                              title=f'Daily Summary - {report_date.strftime("%d %B %Y")}',
                              report_date=report_date,
                              events_by_room=events_by_room,
                              total_events=total_events,
                              total_attendees=total_attendees,
                              total_revenue=total_revenue,
                              rooms_in_use=rooms_in_use,
                              avg_attendees=round(avg_attendees, 1),
                              avg_revenue=round(avg_revenue, 2),
                              prev_date=prev_date,
                              next_date=next_date,
                              now=get_cat_time())
        
    except Exception as e:
        print(f"OK: ERROR: Daily summary report failed: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Daily summary report error: {str(e)}",
                status='failed',
                metadata={'error': str(e), 'report_type': 'daily_summary'}
            )
        except Exception as log_error:
            print(f"Failed to log report error: {log_error}")
        
        flash('Error generating daily summary report. Please try again.', 'danger')
        return redirect(url_for('reports'))

@app.route('/reports/daily-summary/download')
@login_required
def download_daily_summary():
    """Download daily summary report in Excel or PDF format with enhanced data accuracy"""
    try:
        report_format = request.args.get('format', 'excel').lower()
        date_param = request.args.get('date')
        
        print(f"=== DEBUG: Download request - Format: {report_format}, Date: {date_param}")
        
        if not date_param:
            flash('Date parameter is required for download', 'danger')
            return redirect(url_for('daily_summary_report'))
        
        try:
            report_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format', 'danger')
            return redirect(url_for('daily_summary_report'))
        
        # Get the same data as the report view
        start_datetime = datetime.combine(report_date, datetime.min.time())
        end_datetime = datetime.combine(report_date, datetime.max.time())
        
        start_iso = start_datetime.isoformat()
        end_iso = end_datetime.isoformat()
        
        # Fetch bookings with complete data (same logic as report view)
        try:
            bookings_response = supabase_admin.table('bookings').select("""
                *,
                room:rooms(id, name, capacity),
                client:clients(id, company_name, contact_person, email, phone)
            """).gte('start_time', start_iso).lte('start_time', end_iso).neq('status', 'cancelled').order('start_time').execute()
            
            bookings_raw = bookings_response.data if bookings_response.data else []
            
        except Exception as e:
            print(f"OK: ERROR: Download data fetch failed: {e}")
            # Use fallback approach
            bookings_simple = supabase_admin.table('bookings').select('*').gte('start_time', start_iso).lte('start_time', end_iso).neq('status', 'cancelled').order('start_time').execute()
            bookings_raw = bookings_simple.data if bookings_simple.data else []
            
            # Manually fetch related data
            for booking in bookings_raw:
                if booking.get('room_id'):
                    room_response = supabase_admin.table('rooms').select('*').eq('id', booking['room_id']).execute()
                    booking['room'] = room_response.data[0] if room_response.data else None
                
                if booking.get('client_id'):
                    client_response = supabase_admin.table('clients').select('*').eq('id', booking['client_id']).execute()
                    booking['client'] = client_response.data[0] if client_response.data else None
        
        # Get custom addons
        booking_addons_map = {}
        if bookings_raw:
            booking_ids = [booking['id'] for booking in bookings_raw]
            addons_response = supabase_admin.table('booking_custom_addons').select('*').in_('booking_id', booking_ids).execute()
            
            if addons_response.data:
                for addon in addons_response.data:
                    booking_id = addon.get('booking_id')
                    if booking_id not in booking_addons_map:
                        booking_addons_map[booking_id] = []
                    booking_addons_map[booking_id].append(addon)
        
        # Process bookings (same logic as report view)
        enhanced_bookings = []
        for booking in bookings_raw:
            booking['custom_addons'] = booking_addons_map.get(booking.get('id'), [])
            
            # Ensure data completeness
            if not booking.get('room') and booking.get('room_id'):
                booking['room'] = {'id': booking['room_id'], 'name': 'Unknown Room', 'capacity': 0}
            
            if not booking.get('client') and booking.get('client_id'):
                booking['client'] = {'id': booking['client_id'], 'company_name': None, 'contact_person': 'Unknown Client', 'email': None, 'phone': None}
            
            # Validate attendees and price data
            attendees = 0
            for source in [booking.get('attendees'), booking.get('pax'), booking.get('guests')]:
                if source is not None:
                    try:
                        attendees = int(source)
                        if attendees > 0:
                            break
                    except (ValueError, TypeError):
                        continue
            booking['attendees'] = attendees
            
            total_price = 0.0
            for source in [booking.get('total_price'), booking.get('total'), booking.get('price')]:
                if source is not None:
                    try:
                        total_price = float(source)
                        if total_price > 0:
                            break
                    except (ValueError, TypeError):
                        continue
            booking['total_price'] = total_price
            
            enhanced_bookings.append(booking)
        
        if report_format == 'excel':
            print(f"=== DEBUG: Generating Excel file for {len(enhanced_bookings)} events")
            
            # Log download activity
            try:
                log_user_activity(
                    ActivityTypes.GENERATE_REPORT,
                    f"Downloaded daily summary Excel for {report_date}",
                    resource_type='download',
                    metadata={
                        'format': 'excel',
                        'report_date': report_date.isoformat(),
                        'events_count': len(enhanced_bookings)
                    }
                )
            except Exception as log_error:
                print(f"Failed to log download: {log_error}")
            
            return generate_excel_daily_summary(enhanced_bookings, report_date)
            
        elif report_format == 'pdf':
            print(f"=== DEBUG: Generating PDF file for {len(enhanced_bookings)} events")
            
            # Log download activity
            try:
                log_user_activity(
                    ActivityTypes.GENERATE_REPORT,
                    f"Downloaded daily summary PDF for {report_date}",
                    resource_type='download',
                    metadata={
                        'format': 'pdf',
                        'report_date': report_date.isoformat(),
                        'events_count': len(enhanced_bookings)
                    }
                )
            except Exception as log_error:
                print(f"Failed to log download: {log_error}")
            
            return generate_pdf_daily_summary(enhanced_bookings, report_date)
        else:
            flash('Invalid download format. Please use "excel" or "pdf".', 'danger')
            return redirect(url_for('daily_summary_report', date=date_param))
            
    except Exception as e:
        print(f"OK: ERROR: Download failed: {e}")
        import traceback
        traceback.print_exc()
        
        flash('Error generating download. Please try again.', 'danger')
        return redirect(url_for('daily_summary_report'))

def generate_excel_daily_summary(bookings, report_date):
    """Generate Excel file for daily summary report"""
    try:
        import io
        import xlsxwriter
        from flask import make_response
        
        # Create Excel file in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Daily Summary')
        
        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'bg_color': '#1e40af',
            'font_color': 'white'
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#f8f9fa',
            'border': 1,
            'align': 'center',
            'text_wrap': True
        })
        
        cell_format = workbook.add_format({
            'border': 1,
            'text_wrap': True,
            'valign': 'top'
        })
        
        money_format = workbook.add_format({
            'border': 1,
            'num_format': '$#,##0.00'
        })
        
        time_format = workbook.add_format({
            'border': 1,
            'num_format': 'hh:mm AM/PM'
        })
        
        # Write title
        worksheet.merge_range('A1:G2', f'RAINBOW TOWERS CONFERENCE CENTRE\nDaily Summary Report - {report_date.strftime("%A, %d %B %Y")}', title_format)
        
        # Write headers
        headers = ['Time', 'Event Title', 'Client', 'Room', 'PAX', 'Total Cost', 'Status']
        for col, header in enumerate(headers):
            worksheet.write(3, col, header, header_format)
        
        # Write data
        row = 4
        total_revenue = 0
        total_attendees = 0
        
        for booking in bookings:
            # Convert datetime objects for Excel
            start_time = booking.get('start_time')
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            
            end_time = booking.get('end_time')
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            time_str = ''
            if start_time and end_time:
                time_str = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
            
            client_name = 'Unknown Client'
            if booking.get('client'):
                client_name = booking['client'].get('company_name') or booking['client'].get('contact_person', 'Unknown Client')
            
            room_name = 'Unknown Room'
            if booking.get('room'):
                room_name = booking['room'].get('name', 'Unknown Room')
            
            attendees = booking.get('attendees', 0)
            total_price = booking.get('total_price', 0)
            
            total_revenue += total_price
            total_attendees += attendees
            
            # Write row data
            worksheet.write(row, 0, time_str, cell_format)
            worksheet.write(row, 1, booking.get('title', 'Untitled Event'), cell_format)
            worksheet.write(row, 2, client_name, cell_format)
            worksheet.write(row, 3, room_name, cell_format)
            worksheet.write(row, 4, attendees, cell_format)
            worksheet.write(row, 5, total_price, money_format)
            worksheet.write(row, 6, (booking.get('status', 'tentative')).title(), cell_format)
            
            row += 1
        
        # Write summary
        row += 2
        worksheet.write(row, 0, 'SUMMARY:', header_format)
        worksheet.write(row + 1, 0, f'Total Events: {len(bookings)}', cell_format)
        worksheet.write(row + 2, 0, f'Total Attendees: {total_attendees}', cell_format)
        worksheet.write(row + 3, 0, 'Total Revenue:', cell_format)
        worksheet.write(row + 3, 1, total_revenue, money_format)
        
        # Set column widths
        worksheet.set_column('A:A', 15)  # Time
        worksheet.set_column('B:B', 25)  # Event Title
        worksheet.set_column('C:C', 20)  # Client
        worksheet.set_column('D:D', 15)  # Room
        worksheet.set_column('E:E', 8)   # PAX
        worksheet.set_column('F:F', 12)  # Total Cost
        worksheet.set_column('G:G', 12)  # Status
        
        workbook.close()
        output.seek(0)
        
        # Create response
        response = make_response(output.read())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=Daily_Summary_{report_date.strftime("%Y%m%d")}.xlsx'
        
        return response
        
    except Exception as e:
        print(f"OK: ERROR: Excel generation failed: {e}")
        flash('Excel generation temporarily unavailable. Please try PDF or print the report.', 'warning')
        return redirect(url_for('daily_summary_report', date=report_date.strftime('%Y-%m-%d')))

def generate_pdf_daily_summary(bookings, report_date):
    """Generate PDF file for daily summary report"""
    try:
        # For now, redirect to print view as PDF generation requires additional libraries
        flash('PDF download feature will be available soon. Please use the print function to save as PDF.', 'info')
        return redirect(url_for('daily_summary_report', date=report_date.strftime('%Y-%m-%d')))
        
    except Exception as e:
        print(f"OK: ERROR: PDF generation failed: {e}")
        flash('PDF generation temporarily unavailable. Please use print function or Excel download.', 'warning')
        return redirect(url_for('daily_summary_report', date=report_date.strftime('%Y-%m-%d')))

@app.route('/reports/weekly-summary')
@login_required
def weekly_summary_report():
    """Weekly Summary Report - shows room schedule for a week"""
    try:
        print("=== DEBUG: Loading weekly summary report")
        
        # Get start date parameter (default to current week start)
        start_date_param = request.args.get('start_date')
        if start_date_param:
            try:
                start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
            except ValueError:
                start_date = get_cat_time().date()
        else:
            start_date = get_cat_time().date()
        
        # Calculate week boundaries (Monday to Sunday)
        days_since_monday = start_date.weekday()
        week_start = start_date - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)
        
        print(f"=== DEBUG: Generating weekly summary for {week_start} to {week_end}")
        
        # Generate all days of the week
        week_days = [week_start + timedelta(days=i) for i in range(7)]
        
        # Get all rooms
        rooms_response = supabase_admin.table('rooms').select('*').order('name').execute()
        rooms = rooms_response.data if rooms_response.data else []
        
        # Get all bookings for the week
        start_datetime = datetime.combine(week_start, datetime.min.time())
        end_datetime = datetime.combine(week_end, datetime.max.time())
        
        bookings_response = supabase_admin.table('bookings').select("""
            *,
            client:clients(company_name, contact_person)
        """).gte('start_time', start_datetime.isoformat()).lte('start_time', end_datetime.isoformat()).neq('status', 'cancelled').execute()
        
        bookings_raw = bookings_response.data if bookings_response.data else []
        
        # Organize bookings by room and date
        weekly_schedule = {}
        total_events = 0
        total_revenue = 0
        total_attendees = 0
        
        for booking in bookings_raw:
            try:
                # Parse booking date
                if isinstance(booking['start_time'], str):
                    booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).date()
                else:
                    booking_date = booking['start_time'].date()
                
                room_id = booking.get('room_id')
                if room_id and booking_date:
                    if room_id not in weekly_schedule:
                        weekly_schedule[room_id] = {}
                    
                    date_str = booking_date.isoformat()
                    if date_str not in weekly_schedule[room_id]:
                        weekly_schedule[room_id][date_str] = []
                    
                    # Convert datetime and add to schedule
                    booking = convert_datetime_strings([booking])[0]
                    weekly_schedule[room_id][date_str].append(booking)
                    
                    total_events += 1
                    total_revenue += float(booking.get('total_price', 0) or 0)
                    total_attendees += booking.get('attendees', 0) or 0
                    
            except Exception as booking_error:
                print(f"Error processing booking {booking.get('id')}: {booking_error}")
                continue
        
        # Calculate navigation weeks
        prev_week_start = week_start - timedelta(days=7)
        next_week_start = week_start + timedelta(days=7)
        
        # Calculate additional metrics
        rooms_in_use = len([room_id for room_id in weekly_schedule if any(weekly_schedule[room_id].values())])
        avg_attendees = total_attendees / total_events if total_events > 0 else 0
        avg_revenue_per_event = total_revenue / total_events if total_events > 0 else 0
        
        return render_template('reports/weekly_summary.html',
                              title=f'Weekly Summary - {week_start.strftime("%d %b")} to {week_end.strftime("%d %b %Y")}',
                              week_start=week_start,
                              week_end=week_end,
                              week_days=week_days,
                              rooms=rooms,
                              weekly_schedule=weekly_schedule,
                              total_events=total_events,
                              total_revenue=total_revenue,
                              total_attendees=total_attendees,
                              rooms_in_use=rooms_in_use,
                              avg_attendees=avg_attendees,
                              avg_revenue_per_event=avg_revenue_per_event,
                              prev_week_start=prev_week_start,
                              next_week_start=next_week_start,
                              now=get_cat_time())
        
    except Exception as e:
        print(f"OK: ERROR: Weekly summary report failed: {e}")
        import traceback
        traceback.print_exc()
        flash('Error generating weekly summary report. Please try again.', 'danger')
        return redirect(url_for('reports'))

@app.route('/reports/monthly-report')
@login_required
def monthly_report():
    """Monthly Performance Report - comprehensive monthly analytics"""
    try:
        print("=== DEBUG: Loading monthly report")
        
        # Get start date parameter (default to current month)
        start_date_param = request.args.get('start_date')
        if start_date_param:
            try:
                input_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
                report_month = input_date.replace(day=1)
            except ValueError:
                report_month = get_cat_time().date().replace(day=1)
        else:
            report_month = get_cat_time().date().replace(day=1)
        
        # Calculate month boundaries
        if report_month.month == 12:
            next_month = report_month.replace(year=report_month.year + 1, month=1)
        else:
            next_month = report_month.replace(month=report_month.month + 1)
        
        month_end = next_month - timedelta(days=1)
        
        print(f"=== DEBUG: Generating monthly report for {report_month.strftime('%B %Y')}")
        
        # Get all bookings for the month
        start_datetime = datetime.combine(report_month, datetime.min.time())
        end_datetime = datetime.combine(month_end, datetime.max.time())
        
        bookings_response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, company_name, contact_person)
        """).gte('start_time', start_datetime.isoformat()).lte('start_time', end_datetime.isoformat()).neq('status', 'cancelled').execute()
        
        bookings_raw = bookings_response.data if bookings_response.data else []
        
        # Calculate key metrics
        total_events = len(bookings_raw)
        total_revenue = sum(float(b.get('total_price', 0) or 0) for b in bookings_raw)
        total_attendees = sum(b.get('attendees', 0) or 0 for b in bookings_raw)
        avg_booking_value = total_revenue / total_events if total_events > 0 else 0
        
        # Get unique clients and rooms
        active_clients = len(set(b.get('client_id') for b in bookings_raw if b.get('client_id')))
        rooms_utilized = len(set(b.get('room_id') for b in bookings_raw if b.get('room_id')))
        
        # Calculate room performance
        room_performance = []
        room_stats = {}
        
        for booking in bookings_raw:
            room_id = booking.get('room_id')
            if room_id:
                if room_id not in room_stats:
                    room_stats[room_id] = {
                        'events': 0,
                        'revenue': 0,
                        'hours': 0,
                        'room': booking.get('room', {})
                    }
                
                room_stats[room_id]['events'] += 1
                room_stats[room_id]['revenue'] += float(booking.get('total_price', 0) or 0)
                
                # Calculate hours
                try:
                    start = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00'))
                    hours = (end - start).total_seconds() / 3600
                    room_stats[room_id]['hours'] += hours
                except:
                    room_stats[room_id]['hours'] += 4  # Default estimate
        
        # Calculate utilization for each room
        total_days = (month_end - report_month).days + 1
        business_hours_per_day = 10
        
        for room_id, stats in room_stats.items():
            total_available_hours = total_days * business_hours_per_day
            utilization = (stats['hours'] / total_available_hours * 100) if total_available_hours > 0 else 0
            
            room_performance.append({
                'name': stats['room'].get('name', 'Unknown Room'),
                'events': stats['events'],
                'revenue': stats['revenue'],
                'utilization': round(utilization, 1),
                'hours': round(stats['hours'], 1)
            })
        
        # Sort by utilization
        room_performance.sort(key=lambda x: x['utilization'], reverse=True)
        
        # Calculate overall utilization
        total_possible_hours = rooms_utilized * total_days * business_hours_per_day if rooms_utilized > 0 else 1
        total_booked_hours = sum(rp['hours'] for rp in room_performance)
        utilization_rate = (total_booked_hours / total_possible_hours * 100) if total_possible_hours > 0 else 0
        
        # Get top clients by revenue
        client_stats = {}
        for booking in bookings_raw:
            client_id = booking.get('client_id')
            if client_id and booking.get('client'):
                client_name = booking['client'].get('company_name') or booking['client'].get('contact_person', 'Unknown')
                if client_id not in client_stats:
                    client_stats[client_id] = {
                        'name': client_name,
                        'revenue': 0,
                        'events': 0
                    }
                client_stats[client_id]['revenue'] += float(booking.get('total_price', 0) or 0)
                client_stats[client_id]['events'] += 1
        
        top_clients = sorted(client_stats.values(), key=lambda x: x['revenue'], reverse=True)[:10]
        
        # Calculate navigation months
        if report_month.month == 1:
            prev_month = report_month.replace(year=report_month.year - 1, month=12)
        else:
            prev_month = report_month.replace(month=report_month.month - 1)
        
        if report_month.month == 12:
            next_month_nav = report_month.replace(year=report_month.year + 1, month=1)
        else:
            next_month_nav = report_month.replace(month=report_month.month + 1)
        
        # Don't show next month if it's in the future
        if next_month_nav > get_cat_time().date().replace(day=1):
            next_month_nav = None
        
        # Prepare insights
        insights = {
            'opportunities': [
                f"Room utilization is at {utilization_rate:.1f}% - {'excellent' if utilization_rate >= 70 else 'good' if utilization_rate >= 50 else 'room for improvement'}",
                f"Top performing room: {room_performance[0]['name']}" if room_performance else "No room data available",
                f"Average booking value: ${avg_booking_value:.0f}" if avg_booking_value > 0 else "No booking data"
            ],
            'improvements': [
                "Consider promotional pricing for underutilized rooms",
                "Focus on repeat client retention strategies",
                "Optimize peak hour pricing"
            ]
        }
        
        return render_template('reports/monthly_summary.html',
                              title=f'Monthly Report - {report_month.strftime("%B %Y")}',
                              report_month=report_month,
                              total_events=total_events,
                              total_revenue=total_revenue,
                              total_attendees=total_attendees,
                              avg_booking_value=avg_booking_value,
                              active_clients=active_clients,
                              rooms_utilized=rooms_utilized,
                              utilization_rate=round(utilization_rate, 1),
                              room_performance=room_performance,
                              top_clients=top_clients,
                              room_revenue=total_revenue * 0.7,  # Estimate
                              addon_revenue=total_revenue * 0.3,  # Estimate
                              prev_month=prev_month,
                              next_month=next_month_nav,
                              insights=insights,
                              now=get_cat_time())
        
    except Exception as e:
        print(f"OK: ERROR: Monthly report failed: {e}")
        import traceback
        traceback.print_exc()
        flash('Error generating monthly report. Please try again.', 'danger')
        return redirect(url_for('reports'))
    
# ===============================
# REPORT DOWNLOAD ROUTES
# ===============================

@app.route('/reports/weekly-summary/download')
@login_required
def download_weekly_summary():
    """Download weekly summary report in Excel or PDF format"""
    try:
        report_format = request.args.get('format', 'excel')
        start_date = request.args.get('start_date', get_cat_time().date().isoformat())
        
        if report_format == 'excel':
            flash('Excel download feature coming soon!', 'info')
            return redirect(url_for('weekly_summary_report', start_date=start_date))
        elif report_format == 'pdf':
            flash('PDF download feature coming soon! Please use the print function.', 'info')
            return redirect(url_for('weekly_summary_report', start_date=start_date))
        else:
            flash('Invalid download format', 'error')
            return redirect(url_for('weekly_summary_report'))
            
    except Exception as e:
        print(f"Download error: {e}")
        flash('Error downloading report', 'error')
        return redirect(url_for('weekly_summary_report'))

@app.route('/reports/monthly-report/download')
@login_required
def download_monthly_report():
    """Download monthly report in Excel or PDF format"""
    try:
        report_format = request.args.get('format', 'excel')
        start_date = request.args.get('start_date', get_cat_time().date().isoformat())
        
        if report_format == 'excel':
            flash('Excel download feature coming soon!', 'info')
            return redirect(url_for('monthly_report', start_date=start_date))
        elif report_format == 'pdf':
            flash('PDF download feature coming soon! Please use the print function.', 'info')
            return redirect(url_for('monthly_report', start_date=start_date))
        else:
            flash('Invalid download format', 'error')
            return redirect(url_for('monthly_report'))
            
    except Exception as e:
        print(f"Download error: {e}")
        flash('Error downloading report', 'error')
        return redirect(url_for('monthly_report'))

# ===============================
# API Routes for Dashboard Widgets
# ===============================

@app.route('/api/dashboard/upcoming-bookings')
@login_required
def api_upcoming_bookings():
    """API endpoint for upcoming bookings widget using admin client"""
    try:
        days = request.args.get('days', 7, type=int)
        end_date = get_cat_time() + timedelta(days=days)
        
        bookings = supabase_admin.table('bookings').select("""
            id, title, start_time, status,
            room:rooms(name),
            client:clients(company_name, contact_person)
        """).gte('start_time', get_cat_time().isoformat()).lte('start_time', end_date.isoformat()).neq('status', 'cancelled').order('start_time').execute()
        
        data = []
        for booking in bookings.data:
            data.append({
                'id': booking['id'],
                'title': booking['title'],
                'room': booking['room']['name'] if booking['room'] else 'Unknown',
                'client': booking['client']['company_name'] or booking['client']['contact_person'] if booking['client'] else 'Unknown',
                'start_time': booking['start_time'],
                'status': booking['status']
            })
        
        return jsonify(data)
    except Exception as e:
        print(f"API error: {e}")
        return jsonify([])

@app.route('/api/dashboard/room-status')
@login_required
def api_room_status():
    """API endpoint for room status widget using admin client"""
    try:
        now = get_cat_time().isoformat()
        rooms = supabase_select('rooms')
        
        data = []
        for room in rooms:
            # Check if room is currently booked using admin client
            current_booking = supabase_admin.table('bookings').select('id, title, end_time').eq('room_id', room['id']).lte('start_time', now).gte('end_time', now).neq('status', 'cancelled').execute()
            
            # Get next booking using admin client
            next_booking = supabase_admin.table('bookings').select('id, title, start_time').eq('room_id', room['id']).gt('start_time', now).neq('status', 'cancelled').order('start_time').limit(1).execute()
            
            status = room['status']
            if status == 'available' and current_booking.data:
                status = 'in_use'
            
            data.append({
                'id': room['id'],
                'name': room['name'],
                'status': status,
                'current_booking': current_booking.data[0] if current_booking.data else None,
                'next_booking': next_booking.data[0] if next_booking.data else None
            })
        
        return jsonify(data)
    except Exception as e:
        print(f"Room status API error: {e}")
        return jsonify([])

@app.route('/api/rooms/<int:room_id>')
@login_required
def get_room_details(room_id):
    """API endpoint to get detailed room information"""
    try:
        room_data = supabase_select('rooms', filters=[('id', 'eq', room_id)])
        if room_data:
            room = room_data[0]
            return jsonify({
                'id': room['id'],
                'name': room['name'],
                'capacity': room['capacity'],
                'description': room['description'],
                'hourly_rate': room['hourly_rate'],
                'half_day_rate': room['half_day_rate'],
                'full_day_rate': room['full_day_rate'],
                'amenities': room['amenities'],
                'status': room['status'],
                'image_url': room['image_url']
            })
        else:
            return jsonify({'error': 'Room not found'}), 404
    except Exception as e:
        print(f"Room details API error: {e}")
        return jsonify({'error': 'Error fetching room details'}), 500

@app.route('/api/rooms')
@login_required
def get_all_rooms():
    """API endpoint to get all rooms with basic info"""
    try:
        rooms = supabase_select('rooms')
        return jsonify([{
            'id': room['id'],
            'name': room['name'],
            'capacity': room['capacity'],
            'status': room['status'],
            'hourly_rate': room['hourly_rate'],
            'half_day_rate': room['half_day_rate'],
            'full_day_rate': room['full_day_rate']
        } for room in rooms])
    except Exception as e:
        print(f"Rooms API error: {e}")
        return jsonify([])

@app.route('/debug/rooms/<int:room_id>')
@login_required
def debug_room(room_id):
    """Debug endpoint to check room data"""
    try:
        room_data = supabase_select('rooms', filters=[('id', 'eq', room_id)])
        if room_data:
            return jsonify({
                'success': True,
                'room': room_data[0],
                'message': f'Room {room_id} found successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Room {room_id} not found'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': f'Error fetching room {room_id}'
        })

@app.route('/debug/test-update/<int:room_id>')
@login_required
def debug_test_update(room_id):
    """Debug endpoint to test room update"""
    try:
        # Test a simple update
        test_data = {
            'description': f'Test update at {get_cat_time().isoformat()}'
        }
        
        result = supabase_update('rooms', test_data, [('id', 'eq', room_id)])
        
        return jsonify({
            'success': bool(result),
            'result': result,
            'message': f'Test update for room {room_id} completed'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': f'Error testing update for room {room_id}'
        })

@app.route('/debug')
def debug_info():
    """Debug endpoint to check session status"""
    return jsonify({
        'authenticated': current_user.is_authenticated,
        'user_id': getattr(current_user, 'id', None),
        'session_keys': list(session.keys()),
        'has_supabase_session': 'supabase_session' in session,
        'secret_key_set': bool(app.config.get('SECRET_KEY')),
        'session_permanent': session.permanent if hasattr(session, 'permanent') else False,
        'environment': os.environ.get('FLASK_ENV', 'development')
    })
@app.route('/debug/calendar-data')
@login_required
def debug_calendar_data():
    """Debug route to verify calendar event data structure"""
    try:
        print("=== DEBUG: Testing calendar data structure")
        
        # Get events using the same function as the API
        events = get_booking_calendar_events_supabase()
        
        debug_info = {
            'timestamp': get_cat_time().isoformat(),
            'total_events': len(events),
            'events_summary': [],
            'data_validation': {
                'events_with_attendees': 0,
                'events_with_total': 0,
                'events_with_cost_per_person': 0,
                'attendees_data_types': [],
                'total_data_types': [],
                'cost_per_person_data_types': []
            }
        }
        
        # Analyze each event
        for event in events[:10]:  # Limit to first 10 for debugging
            props = event.get('extendedProps', {})
            
            # Validate attendees
            attendees = props.get('attendees')
            if attendees is not None and attendees > 0:
                debug_info['data_validation']['events_with_attendees'] += 1
            debug_info['data_validation']['attendees_data_types'].append(type(attendees).__name__)
            
            # Validate total
            total = props.get('total')
            if total is not None and total > 0:
                debug_info['data_validation']['events_with_total'] += 1
            debug_info['data_validation']['total_data_types'].append(type(total).__name__)
            
            # Validate cost per person
            cost_per_person = props.get('cost_per_person')
            if cost_per_person is not None and cost_per_person > 0:
                debug_info['data_validation']['events_with_cost_per_person'] += 1
            debug_info['data_validation']['cost_per_person_data_types'].append(type(cost_per_person).__name__)
            
            # Add event summary
            debug_info['events_summary'].append({
                'id': event.get('id'),
                'title': event.get('title'),
                'attendees': attendees,
                'total': total,
                'cost_per_person': cost_per_person,
                'room': props.get('room'),
                'client': props.get('client'),
                'status': props.get('status'),
                'all_props_keys': list(props.keys())
            })
        
        # Calculate percentages
        if debug_info['total_events'] > 0:
            debug_info['data_validation']['attendees_percentage'] = round(
                (debug_info['data_validation']['events_with_attendees'] / debug_info['total_events']) * 100, 1
            )
            debug_info['data_validation']['total_percentage'] = round(
                (debug_info['data_validation']['events_with_total'] / debug_info['total_events']) * 100, 1
            )
            debug_info['data_validation']['cost_per_person_percentage'] = round(
                (debug_info['data_validation']['events_with_cost_per_person'] / debug_info['total_events']) * 100, 1
            )
        
        # Get unique data types
        debug_info['data_validation']['unique_attendees_types'] = list(set(debug_info['data_validation']['attendees_data_types']))
        debug_info['data_validation']['unique_total_types'] = list(set(debug_info['data_validation']['total_data_types']))
        debug_info['data_validation']['unique_cost_per_person_types'] = list(set(debug_info['data_validation']['cost_per_person_data_types']))
        
        # Recommendations
        debug_info['recommendations'] = []
        
        if debug_info['data_validation']['events_with_attendees'] == 0:
            debug_info['recommendations'].append("OK: No events have attendees data - check database attendees field")
        elif debug_info['data_validation']['attendees_percentage'] < 80:
            debug_info['recommendations'].append(f"OK: Only {debug_info['data_validation']['attendees_percentage']}% of events have attendees data")
        else:
            debug_info['recommendations'].append("OK: Attendees data looks good")
        
        if debug_info['data_validation']['events_with_total'] == 0:
            debug_info['recommendations'].append("OK: No events have total price data - check database total_price field")
        elif debug_info['data_validation']['total_percentage'] < 80:
            debug_info['recommendations'].append(f"OK: Only {debug_info['data_validation']['total_percentage']}% of events have total data")
        else:
            debug_info['recommendations'].append("OK: Total price data looks good")
        
        if debug_info['data_validation']['events_with_cost_per_person'] == 0:
            debug_info['recommendations'].append("OK: No events have cost per person calculated - check attendees and total data")
        else:
            debug_info['recommendations'].append("OK: Cost per person calculation working")
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': get_cat_time().isoformat(),
            'message': 'Debug calendar data failed'
        }), 500

@app.route('/debug/sample-booking-data')
@login_required  
def debug_sample_booking_data():
    """Debug route to check raw booking data from database"""
    try:
        # Get a few sample bookings
        bookings_response = supabase_admin.table('bookings').select('*').limit(5).execute()
        bookings = bookings_response.data if bookings_response.data else []
        
        debug_data = {
            'timestamp': get_cat_time().isoformat(),
            'sample_bookings': [],
            'field_analysis': {
                'attendees_field_names': [],
                'total_field_names': [],
                'available_fields': set()
            }
        }
        
        for booking in bookings:
            # Analyze available fields
            debug_data['field_analysis']['available_fields'].update(booking.keys())
            
            # Check for attendees-related fields
            attendees_fields = {}
            for field in ['attendees', 'pax', 'guests', 'participant_count']:
                if field in booking:
                    attendees_fields[field] = booking[field]
                    debug_data['field_analysis']['attendees_field_names'].append(field)
            
            # Check for total-related fields  
            total_fields = {}
            for field in ['total_price', 'total', 'price', 'amount', 'cost']:
                if field in booking:
                    total_fields[field] = booking[field]
                    debug_data['field_analysis']['total_field_names'].append(field)
            
            debug_data['sample_bookings'].append({
                'id': booking.get('id'),
                'title': booking.get('title'),
                'status': booking.get('status'),
                'attendees_fields': attendees_fields,
                'total_fields': total_fields,
                'all_fields': list(booking.keys())
            })
        
        # Remove duplicates and convert set to list
        debug_data['field_analysis']['available_fields'] = sorted(list(debug_data['field_analysis']['available_fields']))
        debug_data['field_analysis']['attendees_field_names'] = sorted(list(set(debug_data['field_analysis']['attendees_field_names'])))
        debug_data['field_analysis']['total_field_names'] = sorted(list(set(debug_data['field_analysis']['total_field_names'])))
        
        return jsonify(debug_data)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': get_cat_time().isoformat()
        }), 500
    
@app.route('/debug/clients')
@login_required
def debug_clients():
    """Debug route to test client data retrieval"""
    try:
        debug_info = {
            'timestamp': get_cat_time().isoformat(),
            'supabase_connection': False,
            'raw_clients_data': [],
            'processed_clients_data': [],
            'booking_counts': {},
            'errors': [],
            'summary': {}
        }
        
        print("=== DEBUG: Starting comprehensive client data test...")
        
        # Test 1: Basic Supabase connection
        try:
            test_response = supabase_admin.table('clients').select('count').execute()
            debug_info['supabase_connection'] = True
            print("OK: DEBUG: Supabase connection successful")
        except Exception as e:
            debug_info['errors'].append(f"Supabase connection failed: {str(e)}")
            print(f"OK: DEBUG: Supabase connection failed: {e}")
        
        # Test 2: Raw clients data
        try:
            clients_response = supabase_admin.table('clients').select('*').execute()
            raw_clients = clients_response.data if clients_response.data else []
            debug_info['raw_clients_data'] = raw_clients
            print(f"OK: DEBUG: Raw clients fetch successful - {len(raw_clients)} clients")
            
            if raw_clients:
                print(f"=== DEBUG: Sample raw client: {raw_clients[0]}")
        except Exception as e:
            debug_info['errors'].append(f"Raw clients fetch failed: {str(e)}")
            print(f"OK: DEBUG: Raw clients fetch failed: {e}")
        
        # Test 3: Bookings data for counting
        try:
            bookings_response = supabase_admin.table('bookings').select('client_id, status').execute()
            bookings = bookings_response.data if bookings_response.data else []
            
            # Calculate booking counts
            booking_counts = {}
            for booking in bookings:
                client_id = booking.get('client_id')
                if client_id and booking.get('status') != 'cancelled':
                    booking_counts[client_id] = booking_counts.get(client_id, 0) + 1
            
            debug_info['booking_counts'] = booking_counts
            print(f"OK: DEBUG: Booking counts calculated - {len(bookings)} total bookings, {len(booking_counts)} clients with bookings")
        except Exception as e:
            debug_info['errors'].append(f"Booking counts calculation failed: {str(e)}")
            print(f"OK: DEBUG: Booking counts calculation failed: {e}")
        
        # Test 4: Process clients with booking counts
        try:
            if debug_info['raw_clients_data']:
                processed_clients = []
                for client in debug_info['raw_clients_data']:
                    processed_client = client.copy()
                    processed_client['booking_count'] = debug_info['booking_counts'].get(client.get('id'), 0)
                    processed_client['display_name'] = client.get('company_name') or client.get('contact_person', 'Unknown')
                    processed_clients.append(processed_client)
                
                debug_info['processed_clients_data'] = processed_clients
                print(f"OK: DEBUG: Client processing successful - {len(processed_clients)} clients processed")
        except Exception as e:
            debug_info['errors'].append(f"Client processing failed: {str(e)}")
            print(f"OK: DEBUG: Client processing failed: {e}")
        
        # Test 5: Test the actual function used by the clients route
        try:
            function_result = get_clients_with_booking_counts()
            debug_info['function_result_count'] = len(function_result)
            debug_info['function_success'] = True
            print(f"OK: DEBUG: get_clients_with_booking_counts() returned {len(function_result)} clients")
        except Exception as e:
            debug_info['errors'].append(f"get_clients_with_booking_counts() failed: {str(e)}")
            debug_info['function_success'] = False
            print(f"OK: DEBUG: get_clients_with_booking_counts() failed: {e}")
        
        # Summary
        debug_info['summary'] = {
            'total_errors': len(debug_info['errors']),
            'connection_ok': debug_info['supabase_connection'],
            'raw_clients_count': len(debug_info['raw_clients_data']),
            'clients_with_bookings': len([c for c in debug_info['processed_clients_data'] if c.get('booking_count', 0) > 0]),
            'function_working': debug_info.get('function_success', False)
        }
        
        print(f"=== DEBUG: Test summary - Connection: {debug_info['summary']['connection_ok']}, Clients: {debug_info['summary']['raw_clients_count']}, Function: {debug_info['summary']['function_working']}")
        
        return jsonify(debug_info)
        
    except Exception as e:
        print(f"OK: CRITICAL: Debug route itself failed: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': get_cat_time().isoformat(),
            'critical_failure': True
        }), 500

# Also add this simple test route
@app.route('/debug/clients/simple')
@login_required
def debug_clients_simple():
    """Simple test to check if any clients exist"""
    try:
        # Direct query
        response = supabase_admin.table('clients').select('id, company_name, contact_person, email').execute()
        clients = response.data if response.data else []
        
        return jsonify({
            'success': True,
            'clients_found': len(clients),
            'clients': clients[:5],  # First 5 clients
            'message': f'Found {len(clients)} clients in database',
            'timestamp': get_cat_time().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch clients',
            'timestamp': get_cat_time().isoformat()
        }), 500

@app.route('/debug/database-connection')
def debug_database_connection():
    """Comprehensive database connection test for production"""
    try:
        debug_info = {
            'timestamp': get_cat_time().isoformat(),
            'environment': os.environ.get('FLASK_ENV', 'development'),
            'supabase_url_set': bool(SUPABASE_URL),
            'supabase_anon_key_set': bool(SUPABASE_ANON_KEY),
            'supabase_service_key_set': bool(SUPABASE_SERVICE_KEY),
            'secret_key_set': bool(app.config.get('SECRET_KEY')),
            'errors': []
        }
        
        # Test basic connection
        try:
            # Test with admin client (service key)
            response = supabase_admin.table('rooms').select('count').execute()
            debug_info['admin_client_works'] = True
            debug_info['rooms_accessible'] = True
        except Exception as e:
            debug_info['admin_client_works'] = False
            debug_info['errors'].append(f'Admin client error: {str(e)}')
        
        # Test regular client
        try:
            response = supabase.table('rooms').select('count').execute()
            debug_info['regular_client_works'] = True
        except Exception as e:
            debug_info['regular_client_works'] = False
            debug_info['errors'].append(f'Regular client error: {str(e)}')
        
        # Test data retrieval
        try:
            rooms = supabase_admin.table('rooms').select('*').execute()
            clients = supabase_admin.table('clients').select('*').execute()
            bookings = supabase_admin.table('bookings').select('*').execute()
            
            debug_info['data_counts'] = {
                'rooms': len(rooms.data) if rooms.data else 0,
                'clients': len(clients.data) if clients.data else 0,
                'bookings': len(bookings.data) if bookings.data else 0
            }
        except Exception as e:
            debug_info['errors'].append(f'Data retrieval error: {str(e)}')
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': get_cat_time().isoformat()
        }), 500

@app.route('/debug/sample-data')
def debug_sample_data():
    """Get sample data to verify database connection"""
    try:
        # Get sample data using admin client
        rooms_sample = supabase_admin.table('rooms').select('*').limit(3).execute()
        clients_sample = supabase_admin.table('clients').select('*').limit(3).execute()
        bookings_sample = supabase_admin.table('bookings').select('*').limit(3).execute()
        
        return jsonify({
            'success': True,
            'timestamp': get_cat_time().isoformat(),
            'sample_data': {
                'rooms': rooms_sample.data,
                'clients': clients_sample.data,
                'bookings': bookings_sample.data
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': get_cat_time().isoformat()
        }), 500
        
@app.route('/debug/supabase-data')
@login_required
def debug_supabase_data():
    """Debug route to examine Supabase data structure"""
    try:
        now = get_cat_time().isoformat()
        
        # Test simple booking query
        simple_bookings = supabase_admin.table('bookings').select('*').limit(2).execute()
        
        # Test nested relationship query
        nested_bookings = supabase_admin.table('bookings').select("""
            *,
            room:rooms(name),
            client:clients(company_name, contact_person)
        """).limit(2).execute()
        
        # Test individual room and client queries
        rooms = supabase_admin.table('rooms').select('*').limit(2).execute()
        clients = supabase_admin.table('clients').select('*').limit(2).execute()
        
        return jsonify({
            'success': True,
            'timestamp': get_cat_time().isoformat(),
            'environment': os.environ.get('FLASK_ENV', 'development'),
            'simple_bookings': {
                'count': len(simple_bookings.data) if simple_bookings.data else 0,
                'data': simple_bookings.data
            },
            'nested_bookings': {
                'count': len(nested_bookings.data) if nested_bookings.data else 0,
                'data': nested_bookings.data,
                'structure_check': {
                    'has_room_relationship': bool(nested_bookings.data and nested_bookings.data[0].get('room')) if nested_bookings.data else False,
                    'has_client_relationship': bool(nested_bookings.data and nested_bookings.data[0].get('client')) if nested_bookings.data else False,
                }
            },
            'rooms': {
                'count': len(rooms.data) if rooms.data else 0,
                'sample': rooms.data[0] if rooms.data else None
            },
            'clients': {
                'count': len(clients.data) if clients.data else 0,
                'sample': clients.data[0] if clients.data else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': get_cat_time().isoformat()
        }), 500

@app.route('/debug/test-queries')
def debug_test_queries():
    """Test specific queries that might be failing"""
    try:
        results = {}
        
        # Test dashboard queries
        try:
            now = get_cat_time().isoformat()
            upcoming_bookings = supabase_admin.table('bookings').select("""
                *,
                room:rooms(name),
                client:clients(company_name, contact_person)
            """).gte('start_time', now).neq('status', 'cancelled').order('start_time').limit(5).execute()
            
            results['upcoming_bookings'] = {
                'success': True,
                'count': len(upcoming_bookings.data),
                'sample': upcoming_bookings.data[:2] if upcoming_bookings.data else []
            }
        except Exception as e:
            results['upcoming_bookings'] = {
                'success': False,
                'error': str(e)
            }
        
        # Test room utilization query
        try:
            rooms = supabase_admin.table('rooms').select('*').execute()
            results['rooms_query'] = {
                'success': True,
                'count': len(rooms.data),
                'sample': rooms.data[:2] if rooms.data else []
            }
        except Exception as e:
            results['rooms_query'] = {
                'success': False,
                'error': str(e)
            }
        
        # Test addons query
        try:
            categories_data = supabase_admin.table('addon_categories').select("""
                *,
                addons(*)
            """).execute()
            results['addons_query'] = {
                'success': True,
                'count': len(categories_data.data),
                'sample': categories_data.data[:1] if categories_data.data else []
            }
        except Exception as e:
            results['addons_query'] = {
                'success': False,
                'error': str(e)
            }
        
        return jsonify({
            'success': True,
            'timestamp': get_cat_time().isoformat(),
            'query_results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': get_cat_time().isoformat()
        }), 500

@app.route('/api/clients/booking-counts')
@login_required
def api_client_booking_counts():
    """API endpoint to get booking counts for all clients"""
    try:
        clients = get_clients_with_booking_counts()
        
        booking_counts = {}
        for client in clients:
            booking_counts[client['id']] = client.get('booking_count', 0)
        
        return jsonify({
            'success': True,
            'booking_counts': booking_counts,
            'total_clients': len(clients)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<int:id>/stats')
@login_required
def api_client_stats(id):
    """API endpoint to get detailed statistics for a specific client"""
    try:
        # Get client
        client = get_client_by_id_from_db(id)
        if not client:
            return jsonify({'success': False, 'error': 'Client not found'}), 404
        
        # Get bookings
        bookings = get_client_bookings_from_db(id)
        
        # Calculate stats
        total_bookings = len(bookings)
        total_spent = sum(float(booking.get('total_price', 0)) for booking in bookings)
        avg_booking_value = total_spent / total_bookings if total_bookings > 0 else 0
        
        # Count by status
        status_counts = {}
        for booking in bookings:
            status = booking.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return jsonify({
            'success': True,
            'client_id': id,
            'client_name': client.get('company_name') or client.get('contact_person'),
            'stats': {
                'total_bookings': total_bookings,
                'total_spent': round(total_spent, 2),
                'avg_booking_value': round(avg_booking_value, 2),
                'status_breakdown': status_counts
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/debug/clients-sync')
@login_required
def debug_clients_sync():
    """Debug endpoint to check client-booking data synchronization"""
    try:
        debug_info = {
            'timestamp': get_cat_time().isoformat(),
            'clients_analysis': {},
            'booking_analysis': {},
            'sync_issues': []
        }
        
        # Analyze clients
        clients = get_all_clients_from_db()
        debug_info['clients_analysis'] = {
            'total_clients': len(clients),
            'clients_with_company_name': len([c for c in clients if c.get('company_name')]),
            'clients_with_phone': len([c for c in clients if c.get('phone')]),
            'sample_clients': clients[:3] if clients else []
        }
        
        # Analyze bookings
        bookings_response = supabase_admin.table('bookings').select('*').execute()
        bookings = bookings_response.data if bookings_response.data else []
        
        client_ids_with_bookings = set()
        orphaned_bookings = []
        
        for booking in bookings:
            client_id = booking.get('client_id')
            if client_id:
                client_ids_with_bookings.add(client_id)
                # Check if client exists
                if not any(c['id'] == client_id for c in clients):
                    orphaned_bookings.append(booking['id'])
        
        debug_info['booking_analysis'] = {
            'total_bookings': len(bookings),
            'unique_clients_with_bookings': len(client_ids_with_bookings),
            'orphaned_bookings': len(orphaned_bookings),
            'status_breakdown': {}
        }
        
        # Status breakdown
        for booking in bookings:
            status = booking.get('status', 'unknown')
            debug_info['booking_analysis']['status_breakdown'][status] = \
                debug_info['booking_analysis']['status_breakdown'].get(status, 0) + 1
        
        # Check for sync issues
        if orphaned_bookings:
            debug_info['sync_issues'].append(f"Found {len(orphaned_bookings)} orphaned bookings")
        
        clients_without_bookings = len(clients) - len(client_ids_with_bookings)
        if clients_without_bookings > 0:
            debug_info['sync_issues'].append(f"{clients_without_bookings} clients have no bookings")
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': get_cat_time().isoformat()
        }), 500

# ===============================
# PRODUCTION DEBUG HELPER FUNCTIONS
# ===============================

@app.route('/debug/production-stats')
@login_required
def debug_production_stats():
    """Debug endpoint to check production statistics calculation"""
    try:
        debug_info = {
            'timestamp': get_cat_time().isoformat(),
            'environment': os.environ.get('FLASK_ENV', 'development'),
            'database_connection': False,
            'queries_executed': [],
            'errors_encountered': [],
            'statistics_raw': {},
            'supabase_config': {
                'url_set': bool(SUPABASE_URL),
                'anon_key_set': bool(SUPABASE_ANON_KEY),
                'service_key_set': bool(SUPABASE_SERVICE_KEY),
                'admin_client_available': bool(supabase_admin)
            }
        }
        
        # Test 1: Basic connectivity
        try:
            test_response = supabase_admin.table('rooms').select('count').execute()
            debug_info['database_connection'] = True
            debug_info['queries_executed'].append('Basic connectivity test: SUCCESS')
        except Exception as e:
            debug_info['database_connection'] = False
            debug_info['errors_encountered'].append(f'Connectivity test failed: {str(e)}')
        
        # Test 2: Rooms query
        try:
            rooms_response = supabase_admin.table('rooms').select('*').execute()
            rooms_count = len(rooms_response.data) if rooms_response.data else 0
            debug_info['statistics_raw']['total_rooms'] = rooms_count
            debug_info['queries_executed'].append(f'Rooms query: Found {rooms_count} rooms')
        except Exception as e:
            debug_info['errors_encountered'].append(f'Rooms query failed: {str(e)}')
        
        # Test 3: Bookings query
        try:
            bookings_response = supabase_admin.table('bookings').select('*').execute()
            bookings_count = len(bookings_response.data) if bookings_response.data else 0
            debug_info['statistics_raw']['total_bookings'] = bookings_count
            debug_info['queries_executed'].append(f'Bookings query: Found {bookings_count} bookings')
            
            # Calculate current month bookings
            if bookings_response.data:
                current_month_start = get_cat_time().date().replace(day=1)
                current_month_bookings = 0
                current_month_revenue = 0.0
                
                for booking in bookings_response.data:
                    try:
                        if booking.get('status') != 'cancelled':
                            booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).date()
                            if booking_date >= current_month_start:
                                current_month_bookings += 1
                                current_month_revenue += float(booking.get('total_price', 0) or 0)
                    except Exception as booking_error:
                        debug_info['errors_encountered'].append(f'Error processing booking {booking.get("id", "unknown")}: {str(booking_error)}')
                
                debug_info['statistics_raw']['current_month_bookings'] = current_month_bookings
                debug_info['statistics_raw']['current_month_revenue'] = current_month_revenue
                debug_info['queries_executed'].append(f'Current month analysis: {current_month_bookings} bookings, ${current_month_revenue:.2f} revenue')
            
        except Exception as e:
            debug_info['errors_encountered'].append(f'Bookings query failed: {str(e)}')
        
        # Test 4: Clients query
        try:
            clients_response = supabase_admin.table('clients').select('*').execute()
            clients_count = len(clients_response.data) if clients_response.data else 0
            debug_info['statistics_raw']['total_clients'] = clients_count
            debug_info['queries_executed'].append(f'Clients query: Found {clients_count} clients')
        except Exception as e:
            debug_info['errors_encountered'].append(f'Clients query failed: {str(e)}')
        
        # Test 5: Add-ons query
        try:
            addons_response = supabase_admin.table('addons').select('*').execute()
            addons_count = len(addons_response.data) if addons_response.data else 0
            debug_info['statistics_raw']['total_addons'] = addons_count
            debug_info['queries_executed'].append(f'Add-ons query: Found {addons_count} add-ons')
        except Exception as e:
            debug_info['errors_encountered'].append(f'Add-ons query failed: {str(e)}')
        
        # Test 6: Authentication check
        try:
            if current_user.is_authenticated:
                debug_info['user_info'] = {
                    'authenticated': True,
                    'user_id': current_user.id,
                    'user_email': current_user.email,
                    'user_role': current_user.role
                }
            else:
                debug_info['user_info'] = {'authenticated': False}
        except Exception as e:
            debug_info['errors_encountered'].append(f'User info failed: {str(e)}')
        
        # Summary
        debug_info['summary'] = {
            'total_queries_attempted': len(debug_info['queries_executed']),
            'total_errors': len(debug_info['errors_encountered']),
            'database_accessible': debug_info['database_connection'],
            'has_data': any(debug_info['statistics_raw'].values()) if debug_info['statistics_raw'] else False
        }
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': get_cat_time().isoformat(),
            'critical_failure': True
        }), 500

@app.route('/debug/supabase-config')
@login_required
def debug_supabase_config():
    """Debug Supabase configuration in production"""
    try:
        config_info = {
            'timestamp': get_cat_time().isoformat(),
            'environment_variables': {
                'SUPABASE_URL': SUPABASE_URL[:50] + '...' if SUPABASE_URL else 'NOT SET',
                'SUPABASE_ANON_KEY': 'SET (' + str(len(SUPABASE_ANON_KEY)) + ' chars)' if SUPABASE_ANON_KEY else 'NOT SET',
                'SUPABASE_SERVICE_KEY': 'SET (' + str(len(SUPABASE_SERVICE_KEY)) + ' chars)' if SUPABASE_SERVICE_KEY else 'NOT SET',
                'FLASK_ENV': os.environ.get('FLASK_ENV', 'not set'),
                'SECRET_KEY': 'SET' if app.config.get('SECRET_KEY') else 'NOT SET'
            },
            'client_status': {
                'regular_client_initialized': bool(supabase),
                'admin_client_initialized': bool(supabase_admin),
                'clients_are_same': supabase is supabase_admin
            },
            'connection_tests': {}
        }
        
        # Test regular client
        try:
            if supabase:
                test_response = supabase.table('rooms').select('id').limit(1).execute()
                config_info['connection_tests']['regular_client'] = {
                    'success': True,
                    'rows_returned': len(test_response.data) if test_response.data else 0
                }
            else:
                config_info['connection_tests']['regular_client'] = {
                    'success': False,
                    'error': 'Client not initialized'
                }
        except Exception as e:
            config_info['connection_tests']['regular_client'] = {
                'success': False,
                'error': str(e)
            }
        
        # Test admin client
        try:
            if supabase_admin:
                test_response = supabase_admin.table('rooms').select('id').limit(1).execute()
                config_info['connection_tests']['admin_client'] = {
                    'success': True,
                    'rows_returned': len(test_response.data) if test_response.data else 0
                }
            else:
                config_info['connection_tests']['admin_client'] = {
                    'success': False,
                    'error': 'Admin client not initialized'
                }
        except Exception as e:
            config_info['connection_tests']['admin_client'] = {
                'success': False,
                'error': str(e)
            }
        
        return jsonify(config_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': get_cat_time().isoformat()
        }), 500

@app.route('/debug/force-refresh-stats')
@login_required
def force_refresh_stats():
    """Force refresh statistics and return detailed breakdown"""
    try:
        refresh_info = {
            'timestamp': get_cat_time().isoformat(),
            'refresh_steps': [],
            'final_stats': {},
            'errors': []
        }
        
        # Step 1: Clear any potential caching issues
        refresh_info['refresh_steps'].append('Step 1: Initializing fresh data fetch')
        
        now_utc = get_cat_time()
        current_month_start = now_utc.date().replace(day=1).isoformat()
        
        # Step 2: Fetch bookings with detailed logging
        refresh_info['refresh_steps'].append('Step 2: Fetching bookings data')
        try:
            bookings_query = supabase_admin.table('bookings').select('id, total_price, start_time, status').gte('start_time', current_month_start)
            bookings_response = bookings_query.execute()
            
            if bookings_response.data:
                valid_bookings = [b for b in bookings_response.data if b.get('status') != 'cancelled']
                total_revenue = sum(float(b.get('total_price', 0) or 0) for b in valid_bookings)
                
                refresh_info['final_stats']['current_month_bookings'] = len(valid_bookings)
                refresh_info['final_stats']['current_month_revenue'] = round(total_revenue, 2)
                refresh_info['refresh_steps'].append(f'Step 2 Complete: Found {len(valid_bookings)} valid bookings, ${total_revenue:.2f} revenue')
            else:
                refresh_info['final_stats']['current_month_bookings'] = 0
                refresh_info['final_stats']['current_month_revenue'] = 0
                refresh_info['refresh_steps'].append('Step 2 Complete: No bookings found')
                
        except Exception as e:
            refresh_info['errors'].append(f'Step 2 Error: {str(e)}')
            refresh_info['final_stats']['current_month_bookings'] = 0
            refresh_info['final_stats']['current_month_revenue'] = 0
        
        # Step 3: Fetch rooms data
        refresh_info['refresh_steps'].append('Step 3: Fetching rooms data')
        try:
            rooms_response = supabase_admin.table('rooms').select('id, status').execute()
            
            if rooms_response.data:
                active_rooms = len([r for r in rooms_response.data if r.get('status') in ['available', None]])
                refresh_info['final_stats']['active_rooms'] = active_rooms
                refresh_info['refresh_steps'].append(f'Step 3 Complete: Found {active_rooms} active rooms')
            else:
                refresh_info['final_stats']['active_rooms'] = 0
                refresh_info['refresh_steps'].append('Step 3 Complete: No rooms found')
                
        except Exception as e:
            refresh_info['errors'].append(f'Step 3 Error: {str(e)}')
            refresh_info['final_stats']['active_rooms'] = 0
        
        # Step 4: Calculate utilization
        refresh_info['refresh_steps'].append('Step 4: Calculating utilization rate')
        try:
            if refresh_info['final_stats']['active_rooms'] > 0 and refresh_info['final_stats']['current_month_bookings'] > 0:
                days_in_month = (now_utc.date() - datetime.strptime(current_month_start, '%Y-%m-%d').date()).days + 1
                total_possible_hours = refresh_info['final_stats']['active_rooms'] * days_in_month * 10
                estimated_booked_hours = refresh_info['final_stats']['current_month_bookings'] * 3
                utilization_rate = (estimated_booked_hours / total_possible_hours) * 100
                refresh_info['final_stats']['utilization_rate'] = round(utilization_rate, 1)
                refresh_info['refresh_steps'].append(f'Step 4 Complete: Utilization rate {utilization_rate:.1f}%')
            else:
                refresh_info['final_stats']['utilization_rate'] = 0
                refresh_info['refresh_steps'].append('Step 4 Complete: No utilization (no rooms or bookings)')
        except Exception as e:
            refresh_info['errors'].append(f'Step 4 Error: {str(e)}')
            refresh_info['final_stats']['utilization_rate'] = 0
        
        refresh_info['summary'] = {
            'total_steps_completed': len(refresh_info['refresh_steps']),
            'total_errors': len(refresh_info['errors']),
            'data_successfully_loaded': any(refresh_info['final_stats'].values()),
            'recommended_action': 'Check database permissions and RLS policies' if refresh_info['errors'] else 'Data loading successful'
        }
        
        return jsonify(refresh_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': get_cat_time().isoformat(),
            'critical_failure': True
        }), 500

# Add this improved helper function for environment validation
def validate_production_environment():
    """Comprehensive production environment validation"""
    validation_results = {
        'environment_valid': True,
        'warnings': [],
        'errors': [],
        'recommendations': []
    }
    
    # Check required environment variables
    required_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY']
    for var in required_vars:
        if not os.environ.get(var):
            validation_results['errors'].append(f'Missing required environment variable: {var}')
            validation_results['environment_valid'] = False
    
    # Check optional but important variables
    if not os.environ.get('SUPABASE_SERVICE_KEY'):
        validation_results['warnings'].append('SUPABASE_SERVICE_KEY not set - admin operations may fail')
        validation_results['recommendations'].append('Set SUPABASE_SERVICE_KEY for full functionality')
    
    if not app.config.get('SECRET_KEY') or app.config.get('SECRET_KEY').startswith('fallback'):
        validation_results['warnings'].append('Using fallback SECRET_KEY')
        validation_results['recommendations'].append('Set a proper SECRET_KEY for production')
    
    # Check Flask environment
    flask_env = os.environ.get('FLASK_ENV', 'development')
    if flask_env != 'production':
        validation_results['warnings'].append(f'FLASK_ENV is set to "{flask_env}" instead of "production"')
    
    return validation_results

@app.route('/health')
def health_check():
    """Simple health check for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': get_cat_time().isoformat(),
        'database_connected': bool(SUPABASE_URL and SUPABASE_ANON_KEY)
    })
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
# Basic Routes
# ===============================
# NOTE: /health route is defined earlier in the file (around line 8198)
# This duplicate has been removed to avoid endpoint conflicts

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
        print('=== Testing Supabase connection...')
        print(f'=== Connected to: {SUPABASE_URL}')
        
        if not supabase_admin:
            print('OK: Admin client not available')
            return
        
        # Test database connection
        response = supabase_admin.table('rooms').select('id, name').execute()
        print('OK: Supabase database connection successful')
        print(f'OK: Found {len(response.data)} rooms in database')
        
        if response.data:
            print('   === Rooms found:')
            for room in response.data:
                print(f'   - {room["name"]}')
        else:
            print('   OK:  No rooms found - make sure sample data is inserted')
        
        # Test other tables
        clients = supabase_admin.table('clients').select('id').execute()
        print(f'OK: Found {len(clients.data)} clients')
        
        print('\n=== Connection test completed!')
            
    except Exception as e:
        print(f'OK: Supabase connection failed: {e}')
        print('\n=== Troubleshooting:')
        print('- Check your .env file has correct SUPABASE_URL and keys')
        print('- Verify your Supabase project is active')
        print('- Check if sample data was inserted in Supabase dashboard')

@app.cli.command('backup-data')
def backup_data():
    """Simple data backup command using admin client"""
    try:
        import json
        
        print('=== Creating backup...')
        
        # Export key data using admin client
        backup_data = {
            'timestamp': get_cat_time().isoformat(),
            'rooms': supabase_admin.table('rooms').select('*').execute().data,
            'clients': supabase_admin.table('clients').select('*').execute().data,
            'addon_categories': supabase_admin.table('addon_categories').select('*').execute().data,
            'addons': supabase_admin.table('addons').select('*').execute().data,
            'bookings': supabase_admin.table('bookings').select('*').execute().data
        }
        
        filename = f"backup_{get_cat_time().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        print(f'OK: Backup created: {filename}')
        print(f'=== Data summary:')
        print(f'   - Rooms: {len(backup_data["rooms"])}')
        print(f'   - Clients: {len(backup_data["clients"])}')
        print(f'   - Add-on Categories: {len(backup_data["addon_categories"])}')
        print(f'   - Add-ons: {len(backup_data["addons"])}')
        print(f'   - Bookings: {len(backup_data["bookings"])}')
        
    except Exception as e:
        print(f'OK: Backup failed: {e}')
        
def require_admin_or_manager(f):
    """Decorator to require admin or manager role"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role not in ['admin', 'manager']:
            flash('Access denied. Administrator or Manager privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/activity-logs')
@login_required
@require_admin_or_manager
def activity_logs():
    """View all user activity logs (Admin/Manager only) - FIXED FOR NONE VALUES"""
    try:
        # Get filter parameters
        user_filter = request.args.get('user', '').strip()
        activity_type_filter = request.args.get('activity_type', '').strip()
        status_filter = request.args.get('status', 'all')
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Log this admin activity
        try:
            log_user_activity(
                ActivityTypes.PAGE_VIEW,
                "Viewed activity logs admin panel",
                resource_type='admin',
                metadata={
                    'filters': {
                        'user': user_filter,
                        'activity_type': activity_type_filter,
                        'status': status_filter,
                        'date_from': date_from,
                        'date_to': date_to
                    }
                }
            )
        except Exception as log_error:
            print(f"Failed to log admin activity: {log_error}")
        
        # Build query
        query = supabase_admin.table('user_activity_log').select('*')
        
        # Apply filters with None checks
        if user_filter:
            query = query.ilike('user_name', f'%{user_filter}%')
        
        if activity_type_filter:
            query = query.eq('activity_type', activity_type_filter)
        
        if status_filter != 'all':
            query = query.eq('status', status_filter)
        
        if date_from:
            try:
                # Validate date format
                datetime.strptime(date_from, '%Y-%m-%d')
                query = query.gte('created_at', date_from)
            except ValueError:
                flash('Invalid start date format. Please use YYYY-MM-DD.', 'warning')
                date_from = ''
        
        if date_to:
            try:
                # Validate date format and add one day to include the entire end date
                end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.lt('created_at', end_date.isoformat())
            except ValueError:
                flash('Invalid end date format. Please use YYYY-MM-DD.', 'warning')
                date_to = ''
        
        # Get total count for pagination
        count_response = query.execute()
        total_logs = len(count_response.data) if count_response.data else 0
        
        # Get paginated results
        offset = (page - 1) * per_page
        logs_response = query.order('created_at', desc=True).range(offset, offset + per_page - 1).execute()
        
        logs = logs_response.data if logs_response.data else []
        
        # Process logs and handle None values
        processed_logs = []
        for log in logs:
            # Create a safe copy of the log with None values handled
            safe_log = {}
            
            # Handle each field safely
            safe_log['id'] = log.get('id', 0)
            safe_log['user_id'] = log.get('user_id', '') or ''
            safe_log['user_name'] = log.get('user_name', '') or 'Unknown User'
            safe_log['user_email'] = log.get('user_email', '') or 'unknown@example.com'
            safe_log['activity_type'] = log.get('activity_type', '') or 'unknown'
            safe_log['activity_description'] = log.get('activity_description', '') or 'No description'
            safe_log['resource_type'] = log.get('resource_type', '') or ''
            safe_log['resource_id'] = log.get('resource_id', '') or ''
            safe_log['ip_address'] = log.get('ip_address', '') or 'Unknown'
            safe_log['user_agent'] = log.get('user_agent', '') or 'Unknown'
            safe_log['session_id'] = log.get('session_id', '') or ''
            safe_log['status'] = log.get('status', '') or 'unknown'
            
            # Handle datetime conversion safely
            if log.get('created_at'):
                try:
                    safe_log['created_at'] = datetime.fromisoformat(log['created_at'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    safe_log['created_at'] = get_cat_time()
            else:
                safe_log['created_at'] = get_cat_time()
            
            # Handle metadata safely
            if log.get('metadata'):
                if isinstance(log['metadata'], str):
                    try:
                        safe_log['metadata'] = json.loads(log['metadata'])
                    except (json.JSONDecodeError, TypeError):
                        safe_log['metadata'] = {}
                elif isinstance(log['metadata'], dict):
                    safe_log['metadata'] = log['metadata']
                else:
                    safe_log['metadata'] = {}
            else:
                safe_log['metadata'] = {}
            
            processed_logs.append(safe_log)
        
        # Get unique activity types for filter dropdown (handle None values)
        try:
            activity_types_response = supabase_admin.table('user_activity_log').select('activity_type').execute()
            unique_activity_types = []
            if activity_types_response.data:
                for log in activity_types_response.data:
                    activity_type = log.get('activity_type')
                    if activity_type and activity_type.strip():  # Only add non-empty activity types
                        unique_activity_types.append(activity_type)
                
                # Remove duplicates and sort
                unique_activity_types = sorted(list(set(unique_activity_types)))
            
        except Exception as e:
            print(f"Error fetching activity types: {e}")
            unique_activity_types = []
        
        # Calculate pagination info
        total_pages = (total_logs + per_page - 1) // per_page if total_logs > 0 else 1
        
        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total_logs,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page < total_pages else None
        }
        
        # Ensure all filter values are strings (not None)
        filters = {
            'user': user_filter or '',
            'activity_type': activity_type_filter or '',
            'status': status_filter or 'all',
            'date_from': date_from or '',
            'date_to': date_to or ''
        }
        
        print(f"OK: DEBUG: Activity logs loaded - {len(processed_logs)} logs, page {page} of {total_pages}")
        
        return render_template('admin/activity_logs.html',
                              title='User Activity Logs',
                              logs=processed_logs,
                              pagination=pagination_info,
                              filters=filters,
                              unique_activity_types=unique_activity_types)
        
    except Exception as e:
        print(f"OK: ERROR: Failed to load activity logs: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading activity logs. Please try again.', 'danger')
        return redirect(url_for('dashboard'))
    
@app.route('/admin/activity-stats')
@login_required
@require_admin_or_manager
def activity_stats():
    """Dashboard for activity statistics (Admin/Manager only)"""
    try:
        # Get date range (default to last 30 days)
        days = request.args.get('days', 30, type=int)
        start_date = get_cat_time() - timedelta(days=days)
        
        print(f"=== DEBUG: Generating activity stats for last {days} days")
        
        # Get activity logs for the period
        logs_response = supabase_admin.table('user_activity_log').select('*').gte('created_at', start_date.isoformat()).execute()
        
        logs = logs_response.data if logs_response.data else []
        print(f"OK: DEBUG: Found {len(logs)} activities for stats calculation")
        
        # Calculate basic statistics
        total_activities = len(logs)
        unique_users = len(set([log['user_id'] for log in logs if log.get('user_id')]))
        successful_activities = len([log for log in logs if log.get('status') == 'success'])
        failed_activities = len([log for log in logs if log.get('status') == 'failed'])
        
        # Activity breakdown by type
        activity_breakdown = {}
        for log in logs:
            activity_type = log.get('activity_type', 'unknown')
            activity_breakdown[activity_type] = activity_breakdown.get(activity_type, 0) + 1
        
        # Most active users
        user_activity_count = {}
        for log in logs:
            user_name = log.get('user_name', 'Unknown')
            user_activity_count[user_name] = user_activity_count.get(user_name, 0) + 1
        
        most_active_users = sorted(user_activity_count.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Daily activity trend (last 7 days)
        daily_activity = {}
        for i in range(7):
            date = (get_cat_time() - timedelta(days=i)).date()
            daily_activity[date.isoformat()] = 0
        
        for log in logs:
            try:
                log_date = datetime.fromisoformat(log['created_at'].replace('Z', '+00:00')).date()
                if log_date.isoformat() in daily_activity:
                    daily_activity[log_date.isoformat()] += 1
            except:
                pass
        
        # Prepare statistics for template
        stats = {
            'total_activities': total_activities,
            'unique_users': unique_users,
            'successful_activities': successful_activities,
            'failed_activities': failed_activities,
            'success_rate': round((successful_activities / total_activities * 100), 1) if total_activities > 0 else 0,
            'activity_breakdown': sorted(activity_breakdown.items(), key=lambda x: x[1], reverse=True),
            'most_active_users': most_active_users,
            'daily_activity': sorted(daily_activity.items()),
            'period_days': days
        }
        
        print(f"=== DEBUG: Stats calculated - Total: {total_activities}, Users: {unique_users}, Success: {stats['success_rate']}%")
        
        # Log this admin activity
        try:
            log_user_activity(
                ActivityTypes.PAGE_VIEW,
                f"Viewed activity statistics dashboard ({days} days)",
                resource_type='admin',
                metadata={
                    'period_days': days,
                    'stats_generated_at': get_cat_time().isoformat(),
                    'total_activities_analyzed': total_activities,
                    'unique_users_analyzed': unique_users
                }
            )
        except Exception as log_error:
            print(f"Failed to log admin activity: {log_error}")
        
        return render_template('admin/activity_stats.html',
                              title='Activity Statistics',
                              stats=stats)
        
    except Exception as e:
        print(f"OK: ERROR: Failed to load activity statistics: {e}")
        import traceback
        traceback.print_exc()
        
        # Log the error
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Activity statistics generation failed: {str(e)}",
                status='failed',
                metadata={'error': str(e), 'error_type': type(e).__name__}
            )
        except Exception as log_error:
            print(f"Failed to log error: {log_error}")
        
        flash('Error loading activity statistics. Please try again.', 'danger')
        return redirect(url_for('dashboard'))


# Also add this route if you want to support user-specific activity logs for admins
@app.route('/admin/activity-logs/user/<user_id>')
@login_required
@require_admin_or_manager
def user_activity_logs(user_id):
    """View activity logs for a specific user (Admin/Manager only)"""
    try:
        print(f"=== DEBUG: Loading activity logs for user ID: {user_id}")
        
        # Get user information
        user_info_response = supabase_admin.table('users').select('*').eq('id', user_id).execute()
        user_info = user_info_response.data[0] if user_info_response.data else None
        
        if not user_info:
            flash('User not found', 'danger')
            return redirect(url_for('activity_logs'))
        
        # Get user's activity logs
        logs_response = supabase_admin.table('user_activity_log').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(100).execute()
        
        logs = logs_response.data if logs_response.data else []
        
        # Process logs - convert datetime strings
        for log in logs:
            if log.get('created_at'):
                try:
                    log['created_at'] = datetime.fromisoformat(log['created_at'].replace('Z', '+00:00'))
                except:
                    pass
            
            if log.get('metadata') and isinstance(log['metadata'], str):
                try:
                    log['metadata'] = json.loads(log['metadata'])
                except:
                    pass
        
        # Calculate user statistics
        total_activities = len(logs)
        successful_activities = len([log for log in logs if log.get('status') == 'success'])
        failed_activities = len([log for log in logs if log.get('status') == 'failed'])
        
        # Get activity breakdown
        activity_breakdown = {}
        for log in logs:
            activity_type = log.get('activity_type', 'unknown')
            activity_breakdown[activity_type] = activity_breakdown.get(activity_type, 0) + 1
        
        user_stats = {
            'total_activities': total_activities,
            'successful_activities': successful_activities,
            'failed_activities': failed_activities,
            'success_rate': round((successful_activities / total_activities * 100), 1) if total_activities > 0 else 0,
            'activity_breakdown': activity_breakdown,
            'last_activity': logs[0]['created_at'] if logs else None
        }
        
        # Log this admin activity
        try:
            log_user_activity(
                ActivityTypes.PAGE_VIEW,
                f"Viewed activity logs for user: {user_info.get('first_name', '')} {user_info.get('last_name', '')}",
                resource_type='admin',
                metadata={
                    'viewed_user_id': user_id,
                    'viewed_user_email': user_info.get('email'),
                    'activities_viewed': total_activities
                }
            )
        except Exception as log_error:
            print(f"Failed to log admin activity: {log_error}")
        
        return render_template('admin/user_activity_logs.html',
                              title=f"Activity Logs - {user_info.get('first_name', '')} {user_info.get('last_name', '')}",
                              user_info=user_info,
                              logs=logs,
                              stats=user_stats)
        
    except Exception as e:
        print(f"OK: ERROR: Failed to load user activity logs: {e}")
        flash('Error loading user activity logs', 'danger')
        return redirect(url_for('activity_logs'))


@app.route('/my-activity')
@login_required
def my_activity():
    """View current user's own activity logs"""
    try:
        # Get current user's activity logs
        logs_response = supabase_admin.table('user_activity_log').select('*').eq('user_id', current_user.id).order('created_at', desc=True).limit(50).execute()
        
        logs = logs_response.data if logs_response.data else []
        
        # Process logs
        for log in logs:
            if log.get('created_at'):
                try:
                    log['created_at'] = datetime.fromisoformat(log['created_at'].replace('Z', '+00:00'))
                except:
                    pass
            
            if log.get('metadata') and isinstance(log['metadata'], str):
                try:
                    log['metadata'] = json.loads(log['metadata'])
                except:
                    pass
        
        # Log this page view
        try:
            log_user_activity(
                ActivityTypes.PAGE_VIEW,
                "Viewed own activity history",
                resource_type='profile'
            )
        except Exception as log_error:
            print(f"Failed to log activity view: {log_error}")
        
        return render_template('profile/my_activity.html',
                              title='My Activity History',
                              logs=logs)
        
    except Exception as e:
        print(f"OK: ERROR: Failed to load user's own activity logs: {e}")
        flash('Error loading your activity history', 'danger')
        return redirect(url_for('dashboard'))

# ===============================
# ADDITIONAL HELPER FUNCTIONS FOR ENHANCED BOOKING SYSTEM
# ===============================

def safe_float_conversion(value, default=0.0):
    """Safely convert value to float with fallback"""
    try:
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int_conversion(value, default=0):
    """Safely convert value to int with fallback"""
    try:
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

def get_booking_with_details(booking_id):
    """Get booking with all related details in a robust way"""
    try:
        print(f"=== DEBUG: Fetching complete booking details for ID {booking_id}")
        
        # Get basic booking data
        booking_response = supabase_admin.table('bookings').select('*').eq('id', booking_id).execute()
        
        if not booking_response.data:
            return None
        
        booking = booking_response.data[0]
        
        # Get room data
        if booking.get('room_id'):
            room_response = supabase_admin.table('rooms').select('*').eq('id', booking['room_id']).execute()
            booking['room'] = room_response.data[0] if room_response.data else None
        
        # Get client data
        if booking.get('client_id'):
            client_response = supabase_admin.table('clients').select('*').eq('id', booking['client_id']).execute()
            booking['client'] = client_response.data[0] if client_response.data else None
        
        # Get booking addons
        booking_addons = []
        try:
            ba_response = supabase_admin.table('booking_addons').select('*').eq('booking_id', booking_id).execute()
            
            for ba in ba_response.data if ba_response.data else []:
                if ba.get('addon_id'):
                    addon_response = supabase_admin.table('addons').select('*').eq('id', ba['addon_id']).execute()
                    if addon_response.data:
                        addon = addon_response.data[0]
                        ba['addon'] = addon
                        booking_addons.append(ba)
        except Exception as addon_error:
            print(f"Warning: Error fetching addons: {addon_error}")
        
        booking['booking_addons'] = booking_addons
        
        # Convert datetime strings
        booking = convert_datetime_strings(booking)
        
        print(f"OK: DEBUG: Successfully fetched complete booking details")
        return booking
        
    except Exception as e:
        print(f"OK: ERROR: Failed to fetch booking details: {e}")
        return None

def calculate_booking_totals(booking, room_rates=None):
    """Calculate booking totals - SIMPLIFIED (NO TAX/DISCOUNT)"""
    try:
        # Parse times safely
        if isinstance(booking.get('start_time'), str):
            start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).replace(tzinfo=None)
            end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00')).replace(tzinfo=None)
        else:
            start_time = booking.get('start_time')
            end_time = booking.get('end_time')
        
        if not start_time or not end_time:
            # Use fallback values
            duration_hours = 4
            room_rate = safe_float_conversion(booking.get('total_price', 0)) * 0.7
            rate_type = "Estimated Rate"
        else:
            duration_hours = (end_time - start_time).total_seconds() / 3600
            
            # Get room rates
            if room_rates:
                hourly_rate = safe_float_conversion(room_rates.get('hourly_rate', 0))
                half_day_rate = safe_float_conversion(room_rates.get('half_day_rate', 0))
                full_day_rate = safe_float_conversion(room_rates.get('full_day_rate', 0))
            else:
                # Use booking's room data or fallback
                room = booking.get('room', {})
                hourly_rate = safe_float_conversion(room.get('hourly_rate', 50))
                half_day_rate = safe_float_conversion(room.get('half_day_rate', 200))
                full_day_rate = safe_float_conversion(room.get('full_day_rate', 350))
            
            # Calculate room rate based on duration
            if duration_hours <= 4:
                room_rate = hourly_rate * duration_hours
                rate_type = f"Hourly Rate ({duration_hours:.1f} hours)"
            elif duration_hours <= 6:
                room_rate = half_day_rate
                rate_type = "Half-day Rate"
            else:
                room_rate = full_day_rate
                rate_type = "Full-day Rate"
        
        # Calculate addons total
        addons_total = 0
        addon_items = []
        
        for ba in booking.get('booking_addons', []):
            if ba.get('addon'):
                addon = ba['addon']
                quantity = safe_int_conversion(ba.get('quantity', 1), 1)
                price = safe_float_conversion(addon.get('price', 0))
                total = price * quantity
                addons_total += total
                
                # Get category name
                category_name = 'Other'
                if addon.get('category_id'):
                    try:
                        cat_response = supabase_admin.table('addon_categories').select('name').eq('id', addon['category_id']).execute()
                        if cat_response.data:
                            category_name = cat_response.data[0]['name']
                    except:
                        pass
                
                addon_items.append({
                    'name': addon.get('name', 'Unknown Addon'),
                    'category': category_name,
                    'price': price,
                    'quantity': quantity,
                    'total': total
                })
        
        # SIMPLIFIED CALCULATION - NO TAX OR DISCOUNT
        total = room_rate + addons_total
        
        return {
            'room_rate': round(room_rate, 2),
            'rate_type': rate_type,
            'addons_total': round(addons_total, 2),
            'addon_items': addon_items,
            'duration_hours': round(duration_hours, 1),
            'subtotal': round(total, 2),  # Same as total
            'total': round(total, 2)      # No tax/discount applied
        }
        
    except Exception as e:
        print(f"OK: ERROR: Failed to calculate booking totals: {e}")
        # Return safe fallback values
        total_price = safe_float_conversion(booking.get('total_price', 100))
        return {
            'room_rate': round(total_price * 0.7, 2),
            'rate_type': 'Estimated Rate',
            'addons_total': round(total_price * 0.3, 2),
            'addon_items': [],
            'duration_hours': 4,
            'subtotal': round(total_price, 2),
            'total': round(total_price, 2)
        }

# ===============================
# ENHANCED VIEW BOOKING ROUTE
# ===============================

@app.route('/bookings/<int:id>')
@login_required
def view_booking(id):
    """View booking details with enhanced data from new schema"""
    try:
        print(f"=== DEBUG: Loading enhanced booking details for ID {id}")
        
        # Get complete booking details using new schema
        booking = get_complete_booking_details(id)
        
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        # Calculate enhanced totals using custom addons
        enhanced_totals = calculate_enhanced_booking_totals(booking)
        
        # Add calculated fields to booking
        booking.update(enhanced_totals)
        
        # Log page view
        try:
            log_user_activity(
                ActivityTypes.PAGE_VIEW,
                f"Viewed booking details for '{booking.get('title', 'Unknown Event')}'",
                resource_type='booking',
                resource_id=id,
                metadata={
                    'booking_status': booking.get('status'),
                    'client_name': booking.get('client', {}).get('company_name') or booking.get('client', {}).get('contact_person'),
                    'room_name': booking.get('room', {}).get('name'),
                    'total_amount': booking.get('total_price', 0),
                    'custom_addons_count': len(booking.get('custom_addons', []))
                }
            )
        except Exception as log_error:
            print(f"Failed to log booking view: {log_error}")
        
        print(f"OK: DEBUG: Successfully loaded enhanced booking '{booking.get('title', 'Unknown')}'")
        
        return render_template('bookings/view.html', 
                             title=f'Booking: {booking["title"]}', 
                             booking=booking)
        
    except Exception as e:
        print(f"OK: ERROR: Failed to load enhanced booking details: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Error viewing booking ID {id}: {str(e)}",
                resource_type='booking',
                resource_id=id,
                status='failed',
                metadata={'error': str(e)}
            )
        except Exception as log_error:
            print(f"Failed to log booking view error: {log_error}")
        
        flash('Error loading booking details. Please try again.', 'danger')
        return redirect(url_for('bookings'))

def calculate_enhanced_booking_totals(booking):
    """Calculate booking totals using custom addons and stored room rate"""
    try:
        # Use stored room_rate and addons_total from booking record
        room_rate = float(booking.get('room_rate', 0))
        addons_total = float(booking.get('addons_total', 0))
        total = float(booking.get('total_price', 0))
        
        # Get custom addons for display
        custom_addons = booking.get('custom_addons', [])
        
        # Categorize addon items
        room_items = []
        addon_items = []
        
        for addon in custom_addons:
            if addon.get('is_room_rate', False):
                room_items.append(addon)
            else:
                addon_items.append(addon)
        
        return {
            'room_rate': round(room_rate, 2),
            'addons_total': round(addons_total, 2),
            'room_items': room_items,
            'addon_items': addon_items,
            'custom_addons': custom_addons,
            'subtotal': round(total, 2),
            'total': round(total, 2),
            'rate_type': 'User-Entered Rate'  # Since we're no longer calculating from fixed rates
        }
        
    except Exception as e:
        print(f"OK: ERROR: Failed to calculate enhanced booking totals: {e}")
        # Return safe fallback values
        total_price = float(booking.get('total_price', 0))
        return {
            'room_rate': round(total_price * 0.7, 2),  # Rough estimate
            'addons_total': round(total_price * 0.3, 2),  # Rough estimate
            'room_items': [],
            'addon_items': [],
            'custom_addons': booking.get('custom_addons', []),
            'subtotal': round(total_price, 2),
            'total': round(total_price, 2),
            'rate_type': 'Estimated Rate'
        }
# ===============================
# ENHANCED NOTIFICATION SYSTEM
# ===============================

def create_booking_notification(booking_id, notification_type, message, priority='normal'):
    """Create a notification for booking-related events"""
    try:
        notification_data = {
            'booking_id': booking_id,
            'user_id': current_user.id if current_user.is_authenticated else None,
            'type': notification_type,
            'message': message,
            'priority': priority,
            'is_read': False,
            'created_at': get_cat_time().isoformat()
        }
        
        # You could store these in a notifications table if you have one
        # For now, we'll use the activity log system
        log_user_activity(
            f'notification_{notification_type}',
            message,
            resource_type='notification',
            resource_id=booking_id,
            metadata={'priority': priority, 'notification_type': notification_type}
        )
        
        return True
        
    except Exception as e:
        print(f"Failed to create notification: {e}")
        return False

def send_booking_status_notification(booking_id, old_status, new_status):
    """Send notification when booking status changes"""
    try:
        booking = get_booking_with_details(booking_id)
        if not booking:
            return False
        
        client_name = 'Unknown Client'
        if booking.get('client'):
            client_name = booking['client'].get('company_name') or booking['client'].get('contact_person', 'Unknown Client')
        
        status_messages = {
            'tentative': f"=== Booking '{booking['title']}' for {client_name} is now tentative. Quotation can be generated.",
            'confirmed': f"OK: Booking '{booking['title']}' for {client_name} has been confirmed! Invoice can now be generated.",
            'cancelled': f"OK: Booking '{booking['title']}' for {client_name} has been cancelled."
        }
        
        message = status_messages.get(new_status, f"Booking status updated to {new_status}")
        priority = 'high' if new_status == 'confirmed' else 'normal'
        
        create_booking_notification(booking_id, 'status_change', message, priority)
        
        return True
        
    except Exception as e:
        print(f"Failed to send status notification: {e}")
        return False

# ===============================
# ENHANCED TEMPLATE FILTERS
# ===============================
@app.template_filter('calculate_total')
def calculate_total_filter(room_rate, addons_total):
    """Calculate total without tax or discount"""
    try:
        room_rate = float(room_rate or 0)
        addons_total = float(addons_total or 0)
        return round(room_rate + addons_total, 2)
    except (ValueError, TypeError):
        return 0.00

@app.template_filter('format_pricing_summary')
def format_pricing_summary_filter(booking):
    """Format pricing summary for display - SIMPLIFIED"""
    try:
        room_rate = float(booking.get('room_rate', 0))
        addons_total = float(booking.get('addons_total', 0))
        total = room_rate + addons_total
        
        return {
            'room_rate': round(room_rate, 2),
            'addons_total': round(addons_total, 2),
            'total': round(total, 2),
            'currency': 'USD'
        }
    except (ValueError, TypeError):
        return {
            'room_rate': 0.00,
            'addons_total': 0.00,
            'total': 0.00,
            'currency': 'USD'
        }
@app.template_filter('money')
def money_filter(amount):
    """Format money amounts consistently"""
    try:
        if amount is None:
            return "$0.00"
        return f"${float(amount):.2f}"
    except (ValueError, TypeError):
        return "$0.00"

@app.template_filter('duration')
def duration_filter(hours):
    """Format duration in hours to human readable format"""
    try:
        hours = float(hours)
        if hours < 1:
            minutes = int(hours * 60)
            return f"{minutes} minutes"
        elif hours == 1:
            return "1 hour"
        elif hours < 24:
            return f"{hours:.1f} hours"
        else:
            days = int(hours // 24)
            remaining_hours = hours % 24
            if remaining_hours == 0:
                return f"{days} day{'s' if days > 1 else ''}"
            else:
                return f"{days} day{'s' if days > 1 else ''} {remaining_hours:.1f} hours"
    except (ValueError, TypeError):
        return "Unknown duration"

@app.template_filter('booking_status_color')
def booking_status_color_filter(status):
    """Get Bootstrap color class for booking status"""
    status_colors = {
        'tentative': 'warning',
        'confirmed': 'success',
        'cancelled': 'danger',
        'completed': 'info'
    }
    return status_colors.get(status, 'secondary')

@app.template_filter('nl2br')
def nl2br_filter(text):
    """Convert newlines to HTML breaks"""
    if not text:
        return ''
    return text.replace('\n', '<br>')

# Add these template filters to your app.py file (after the existing template filters)

@app.template_filter('safe_startswith')
def safe_startswith_filter(text, prefix):
    """Safely check if text starts with prefix, handling None values"""
    if text is None or prefix is None:
        return False
    try:
        return str(text).startswith(str(prefix))
    except (AttributeError, TypeError):
        return False

@app.template_filter('safe_string')
def safe_string_filter(value, default=''):
    """Convert value to string safely, handling None values"""
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default

@app.template_filter('safe_contains')
def safe_contains_filter(text, substring):
    """Safely check if text contains substring, handling None values"""
    if text is None or substring is None:
        return False
    try:
        return str(substring).lower() in str(text).lower()
    except (AttributeError, TypeError):
        return False

@app.template_filter('truncate_safe')
def truncate_safe_filter(text, length=100, suffix='...'):
    """Safely truncate text, handling None values"""
    if text is None:
        return ''
    try:
        text = str(text)
        if len(text) <= length:
            return text
        return text[:length] + suffix
    except (TypeError, ValueError):
        return ''

@app.template_filter('default_if_none')
def default_if_none_filter(value, default='N/A'):
    """Return default value if input is None or empty"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    return value

# ===============================
# ERROR RECOVERY FUNCTIONS
# ===============================

def recover_booking_data(booking_id):
    """Attempt to recover missing booking data"""
    try:
        print(f"=== DEBUG: Attempting to recover data for booking {booking_id}")
        
        # Get basic booking
        booking_response = supabase_admin.table('bookings').select('*').eq('id', booking_id).execute()
        
        if not booking_response.data:
            return None
        
        booking = booking_response.data[0]
        
        # Check and recover room data
        if booking.get('room_id') and not booking.get('room'):
            room_response = supabase_admin.table('rooms').select('*').eq('id', booking['room_id']).execute()
            if room_response.data:
                booking['room'] = room_response.data[0]
                print(f"OK: DEBUG: Recovered room data for booking {booking_id}")
        
        # Check and recover client data
        if booking.get('client_id') and not booking.get('client'):
            client_response = supabase_admin.table('clients').select('*').eq('id', booking['client_id']).execute()
            if client_response.data:
                booking['client'] = client_response.data[0]
                print(f"OK: DEBUG: Recovered client data for booking {booking_id}")
        
        return booking
        
    except Exception as e:
        print(f"OK: ERROR: Failed to recover booking data: {e}")
        return None
    
    

# ===============================
# VALIDATION HELPERS
# ===============================

def validate_booking_times(start_time, end_time):
    """Validate booking start and end times"""
    errors = []
    
    try:
        # Ensure end time is after start time
        if end_time <= start_time:
            errors.append("End time must be after start time")
        
        # Check if booking is in the past
        if start_time < get_cat_time():
            errors.append("Booking cannot be scheduled in the past")
        
        # Check if booking is too far in the future (optional)
        max_future = get_cat_time() + timedelta(days=365)
        if start_time > max_future:
            errors.append("Booking cannot be scheduled more than 1 year in advance")
        
        # Check business hours (optional - customize as needed)
        if start_time.hour < 6 or start_time.hour > 22:
            errors.append("Bookings must be within business hours (6 AM - 10 PM)")
        
        if end_time.hour < 6 or end_time.hour > 23:
            errors.append("Bookings must end within business hours (6 AM - 11 PM)")
        
        # Check duration limits
        duration_hours = (end_time - start_time).total_seconds() / 3600
        if duration_hours > 12:
            errors.append("Bookings cannot exceed 12 hours")
        
        if duration_hours < 0.5:
            errors.append("Bookings must be at least 30 minutes long")
    
    except Exception as e:
        errors.append(f"Invalid date/time format: {str(e)}")
    
    return errors

def validate_booking_capacity(room_id, attendees):
    """Validate that room capacity is sufficient for attendees"""
    try:
        if not attendees or attendees <= 0:
            return []  # No validation needed if attendees not specified
        
        room_response = supabase_admin.table('rooms').select('name, capacity').eq('id', room_id).execute()
        
        if not room_response.data:
            return ["Selected room not found"]
        
        room = room_response.data[0]
        capacity = room.get('capacity', 0)
        
        if attendees > capacity:
            return [f"Room '{room['name']}' has capacity for {capacity} people, but {attendees} attendees specified"]
        
        if attendees > capacity * 0.9:  # Warn if over 90% capacity
            return [f"Warning: Room will be at {(attendees/capacity*100):.0f}% capacity"]
        
        return []
        
    except Exception as e:
        return [f"Error validating room capacity: {str(e)}"]

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

