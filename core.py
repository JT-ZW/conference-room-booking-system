import os
from flask import session, flash, render_template, redirect, url_for
from datetime import datetime, UTC
from supabase import create_client, Client
from settings.config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY
from flask_login import UserMixin, current_user
from utils.validation import convert_datetime_strings, safe_float_conversion, safe_int_conversion
from decimal import Decimal

# Initialize Supabase clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
if SUPABASE_SERVICE_KEY:
    supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
else:
    supabase_admin = supabase

# ===============================
# UTILITY FUNCTIONS
# ===============================

def safe_str(value):
    """Safely convert value to string, handling None"""
    if value is None:
        return ''
    return str(value).strip()

def safe_str_lower(value):
    """Safely convert value to lowercase string, handling None"""
    return safe_str(value).lower()

# ===============================
# USER MODEL
# ===============================

class User(UserMixin):
    """User class that works with Supabase Auth"""
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.email = user_data.get('email')
        self.user_metadata = user_data.get('user_metadata', {})
        self.app_metadata = user_data.get('app_metadata', {})
        self.profile = self.get_profile()

    def get_profile(self):
        """Get user profile from Supabase users table"""
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
# DATABASE HELPERS
# ===============================

def supabase_select(table_name, columns="*", filters=None, order_by=None, limit=None):
    """Select data from Supabase table"""
    try:
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
        return response.data if response.data else []
            
    except Exception as e:
        print(f"❌ ERROR: Failed to query table '{table_name}': {e}")
        return []

def supabase_insert(table_name, data):
    """Insert data into Supabase table"""
    try:
        response = supabase_admin.table(table_name).insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Insert error: {e}")
        return None

def supabase_update(table_name, data, filters):
    """Update data in Supabase table"""
    try:
        query = supabase_admin.table(table_name).update(data)
        
        for filter_item in filters:
            if len(filter_item) == 3:
                column, operator, value = filter_item
                if operator == 'eq':
                    query = query.eq(column, value)
        
        response = query.execute()
        return response.data if response.data else []
                
    except Exception as e:
        print(f"Update error: {e}")
        return []

def supabase_delete(table_name, filters):
    """Delete data from Supabase table"""
    try:
        query = supabase_admin.table(table_name)
        
        for filter_item in filters:
            if len(filter_item) == 3:
                column, operator, value = filter_item
                if operator == 'eq':
                    query = query.eq(column, value)
        
        query.delete().execute()
        return True
    except Exception as e:
        print(f"Delete error: {e}")
        return False

# ===============================
# AUTHENTICATION
# ===============================

def authenticate_user(email, password):
    """Authenticate user with Supabase"""
    try:
        response = supabase.auth.sign_in({
            "email": email,
            "password": password
        })
        
        if response.user and response.session:
            # Clear and set up session
            session.clear()
            session.permanent = True
            
            session_data = {
                'access_token': response.session.access_token,
                'refresh_token': response.session.refresh_token,
                'user_id': response.user.id
            }
            
            session['supabase_session'] = session_data
            session['created_at'] = datetime.now(UTC).isoformat()
            session['user_id'] = response.user.id
            session['user_email'] = response.user.email
            session.modified = True
            
            return User(response.user.__dict__)
        
        return None
            
    except Exception as e:
        print(f"Authentication error: {e}")
        return None

def create_user_supabase(email, password, first_name, last_name, role='staff'):
    """Create new user in Supabase"""
    try:
        # Create auth user
        auth_response = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
                "role": role
            }
        })
        
        if auth_response.user:
            # Create user profile
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
            
            profile_response = supabase_admin.table('users').insert(profile_data).execute()
            
            if profile_response.data:
                return True, None
            else:
                # Cleanup on failure
                try:
                    supabase_admin.auth.admin.delete_user(auth_response.user.id)
                except:
                    pass
                return False, "Failed to create user profile"
        
        return False, "Failed to create auth user"
        
    except Exception as e:
        error_message = str(e).lower()
        if 'already registered' in error_message or 'already exists' in error_message:
            return False, "Email already registered"
        elif 'password' in error_message:
            return False, "Password does not meet requirements"
        elif 'email' in error_message and 'invalid' in error_message:
            return False, "Invalid email format"
        else:
            return False, "Registration failed"

# ===============================
# ACTIVITY LOGGING
# ===============================

def safe_log_user_activity(activity_type, description, resource_type=None, resource_id=None, metadata=None):
    """Log user activity (simplified version)"""
    try:
        activity_data = {
            'activity_type': activity_type,
            'description': description,
            'created_at': datetime.now(UTC).isoformat()
        }
        
        if current_user and current_user.is_authenticated:
            activity_data['user_id'] = str(current_user.id)
        
        if resource_type:
            activity_data['resource_type'] = resource_type
        if resource_id:
            activity_data['resource_id'] = str(resource_id)
        if metadata and isinstance(metadata, dict):
            activity_data['metadata'] = metadata
        
        # Try to insert into activity log table if it exists
        try:
            supabase_admin.table('user_activity_log').insert(activity_data).execute()
        except:
            # If table doesn't exist, just log to console
            print(f"📝 ACTIVITY: {activity_type} - {description}")
        
        return True
        
    except Exception as e:
        print(f"Activity logging error: {e}")
        return True  # Don't fail operations due to logging issues

# ===============================
# CLIENT MANAGEMENT
# ===============================

def get_all_clients_from_db():
    """Get all clients from database"""
    try:
        response = supabase_admin.table('clients').select('*').order('company_name').execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch clients: {e}")
        return []

