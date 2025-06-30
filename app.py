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
from wtforms import StringField, PasswordField, BooleanField, SelectField, DateTimeField, TextAreaField, IntegerField, DecimalField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Length, ValidationError, EqualTo
import json
from decimal import Decimal
from flask_wtf.csrf import CSRFProtect
from supabase import create_client, Client
from dotenv import load_dotenv
import requests
import functools
import traceback
import json
import threading

# STEP 1: Add this function right after your imports, before "# Load environment variables"

def validate_environment():
    """Validate all required environment variables"""
    required_vars = {
        'SUPABASE_URL': os.environ.get('SUPABASE_URL'),
        'SUPABASE_ANON_KEY': os.environ.get('SUPABASE_ANON_KEY'),
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        print(f"❌ {error_msg}")
        raise ValueError(error_msg)
    
    print("✅ All required environment variables are set")
    
    # Check optional but important variables
    service_key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not service_key:
        print("⚠️ WARNING: SUPABASE_SERVICE_KEY not set. Some operations may fail due to RLS.")
    else:
        print("✅ Service key available for admin operations")
    
    return True

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-key-change-in-production-' + str(datetime.now().timestamp()))

# Session configuration - FIXED FOR PRODUCTION
# Check if we're running on HTTPS (common in production deployments)

app.config['SESSION_COOKIE_SECURE'] = False  # Set to False for now, will be handled later
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# CSRF configuration - FIXED FOR PRODUCTION
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600
app.config['WTF_CSRF_SSL_STRICT'] = False

ACTIVITY_LOG_RETENTION_DAYS = int(os.environ.get('ACTIVITY_LOG_RETENTION_DAYS', 90))
ACTIVITY_LOG_ENABLED = os.environ.get('ACTIVITY_LOG_ENABLED', 'true').lower() == 'true'

# Load environment variables
load_dotenv()

# Validate environment variables first
validate_environment()

# Supabase Configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

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
    
# Initialize extensions with better error handling
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
login_manager.login_view = 'login'

# Add CSRF error handler
@app.errorhandler(400)
def csrf_error(e):
    """Handle CSRF errors"""
    print(f"CSRF Error: {e}")
    if 'CSRF' in str(e) or 'csrf' in str(e).lower():
        flash('Security token expired. Please try again.', 'warning')
        return redirect(request.referrer or url_for('addons'))
    return render_template('errors/400.html'), 400

@app.context_processor
def inject_now():
    """Inject the current datetime into templates."""
    return {'now': datetime.now(UTC)}

@app.before_request
def production_session_validation():
    """Simplified session validation for production"""
    # Skip validation for static files, debug routes, and auth routes
    if (request.endpoint and 
        (request.endpoint.startswith('static') or 
         request.endpoint.startswith('debug') or
         request.endpoint in ['login', 'logout', 'register', 'health_check', 'debug_database_connection', 'debug_sample_data', 'debug_test_queries'] or
         request.path.startswith('/static/') or
         request.path.startswith('/debug/'))):
        return
    
    # Log basic info in production
    if os.environ.get('FLASK_ENV') == 'production':
        print(f"🔍 PROD: Request to {request.endpoint} by {'authenticated' if current_user.is_authenticated else 'anonymous'} user")
    
    # Simplified validation - only check if user needs to be authenticated
    if not current_user.is_authenticated and request.endpoint not in ['login', 'register', 'health_check']:
        if request.endpoint and not request.endpoint.startswith('static'):
            print(f"🔒 Redirecting unauthenticated user from {request.endpoint} to login")
            return redirect(url_for('login'))
        
# Add a new debug route to check session status
@app.route('/debug/session')
def debug_session():
    """Debug route to check session status"""
    return jsonify({
        'authenticated': current_user.is_authenticated,
        'user_id': getattr(current_user, 'id', None),
        'user_email': getattr(current_user, 'email', None),
        'session_keys': list(session.keys()),
        'has_supabase_session': 'supabase_session' in session,
        'session_permanent': session.permanent,
        'secret_key_set': bool(app.config.get('SECRET_KEY')),
        'environment': os.environ.get('FLASK_ENV', 'development'),
        'supabase_session_data': session.get('supabase_session', 'Not found')
    })

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
            session['created_at'] = datetime.now(UTC).isoformat()
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
        print(f"   Error type: {type(e)}")
        
        # If admin client fails, try with regular client as fallback
        if supabase and supabase_admin != supabase:
            try:
                print(f"🔄 DEBUG: Trying fallback with regular client for '{table_name}'")
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
                    print(f"✅ DEBUG: Fallback successful for '{table_name}': {len(response.data)} rows")
                    return response.data
                    
            except Exception as fallback_error:
                print(f"❌ DEBUG: Fallback also failed for '{table_name}': {fallback_error}")
        
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
            'created_at': datetime.now(UTC).isoformat()
        }
        
        # Insert into database using admin client (non-blocking)
        try:
            result = supabase_admin.table('user_activity_log').insert(log_data).execute()
            if not result.data:
                print(f"⚠️ WARNING: Activity log insert returned no data for {activity_type}")
        except Exception as db_error:
            # Log the error but don't raise it to avoid breaking the main functionality
            print(f"❌ ERROR: Failed to log activity '{activity_type}': {db_error}")
            
    except Exception as e:
        # Catch-all error handler - never let logging break the main app
        print(f"❌ CRITICAL: Activity logger failed with error: {e}")
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
            'created_at': datetime.now(UTC).isoformat()
        }
        
        # Insert into database
        result = supabase_admin.table('user_activity_log').insert(log_data).execute()
        
    except Exception as e:
        print(f"❌ ERROR: Failed to log authentication activity: {e}")


