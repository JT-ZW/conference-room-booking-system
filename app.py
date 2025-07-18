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
    
    # Clients
    CREATE_CLIENT = 'create_client'
    UPDATE_CLIENT = 'update_client'
    DELETE_CLIENT = 'delete_client'
    VIEW_CLIENT = 'view_client'
    
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
            if supabase_admin:
                response = supabase_admin.table('users').select('*').eq('id', self.id).execute()
                return response.data[0] if response.data else {}
        except:
            pass
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
        return self.profile.get('username', self.email.split('@')[0] if self.email else 'user')
    
    @property
    def is_active(self):
        return self.profile.get('is_active', True)
    
    def get_id(self):
        return str(self.id)

# ===============================
# Authentication Functions
# ===============================

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        if supabase_admin:
            response = supabase_admin.auth.admin.get_user_by_id(user_id)
            if response.user:
                return User(response.user.__dict__)
        return None
    except Exception as e:
        print(f"Error loading user: {e}")
        return None

def authenticate_user(email, password):
    """Authenticate user with Supabase and set up session properly"""
    try:
        print(f"DEBUG: Attempting to authenticate user: {email}")
        
        if not supabase:
            print("ERROR: Supabase client not initialized")
            return None
        
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
            session['created_at'] = datetime.now(UTC).isoformat()
            session['user_id'] = response.user.id
            session['user_email'] = response.user.email
            
            # Force session save
            session.modified = True
            
            print(f"DEBUG: Session created successfully")
            return User(response.user.__dict__)
        else:
            print("DEBUG: Authentication failed - no user or session")
            return None
            
    except Exception as e:
        print(f"DEBUG: Authentication error: {e}")
        return None

def create_user_supabase(email, password, first_name, last_name, role='staff'):
    """Create new user in Supabase with enhanced error handling"""
    try:
        print(f"DEBUG: Creating user - {email}, {first_name} {last_name}, role: {role}")
        
        if not supabase_admin:
            raise Exception("Admin client not available")
        
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
                'created_at': datetime.now(UTC).isoformat()
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

# ===============================
# Database Helper Functions
# ===============================

def supabase_select(table_name, columns="*", filters=None, order_by=None, limit=None):
    """Enhanced select function with better error handling and RLS bypass"""
    try:
        if not supabase_admin:
            raise Exception("Supabase admin client not initialized")
        
        print(f"🔍 DEBUG: Querying table '{table_name}' with admin client")
        
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
            print(f"✅ DEBUG: Successfully retrieved {len(response.data)} rows from '{table_name}'")
            return response.data
        else:
            print(f"⚠️ DEBUG: Empty response from table '{table_name}'")
            return []
            
    except Exception as e:
        print(f"❌ ERROR: Failed to query table '{table_name}': {e}")
        return []

def supabase_insert(table_name, data):
    """Insert data into Supabase table using admin client with enhanced error handling"""
    try:
        print(f"DEBUG: Inserting into table '{table_name}'")
        
        if not supabase_admin:
            raise Exception("Admin client not available")
        
        response = supabase_admin.table(table_name).insert(data).execute()
        
        if response.data:
            print(f"DEBUG: Insert successful, created {len(response.data)} row(s)")
            return response.data[0] if response.data else None
        else:
            print("DEBUG: Insert returned no data")
            return None
            
    except Exception as e:
        print(f"Insert error in supabase_insert: {e}")
        return None

def supabase_update(table_name, data, filters):
    """Update data in Supabase table using admin client with correct syntax"""
    try:
        print(f"DEBUG: Updating table '{table_name}'")
        
        if not supabase_admin:
            raise Exception("Admin client not available")
        
        query = supabase_admin.table(table_name).update(data)
        
        # Apply filters
        for filter_item in filters:
            if len(filter_item) == 3:
                column, operator, value = filter_item
                if operator == 'eq':
                    query = query.eq(column, value)
                elif operator == 'neq':
                    query = query.neq(column, value)
        
        response = query.execute()
        
        if response.data is not None:
            print(f"DEBUG: Update successful")
            return response.data
        else:
            return [{'success': True}]
                
    except Exception as e:
        print(f"Update error in supabase_update: {e}")
        return []

def supabase_delete(table_name, filters):
    """Delete data from Supabase table using admin client"""
    try:
        if not supabase_admin:
            raise Exception("Admin client not available")
        
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

# ===============================
# Client Functions
# ===============================