def get_client_by_id_from_db(client_id):
    """Get specific client by ID"""
    try:
        response = supabase_admin.table('clients').select('*').eq('id', client_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch client {client_id}: {e}")
        return None

def get_client_bookings_from_db(client_id):
    """Get all bookings for a specific client"""
    try:
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity)
        """).eq('client_id', client_id).order('start_time', desc=True).execute()
        
        if response.data:
            return convert_datetime_strings(response.data)
        return []
            
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch client bookings: {e}")
        return []

def create_client_in_db(client_data):
    """Create a new client"""
    try:
        # Ensure required fields
        required_fields = ['contact_person', 'email']
        for field in required_fields:
            if not client_data.get(field):
                raise ValueError(f"Missing required field: {field}")
        
        response = supabase_admin.table('clients').insert(client_data).execute()
        return response.data[0] if response.data else None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to create client: {e}")
        return None

def update_client_in_db(client_id, client_data):
    """Update an existing client"""
    try:
        response = supabase_admin.table('clients').update(client_data).eq('id', client_id).execute()
        return response.data[0] if response.data else {'success': True}
    except Exception as e:
        print(f"❌ ERROR: Failed to update client: {e}")
        return None

def delete_client_from_db(client_id):
    """Delete a client"""
    try:
        # Check for existing bookings
        bookings_check = supabase_admin.table('bookings').select('id').eq('client_id', client_id).execute()
        
        if bookings_check.data:
            return False, "Cannot delete client with existing bookings"
        
        # Delete client
        supabase_admin.table('clients').delete().eq('id', client_id).execute()
        return True, "Client deleted successfully"
        
    except Exception as e:
        print(f"❌ ERROR: Failed to delete client: {e}")
        return False, f"Error deleting client: {str(e)}"

def get_clients_with_booking_counts():
    """Get all clients with their booking counts"""
    try:
        # Fetch all clients
        clients = get_all_clients_from_db()
        
        # Fetch booking counts
        bookings_response = supabase_admin.table('bookings').select('id, client_id').execute()
        bookings = bookings_response.data if bookings_response.data else []
        
        # Count bookings per client
        booking_counts = {}
        for booking in bookings:
            client_id = booking.get('client_id')
            if client_id:
                booking_counts[client_id] = booking_counts.get(client_id, 0) + 1
        
        # Add counts to clients
        for client in clients:
            client['booking_count'] = booking_counts.get(client['id'], 0)
            client['display_name'] = client.get('company_name') or client.get('contact_person', 'Unknown')
        
        return clients
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get clients with booking counts: {e}")
        return []

def find_or_create_client_enhanced(client_name, company_name=None, email=None):
    """Find existing client or create new one"""
    try:
        if not client_name or not client_name.strip():
            return None
        
        client_name = client_name.strip()
        company_name = company_name.strip() if company_name else None
        email = email.strip().lower() if email else None
        
        # Search for existing client
        existing_client = None
        clients = get_all_clients_from_db()
        
        for client in clients:
            # Check by company name
            if company_name and client.get('company_name'):
                if client['company_name'].strip().lower() == company_name.lower():
                    existing_client = client
                    break
            
            # Check by contact person
            if client.get('contact_person'):
                if client['contact_person'].strip().lower() == client_name.lower():
                    existing_client = client
                    break
            
            # Check by email
            if email and client.get('email'):
                if client['email'].strip().lower() == email:
                    existing_client = client
                    break
        
        if existing_client:
            return existing_client['id']
        
        # Create new client
        client_data = {
            'contact_person': client_name,
            'company_name': company_name,
            'email': email or f"{client_name.lower().replace(' ', '.')}@example.com",
            'created_at': datetime.now(UTC).isoformat(),
            'notes': f'Auto-created from booking form'
        }
        
        result = create_client_in_db(client_data)
        return result['id'] if result else None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to find/create client: {e}")
        return None

# ===============================
# ROOM MANAGEMENT
# ===============================

def is_room_available_supabase(room_id, start_time, end_time, exclude_booking_id=None):
    """Check if a room is available for given time period"""
    try:
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

# ===============================
# BOOKING MANAGEMENT
# ===============================

def extract_booking_form_data(form_data):
    """Extract and validate booking data from form submission"""
    try:
        # Required fields validation
        required_fields = {
            'room_id': 'Please select a venue',
            'attendees': 'Please enter number of attendees',
            'client_name': 'Please enter client name',
            'event_type': 'Please select event type',
            'start_time': 'Please select start date and time',
            'end_time': 'Please select end date and time'
        }
        
        for field, message in required_fields.items():
            if not form_data.get(field, '').strip():
                flash(f'❌ {message}', 'danger')
                return None
        
        # Parse datetime fields
        try:
            start_time = datetime.strptime(form_data.get('start_time'), '%Y-%m-%d %H:%M')
            end_time = datetime.strptime(form_data.get('end_time'), '%Y-%m-%d %H:%M')
        except ValueError:
            flash('❌ Invalid date/time format', 'danger')
            return None
        
        # Validate time logic
        if end_time <= start_time:
            flash('❌ End time must be after start time', 'danger')
            return None
        
        if start_time < datetime.now():
            flash('❌ Booking cannot be scheduled in the past', 'danger')
            return None
        
        # Process pricing items
        pricing_items, total_price = extract_pricing_items_from_form(form_data)
        
        # If no pricing items, calculate basic room rate
        if not pricing_items or total_price <= 0:
            room_id = int(form_data.get('room_id'))
            total_price = calculate_booking_total(room_id, start_time, end_time)
            
            # Create basic pricing item
            room_data = supabase_select('rooms', filters=[('id', 'eq', room_id)])
            room_name = room_data[0].get('name', 'Conference Room') if room_data else 'Conference Room'
            
            duration_hours = (end_time - start_time).total_seconds() / 3600
            pricing_items = [{
                'description': f'{room_name} Rental',
                'quantity': 1,
                'unit_price': total_price,
                'total_price': total_price,
                'notes': f'Duration: {duration_hours:.1f} hours'
            }]
        
        # Build booking data
        booking_data = {
            'room_id': int(form_data.get('room_id')),
            'attendees': int(form_data.get('attendees')),
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
        
        return booking_data
        
    except Exception as e:
        print(f"❌ ERROR: Failed to extract form data: {e}")
        flash('❌ Error processing form data', 'danger')
        return None

def extract_pricing_items_from_form(form_data):
    """Extract pricing items from dynamic form fields"""
    try:
        pricing_items = []
        total_price = 0
        
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
            
            item_index += 1
        
        return pricing_items, total_price
        
    except Exception as e:
        print(f"❌ ERROR: Failed to extract pricing items: {e}")
        return [], 0

def calculate_booking_total(room_id, start_time, end_time, addon_ids=None):
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
        
        total = room_rate + addons_total
        return max(total, 0)
        
    except Exception as e:
        print(f"Price calculation error: {e}")
        return 0

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
            errors.append('❌ Room is not available for the selected time period')
        
        # Check room capacity
        room_data = supabase_select('rooms', filters=[('id', 'eq', booking_data['room_id'])])
        if room_data:
            room_capacity = room_data[0].get('capacity', 0)
            if booking_data['attendees'] > room_capacity:
                errors.append(f'❌ Room capacity ({room_capacity}) exceeded')
        
        # Validate booking duration
        duration_hours = (booking_data['end_time'] - booking_data['start_time']).total_seconds() / 3600
        if duration_hours > 12:
            errors.append('❌ Bookings cannot exceed 12 hours')
        
        if duration_hours < 0.5:
            errors.append('❌ Bookings must be at least 30 minutes long')
        
        # Validate business hours (6 AM to 11 PM)
        if booking_data['start_time'].hour < 6 or booking_data['start_time'].hour > 22:
            errors.append('❌ Bookings must start within business hours (6 AM - 10 PM)')
        
        if booking_data['end_time'].hour < 6 or booking_data['end_time'].hour > 23:
            errors.append('❌ Bookings must end within business hours (6 AM - 11 PM)')
        
    except Exception as e:
        print(f"❌ ERROR: Business rule validation failed: {e}")
        errors.append('❌ Error validating booking rules')
    
    return errors

def find_or_create_event_type(event_type, custom_event_type=None):
    """Find or create event type"""
    try:
        # Determine event type name
        if event_type == 'other' and custom_event_type:
            event_name = custom_event_type.strip()
        else:
            event_name = event_type.replace('_', ' ').title()
        
        # Search for existing
        existing_event = supabase_admin.table('event_types').select('*').eq('name', event_name).execute()
        
        if existing_event.data:
            event_type_id = existing_event.data[0]['id']
            # Increment usage count
            supabase_admin.table('event_types').update({
                'usage_count': existing_event.data[0]['usage_count'] + 1
            }).eq('id', event_type_id).execute()
            return event_type_id
        
        # Create new
        event_data = {
            'name': event_name,
            'usage_count': 1,
            'created_at': datetime.now(UTC).isoformat()
        }
        
        result = supabase_insert('event_types', event_data)
        return result['id'] if result else None
            
    except Exception as e:
        print(f"❌ ERROR: Failed to find/create event type: {e}")
        return None

def create_complete_booking(booking_data, client_id, event_type_id):
    """Create booking with all related data"""
    try:
        # Determine event title
        if booking_data['event_type'] == 'other' and booking_data['custom_event_type']:
            event_title = booking_data['custom_event_type']
        else:
            event_title = booking_data['event_type'].replace('_', ' ').title()
        
        # Calculate room rate and addons
        room_rate, addons_total = calculate_room_and_addons_totals(booking_data['pricing_items'])
        
        # Create booking record
        booking_record = {
            'room_id': booking_data['room_id'],
            'client_id': client_id,
            'event_type_id': event_type_id,
            'title': f"{event_title} - {booking_data['client_name']}",
            'start_time': booking_data['start_time'].isoformat(),
            'end_time': booking_data['end_time'].isoformat(),
            'attendees': booking_data['attendees'],
            'status': booking_data['status'],
            'notes': booking_data['notes'],
            'room_rate': room_rate,
            'addons_total': addons_total,
            'total_price': booking_data['total_price'],
            'created_by': current_user.id,
            'created_at': datetime.now(UTC).isoformat(),
            'client_name': booking_data['client_name'],
            'company_name': booking_data['company_name'],
            'client_email': booking_data['client_email']
        }
        
        booking_result = supabase_insert('bookings', booking_record)
        if not booking_result:
            return None
        
        booking_id = booking_result['id']
        
        # Create custom addon records
        for item in booking_data['pricing_items']:
            addon_record = {
                'booking_id': booking_id,
                'description': item['description'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price'],
                'total_price': item['total_price'],
                'notes': item.get('notes'),
                'created_at': datetime.now(UTC).isoformat()
            }
            
            supabase_insert('booking_custom_addons', addon_record)
        
        return booking_id
        
    except Exception as e:
        print(f"❌ ERROR: Failed to create booking: {e}")
        return None

def get_complete_booking_details(booking_id):
    """Get complete booking details including all related data"""
    try:
        # Get booking with relations
        booking_response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(*),
            client:clients(*),
            event_type:event_types(*)
        """).eq('id', booking_id).execute()
        
        if not booking_response.data:
            return None
        
        booking = booking_response.data[0]
        
        # Get custom addons
        addons_response = supabase_admin.table('booking_custom_addons').select('*').eq('booking_id', booking_id).execute()
        booking['custom_addons'] = addons_response.data if addons_response.data else []
        
        # Convert datetime strings
        booking = convert_datetime_strings(booking)
        
        return booking
        
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch booking details: {e}")
        return None

