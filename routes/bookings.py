from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import login_required, current_user
from datetime import datetime, UTC, timedelta, date
import io
from core import (
    BookingForm, handle_booking_creation, handle_booking_update,
    get_complete_booking_details, get_booking_with_details, supabase_admin, ActivityTypes,
    calculate_booking_totals, supabase_select, supabase_update,
    extract_booking_form_data, validate_booking_business_rules,
    find_or_create_client_enhanced, find_or_create_event_type,
    create_complete_booking, safe_log_user_activity,
    format_booking_success_message, safe_str, safe_str_lower
)
from httpx import TimeoutException
import time
from functools import wraps
import pytz
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
import tempfile
import os

bookings_bp = Blueprint('bookings', __name__)

# Helper function for safe string conversion
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
    """Display all bookings with enhanced data fetching and filtering"""
    try:
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        date_filter = request.args.get('date', 'all')
        room_filter = request.args.get('room', 'all')
        
        # Build query with filters
        query = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name, email)
        """)
        
        # Apply status filter
        if status_filter != 'all':
            query = query.eq('status', status_filter)
        
        # Apply room filter
        if room_filter != 'all' and room_filter.isdigit():
            query = query.eq('room_id', int(room_filter))
        
        # Apply date filter
        if date_filter == 'today':
            today = datetime.now().date()
            query = query.gte('start_time', today.isoformat()).lt('start_time', (today + timedelta(days=1)).isoformat())
        elif date_filter == 'week':
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=7)
            query = query.gte('start_time', week_start.isoformat()).lt('start_time', week_end.isoformat())
        elif date_filter == 'month':
            today = datetime.now().date()
            month_start = today.replace(day=1)
            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1)
            query = query.gte('start_time', month_start.isoformat()).lt('start_time', month_end.isoformat())
        
        # Execute query with ordering
        response = query.order('start_time', desc=True).execute()
        bookings_data = response.data if response.data else []
        
        # Get rooms for filter dropdown
        rooms_response = supabase_admin.table('rooms').select('id, name').order('name').execute()
        rooms = rooms_response.data if rooms_response.data else []
        
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
            f"Viewed bookings list page ({len(bookings_data)} bookings, filter: {status_filter})",
            resource_type='page'
        )
        
        return render_template('bookings/index.html', 
                             title='Bookings', 
                             bookings=bookings_data,
                             rooms=rooms,
                             current_filters={
                                 'status': status_filter,
                                 'date': date_filter,
                                 'room': room_filter
                             })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch bookings: {e}")
        flash('Error loading bookings', 'danger')
        return render_template('bookings/index.html', 
                             title='Bookings', 
                             bookings=[], 
                             rooms=[],
                             current_filters={'status': 'all', 'date': 'all', 'room': 'all'})

@bookings_bp.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def new_booking():
    """Create a new booking with enhanced validation"""
    form = BookingForm()
    
    try:
        # Get available rooms for the form
        rooms_response = supabase_admin.table('rooms').select('*').eq('status', 'available').order('name').execute()
        rooms = rooms_response.data or []
        
        if not rooms:
            flash('❌ No rooms available for booking. Please contact administrator.', 'warning')
            return redirect(url_for('bookings.bookings'))
        
        # Set form choices
        form.room_id.choices = [(room['id'], f"{room['name']} (Capacity: {room.get('capacity', 'N/A')})") for room in rooms]
        
        if request.method == 'POST':
            # Validate form data
            if not form.validate_on_submit():
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f'❌ {field}: {error}', 'danger')
                return render_template('bookings/form.html', title='New Booking', form=form, rooms=rooms)
            
            # Extract and validate form data
            booking_data = extract_booking_form_data(request.form)
            if not booking_data:
                flash('❌ Invalid booking data provided', 'danger')
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
            return redirect(url_for('bookings.bookings'))
            
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
        return redirect(url_for('bookings.bookings'))

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
                ActivityTypes.CHANGE_BOOKING_STATUS,
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

def check_pdf_dependencies():
    """Check if PDF generation dependencies are available"""
    try:
        # ReportLab should be available if installed
        from reportlab.lib.pagesizes import A4
        return True
    except ImportError as e:
        print(f"⚠️ Warning: ReportLab not available: {e}")
        return False

def create_quotation_pdf(booking, output_path, current_time, valid_until):
    """Create a professional quotation PDF using ReportLab"""
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#2E8B57')
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#1a1a1a')
    )
    
    # Title
    story.append(Paragraph("RAINBOW TOWERS CONFERENCE BOOKING", title_style))
    story.append(Paragraph("QUOTATION", styles['Heading1']))
    story.append(Spacer(1, 20))
    
    # Quotation details
    quotation_number = f"Q{booking['id']:04d}-{current_time.strftime('%Y%m')}"
    story.append(Paragraph(f"Quotation Number: <b>{quotation_number}</b>", styles['Normal']))
    story.append(Paragraph(f"Date: <b>{current_time.strftime('%d %B %Y')}</b>", styles['Normal']))
    story.append(Paragraph(f"Valid Until: <b>{valid_until.strftime('%d %B %Y')}</b>", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Client Information
    story.append(Paragraph("CLIENT INFORMATION", header_style))
    client_name = booking.get('client_name', 'Unknown Client')
    contact_person = booking.get('contact_person', 'N/A')
    story.append(Paragraph(f"Client: <b>{client_name}</b>", styles['Normal']))
    story.append(Paragraph(f"Contact Person: <b>{contact_person}</b>", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Booking Details
    story.append(Paragraph("BOOKING DETAILS", header_style))
    
    # Create booking details table
    booking_data = [
        ['Event Title:', booking.get('title', 'Conference Booking')],
        ['Room:', booking.get('room_name', 'Conference Room')],
        ['Date:', booking.get('start_time', 'TBD')[:10] if booking.get('start_time') else 'TBD'],
        ['Time:', f"{booking.get('start_time', 'TBD')[11:16] if booking.get('start_time') else 'TBD'} - {booking.get('end_time', 'TBD')[11:16] if booking.get('end_time') else 'TBD'}"],
        ['Attendees:', str(booking.get('attendees', 'TBD'))],
        ['Duration:', f"{booking.get('duration_hours', 0)} hours" if booking.get('duration_hours') else 'TBD'],
    ]
    
    booking_table = Table(booking_data, colWidths=[2*inch, 4*inch])
    booking_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
    ]))
    
    story.append(booking_table)
    story.append(Spacer(1, 20))
    
    # Pricing
    story.append(Paragraph("PRICING", header_style))
    
    pricing_data = [
        ['Item', 'Quantity', 'Rate', 'Amount'],
        ['Room Rental', '1', f"${booking.get('room_price', 0):.2f}", f"${booking.get('room_price', 0):.2f}"],
    ]
    
    # Add addons if any
    if booking.get('total_addons_price', 0) > 0:
        pricing_data.append(['Add-ons/Services', '1', f"${booking.get('total_addons_price', 0):.2f}", f"${booking.get('total_addons_price', 0):.2f}"])
    
    # Add totals
    subtotal = booking.get('subtotal', 0)
    tax_amount = booking.get('tax_amount', 0)
    total_price = booking.get('total_price', 0)
    
    pricing_data.extend([
        ['', '', 'Subtotal:', f"${subtotal:.2f}"],
        ['', '', 'Tax:', f"${tax_amount:.2f}"],
        ['', '', 'TOTAL:', f"${total_price:.2f}"],
    ])
    
    pricing_table = Table(pricing_data, colWidths=[2.5*inch, 1*inch, 1.5*inch, 1.5*inch])
    pricing_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2E8B57')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,-3), (-1,-1), colors.HexColor('#f8f9fa')),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,-1), (-1,-1), 12),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
    ]))
    
    story.append(pricing_table)
    story.append(Spacer(1, 30))
    
    # Terms and conditions
    story.append(Paragraph("TERMS & CONDITIONS", header_style))
    terms = [
        "1. This quotation is valid for 30 days from the date of issue.",
        "2. Payment is required to confirm the booking.",
        "3. Cancellation policy applies as per our standard terms.",
        "4. All prices are in USD and inclusive of applicable taxes.",
        "5. Additional services may incur extra charges."
    ]
    
    for term in terms:
        story.append(Paragraph(term, styles['Normal']))
    
    story.append(Spacer(1, 20))
    story.append(Paragraph("Thank you for choosing Rainbow Towers Conference Center!", styles['Normal']))
    
    # Build the PDF
    doc.build(story)

@bookings_bp.route('/bookings/<int:id>/quotation/download')
@login_required
def download_quotation(id):
    """Generate and download quotation PDF using ReportLab"""
    if not check_pdf_dependencies():
        flash('❌ PDF generation is not available. Please contact system administrator.', 'danger')
        return redirect(url_for('bookings.view_booking', id=id))
    
    try:
        booking = get_booking_with_details(id)
        if not booking:
            flash('❌ Booking not found', 'danger')
            return redirect(url_for('bookings.bookings'))

        # Get current time in CAT timezone
        tz = pytz.timezone('Africa/Harare')
        current_time = datetime.now(tz)
        valid_until = current_time + timedelta(days=30)

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file_path = temp_file.name
        temp_file.close()

        # Generate PDF using ReportLab
        create_quotation_pdf(booking, temp_file_path, current_time, valid_until)
        
        # Verify file was created
        if not os.path.exists(temp_file_path):
            raise Exception("PDF file was not created successfully")

        # Log activity
        safe_log_user_activity(
            ActivityTypes.GENERATE_REPORT,
            f"Generated and downloaded quotation PDF for booking #{id}",
            resource_type='booking',
            resource_id=id
        )

        # Send file with cleanup after sending
        return send_file(
            temp_file_path,
            download_name=f'Quotation-{booking["id"]}-{current_time.strftime("%Y%m%d")}.pdf',
            as_attachment=True,
            mimetype='application/pdf'
        )

    except Exception as e:
        error_msg = handle_pdf_generation_error(e)
        print(f"❌ PDF Generation Error: {error_msg}")
        flash(f'❌ {error_msg}', 'danger')
        return redirect(url_for('bookings.view_booking', id=id))
    
    finally:
        # Clean up temporary file
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as cleanup_error:
                print(f"⚠️ Warning: Failed to cleanup temp file {temp_file_path}: {cleanup_error}")

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

        # Debug: Print booking structure
        print(f"🔍 Booking type: {type(booking)}")
        print(f"🔍 Has client: {'client' in booking}")
        print(f"🔍 Client type: {type(booking.get('client'))}")
        print(f"🔍 Has room: {'room' in booking}")
        print(f"🔍 Room type: {type(booking.get('room'))}")

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

        print(f"🔍 About to render template with booking ID: {booking.get('id')}")
        
        return render_template(
            'bookings/invoice.html',
            booking=booking,
            current_date=current_date,
            due_date=due_date,
            invoice_number=f"INV-{booking['id']}-{current_date.strftime('%Y%m')}",
            title=f"Invoice - {booking.get('title', 'Booking')}"
        )

    except Exception as e:
        import traceback
        print(f"❌ ERROR: Failed to generate invoice: {e}")
        print(f"❌ Full traceback: {traceback.format_exc()}")
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
            return redirect(url_for('bookings.bookings'))

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
    """Search clients with enhanced validation and performance"""
    try:
        query = safe_str(request.args.get('q', '')).lower().strip()
        
        # Validate query length
        if len(query) < 2:
            return jsonify({'error': 'Query must be at least 2 characters long', 'results': []})
        
        # Validate query content (prevent injection)
        if not query.replace(' ', '').replace('-', '').replace('.', '').replace('@', '').isalnum():
            return jsonify({'error': 'Invalid characters in search query', 'results': []})
        
        # Limit query length
        if len(query) > 50:
            return jsonify({'error': 'Query too long', 'results': []})

        # Search in database with optimized query
        response = supabase_admin.table('clients').select('id, contact_person, company_name, email').limit(20).execute()
        if not response.data:
            return jsonify({'results': []})

        results = []
        for client in response.data:
            # Safely convert all searchable fields
            company = safe_str(client.get('company_name')).lower()
            contact = safe_str(client.get('contact_person')).lower()
            email = safe_str(client.get('email')).lower()

            # Check if query matches any field
            if (query in company or 
                query in contact or 
                query in email):
                results.append({
                    'id': client.get('id'),
                    'name': client.get('contact_person', ''),
                    'company': client.get('company_name', ''),
                    'email': client.get('email', ''),
                    'display_name': client.get('company_name') or client.get('contact_person', 'Unknown')
                })
                
                # Limit results
                if len(results) >= 10:
                    break

        return jsonify({'results': results, 'total': len(results)})

    except Exception as e:
        print(f"❌ ERROR: Failed to search clients: {e}")
        return jsonify({'error': 'Internal server error', 'results': []}), 500

@bookings_bp.route('/api/companies/search')
@login_required
def search_companies():
    """Search companies for autocomplete with enhanced validation"""
    try:
        query = safe_str(request.args.get('q', '')).strip()
        
        # Validate query
        if len(query) < 2:
            return jsonify({'error': 'Query must be at least 2 characters', 'results': []})
        
        if len(query) > 50:
            return jsonify({'error': 'Query too long', 'results': []})
        
        # Get unique company names with better query
        response = supabase_admin.table('clients').select('company_name').not_.is_('company_name', 'null').execute()
        
        if not response.data:
            return jsonify({'results': []})
        
        companies = []
        seen_companies = set()
        query_lower = safe_str_lower(query)
        
        for row in response.data:
            try:
                company_name = safe_str(row.get('company_name')).strip()
                
                # Skip empty, None values, or common invalid entries
                if (not company_name or 
                    company_name.lower() in ['none', 'null', 'n/a', 'na', 'unknown']):
                    continue
                
                # Check if matches and not already added
                if (query_lower in safe_str_lower(company_name) and 
                    company_name not in seen_companies and
                    len(company_name) >= 2):
                    
                    companies.append({
                        'name': company_name,
                        'value': company_name
                    })
                    seen_companies.add(company_name)
                    
                    # Limit results for performance
                    if len(companies) >= 10:
                        break
                        
            except Exception as e:
                print(f"⚠️ WARNING: Error processing company: {e}")
                continue
        
        return jsonify({'results': companies, 'total': len(companies)})
        
    except Exception as e:
        print(f"❌ ERROR: Failed to search companies: {e}")
        return jsonify({'error': 'Internal server error', 'results': []}), 500

# API calendar events moved to routes/api.py to avoid conflicts

@bookings_bp.route('/bookings/calendar')
@login_required
def calendar_view():
    """Display calendar view of bookings with enhanced functionality"""
    try:
        # Get timezone for date calculations
        timezone = pytz.timezone('Africa/Johannesburg')
        today = datetime.now(timezone).date()
        
        # Parse date parameters with validation
        try:
            year = int(request.args.get('year', today.year))
            month = int(request.args.get('month', today.month))
            
            # Validate date ranges
            if not (2020 <= year <= 2030):
                year = today.year
            if not (1 <= month <= 12):
                month = today.month
                
            start_date = date(year, month, 1)
            
            # Calculate end date for the month
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
                
        except (ValueError, TypeError):
            start_date = date(today.year, today.month, 1)
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1) if today.month < 12 else date(today.year, 12, 31)
        
        # Get optional filters
        room_filter = safe_str(request.args.get('room', '')).strip()
        status_filter = safe_str(request.args.get('status', '')).strip()
        
        # Build query for bookings in the month
        query = supabase_admin.table('bookings').select('''
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name)
        ''').gte('start_time', start_date.isoformat()).lte('start_time', end_date.isoformat())
        
        # Apply filters
        if room_filter:
            try:
                room_id = int(room_filter)
                query = query.eq('room_id', room_id)
            except (ValueError, TypeError):
                pass
                
        if status_filter and status_filter in ['confirmed', 'cancelled', 'pending']:
            query = query.eq('status', status_filter)
        
        response = query.execute()
        bookings = response.data if response.data else []
        
        # Process bookings for calendar display
        processed_bookings = []
        for booking in bookings:
            try:
                if not booking.get('start_time'):
                    continue
                    
                # Parse booking date from start_time
                start_time = datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00'))
                booking_date = start_time.date()
                booking['formatted_date'] = booking_date.strftime('%Y-%m-%d')
                booking['day_of_month'] = booking_date.day
                
                # Get client info safely
                client = booking.get('client', {}) or {}
                if client:
                    client_name = safe_str(client.get('contact_person', ''))
                    booking['client_name'] = client_name if client_name else 'Unknown Client'
                    booking['company_name'] = safe_str(client.get('company_name', ''))
                else:
                    booking['client_name'] = 'Unknown Client'
                    booking['company_name'] = ''
                
                # Get room info safely
                room = booking.get('room', {}) or {}
                booking['room_name'] = safe_str(room.get('name', 'Unknown Room'))
                
                processed_bookings.append(booking)
                
            except Exception as e:
                print(f"⚠️ WARNING: Error processing booking {booking.get('id', 'unknown')}: {e}")
                continue
        
        # Get available rooms for filtering
        rooms_response = supabase_admin.table('rooms').select('id, name').order('name').execute()
        available_rooms = rooms_response.data if rooms_response.data else []
        
        # Generate calendar navigation
        prev_month = start_date.replace(day=1) - timedelta(days=1)
        next_month = start_date.replace(day=28) + timedelta(days=4)
        next_month = next_month.replace(day=1)
        
        safe_log_user_activity(
            ActivityTypes.PAGE_VIEW,
            f"Viewed booking calendar for {start_date.strftime('%B %Y')}",
            resource_type='page'
        )
        
        return render_template('calendar.html', 
                             title='Booking Calendar',
                             bookings=processed_bookings,
                             current_date=start_date,
                             current_month_name=start_date.strftime('%B %Y'),
                             prev_month=prev_month,
                             next_month=next_month,
                             today=today,
                             room_filter=room_filter,
                             status_filter=status_filter,
                             available_rooms=available_rooms)
                             
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
            return redirect(url_for('bookings.bookings'))

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
        return redirect(url_for('bookings.bookings'))

def handle_pdf_generation_error(e):
    """Handle PDF generation errors gracefully"""
    error_message = str(e).lower()
    if 'reportlab' in error_message or 'import' in error_message:
        return "PDF generation failed: ReportLab library not available. Please contact system administrator."
    elif 'permission' in error_message:
        return "PDF generation failed: Permission denied when creating temporary files."
    elif 'disk' in error_message or 'space' in error_message:
        return "PDF generation failed: Not enough disk space."
    elif 'memory' in error_message:
        return "PDF generation failed: Insufficient memory available."
    else:
        return f"PDF generation failed: {str(e)}"

@bookings_bp.route('/api/bookings/<int:booking_id>/status', methods=['POST'])
@login_required
def update_booking_status_api(booking_id):
    """Update booking status via API"""
    try:
        # Validate input
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        new_status = safe_str(data.get('status', '')).strip().lower()
        if new_status not in ['confirmed', 'cancelled', 'pending']:
            return jsonify({'error': 'Invalid status. Must be confirmed, cancelled, or pending'}), 400
        
        # Get existing booking
        booking = get_booking_with_details(booking_id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        old_status = booking.get('status', 'unknown')
        
        # Update status
        update_data = {
            'status': new_status,
            'updated_at': datetime.now(UTC).isoformat()
        }
        
        response = supabase_admin.table('bookings').update(update_data).eq('id', booking_id).execute()
        
        if not response.data:
            return jsonify({'error': 'Failed to update booking status'}), 500
        
        # Log the activity
        safe_log_user_activity(
            ActivityTypes.CHANGE_BOOKING_STATUS,
            f"Changed booking status from {old_status} to {new_status}",
            resource_type='booking',
            resource_id=booking_id
        )
        
        return jsonify({
            'success': True,
            'message': f'Booking status updated to {new_status}',
            'booking_id': booking_id,
            'new_status': new_status
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to update booking status: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bookings_bp.route('/api/bookings/<int:booking_id>/quick-info')
@login_required
def get_booking_quick_info(booking_id):
    """Get quick booking information for tooltips/popups"""
    try:
        booking = get_booking_with_details(booking_id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Format quick info
        client = booking.get('client', {}) or {}
        room = booking.get('room', {}) or {}
        
        client_name = safe_str(client.get('contact_person', ''))
        if not client_name:
            client_name = 'Unknown Client'
        
        quick_info = {
            'id': booking['id'],
            'title': safe_str(booking.get('title', 'Untitled Booking')),
            'client_name': client_name,
            'company': safe_str(client.get('company_name', '')),
            'room_name': safe_str(room.get('name', 'Unknown Room')),
            'date': datetime.fromisoformat(booking['start_time'].replace('Z', '+00:00')).date().isoformat() if booking.get('start_time') else '',
            'time_slot': safe_str(booking.get('time_slot', '')),
            'status': safe_str(booking.get('status', 'unknown')),
            'attendees': booking.get('number_of_attendees', 0),
            'total_cost': booking.get('total_cost', 0)
        }
        
        return jsonify(quick_info)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get booking quick info: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bookings_bp.route('/api/room-availability')
@login_required
def check_room_availability():
    """Check room availability for a specific date and time"""
    try:
        # Get parameters
        room_id = request.args.get('room_id', type=int)
        booking_date = safe_str(request.args.get('date', '')).strip()
        time_slot = safe_str(request.args.get('time_slot', '')).strip()
        exclude_booking_id = request.args.get('exclude_booking_id', type=int)
        
        # Validate parameters
        if not all([room_id, booking_date, time_slot]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Validate date format
        try:
            parsed_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Check for existing bookings - filter by date range since start_time includes time
        start_of_day = parsed_date.isoformat()
        end_of_day = (parsed_date + timedelta(days=1)).isoformat()
        query = supabase_admin.table('bookings').select('id, title, status').eq('room_id', room_id).gte('start_time', start_of_day).lt('start_time', end_of_day).eq('time_slot', time_slot)
        
        # Exclude current booking if editing
        if exclude_booking_id:
            query = query.neq('id', exclude_booking_id)
        
        response = query.execute()
        existing_bookings = response.data if response.data else []
        
        # Filter out cancelled bookings
        active_bookings = [b for b in existing_bookings if b.get('status') != 'cancelled']
        
        is_available = len(active_bookings) == 0
        
        result = {
            'available': is_available,
            'room_id': room_id,
            'date': booking_date,
            'time_slot': time_slot,
            'existing_bookings': len(active_bookings),
            'conflicts': [{'id': b['id'], 'title': b.get('title', ''), 'status': b.get('status', '')} for b in active_bookings] if not is_available else []
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to check room availability: {e}")
        return jsonify({'error': 'Internal server error'}), 500