def get_clients_with_booking_counts():
    """Get all clients with their booking counts efficiently"""
    try:
        print("🔍 DEBUG: Fetching clients with booking counts...")
        
        if not supabase_admin:
            print("❌ ERROR: Admin client not available")
            return []
        
        # Get all clients
        clients_response = supabase_admin.table('clients').select('*').execute()
        clients = clients_response.data if clients_response.data else []
        
        if not clients:
            print("⚠️ DEBUG: No clients found in database")
            return []
        
        # Get all bookings to count efficiently
        bookings_response = supabase_admin.table('bookings').select('client_id, status').execute()
        bookings = bookings_response.data if bookings_response.data else []
        
        # Count bookings per client (excluding cancelled ones)
        booking_counts = {}
        for booking in bookings:
            client_id = booking.get('client_id')
            status = booking.get('status', '')
            
            if client_id and status != 'cancelled':
                booking_counts[client_id] = booking_counts.get(client_id, 0) + 1
        
        # Add booking counts to clients
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
        
        print(f"✅ DEBUG: Enhanced {len(clients)} clients with booking counts")
        return clients
        
    except Exception as e:
        print(f"❌ ERROR: get_clients_with_booking_counts failed: {e}")
        return []

def get_client_by_id_from_db(client_id):
    """Get specific client by ID from Supabase database"""
    try:
        print(f"🔍 DEBUG: Fetching client ID {client_id} from database...")
        
        if not supabase_admin:
            return None
        
        response = supabase_admin.table('clients').select('*').eq('id', client_id).execute()
        
        if response.data:
            print(f"✅ DEBUG: Found client: {response.data[0].get('company_name') or response.data[0].get('contact_person')}")
            return response.data[0]
        else:
            print(f"⚠️ DEBUG: Client ID {client_id} not found in database")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch client ID {client_id}: {e}")
        return None

def get_client_bookings_from_db(client_id):
    """Get all bookings for a specific client with room details"""
    try:
        print(f"🔍 DEBUG: Fetching bookings for client ID {client_id}...")
        
        if not supabase_admin:
            return []
        
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity)
        """).eq('client_id', client_id).order('start_time', desc=True).execute()
        
        if response.data:
            print(f"✅ DEBUG: Found {len(response.data)} bookings for client")
            # Convert datetime strings for template compatibility
            return convert_datetime_strings(response.data)
        else:
            print("ℹ️ DEBUG: No bookings found for this client")
            return []
            
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch client bookings: {e}")
        return []

def create_client_in_db(client_data):
    """Create a new client in Supabase database"""
    try:
        print(f"🔍 DEBUG: Creating new client: {client_data.get('company_name') or client_data.get('contact_person')}")
        
        # Ensure all required fields are present
        required_fields = ['contact_person', 'email']
        for field in required_fields:
            if not client_data.get(field):
                raise ValueError(f"Missing required field: {field}")
        
        response = supabase_insert('clients', client_data)
        
        if response:
            print(f"✅ DEBUG: Successfully created client with ID: {response['id']}")
            return response
        else:
            print("❌ DEBUG: Failed to create client - no data returned")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to create client: {e}")
        return None

def update_client_in_db(client_id, client_data):
    """Update an existing client in Supabase database"""
    try:
        print(f"🔍 DEBUG: Updating client ID {client_id}")
        
        response = supabase_update('clients', client_data, [('id', 'eq', client_id)])
        
        if response:
            print(f"✅ DEBUG: Successfully updated client ID {client_id}")
            return response[0] if response else {'success': True}
        else:
            print(f"⚠️ DEBUG: Update failed for client ID {client_id}")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to update client ID {client_id}: {e}")
        return None

def delete_client_from_db(client_id):
    """Delete a client from Supabase database (after checking for bookings)"""
    try:
        print(f"🔍 DEBUG: Attempting to delete client ID {client_id}")
        
        if not supabase_admin:
            return False, "Database not available"
        
        # First check if client has any bookings
        bookings_check = supabase_admin.table('bookings').select('id').eq('client_id', client_id).execute()
        
        if bookings_check.data:
            print(f"❌ DEBUG: Cannot delete client - has {len(bookings_check.data)} bookings")
            return False, "Cannot delete client with existing bookings"
        
        # If no bookings, proceed with deletion
        response = supabase_admin.table('clients').delete().eq('id', client_id).execute()
        
        print(f"✅ DEBUG: Successfully deleted client ID {client_id}")
        return True, "Client deleted successfully"
        
    except Exception as e:
        print(f"❌ ERROR: Failed to delete client ID {client_id}: {e}")
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
            if supabase_admin:
                existing_users = supabase_admin.table('users').select('email').eq('email', field.data.lower()).execute()
                if existing_users.data:
                    raise ValidationError('Email address already registered. Please use a different email or try logging in.')
        except Exception as e:
            print(f"Warning: Could not check email uniqueness: {e}")

class ClientForm(FlaskForm):
    """Form for adding/editing clients"""
    company_name = StringField('Company Name')
    contact_person = StringField('Contact Person', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number')
    address = TextAreaField('Address')
    notes = TextAreaField('Notes')

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
    """Main index route"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    else:
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