def update_complete_booking(booking_id, booking_data, existing_booking):
    """Update booking with all related data"""
    try:
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
        
        # Calculate room rate and addons
        room_rate, addons_total = calculate_room_and_addons_totals(booking_data['pricing_items'])
        
        # Update booking record
        booking_update = {
            'room_id': booking_data['room_id'],
            'client_id': client_id,
            'event_type_id': event_type_id,
            'title': f"{event_title} - {booking_data['client_name']}",
            'start_time': booking_data['start_time'].isoformat(),
            'end_time': booking_data['end_time'].isoformat(),
            'attendees': booking_data['attendees'],
            'status': booking_data['status'],
            'notes': booking_data['notes'],
            'room_rate': room_rate,
            'addons_total': addons_total,
            'total_price': booking_data['total_price'],
            'updated_at': datetime.now(UTC).isoformat(),
            'client_name': booking_data['client_name'],
            'company_name': booking_data['company_name'],
            'client_email': booking_data['client_email']
        }
        
        booking_result = supabase_update('bookings', booking_update, [('id', 'eq', booking_id)])
        if not booking_result:
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
                'created_at': datetime.now(UTC).isoformat()
            }
            
            supabase_insert('booking_custom_addons', addon_record)
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Failed to update booking: {e}")
        return False

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
                item['is_room_rate'] = True
            else:
                addons_total += item_total
                item['is_room_rate'] = False
        
        # If no room items identified, treat first item as room rate
        if room_rate == 0 and pricing_items:
            first_item = pricing_items[0]
            room_rate = first_item['total_price']
            addons_total = sum(item['total_price'] for item in pricing_items[1:])
            first_item['is_room_rate'] = True
            for item in pricing_items[1:]:
                item['is_room_rate'] = False
        
        return room_rate, addons_total
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate totals: {e}")
        return 0.0, 0.0

