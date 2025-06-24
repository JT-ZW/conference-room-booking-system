#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rainbow Towers Conference Room Booking System
Flask Application File with Complete Supabase Integration

This file contains the main application code for the conference room booking system,
including Supabase database integration, authentication, and core functionality.
"""

import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, DateTimeField, TextAreaField, IntegerField, DecimalField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Length, ValidationError
import json
from decimal import Decimal
from flask_wtf.csrf import CSRFProtect
from supabase import create_client, Client
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Supabase Configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("Please set SUPABASE_URL and SUPABASE_ANON_KEY environment variables")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_SERVICE_KEY else supabase

# Initialize extensions
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@app.context_processor
def inject_now():
    """Inject the current datetime into templates."""
    return {'now': datetime.utcnow()}

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
        """Get user profile from Supabase users table"""
        try:
            response = supabase.table('users').select('*').eq('id', self.id).execute()
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
    """Authenticate user with Supabase"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            session['supabase_session'] = {
                'access_token': response.session.access_token,
                'refresh_token': response.session.refresh_token,
                'user_id': response.user.id
            }
            return User(response.user.__dict__)
        return None
    except Exception as e:
        print(f"Authentication error: {e}")
        return None

def create_user_supabase(email, password, first_name, last_name, role='staff'):
    """Create new user in Supabase"""
    try:
        # Create user in Supabase Auth
        auth_response = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True  # Auto-confirm for internal users
        })
        
        if auth_response.user:
            # Create profile in users table using admin client
            profile_data = {
                'id': auth_response.user.id,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'username': email.split('@')[0],
                'role': role,
                'is_active': True
            }
            
            # Use admin client to bypass RLS
            supabase_admin.table('users').insert(profile_data).execute()
            return True
        return False
    except Exception as e:
        print(f"User creation error: {e}")
        return False

def supabase_select(table_name, columns="*", filters=None, order_by=None, limit=None):
    """Select data from Supabase table"""
    try:
        query = supabase.table(table_name).select(columns)
        
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
        return response.data
    except Exception as e:
        print(f"Select error: {e}")
        return []

def supabase_insert(table_name, data):
    """Insert data into Supabase table"""
    try:
        response = supabase.table(table_name).insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Insert error: {e}")
        return None

def supabase_update(table_name, data, filters):
    """Update data in Supabase table"""
    try:
        query = supabase.table(table_name)
        
        for filter_item in filters:
            if len(filter_item) == 3:
                column, operator, value = filter_item
                if operator == 'eq':
                    query = query.eq(column, value)
        
        response = query.update(data).execute()
        return response.data
    except Exception as e:
        print(f"Update error: {e}")
        return []

def supabase_delete(table_name, filters):
    """Delete data from Supabase table"""
    try:
        query = supabase.table(table_name)
        
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
# Forms
# ===============================

class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

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
    """Check if a room is available using Supabase"""
    try:
        # Build query to find overlapping bookings
        query = supabase.table('bookings').select('id')
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
    """Get all bookings formatted for FullCalendar using Supabase"""
    try:
        # Get bookings with room and client data
        bookings_data = supabase.table('bookings').select("""
            id, title, start_time, end_time, status,
            room:rooms(name),
            client:clients(company_name, contact_person)
        """).execute()
        
        events = []
        for booking in bookings_data.data:
            color = {
                'tentative': '#FFA500',  # Orange
                'confirmed': '#28a745',  # Green
                'cancelled': '#dc3545'   # Red
            }.get(booking['status'], '#17a2b8')  # Default: Teal
            
            events.append({
                'id': booking['id'],
                'title': booking['title'],
                'start': booking['start_time'],
                'end': booking['end_time'],
                'color': color,
                'extendedProps': {
                    'room': booking['room']['name'] if booking['room'] else 'Unknown Room',
                    'client': booking['client']['company_name'] or booking['client']['contact_person'] if booking['client'] else 'Unknown Client',
                    'status': booking['status']
                }
            })
        
        return events
    except Exception as e:
        print(f"Calendar events error: {e}")
        return []