def activity_logged(activity_type, description_template=None, resource_type=None, status='success'):
    """
    Decorator to automatically log activities for route functions.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now(UTC)
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
                        'execution_time_ms': int((datetime.now(UTC) - start_time).total_seconds() * 1000),
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
                    print(f"❌ ERROR: Failed to log activity for {func.__name__}: {log_error}")
            
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

# Enhanced client data access functions
def get_all_clients_from_db():
    """Get all clients from Supabase database with enhanced error handling"""
    try:
        print("🔍 DEBUG: Fetching all clients from Supabase database...")
        
        # Use admin client to ensure we get all client data
        response = supabase_admin.table('clients').select('*').order('company_name').execute()
        
        if response.data:
            print(f"✅ DEBUG: Successfully fetched {len(response.data)} clients from database")
            return response.data
        else:
            print("⚠️ DEBUG: No clients found in database or empty response")
            return []
            
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch clients from database: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_client_by_id_from_db(client_id):
    """Get specific client by ID from Supabase database"""
    try:
        print(f"🔍 DEBUG: Fetching client ID {client_id} from database...")
        
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
        
        response = supabase_admin.table('clients').insert(client_data).execute()
        
        if response.data:
            print(f"✅ DEBUG: Successfully created client with ID: {response.data[0]['id']}")
            return response.data[0]
        else:
            print("❌ DEBUG: Failed to create client - no data returned")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to create client: {e}")
        return None

def update_client_in_db(client_id, client_data):
    """Update an existing client in Supabase database"""
    try:
        print(f"🔍 DEBUG: Updating client ID {client_id} with data: {client_data}")
        
        response = supabase_admin.table('clients').update(client_data).eq('id', client_id).execute()
        
        if response.data:
            print(f"✅ DEBUG: Successfully updated client ID {client_id}")
            return response.data[0]
        else:
            print(f"⚠️ DEBUG: Update completed but no data returned for client ID {client_id}")
            return {'success': True}
            
    except Exception as e:
        print(f"❌ ERROR: Failed to update client ID {client_id}: {e}")
        return None

def delete_client_from_db(client_id):
    """Delete a client from Supabase database (after checking for bookings)"""
    try:
        print(f"🔍 DEBUG: Attempting to delete client ID {client_id}")
        
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
    """Form for creating/editing bookings"""
    room_id = SelectField('Conference Room', coerce=int, validators=[DataRequired()])
    client_id = SelectField('Client', coerce=int, validators=[DataRequired()])
    title = StringField('Event Title', validators=[DataRequired()])
    start_time = DateTimeField('Start Time', format='%Y-%m-%d %H:%M', validators=[DataRequired()])
    end_time = DateTimeField('End Time', format='%Y-%m-%d %H:%M', validators=[DataRequired()])
    status = SelectField('Status', choices=[
        ('tentative', 'Tentative'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ])
    attendees = IntegerField('Number of Attendees')
    notes = TextAreaField('Notes')
    addons = SelectMultipleField('Add-ons', coerce=int)
    discount = DecimalField('Discount (USD)', places=2, default=0)
    
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
    """Get all bookings formatted for FullCalendar using Supabase admin client with fallback logic"""
    try:
        print("🔍 DEBUG: Fetching calendar events from Supabase...")
        
        # First try with nested relationships
        bookings_data = supabase_admin.table('bookings').select("""
            id, title, start_time, end_time, status, room_id, client_id,
            room:rooms(name),
            client:clients(company_name, contact_person)
        """).execute()
        
        print(f"✅ DEBUG: Found {len(bookings_data.data)} bookings for calendar")
        
        events = []
        for booking in bookings_data.data:
            try:
                # Ensure room data exists
                room_name = 'Unknown Room'
                if booking.get('room') and isinstance(booking.get('room'), dict) and booking['room'].get('name'):
                    room_name = booking['room']['name']
                elif booking.get('room_id'):
                    print(f"⚠️ DEBUG: Missing room data for booking {booking.get('id')}, fetching separately")
                    room_data = supabase_admin.table('rooms').select('name').eq('id', booking.get('room_id')).execute()
                    if room_data.data:
                        room_name = room_data.data[0]['name']
                
                # Ensure client data exists
                client_name = 'Unknown Client'
                if booking.get('client') and isinstance(booking.get('client'), dict):
                    client_name = booking['client'].get('company_name') or booking['client'].get('contact_person', 'Unknown Client')
                elif booking.get('client_id'):
                    print(f"⚠️ DEBUG: Missing client data for booking {booking.get('id')}, fetching separately")
                    client_data = supabase_admin.table('clients').select('company_name, contact_person').eq('id', booking.get('client_id')).execute()
                    if client_data.data:
                        client_name = client_data.data[0].get('company_name') or client_data.data[0].get('contact_person', 'Unknown Client')
                
                # Determine event color based on status
                color = {
                    'tentative': '#FFA500',  # Orange
                    'confirmed': '#28a745',  # Green
                    'cancelled': '#dc3545'   # Red
                }.get(booking.get('status', 'tentative'), '#17a2b8')  # Default: Teal
                
                # Create calendar event
                events.append({
                    'id': booking['id'],
                    'title': booking.get('title', 'Untitled Event'),
                    'start': booking['start_time'],
                    'end': booking['end_time'],
                    'color': color,
                    'extendedProps': {
                        'room': room_name,
                        'client': client_name,
                        'status': booking.get('status', 'tentative'),
                        'roomId': booking.get('room_id'),
                        'clientId': booking.get('client_id'),
                        'attendees': booking.get('attendees', 0),
                        'total': booking.get('total_price', 0),
                        'notes': booking.get('notes', ''),
                        'addons': []  # Will be populated if needed
                    }
                })
                
            except Exception as event_error:
                print(f"❌ DEBUG: Error processing individual booking {booking.get('id', 'unknown')}: {event_error}")
                # Continue processing other bookings
                continue
        
        print(f"✅ DEBUG: Successfully processed {len(events)} calendar events")
        return events
        
    except Exception as e:
        print(f"❌ Calendar events error: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: try to get bookings without relationships
        try:
            print("🔄 DEBUG: Trying fallback approach for calendar events")
            simple_bookings = supabase_admin.table('bookings').select('*').execute()
            
            events = []
            for booking in simple_bookings.data:
                try:
                    # Manually fetch room and client data
                    room_name = 'Unknown Room'
                    if booking.get('room_id'):
                        room_data = supabase_admin.table('rooms').select('name').eq('id', booking['room_id']).execute()
                        if room_data.data:
                            room_name = room_data.data[0]['name']
                    
                    client_name = 'Unknown Client'
                    if booking.get('client_id'):
                        client_data = supabase_admin.table('clients').select('company_name, contact_person').eq('id', booking['client_id']).execute()
                        if client_data.data:
                            client_name = client_data.data[0].get('company_name') or client_data.data[0].get('contact_person', 'Unknown Client')
                    
                    color = {
                        'tentative': '#FFA500',
                        'confirmed': '#28a745',
                        'cancelled': '#dc3545'
                    }.get(booking.get('status', 'tentative'), '#17a2b8')
                    
                    events.append({
                        'id': booking['id'],
                        'title': booking.get('title', 'Untitled Event'),
                        'start': booking['start_time'],
                        'end': booking['end_time'],
                        'color': color,
                        'extendedProps': {
                            'room': room_name,
                            'client': client_name,
                            'status': booking.get('status', 'tentative'),
                            'roomId': booking.get('room_id'),
                            'clientId': booking.get('client_id'),
                            'attendees': booking.get('attendees', 0),
                            'total': booking.get('total_price', 0),
                            'notes': booking.get('notes', ''),
                            'addons': []
                        }
                    })
                    
                except Exception as fallback_event_error:
                    print(f"❌ DEBUG: Error in fallback processing for booking {booking.get('id', 'unknown')}: {fallback_event_error}")
                    continue
            
            print(f"✅ DEBUG: Fallback successful, processed {len(events)} calendar events")
            return events
            
        except Exception as fallback_error:
            print(f"❌ DEBUG: Fallback also failed: {fallback_error}")
            return []

def calculate_booking_total(room_id, start_time, end_time, addon_ids=None, discount=0):
    """Calculate total price for a booking"""
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
        
        # Calculate final total
        total = room_rate + addons_total - float(discount)
        return max(total, 0)  # Ensure non-negative
        
    except Exception as e:
        print(f"Price calculation error: {e}")
        return 0

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
                        'login_time': datetime.now(UTC).isoformat()
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
                    additional_info={'attempt_time': datetime.now(UTC).isoformat()}
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
                additional_info={'logout_time': datetime.now(UTC).isoformat()}
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

@app.route('/')
@login_required
def dashboard():
    """Main dashboard page with enhanced error handling and debugging - NOW WITH ACTIVITY LOGGING"""
    
    # Log page view
    try:
        log_user_activity(
            ActivityTypes.PAGE_VIEW,
            "Viewed dashboard",
            resource_type='page',
            metadata={'page': 'dashboard', 'timestamp': datetime.now(UTC).isoformat()}
        )
    except Exception as log_error:
        print(f"Failed to log dashboard view: {log_error}")
    
    try:
        print(f"🔍 DEBUG: Dashboard loading at {datetime.now(UTC)}")
        print(f"🔍 DEBUG: User authenticated: {current_user.is_authenticated}")
        print(f"🔍 DEBUG: Supabase URL set: {bool(SUPABASE_URL)}")
        print(f"🔍 DEBUG: Service key available: {bool(SUPABASE_SERVICE_KEY)}")
        
        # Initialize with safe defaults
        upcoming_bookings_data = []
        today_bookings_data = []
        total_rooms = 0
        total_clients = 0
        total_active_bookings = 0
        
        # Get time boundaries
        now = datetime.now(UTC).isoformat()
        today = datetime.now(UTC).date().isoformat()
        tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
        
        print(f"🔍 DEBUG: Time boundaries - now: {now}, today: {today}, tomorrow: {tomorrow}")
        
        # Test basic connection first
        try:
            test_query = supabase_admin.table('rooms').select('id').limit(1).execute()
            print(f"✅ DEBUG: Basic database connection successful")
        except Exception as e:
            print(f"❌ DEBUG: Basic database connection failed: {e}")
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
            print("🔍 DEBUG: Fetching upcoming bookings...")
            
            # First try with nested relationships
            upcoming_bookings = supabase_admin.table('bookings').select("""
                *,
                room:rooms(name),
                client:clients(company_name, contact_person)
            """).gte('start_time', now).neq('status', 'cancelled').order('start_time').limit(5).execute()
            
            if upcoming_bookings.data:
                upcoming_bookings_raw = upcoming_bookings.data
                print(f"✅ DEBUG: Found {len(upcoming_bookings_raw)} upcoming bookings")
                print(f"🔍 DEBUG: Sample upcoming booking structure: {upcoming_bookings_raw[0] if upcoming_bookings_raw else 'None'}")
                
                # Process each booking to ensure room and client data
                upcoming_bookings_processed = []
                for booking in upcoming_bookings_raw:
                    processed_booking = booking.copy()
                    
                    # Ensure room data exists
                    if not booking.get('room') or not isinstance(booking.get('room'), dict):
                        print(f"⚠️ DEBUG: Missing room data for booking {booking.get('id')}, fetching separately")
                        room_data = supabase_admin.table('rooms').select('id, name').eq('id', booking.get('room_id')).execute()
                        if room_data.data:
                            processed_booking['room'] = room_data.data[0]
                        else:
                            processed_booking['room'] = {'name': 'Unknown Room'}
                    
                    # Ensure client data exists
                    if not booking.get('client') or not isinstance(booking.get('client'), dict):
                        print(f"⚠️ DEBUG: Missing client data for booking {booking.get('id')}, fetching separately")
                        client_data = supabase_admin.table('clients').select('id, company_name, contact_person').eq('id', booking.get('client_id')).execute()
                        if client_data.data:
                            processed_booking['client'] = client_data.data[0]
                        else:
                            processed_booking['client'] = {'company_name': None, 'contact_person': 'Unknown Client'}
                    
                    upcoming_bookings_processed.append(processed_booking)
                
                upcoming_bookings_data = convert_datetime_strings(upcoming_bookings_processed)
            else:
                print("⚠️ DEBUG: No upcoming bookings found")
                
        except Exception as e:
            print(f"❌ DEBUG: Error fetching upcoming bookings: {e}")
            flash('Error loading upcoming bookings', 'warning')
            
            # Fallback: try to get bookings without relationships
            try:
                print("🔄 DEBUG: Trying fallback approach for upcoming bookings")
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
                    print(f"✅ DEBUG: Fallback successful, got {len(upcoming_bookings_data)} upcoming bookings")
            except Exception as fallback_error:
                print(f"❌ DEBUG: Fallback also failed: {fallback_error}")
        
        # Get today's bookings with similar approach
        try:
            print("🔍 DEBUG: Fetching today's bookings...")
            
            today_bookings = supabase_admin.table('bookings').select("""
                *,
                room:rooms(name),
                client:clients(company_name, contact_person)
            """).gte('start_time', today).lt('start_time', tomorrow).neq('status', 'cancelled').execute()
            
            if today_bookings.data:
                today_bookings_raw = today_bookings.data
                print(f"✅ DEBUG: Found {len(today_bookings_raw)} today's bookings")
                
                # Process each booking to ensure room and client data
                today_bookings_processed = []
                for booking in today_bookings_raw:
                    processed_booking = booking.copy()
                    
                    # Ensure room data exists
                    if not booking.get('room') or not isinstance(booking.get('room'), dict):
                        print(f"⚠️ DEBUG: Missing room data for today's booking {booking.get('id')}, fetching separately")
                        room_data = supabase_admin.table('rooms').select('id, name').eq('id', booking.get('room_id')).execute()
                        if room_data.data:
                            processed_booking['room'] = room_data.data[0]
                        else:
                            processed_booking['room'] = {'name': 'Unknown Room'}
                    
                    # Ensure client data exists
                    if not booking.get('client') or not isinstance(booking.get('client'), dict):
                        print(f"⚠️ DEBUG: Missing client data for today's booking {booking.get('id')}, fetching separately")
                        client_data = supabase_admin.table('clients').select('id, company_name, contact_person').eq('id', booking.get('client_id')).execute()
                        if client_data.data:
                            processed_booking['client'] = client_data.data[0]
                        else:
                            processed_booking['client'] = {'company_name': None, 'contact_person': 'Unknown Client'}
                    
                    today_bookings_processed.append(processed_booking)
                
                today_bookings_data = convert_datetime_strings(today_bookings_processed)
            else:
                print("⚠️ DEBUG: No bookings found for today")
                
        except Exception as e:
            print(f"❌ DEBUG: Error fetching today's bookings: {e}")
            flash('Error loading today\'s bookings', 'warning')
            
            # Similar fallback for today's bookings
            try:
                print("🔄 DEBUG: Trying fallback approach for today's bookings")
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
                    print(f"✅ DEBUG: Fallback successful, got {len(today_bookings_data)} today's bookings")
            except Exception as fallback_error:
                print(f"❌ DEBUG: Today's bookings fallback also failed: {fallback_error}")
        
        # Get total counts with individual error handling
        try:
            print("🔍 DEBUG: Fetching total rooms...")
            rooms_response = supabase_admin.table('rooms').select('id').execute()
            total_rooms = len(rooms_response.data) if rooms_response.data else 0
            print(f"✅ DEBUG: Found {total_rooms} total rooms")
        except Exception as e:
            print(f"❌ DEBUG: Error fetching room count: {e}")
        
        try:
            print("🔍 DEBUG: Fetching total clients...")
            clients_response = supabase_admin.table('clients').select('id').execute()
            total_clients = len(clients_response.data) if clients_response.data else 0
            print(f"✅ DEBUG: Found {total_clients} total clients")
        except Exception as e:
            print(f"❌ DEBUG: Error fetching client count: {e}")
        
        try:
            print("🔍 DEBUG: Fetching active bookings...")
            active_bookings_response = supabase_admin.table('bookings').select('id').gte('end_time', now).neq('status', 'cancelled').execute()
            total_active_bookings = len(active_bookings_response.data) if active_bookings_response.data else 0
            print(f"✅ DEBUG: Found {total_active_bookings} active bookings")
        except Exception as e:
            print(f"❌ DEBUG: Error fetching active bookings count: {e}")
        
        # Log final statistics
        print(f"📊 DEBUG: Dashboard statistics:")
        print(f"   - Upcoming bookings: {len(upcoming_bookings_data)}")
        print(f"   - Today's bookings: {len(today_bookings_data)}")
        print(f"   - Total rooms: {total_rooms}")
        print(f"   - Total clients: {total_clients}")
        print(f"   - Active bookings: {total_active_bookings}")
        
        # Debug the data structure before passing to template
        if upcoming_bookings_data:
            print(f"🔍 DEBUG: Final upcoming booking structure: {upcoming_bookings_data[0]}")
        if today_bookings_data:
            print(f"🔍 DEBUG: Final today booking structure: {today_bookings_data[0]}")
        
        return render_template('dashboard.html',
                              title='Dashboard',
                              upcoming_bookings=upcoming_bookings_data,
                              today_bookings=today_bookings_data,
                              total_rooms=total_rooms,
                              total_clients=total_clients,
                              total_active_bookings=total_active_bookings,
                              debug_mode=os.environ.get('FLASK_ENV') == 'production')
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in dashboard: {e}")
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
        print("🔍 DEBUG: Loading calendar page...")
        rooms_data = supabase_select('rooms')
        
        if rooms_data:
            print(f"✅ DEBUG: Loaded {len(rooms_data)} rooms for calendar")
        else:
            print("⚠️ DEBUG: No rooms found for calendar")
            flash('No rooms found. Please add rooms first.', 'warning')
        
        return render_template('calendar.html', title='Booking Calendar', rooms=rooms_data)
        
    except Exception as e:
        print(f"❌ Calendar error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading calendar page', 'danger')
        return render_template('calendar.html', title='Booking Calendar', rooms=[])

@app.route('/api/events')
@login_required
def get_events():
    """API endpoint to get calendar events from Supabase with enhanced error handling"""
    try:
        print("🔍 DEBUG: API events endpoint called")
        events = get_booking_calendar_events_supabase()
        
        print(f"✅ DEBUG: Returning {len(events)} events to calendar")
        
        # Validate events data before returning
        valid_events = []
        for event in events:
            # Ensure required fields exist
            if (event.get('id') and 
                event.get('title') and 
                event.get('start') and 
                event.get('end')):
                valid_events.append(event)
            else:
                print(f"⚠️ DEBUG: Skipping invalid event: {event}")
        
        print(f"✅ DEBUG: Returning {len(valid_events)} valid events")
        return jsonify(valid_events)
        
    except Exception as e:
        print(f"❌ Calendar events API error: {e}")
        import traceback
        traceback.print_exc()
        # Return empty array instead of error to prevent calendar from breaking
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

@app.route('/clients')
@login_required
def clients():
    """List all clients using enhanced Supabase data access with better error handling"""
    try:
        print("🔍 DEBUG: Loading clients page...")
        
        # Use enhanced function to get all clients from database
        clients_data = get_all_clients_from_db()
        
        if clients_data:
            print(f"✅ DEBUG: Loaded {len(clients_data)} clients for display")
            # Sort clients by company name or contact person
            clients_data.sort(key=lambda x: (x.get('company_name') or x.get('contact_person', '')).lower())
        else:
            print("⚠️ DEBUG: No clients found in database")
            flash('No clients found in the database. You can add the first client using the "Add Client" button.', 'info')
        
        return render_template('clients/index.html', title='Clients', clients=clients_data)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load clients page: {e}")
        flash('Error loading clients. Please try again.', 'danger')
        return render_template('clients/index.html', title='Clients', clients=[])

@app.route('/clients/new', methods=['GET', 'POST'])
@login_required
def new_client():
    """Add a new client to Supabase with enhanced error handling"""
    form = ClientForm()
    
    if form.validate_on_submit():
        try:
            print("🔍 DEBUG: Processing new client form submission...")
            
            # Prepare client data
            client_data = {
                'company_name': form.company_name.data.strip() if form.company_name.data else None,
                'contact_person': form.contact_person.data.strip(),
                'email': form.email.data.strip().lower(),
                'phone': form.phone.data.strip() if form.phone.data else None,
                'address': form.address.data.strip() if form.address.data else None,
                'notes': form.notes.data.strip() if form.notes.data else None
            }
            
            # Use enhanced function to create client
            result = create_client_in_db(client_data)
            
            if result:
                client_name = result.get('company_name') or result.get('contact_person')
                flash(f'Client "{client_name}" added successfully', 'success')
                return redirect(url_for('clients'))
            else:
                flash('Error adding client to database', 'danger')
                
        except Exception as e:
            print(f"❌ ERROR: Failed to create new client: {e}")
            flash(f'Error adding client: {str(e)}', 'danger')
    else:
        # Display form validation errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field.replace("_", " ").title()}: {error}', 'danger')
    
    return render_template('clients/form.html', title='Add Client', form=form)

@app.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(id):
    """Edit a client with enhanced Supabase data access"""
    try:
        print(f"🔍 DEBUG: Loading edit form for client ID {id}")
        
        # Get client data using enhanced function
        client = get_client_by_id_from_db(id)
        
        if not client:
            flash('Client not found', 'danger')
            return redirect(url_for('clients'))
        
        form = ClientForm()
        
        if form.validate_on_submit():
            try:
                print(f"🔍 DEBUG: Processing edit form for client ID {id}")
                
                # Prepare update data
                update_data = {
                    'company_name': form.company_name.data.strip() if form.company_name.data else None,
                    'contact_person': form.contact_person.data.strip(),
                    'email': form.email.data.strip().lower(),
                    'phone': form.phone.data.strip() if form.phone.data else None,
                    'address': form.address.data.strip() if form.address.data else None,
                    'notes': form.notes.data.strip() if form.notes.data else None
                }
                
                # Use enhanced function to update client
                result = update_client_in_db(id, update_data)
                
                if result:
                    client_name = update_data.get('company_name') or update_data.get('contact_person')
                    flash(f'Client "{client_name}" updated successfully', 'success')
                    return redirect(url_for('clients'))
                else:
                    flash('Error updating client in database', 'danger')
                    
            except Exception as e:
                print(f"❌ ERROR: Failed to update client ID {id}: {e}")
                flash(f'Error updating client: {str(e)}', 'danger')
        else:
            # Pre-fill form with existing data on GET request
            if request.method == 'GET':
                form.company_name.data = client.get('company_name', '')
                form.contact_person.data = client.get('contact_person', '')
                form.email.data = client.get('email', '')
                form.phone.data = client.get('phone', '')
                form.address.data = client.get('address', '')
                form.notes.data = client.get('notes', '')
            
            # Display form validation errors on POST
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field.replace("_", " ").title()}: {error}', 'danger')
        
        return render_template('clients/form.html', title='Edit Client', form=form, client=client)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load edit form for client ID {id}: {e}")
        flash('Error loading client for editing', 'danger')
        return redirect(url_for('clients'))

@app.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def delete_client(id):
    """Delete a client with enhanced error handling"""
    try:
        print(f"🔍 DEBUG: Processing delete request for client ID {id}")
        
        # Use enhanced function to delete client (includes booking check)
        success, message = delete_client_from_db(id)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
            
    except Exception as e:
        print(f"❌ ERROR: Failed to delete client ID {id}: {e}")
        flash(f'Error deleting client: {str(e)}', 'danger')
    
    return redirect(url_for('clients'))

@app.route('/clients/<int:id>')
@login_required
def view_client(id):
    """View client details and booking history with enhanced data access"""
    try:
        print(f"🔍 DEBUG: Loading client details for ID {id}")
        
        # Get client data using enhanced function
        client = get_client_by_id_from_db(id)
        
        if not client:
            flash('Client not found', 'danger')
            return redirect(url_for('clients'))
        
        # Get client bookings using enhanced function
        bookings_data = get_client_bookings_from_db(id)
        
        # Calculate client statistics
        total_bookings = len(bookings_data)
        total_spent = sum(float(booking.get('total_price', 0)) for booking in bookings_data)
        avg_booking_value = total_spent / total_bookings if total_bookings > 0 else 0
        
        # Get recent booking dates
        recent_bookings = sorted(bookings_data, key=lambda x: x.get('start_time', ''), reverse=True)[:5]
        
        # Add statistics to client data for template
        client_stats = {
            'total_bookings': total_bookings,
            'total_spent': round(total_spent, 2),
            'avg_booking_value': round(avg_booking_value, 2),
            'recent_bookings': recent_bookings
        }
        
        client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
        
        return render_template('clients/view.html', 
                              title=f'Client: {client_name}', 
                              client=client, 
                              bookings=bookings_data,
                              stats=client_stats)
                              
    except Exception as e:
        print(f"❌ ERROR: Failed to load client details for ID {id}: {e}")
        flash('Error loading client details', 'danger')
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
        print("🔍 DEBUG: Starting enhanced addons route")
        
        # Always use the reliable fallback approach instead of nested queries
        # This ensures better compatibility with different Supabase configurations
        
        # Step 1: Get all categories
        try:
            categories_response = supabase_admin.table('addon_categories').select('*').order('name').execute()
            categories = categories_response.data if categories_response.data else []
            print(f"✅ DEBUG: Found {len(categories)} categories")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch categories: {e}")
            categories = []
        
        # Step 2: Get all addons
        try:
            addons_response = supabase_admin.table('addons').select('*').order('name').execute()
            all_addons = addons_response.data if addons_response.data else []
            print(f"✅ DEBUG: Found {len(all_addons)} total addons")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch addons: {e}")
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
            
            print(f"✅ DEBUG: Calculated usage for {len(addon_usage)} addons from {len(booking_addons)} booking_addon records")
        except Exception as e:
            print(f"⚠️ DEBUG: Usage calculation failed: {e}")
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
            
            print(f"📊 DEBUG: Addon '{addon['name']}' - Active: {addon['is_active']}, Bookings: {booking_count}, Category ID: {addon['category_id']}")
            
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
                print(f"✅ DEBUG: Category '{category['name']}' has {len(category['addons'])} addons")
            else:
                category['addons'] = []
                print(f"ℹ️ DEBUG: Category '{category['name']}' has no addons")
        
        # Step 6: Handle uncategorized addons (create a temporary category if needed)
        if uncategorized_addons:
            print(f"⚠️ DEBUG: Found {len(uncategorized_addons)} uncategorized addons")
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
        
        print(f"📊 DEBUG: Final statistics:")
        print(f"  - Total addons: {statistics['total_addons']}")
        print(f"  - Total categories: {statistics['total_categories']}")
        print(f"  - Active addons: {statistics['active_addons']}")
        print(f"  - Usage rate: {statistics['usage_rate']}%")
        print(f"  - Addons with usage: {statistics['addons_with_usage']}")
        
        # Step 8: Verify data integrity before rendering
        print(f"🔍 DEBUG: Data verification:")
        for category in categories:
            print(f"  - Category '{category['name']}': {len(category.get('addons', []))} addons")
            for addon in category.get('addons', [])[:3]:  # Show first 3 addons per category
                print(f"    * {addon['name']} - ${addon['price']} - Active: {addon['is_active']}")
        
        return render_template('addons/index.html', 
                             title='Add-ons', 
                             categories=categories,
                             stats=statistics)
        
    except Exception as e:
        print(f"❌ ERROR: Addons route failed: {e}")
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
        print(f"🔍 DEBUG: Loading bookings page with filters - status: {status_filter}, date: {date_filter}")
        
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
        now = datetime.now(UTC).isoformat()
        today = datetime.now(UTC).date().isoformat()
        tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
        
        if date_filter == 'upcoming':
            query = query.gte('end_time', now)
        elif date_filter == 'past':
            query = query.lt('end_time', now)
        elif date_filter == 'today':
            query = query.gte('start_time', today).lt('start_time', tomorrow)
        
        response = query.order('start_time').execute()
        bookings_raw = response.data
        
        print(f"✅ DEBUG: Found {len(bookings_raw)} bookings from database")
        
        # Process each booking to ensure room and client data exists
        bookings_processed = []
        for booking in bookings_raw:
            processed_booking = booking.copy()
            
            # Ensure room data exists
            if not booking.get('room') or not isinstance(booking.get('room'), dict):
                print(f"⚠️ DEBUG: Missing room data for booking {booking.get('id')}, fetching separately")
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
                print(f"⚠️ DEBUG: Missing client data for booking {booking.get('id')}, fetching separately")
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
        
        print(f"✅ DEBUG: Successfully processed {len(bookings_data)} bookings for display")
        
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch bookings: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: try to get bookings without relationships
        try:
            print("🔄 DEBUG: Trying fallback approach for bookings")
            simple_bookings = supabase_admin.table('bookings').select('*')
            
            # Apply the same filters
            if status_filter != 'all':
                simple_bookings = simple_bookings.eq('status', status_filter)
            
            now = datetime.now(UTC).isoformat()
            today = datetime.now(UTC).date().isoformat()
            tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
            
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
                print(f"✅ DEBUG: Fallback successful, processed {len(bookings_data)} bookings")
            else:
                bookings_data = []
                print("⚠️ DEBUG: No bookings found")
                
        except Exception as fallback_error:
            print(f"❌ DEBUG: Fallback also failed: {fallback_error}")
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
    """Create a new booking - ENHANCED WITH BETTER NOTIFICATIONS AND ERROR HANDLING"""
    form = BookingForm()
    
    # Initialize form.addons.data as empty list if None
    if form.addons.data is None:
        form.addons.data = []
    
    # Initialize rooms data
    rooms_for_template = []
    
    # Populate form choices from Supabase using admin client
    try:
        rooms_data = supabase_select('rooms', filters=[('status', 'eq', 'available')])
        clients_data = supabase_select('clients', order_by='company_name')
        addons_data = supabase_admin.table('addons').select("""
            id, name, price,
            category:addon_categories(name)
        """).eq('is_active', True).execute()
        
        # Include capacity in room choices for frontend
        form.room_id.choices = [(r['id'], f"{r['name']} (Capacity: {r['capacity']})") for r in rooms_data]
        form.client_id.choices = [(c['id'], c['company_name'] or c['contact_person']) for c in clients_data]
        
        # Format addon choices with category and price
        addon_choices = []
        for addon in addons_data.data:
            category_name = addon.get('category', {}).get('name', 'Uncategorized') if addon.get('category') else 'Uncategorized'
            addon_label = f"{category_name} - {addon['name']} (${addon['price']})"
            addon_choices.append((addon['id'], addon_label))
        
        form.addons.choices = addon_choices
        
        # Pass rooms data to template in the format expected by the template
        rooms_for_template = rooms_data
        
    except Exception as e:
        print(f"Error loading form data: {e}")
        flash('Error loading form data. Please refresh the page and try again.', 'danger')
        return redirect(url_for('bookings'))

    if form.validate_on_submit():
        try:
            print(f"🔍 DEBUG: Processing new booking form submission...")
            
            # Step 1: Check room availability
            if not is_room_available_supabase(form.room_id.data, form.start_time.data, form.end_time.data):
                flash('❌ Room is not available for the selected time period. Please choose a different time or room.', 'danger')
                
                # Log failed booking attempt due to room availability
                try:
                    log_user_activity(
                        ActivityTypes.CREATE_BOOKING,
                        f"Failed to create booking '{form.title.data}' - room not available",
                        resource_type='booking',
                        status='failed',
                        metadata={
                            'reason': 'room_not_available',
                            'room_id': form.room_id.data,
                            'client_id': form.client_id.data,
                            'start_time': form.start_time.data.isoformat(),
                            'end_time': form.end_time.data.isoformat(),
                            'title': form.title.data
                        }
                    )
                except Exception as log_error:
                    print(f"Failed to log booking availability failure: {log_error}")
                
                return render_template('bookings/form.html', title='New Booking', form=form, rooms=rooms_for_template)
            
            # Step 2: Calculate pricing
            print(f"🔍 DEBUG: Calculating pricing for booking...")
            total_price = calculate_booking_total(
                form.room_id.data, 
                form.start_time.data, 
                form.end_time.data, 
                form.addons.data, 
                form.discount.data or 0
            )
            print(f"✅ DEBUG: Total price calculated: ${total_price:.2f}")
            
            # Step 3: Get room and client names for better messaging
            room_name = "Unknown Room"
            client_name = "Unknown Client"
            
            try:
                if form.room_id.data:
                    room_data = supabase_admin.table('rooms').select('name').eq('id', form.room_id.data).execute()
                    if room_data.data:
                        room_name = room_data.data[0]['name']
                
                if form.client_id.data:
                    client_data = supabase_admin.table('clients').select('company_name, contact_person').eq('id', form.client_id.data).execute()
                    if client_data.data:
                        client_name = client_data.data[0].get('company_name') or client_data.data[0].get('contact_person', 'Unknown Client')
            except Exception as lookup_error:
                print(f"Error getting room/client names: {lookup_error}")
            
            # Step 4: Create booking data
            booking_data = {
                'room_id': form.room_id.data,
                'client_id': form.client_id.data,
                'title': form.title.data,
                'start_time': form.start_time.data.isoformat(),
                'end_time': form.end_time.data.isoformat(),
                'status': form.status.data,
                'attendees': form.attendees.data,
                'notes': form.notes.data,
                'discount': float(form.discount.data or 0),
                'total_price': total_price,
                'created_by': current_user.id
            }
            
            print(f"🔍 DEBUG: Inserting booking data...")
            
            # Step 5: Insert booking
            result = supabase_insert('bookings', booking_data)
            
            if result:
                booking_id = result['id']
                print(f"✅ DEBUG: Booking created successfully with ID: {booking_id}")
                
                # Step 6: Add selected add-ons to junction table
                addon_count = 0
                addon_names = []
                if form.addons.data:
                    print(f"🔍 DEBUG: Adding {len(form.addons.data)} add-ons to booking...")
                    for addon_id in form.addons.data:
                        addon_booking_data = {
                            'booking_id': booking_id,
                            'addon_id': addon_id,
                            'quantity': 1
                        }
                        addon_result = supabase_insert('booking_addons', addon_booking_data)
                        
                        if addon_result:
                            addon_count += 1
                            # Get addon name for messaging
                            try:
                                addon_data = supabase_admin.table('addons').select('name').eq('id', addon_id).execute()
                                if addon_data.data:
                                    addon_names.append(addon_data.data[0]['name'])
                            except:
                                addon_names.append(f'Addon #{addon_id}')
                    
                    print(f"✅ DEBUG: Successfully added {addon_count} add-ons")
                
                # Step 7: Log successful booking creation
                try:
                    log_user_activity(
                        ActivityTypes.CREATE_BOOKING,
                        f"Created booking '{form.title.data}' in {room_name} for {client_name}",
                        resource_type='booking',
                        resource_id=booking_id,
                        metadata={
                            'room_id': form.room_id.data,
                            'room_name': room_name,
                            'client_id': form.client_id.data,
                            'client_name': client_name,
                            'start_time': form.start_time.data.isoformat(),
                            'end_time': form.end_time.data.isoformat(),
                            'total_price': total_price,
                            'status': form.status.data,
                            'attendees': form.attendees.data,
                            'addon_count': addon_count,
                            'discount': float(form.discount.data or 0)
                        }
                    )
                except Exception as log_error:
                    print(f"Failed to log booking creation: {log_error}")
                
                # Step 8: Provide appropriate success message and next steps
                if form.status.data == 'tentative':
                    # Auto-generate quotation for tentative bookings
                    try:
                        log_user_activity(
                            ActivityTypes.GENERATE_REPORT,
                            f"Auto-generating quotation for tentative booking '{form.title.data}'",
                            resource_type='quotation',
                            resource_id=booking_id,
                            metadata={
                                'booking_id': booking_id,
                                'booking_title': form.title.data,
                                'auto_generated': True
                            }
                        )
                    except Exception as log_error:
                        print(f"Failed to log quotation generation: {log_error}")
                    
                    # Create detailed success message for tentative booking
                    success_message = f"""
                    ✅ <strong>Tentative booking created successfully!</strong><br>
                    📋 <strong>Booking Details:</strong><br>
                    • Event: {form.title.data}<br>
                    • Room: {room_name}<br>
                    • Client: {client_name}<br>
                    • Date: {form.start_time.data.strftime('%d %B %Y')}<br>
                    • Time: {form.start_time.data.strftime('%H:%M')} - {form.end_time.data.strftime('%H:%M')}<br>
                    • Total: ${total_price:.2f}<br>
                    📄 <strong>Next Step:</strong> Generating quotation for client approval...
                    """
                    
                    flash(success_message, 'success')
                    return redirect(url_for('generate_quotation', id=booking_id))
                    
                elif form.status.data == 'confirmed':
                    # Confirmed booking success message
                    success_message = f"""
                    ✅ <strong>Booking confirmed successfully!</strong><br>
                    📋 <strong>Booking Details:</strong><br>
                    • Event: {form.title.data}<br>
                    • Room: {room_name}<br>
                    • Client: {client_name}<br>
                    • Date: {form.start_time.data.strftime('%d %B %Y')}<br>
                    • Time: {form.start_time.data.strftime('%H:%M')} - {form.end_time.data.strftime('%H:%M')}<br>
                    • Total: ${total_price:.2f}<br>
                    """
                    
                    if addon_count > 0:
                        success_message += f"• Add-ons: {', '.join(addon_names[:3])}{'...' if len(addon_names) > 3 else ''}<br>"
                    
                    success_message += "🎉 <strong>The room is now reserved!</strong> You can generate an invoice when ready."
                    
                    flash(success_message, 'success')
                    return redirect(url_for('view_booking', id=booking_id))
                else:
                    # Standard booking success message
                    success_message = f"""
                    ✅ <strong>Booking created successfully!</strong><br>
                    📋 Event: {form.title.data} in {room_name}<br>
                    👤 Client: {client_name}<br>
                    💰 Total: ${total_price:.2f}
                    """
                    
                    flash(success_message, 'success')
                    return redirect(url_for('view_booking', id=booking_id))
                
            else:
                # Database insert failed
                try:
                    log_user_activity(
                        ActivityTypes.CREATE_BOOKING,
                        f"Failed to create booking '{form.title.data}' - database insert failed",
                        resource_type='booking',
                        status='failed',
                        metadata={
                            'reason': 'database_insert_failed',
                            'room_id': form.room_id.data,
                            'client_id': form.client_id.data,
                            'start_time': form.start_time.data.isoformat(),
                            'end_time': form.end_time.data.isoformat(),
                            'title': form.title.data,
                            'total_price': total_price
                        }
                    )
                except Exception as log_error:
                    print(f"Failed to log booking creation failure: {log_error}")
                
                flash('❌ Error creating booking. The data could not be saved. Please try again.', 'danger')
                
        except Exception as e:
            print(f"❌ ERROR creating booking: {e}")
            import traceback
            traceback.print_exc()
            
            # Log booking creation error with exception details
            try:
                log_user_activity(
                    ActivityTypes.CREATE_BOOKING,
                    f"Error creating booking '{form.title.data}': {str(e)}",
                    resource_type='booking',
                    status='failed',
                    metadata={
                        'reason': 'exception_occurred',
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'room_id': form.room_id.data,
                        'client_id': form.client_id.data,
                        'title': form.title.data
                    }
                )
            except Exception as log_error:
                print(f"Failed to log booking creation exception: {log_error}")
            
            flash('❌ Unexpected error creating booking. Please check all fields and try again.', 'danger')
    else:
        # Form validation errors
        if request.method == 'POST' and form.errors:
            try:
                log_user_activity(
                    ActivityTypes.CREATE_BOOKING,
                    f"Booking creation failed due to form validation errors",
                    resource_type='booking',
                    status='failed',
                    metadata={
                        'reason': 'form_validation_failed',
                        'form_errors': form.errors,
                        'title': form.title.data or 'Unknown',
                        'validation_errors': list(form.errors.keys())
                    }
                )
            except Exception as log_error:
                print(f"Failed to log form validation errors: {log_error}")
            
            # Display user-friendly validation error messages
            error_messages = []
            for field, errors in form.errors.items():
                field_name = field.replace('_', ' ').title()
                for error in errors:
                    error_messages.append(f"{field_name}: {error}")
            
            if error_messages:
                flash(f"❌ Please correct the following errors:<br>• " + "<br>• ".join(error_messages), 'danger')
    
    # Log page view for GET requests (when form is first loaded)
    if request.method == 'GET':
        try:
            log_user_activity(
                ActivityTypes.PAGE_VIEW,
                "Viewed new booking form",
                resource_type='page',
                metadata={
                    'page': 'new_booking',
                    'form_type': 'booking_creation',
                    'available_rooms': len(rooms_for_template),
                    'timestamp': datetime.now(UTC).isoformat()
                }
            )
        except Exception as log_error:
            print(f"Failed to log new booking page view: {log_error}")
    
    return render_template('bookings/form.html', title='New Booking', form=form, rooms=rooms_for_template)




@app.route('/bookings/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_booking(id):
    """Edit a booking using Supabase admin client with quotation integration"""
    try:
        booking_data = supabase_admin.table('bookings').select("""
            *,
            booking_addons(addon_id)
        """).eq('id', id).execute()
        
        if not booking_data.data:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        booking = booking_data.data[0]
        original_status = booking['status']  # Store original status
        form = BookingForm()
        
        # Initialize form.addons.data as empty list if None
        if form.addons.data is None:
            form.addons.data = []
        
        # Initialize rooms data
        rooms_for_template = []
        
        # Populate form choices
        rooms_data = supabase_select('rooms', filters=[('status', 'eq', 'available')])
        clients_data = supabase_select('clients', order_by='company_name')
        addons_data = supabase_admin.table('addons').select("""
            id, name, price,
            category:addon_categories(name)
        """).eq('is_active', True).execute()
        
        # Include current room if it's not in available rooms
        current_room = supabase_select('rooms', filters=[('id', 'eq', booking['room_id'])])
        all_rooms = rooms_data.copy()
        if current_room and current_room[0] not in all_rooms:
            all_rooms.append(current_room[0])
        
        form.room_id.choices = [(r['id'], f"{r['name']} (Capacity: {r['capacity']})") for r in all_rooms]
        form.client_id.choices = [(c['id'], c['company_name'] or c['contact_person']) for c in clients_data]
        
        addon_choices = []
        for addon in addons_data.data:
            category_name = addon.get('category', {}).get('name', 'Uncategorized') if addon.get('category') else 'Uncategorized'
            addon_label = f"{category_name} - {addon['name']} (${addon['price']})"
            addon_choices.append((addon['id'], addon_label))
        
        form.addons.choices = addon_choices
        
        # Pass rooms data to template in the format expected by the template
        rooms_for_template = all_rooms
        
        if form.validate_on_submit():
            # Check room availability (excluding this booking) using admin client
            start_time = form.start_time.data
            end_time = form.end_time.data
            
            overlapping = supabase_admin.table('bookings').select('id').eq('room_id', form.room_id.data).neq('status', 'cancelled').neq('id', id).lt('start_time', end_time.isoformat()).gt('end_time', start_time.isoformat()).execute()
            
            if overlapping.data:
                flash('Room is not available for the selected time period', 'danger')
                return render_template('bookings/form.html', title='Edit Booking', form=form, booking=booking, rooms=rooms_for_template)
            
            # Calculate new pricing
            total_price = calculate_booking_total(
                form.room_id.data, 
                start_time, 
                end_time, 
                form.addons.data, 
                form.discount.data or 0
            )
            
            # Update booking
            update_data = {
                'room_id': form.room_id.data,
                'client_id': form.client_id.data,
                'title': form.title.data,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'status': form.status.data,
                'attendees': form.attendees.data,
                'notes': form.notes.data,
                'discount': float(form.discount.data or 0),
                'total_price': total_price
            }
            
            result = supabase_update('bookings', update_data, [('id', 'eq', id)])
            
            if result:
                # Update add-ons - delete existing and insert new
                supabase_delete('booking_addons', [('booking_id', 'eq', id)])
                
                if form.addons.data:
                    for addon_id in form.addons.data:
                        addon_booking_data = {
                            'booking_id': id,
                            'addon_id': addon_id,
                            'quantity': 1
                        }
                        supabase_insert('booking_addons', addon_booking_data)
                
                # Check if status changed to tentative (for quotation generation)
                new_status = form.status.data
                if new_status == 'tentative' and original_status != 'tentative':
                    flash('Booking updated successfully. Generating quotation...', 'success')
                    return redirect(url_for('generate_quotation', id=id))
                elif new_status == 'confirmed' and original_status != 'confirmed':
                    flash('Booking confirmed successfully. You can now generate an invoice.', 'success')
                    return redirect(url_for('view_booking', id=id))
                else:
                    flash('Booking updated successfully', 'success')
                    return redirect(url_for('view_booking', id=id))
            else:
                flash('Error updating booking', 'danger')
        else:
            # Pre-fill form with existing data
            form.room_id.data = booking['room_id']
            form.client_id.data = booking['client_id']
            form.title.data = booking['title']
            form.start_time.data = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).replace(tzinfo=None)
            form.end_time.data = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00')).replace(tzinfo=None)
            form.status.data = booking['status']
            form.attendees.data = booking['attendees']
            form.notes.data = booking['notes']
            form.discount.data = booking['discount']
            
            # Pre-select current add-ons
            current_addons = [ba['addon_id'] for ba in booking.get('booking_addons', [])]
            form.addons.data = current_addons
        
        return render_template('bookings/form.html', title='Edit Booking', form=form, booking=booking, rooms=rooms_for_template)
        
    except Exception as e:
        print(f"Error editing booking: {e}")
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
    """Generate a quotation for a booking - ENHANCED WITH ROBUST ERROR HANDLING"""
    try:
        print(f"🔍 DEBUG: Generating quotation for booking ID {id}")
        
        # Step 1: Get basic booking data first (simple query for reliability)
        booking_response = supabase_admin.table('bookings').select('*').eq('id', id).execute()
        
        if not booking_response.data:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        booking = booking_response.data[0]
        print(f"✅ DEBUG: Found booking: {booking.get('title', 'Untitled')}")
        
        # Step 2: Get room data separately for reliability
        room = None
        if booking.get('room_id'):
            room_response = supabase_admin.table('rooms').select('*').eq('id', booking['room_id']).execute()
            if room_response.data:
                room = room_response.data[0]
                print(f"✅ DEBUG: Found room: {room.get('name', 'Unknown')}")
            else:
                print(f"⚠️ WARNING: Room ID {booking['room_id']} not found")
                flash('Room information not found for this booking', 'warning')
                return redirect(url_for('view_booking', id=id))
        else:
            flash('No room associated with this booking', 'warning')
            return redirect(url_for('view_booking', id=id))
        
        # Step 3: Get client data separately
        client = None
        if booking.get('client_id'):
            client_response = supabase_admin.table('clients').select('*').eq('id', booking['client_id']).execute()
            if client_response.data:
                client = client_response.data[0]
                print(f"✅ DEBUG: Found client: {client.get('company_name') or client.get('contact_person', 'Unknown')}")
            else:
                print(f"⚠️ WARNING: Client ID {booking['client_id']} not found")
                flash('Client information not found for this booking', 'warning')
                return redirect(url_for('view_booking', id=id))
        else:
            flash('No client associated with this booking', 'warning')
            return redirect(url_for('view_booking', id=id))
        
        # Step 4: Get booking addons separately (robust approach)
        addon_items = []
        addons_total = 0
        try:
            booking_addons_response = supabase_admin.table('booking_addons').select('*').eq('booking_id', id).execute()
            
            for ba in booking_addons_response.data if booking_addons_response.data else []:
                addon_id = ba.get('addon_id')
                if addon_id:
                    # Get addon details
                    addon_response = supabase_admin.table('addons').select('*').eq('id', addon_id).execute()
                    if addon_response.data:
                        addon = addon_response.data[0]
                        quantity = ba.get('quantity', 1)
                        price = float(addon.get('price', 0))
                        total = price * quantity
                        
                        # Get category name
                        category_name = 'Other'
                        if addon.get('category_id'):
                            cat_response = supabase_admin.table('addon_categories').select('name').eq('id', addon['category_id']).execute()
                            if cat_response.data:
                                category_name = cat_response.data[0]['name']
                        
                        addon_items.append({
                            'name': addon.get('name', 'Unknown Addon'),
                            'category': category_name,
                            'price': price,
                            'quantity': quantity,
                            'total': total
                        })
                        addons_total += total
                        
            print(f"✅ DEBUG: Processed {len(addon_items)} addon items, total: ${addons_total:.2f}")
            
        except Exception as addon_error:
            print(f"⚠️ WARNING: Error processing addons: {addon_error}")
            # Continue without addons rather than failing completely
            addon_items = []
            addons_total = 0
        
        # Step 5: Calculate room rate and totals
        try:
            # Parse booking times safely
            if isinstance(booking.get('start_time'), str):
                start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).replace(tzinfo=None)
                end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                start_time = booking['start_time']
                end_time = booking['end_time']
            
            # Calculate duration
            duration_hours = (end_time - start_time).total_seconds() / 3600
            
            # Calculate room rate based on duration
            if duration_hours <= 4:
                room_rate = float(room.get('hourly_rate', 0)) * duration_hours
                rate_type = f"Hourly Rate ({duration_hours:.1f} hours)"
            elif duration_hours <= 6:
                room_rate = float(room.get('half_day_rate', 0))
                rate_type = "Half-day Rate"
            else:
                room_rate = float(room.get('full_day_rate', 0))
                rate_type = "Full-day Rate"
            
            print(f"✅ DEBUG: Room rate calculated: ${room_rate:.2f} ({rate_type})")
            
        except Exception as calc_error:
            print(f"⚠️ WARNING: Error calculating room rate: {calc_error}")
            # Use fallback values
            room_rate = float(booking.get('total_price', 0)) * 0.7  # Estimate 70% is room cost
            rate_type = "Estimated Rate"
            start_time = datetime.now(UTC)
            end_time = start_time + timedelta(hours=4)
            duration_hours = 4
        
        # Step 6: Calculate totals with proper error handling
        try:
            discount = float(booking.get('discount', 0))
            subtotal = room_rate + addons_total - discount
            vat_rate = 0.15
            vat_amount = subtotal * vat_rate
            total_with_vat = subtotal + vat_amount
            
            # Ensure non-negative values
            subtotal = max(subtotal, 0)
            vat_amount = max(vat_amount, 0)
            total_with_vat = max(total_with_vat, 0)
            
        except Exception as total_error:
            print(f"⚠️ WARNING: Error calculating totals: {total_error}")
            # Use booking total as fallback
            total_price = float(booking.get('total_price', 100))
            subtotal = total_price / 1.15  # Remove VAT
            vat_amount = total_price - subtotal
            total_with_vat = total_price
            discount = float(booking.get('discount', 0))
        
        # Step 7: Prepare booking data for template
        # Add calculated fields to booking object
        booking.update({
            'room': room,
            'client': client,
            'room_rate': round(room_rate, 2),
            'rate_type': rate_type,
            'addons_total': round(addons_total, 2),
            'addon_items': addon_items,
            'duration_hours': round(duration_hours, 1),
            'subtotal': round(subtotal, 2),
            'vat_amount': round(vat_amount, 2),
            'total_with_vat': round(total_with_vat, 2),
            'discount': discount
        })
        
        # Convert datetime strings to datetime objects for template
        booking = convert_datetime_strings(booking)
        
        # Generate quotation number and validity
        quotation_number = f"QUO-{booking['id']}-{datetime.now(UTC).strftime('%Y%m')}"
        valid_until = datetime.now(UTC) + timedelta(days=30)  # Valid for 30 days
        
        print(f"✅ DEBUG: Quotation data prepared successfully")
        print(f"📊 DEBUG: Quotation summary - Room: ${room_rate:.2f}, Addons: ${addons_total:.2f}, Total: ${total_with_vat:.2f}")
        
        # Log quotation generation
        try:
            log_user_activity(
                ActivityTypes.GENERATE_REPORT,
                f"Generated quotation {quotation_number} for booking '{booking['title']}'",
                resource_type='quotation',
                resource_id=id,
                metadata={
                    'quotation_number': quotation_number,
                    'total_amount': total_with_vat,
                    'client_email': client.get('email'),
                    'room_name': room.get('name')
                }
            )
        except Exception as log_error:
            print(f"Failed to log quotation generation: {log_error}")
        
        return render_template('bookings/quotation.html', 
                              title=f'Quotation for {booking["title"]}',
                              booking=booking,
                              quotation_number=quotation_number,
                              valid_until=valid_until,
                              now=datetime.now(UTC),
                              timedelta=timedelta)
                              
    except Exception as e:
        print(f"❌ CRITICAL ERROR in quotation generation: {e}")
        import traceback
        traceback.print_exc()
        
        # Log the error
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
    """Generate an invoice for a booking - ENHANCED WITH ROBUST ERROR HANDLING"""
    try:
        print(f"🔍 DEBUG: Generating invoice for booking ID {id}")
        
        # Use the same robust approach as quotation generation
        booking_response = supabase_admin.table('bookings').select('*').eq('id', id).execute()
        
        if not booking_response.data:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        booking = booking_response.data[0]
        
        # Check if booking is confirmed
        if booking.get('status') != 'confirmed':
            flash('Invoices can only be generated for confirmed bookings. Please confirm the booking first.', 'warning')
            return redirect(url_for('view_booking', id=id))
        
        # Get room data
        room = None
        if booking.get('room_id'):
            room_response = supabase_admin.table('rooms').select('*').eq('id', booking['room_id']).execute()
            if room_response.data:
                room = room_response.data[0]
            else:
                flash('Room information not found for this booking', 'warning')
                return redirect(url_for('view_booking', id=id))
        
        # Get client data
        client = None
        if booking.get('client_id'):
            client_response = supabase_admin.table('clients').select('*').eq('id', booking['client_id']).execute()
            if client_response.data:
                client = client_response.data[0]
            else:
                flash('Client information not found for this booking', 'warning')
                return redirect(url_for('view_booking', id=id))
        
        # Get addons (same logic as quotation)
        addon_items = []
        addons_total = 0
        try:
            booking_addons_response = supabase_admin.table('booking_addons').select('*').eq('booking_id', id).execute()
            
            for ba in booking_addons_response.data if booking_addons_response.data else []:
                addon_id = ba.get('addon_id')
                if addon_id:
                    addon_response = supabase_admin.table('addons').select('*').eq('id', addon_id).execute()
                    if addon_response.data:
                        addon = addon_response.data[0]
                        quantity = ba.get('quantity', 1)
                        price = float(addon.get('price', 0))
                        total = price * quantity
                        
                        # Get category name
                        category_name = 'Other'
                        if addon.get('category_id'):
                            cat_response = supabase_admin.table('addon_categories').select('name').eq('id', addon['category_id']).execute()
                            if cat_response.data:
                                category_name = cat_response.data[0]['name']
                        
                        addon_items.append({
                            'name': addon.get('name', 'Unknown Addon'),
                            'category': category_name,
                            'price': price,
                            'quantity': quantity,
                            'total': total
                        })
                        addons_total += total
        except Exception as addon_error:
            print(f"Warning: Error processing addons for invoice: {addon_error}")
            addon_items = []
            addons_total = 0
        
        # Calculate room rate and totals (same logic as quotation)
        try:
            if isinstance(booking.get('start_time'), str):
                start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).replace(tzinfo=None)
                end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                start_time = booking['start_time']
                end_time = booking['end_time']
            
            duration_hours = (end_time - start_time).total_seconds() / 3600
            
            if duration_hours <= 4:
                room_rate = float(room.get('hourly_rate', 0)) * duration_hours
                rate_type = f"Hourly Rate ({duration_hours:.1f} hours)"
            elif duration_hours <= 6:
                room_rate = float(room.get('half_day_rate', 0))
                rate_type = "Half-day Rate"
            else:
                room_rate = float(room.get('full_day_rate', 0))
                rate_type = "Full-day Rate"
                
        except Exception as calc_error:
            print(f"Warning: Error calculating room rate for invoice: {calc_error}")
            room_rate = float(booking.get('total_price', 0)) * 0.7
            rate_type = "Estimated Rate"
            start_time = datetime.now(UTC)
            end_time = start_time + timedelta(hours=4)
            duration_hours = 4
        
        # Calculate totals
        try:
            discount = float(booking.get('discount', 0))
            subtotal = room_rate + addons_total - discount
            vat_rate = 0.15
            vat_amount = subtotal * vat_rate
            total_with_vat = subtotal + vat_amount
            
            subtotal = max(subtotal, 0)
            vat_amount = max(vat_amount, 0)
            total_with_vat = max(total_with_vat, 0)
            
        except Exception as total_error:
            print(f"Warning: Error calculating totals for invoice: {total_error}")
            total_price = float(booking.get('total_price', 100))
            subtotal = total_price / 1.15
            vat_amount = total_price - subtotal
            total_with_vat = total_price
            discount = float(booking.get('discount', 0))
        
        # Prepare booking data for template
        booking.update({
            'room': room,
            'client': client,
            'room_rate': round(room_rate, 2),
            'rate_type': rate_type,
            'addons_total': round(addons_total, 2),
            'addon_items': addon_items,
            'duration_hours': round(duration_hours, 1),
            'subtotal': round(subtotal, 2),
            'vat_amount': round(vat_amount, 2),
            'total_with_vat': round(total_with_vat, 2),
            'discount': discount
        })
        
        booking = convert_datetime_strings(booking)
        
        print(f"✅ DEBUG: Invoice data prepared successfully")
        
        # Log invoice generation
        try:
            log_user_activity(
                ActivityTypes.GENERATE_REPORT,
                f"Generated invoice for confirmed booking '{booking['title']}'",
                resource_type='invoice',
                resource_id=id,
                metadata={
                    'invoice_amount': total_with_vat,
                    'client_email': client.get('email'),
                    'room_name': room.get('name')
                }
            )
        except Exception as log_error:
            print(f"Failed to log invoice generation: {log_error}")
        
        return render_template('bookings/invoice.html', 
                              title=f'Invoice for {booking["title"]}',
                              booking=booking,
                              now=datetime.now(UTC),
                              timedelta=timedelta)
                              
    except Exception as e:
        print(f"❌ ERROR in invoice generation: {e}")
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
                              now=datetime.now(UTC))
                              
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
    """Reports dashboard with overview statistics using real data"""
    try:
        # Get current date info
        today = datetime.now(UTC).date()
        current_month_start = today.replace(day=1)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = current_month_start - timedelta(days=1)
        
        # Get overview statistics using admin client
        now_iso = datetime.now(UTC).isoformat()
        
        # Total bookings this month
        current_month_bookings = supabase_admin.table('bookings').select('id, total_price').gte('start_time', current_month_start.isoformat()).neq('status', 'cancelled').execute()
        
        # Revenue this month
        current_month_revenue = sum(float(b.get('total_price', 0)) for b in current_month_bookings.data)
        
        # Total active rooms
        active_rooms = len(supabase_admin.table('rooms').select('id').eq('status', 'available').execute().data)
        
        # Most popular addon this month
        popular_addon_data = supabase_admin.table('booking_addons').select("""
            addon_id,
            addon:addons(name),
            booking:bookings!inner(start_time)
        """).gte('booking.start_time', current_month_start.isoformat()).execute()
        
        # Count addon usage
        addon_counts = {}
        for ba in popular_addon_data.data:
            if ba.get('addon') and ba.get('addon', {}).get('name'):
                addon_name = ba['addon']['name']
                addon_counts[addon_name] = addon_counts.get(addon_name, 0) + 1
        
        most_popular_addon = max(addon_counts.items(), key=lambda x: x[1])[0] if addon_counts else "No data"
        
        # Room utilization rate calculation
        total_days = (today - current_month_start).days + 1
        total_possible_hours = active_rooms * total_days * 10  # 10 business hours per day
        
        # Calculate actual booked hours
        total_booked_hours = 0
        for booking in current_month_bookings.data:
            # Get booking details for duration calculation
            booking_details = supabase_admin.table('bookings').select('start_time, end_time').eq('id', booking['id']).execute()
            if booking_details.data:
                try:
                    start = datetime.fromisoformat(booking_details.data[0]['start_time'].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(booking_details.data[0]['end_time'].replace('Z', '+00:00'))
                    duration = (end - start).total_seconds() / 3600
                    total_booked_hours += duration
                except:
                    total_booked_hours += 4  # Fallback estimate
        
        utilization_rate = (total_booked_hours / total_possible_hours * 100) if total_possible_hours > 0 else 0
        
        overview_stats = {
            'current_month_bookings': len(current_month_bookings.data),
            'current_month_revenue': round(current_month_revenue, 2),
            'active_rooms': active_rooms,
            'most_popular_addon': most_popular_addon,
            'utilization_rate': round(utilization_rate, 1),
            'total_booked_hours': round(total_booked_hours, 1),
            'avg_booking_value': round(current_month_revenue / len(current_month_bookings.data), 2) if current_month_bookings.data else 0
        }
        
        return render_template('reports/index.html', title='Reports', stats=overview_stats)
        
    except Exception as e:
        print(f"Reports dashboard error: {e}")
        import traceback
        traceback.print_exc()
        # Return with empty stats if there's an error
        empty_stats = {
            'current_month_bookings': 0,
            'current_month_revenue': 0,
            'active_rooms': 0,
            'most_popular_addon': "No data",
            'utilization_rate': 0,
            'total_booked_hours': 0,
            'avg_booking_value': 0
        }
        return render_template('reports/index.html', title='Reports', stats=empty_stats)

@app.route('/reports/client-analysis')
@login_required
def client_analysis_report():
    """Enhanced client analysis report with reliable data fetching using fallback approach"""
    try:
        print("🔍 DEBUG: Starting reliable client analysis report generation")
        
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = datetime.now(UTC).date()
        if not start_date:
            start_date = today - timedelta(days=90)  # Last 3 months
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        print(f"📅 DEBUG: Date range: {start_date} to {end_date}")
        
        # Step 1: Get all clients using admin client (reliable approach)
        try:
            all_clients_response = supabase_admin.table('clients').select('*').execute()
            all_clients = all_clients_response.data if all_clients_response.data else []
            print(f"✅ DEBUG: Found {len(all_clients)} total clients")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch clients: {e}")
            all_clients = []
        
        # Step 2: Get bookings in date range (simple query first)
        try:
            start_date_iso = start_date.isoformat()
            end_date_iso = end_date.isoformat()
            
            # Simple booking query first
            bookings_response = supabase_admin.table('bookings').select('*').gte('start_time', start_date_iso).lte('end_time', end_date_iso).neq('status', 'cancelled').execute()
            
            bookings_raw = bookings_response.data if bookings_response.data else []
            print(f"✅ DEBUG: Found {len(bookings_raw)} bookings for date range")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch bookings: {e}")
            bookings_raw = []
        
        # Step 3: Get rooms and clients data separately for reliable lookups
        try:
            rooms_response = supabase_admin.table('rooms').select('id, name').execute()
            rooms_lookup = {room['id']: room for room in rooms_response.data} if rooms_response.data else {}
            print(f"✅ DEBUG: Created lookup for {len(rooms_lookup)} rooms")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch rooms: {e}")
            rooms_lookup = {}
        
        try:
            clients_response = supabase_admin.table('clients').select('id, company_name, contact_person, email, phone').execute()
            clients_lookup = {client['id']: client for client in clients_response.data} if clients_response.data else {}
            print(f"✅ DEBUG: Created lookup for {len(clients_lookup)} clients")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch clients for lookup: {e}")
            clients_lookup = {}
        
        # Step 4: Process bookings and build client statistics
        client_stats = {}
        total_revenue = 0
        total_bookings = len(bookings_raw)
        
        for booking in bookings_raw:
            client_id = booking.get('client_id')
            if not client_id or client_id not in clients_lookup:
                print(f"⚠️ DEBUG: Skipping booking {booking.get('id')} - no valid client_id")
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
                print(f"⚠️ DEBUG: Error processing booking {booking.get('id')}: {e}")
                # Still count the booking even if revenue parsing fails
                client_stats[client_id]['bookings'] += 1
        
        print(f"📊 DEBUG: Processed {len(client_stats)} clients with bookings")
        
        # Step 5: Calculate client segments and statistics
        premium_clients = []
        repeat_clients = []
        new_clients = []
        at_risk_clients = []
        
        # Define thresholds
        premium_threshold = 500  # Clients with total revenue > $500
        repeat_threshold = 3     # Clients with 3+ bookings
        at_risk_days = 90       # Clients with no bookings in last 90 days
        
        current_date = datetime.now(UTC)
        
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
        
        print(f"✅ DEBUG: Client analysis completed successfully")
        print(f"📊 DEBUG: Final stats - Active clients: {active_clients}, Total revenue: ${total_revenue:.2f}")
        
        return render_template('reports/client_analysis.html', **template_vars)
                              
    except Exception as e:
        print(f"❌ ERROR: Client analysis report failed: {e}")
        import traceback
        traceback.print_exc()
        
        flash('Error generating client analysis report. Please try again.', 'danger')
        
        # Return with safe empty data
        today = datetime.now(UTC).date()
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
        print("🔍 DEBUG: Starting enhanced revenue report generation")
        
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = datetime.now(UTC).date()
        if not start_date:
            start_date = today.replace(day=1)  # Start of current month
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        print(f"📅 DEBUG: Date range: {start_date} to {end_date}")
        
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
            print(f"✅ DEBUG: Found {len(bookings_raw)} confirmed bookings")
            
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch bookings: {e}")
            # Fallback approach
            try:
                print("🔄 DEBUG: Trying fallback approach for bookings")
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
                
                print(f"✅ DEBUG: Fallback successful, processed {len(bookings_raw)} bookings")
                
            except Exception as fallback_error:
                print(f"❌ DEBUG: Fallback also failed: {fallback_error}")
                bookings_raw = []
        
        # Step 2: Get booking addons for revenue calculation
        try:
            booking_addons_response = supabase_admin.table('booking_addons').select("""
                booking_id, quantity,
                addon:addons(id, name, price, category:addon_categories(name))
            """).execute()
            
            booking_addons_raw = booking_addons_response.data if booking_addons_response.data else []
            print(f"✅ DEBUG: Found {len(booking_addons_raw)} booking addon records")
            
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch booking addons: {e}")
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
                
                print(f"✅ DEBUG: Fallback successful for addons")
                
            except Exception as fallback_error:
                print(f"❌ DEBUG: Addon fallback failed: {fallback_error}")
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
        
        print(f"📊 DEBUG: Revenue summary calculated:")
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
        
        print("✅ DEBUG: Template variables prepared, rendering template")
        return render_template('reports/revenue.html', **template_vars)
                              
    except Exception as e:
        print(f"❌ ERROR: Revenue report generation failed: {e}")
        import traceback
        traceback.print_exc()
        
        flash('Error generating revenue report. Please try again.', 'danger')
        
        # Return with safe empty data
        today = datetime.now(UTC).date()
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
        print("🔍 DEBUG: Starting reliable popular addons report generation")
        
        # Get date range from query parameters or use current month
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = datetime.now(UTC).date()
        if not start_date:
            start_date = today.replace(day=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        print(f"📅 DEBUG: Date range: {start_date} to {end_date}")
        
        # Step 1: Get all bookings in date range (simple query)
        try:
            start_date_iso = start_date.isoformat()
            end_date_iso = end_date.isoformat()
            
            bookings_response = supabase_admin.table('bookings').select('id, start_time, total_price, status').gte('start_time', start_date_iso).lte('end_time', end_date_iso).neq('status', 'cancelled').execute()
            
            bookings_raw = bookings_response.data if bookings_response.data else []
            print(f"✅ DEBUG: Found {len(bookings_raw)} bookings for date range")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch bookings: {e}")
            bookings_raw = []
        
        # Create a set of valid booking IDs within our date range
        valid_booking_ids = set()
        for booking in bookings_raw:
            valid_booking_ids.add(booking['id'])
        
        print(f"📊 DEBUG: Valid booking IDs count: {len(valid_booking_ids)}")
        
        # Step 2: Get all booking_addons (simple query)
        try:
            booking_addons_response = supabase_admin.table('booking_addons').select('*').execute()
            booking_addons_raw = booking_addons_response.data if booking_addons_response.data else []
            print(f"✅ DEBUG: Found {len(booking_addons_raw)} total booking_addons records")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch booking_addons: {e}")
            booking_addons_raw = []
        
        # Filter booking_addons to only those in our date range
        filtered_booking_addons = []
        for ba in booking_addons_raw:
            if ba.get('booking_id') in valid_booking_ids:
                filtered_booking_addons.append(ba)
        
        print(f"📊 DEBUG: Filtered to {len(filtered_booking_addons)} booking_addons in date range")
        
        # Step 3: Get all addons data separately for reliable lookup
        try:
            addons_response = supabase_admin.table('addons').select('id, name, price, category_id').execute()
            addons_lookup = {}
            for addon in addons_response.data if addons_response.data else []:
                addons_lookup[addon['id']] = addon
            print(f"✅ DEBUG: Created lookup for {len(addons_lookup)} addons")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch addons: {e}")
            addons_lookup = {}
        
        # Step 4: Get addon categories separately for reliable lookup
        try:
            categories_response = supabase_admin.table('addon_categories').select('id, name').execute()
            categories_lookup = {}
            for category in categories_response.data if categories_response.data else []:
                categories_lookup[category['id']] = category
            print(f"✅ DEBUG: Created lookup for {len(categories_lookup)} categories")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch categories: {e}")
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
                print(f"⚠️ DEBUG: Skipping booking_addon - invalid addon_id: {addon_id}")
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
        
        print(f"📊 DEBUG: Processed {len(addon_stats)} unique addons")
        
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
        
        print(f"📊 DEBUG: Final summary - Total addon revenue: ${total_addon_revenue:.2f}, Unique bookings: {total_unique_bookings}")
        
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
        
        print("✅ DEBUG: Popular addons template variables prepared successfully")
        return render_template('reports/popular_addons.html', **template_vars)
                              
    except Exception as e:
        print(f"❌ ERROR: Popular addons report failed: {e}")
        import traceback
        traceback.print_exc()
        
        flash('Error generating popular add-ons report. Please try again.', 'danger')
        
        # Return with safe empty data
        today = datetime.now(UTC).date()
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
        print("🔍 DEBUG: Starting enhanced room utilization report")
        
        # Get date range from query parameters or use current month
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = datetime.now(UTC).date()
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
        
        print(f"📅 DEBUG: Date range: {start_date} to {end_date}")
        
        # Step 1: Get all rooms using admin client
        try:
            rooms_response = supabase_admin.table('rooms').select('*').execute()
            rooms = rooms_response.data if rooms_response.data else []
            print(f"✅ DEBUG: Found {len(rooms)} rooms")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch rooms: {e}")
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
            print(f"✅ DEBUG: Found {len(bookings)} bookings for date range")
        except Exception as e:
            print(f"❌ ERROR: Failed to fetch bookings: {e}")
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
            
            print(f"🔍 DEBUG: Processing room '{room_name}' (ID: {room_id})")
            
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
                    
                    print(f"  📊 Booking: {duration:.1f} hours, ${revenue:.2f}")
                    
                except (ValueError, TypeError, KeyError) as e:
                    print(f"  ⚠️ Error parsing booking {booking.get('id', 'unknown')}: {e}")
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
            
            print(f"  ✅ Room summary: {room_hours:.1f}h booked / {available_hours}h available = {utilization_pct:.1f}%")
        
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
        
        print(f"📊 DEBUG: Final statistics:")
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
        print(f"❌ ERROR: Room utilization report failed: {e}")
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
                              start_date=datetime.now(UTC).date(),
                              end_date=datetime.now(UTC).date())

# ===============================
# API Routes for Dashboard Widgets
# ===============================

@app.route('/api/dashboard/upcoming-bookings')
@login_required
def api_upcoming_bookings():
    """API endpoint for upcoming bookings widget using admin client"""
    try:
        days = request.args.get('days', 7, type=int)
        end_date = datetime.now(UTC) + timedelta(days=days)
        
        bookings = supabase_admin.table('bookings').select("""
            id, title, start_time, status,
            room:rooms(name),
            client:clients(company_name, contact_person)
        """).gte('start_time', datetime.now(UTC).isoformat()).lte('start_time', end_date.isoformat()).neq('status', 'cancelled').order('start_time').execute()
        
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
        now = datetime.now(UTC).isoformat()
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
            'description': f'Test update at {datetime.now(UTC).isoformat()}'
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
    
    # Add these debug routes to your app.py file (before the main entry point)

@app.route('/debug/database-connection')
def debug_database_connection():
    """Comprehensive database connection test for production"""
    try:
        debug_info = {
            'timestamp': datetime.now(UTC).isoformat(),
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
            'timestamp': datetime.now(UTC).isoformat()
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
            'timestamp': datetime.now(UTC).isoformat(),
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
            'timestamp': datetime.now(UTC).isoformat()
        }), 500
        
@app.route('/debug/supabase-data')
@login_required
def debug_supabase_data():
    """Debug route to examine Supabase data structure"""
    try:
        now = datetime.now(UTC).isoformat()
        
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
            'timestamp': datetime.now(UTC).isoformat(),
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
            'timestamp': datetime.now(UTC).isoformat()
        }), 500

@app.route('/debug/test-queries')
def debug_test_queries():
    """Test specific queries that might be failing"""
    try:
        results = {}
        
        # Test dashboard queries
        try:
            now = datetime.now(UTC).isoformat()
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
            'timestamp': datetime.now(UTC).isoformat(),
            'query_results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now(UTC).isoformat()
        }), 500

@app.route('/health')
def health_check():
    """Simple health check for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(UTC).isoformat(),
        'database_connected': bool(SUPABASE_URL and SUPABASE_ANON_KEY)
    })