def calculate_booking_totals(booking, room_rates=None):
    """Calculate booking totals"""
    try:
        # Parse times safely
        if isinstance(booking.get('start_time'), str):
            start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).replace(tzinfo=None)
            end_time = datetime.fromisoformat(booking['end_time'].replace('Z', '+00:00')).replace(tzinfo=None)
        else:
            start_time = booking.get('start_time')
            end_time = booking.get('end_time')
        
        if not start_time or not end_time:
            # Fallback values
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
        
        # Check custom addons
        for addon in booking.get('custom_addons', []):
            addons_total += safe_float_conversion(addon.get('total_price', 0))
            addon_items.append({
                'name': addon.get('description', 'Unknown Item'),
                'quantity': addon.get('quantity', 1),
                'price': safe_float_conversion(addon.get('unit_price', 0)),
                'total': safe_float_conversion(addon.get('total_price', 0))
            })
        
        # Use stored values if custom addons not available
        if not addon_items and booking.get('addons_total'):
            addons_total = safe_float_conversion(booking.get('addons_total', 0))
        
        # Use stored room rate if available
        if booking.get('room_rate'):
            room_rate = safe_float_conversion(booking.get('room_rate', room_rate))
        
        total = room_rate + addons_total
        
        return {
            'room_rate': round(room_rate, 2),
            'rate_type': rate_type,
            'addons_total': round(addons_total, 2),
            'addon_items': addon_items,
            'duration_hours': round(duration_hours, 1),
            'subtotal': round(total, 2),
            'total': round(total, 2)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate booking totals: {e}")
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

def get_booking_calendar_events_supabase():
    """Get all bookings formatted for calendar display"""
    try:
        # Get all bookings with related data
        bookings_response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name)
        """).neq('status', 'cancelled').execute()
        
        if not bookings_response.data:
            return []
        
        events = []
        for booking in bookings_response.data:
            # Get room name
            room_name = 'Unknown Room'
            if booking.get('room'):
                room_name = booking['room'].get('name', 'Unknown Room')
            
            # Get client name
            client_name = 'Unknown Client'
            if booking.get('client'):
                client = booking['client']
                client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
            elif booking.get('client_name'):
                client_name = booking.get('client_name')
            
            # Determine event color based on status
            status = booking.get('status', 'tentative')
            color_map = {
                'tentative': '#FFA500',  # Orange
                'confirmed': '#28a745',  # Green
                'cancelled': '#dc3545'   # Red
            }
            color = color_map.get(status, '#17a2b8')  # Default: Teal
            
            # Create event
            event_data = {
                'id': booking['id'],
                'title': booking.get('title') or f"{booking.get('event_type', 'Event')} - {client_name}",
                'start': booking.get('start_time'),
                'end': booking.get('end_time'),
                'color': color,
                'extendedProps': {
                    'room': room_name,
                    'roomId': booking.get('room_id'),
                    'client': client_name,
                    'clientId': booking.get('client_id'),
                    'attendees': booking.get('attendees', 0),
                    'total': safe_float_conversion(booking.get('total_price', 0)),
                    'status': status,
                    'notes': booking.get('notes', '')
                }
            }
            
            events.append(event_data)
        
        return events
        
    except Exception as e:
        print(f"❌ Calendar events error: {e}")
        return []

def format_booking_success_message(booking_data):
    """Format a success message for booking creation"""
    event_title = booking_data.get('custom_event_type') if booking_data.get('event_type') == 'other' else booking_data.get('event_type', 'Event').replace('_', ' ').title()
    
    return f"""
    ✅ <strong>Booking created successfully!</strong><br>
    📋 <strong>Event:</strong> {event_title}<br>
    👤 <strong>Client:</strong> {booking_data.get('client_name')}<br>
    🏢 <strong>Company:</strong> {booking_data.get('company_name') or 'Not specified'}<br>
    👥 <strong>Attendees:</strong> {booking_data.get('attendees')}<br>
    💰 <strong>Total:</strong> ${booking_data.get('total_price'):.2f}
    """

# ===============================
# HANDLER FUNCTIONS
# ===============================

def handle_booking_creation(form_data, rooms_for_template):
    """Handle the creation of a new booking"""
    try:
        from flask import render_template
        
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
            flash('❌ Error processing client information', 'danger')
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
        # Find or create event type
        event_type_id = find_or_create_event_type(
            booking_data['event_type'], 
            booking_data.get('custom_event_type')
        )
        
        # Create booking
        booking_id = create_complete_booking(booking_data, client_id, event_type_id)
        
        if booking_id:
            safe_log_user_activity(
                ActivityTypes.CREATE_BOOKING,
                f"Created booking for {booking_data.get('client_name')}",
                resource_type='booking',
                resource_id=booking_id
            )
            
            success_message = format_booking_success_message(booking_data)
            flash(success_message, 'success')
            
            return redirect(url_for('bookings.view_booking', id=booking_id))
        else:
            flash('❌ Error creating booking', 'danger')
            return render_template('bookings/form.html', 
                                  title='New Booking', 
                                  form=BookingForm(), 
                                  rooms=rooms_for_template)
        
    except Exception as e:
        print(f"❌ ERROR: Booking creation failed: {e}")
        flash('❌ Unexpected error creating booking', 'danger')
        return render_template('bookings/form.html', 
                              title='New Booking', 
                              form=BookingForm(), 
                              rooms=rooms_for_template)

def handle_booking_update(booking_id, form_data, existing_booking, rooms_for_template):
    """Handle updating an existing booking"""
    try:
        from flask import render_template
        
        # Extract and validate form data
        booking_data = extract_booking_form_data(form_data)
        if not booking_data:
            return render_template('bookings/form.html', 
                                  title='Edit Booking', 
                                  form=BookingForm(), 
                                  booking=existing_booking,
                                  rooms=rooms_for_template)
        
        # Validate business rules
        validation_errors = validate_booking_business_rules(booking_data, exclude_booking_id=booking_id)
        if validation_errors:
            for error in validation_errors:
                flash(error, 'danger')
            return render_template('bookings/form.html', 
                                  title='Edit Booking', 
                                  form=BookingForm(), 
                                  booking=existing_booking,
                                  rooms=rooms_for_template)
        
        # Update booking
        success = update_complete_booking(booking_id, booking_data, existing_booking)
        
        if success:
            safe_log_user_activity(
                ActivityTypes.UPDATE_BOOKING,
                f"Updated booking for {booking_data.get('client_name')}",
                resource_type='booking',
                resource_id=booking_id
            )
            
            flash('✅ Booking updated successfully!', 'success')
            return redirect(url_for('bookings.view_booking', id=booking_id))
        else:
            flash('❌ Error updating booking', 'danger')
            return render_template('bookings/form.html', 
                                  title='Edit Booking', 
                                  form=BookingForm(), 
                                  booking=existing_booking,
                                  rooms=rooms_for_template)
        
    except Exception as e:
        print(f"❌ ERROR: Booking update failed: {e}")
        flash('❌ Unexpected error updating booking', 'danger')
        return render_template('bookings/form.html', 
                              title='Edit Booking', 
                              form=BookingForm(), 
                              booking=existing_booking,
                              rooms=rooms_for_template)

# ===============================
# ACTIVITY TYPE CONSTANTS
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
# FORMS
# ===============================

from wtforms import StringField, PasswordField, BooleanField, SelectField, DateTimeField, TextAreaField, IntegerField, DecimalField, HiddenField
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Email, Length, ValidationError, EqualTo

class ClientForm(FlaskForm):
    company_name = StringField('Company Name')
    contact_person = StringField('Contact Person', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number')
    address = TextAreaField('Address')
    notes = TextAreaField('Notes')

class RoomForm(FlaskForm):
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
    room_id = SelectField('Conference Room', coerce=int, validators=[DataRequired()])
    attendees = IntegerField('Number of Attendees (PAX)', validators=[DataRequired()])
    client_name = StringField('Client Name', validators=[DataRequired()])
    company_name = StringField('Company Name')
    client_id = HiddenField()
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
    status = SelectField('Status', choices=[
        ('tentative', 'Tentative'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ], default='tentative')
    
    def validate_end_time(self, field):
        if field.data <= self.start_time.data:
            raise ValidationError('End time must be after start time')
    
    def validate_attendees(self, field):
        if not field.data or not self.room_id.data:
            return
        
        room_data = supabase_select('rooms', filters=[('id', 'eq', self.room_id.data)])
        if not room_data:
            return
        
        room = room_data[0]
        if field.data > room['capacity']:
            flash(f'Warning: Room capacity ({room["capacity"]}) exceeded', 'warning')

class AddonCategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description')

class AddonForm(FlaskForm):
    name = StringField('Add-on Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    price = DecimalField('Price (USD)', places=2, validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active')

class AccommodationForm(FlaskForm):
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

class LoginForm(FlaskForm):
    username = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[
        ('staff', 'Staff Member'),
        ('manager', 'Manager'),
        ('admin', 'Administrator')
    ], default='staff')

    def validate_email(self, field):
        try:
            existing_users = supabase_admin.table('users').select('email').eq('email', field.data.lower()).execute()
            if existing_users.data:
                raise ValidationError('Email address already registered')
        except Exception as e:
            print(f"Warning: Could not check email uniqueness: {e}")

def get_booking_with_details(booking_id):
    """Get booking with all related details"""
    try:
        # Get booking with relations
        booking_response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(*),
            client:clients(*),
            event_type:event_types(*)
        """).eq('id', booking_id).execute()

        if not booking_response.data:
            return None

        booking = booking_response.data[0]

        # Get custom addons
        addons_response = supabase_admin.table('booking_custom_addons').select('*').eq('booking_id', booking_id).execute()
        booking['custom_addons'] = addons_response.data if addons_response.data else []

        # Convert datetime strings
        booking = convert_datetime_strings(booking)

        # Calculate totals
        totals = calculate_booking_totals(booking)
        booking.update(totals)

        return booking

    except Exception as e:
        print(f"❌ ERROR: Failed to fetch booking details: {e}")
        return None

