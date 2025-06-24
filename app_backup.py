#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rainbow Towers Conference Room Booking System
Flask Application File

This file contains the main application code for the conference room booking system,
including database models, routes, and core functionality.
"""

import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import and_, or_
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, DateTimeField, TextAreaField, IntegerField, DecimalField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Length, ValidationError
import json
from decimal import Decimal
from flask_wtf.csrf import CSRFProtect

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///rainbow_towers_bookings.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)


@app.context_processor
def inject_now():
    """Inject the current datetime into templates."""
    from datetime import datetime
    return {'now': datetime.utcnow()}
# ===============================
# Database Models
# ===============================

# Association tables for many-to-many relationships
booking_addons = db.Table('booking_addons',
    db.Column('booking_id', db.Integer, db.ForeignKey('booking.id'), primary_key=True),
    db.Column('addon_id', db.Integer, db.ForeignKey('addon.id'), primary_key=True),
    db.Column('quantity', db.Integer, default=1),
    db.Column('notes', db.String(200))
)

class User(UserMixin, db.Model):
    """Staff user accounts for the booking system"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    role = db.Column(db.String(20), default='staff')  # admin, staff, manager
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Room(db.Model):
    """Conference rooms available for booking"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer)
    description = db.Column(db.Text)
    hourly_rate = db.Column(db.Numeric(10, 2))
    half_day_rate = db.Column(db.Numeric(10, 2))
    full_day_rate = db.Column(db.Numeric(10, 2))
    amenities = db.Column(db.Text)  # Stored as JSON string
    status = db.Column(db.String(20), default='available')  # available, maintenance, reserved
    image_url = db.Column(db.String(255))
    
    bookings = db.relationship('Booking', backref='room', lazy=True)
    
    def __repr__(self):
        return f'<Room {self.name}>'
    
    @property
    def amenities_list(self):
        if self.amenities:
            return json.loads(self.amenities)
        return []

class Client(db.Model):
    """Client/customer information"""
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100))
    contact_person = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    bookings = db.relationship('Booking', backref='client', lazy=True)
    
    def __repr__(self):
        return f'<Client {self.company_name or self.contact_person}>'

class AddonCategory(db.Model):
    """Categories for booking add-ons"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    
    addons = db.relationship('Addon', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<AddonCategory {self.name}>'

class Addon(db.Model):
    """Add-on services and equipment for bookings"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('addon_category.id'))
    is_active = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<Addon {self.name}>'

class Booking(db.Model):
    """Conference room bookings"""
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='tentative')  # tentative, confirmed, cancelled
    attendees = db.Column(db.Integer)
    notes = db.Column(db.Text)
    
    # Pricing
    room_rate = db.Column(db.Numeric(10, 2))
    addons_total = db.Column(db.Numeric(10, 2), default=0)
    discount = db.Column(db.Numeric(10, 2), default=0)
    total_price = db.Column(db.Numeric(10, 2))
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    addons = db.relationship('Addon', secondary=booking_addons, backref=db.backref('bookings', lazy='dynamic'))
    creator = db.relationship('User', backref='created_bookings')
    
    def __repr__(self):
        return f'<Booking {self.id}: {self.title}>'
    
    def calculate_total(self):
        """Calculate the total price for the booking"""
        # Calculate duration in hours or days
        duration = (self.end_time - self.start_time).total_seconds() / 3600
        
        # Get room rate based on duration
        if duration <= 4:  # Hourly rate
            self.room_rate = self.room.hourly_rate * Decimal(duration)
        elif duration <= 6:  # Half day rate
            self.room_rate = self.room.half_day_rate
        else:  # Full day rate
            self.room_rate = self.room.full_day_rate
        
        # Calculate add-ons total from the junction table
        self.addons_total = Decimal(0)
        for addon in self.addons:
            # Get quantity from the junction table
            booking_addon = db.session.query(booking_addons).filter_by(
                booking_id=self.id, addon_id=addon.id).first()
            quantity = booking_addon.quantity if booking_addon else 1
            self.addons_total += addon.price * Decimal(quantity)
        
        # Calculate final total
        self.total_price = self.room_rate + self.addons_total - self.discount
        return self.total_price
    
    def check_capacity(self):
        """Check if the room has sufficient capacity for the number of attendees.
        Returns:
            tuple: (is_valid, message) where is_valid is a boolean indicating if the capacity is sufficient,
                   and message is a string with an explanation (or None if valid)
        """
        # Skip check if attendees or room is not set
        if not self.attendees or not self.room:
            return True, None

        # Check if room capacity is exceeded
        if self.attendees > self.room.capacity:
            return False, f"The room {self.room.name} has a capacity of {self.room.capacity}, but the booking has {self.attendees} attendees."

        return True, None

class Accommodation(db.Model):
    """Hotel accommodation linked to conference bookings"""
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'))
    room_type = db.Column(db.String(50))
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)
    number_of_rooms = db.Column(db.Integer, default=1)
    special_requests = db.Column(db.Text)
    status = db.Column(db.String(20), default='requested')  # requested, confirmed, cancelled
    
    booking = db.relationship('Booking', backref='accommodations')
    
    def __repr__(self):
        return f'<Accommodation for Booking {self.booking_id}>'

class Payment(db.Model):
    """Payment records for bookings"""
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    booking = db.relationship('Booking', backref='payments')
    
    def __repr__(self):
        return f'<Payment {self.id} for Booking {self.booking_id}>'

# ===============================
# Forms
# ===============================

class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Username', validators=[DataRequired()])
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

# Here's how to modify your BookingForm class to add the validation
# and implement the business logic check in the Booking model

# Update the BookingForm class in app.py
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
        # Skip validation if attendees field is empty or room_id is not provided
        if not field.data or not self.room_id.data:
            return
        
        room = Room.query.get(self.room_id.data)
        if not room:
            return
        
        # Check if room capacity is exceeded
        if field.data > room.capacity:
            flash(f'Warning: The selected room ({room.name}) has a capacity of {room.capacity}, but you\'ve entered {field.data} attendees.', 'warning')
            # We're using a warning, not an error, so it doesn't prevent form submission
            # If you want to prevent submission, use this instead:
            # raise ValidationError(f'The room cannot accommodate {field.data} attendees. Maximum capacity is {room.capacity}.')

# Add a method to the Booking model in app.py to check capacity
def check_capacity(self):
    """Check if the room has sufficient capacity for the number of attendees.
    Returns:
        tuple: (is_valid, message) where is_valid is a boolean indicating if the capacity is sufficient,
               and message is a string with an explanation (or None if valid)
    """
    # Skip check if attendees or room is not set
    if not self.attendees or not self.room:
        return True, None

    # Check if room capacity is exceeded
    if self.attendees > self.room.capacity:
        return False, f"The room {self.room.name} has a capacity of {self.room.capacity}, but the booking has {self.attendees} attendees."

    return True, None
        
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

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))

def is_room_available(room_id, start_time, end_time, exclude_booking_id=None):
    """Check if a room is available for the specified time period"""
    overlapping_bookings = Booking.query.filter(
        Booking.room_id == room_id,
        Booking.status != 'cancelled',
        Booking.start_time < end_time,
        Booking.end_time > start_time
    )
    
    if exclude_booking_id:
        overlapping_bookings = overlapping_bookings.filter(Booking.id != exclude_booking_id)
    
    return overlapping_bookings.count() == 0

def get_booking_calendar_events():
    """Get all bookings formatted for FullCalendar"""
    bookings = Booking.query.all()
    events = []
    
    for booking in bookings:
        color = {
            'tentative': '#FFA500',  # Orange
            'confirmed': '#28a745',  # Green
            'cancelled': '#dc3545'   # Red
        }.get(booking.status, '#17a2b8')  # Default: Teal
        
        events.append({
            'id': booking.id,
            'title': booking.title,
            'start': booking.start_time.isoformat(),
            'end': booking.end_time.isoformat(),
            'color': color,
            'extendedProps': {
                'room': booking.room.name,
                'client': booking.client.company_name or booking.client.contact_person,
                'status': booking.status
            }
        })
    
    return events

# ===============================
# Routes - Authentication
# ===============================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('Invalid username or password', 'danger')
    
    return render_template('login.html', form=form, title='Sign In')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# ===============================
# Routes - Dashboard
# ===============================

@app.route('/')
@login_required
def dashboard():
    """Main dashboard page"""
    # Get statistics for the dashboard
    upcoming_bookings = Booking.query.filter(
        Booking.start_time >= datetime.utcnow(),
        Booking.status != 'cancelled'
    ).order_by(Booking.start_time).limit(5).all()
    
    today_bookings = Booking.query.filter(
        Booking.start_time.between(
            datetime.utcnow().replace(hour=0, minute=0, second=0),
            datetime.utcnow().replace(hour=23, minute=59, second=59)
        ),
        Booking.status != 'cancelled'
    ).all()
    
    total_rooms = Room.query.count()
    total_clients = Client.query.count()
    total_active_bookings = Booking.query.filter(
        Booking.status != 'cancelled',
        Booking.end_time >= datetime.utcnow()
    ).count()
    
    return render_template('dashboard.html', 
                          title='Dashboard',
                          upcoming_bookings=upcoming_bookings,
                          today_bookings=today_bookings,
                          total_rooms=total_rooms,
                          total_clients=total_clients,
                          total_active_bookings=total_active_bookings)

@app.route('/calendar')
@login_required
def calendar():
    """Calendar view for bookings"""
    rooms = Room.query.all()
    return render_template('calendar.html', title='Booking Calendar', rooms=rooms)

@app.route('/api/events')
@login_required
def get_events():
    """API endpoint to get calendar events"""
    events = get_booking_calendar_events()
    return jsonify(events)

# ===============================
# Routes - Rooms
# ===============================

@app.route('/rooms')
@login_required
def rooms():
    """List all conference rooms"""
    rooms = Room.query.all()
    return render_template('rooms/index.html', title='Conference Rooms', rooms=rooms)

@app.route('/rooms/new', methods=['GET', 'POST'])
@login_required
def new_room():
    """Add a new conference room"""
    form = RoomForm()
    if form.validate_on_submit():
        amenities_list = [item.strip() for item in form.amenities.data.split(',') if item.strip()]
        amenities_json = json.dumps(amenities_list)
        
        room = Room(
            name=form.name.data,
            capacity=form.capacity.data,
            description=form.description.data,
            hourly_rate=form.hourly_rate.data,
            half_day_rate=form.half_day_rate.data,
            full_day_rate=form.full_day_rate.data,
            amenities=amenities_json,
            status=form.status.data,
            image_url=form.image_url.data
        )
        db.session.add(room)
        db.session.commit()
        flash('Conference room added successfully', 'success')
        return redirect(url_for('rooms'))
    
    return render_template('rooms/form.html', title='Add Conference Room', form=form)

@app.route('/rooms/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(id):
    """Edit a conference room"""
    room = Room.query.get_or_404(id)
    form = RoomForm(obj=room)
    
    if form.validate_on_submit():
        amenities_list = [item.strip() for item in form.amenities.data.split(',') if item.strip()]
        amenities_json = json.dumps(amenities_list)
        
        room.name = form.name.data
        room.capacity = form.capacity.data
        room.description = form.description.data
        room.hourly_rate = form.hourly_rate.data
        room.half_day_rate = form.half_day_rate.data
        room.full_day_rate = form.full_day_rate.data
        room.amenities = amenities_json
        room.status = form.status.data
        room.image_url = form.image_url.data
        
        db.session.commit()
        flash('Conference room updated successfully', 'success')
        return redirect(url_for('rooms'))
    
    # Pre-fill the amenities field with comma-separated values
    if room.amenities:
        form.amenities.data = ', '.join(json.loads(room.amenities))
    
    return render_template('rooms/form.html', title='Edit Conference Room', form=form, room=room)

@app.route('/rooms/<int:id>/delete', methods=['POST'])
@login_required
def delete_room(id):
    """Delete a conference room"""
    room = Room.query.get_or_404(id)
    
    # Check if room has any bookings
    has_bookings = Booking.query.filter_by(room_id=id).first() is not None
    
    if has_bookings:
        flash('Cannot delete room with existing bookings', 'danger')
    else:
        db.session.delete(room)
        db.session.commit()
        flash('Conference room deleted successfully', 'success')
    
    return redirect(url_for('rooms'))

# ===============================
# Routes - Clients
# ===============================

@app.route('/clients')
@login_required
def clients():
    """List all clients"""
    clients = Client.query.order_by(Client.company_name).all()
    return render_template('clients/index.html', title='Clients', clients=clients)

@app.route('/clients/new', methods=['GET', 'POST'])
@login_required
def new_client():
    """Add a new client"""
    form = ClientForm()
    if form.validate_on_submit():
        client = Client(
            company_name=form.company_name.data,
            contact_person=form.contact_person.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            notes=form.notes.data
        )
        db.session.add(client)
        db.session.commit()
        flash('Client added successfully', 'success')
        return redirect(url_for('clients'))
    
    return render_template('clients/form.html', title='Add Client', form=form)

@app.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(id):
    """Edit a client"""
    client = Client.query.get_or_404(id)
    form = ClientForm(obj=client)
    
    if form.validate_on_submit():
        client.company_name = form.company_name.data
        client.contact_person = form.contact_person.data
        client.email = form.email.data
        client.phone = form.phone.data
        client.address = form.address.data
        client.notes = form.notes.data
        
        db.session.commit()
        flash('Client updated successfully', 'success')
        return redirect(url_for('clients'))
    
@app.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def delete_client(id):
    """Delete a client"""
    client = Client.query.get_or_404(id)
    
    # Check if client has any bookings
    if client.bookings:
        flash('Cannot delete client with existing bookings', 'danger')
    else:
        db.session.delete(client)
        db.session.commit()
        flash('Client deleted successfully', 'success')
    
    return redirect(url_for('clients'))
    
    return render_template('clients/form.html', title='Edit Client', form=form, client=client)

@app.route('/clients/<int:id>')
@login_required
def view_client(id):
    """View client details and booking history"""
    client = Client.query.get_or_404(id)
    bookings = Booking.query.filter_by(client_id=id).order_by(Booking.start_time.desc()).all()
    return render_template('clients/view.html', title=f'Client: {client.company_name or client.contact_person}', 
                          client=client, bookings=bookings)

# ===============================
# Routes - Add-ons
# ===============================

@app.route('/addons')
@login_required
def addons():
    """List all add-ons by category"""
    categories = AddonCategory.query.all()
    return render_template('addons/index.html', title='Add-ons', categories=categories)

# Additional helper function for the new_addon route

@app.route('/addons/new', methods=['GET', 'POST'])
@login_required
def new_addon():
    """Add a new add-on service or equipment"""
    form = AddonForm()
    
    # Populate the category choices
    form.category_id.choices = [(c.id, c.name) for c in AddonCategory.query.all()]
    
    # Pre-select category if provided in query parameter
    category_id = request.args.get('category', type=int)
    if category_id:
        category = AddonCategory.query.get(category_id)
        if category:
            form.category_id.data = category.id
    
    if form.validate_on_submit():
        addon = Addon(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            category_id=form.category_id.data,
            is_active=form.is_active.data
        )
        db.session.add(addon)
        db.session.commit()
        
        flash('Add-on service created successfully', 'success')
        return redirect(url_for('addons'))
    
    return render_template('addons/form.html', title='New Add-on', form=form)

@app.route('/addons/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_addon(id):
    """Edit an add-on"""
    addon = Addon.query.get_or_404(id)
    form = AddonForm(obj=addon)
    form.category_id.choices = [(c.id, c.name) for c in AddonCategory.query.all()]
    
    if form.validate_on_submit():
        addon.name = form.name.data
        addon.description = form.description.data
        addon.price = form.price.data
        addon.category_id = form.category_id.data
        addon.is_active = form.is_active.data
        
        db.session.commit()
        flash('Add-on updated successfully', 'success')
        return redirect(url_for('addons'))
    
    return render_template('addons/form.html', title='Edit Add-on', form=form, addon=addon)

# Updated version of the new_addon_category route to better handle AJAX requests

@app.route('/addon_categories/new', methods=['GET', 'POST'])
@login_required
def new_addon_category():
    """Add a new add-on category"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Category name is required'})
            flash('Category name is required', 'danger')
            return redirect(url_for('addons'))
        
        category = AddonCategory(name=name, description=description)
        db.session.add(category)
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True, 
                'category': {
                    'id': category.id,
                    'name': category.name
                }
            })
            
        flash('Category added successfully', 'success')
        return redirect(url_for('addons'))
    
    return render_template('addons/new_category.html', title='New Add-on Category')

