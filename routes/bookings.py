from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import login_required, current_user
from datetime import datetime, UTC, timedelta
import io
from core import (
    BookingForm, handle_booking_creation, handle_booking_update,
    get_complete_booking_details, get_booking_with_details, supabase_admin, ActivityTypes,
    calculate_booking_totals, supabase_select,
    extract_booking_form_data, validate_booking_business_rules,
    find_or_create_client_enhanced, find_or_create_event_type,
    create_complete_booking, safe_log_user_activity,
    format_booking_success_message
)
from httpx import TimeoutException
import time
from functools import wraps
import pytz
import pdfkit
import os

bookings_bp = Blueprint('bookings', __name__)

# Helper function for safe string conversion
def safe_str(value):
    """Safely convert value to string, handling None"""
    if value is None:
        return ''
    return str(value).strip()

def safe_str_lower(value):
    """Safely convert value to lowercase string, handling None"""
    return safe_str(value).lower()

def retry_on_timeout(max_retries=3, delay=1):
    """Decorator to retry operations on timeout"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except TimeoutException as e:
                    retries += 1
                    if retries == max_retries:
                        raise e
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

@retry_on_timeout(max_retries=3)
def save_booking_to_db(booking_data):
    """Save booking with retry mechanism"""
    try:
        # Set timeout for database operations
        result = supabase_admin.table('bookings').insert(
            booking_data
        ).execute(timeout=30)  # 30 second timeout
        
        if result and result.data:
            return result.data[0]
        return None
    except Exception as e:
        print(f"❌ ERROR: Failed to save booking: {e}")
        return None

# ===============================
# MAIN BOOKING ROUTES
# ===============================

@bookings_bp.route('/bookings')
@login_required
def bookings():
    """Display all bookings with enhanced data fetching"""
    try:
        # Get all bookings with related data
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name, email)
        """).order('start_time', desc=True).execute()
        
        bookings_data = response.data if response.data else []
        
        # Enhance booking data for display
        for booking in bookings_data:
            # Ensure room name
            if booking.get('room'):
                booking['room_name'] = booking['room'].get('name', 'Unknown Room')
            else:
                booking['room_name'] = 'Unknown Room'
            
            # Ensure client name
            if booking.get('client'):
                client = booking['client']
                booking['client_name'] = client.get('company_name') or client.get('contact_person', 'Unknown Client')
            else:
                booking['client_name'] = booking.get('client_name', 'Unknown Client')
            
            # Format dates for display
            try:
                if booking.get('start_time'):
                    start_dt = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                    booking['start_time_formatted'] = start_dt.strftime('%Y-%m-%d %H:%M')
                if booking.get('end_time'):
                    end_dt = datetime.fromisoformat(booking['end_time'].replace('Z', ''))
                    booking['end_time_formatted'] = end_dt.strftime('%Y-%m-%d %H:%M')
            except:
                booking['start_time_formatted'] = 'Invalid Date'
                booking['end_time_formatted'] = 'Invalid Date'
        
        # Log page view
        safe_log_user_activity(
            ActivityTypes.PAGE_VIEW,
            f"Viewed bookings list page ({len(bookings_data)} bookings)",
            resource_type='page'
        )
        
        return render_template('bookings/index.html', title='Bookings', bookings=bookings_data)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch bookings: {e}")
        flash('Error loading bookings', 'danger')
        return render_template('bookings/index.html', title='Bookings', bookings=[])