# ===============================
# DASHBOARD FUNCTIONS
# ===============================

def get_dashboard_stats():
    """Get comprehensive dashboard statistics"""
    try:
        from datetime import datetime, UTC, timedelta
        
        stats = {
            'total_bookings': 0,
            'total_clients': 0,
            'total_rooms': 0,
            'available_rooms': 0,
            'confirmed_bookings': 0,
            'tentative_bookings': 0,
            'cancelled_bookings': 0,
            'total_revenue': 0,
            'revenue_this_month': 0,
            'average_booking_value': 0,
            'upcoming_bookings': 0,
            'todays_bookings': 0,
            'occupancy_rate': 0,
            'revenue_growth': 0
        }
        
        # Get all bookings
        bookings_response = supabase_admin.table('bookings').select('*').execute()
        all_bookings = bookings_response.data if bookings_response.data else []
        
        # Get total rooms
        rooms_response = supabase_admin.table('rooms').select('*').execute()
        all_rooms = rooms_response.data if rooms_response.data else []
        stats['total_rooms'] = len(all_rooms)
        stats['available_rooms'] = len([r for r in all_rooms if r.get('is_available', True)])
        
        # Get total clients
        clients_response = supabase_admin.table('clients').select('id').execute()
        stats['total_clients'] = len(clients_response.data) if clients_response.data else 0
        
        # Process bookings by status
        non_cancelled_bookings = [b for b in all_bookings if b.get('status') != 'cancelled']
        stats['total_bookings'] = len(non_cancelled_bookings)
        stats['confirmed_bookings'] = len([b for b in all_bookings if b.get('status') == 'confirmed'])
        stats['tentative_bookings'] = len([b for b in all_bookings if b.get('status') == 'tentative'])
        stats['cancelled_bookings'] = len([b for b in all_bookings if b.get('status') == 'cancelled'])
        
        # Calculate revenue metrics
        total_revenue = 0
        revenue_this_month = 0
        now = datetime.now(UTC)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        for booking in non_cancelled_bookings:
            booking_revenue = safe_float_conversion(booking.get('total_price', 0))
            total_revenue += booking_revenue
            
            # Check if booking is this month
            if booking.get('start_time'):
                try:
                    booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                    # Ensure both dates are timezone-aware for comparison
                    if booking_date >= current_month_start:
                        revenue_this_month += booking_revenue
                except Exception:
                    pass
        
        stats['total_revenue'] = total_revenue
        stats['revenue_this_month'] = revenue_this_month
        stats['average_booking_value'] = total_revenue / len(non_cancelled_bookings) if non_cancelled_bookings else 0
        
        # Calculate upcoming bookings (next 30 days)
        next_month = now + timedelta(days=30)
        upcoming_count = 0
        todays_count = 0
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        for booking in non_cancelled_bookings:
            if booking.get('start_time'):
                try:
                    booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                    
                    # Count upcoming bookings
                    if now <= booking_date <= next_month:
                        upcoming_count += 1
                    
                    # Count today's bookings
                    if today_start <= booking_date < today_end:
                        todays_count += 1
                        
                except Exception:
                    pass
        
        stats['upcoming_bookings'] = upcoming_count
        stats['todays_bookings'] = todays_count
        
        # Calculate occupancy rate (percentage of rooms with bookings in the last 30 days)
        if stats['total_rooms'] > 0:
            # Look at the last 30 days for a more meaningful occupancy rate
            period_start = now - timedelta(days=30)
            period_end = now
            
            occupied_rooms = set()
            total_bookings_in_period = 0
            
            for booking in non_cancelled_bookings:
                if booking.get('start_time') and booking.get('room_id'):
                    try:
                        booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                        # Include bookings from the last 30 days
                        if period_start <= booking_date <= period_end:
                            occupied_rooms.add(booking['room_id'])
                            total_bookings_in_period += 1
                    except Exception as e:
                        print(f"⚠️ Error parsing booking date: {e}")
                        pass
            
            # Calculate as percentage of rooms that had at least one booking in the period
            stats['occupancy_rate'] = (len(occupied_rooms) / stats['total_rooms']) * 100
            print(f"🏨 Occupancy calculation: {len(occupied_rooms)} rooms used out of {stats['total_rooms']} total rooms in last 30 days ({total_bookings_in_period} bookings) = {stats['occupancy_rate']:.1f}%")
        else:
            print("⚠️ No rooms found for occupancy calculation")
            stats['occupancy_rate'] = 0
        
        # Calculate revenue growth (this month vs last month)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_revenue = 0
        
        for booking in non_cancelled_bookings:
            if booking.get('start_time'):
                try:
                    booking_date = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                    if last_month_start <= booking_date < current_month_start:
                        last_month_revenue += safe_float_conversion(booking.get('total_price', 0))
                except Exception:
                    pass
        
        if last_month_revenue > 0:
            stats['revenue_growth'] = ((revenue_this_month - last_month_revenue) / last_month_revenue) * 100
        else:
            stats['revenue_growth'] = 100 if revenue_this_month > 0 else 0
        
        print(f"✅ Dashboard stats calculated: {stats['total_bookings']} bookings, ${stats['total_revenue']:.2f} total revenue, {stats['occupancy_rate']:.1f}% occupancy")
        return stats
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get dashboard stats: {e}")
        return {
            'total_bookings': 0,
            'total_clients': 0,
            'total_rooms': 0,
            'available_rooms': 0,
            'confirmed_bookings': 0,
            'tentative_bookings': 0,
            'cancelled_bookings': 0,
            'total_revenue': 0,
            'revenue_this_month': 0,
            'average_booking_value': 0,
            'upcoming_bookings': 0,
            'todays_bookings': 0,
            'occupancy_rate': 0,
            'revenue_growth': 0
        }