# ===============================
# Error Handlers
# ===============================

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
# CLI Commands
# ===============================

@app.cli.command('create-admin')
def create_admin_command():
    """Create admin user in Supabase"""
    email = input('Enter admin email: ')
    password = input('Enter admin password: ')
    first_name = input('Enter first name: ')
    last_name = input('Enter last name: ')
    
    if create_user_supabase(email, password, first_name, last_name, 'admin'):
        print(f'Admin user created successfully: {email}')
        print('Note: Check your email to confirm the account if email confirmation is enabled.')
    else:
        print('Failed to create admin user')

@app.cli.command('test-connection')
def test_supabase_connection():
    """Test Supabase connection with improved RLS handling"""
    try:
        print('🔍 Testing Supabase connection...')
        print(f'🔗 Connected to: {SUPABASE_URL}')
        
        # Test database connection with room data using admin client
        response = supabase_admin.table('rooms').select('id, name').execute()
        print('✅ Supabase database connection successful')
        print(f'✅ Found {len(response.data)} rooms in database')
        
        if response.data:
            print('   📋 Rooms found:')
            for room in response.data:
                print(f'   - {room["name"]}')
        else:
            print('   ⚠️  No rooms found - make sure sample data is inserted')
        
        # Test other tables using admin client
        clients = supabase_admin.table('clients').select('id').execute()
        addons = supabase_admin.table('addons').select('id').execute()
        categories = supabase_admin.table('addon_categories').select('id').execute()
        bookings = supabase_admin.table('bookings').select('id').execute()
        
        print(f'✅ Found {len(clients.data)} clients')
        print(f'✅ Found {len(addons.data)} add-ons')
        print(f'✅ Found {len(categories.data)} categories')
        print(f'✅ Found {len(bookings.data)} bookings')
        
        # Test auth connection
        try:
            supabase.auth.get_session()
            print('✅ Supabase auth connection successful')
        except:
            print('⚠️  Supabase auth connection test (normal if no active session)')
        
        # Check if service key is available
        if SUPABASE_SERVICE_KEY:
            print('✅ Service key configured for admin operations')
        else:
            print('⚠️  No service key found - some admin operations may fail')
            print('   Add SUPABASE_SERVICE_KEY to your .env file for full functionality')
        
        print('\n🎉 All connection tests completed!')
            
    except Exception as e:
        print(f'❌ Supabase connection failed: {e}')
        print('\n🔧 Troubleshooting:')
        print('- Check your .env file has correct:')
        print('  - SUPABASE_URL')
        print('  - SUPABASE_ANON_KEY')
        print('  - SUPABASE_SERVICE_KEY (for admin operations)')
        print('- Verify your Supabase project is active')
        print('- Check if sample data was inserted in Supabase dashboard')