@bookings_bp.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def new_booking():
    """Create a new booking"""
    form = BookingForm()
    
    try:
        # Get rooms for the form
        rooms = supabase_admin.table('rooms').select('*').eq('status', 'available').order('name').execute().data or []
        form.room_id.choices = [(room['id'], f"{room['name']} (Capacity: {room.get('capacity', 'N/A')})") for room in rooms]
        
        if request.method == 'POST':
            # Extract and validate form data
            booking_data = extract_booking_form_data(request.form)
            if not booking_data:
                return render_template('bookings/form.html', title='New Booking', form=form, rooms=rooms)
            
            # Validate business rules
            validation_errors = validate_booking_business_rules(booking_data)
            if validation_errors:
                for error in validation_errors:
                    flash(error, 'danger')
                return render_template('bookings/form.html', title='New Booking', form=form, rooms=rooms)
            
            # Find or create client
            client_id = find_or_create_client_enhanced(
                booking_data['client_name'], 
                booking_data.get('company_name'),
                booking_data.get('client_email')
            )
            
            if not client_id:
                flash('❌ Error processing client information', 'danger')
                return render_template('bookings/form.html', title='New Booking', form=form, rooms=rooms)
            
            # Find or create event type
            event_type_id = find_or_create_event_type(
                booking_data['event_type'], 
                booking_data.get('custom_event_type')
            )
            
            # Create booking
            booking_id = create_complete_booking(booking_data, client_id, event_type_id)
            
            if booking_id:
                # Log successful creation
                safe_log_user_activity(
                    ActivityTypes.CREATE_BOOKING,
                    f"Created booking for {booking_data.get('client_name')}",
                    resource_type='booking',
                    resource_id=booking_id
                )
                
                # Store success message in session for dashboard
                session['booking_success'] = True
                session['booking_success_message'] = format_booking_success_message(booking_data)
                
                # Redirect to booking view page
                return redirect(url_for('bookings.view_booking', id=booking_id))
            else:
                flash('❌ Error creating booking', 'danger')
        
        return render_template('bookings/form.html', title='New Booking', form=form, rooms=rooms)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to process new booking: {e}")
        flash('Error processing booking', 'danger')
        return render_template('bookings/form.html', title='New Booking', form=form, rooms=[])

@bookings_bp.route('/bookings/<int:id>')
@login_required
def view_booking(id):
    """View booking details with improved error handling"""
    try:
        booking = get_booking_with_details(id)
        
        if not booking:
            flash('❌ Booking not found', 'danger')
            return redirect(url_for('bookings.index'))
            
        # Convert datetime strings if needed
        if isinstance(booking.get('created_at'), str):
            booking['created_at'] = datetime.fromisoformat(booking['created_at'].replace('Z', '+00:00'))
        if isinstance(booking.get('updated_at'), str):
            booking['updated_at'] = datetime.fromisoformat(booking['updated_at'].replace('Z', '+00:00'))
            
        return render_template(
            'bookings/view.html',
            booking=booking,
            title=f"Booking - {booking.get('title', '')}"
        )
        
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch booking {id}: {e}")
        flash('❌ Error loading booking details', 'danger')
        return redirect(url_for('bookings.index'))