def get_recent_bookings(limit=10):
    """Get recent bookings for dashboard with enhanced formatting"""
    try:
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name),
            client:clients(id, contact_person, company_name)
        """).order('created_at', desc=True).limit(limit).execute()
        
        if response.data:
            # Convert datetime strings for template compatibility
            bookings = convert_datetime_strings(response.data)
            
            # Enhance booking data for display
            for booking in bookings:
                # Ensure client name is available
                if booking.get('client'):
                    client = booking['client']
                    booking['client_name'] = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                    booking['client_display_name'] = booking['client_name']
                else:
                    booking['client_name'] = booking.get('client_name', 'Unknown Client')
                    booking['client_display_name'] = booking['client_name']
                
                # Ensure room name is available
                if booking.get('room'):
                    booking['room_name'] = booking['room'].get('name', 'Unknown Room')
                else:
                    booking['room_name'] = 'Unknown Room'
                
                # Format status for display
                status = booking.get('status', 'tentative')
                booking['status_display'] = status.replace('_', ' ').title()
                
                # Safe total price
                booking['total_price'] = safe_float_conversion(booking.get('total_price', 0))
                
                # Add time ago calculation
                if booking.get('created_at'):
                    from datetime import datetime, UTC
                    created_at = booking['created_at']
                    if isinstance(created_at, str):
                        try:
                            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00')).replace(tzinfo=None)
                            now = datetime.now(UTC).replace(tzinfo=None)
                            diff = now - created_dt
                            
                            if diff.days > 0:
                                if diff.days == 1:
                                    booking['time_ago'] = "1 day ago"
                                elif diff.days < 7:
                                    booking['time_ago'] = f"{diff.days} days ago"
                                elif diff.days < 30:
                                    weeks = diff.days // 7
                                    booking['time_ago'] = f"{weeks} week{'s' if weeks > 1 else ''} ago"
                                else:
                                    months = diff.days // 30
                                    booking['time_ago'] = f"{months} month{'s' if months > 1 else ''} ago"
                            else:
                                hours = diff.seconds // 3600
                                if hours > 0:
                                    booking['time_ago'] = f"{hours} hour{'s' if hours > 1 else ''} ago"
                                else:
                                    minutes = diff.seconds // 60
                                    if minutes > 0:
                                        booking['time_ago'] = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                                    else:
                                        booking['time_ago'] = "Just now"
                        except Exception:
                            booking['time_ago'] = "Recently"
                else:
                    booking['time_ago'] = "Recently"
                
                # Add booking title if missing
                if not booking.get('title'):
                    booking['title'] = f"Meeting - {booking['client_name']}"
            
            return bookings
        
        return []
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get recent bookings: {e}")
        return []

def get_upcoming_bookings(limit=10):
    """Get upcoming bookings for dashboard with enhanced formatting"""
    try:
        from datetime import datetime, UTC, timedelta
        
        # Get bookings starting from now
        now = datetime.now(UTC)
        
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name)
        """).gte('start_time', now.isoformat()).neq('status', 'cancelled').order('start_time', desc=False).limit(limit).execute()
        
        if response.data:
            # Convert datetime strings for template compatibility
            bookings = convert_datetime_strings(response.data)
            
            # Enhance booking data for display
            for booking in bookings:
                # Ensure client name is available
                if booking.get('client'):
                    client = booking['client']
                    booking['client_name'] = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                    booking['client_display_name'] = booking['client_name']
                else:
                    booking['client_name'] = booking.get('client_name', 'Unknown Client')
                    booking['client_display_name'] = booking['client_name']
                
                # Ensure room name and details are available
                if booking.get('room'):
                    room = booking['room']
                    booking['room_name'] = room.get('name', 'Unknown Room')
                    booking['room_capacity'] = room.get('capacity')
                else:
                    booking['room_name'] = 'Unknown Room'
                    booking['room_capacity'] = None
                
                # Format status for display
                status = booking.get('status', 'tentative')
                booking['status_display'] = status.replace('_', ' ').title()
                
                # Safe total price
                booking['total_price'] = safe_float_conversion(booking.get('total_price', 0))
                
                # Calculate time until booking and format display
                if booking.get('start_time'):
                    start_time = booking['start_time']
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    
                    time_diff = start_time - now.replace(tzinfo=None)
                    if time_diff.days > 0:
                        if time_diff.days == 1:
                            booking['days_until'] = "Tomorrow"
                        else:
                            booking['days_until'] = f"In {time_diff.days} days"
                    elif time_diff.seconds > 3600:
                        hours = time_diff.seconds // 3600
                        booking['days_until'] = f"In {hours} hour{'s' if hours > 1 else ''}"
                    else:
                        minutes = time_diff.seconds // 60
                        booking['days_until'] = f"In {minutes} minute{'s' if minutes > 1 else ''}"
                    
                    # Format start time for display
                    booking['start_time'] = start_time.strftime('%H:%M')
                    booking['start_date'] = start_time.strftime('%d %b')
                
                # Format end time if available
                if booking.get('end_time'):
                    end_time = booking['end_time']
                    if isinstance(end_time, str):
                        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    booking['end_time'] = end_time.strftime('%H:%M')
                
                # Add booking title if missing
                if not booking.get('title'):
                    booking['title'] = f"Meeting - {booking['client_name']}"
            
            return bookings
        
        return []
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get upcoming bookings: {e}")
        return []