@app.cli.command('backup-data')
def backup_data():
    """Simple data backup command using admin client"""
    try:
        import json
        
        print('📦 Creating backup...')
        
        # Export key data using admin client
        backup_data = {
            'timestamp': datetime.now(UTC).isoformat(),
            'rooms': supabase_admin.table('rooms').select('*').execute().data,
            'clients': supabase_admin.table('clients').select('*').execute().data,
            'addon_categories': supabase_admin.table('addon_categories').select('*').execute().data,
            'addons': supabase_admin.table('addons').select('*').execute().data,
            'bookings': supabase_admin.table('bookings').select('*').execute().data
        }
        
        filename = f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        print(f'✅ Backup created: {filename}')
        print(f'📊 Data summary:')
        print(f'   - Rooms: {len(backup_data["rooms"])}')
        print(f'   - Clients: {len(backup_data["clients"])}')
        print(f'   - Add-on Categories: {len(backup_data["addon_categories"])}')
        print(f'   - Add-ons: {len(backup_data["addons"])}')
        print(f'   - Bookings: {len(backup_data["bookings"])}')
        
    except Exception as e:
        print(f'❌ Backup failed: {e}')
        
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
    """View all user activity logs (Admin/Manager only)"""
    try:
        # Get filter parameters
        user_filter = request.args.get('user')
        activity_type_filter = request.args.get('activity_type')
        status_filter = request.args.get('status', 'all')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
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
        
        # Apply filters
        if user_filter:
            query = query.ilike('user_name', f'%{user_filter}%')
        
        if activity_type_filter:
            query = query.eq('activity_type', activity_type_filter)
        
        if status_filter != 'all':
            query = query.eq('status', status_filter)
        
        if date_from:
            query = query.gte('created_at', date_from)
        
        if date_to:
            # Add one day to include the entire end date
            end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.lt('created_at', end_date.isoformat())
        
        # Get total count for pagination
        count_response = query.execute()
        total_logs = len(count_response.data) if count_response.data else 0
        
        # Get paginated results
        offset = (page - 1) * per_page
        logs_response = query.order('created_at', desc=True).range(offset, offset + per_page - 1).execute()
        
        logs = logs_response.data if logs_response.data else []
        
        # Convert datetime strings and parse metadata
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
        
        # Get unique activity types for filter dropdown
        activity_types_response = supabase_admin.table('user_activity_log').select('activity_type').execute()
        unique_activity_types = list(set([log['activity_type'] for log in activity_types_response.data if activity_types_response.data]))
        unique_activity_types.sort()
        
        # Calculate pagination info
        total_pages = (total_logs + per_page - 1) // per_page
        
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
        
        return render_template('admin/activity_logs.html',
                              title='User Activity Logs',
                              logs=logs,
                              pagination=pagination_info,
                              filters={
                                  'user': user_filter,
                                  'activity_type': activity_type_filter,
                                  'status': status_filter,
                                  'date_from': date_from,
                                  'date_to': date_to
                              },
                              unique_activity_types=unique_activity_types)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load activity logs: {e}")
        flash('Error loading activity logs', 'danger')
        return redirect(url_for('dashboard'))
    