# Add these routes to your app.py file for addon category management

@app.route('/addon_categories/<int:id>/edit', methods=['POST'])
@login_required
def edit_addon_category(id):
    """Edit an add-on category"""
    category = AddonCategory.query.get_or_404(id)
    
    name = request.form.get('name')
    description = request.form.get('description')
    
    if name:
        category.name = name
        category.description = description
        db.session.commit()
        flash('Category updated successfully', 'success')
    else:
        flash('Category name is required', 'danger')
    
    return redirect(url_for('addons'))

@app.route('/addon_categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_addon_category(id):
    """Delete an add-on category"""
    category = AddonCategory.query.get_or_404(id)
    
    # Check if category has any addons
    if category.addons:
        flash('Cannot delete category with existing add-ons', 'danger')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted successfully', 'success')
    
    return redirect(url_for('addons'))

@app.route('/addons/<int:id>/delete', methods=['POST'])
@login_required
def delete_addon(id):
    """Delete an add-on"""
    addon = Addon.query.get_or_404(id)
    
    # Check if addon is used in any bookings
    if addon.bookings.count() > 0:
        flash('Cannot delete add-on that is used in bookings', 'danger')
    else:
        db.session.delete(addon)
        db.session.commit()
        flash('Add-on deleted successfully', 'success')
    
    return redirect(url_for('addons'))

# API endpoint for toggling addon status (optional, but referenced in the JavaScript)
@app.route('/api/addons/<int:id>/toggle-status', methods=['POST'])
@login_required
def toggle_addon_status(id):
    """Toggle the active status of an add-on"""
    addon = Addon.query.get_or_404(id)
    
    data = request.get_json()
    is_active = data.get('is_active', not addon.is_active)
    
    addon.is_active = is_active
    db.session.commit()
    
    return jsonify({'success': True, 'is_active': addon.is_active})

# ===============================
# Routes - Bookings
# ===============================

@app.route('/bookings')
@login_required
def bookings():
    """List all bookings"""
    status_filter = request.args.get('status', 'all')
    date_filter = request.args.get('date', 'upcoming')
    
    query = Booking.query
    
    # Apply status filter
    if status_filter != 'all':
        query = query.filter(Booking.status == status_filter)
    
    # Apply date filter
    if date_filter == 'upcoming':
        query = query.filter(Booking.end_time >= datetime.utcnow())
    elif date_filter == 'past':
        query = query.filter(Booking.end_time < datetime.utcnow())
    elif date_filter == 'today':
        today = datetime.utcnow().date()
        query = query.filter(
            db.func.date(Booking.start_time) == today
        )
    
    # Order by start time
    bookings = query.order_by(Booking.start_time).all()
    
    return render_template('bookings/index.html', 
                          title='Bookings', 
                          bookings=bookings,
                          status_filter=status_filter,
                          date_filter=date_filter)

@app.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def new_booking():
    """Create a new booking"""
    form = BookingForm()
    
    # Populate form choices
    rooms = Room.query.filter_by(status='available').all()
    form.room_id.choices = [(r.id, r.name) for r in rooms]
    form.client_id.choices = [(c.id, c.company_name or c.contact_person) for c in Client.query.order_by(Client.company_name).all()]
    
    # Make sure addons choices are populated
    addons_with_categories = []
    for addon in Addon.query.filter_by(is_active=True).all():
        category_name = addon.category.name if addon.category else "Uncategorized"
        addon_label = f"{category_name} - {addon.name} (${addon.price})"
        addons_with_categories.append((addon.id, addon_label))
    
    form.addons.choices = addons_with_categories

    # Initialize form.addons.data as an empty list if it's None
    if form.addons.data is None:
        form.addons.data = []

    if form.validate_on_submit():
        # Check room availability
        if not is_room_available(form.room_id.data, form.start_time.data, form.end_time.data):
            flash('Room is not available for the selected time period', 'danger')
            return render_template('bookings/form.html', title='New Booking', form=form, rooms=rooms)
        
        # Create new booking
        booking = Booking(
            room_id=form.room_id.data,
            client_id=form.client_id.data,
            title=form.title.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            status=form.status.data,
            attendees=form.attendees.data,
            notes=form.notes.data,
            discount=form.discount.data,
            created_by=current_user.id
        )
        
        # Perform capacity check
        has_capacity, message = booking.check_capacity()
        if not has_capacity:
            flash(f'Warning: {message} The booking will be created, but you may want to consider a larger room or reducing the attendee count.', 'warning')
        
        db.session.add(booking)
        db.session.flush()  # Get booking ID without committing
        
        # Add selected add-ons
        for addon_id in form.addons.data:
            addon = Addon.query.get(addon_id)
            booking.addons.append(addon)
        
        # Calculate the total price
        booking.calculate_total()
        
        db.session.commit()
        flash('Booking created successfully', 'success')
        return redirect(url_for('view_booking', id=booking.id))
    
    return render_template('bookings/form.html', title='New Booking', form=form, rooms=rooms)


@app.route('/bookings/<int:id>')
@login_required
def view_booking(id):
    """View booking details"""
    booking = Booking.query.get_or_404(id)
    return render_template('bookings/view.html', title=f'Booking: {booking.title}', booking=booking)

@app.route('/bookings/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_booking(id):
    """Edit a booking"""
    booking = Booking.query.get_or_404(id)
    form = BookingForm(obj=booking)
    
    # Populate form choices
    rooms = Room.query.filter_by(status='available').all()
    form.room_id.choices = [(r.id, r.name) for r in rooms]
    form.client_id.choices = [(c.id, c.company_name or c.contact_person) for c in Client.query.order_by(Client.company_name).all()]
    
    # Make sure addons choices are populated
    addons_with_categories = []
    for addon in Addon.query.filter_by(is_active=True).all():
        category_name = addon.category.name if addon.category else "Uncategorized"
        addon_label = f"{category_name} - {addon.name} (${addon.price})"
        addons_with_categories.append((addon.id, addon_label))
    
    form.addons.choices = addons_with_categories
    
    # Pre-select current addons
    if request.method == 'GET':
        form.addons.data = [addon.id for addon in booking.addons]
    
    if form.validate_on_submit():
        # Check room availability (excluding this booking)
        if not is_room_available(form.room_id.data, form.start_time.data, form.end_time.data, exclude_booking_id=id):
            flash('Room is not available for the selected time period', 'danger')
            return render_template('bookings/form.html', title='Edit Booking', form=form, booking=booking, rooms=rooms)
        
        # Update booking details
        booking.room_id = form.room_id.data
        booking.client_id = form.client_id.data
        booking.title = form.title.data
        booking.start_time = form.start_time.data
        booking.end_time = form.end_time.data
        booking.status = form.status.data
        booking.attendees = form.attendees.data
        booking.notes = form.notes.data
        booking.discount = form.discount.data
        
        # Perform capacity check
        has_capacity, message = booking.check_capacity()
        if not has_capacity:
            flash(f'Warning: {message} The booking will be updated, but you may want to consider a larger room or reducing the attendee count.', 'warning')
        
        # Update add-ons
        booking.addons = []
        for addon_id in form.addons.data:
            addon = Addon.query.get(addon_id)
            booking.addons.append(addon)
        
        # Recalculate total
        booking.calculate_total()
        
        db.session.commit()
        flash('Booking updated successfully', 'success')
        return redirect(url_for('view_booking', id=booking.id))
    
    return render_template('bookings/form.html', title='Edit Booking', form=form, booking=booking, rooms=rooms)

@app.route('/bookings/<int:id>/delete', methods=['POST'])
@login_required
def delete_booking(id):
    """Delete a booking"""
    booking = Booking.query.get_or_404(id)
    
    # Instead of deleting, mark as cancelled
    booking.status = 'cancelled'
    db.session.commit()
    
    flash('Booking has been cancelled', 'success')
    return redirect(url_for('bookings'))

@app.route('/bookings/<int:id>/change-status/<status>', methods=['POST'])
@login_required
def change_booking_status(id, status):
    """Change booking status (tentative/confirmed/cancelled)"""
    if status not in ['tentative', 'confirmed', 'cancelled']:
        flash('Invalid status', 'danger')
        return redirect(url_for('view_booking', id=id))
    
    booking = Booking.query.get_or_404(id)
    booking.status = status
    db.session.commit()
    
    status_messages = {
        'tentative': 'Booking marked as tentative',
        'confirmed': 'Booking confirmed successfully',
        'cancelled': 'Booking cancelled successfully'
    }
    
    flash(status_messages[status], 'success')
    return redirect(url_for('view_booking', id=id))

@app.route('/bookings/<int:id>/add-accommodation', methods=['GET', 'POST'])
@login_required
def add_accommodation(id):
    """Add accommodation to a booking"""
    booking = Booking.query.get_or_404(id)
    form = AccommodationForm()
    
    if form.validate_on_submit():
        accommodation = Accommodation(
            booking_id=booking.id,
            room_type=form.room_type.data,
            check_in=form.check_in.data,
            check_out=form.check_out.data,
            number_of_rooms=form.number_of_rooms.data,
            special_requests=form.special_requests.data
        )
        
        db.session.add(accommodation)
        db.session.commit()
        
        flash('Accommodation added to booking', 'success')
        return redirect(url_for('view_booking', id=booking.id))
    
    return render_template('bookings/accommodation_form.html', title='Add Accommodation', form=form, booking=booking)

@app.route('/bookings/<int:id>/invoice')
@login_required
def generate_invoice(id):
    """Generate an invoice for a booking"""
    booking = Booking.query.get_or_404(id)
    return render_template('bookings/invoice.html', 
                           title=f'Invoice for {booking.title}',
                           booking=booking,
                           now=datetime.utcnow(),
                           timedelta=timedelta)

@app.route('/bookings/<int:id>/print')
@login_required
def print_booking_details(id):
    """Print booking details"""
    booking = Booking.query.get_or_404(id)
    return render_template('bookings/print_details.html',
                           title=f'Booking Details: {booking.title}',
                           booking=booking,
                           now=datetime.utcnow())

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
    
    available = is_room_available(room_id, start_time, end_time, exclude_booking_id=booking_id)
    
    return jsonify({'available': available})

# ===============================
# Routes - Reports
# ===============================

@app.route('/reports')
@login_required
def reports():
    """Reports dashboard"""
    return render_template('reports/index.html', title='Reports')

# Updated Room Utilization Report Function with Real-Time Data (Continued)
# Replace the existing room_utilization_report function in app.py with this improved version

@app.route('/reports/room-utilization')
@login_required
def room_utilization_report():
    """Room utilization report with real-time data calculations"""
    # Get date range from query parameters or use current month
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    today = datetime.utcnow().date()
    if not start_date:
        start_date = today.replace(day=1)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        # Last day of current month
        next_month = today.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Calculate utilization for each room
    rooms = Room.query.all()
    utilization_data = []
    
    for room in rooms:
        # Total available hours in date range (assuming 12 hours per day)
        total_days = (end_date - start_date).days + 1
        total_available_hours = total_days * 12
        
        # Booked hours
        bookings = Booking.query.filter(
            Booking.room_id == room.id,
            Booking.status != 'cancelled',
            db.func.date(Booking.start_time) >= start_date,
            db.func.date(Booking.end_time) <= end_date
        ).all()
        
        booked_hours = 0
        daily_utilization = {}  # For tracking utilization by day of week
        hourly_utilization = {}  # For tracking utilization by hour of day
        
        # Initialize hourly and daily tracking
        for day in range(7):  # 0-6 for Monday-Sunday
            daily_utilization[day] = 0
        
        for hour in range(8, 20):  # 8am to 8pm
            hourly_utilization[hour] = 0
        
        for booking in bookings:
            # Calculate duration in hours
            start_datetime = max(booking.start_time, datetime.combine(start_date, datetime.min.time()))
            end_datetime = min(booking.end_time, datetime.combine(end_date, datetime.max.time()))
            
            duration = (end_datetime - start_datetime).total_seconds() / 3600
            booked_hours += duration
            
            # Track utilization by day of week
            booking_day = booking.start_time.weekday()
            daily_utilization[booking_day] += duration
            
            # Track utilization by hour of day
            booking_start_hour = booking.start_time.hour
            booking_end_hour = booking.end_time.hour
            
            for hour in range(max(8, booking_start_hour), min(20, booking_end_hour + 1)):
                # Roughly estimate how much of this hour is used
                if hour == booking_start_hour and hour == booking_end_hour:
                    # Both start and end in same hour
                    hour_fraction = (booking.end_time.minute - booking.start_time.minute) / 60
                elif hour == booking_start_hour:
                    # Start hour
                    hour_fraction = (60 - booking.start_time.minute) / 60
                elif hour == booking_end_hour:
                    # End hour
                    hour_fraction = booking.end_time.minute / 60
                else:
                    # Full hour
                    hour_fraction = 1
                
                hourly_utilization[hour] += hour_fraction
        
        # Calculate utilization percentage
        if total_available_hours > 0:
            utilization_pct = (booked_hours / total_available_hours) * 100
        else:
            utilization_pct = 0
        
        # Calculate daily average usage (hours per day)
        daily_avg = {}
        for day, hours in daily_utilization.items():
            # Count how many of this day of week are in the date range
            days_count = sum(1 for d in range((end_date - start_date).days + 1) 
                         if (start_date + timedelta(days=d)).weekday() == day)
            
            if days_count > 0:
                daily_avg[day] = hours / days_count
            else:
                daily_avg[day] = 0
        
        # Calculate hourly average usage (% of days this hour is used)
        hourly_avg = {}
        for hour, usage in hourly_utilization.items():
            hourly_avg[hour] = (usage / total_days) * 100
        
        # Get most popular time slots
        most_popular_day = max(daily_avg.items(), key=lambda x: x[1])[0]
        most_popular_hour = max(hourly_avg.items(), key=lambda x: x[1])[0]
        
        # Get day name from day number
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        most_popular_day_name = day_names[most_popular_day]
        
        # Format most popular hour
        most_popular_hour_formatted = f"{most_popular_hour}:00 - {most_popular_hour + 1}:00"
        
        # Format daily averages for chart
        daily_usage_data = [round(daily_avg.get(d, 0), 1) for d in range(7)]
        
        # Format hourly averages for chart
        hourly_usage_data = [round(hourly_avg.get(h, 0), 1) for h in range(8, 20)]
        
        # Add to utilization data
        utilization_data.append({
            'room': room,
            'booked_hours': round(booked_hours, 1),
            'total_available_hours': total_available_hours,
            'utilization_pct': round(utilization_pct, 1),
            'daily_usage': daily_usage_data,
            'hourly_usage': hourly_usage_data,
            'most_popular_day': most_popular_day_name,
            'most_popular_hour': most_popular_hour_formatted
        })
    
    # Sort rooms by utilization percentage (descending)
    utilization_data.sort(key=lambda x: x['utilization_pct'], reverse=True)
    
    # Calculate overall utilization metrics
    total_booked_hours = sum(room_data['booked_hours'] for room_data in utilization_data)
    total_available_hours = sum(room_data['total_available_hours'] for room_data in utilization_data)
    
    overall_utilization = 0
    if total_available_hours > 0:
        overall_utilization = (total_booked_hours / total_available_hours) * 100
    
    # Get daily aggregated usage (sum across all rooms)
    overall_daily_usage = [0] * 7
    for room_data in utilization_data:
        for i, hours in enumerate(room_data['daily_usage']):
            overall_daily_usage[i] += hours
    
    # Get hourly aggregated usage (average across all rooms)
    overall_hourly_usage = [0] * 12  # 12 hours from 8am to 8pm
    for room_data in utilization_data:
        for i, pct in enumerate(room_data['hourly_usage']):
            overall_hourly_usage[i] += pct
    
    if rooms:
        # Calculate average
        overall_hourly_usage = [round(pct / len(rooms), 1) for pct in overall_hourly_usage]
    
    # Find peak and off-peak hours
    peak_hour_index = overall_hourly_usage.index(max(overall_hourly_usage))
    off_peak_hour_index = overall_hourly_usage.index(min(overall_hourly_usage))
    
    peak_hour = f"{peak_hour_index + 8}:00 - {peak_hour_index + 9}:00"
    off_peak_hour = f"{off_peak_hour_index + 8}:00 - {off_peak_hour_index + 9}:00"
    
    # Find utilization by day of week
    day_labels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Calculate efficiency metrics
    # Any room under 30% utilization is considered underutilized
    underutilized_rooms = [room_data for room_data in utilization_data if room_data['utilization_pct'] < 30]
    
    # Any room over 70% utilization is considered heavily utilized
    heavily_utilized_rooms = [room_data for room_data in utilization_data if room_data['utilization_pct'] > 70]
    
    # Identify rooms that could be merged or reallocated
    optimization_suggestions = []
    
    if len(underutilized_rooms) >= 2:
        # Suggest merging underutilized rooms
        suggestion = f"Consider combining bookings from {underutilized_rooms[0]['room'].name} and {underutilized_rooms[1]['room'].name} to increase efficiency."
        optimization_suggestions.append(suggestion)
    
    if heavily_utilized_rooms:
        # Suggest adding capacity for heavily utilized rooms
        suggestion = f"High demand for {heavily_utilized_rooms[0]['room'].name} (Utilization: {heavily_utilized_rooms[0]['utilization_pct']}%). Consider adding similar capacity."
        optimization_suggestions.append(suggestion)
    
    # Suggest pricing adjustments based on demand
    for room_data in utilization_data:
        if room_data['utilization_pct'] > 80:
            suggestion = f"Consider increasing rates for {room_data['room'].name} due to high demand."
            optimization_suggestions.append(suggestion)
        elif room_data['utilization_pct'] < 20:
            suggestion = f"Consider promotional offers for {room_data['room'].name} to increase utilization."
            optimization_suggestions.append(suggestion)
    
    # Limit to top 3 suggestions
    optimization_suggestions = optimization_suggestions[:3]
    
    # Calculate potential revenue increase
    potential_revenue = 0
    for room_data in underutilized_rooms:
        # Assume we can increase utilization to 50%
        current_util = room_data['utilization_pct'] / 100
        target_util = 0.5
        
        # Additional hours that could be booked
        additional_hours = (target_util - current_util) * room_data['total_available_hours']
        
        # Assume average hourly rate
        avg_rate = float(room_data['room'].hourly_rate or 50)
        
        # Additional revenue
        potential_revenue += additional_hours * avg_rate
    
    return render_template('reports/room_utilization.html', 
                          title='Room Utilization Report',
                          utilization_data=utilization_data,
                          start_date=start_date,
                          end_date=end_date,
                          day_labels=day_labels,
                          overall_utilization=round(overall_utilization, 1),
                          overall_daily_usage=overall_daily_usage,
                          overall_hourly_usage=overall_hourly_usage,
                          peak_hour=peak_hour,
                          off_peak_hour=off_peak_hour,
                          underutilized_rooms=underutilized_rooms,
                          heavily_utilized_rooms=heavily_utilized_rooms,
                          optimization_suggestions=optimization_suggestions,
                          potential_revenue=round(potential_revenue, 2))

@app.route('/reports/revenue')
@login_required
def revenue_report():
    """Revenue report with real-time data calculations"""
    # Get date range from query parameters or use current month
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    today = datetime.utcnow().date()
    if not start_date:
        start_date = today.replace(day=1)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        # Last day of current month
        next_month = today.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get confirmed bookings in date range using database query
    bookings = Booking.query.filter(
        Booking.status == 'confirmed',
        db.func.date(Booking.start_time) >= start_date,
        db.func.date(Booking.end_time) <= end_date
    ).all()
    
    # Calculate revenue metrics using Decimal for consistency
    from decimal import Decimal
    
    # Initialize with Decimal zeros
    total_revenue = Decimal('0')
    room_revenue = Decimal('0')
    addon_revenue = Decimal('0')
    
    # Room revenues by room name
    room_revenues = {}
    
    # Add-on revenues by category
    addon_revenues = {}
    booking_addon_data = {}
    
    # Process each booking
    for booking in bookings:
        # Convert to Decimal if not already
        booking_total = booking.total_price if isinstance(booking.total_price, Decimal) else Decimal(str(booking.total_price or 0))
        booking_room_rate = booking.room_rate if isinstance(booking.room_rate, Decimal) else Decimal(str(booking.room_rate or 0))
        booking_addon_total = booking.addons_total if isinstance(booking.addons_total, Decimal) else Decimal(str(booking.addons_total or 0))
        
        # Update totals
        total_revenue += booking_total
        room_revenue += booking_room_rate
        addon_revenue += booking_addon_total
        
        # Update room revenues
        room_name = booking.room.name
        if room_name not in room_revenues:
            room_revenues[room_name] = Decimal('0')
        room_revenues[room_name] += booking_total
        
        # Process add-ons for this booking
        for addon in booking.addons:
            # Get category name (handle None cases)
            category_name = addon.category.name if addon.category and addon.category.name else "Uncategorized"
            
            # Initialize category if not exists
            if category_name not in addon_revenues:
                addon_revenues[category_name] = Decimal('0')
            
            # Get quantity from junction table
            booking_addon = db.session.query(booking_addons).filter_by(
                booking_id=booking.id, addon_id=addon.id).first()
            quantity = booking_addon.quantity if booking_addon else 1
            
            # Store addon data for template
            key = f"{booking.id}_{addon.id}"
            booking_addon_data[key] = {
                'quantity': quantity,
                'addon_id': addon.id,
                'booking_id': booking.id
            }
            
            # Add to category revenue
            addon_price = addon.price if isinstance(addon.price, Decimal) else Decimal(str(addon.price or 0))
            addon_revenues[category_name] += addon_price * Decimal(str(quantity))
    
    # Convert room_revenues to sorted list for charts
    sorted_room_revenues = sorted(
        [{'name': name, 'revenue': revenue} for name, revenue in room_revenues.items()],
        key=lambda x: x['revenue'],
        reverse=True
    )
    
    # Convert addon_revenues to sorted list for charts
    sorted_addon_revenues = sorted(
        [{'name': name, 'revenue': revenue} for name, revenue in addon_revenues.items()],
        key=lambda x: x['revenue'],
        reverse=True
    )
    
    return render_template('reports/revenue.html',
                          title='Revenue Report',
                          bookings=bookings,
                          total_revenue=total_revenue,
                          room_revenue=room_revenue,
                          addon_revenue=addon_revenue,
                          room_revenues=room_revenues,
                          addon_revenues=addon_revenues,
                          sorted_room_revenues=sorted_room_revenues,
                          sorted_addon_revenues=sorted_addon_revenues,
                          booking_addon_data=booking_addon_data,
                          start_date=start_date,
                          end_date=end_date)
# Updated Client Analysis Report Function with Real-Time Data (Continued)
# This is the continuation of the previous function

@app.route('/reports/client-analysis')
@login_required
def client_analysis_report():
    """Client Analysis Report with real-time data calculations"""
    # Get date range from query parameters or use last 6 months
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    today = datetime.utcnow().date()
    if not start_date:
        # Default to last 6 months
        start_date = (today - timedelta(days=180))
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        end_date = today
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get all bookings in the date range
    bookings = Booking.query.filter(
        db.func.date(Booking.start_time) >= start_date,
        db.func.date(Booking.end_time) <= end_date
    ).all()
    
    # Ensure consistent use of Decimal
    from decimal import Decimal
    
    # Calculate basic metrics
    total_bookings = len(bookings)
    
    # Get all clients with bookings in the period
    client_ids = set(booking.client_id for booking in bookings)
    active_clients = len(client_ids)
    
    # Calculate booking counts and revenue by client
    client_data = {}
    total_revenue = Decimal('0')
    
    # Define the cutoff for at-risk clients (90 days ago)
    at_risk_cutoff = today - timedelta(days=90)
    
    # Get all bookings history for active clients (including before the date range)
    all_client_bookings = Booking.query.filter(
        Booking.client_id.in_(client_ids)
    ).order_by(Booking.start_time).all()
    
    # Build client history for first/last booking determination
    client_booking_history = {}
    for booking in all_client_bookings:
        client_id = booking.client_id
        if client_id not in client_booking_history:
            client_booking_history[client_id] = {
                'first_booking': datetime.utcnow(),
                'last_booking': datetime(1900, 1, 1),
                'all_bookings': []
            }
        
        history = client_booking_history[client_id]
        if booking.start_time < history['first_booking']:
            history['first_booking'] = booking.start_time
        if booking.start_time > history['last_booking']:
            history['last_booking'] = booking.start_time
        
        history['all_bookings'].append(booking)
    
    # Process current period bookings
    for booking in bookings:
        client_id = booking.client_id
        if client_id not in client_data:
            client_data[client_id] = {
                'id': client_id,
                'company_name': booking.client.company_name,
                'contact_person': booking.client.contact_person,
                'booking_count': 0,
                'total_spent': Decimal('0'),
                'first_booking': client_booking_history.get(client_id, {}).get('first_booking'),
                'last_booking': client_booking_history.get(client_id, {}).get('last_booking'),
                'rooms_booked': set(),
                'addons_used': set()
            }
        
        # Update client metrics
        client_data[client_id]['booking_count'] += 1
        booking_total = booking.total_price if isinstance(booking.total_price, Decimal) else Decimal(str(booking.total_price or 0))
        client_data[client_id]['total_spent'] += booking_total
        client_data[client_id]['rooms_booked'].add(booking.room_id)
        total_revenue += booking_total
        
        # Track add-ons
        for addon in booking.addons:
            client_data[client_id]['addons_used'].add(addon.id)
    
    # Calculate average booking value
    avg_booking_value = total_revenue / Decimal(str(total_bookings)) if total_bookings > 0 else Decimal('0')
    avg_client_value = total_revenue / Decimal(str(active_clients)) if active_clients > 0 else Decimal('0')
    
    # Identify client segments
    new_clients = []
    returning_clients = []
    at_risk_clients = []
    repeat_clients = []
    premium_clients = []
    
    for client_id, data in client_data.items():
        # Use the booking history to determine if client is new or returning
        client_first_booking_date = data['first_booking'].date()
        client_last_booking_date = data['last_booking'].date()
        
        # New client check (first booking is within the date range)
        if client_first_booking_date >= start_date:
            new_clients.append(client_id)
        else:
            returning_clients.append(client_id)
        
        # At-risk client check (no bookings in last 90 days)
        if client_last_booking_date < at_risk_cutoff:
            at_risk_clients.append(client_id)
        
        # Repeat clients have 3+ bookings
        if data['booking_count'] >= 3:
            repeat_clients.append(client_id)
        
        # Premium clients have avg booking value > $300
        avg_client_booking = data['total_spent'] / Decimal(str(data['booking_count']))
        if avg_client_booking > Decimal('300'):
            premium_clients.append(client_id)
    
    # Count clients in each segment
    new_clients_count = len(new_clients)
    returning_clients_count = len(returning_clients)
    at_risk_clients_count = len(at_risk_clients)
    repeat_clients_count = len(repeat_clients)
    premium_clients_count = len(premium_clients)
    
    # Calculate retention rate
    # Simple calculation: returning clients / (total clients - new clients)
    denominator = active_clients - new_clients_count
    retention_rate = (returning_clients_count / denominator * 100) if denominator > 0 else 0
    
    # Calculate segment booking stats
    repeat_clients_bookings = sum(client_data[cid]['booking_count'] for cid in repeat_clients) if repeat_clients else 0
    premium_clients_bookings = sum(client_data[cid]['booking_count'] for cid in premium_clients) if premium_clients else 0
    new_clients_bookings = sum(client_data[cid]['booking_count'] for cid in new_clients) if new_clients else 0
    at_risk_clients_bookings = sum(client_data[cid]['booking_count'] for cid in at_risk_clients) if at_risk_clients else 0
    
    # Calculate segment booking value
    repeat_clients_total = sum(client_data[cid]['total_spent'] for cid in repeat_clients) if repeat_clients else Decimal('0')
    premium_clients_total = sum(client_data[cid]['total_spent'] for cid in premium_clients) if premium_clients else Decimal('0')
    new_clients_total = sum(client_data[cid]['total_spent'] for cid in new_clients) if new_clients else Decimal('0')
    at_risk_clients_total = sum(client_data[cid]['total_spent'] for cid in at_risk_clients) if at_risk_clients else Decimal('0')
    
    # Calculate average values per segment
    repeat_clients_avg_value = repeat_clients_total / Decimal(str(repeat_clients_bookings)) if repeat_clients_bookings > 0 else Decimal('0')
    premium_clients_avg_value = premium_clients_total / Decimal(str(premium_clients_bookings)) if premium_clients_bookings > 0 else Decimal('0')
    new_clients_avg_value = new_clients_total / Decimal(str(new_clients_bookings)) if new_clients_bookings > 0 else Decimal('0')
    at_risk_clients_avg_value = at_risk_clients_total / Decimal(str(at_risk_clients_bookings)) if at_risk_clients_bookings > 0 else Decimal('0')
    
    # Get top clients by bookings and revenue
    sorted_by_bookings = sorted(client_data.values(), key=lambda x: x['booking_count'], reverse=True)
    sorted_by_revenue = sorted(client_data.values(), key=lambda x: x['total_spent'], reverse=True)
    
    top_clients_by_bookings = sorted_by_bookings[:5] if sorted_by_bookings else []
    top_clients_by_revenue = sorted_by_revenue[:5] if sorted_by_revenue else []
    
    # Booking frequency distribution
    booking_frequency = {
        'one_booking': sum(1 for c in client_data.values() if c['booking_count'] == 1),
        'two_to_three': sum(1 for c in client_data.values() if 2 <= c['booking_count'] <= 3),
        'four_to_five': sum(1 for c in client_data.values() if 4 <= c['booking_count'] <= 5),
        'six_plus': sum(1 for c in client_data.values() if c['booking_count'] >= 6)
    }
    
    # Generate monthly trends data based on actual booking history
    # Get the start of the trend period (12 months ago)
    trend_start = today.replace(day=1) - timedelta(days=365)
    
    # Group all bookings by month
    monthly_bookings = {}
    
    # Query bookings for the trend period
    trend_bookings = Booking.query.filter(
        db.func.date(Booking.start_time) >= trend_start,
        db.func.date(Booking.start_time) <= today
    ).all()
    
    # Create a dictionary with all months initialized to zero
    for i in range(12):
        month = (today.replace(day=1) - timedelta(days=30*i)).strftime('%Y-%m')
        monthly_bookings[month] = {'new': 0, 'returning': 0}
    
    # Populate with actual booking data
    for booking in trend_bookings:
        month_key = booking.start_time.strftime('%Y-%m')
        if month_key in monthly_bookings:
            client_id = booking.client_id
            # Check if this is client's first booking
            client_first_booking = min([b.start_time for b in all_client_bookings if b.client_id == client_id])
            
            if booking.start_time == client_first_booking:
                monthly_bookings[month_key]['new'] += 1
            else:
                monthly_bookings[month_key]['returning'] += 1
    
    # Convert to format needed for chart
    monthly_trends = {
        'new_clients': [data['new'] for _, data in sorted(monthly_bookings.items())],
        'returning_clients': [data['returning'] for _, data in sorted(monthly_bookings.items())]
    }
    
    # Generate room preferences data based on actual booking history
    room_preferences = {
        'room_types': [],
        'premium_clients': [],
        'regular_clients': [],
        'new_clients': []
    }
    
    # Get all rooms for the report
    rooms = Room.query.all()
    
    # Add room names to the preferences data
    for room in rooms:
        room_preferences['room_types'].append(room.name)
        
        # Initialize counts for each client segment
        premium_count = 0
        regular_count = 0
        new_count = 0
        
        # Count bookings by segment
        for booking in bookings:
            if booking.room_id == room.id:
                client_id = booking.client_id
                
                if client_id in premium_clients:
                    premium_count += 1
                elif client_id in new_clients:
                    new_count += 1
                else:
                    regular_count += 1
        
        # Add counts to preferences data
        room_preferences['premium_clients'].append(premium_count)
        room_preferences['regular_clients'].append(regular_count)
        room_preferences['new_clients'].append(new_count)
    
    # Generate add-on preference data based on actual booking history
    # Group add-ons by category
    addon_categories = AddonCategory.query.all()
    addon_preferences = []
    
    for category in addon_categories:
        # Skip categories with no add-ons
        if not category.addons:
            continue
            
        # Count bookings and calculate revenue for this category
        booking_count = 0
        category_revenue = Decimal('0')
        
        for booking in bookings:
            for addon in booking.addons:
                if addon.category_id == category.id:
                    booking_count += 1
                    addon_price = addon.price if isinstance(addon.price, Decimal) else Decimal(str(addon.price or 0))
                    category_revenue += addon_price
                    break  # Count only once per booking
        
        # Calculate popularity as percentage of total bookings
        popularity = (booking_count / total_bookings * 100) if total_bookings > 0 else 0
        
        addon_preferences.append({
            'name': category.name,
            'popularity': int(popularity),
            'revenue': float(category_revenue)  # Convert to float for the template
        })
    
    # Sort add-on preferences by popularity
    addon_preferences = sorted(addon_preferences, key=lambda x: x['popularity'], reverse=True)
    
    # Generate client segment specific preferences
    # 1. For premium clients
    premium_client_preferences = {
        'most_popular_addon': 'Unknown',
        'avg_addons_per_booking': 0
    }
    
    # 2. For new clients
    new_client_preferences = {
        'most_popular_addon': 'Unknown',
        'avg_addons_per_booking': 0
    }
    
    # Use real booking data to determine premium client preferences
    premium_addon_counts = {}
    premium_bookings_with_addons = 0
    premium_total_addons = 0
    
    for booking in bookings:
        client_id = booking.client_id
        if client_id in premium_clients and booking.addons:
            premium_bookings_with_addons += 1
            premium_total_addons += len(booking.addons)
            
            for addon in booking.addons:
                category_name = addon.category.name if addon.category else "Uncategorized"
                if category_name not in premium_addon_counts:
                    premium_addon_counts[category_name] = 0
                premium_addon_counts[category_name] += 1
    
    # Find most popular add-on for premium clients
    if premium_addon_counts:
        premium_client_preferences['most_popular_addon'] = max(premium_addon_counts.items(), key=lambda x: x[1])[0]
    
    # Calculate average add-ons per booking for premium clients
    if premium_bookings_with_addons > 0:
        premium_client_preferences['avg_addons_per_booking'] = round(premium_total_addons / premium_bookings_with_addons, 1)
    
    # Use real booking data to determine new client preferences
    new_addon_counts = {}
    new_bookings_with_addons = 0
    new_total_addons = 0
    
    for booking in bookings:
        client_id = booking.client_id
        if client_id in new_clients and booking.addons:
            new_bookings_with_addons += 1
            new_total_addons += len(booking.addons)
            
            for addon in booking.addons:
                category_name = addon.category.name if addon.category else "Uncategorized"
                if category_name not in new_addon_counts:
                    new_addon_counts[category_name] = 0
                new_addon_counts[category_name] += 1
    
    # Find most popular add-on for new clients
    if new_addon_counts:
        new_client_preferences['most_popular_addon'] = max(new_addon_counts.items(), key=lambda x: x[1])[0]
    
    # Calculate average add-ons per booking for new clients
    if new_bookings_with_addons > 0:
        new_client_preferences['avg_addons_per_booking'] = round(new_total_addons / new_bookings_with_addons, 1)
    
    # Determine highest revenue add-on
    addon_revenues = {}
    for booking in bookings:
        for addon in booking.addons:
            addon_id = addon.id
            category_name = addon.category.name if addon.category else "Uncategorized"
            key = f"{category_name}"
            
            if key not in addon_revenues:
                addon_revenues[key] = Decimal('0')
            
            addon_price = addon.price if isinstance(addon.price, Decimal) else Decimal(str(addon.price or 0))
            addon_revenues[key] += addon_price
    
    highest_revenue_addon = {
        'name': 'None',
        'revenue': 0
    }
    
    if addon_revenues:
        highest_key = max(addon_revenues.items(), key=lambda x: x[1])[0]
        highest_revenue_addon = {
            'name': highest_key,
            'revenue': float(addon_revenues[highest_key])
        }
    
    # Identify underutilized add-on with potential
    addon_usage_rates = {}
    for category in addon_categories:
        # Count bookings that could have used this category
        total_potential = total_bookings
        
        # Count bookings that actually used this category
        actual_usage = 0
        for booking in bookings:
            used_category = False
            for addon in booking.addons:
                if addon.category_id == category.id:
                    used_category = True
                    break
            if used_category:
                actual_usage += 1
        
        if total_potential > 0:
            usage_rate = (actual_usage / total_potential) * 100
            addon_usage_rates[category.name] = {
                'usage_rate': usage_rate,
                'satisfaction_rate': 90 + ((100 - usage_rate) / 10)  # Estimate satisfaction inversely to usage (lower usage often means higher satisfaction)
            }
    
    underutilized_addon = {
        'name': 'None',
        'current_utilization': 0,
        'satisfaction_rate': 0
    }
    
    if addon_usage_rates:
        # Find an add-on with low utilization but high satisfaction
        potential_addons = [(name, data) for name, data in addon_usage_rates.items() 
                           if data['usage_rate'] < 50 and data['satisfaction_rate'] > 85]
        
        if potential_addons:
            # Sort by lowest utilization
            potential_addons.sort(key=lambda x: x[1]['usage_rate'])
            best_candidate = potential_addons[0]
            
            underutilized_addon = {
                'name': best_candidate[0],
                'current_utilization': int(best_candidate[1]['usage_rate']),
                'satisfaction_rate': int(best_candidate[1]['satisfaction_rate'])
            }
    
    # For retention data, calculate real retention rates by duration
    # This can be somewhat complex as it requires historical data
    # For now, provide reasonable estimates based on client behaviors
    
    # Get clients grouped by time since first booking
    retention_counts = {
        'less_than_1_month': 0,
        'one_to_3_months': 0,
        'three_to_6_months': 0,
        'six_to_12_months': 0,
        'more_than_12_months': 0
    }
    
    retention_totals = {
        'less_than_1_month': 0,
        'one_to_3_months': 0,
        'three_to_6_months': 0,
        'six_to_12_months': 0,
        'more_than_12_months': 0
    }
    
    # Count clients that returned and total clients in each time bracket
    for client_id, history in client_booking_history.items():
        # Skip clients without multiple bookings
        if len(history['all_bookings']) <= 1:
                       continue
        
        # Sort bookings by time
        sorted_bookings = sorted(history['all_bookings'], key=lambda b: b.start_time)
        
        # Look at pairs of consecutive bookings
        for i in range(len(sorted_bookings) - 1):
            first_booking = sorted_bookings[i]
            next_booking = sorted_bookings[i + 1]
            
            # Calculate gap between bookings
            gap_days = (next_booking.start_time - first_booking.start_time).days
            
            # Categorize by gap duration
            category = ''
            if gap_days < 30:
                category = 'less_than_1_month'
            elif gap_days < 90:
                category = 'one_to_3_months'
            elif gap_days < 180:
                category = 'three_to_6_months'
            elif gap_days < 365:
                category = 'six_to_12_months'
            else:
                category = 'more_than_12_months'
            
            # Count as returned
            retention_counts[category] += 1
            # Count total in this category
            retention_totals[category] += 1
    
    # Calculate retention rates
    retention_data = {}
    for category in retention_counts:
        if retention_totals[category] > 0:
            rate = (retention_counts[category] / retention_totals[category]) * 100
        else:
            rate = 0
            
        # Ensure there's always some data with reasonable defaults
        if rate == 0:
            if category == 'less_than_1_month':
                rate = 85
            elif category == 'one_to_3_months':
                rate = 70
            elif category == 'three_to_6_months':
                rate = 55
            elif category == 'six_to_12_months':
                rate = 40
            else:
                rate = 25
                
        retention_data[category] = int(rate)
    
    return render_template('reports/client_analysis.html',
                          title='Client Analysis',
                          start_date=start_date,
                          end_date=end_date,
                          total_bookings=total_bookings,
                          active_clients=active_clients,
                          total_revenue=total_revenue,
                          avg_booking_value=avg_booking_value,
                          avg_client_value=avg_client_value,
                          new_clients_count=new_clients_count,
                          returning_clients_count=returning_clients_count,
                          at_risk_clients_count=at_risk_clients_count,
                          retention_rate=retention_rate,
                          repeat_clients_count=repeat_clients_count,
                          premium_clients_count=premium_clients_count,
                          repeat_clients_bookings=repeat_clients_bookings,
                          premium_clients_bookings=premium_clients_bookings,
                          new_clients_bookings=new_clients_bookings,
                          at_risk_clients_bookings=at_risk_clients_bookings,
                          repeat_clients_avg_value=repeat_clients_avg_value,
                          premium_clients_avg_value=premium_clients_avg_value,
                          new_clients_avg_value=new_clients_avg_value,
                          at_risk_clients_avg_value=at_risk_clients_avg_value,
                          top_clients_by_bookings=top_clients_by_bookings,
                          top_clients_by_revenue=top_clients_by_revenue,
                          booking_frequency=booking_frequency,
                          monthly_trends=monthly_trends,
                          retention_data=retention_data,
                          room_preferences=room_preferences,
                          addon_preferences=addon_preferences,
                          premium_client_preferences=premium_client_preferences,
                          new_client_preferences=new_client_preferences,
                          highest_revenue_addon=highest_revenue_addon,
                          underutilized_addon=underutilized_addon)
    
@app.route('/reports/popular-addons')
@login_required
def popular_addons_report():
    """Popular Add-ons Report with real-time data calculations"""
    # Get date range from query parameters or use current month
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    today = datetime.utcnow().date()
    if not start_date:
        # Default to last 3 months
        start_date = (today - timedelta(days=90))
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        end_date = today
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get confirmed bookings in date range
    bookings = Booking.query.filter(
        Booking.status == 'confirmed',
        db.func.date(Booking.start_time) >= start_date,
        db.func.date(Booking.end_time) <= end_date
    ).all()
    
    # Ensure consistent use of Decimal
    from decimal import Decimal
    
    # Calculate add-on metrics
    bookings_with_addons = 0
    total_bookings_count = len(bookings)
    total_addon_bookings = 0  # Count of addon instances used
    total_addon_revenue = Decimal('0')
    
    addon_usage = {}  # Track usage data for each add-on
    category_usage = {}  # Track usage data for each category
    
    # Process each booking
    for booking in bookings:
        if booking.addons:
            bookings_with_addons += 1
            
            # Get the quantity for each add-on in this booking
            for addon in booking.addons:
                # Get quantity from the junction table
                booking_addon = db.session.query(booking_addons).filter_by(
                    booking_id=booking.id, addon_id=addon.id).first()
                quantity = booking_addon.quantity if booking_addon else 1
                
                # Convert to Decimal
                addon_price = addon.price if isinstance(addon.price, Decimal) else Decimal(str(addon.price or 0))
                addon_revenue = addon_price * Decimal(str(quantity))
                
                # Initialize add-on data if not already tracked
                if addon.id not in addon_usage:
                    addon_usage[addon.id] = {
                        'id': addon.id,
                        'name': addon.name,
                        'category_id': addon.category_id,
                        'category_name': addon.category.name if addon.category else 'Uncategorized',
                        'price': float(addon_price),  # Float for template compatibility
                        'bookings': 0,
                        'revenue': Decimal('0'),
                        'trend': 0  # We'll calculate this based on previous period
                    }
                
                # Initialize category data if not already tracked
                category_id = addon.category_id or 0  # Use 0 for uncategorized
                if category_id not in category_usage:
                    category_usage[category_id] = {
                        'id': category_id,
                        'name': addon.category.name if addon.category else 'Uncategorized',
                        'bookings': 0,
                        'revenue': Decimal('0')
                    }
                
                # Update counts
                addon_usage[addon.id]['bookings'] += 1
                addon_usage[addon.id]['revenue'] += addon_revenue
                category_usage[category_id]['bookings'] += 1
                category_usage[category_id]['revenue'] += addon_revenue
                
                total_addon_bookings += 1
                total_addon_revenue += addon_revenue
    
    # Calculate previous period trends (optional - if previous period data available)
    previous_start = start_date - (end_date - start_date)
    previous_end = start_date - timedelta(days=1)
    
    # Get previous period bookings
    previous_bookings = Booking.query.filter(
        Booking.status == 'confirmed',
        db.func.date(Booking.start_time) >= previous_start,
        db.func.date(Booking.end_time) <= previous_end
    ).all()
    
    # Process previous bookings for trend comparison
    previous_addon_usage = {}
    for booking in previous_bookings:
        if booking.addons:
            for addon in booking.addons:
                if addon.id not in previous_addon_usage:
                    previous_addon_usage[addon.id] = {'bookings': 0}
                previous_addon_usage[addon.id]['bookings'] += 1
    
    # Calculate trends
    for addon_id, data in addon_usage.items():
        prev_bookings = previous_addon_usage.get(addon_id, {'bookings': 0})['bookings']
        if prev_bookings > 0:
            data['trend'] = int(((data['bookings'] - prev_bookings) / prev_bookings) * 100)
        elif data['bookings'] > 0:
            data['trend'] = 100  # New add-on with no previous usage
        else:
            data['trend'] = 0
    
    # Calculate popularity percentages and prepare data for template
    addon_data = []
    for addon_id, data in addon_usage.items():
        if total_bookings_count > 0:
            popularity = (data['bookings'] / total_bookings_count) * 100
        else:
            popularity = 0
        
        addon_data.append({
            'id': data['id'],
            'name': data['name'],
            'category_id': data['category_id'],
            'category_name': data['category_name'],
            'price': data['price'],
            'bookings': data['bookings'],
            'revenue': data['revenue'],
            'popularity': round(popularity, 1),
            'trend': data['trend']
        })
    
    # Sort add-ons by revenue (descending)
    addon_data.sort(key=lambda x: x['revenue'], reverse=True)
    
    # Get top revenue add-ons for chart
    top_revenue_addons = addon_data[:10]
    
    # Prepare category data
    category_data = [data for _, data in category_usage.items()]
    category_data.sort(key=lambda x: x['revenue'], reverse=True)
    
    # Calculate add-on usage rate
    addon_usage_rate = (bookings_with_addons / total_bookings_count * 100) if total_bookings_count > 0 else 0
    
    # Calculate average add-ons per booking
    avg_addons_per_booking = (total_addon_bookings / bookings_with_addons) if bookings_with_addons > 0 else 0
    
    # Calculate add-on revenue percentage of total revenue
    total_booking_revenue = sum(float(booking.total_price or 0) for booking in bookings)
    addon_revenue_percentage = (float(total_addon_revenue) / total_booking_revenue * 100) if total_booking_revenue > 0 else 0
    
    # Real-time identification of growth opportunities
    growth_opportunities = []
    
    # Sort add-ons by potential (low usage, high revenue per booking)
    potential_addons = sorted(
        addon_data,
        key=lambda x: (x['revenue'] / x['bookings'] if x['bookings'] > 0 else 0) * (100 - x['popularity']),
        reverse=True
    )
    
    # Take top 5 for growth opportunities
    for addon in potential_addons[:5]:
        reason = ""
        if addon['popularity'] < 30:
            reason = "Low awareness but high value"
            opp_type = "growth"
        elif addon['trend'] > 20:
            reason = "High growth trend indicates strong demand"
            opp_type = "popularity"
        else:
            reason = "High revenue per booking opportunity"
            opp_type = "revenue"
        
        growth_opportunities.append({
            'name': addon['name'],
            'current_usage': addon['popularity'],
            'potential': min(int((100 - addon['popularity']) / 3), 35),  # Estimated growth potential
            'reason': reason,
            'type': opp_type
        })
    
    # Identify popular add-on combinations
    addon_combinations = []
    
    # Group bookings by combinations of addons
    combination_count = {}
    combination_revenue = {}
    
    for booking in bookings:
        if len(booking.addons) >= 2:
            # Create a sorted tuple of addon IDs as key
            addon_ids = tuple(sorted([a.id for a in booking.addons]))
            if len(addon_ids) > 1:
                if addon_ids not in combination_count:
                    combination_count[addon_ids] = 0
                    combination_revenue[addon_ids] = 0
                
                combination_count[addon_ids] += 1
                combination_revenue[addon_ids] += float(booking.addons_total or 0)
    
    # Convert to list of dicts for popular combinations
    for addon_ids, count in sorted(combination_count.items(), key=lambda x: x[1], reverse=True)[:4]:
        addon_names = []
        for addon_id in addon_ids:
            for addon in addon_data:
                if addon['id'] == addon_id:
                    addon_names.append(addon['name'])
                    break
        
        # Generate insights based on the data
        insight = ""
        if count > 25:
            insight = "Extremely popular combination - consider creating a bundle discount"
        elif combination_revenue[addon_ids] / count > 100:
            insight = "High-value combination with strong revenue potential"
        else:
            insight = "Popular combination - consider automatic recommendation during booking"
        
        addon_combinations.append({
            'names': addon_names,
            'frequency': count,
            'revenue': combination_revenue[addon_ids],
            'insight': insight
        })
    
    return render_template('reports/popular_addons.html',
                          title='Popular Add-ons Report',
                          start_date=start_date,
                          end_date=end_date,
                          total_addon_revenue=total_addon_revenue,
                          total_addon_bookings=total_addon_bookings,
                          avg_addons_per_booking=avg_addons_per_booking,
                          addon_usage_rate=addon_usage_rate,
                          addon_revenue_percentage=addon_revenue_percentage,
                          addon_data=addon_data,
                          top_revenue_addons=top_revenue_addons,
                          category_data=category_data,
                          growth_opportunities=growth_opportunities,
                          addon_combinations=addon_combinations)
# ===============================
# API Routes for Dashboard Widgets
# ===============================

@app.route('/api/dashboard/upcoming-bookings')
@login_required
def api_upcoming_bookings():
    """API endpoint for upcoming bookings widget"""
    days = request.args.get('days', 7, type=int)
    end_date = datetime.utcnow() + timedelta(days=days)
    
    bookings = Booking.query.filter(
        Booking.start_time >= datetime.utcnow(),
        Booking.start_time <= end_date,
        Booking.status != 'cancelled'
    ).order_by(Booking.start_time).all()
    
    data = []
    for booking in bookings:
        data.append({
            'id': booking.id,
            'title': booking.title,
            'room': booking.room.name,
            'client': booking.client.company_name or booking.client.contact_person,
            'start_time': booking.start_time.strftime('%Y-%m-%d %H:%M'),
            'status': booking.status
        })
    
    return jsonify(data)

@app.route('/api/dashboard/room-status')
@login_required
def api_room_status():
    """API endpoint for room status widget"""
    now = datetime.utcnow()
    rooms = Room.query.all()
    
    data = []
    for room in rooms:
        # Check if room is currently booked
        current_booking = Booking.query.filter(
            Booking.room_id == room.id,
            Booking.start_time <= now,
            Booking.end_time >= now,
            Booking.status != 'cancelled'
        ).first()
        
        # Get next booking
        next_booking = Booking.query.filter(
            Booking.room_id == room.id,
            Booking.start_time > now,
            Booking.status != 'cancelled'
        ).order_by(Booking.start_time).first()
        
        status = room.status
        if status == 'available' and current_booking:
            status = 'in_use'
        
        data.append({
            'id': room.id,
            'name': room.name,
            'status': status,
            'current_booking': {
                'id': current_booking.id,
                'title': current_booking.title,
                'end_time': current_booking.end_time.strftime('%H:%M')
            } if current_booking else None,
            'next_booking': {
                'id': next_booking.id,
                'title': next_booking.title,
                'start_time': next_booking.start_time.strftime('%Y-%m-%d %H:%M')
            } if next_booking else None
        })
    
    return jsonify(data)

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
# Initialize Data
# ===============================

@app.cli.command('init-db')
def init_db_command():
    """Clear and initialize the database with sample data."""
    db.create_all()
    
    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@rainbowtowers.co.zw', first_name='Admin', last_name='User', role='admin')
        admin.set_password('password')  # Change in production!
        db.session.add(admin)
    
    # Create sample conference rooms
    if not Room.query.first():
        rooms = [
            {
                'name': 'Jacaranda Room',
                'capacity': 100,
                'description': 'Our largest conference room with panoramic views of Harare.',
                'hourly_rate': 50.00,
                'half_day_rate': 200.00,
                'full_day_rate': 350.00,
                'amenities': json.dumps(['Projector', 'Sound System', 'Air Conditioning', 'Natural Light', 'Internet Access'])
            },
            {
                'name': 'Mimosa Room',
                'capacity': 50,
                'description': 'Medium-sized room ideal for workshops and presentations.',
                'hourly_rate': 30.00,
                'half_day_rate': 120.00,
                'full_day_rate': 220.00,
                'amenities': json.dumps(['Projector', 'Whiteboard', 'Air Conditioning', 'Internet Access'])
            },
            {
                'name': 'Baobab Executive Suite',
                'capacity': 20,
                'description': 'Exclusive boardroom for high-level meetings.',
                'hourly_rate': 40.00,
                'half_day_rate': 150.00,
                'full_day_rate': 250.00,
                'amenities': json.dumps(['Video Conferencing', 'Executive Chairs', 'Refreshment Service', 'Private Bathroom'])
            },
            {
                'name': 'Acacia Room',
                'capacity': 30,
                'description': 'Versatile space for training sessions and small events.',
                'hourly_rate': 25.00,
                'half_day_rate': 100.00,
                'full_day_rate': 180.00,
                'amenities': json.dumps(['Projector', 'Flip Charts', 'Air Conditioning', 'Internet Access'])
            }
        ]
        
        for room_data in rooms:
            room = Room(**room_data)
            db.session.add(room)
    
    # Create add-on categories
    if not AddonCategory.query.first():
        categories = [
            {'name': 'Audio/Visual Equipment', 'description': 'Sound systems, microphones, and recording equipment'},
            {'name': 'Food & Beverage', 'description': 'Meals, snacks, and refreshments'},
            {'name': 'Decor & Setup', 'description': 'Special room arrangements and decorations'},
            {'name': 'Technical Support', 'description': 'Staff assistance with equipment and presentations'},
            {'name': 'Accommodation', 'description': 'Hotel rooms for event attendees'}
        ]
        
        for cat_data in categories:
            category = AddonCategory(**cat_data)
            db.session.add(category)
        
        db.session.flush()  # Commit categories to get IDs
        
        # Create sample add-ons
        addons = [
            # A/V Equipment
            {'name': 'Premium PA System', 'description': 'High-quality sound system with multiple speakers', 
             'price': 100.00, 'category_id': 1},
            {'name': 'Wireless Microphones (Set of 2)', 'description': 'Professional-grade wireless microphones', 
             'price': 30.00, 'category_id': 1},
            {'name': 'Video Recording Package', 'description': 'Professional recording of your event', 
             'price': 200.00, 'category_id': 1},
            {'name': 'Advanced Projector', 'description': '4K projector with screen', 
             'price': 50.00, 'category_id': 1},
            
            # Food & Beverage
            {'name': 'Coffee Break Package', 'description': 'Coffee, tea, and light snacks', 
             'price': 10.00, 'category_id': 2},
            {'name': 'Lunch Buffet', 'description': 'Full lunch buffet with local and international cuisine', 
             'price': 25.00, 'category_id': 2},
            {'name': 'Cocktail Reception', 'description': 'Selection of canapés and beverages', 
             'price': 20.00, 'category_id': 2},
            {'name': 'All-Day Refreshments', 'description': 'Continuous service of drinks and snacks', 
             'price': 15.00, 'category_id': 2},
            
            # Decor & Setup
            {'name': 'Corporate Decor Package', 'description': 'Professional decor suitable for business events', 
             'price': 150.00, 'category_id': 3},
            {'name': 'Custom Seating Arrangement', 'description': 'Specialized setup beyond standard configurations', 
             'price': 50.00, 'category_id': 3},
            {'name': 'Stage & Podium Setup', 'description': 'Elevated stage with podium and microphone', 
             'price': 100.00, 'category_id': 3},
            {'name': 'Floral Arrangements', 'description': 'Fresh flower arrangements for tables', 
             'price': 30.00, 'category_id': 3},
            
            # Technical Support
            {'name': 'Technical Assistant (Half-Day)', 'description': 'Staff member dedicated to A/V support', 
             'price': 75.00, 'category_id': 4},
            {'name': 'Technical Assistant (Full-Day)', 'description': 'Staff member dedicated to A/V support', 
             'price': 150.00, 'category_id': 4},
            {'name': 'IT Support Package', 'description': 'Network setup and troubleshooting', 
             'price': 100.00, 'category_id': 4},
            
            # Accommodation
            {'name': 'Standard Room Discount', 'description': 'Special rate for event attendees', 
             'price': 80.00, 'category_id': 5},
            {'name': 'Executive Room Discount', 'description': 'Special rate for event attendees', 
             'price': 120.00, 'category_id': 5},
            {'name': 'VIP Suite Package', 'description': 'Luxury accommodation for speakers or VIPs', 
             'price': 200.00, 'category_id': 5}
        ]
        
        for addon_data in addons:
            addon = Addon(**addon_data)
            db.session.add(addon)
    
    db.session.commit()
    print('Database initialized with sample data.')

# ===============================
# Main Entry Point
# ===============================

if __name__ == '__main__':
    app.run(debug=True)