def get_todays_bookings():
    """Get today's bookings for dashboard with enhanced formatting"""
    try:
        from datetime import datetime, UTC, timedelta
        
        # Get start and end of today
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name)
        """).gte('start_time', today_start.isoformat()).lt('start_time', today_end.isoformat()).neq('status', 'cancelled').order('start_time').execute()
        
        if response.data:
            # Convert datetime strings for template compatibility
            bookings = convert_datetime_strings(response.data)
            
            # Enhance booking data for display
            for booking in bookings:
                # Ensure client name is available
                if booking.get('client'):
                    client = booking['client']
                    booking['client_name'] = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                    booking['client_display_name'] = booking['client_name']
                else:
                    booking['client_name'] = booking.get('client_name', 'Unknown Client')
                    booking['client_display_name'] = booking['client_name']
                
                # Ensure room name is available
                if booking.get('room'):
                    room = booking['room']
                    booking['room_name'] = room.get('name', 'Unknown Room')
                    booking['room_capacity'] = room.get('capacity')
                else:
                    booking['room_name'] = 'Unknown Room'
                    booking['room_capacity'] = None
                
                # Format status for display
                status = booking.get('status', 'tentative')
                booking['status_display'] = status.replace('_', ' ').title()
                
                # Safe total price
                booking['total_price'] = safe_float_conversion(booking.get('total_price', 0))
                
                # Format time for display
                start_time_formatted = 'TBD'
                end_time_formatted = 'TBD'
                time_range = 'Time TBD'
                
                if booking.get('start_time'):
                    start_time = booking['start_time']
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    start_time_formatted = start_time.strftime('%H:%M')
                
                if booking.get('end_time'):
                    end_time = booking['end_time']
                    if isinstance(end_time, str):
                        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    end_time_formatted = end_time.strftime('%H:%M')
                
                # Create time range display
                if start_time_formatted != 'TBD' and end_time_formatted != 'TBD':
                    time_range = f"{start_time_formatted} - {end_time_formatted}"
                elif start_time_formatted != 'TBD':
                    time_range = f"From {start_time_formatted}"
                
                booking['start_time_formatted'] = start_time_formatted
                booking['end_time_formatted'] = end_time_formatted
                booking['time_range'] = time_range
                
                # Add booking title if missing
                if not booking.get('title'):
                    booking['title'] = f"Meeting - {booking['client_name']}"
                
                # Add status indicator for current time
                if start_time_formatted != 'TBD':
                    current_time = now.time()
                    start_time_obj = datetime.strptime(start_time_formatted, '%H:%M').time()
                    
                    if current_time < start_time_obj:
                        booking['status_indicator'] = 'upcoming'
                    elif end_time_formatted != 'TBD':
                        end_time_obj = datetime.strptime(end_time_formatted, '%H:%M').time()
                        if current_time <= end_time_obj:
                            booking['status_indicator'] = 'ongoing'
                        else:
                            booking['status_indicator'] = 'completed'
                    else:
                        booking['status_indicator'] = 'ongoing'
                else:
                    booking['status_indicator'] = 'scheduled'
            
            return bookings
        
        return []
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get today's bookings: {e}")
        return []

def get_revenue_trends():
    """Get revenue trends for dashboard charts"""
    try:
        from datetime import datetime, UTC, timedelta
        import calendar
        
        # Get last 6 months of data
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=180)  # Approximately 6 months
        
        response = supabase_admin.table('bookings').select('*').gte('start_time', start_date.isoformat()).neq('status', 'cancelled').execute()
        
        if not response.data:
            return {
                'monthly_revenue': [],
                'monthly_labels': [],
                'total_revenue': 0,
                'revenue_growth': 0
            }
        
        # Group bookings by month
        monthly_data = {}
        total_revenue = 0
        
        for booking in response.data:
            try:
                start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).replace(tzinfo=None)
                month_key = start_time.strftime('%Y-%m')
                month_name = start_time.strftime('%b %Y')
                
                revenue = safe_float_conversion(booking.get('total_price', 0))
                total_revenue += revenue
                
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        'revenue': 0,
                        'label': month_name,
                        'date': start_time
                    }
                
                monthly_data[month_key]['revenue'] += revenue
                
            except Exception as e:
                print(f"⚠️ WARNING: Error processing booking for revenue trends: {e}")
                continue
        
        # Sort by date and prepare chart data
        sorted_months = sorted(monthly_data.items(), key=lambda x: x[1]['date'])
        
        monthly_revenue = [month[1]['revenue'] for month in sorted_months]
        monthly_labels = [month[1]['label'] for month in sorted_months]
        
        # Calculate growth rate (last month vs previous month)
        revenue_growth = 0
        if len(monthly_revenue) >= 2:
            current_month = monthly_revenue[-1]
            previous_month = monthly_revenue[-2]
            if previous_month > 0:
                revenue_growth = ((current_month - previous_month) / previous_month) * 100
        
        return {
            'monthly_revenue': monthly_revenue,
            'monthly_labels': monthly_labels,
            'total_revenue': round(total_revenue, 2),
            'revenue_growth': round(revenue_growth, 1)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue trends: {e}")
        return {
            'monthly_revenue': [],
            'monthly_labels': [],
            'total_revenue': 0,
            'revenue_growth': 0
        }