def calculate_booking_total(room_id, start_time, end_time, addon_ids=None, discount=0):
    """Calculate total price for a booking"""
    try:
        # Get room data
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
    """User login page with Supabase authentication"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate_user(form.username.data, form.password.data)
        if user:
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(next_page or url_for('dashboard'))
        flash('Invalid email or password', 'danger')
    
    return render_template('login.html', form=form, title='Sign In')

@app.route('/logout')
@login_required
def logout():
    """User logout with Supabase"""
    try:
        supabase.auth.sign_out()
        session.pop('supabase_session', None)
        logout_user()
        flash('You have been logged out', 'info')
    except:
        pass
    
    return redirect(url_for('login'))

# ===============================
# Routes - Dashboard
# ===============================

@app.route('/')
@login_required
def dashboard():
    """Main dashboard page using Supabase"""
    try:
        # Get statistics
        now = datetime.utcnow().isoformat()
        today = datetime.utcnow().date().isoformat()
        tomorrow = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
        
        # Upcoming bookings (next 5)
        upcoming_bookings = supabase.table('bookings').select("""
            *,
            room:rooms(name),
            client:clients(company_name, contact_person)
        """).gte('start_time', now).neq('status', 'cancelled').order('start_time').limit(5).execute()
        
        # Today's bookings
        today_bookings = supabase.table('bookings').select("""
            *,
            room:rooms(name),
            client:clients(company_name, contact_person)
        """).gte('start_time', today).lt('start_time', tomorrow).neq('status', 'cancelled').execute()
        
        # Total counts using admin client for reliable counts
        total_rooms = len(supabase_admin.table('rooms').select('id').execute().data)
        total_clients = len(supabase_admin.table('clients').select('id').execute().data)
        total_active_bookings = len(supabase.table('bookings').select('id').gte('end_time', now).neq('status', 'cancelled').execute().data)
        
        return render_template('dashboard.html',
                              title='Dashboard',
                              upcoming_bookings=upcoming_bookings.data,
                              today_bookings=today_bookings.data,
                              total_rooms=total_rooms,
                              total_clients=total_clients,
                              total_active_bookings=total_active_bookings)
        
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template('dashboard.html',
                              title='Dashboard',
                              upcoming_bookings=[],
                              today_bookings=[],
                              total_rooms=0,
                              total_clients=0,
                              total_active_bookings=0)

@app.route('/calendar')
@login_required
def calendar():
    """Calendar view for bookings"""
    try:
        rooms_data = supabase_select('rooms')
        return render_template('calendar.html', title='Booking Calendar', rooms=rooms_data)
    except Exception as e:
        print(f"Calendar error: {e}")
        return render_template('calendar.html', title='Booking Calendar', rooms=[])

@app.route('/api/events')
@login_required
def get_events():
    """API endpoint to get calendar events from Supabase"""
    try:
        events = get_booking_calendar_events_supabase()
        return jsonify(events)
    except Exception as e:
        print(f"Calendar events error: {e}")
        return jsonify([])

# ===============================
# Routes - Rooms
# ===============================

@app.route('/rooms')
@login_required
def rooms():
    """List all conference rooms using Supabase"""
    rooms_data = supabase_select('rooms', order_by='name')
    return render_template('rooms/index.html', title='Conference Rooms', rooms=rooms_data)

@app.route('/rooms/new', methods=['GET', 'POST'])
@login_required
def new_room():
    """Add a new conference room to Supabase"""
    form = RoomForm()
    if form.validate_on_submit():
        amenities_list = [item.strip() for item in form.amenities.data.split(',') if item.strip()]
        
        room_data = {
            'name': form.name.data,
            'capacity': form.capacity.data,
            'description': form.description.data,
            'hourly_rate': float(form.hourly_rate.data),
            'half_day_rate': float(form.half_day_rate.data),
            'full_day_rate': float(form.full_day_rate.data),
            'amenities': amenities_list,
            'status': form.status.data,
            'image_url': form.image_url.data
        }
        
        result = supabase_insert('rooms', room_data)
        if result:
            flash('Conference room added successfully', 'success')
            return redirect(url_for('rooms'))
        else:
            flash('Error adding conference room', 'danger')
    
    return render_template('rooms/form.html', title='Add Conference Room', form=form)

@app.route('/rooms/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(id):
    """Edit a conference room in Supabase"""
    room_data = supabase_select('rooms', filters=[('id', 'eq', id)])
    if not room_data:
        flash('Room not found', 'danger')
        return redirect(url_for('rooms'))
    
    room = room_data[0]
    form = RoomForm()
    
    if form.validate_on_submit():
        amenities_list = [item.strip() for item in form.amenities.data.split(',') if item.strip()]
        
        update_data = {
            'name': form.name.data,
            'capacity': form.capacity.data,
            'description': form.description.data,
            'hourly_rate': float(form.hourly_rate.data),
            'half_day_rate': float(form.half_day_rate.data),
            'full_day_rate': float(form.full_day_rate.data),
            'amenities': amenities_list,
            'status': form.status.data,
            'image_url': form.image_url.data
        }
        
        result = supabase_update('rooms', update_data, [('id', 'eq', id)])
        if result:
            flash('Conference room updated successfully', 'success')
            return redirect(url_for('rooms'))
        else:
            flash('Error updating conference room', 'danger')
    else:
        # Pre-fill form with existing data
        form.name.data = room['name']
        form.capacity.data = room['capacity']
        form.description.data = room['description']
        form.hourly_rate.data = room['hourly_rate']
        form.half_day_rate.data = room['half_day_rate']
        form.full_day_rate.data = room['full_day_rate']
        form.status.data = room['status']
        form.image_url.data = room['image_url']
        
        if room['amenities']:
            form.amenities.data = ', '.join(room['amenities'])
    
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
# Routes - Clients
# ===============================

@app.route('/clients')
@login_required
def clients():
    """List all clients using Supabase"""
    clients_data = supabase_select('clients', order_by='company_name')
    return render_template('clients/index.html', title='Clients', clients=clients_data)

@app.route('/clients/new', methods=['GET', 'POST'])
@login_required
def new_client():
    """Add a new client to Supabase"""
    form = ClientForm()
    if form.validate_on_submit():
        client_data = {
            'company_name': form.company_name.data,
            'contact_person': form.contact_person.data,
            'email': form.email.data,
            'phone': form.phone.data,
            'address': form.address.data,
            'notes': form.notes.data
        }
        
        result = supabase_insert('clients', client_data)
        if result:
            flash('Client added successfully', 'success')
            return redirect(url_for('clients'))
        else:
            flash('Error adding client', 'danger')
    
    return render_template('clients/form.html', title='Add Client', form=form)

@app.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(id):
    """Edit a client"""
    client_data = supabase_select('clients', filters=[('id', 'eq', id)])
    if not client_data:
        flash('Client not found', 'danger')
        return redirect(url_for('clients'))
    
    client = client_data[0]
    form = ClientForm(data=client)
    
    if form.validate_on_submit():
        update_data = {
            'company_name': form.company_name.data,
            'contact_person': form.contact_person.data,
            'email': form.email.data,
            'phone': form.phone.data,
            'address': form.address.data,
            'notes': form.notes.data
        }
        
        result = supabase_update('clients', update_data, [('id', 'eq', id)])
        if result:
            flash('Client updated successfully', 'success')
            return redirect(url_for('clients'))
        else:
            flash('Error updating client', 'danger')
    
    return render_template('clients/form.html', title='Edit Client', form=form, client=client)

@app.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def delete_client(id):
    """Delete a client"""
    bookings = supabase_select('bookings', filters=[('client_id', 'eq', id)])
    
    if bookings:
        flash('Cannot delete client with existing bookings', 'danger')
    else:
        if supabase_delete('clients', [('id', 'eq', id)]):
            flash('Client deleted successfully', 'success')
        else:
            flash('Error deleting client', 'danger')
    
    return redirect(url_for('clients'))

@app.route('/clients/<int:id>')
@login_required
def view_client(id):
    """View client details and booking history"""
    client_data = supabase_select('clients', filters=[('id', 'eq', id)])
    if not client_data:
        flash('Client not found', 'danger')
        return redirect(url_for('clients'))
    
    client = client_data[0]
    bookings = supabase.table('bookings').select("""
        *,
        room:rooms(name)
    """).eq('client_id', id).order('start_time', desc=True).execute()
    
    return render_template('clients/view.html', 
                          title=f'Client: {client["company_name"] or client["contact_person"]}', 
                          client=client, 
                          bookings=bookings.data)

# ===============================
# Routes - Add-ons
# ===============================

@app.route('/addons')
@login_required
def addons():
    """List all add-ons by category"""
    categories_data = supabase.table('addon_categories').select("""
        *,
        addons(*)
    """).execute()
    return render_template('addons/index.html', title='Add-ons', categories=categories_data.data)

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
def new_addon_category():
    """Add a new add-on category"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Category name is required', 'danger')
            return redirect(url_for('addons'))
        
        category_data = {'name': name, 'description': description}
        result = supabase_insert('addon_categories', category_data)
        
        if result:
            flash('Category added successfully', 'success')
        else:
            flash('Error adding category', 'danger')
            
        return redirect(url_for('addons'))
    
    return render_template('addons/new_category.html', title='New Add-on Category')

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
# Routes - Bookings
# ===============================