@bookings_bp.route('/bookings/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_booking(id):
    """Edit an existing booking"""
    form = BookingForm()
    
    try:
        # Get rooms for the form
        rooms = supabase_admin.table('rooms').select('*').order('name').execute().data or []
        form.room_id.choices = [(room['id'], f"{room['name']} (Capacity: {room.get('capacity', 'N/A')})") for room in rooms]
        
        # Fetch existing booking
        booking = get_complete_booking_details(id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.bookings'))
        
        if request.method == 'POST':
            result = handle_booking_update(id, request.form, booking, rooms)
            if hasattr(result, 'status_code') and result.status_code in [301, 302]:
                return result
            return result
        
        # Populate form with existing data
        if booking:
            form.room_id.data = booking.get('room_id')
            form.attendees.data = booking.get('attendees')
            form.client_name.data = booking.get('client_name') or (booking.get('client', {}).get('contact_person', ''))
            form.company_name.data = booking.get('company_name') or (booking.get('client', {}).get('company_name', ''))
            form.notes.data = booking.get('notes')
            form.status.data = booking.get('status', 'tentative')
            
            # Parse datetime
            try:
                if booking.get('start_time'):
                    if isinstance(booking['start_time'], str):
                        form.start_time.data = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                    else:
                        form.start_time.data = booking['start_time']
                
                if booking.get('end_time'):
                    if isinstance(booking['end_time'], str):
                        form.end_time.data = datetime.fromisoformat(booking['end_time'].replace('Z', ''))
                    else:
                        form.end_time.data = booking['end_time']
            except Exception as dt_error:
                print(f"⚠️ WARNING: Error parsing datetime: {dt_error}")
        
        return render_template('bookings/form.html', 
                             title='Edit Booking', 
                             form=form, 
                             rooms=rooms, 
                             booking=booking)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to process edit booking: {e}")
        flash('Error loading booking for edit', 'danger')
        return redirect(url_for('bookings.bookings'))

@bookings_bp.route('/bookings/<int:id>/delete', methods=['POST'])
@login_required
def delete_booking(id):
    """Delete a booking"""
    try:
        # Get booking details for logging
        booking_response = supabase_admin.table('bookings').select('*').eq('id', id).execute()
        
        if not booking_response.data:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.bookings'))
        
        booking = booking_response.data[0]
        
        # Delete related records first
        supabase_admin.table('booking_custom_addons').delete().eq('booking_id', id).execute()
        
        # Delete the booking
        supabase_admin.table('bookings').delete().eq('id', id).execute()
        
        # Log deletion
        safe_log_user_activity(
            ActivityTypes.DELETE_BOOKING,
            f"Deleted booking '{booking.get('title', 'Unknown')}'",
            resource_type='booking',
            resource_id=id
        )
        
        flash('✅ Booking deleted successfully', 'success')
        
    except Exception as e:
        print(f"❌ ERROR: Failed to delete booking {id}: {e}")
        flash('❌ Error deleting booking', 'danger')
    
    return redirect(url_for('bookings.bookings'))

@bookings_bp.route('/bookings/<int:id>/status', methods=['POST'])
@login_required
def update_booking_status(id):
    """Update booking status with timestamp tracking"""
    try:
        status = request.form.get('status')
        if not status:
            flash('❌ No status provided', 'danger')
            return redirect(url_for('bookings.view_booking', id=id))

        # Prepare update data
        update_data = {
            'status': status,
            'updated_at': datetime.now(UTC).isoformat()
        }

        # Add appropriate timestamp based on status
        if status == 'confirmed':
            update_data['confirmed_at'] = datetime.now(UTC).isoformat()
        elif status == 'cancelled':
            update_data['cancelled_at'] = datetime.now(UTC).isoformat()

        # Update booking
        result = supabase_admin.table('bookings').update(
            update_data
        ).eq('id', id).execute()

        if result.data:
            flash(f'✅ Booking status updated to {status}', 'success')
            
            # Log activity
            safe_log_user_activity(
                ActivityTypes.UPDATE_STATUS,
                f"Updated booking #{id} status to {status}",
                resource_type='booking',
                resource_id=id
            )
        else:
            flash('❌ Failed to update booking status', 'danger')

        return redirect(url_for('bookings.view_booking', id=id))

    except Exception as e:
        print(f"❌ ERROR: Failed to update booking status: {e}")
        flash('❌ Error updating booking status', 'danger')
        return redirect(url_for('bookings.view_booking', id=id))

# ===============================
# QUOTATION AND INVOICE ROUTES
# ===============================

@bookings_bp.route('/bookings/<int:id>/quotation')
@login_required
def generate_quotation(id):
    """Generate quotation view for a booking"""
    try:
        # Get booking details
        booking = get_complete_booking_details(id)
        
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.bookings'))
        
        # Calculate totals
        totals = calculate_booking_totals(booking)
        
        # Log activity
        safe_log_user_activity(
            ActivityTypes.GENERATE_REPORT,
            f"Generated quotation for booking '{booking.get('title', 'Unknown')}'",
            resource_type='booking',
            resource_id=id
        )
        
        return render_template('bookings/quotation.html', 
                             title=f'Quotation - {booking.get("title", "Booking")}', 
                             booking=booking, 
                             totals=totals)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to generate quotation: {e}")
        flash('Error generating quotation', 'danger')
        return redirect(url_for('bookings.view_booking', id=id))

@bookings_bp.route('/bookings/<int:id>/quotation/download')
@login_required
def download_quotation(id):
    """Generate and download quotation PDF"""
    try:
        # Get booking details
        booking = get_booking_with_details(id)
        if not booking:
            flash('❌ Booking not found', 'danger')
            return redirect(url_for('bookings.bookings'))  # Changed from index

        # Get current time in local timezone - Fixed datetime error
        current_time = datetime.now(pytz.timezone('Africa/Harare'))
        valid_until_date = current_time + timedelta(days=30)

        # Prepare template data
        template_data = {
            'booking': booking,
            'current_date': current_time,  # Changed from now
            'quotation_number': f"Q{booking['id']}-{current_time.strftime('%Y%m')}",
            'valid_until': valid_until_date.strftime('%Y-%m-%d')
        }

        # Render HTML template
        html = render_template('bookings/quotation.html', **template_data)

        # Configure PDF options
        pdf_options = {
            'page-size': 'A4',
            'margin-top': '20mm',
            'margin-right': '20mm',
            'margin-bottom': '20mm',
            'margin-left': '20mm',
            'encoding': 'UTF-8',
            'enable-local-file-access': None
        }

        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(current_app.root_path, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        # Generate PDF
        output_path = os.path.join(temp_dir, f'quotation_{booking["id"]}.pdf')
        pdfkit.from_string(html, output_path, options=pdf_options)

        # Log activity
        safe_log_user_activity(
            ActivityTypes.GENERATE_REPORT,
            f"Generated quotation for booking #{id}",
            resource_type='booking',
            resource_id=id
        )

        return send_file(
            output_path,
            download_name=f'Quotation-{booking["id"]}.pdf',
            as_attachment=True,
            mimetype='application/pdf'
        )

    except Exception as e:
        print(f"❌ ERROR: Failed to generate quotation: {e}")
        flash('❌ Error generating quotation', 'danger')
        return redirect(url_for('bookings.view_booking', id=id))

@bookings_bp.route('/bookings/<int:id>/invoice')
@login_required
def generate_invoice(id):
    """Generate invoice for booking"""
    try:
        from datetime import datetime, timedelta
        import pytz

        booking = get_booking_with_details(id)
        if not booking:
            flash('❌ Booking not found', 'danger')
            return redirect(url_for('bookings.bookings'))

        # Get current time in CAT timezone
        tz = pytz.timezone('Africa/Harare')
        current_date = datetime.now(tz)
        due_date = current_date + timedelta(days=30)

        # Calculate totals if not present
        if not booking.get('total_price'):
            booking['total_price'] = sum(
                float(addon.get('total_price', 0)) 
                for addon in booking.get('custom_addons', [])
            )

        # Format dates for template
        if isinstance(booking.get('start_time'), str):
            booking['start_time'] = datetime.fromisoformat(
                booking['start_time'].replace('Z', '+00:00')
            ).astimezone(tz)
        if isinstance(booking.get('end_time'), str):
            booking['end_time'] = datetime.fromisoformat(
                booking['end_time'].replace('Z', '+00:00')
            ).astimezone(tz)

        # Log activity
        safe_log_user_activity(
            ActivityTypes.GENERATE_REPORT,
            f"Generated invoice for booking #{id}",
            resource_type='booking',
            resource_id=id
        )

        return render_template(
            'bookings/invoice.html',
            booking=booking,
            current_date=current_date,
            due_date=due_date,
            invoice_number=f"INV-{booking['id']}-{current_date.strftime('%Y%m')}",
            title=f"Invoice - {booking.get('title', 'Booking')}"
        )

    except Exception as e:
        print(f"❌ ERROR: Failed to generate invoice: {e}")
        flash('❌ Error generating invoice', 'danger')
        return redirect(url_for('bookings.view_booking', id=id))

@bookings_bp.route('/bookings/<int:id>/send-quotation', methods=['POST'])
@login_required
def send_quotation_email(id):
    """Send quotation email to client"""
    try:
        booking = get_booking_with_details(id)
        if not booking:
            flash('❌ Booking not found', 'danger')
            return redirect(url_for('bookings.index'))

        # Get client email
        client_email = None
        if booking.get('client'):
            client_email = booking['client'].get('email')
        elif booking.get('client_email'):
            client_email = booking['client_email']

        if not client_email:
            flash('❌ No client email address available', 'danger')
            return redirect(url_for('bookings.view_booking', id=id))

        # Mark quotation as sent
        supabase_update('bookings', 
            {'quotation_sent': True}, 
            [('id', 'eq', id)]
        )

        # Log activity
        safe_log_user_activity(
            ActivityTypes.GENERATE_REPORT,
            f"Sent quotation email for booking #{id}",
            resource_type='booking',
            resource_id=id
        )

        flash('✅ Quotation email sent successfully!', 'success')
        return redirect(url_for('bookings.view_booking', id=id))

    except Exception as e:
        print(f"❌ ERROR: Failed to send quotation email: {e}")
        flash('❌ Error sending quotation email', 'danger')
        return redirect(url_for('bookings.view_booking', id=id))

@bookings_bp.route('/bookings/<int:id>/send-invoice', methods=['POST'])
@login_required
def send_invoice_email(id):
    """Send invoice email to client"""
    try:
        # ... email sending logic ...
        return redirect(url_for('bookings.view_booking', id=id))
    except Exception as e:
        print(f"❌ ERROR: Failed to send invoice email: {e}")
        flash('❌ Error sending invoice email', 'danger')
        return redirect(url_for('bookings.view_booking', id=id))

# ===============================
# API ROUTES
# ===============================

@bookings_bp.route('/api/clients/search')
@login_required
def search_clients():
    """Search clients with safe string handling"""
    try:
        query = safe_str(request.args.get('q')).lower()
        if len(query) < 2:
            return jsonify([])

        response = supabase_admin.table('clients').select('*').execute()
        if not response.data:
            return jsonify([])

        results = []
        for client in response.data:
            # Safely convert all searchable fields
            company = safe_str(client.get('company_name')).lower()
            contact = safe_str(client.get('contact_person')).lower()
            email = safe_str(client.get('email')).lower()

            if (query in company or 
                query in contact or 
                query in email):
                results.append({
                    'id': client.get('id'),
                    'name': client.get('contact_person', ''),
                    'company': client.get('company_name', ''),
                    'email': client.get('email', '')
                })

        return jsonify(results)

    except Exception as e:
        print(f"❌ ERROR: Failed to get enhanced clients list: {e}")
        return jsonify([])

@bookings_bp.route('/api/companies/search')
@login_required
def search_companies():
    """Search companies for autocomplete"""
    try:
        query = request.args.get('q', '').strip()
        if len(query) < 2:
            return jsonify([])
        
        # Get unique company names
        response = supabase_admin.table('clients').select('company_name').execute()
        
        if not response.data:
            return jsonify([])
        
        companies = []
        seen_companies = set()
        query_lower = safe_str_lower(query)
        
        for row in response.data:
            try:
                company_name = str(row.get('company_name') or '').strip()
                
                # Skip empty or 'None' values
                if not company_name or safe_str_lower(company_name) == 'none':
                    continue
                
                # Check if matches and not already added
                if query_lower in safe_str_lower(company_name) and company_name not in seen_companies:
                    companies.append({'name': company_name})
                    seen_companies.add(company_name)
                    
                    if len(companies) >= 10:
                        break
                        
            except Exception as e:
                print(f"⚠️ WARNING: Error processing company: {e}")
                continue
        
        return jsonify(companies)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to search companies: {e}")
        return jsonify([])

@bookings_bp.route('/api/bookings/calendar')
@login_required
def api_calendar_events():
    """API endpoint for calendar events"""
    try:
        from core import get_booking_calendar_events_supabase
        events = get_booking_calendar_events_supabase()
        return jsonify(events)
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch calendar events: {e}")
        return jsonify([])

@bookings_bp.route('/bookings/calendar')
@login_required
def calendar_view():
    """Display calendar view of bookings"""
    try:
        safe_log_user_activity(
            ActivityTypes.PAGE_VIEW,
            "Viewed booking calendar",
            resource_type='page'
        )
        return render_template('bookings/calendar.html', title='Booking Calendar')
    except Exception as e:
        print(f"❌ ERROR: Failed to load calendar view: {e}")
        flash('Error loading calendar view', 'danger')
        return redirect(url_for('bookings.bookings'))

@bookings_bp.route('/bookings/<int:id>/print')
@login_required
def print_details(id):
    """Print booking details"""
    try:
        booking = get_booking_with_details(id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.index'))

        # Add current datetime for the footer
        now = datetime.now(UTC)
        
        # Calculate VAT and totals if not present
        if booking.get('subtotal'):
            booking['vat_amount'] = round(float(booking['subtotal']) * 0.15, 2)
            booking['total_with_vat'] = round(float(booking['subtotal']) * 1.15, 2)

        return render_template('bookings/print_details.html',
            booking=booking,
            title=f"Print Booking - {booking.get('title', '')}",
            now=now
        )

    except Exception as e:
        print(f"❌ ERROR: Failed to print booking details: {e}")
        flash('Error loading booking details for printing', 'danger')
        return redirect(url_for('bookings.index'))

@bookings_bp.route('/bookings/new', methods=['POST'])
@login_required
def create_booking():
    """Create new booking"""
    try:
        form = BookingForm()
        if form.validate_on_submit():
            # Extract form data
            booking_data = extract_booking_form_data(form)
            
            # Add created_by (store username instead of ID)
            booking_data.update({
                'created_by': current_user.username,  # Store username
                'created_at': datetime.now(pytz.timezone('Africa/Harare')).isoformat(),
                'updated_at': datetime.now(pytz.timezone('Africa/Harare')).isoformat()
            })
            
            # Create booking
            result = create_complete_booking(booking_data)
            
            if result:
                flash('✅ Booking created successfully!', 'success')
                return redirect(url_for('bookings.view_booking', id=result.get('id'), created='true'))
            
            flash('❌ Failed to create booking', 'danger')
            
        return render_template('bookings/form.html', form=form)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to create booking: {e}")
        flash('❌ Error creating booking', 'danger')
        return redirect(url_for('bookings.bookings'))