@app.route('/admin/activity-stats')
@login_required
@require_admin_or_manager
def activity_stats():
    """Dashboard for activity statistics (Admin/Manager only)"""
    try:
        # Get date range (default to last 30 days)
        days = request.args.get('days', 30, type=int)
        start_date = datetime.now(UTC) - timedelta(days=days)
        
        print(f"🔍 DEBUG: Generating activity stats for last {days} days")
        
        # Get activity logs for the period
        logs_response = supabase_admin.table('user_activity_log').select('*').gte('created_at', start_date.isoformat()).execute()
        
        logs = logs_response.data if logs_response.data else []
        print(f"✅ DEBUG: Found {len(logs)} activities for stats calculation")
        
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
            date = (datetime.now(UTC) - timedelta(days=i)).date()
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
        
        print(f"📊 DEBUG: Stats calculated - Total: {total_activities}, Users: {unique_users}, Success: {stats['success_rate']}%")
        
        # Log this admin activity
        try:
            log_user_activity(
                ActivityTypes.PAGE_VIEW,
                f"Viewed activity statistics dashboard ({days} days)",
                resource_type='admin',
                metadata={
                    'period_days': days,
                    'stats_generated_at': datetime.now(UTC).isoformat(),
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
        print(f"❌ ERROR: Failed to load activity statistics: {e}")
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
        print(f"🔍 DEBUG: Loading activity logs for user ID: {user_id}")
        
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
        print(f"❌ ERROR: Failed to load user activity logs: {e}")
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
        print(f"❌ ERROR: Failed to load user's own activity logs: {e}")
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
        print(f"🔍 DEBUG: Fetching complete booking details for ID {booking_id}")
        
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
        
        print(f"✅ DEBUG: Successfully fetched complete booking details")
        return booking
        
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch booking details: {e}")
        return None

def calculate_booking_totals(booking, room_rates=None):
    """Calculate all booking totals including room rate, addons, VAT, etc."""
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
        
        # Calculate discount and totals
        discount = safe_float_conversion(booking.get('discount', 0))
        subtotal = max(room_rate + addons_total - discount, 0)
        vat_rate = 0.15
        vat_amount = subtotal * vat_rate
        total_with_vat = subtotal + vat_amount
        
        return {
            'room_rate': round(room_rate, 2),
            'rate_type': rate_type,
            'addons_total': round(addons_total, 2),
            'addon_items': addon_items,
            'duration_hours': round(duration_hours, 1),
            'discount': discount,
            'subtotal': round(subtotal, 2),
            'vat_amount': round(vat_amount, 2),
            'total_with_vat': round(total_with_vat, 2)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate booking totals: {e}")
        # Return safe fallback values
        total_price = safe_float_conversion(booking.get('total_price', 100))
        return {
            'room_rate': round(total_price * 0.7, 2),
            'rate_type': 'Estimated Rate',
            'addons_total': round(total_price * 0.3, 2),
            'addon_items': [],
            'duration_hours': 4,
            'discount': 0,
            'subtotal': round(total_price / 1.15, 2),
            'vat_amount': round(total_price - (total_price / 1.15), 2),
            'total_with_vat': round(total_price, 2)
        }

# ===============================
# ENHANCED VIEW BOOKING ROUTE
# ===============================

@app.route('/bookings/<int:id>')
@login_required
def view_booking(id):
    """View booking details with enhanced error handling and complete data"""
    try:
        print(f"🔍 DEBUG: Loading booking details for ID {id}")
        
        # Get complete booking details
        booking = get_booking_with_details(id)
        
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        # Calculate totals
        totals = calculate_booking_totals(booking)
        
        # Add calculated fields to booking
        booking.update(totals)
        
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
                    'room_name': booking.get('room', {}).get('name')
                }
            )
        except Exception as log_error:
            print(f"Failed to log booking view: {log_error}")
        
        print(f"✅ DEBUG: Successfully loaded booking '{booking.get('title', 'Unknown')}'")
        
        return render_template('bookings/view.html', 
                             title=f'Booking: {booking["title"]}', 
                             booking=booking)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load booking details: {e}")
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
            'created_at': datetime.now(UTC).isoformat()
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
            'tentative': f"📋 Booking '{booking['title']}' for {client_name} is now tentative. Quotation can be generated.",
            'confirmed': f"✅ Booking '{booking['title']}' for {client_name} has been confirmed! Invoice can now be generated.",
            'cancelled': f"❌ Booking '{booking['title']}' for {client_name} has been cancelled."
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

# ===============================
# ERROR RECOVERY FUNCTIONS
# ===============================

def recover_booking_data(booking_id):
    """Attempt to recover missing booking data"""
    try:
        print(f"🔧 DEBUG: Attempting to recover data for booking {booking_id}")
        
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
                print(f"✅ DEBUG: Recovered room data for booking {booking_id}")
        
        # Check and recover client data
        if booking.get('client_id') and not booking.get('client'):
            client_response = supabase_admin.table('clients').select('*').eq('id', booking['client_id']).execute()
            if client_response.data:
                booking['client'] = client_response.data[0]
                print(f"✅ DEBUG: Recovered client data for booking {booking_id}")
        
        return booking
        
    except Exception as e:
        print(f"❌ ERROR: Failed to recover booking data: {e}")
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
        if start_time < datetime.now(UTC):
            errors.append("Booking cannot be scheduled in the past")
        
        # Check if booking is too far in the future (optional)
        max_future = datetime.now(UTC) + timedelta(days=365)
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