@app.route('/bookings')
@login_required
def bookings():
    """List all bookings using Supabase"""
    status_filter = request.args.get('status', 'all')
    date_filter = request.args.get('date', 'upcoming')
    
    try:
        query = supabase.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, company_name, contact_person),
            created_by_user:users(first_name, last_name)
        """)
        
        # Apply status filter
        if status_filter != 'all':
            query = query.eq('status', status_filter)
        
        # Apply date filter
        now = datetime.utcnow().isoformat()
        today = datetime.utcnow().date().isoformat()
        tomorrow = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
        
        if date_filter == 'upcoming':
            query = query.gte('end_time', now)
        elif date_filter == 'past':
            query = query.lt('end_time', now)
        elif date_filter == 'today':
            query = query.gte('start_time', today).lt('start_time', tomorrow)
        
        response = query.order('start_time').execute()
        bookings_data = response.data
        
    except Exception as e:
        print(f"Error fetching bookings: {e}")
        bookings_data = []
        flash('Error loading bookings', 'warning')
    
    return render_template('bookings/index.html', 
                          title='Bookings', 
                          bookings=bookings_data,
                          status_filter=status_filter,
                          date_filter=date_filter)

@app.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def new_booking():
    """Create a new booking using Supabase"""
    form = BookingForm()
    
    # Populate form choices from Supabase
    try:
        rooms_data = supabase_select('rooms', filters=[('status', 'eq', 'available')])
        clients_data = supabase_select('clients', order_by='company_name')
        addons_data = supabase.table('addons').select("""
            id, name, price,
            category:addon_categories(name)
        """).eq('is_active', True).execute()
        
        form.room_id.choices = [(r['id'], r['name']) for r in rooms_data]
        form.client_id.choices = [(c['id'], c['company_name'] or c['contact_person']) for c in clients_data]
        
        # Format addon choices with category and price
        addon_choices = []
        for addon in addons_data.data:
            category_name = addon.get('category', {}).get('name', 'Uncategorized') if addon.get('category') else 'Uncategorized'
            addon_label = f"{category_name} - {addon['name']} (${addon['price']})"
            addon_choices.append((addon['id'], addon_label))
        
        form.addons.choices = addon_choices
        
    except Exception as e:
        print(f"Error loading form data: {e}")
        flash('Error loading form data', 'danger')
        return redirect(url_for('bookings'))

    if form.validate_on_submit():
        try:
            # Check room availability
            if not is_room_available_supabase(form.room_id.data, form.start_time.data, form.end_time.data):
                flash('Room is not available for the selected time period', 'danger')
                return render_template('bookings/form.html', title='New Booking', form=form)
            
            # Calculate pricing
            total_price = calculate_booking_total(
                form.room_id.data, 
                form.start_time.data, 
                form.end_time.data, 
                form.addons.data, 
                form.discount.data or 0
            )
            
            # Create booking data
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
            
            # Insert booking
            result = supabase_insert('bookings', booking_data)
            
            if result:
                booking_id = result['id']
                
                # Add selected add-ons to junction table
                if form.addons.data:
                    for addon_id in form.addons.data:
                        addon_booking_data = {
                            'booking_id': booking_id,
                            'addon_id': addon_id,
                            'quantity': 1
                        }
                        supabase_insert('booking_addons', addon_booking_data)
                
                flash('Booking created successfully', 'success')
                return redirect(url_for('view_booking', id=booking_id))
            else:
                flash('Error creating booking', 'danger')
                
        except Exception as e:
            print(f"Error creating booking: {e}")
            flash('Error creating booking', 'danger')
    
    return render_template('bookings/form.html', title='New Booking', form=form)

@app.route('/bookings/<int:id>')
@login_required
def view_booking(id):
    """View booking details using Supabase"""
    try:
        booking_data = supabase.table('bookings').select("""
            *,
            room:rooms(*),
            client:clients(*),
            created_by_user:users(first_name, last_name),
            booking_addons(
                quantity,
                addon:addons(
                    id, name, description, price,
                    category:addon_categories(name)
                )
            )
        """).eq('id', id).execute()
        
        if not booking_data.data:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        booking = booking_data.data[0]
        return render_template('bookings/view.html', 
                             title=f'Booking: {booking["title"]}', 
                             booking=booking)
        
    except Exception as e:
        print(f"Error fetching booking: {e}")
        flash('Error loading booking details', 'danger')
        return redirect(url_for('bookings'))

@app.route('/bookings/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_booking(id):
    """Edit a booking using Supabase"""
    try:
        booking_data = supabase.table('bookings').select("""
            *,
            booking_addons(addon_id)
        """).eq('id', id).execute()
        
        if not booking_data.data:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings'))
        
        booking = booking_data.data[0]
        form = BookingForm()
        
        # Populate form choices
        rooms_data = supabase_select('rooms', filters=[('status', 'eq', 'available')])
        clients_data = supabase_select('clients', order_by='company_name')
        addons_data = supabase.table('addons').select("""
            id, name, price,
            category:addon_categories(name)
        """).eq('is_active', True).execute()
        
        form.room_id.choices = [(r['id'], r['name']) for r in rooms_data]
        form.client_id.choices = [(c['id'], c['company_name'] or c['contact_person']) for c in clients_data]
        
        addon_choices = []
        for addon in addons_data.data:
            category_name = addon.get('category', {}).get('name', 'Uncategorized') if addon.get('category') else 'Uncategorized'
            addon_label = f"{category_name} - {addon['name']} (${addon['price']})"
            addon_choices.append((addon['id'], addon_label))
        
        form.addons.choices = addon_choices
        
        if form.validate_on_submit():
            # Check room availability (excluding this booking)
            start_time = form.start_time.data
            end_time = form.end_time.data
            
            overlapping = supabase.table('bookings').select('id').eq('room_id', form.room_id.data).neq('status', 'cancelled').neq('id', id).lt('start_time', end_time.isoformat()).gt('end_time', start_time.isoformat()).execute()
            
            if overlapping.data:
                flash('Room is not available for the selected time period', 'danger')
                return render_template('bookings/form.html', title='Edit Booking', form=form, booking=booking)
            
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
        
        return render_template('bookings/form.html', title='Edit Booking', form=form, booking=booking)
        
    except Exception as e:
        print(f"Error editing booking: {e}")
        flash('Error loading booking for edit', 'danger')
        return redirect(url_for('bookings'))

@app.route('/bookings/<int:id>/delete', methods=['POST'])
@login_required
def delete_booking(id):
    """Cancel a booking (soft delete)"""
    try:
        result = supabase_update('bookings', {'status': 'cancelled'}, [('id', 'eq', id)])
        if result:
            flash('Booking has been cancelled', 'success')
        else:
            flash('Error cancelling booking', 'danger')
    except Exception as e:
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

@app.route('/bookings/<int:id>/invoice')
@login_required
def generate_invoice(id):
    """Generate an invoice for a booking"""
    booking_data = supabase.table('bookings').select("""
        *,
        room:rooms(*),
        client:clients(*),
        booking_addons(
            quantity,
            addon:addons(*)
        )
    """).eq('id', id).execute()
    
    if not booking_data.data:
        flash('Booking not found', 'danger')
        return redirect(url_for('bookings'))
    
    booking = booking_data.data[0]
    return render_template('bookings/invoice.html', 
                           title=f'Invoice for {booking["title"]}',
                           booking=booking,
                           now=datetime.utcnow(),
                           timedelta=timedelta)

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
    """Reports dashboard"""
    return render_template('reports/index.html', title='Reports')

@app.route('/reports/room-utilization')
@login_required
def room_utilization_report():
    """Simple room utilization report"""
    try:
        # Get date range from query parameters or use current month
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = datetime.utcnow().date()
        if not start_date:
            start_date = today.replace(day=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get rooms and bookings using admin client for reliable data
        rooms = supabase_admin.table('rooms').select('*').execute().data
        bookings = supabase.table('bookings').select("""
            *,
            room:rooms(name)
        """).gte('start_time', start_date.isoformat()).lte('end_time', end_date.isoformat()).neq('status', 'cancelled').execute()
        
        # Calculate utilization for each room
        utilization_data = []
        for room in rooms:
            room_bookings = [b for b in bookings.data if b['room']['name'] == room['name']]
            
            total_hours = 0
            for booking in room_bookings:
                start = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00'))
                duration = (end - start).total_seconds() / 3600
                total_hours += duration
            
            # Assume 12 available hours per day
            total_days = (end_date - start_date).days + 1
            available_hours = total_days * 12
            utilization_pct = (total_hours / available_hours * 100) if available_hours > 0 else 0
            
            utilization_data.append({
                'room': room,
                'booked_hours': round(total_hours, 1),
                'total_available_hours': available_hours,
                'utilization_pct': round(utilization_pct, 1)
            })
        
        return render_template('reports/room_utilization.html',
                              title='Room Utilization Report',
                              utilization_data=utilization_data,
                              start_date=start_date,
                              end_date=end_date)
    except Exception as e:
        print(f"Report error: {e}")
        flash('Error generating report', 'danger')
        return redirect(url_for('reports'))

@app.route('/reports/revenue')
@login_required
def revenue_report():
    """Simple revenue report"""
    try:
        # Get date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = datetime.utcnow().date()
        if not start_date:
            start_date = today.replace(day=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get confirmed bookings in date range
        bookings = supabase.table('bookings').select("""
            *,
            room:rooms(name),
            client:clients(company_name, contact_person)
        """).eq('status', 'confirmed').gte('start_time', start_date.isoformat()).lte('end_time', end_date.isoformat()).execute()
        
        # Calculate totals
        total_revenue = sum(float(b['total_price'] or 0) for b in bookings.data)
        
        return render_template('reports/revenue.html',
                              title='Revenue Report',
                              bookings=bookings.data,
                              total_revenue=total_revenue,
                              start_date=start_date,
                              end_date=end_date)
    except Exception as e:
        print(f"Revenue report error: {e}")
        flash('Error generating revenue report', 'danger')
        return redirect(url_for('reports'))

# ===============================
# API Routes for Dashboard Widgets
# ===============================

@app.route('/api/dashboard/upcoming-bookings')
@login_required
def api_upcoming_bookings():
    """API endpoint for upcoming bookings widget"""
    try:
        days = request.args.get('days', 7, type=int)
        end_date = datetime.utcnow() + timedelta(days=days)
        
        bookings = supabase.table('bookings').select("""
            id, title, start_time, status,
            room:rooms(name),
            client:clients(company_name, contact_person)
        """).gte('start_time', datetime.utcnow().isoformat()).lte('start_time', end_date.isoformat()).neq('status', 'cancelled').order('start_time').execute()
        
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
    """API endpoint for room status widget"""
    try:
        now = datetime.utcnow().isoformat()
        rooms = supabase_select('rooms')
        
        data = []
        for room in rooms:
            # Check if room is currently booked
            current_booking = supabase.table('bookings').select('id, title, end_time').eq('room_id', room['id']).lte('start_time', now).gte('end_time', now).neq('status', 'cancelled').execute()
            
            # Get next booking
            next_booking = supabase.table('bookings').select('id, title, start_time').eq('room_id', room['id']).gt('start_time', now).neq('status', 'cancelled').order('start_time').limit(1).execute()
            
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

# ===============================
# Error Handlers
# ===============================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
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
        # Use service key for admin testing (bypasses RLS)
        admin_client = supabase_admin if SUPABASE_SERVICE_KEY else supabase
        
        print('🔍 Testing Supabase connection...')
        print(f'🔗 Connected to: {SUPABASE_URL}')
        
        # Test database connection with room data
        response = admin_client.table('rooms').select('id, name').execute()
        print('✅ Supabase database connection successful')
        print(f'✅ Found {len(response.data)} rooms in database')
        
        if response.data:
            print('   📋 Rooms found:')
            for room in response.data:
                print(f'   - {room["name"]}')
        else:
            print('   ⚠️  No rooms found - make sure sample data is inserted')
        
        # Test other tables
        clients = admin_client.table('clients').select('id').execute()
        addons = admin_client.table('addons').select('id').execute()
        categories = admin_client.table('addon_categories').select('id').execute()
        bookings = admin_client.table('bookings').select('id').execute()
        
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
    """Simple data backup command"""
    try:
        import json
        from datetime import datetime
        
        print('📦 Creating backup...')
        
        # Use admin client for reliable backup
        admin_client = supabase_admin if SUPABASE_SERVICE_KEY else supabase
        
        # Export key data
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'rooms': admin_client.table('rooms').select('*').execute().data,
            'clients': admin_client.table('clients').select('*').execute().data,
            'addon_categories': admin_client.table('addon_categories').select('*').execute().data,
            'addons': admin_client.table('addons').select('*').execute().data,
            'bookings': admin_client.table('bookings').select('*').execute().data
        }
        
        filename = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
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

# ===============================
# Main Entry Point
# ===============================

if __name__ == '__main__':
    # Production vs Development
    if os.environ.get('FLASK_ENV') == 'production':
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    else:
        app.run(debug=True)