from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from utils.decorators import activity_logged
from utils.logging import log_user_activity
from core import (get_clients_with_booking_counts, get_client_by_id_from_db, get_client_bookings_from_db, 
                  update_client_in_db, delete_client_from_db, create_client_in_db, ClientForm, 
                  ActivityTypes, supabase_admin, convert_datetime_strings)
from datetime import datetime, UTC, timedelta, timezone
import pytz  # You may need to install this: pip install pytz
import io
import csv
from collections import defaultdict

clients_bp = Blueprint('clients', __name__)

# ===============================
# CLIENT LISTING AND DIRECTORY
# ===============================

@clients_bp.route('/clients')
@login_required
@activity_logged(ActivityTypes.PAGE_VIEW, "Viewed client directory")
def clients():
    """Enhanced client directory with search, filtering, and statistics"""
    try:
        print("🔍 DEBUG: Loading client directory")
        
        # Get query parameters
        search_query = request.args.get('search', '').strip()
        sort_by = request.args.get('sort', 'company_name')
        order = request.args.get('order', 'asc')
        filter_by = request.args.get('filter', 'all')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        
        # Get clients with enhanced data
        clients_data = get_enhanced_clients_list(search_query, sort_by, order, filter_by)
        
        # Calculate pagination
        total_clients = len(clients_data)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_clients = clients_data[start_idx:end_idx]
        
        # Calculate pagination info
        total_pages = (total_clients + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        # Get directory statistics
        directory_stats = get_client_directory_stats(clients_data)
        
        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total_clients,
            'pages': total_pages,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_num': page - 1 if has_prev else None,
            'next_num': page + 1 if has_next else None
        }
        
        print(f"✅ DEBUG: Client directory loaded - {total_clients} clients found")
        
        return render_template('clients/index.html', 
                             title='Client Directory',
                             clients=paginated_clients,
                             pagination=pagination_info,
                             directory_stats=directory_stats,
                             search_query=search_query,
                             sort_by=sort_by,
                             order=order,
                             filter_by=filter_by)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load client directory: {e}")
        import traceback
        traceback.print_exc()
        
        flash('⚠️ Error loading client directory. Please try again.', 'warning')
        return render_template('clients/index.html', 
                             title='Client Directory',
                             clients=[],
                             pagination={'page': 1, 'pages': 1, 'total': 0, 'has_prev': False, 'has_next': False},
                             directory_stats=get_empty_directory_stats(),
                             search_query='',
                             sort_by='company_name',
                             order='asc',
                             filter_by='all',
                             error="Failed to load client data")

@clients_bp.route('/clients/new', methods=['GET', 'POST'])
@login_required
def new_client():
    """Create a new client with comprehensive form handling"""
    form = ClientForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                print("🔍 DEBUG: Creating new client")
                
                # Prepare client data
                client_data = {
                    'company_name': form.company_name.data.strip() if form.company_name.data else None,
                    'contact_person': form.contact_person.data.strip(),
                    'email': form.email.data.strip().lower(),
                    'phone': form.phone.data.strip() if form.phone.data else None,
                    'address': form.address.data.strip() if form.address.data else None,
                    'notes': form.notes.data.strip() if form.notes.data else None,
                    'created_at': datetime.now(UTC).isoformat(),
                    'created_by': current_user.id if hasattr(current_user, 'id') else None
                }
                
                # Check for duplicate email
                existing_client = check_duplicate_client_email(client_data['email'])
                if existing_client:
                    flash('❌ A client with this email already exists.', 'danger')
                    return render_template('clients/form.html', title='New Client', form=form)
                
                # Create client
                result = create_client_in_db(client_data)
                
                if result:
                    # Log activity
                    try:
                        log_user_activity(
                            ActivityTypes.CREATE_CLIENT,
                            f"Created new client: {client_data['contact_person']} ({client_data.get('company_name', 'No company')})",
                            resource_type='client',
                            resource_id=result['id'],
                            metadata={
                                'contact_person': client_data['contact_person'],
                                'company_name': client_data.get('company_name'),
                                'email': client_data['email']
                            }
                        )
                    except Exception as log_error:
                        print(f"⚠️ WARNING: Failed to log activity: {log_error}")
                    
                    flash(f'✅ Client "{client_data["contact_person"]}" created successfully!', 'success')
                    return redirect(url_for('clients.view_client', id=result['id']))
                else:
                    flash('❌ Error creating client. Please try again.', 'danger')
                    
            except Exception as e:
                print(f"❌ ERROR: Failed to create client: {e}")
                flash('❌ Unexpected error creating client. Please try again.', 'danger')
        else:
            flash('❌ Please correct the errors below.', 'danger')
    
    return render_template('clients/form.html', title='New Client', form=form)

# ===============================
# CLIENT DETAILS AND MANAGEMENT
# ===============================

@clients_bp.route('/clients/<int:id>')
@login_required
def view_client(id):
    """Enhanced client details view with comprehensive analytics"""
    try:
        print(f"🔍 DEBUG: Loading client details for ID {id}")
        
        # Get client data
        client = get_client_by_id_from_db(id)
        if not client:
            flash('❌ Client not found.', 'danger')
            return redirect(url_for('clients.clients'))
        
        # Get client bookings with detailed information
        bookings = get_enhanced_client_bookings(id)
        
        # Calculate comprehensive client statistics
        client_stats = calculate_client_statistics(client, bookings)
        
        # Get client activity timeline
        activity_timeline = get_client_activity_timeline(id)
        
        # Get related clients (same company or similar)
        related_clients = get_related_clients(client)
        
        # Log view activity
        try:
            log_user_activity(
                ActivityTypes.VIEW_CLIENT,
                f"Viewed client details: {client.get('contact_person', 'Unknown')}",
                resource_type='client',
                resource_id=id,
                metadata={
                    'client_name': client.get('contact_person'),
                    'company_name': client.get('company_name'),
                    'total_bookings': len(bookings)
                }
            )
        except Exception as log_error:
            print(f"⚠️ WARNING: Failed to log activity: {log_error}")
        
        print(f"✅ DEBUG: Client details loaded - {len(bookings)} bookings found")
        
        return render_template('clients/view.html', 
                             title=f"Client: {client.get('contact_person', 'Unknown')}",
                             client=client,
                             bookings=bookings,
                             client_stats=client_stats,
                             activity_timeline=activity_timeline,
                             related_clients=related_clients)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load client details: {e}")
        import traceback
        traceback.print_exc()
        
        flash('❌ Error loading client details. Please try again.', 'danger')
        return redirect(url_for('clients.clients'))

@clients_bp.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(id):
    """Edit client details"""
    try:
        # Get client data
        response = supabase_admin.table('clients').select('*').eq('id', id).execute()
        if not response.data:
            flash('❌ Client not found', 'danger')
            return redirect(url_for('clients.clients'))  # Note: changed from index to clients
            
        client = response.data[0]
        
        # Convert created_at string to datetime using UTC timezone
        if client.get('created_at'):
            try:
                client['created_at'] = datetime.fromisoformat(
                    client['created_at'].replace('Z', '+00:00')
                ).replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError) as e:
                print(f"⚠️ WARNING: Date conversion error: {e}")
                client['created_at'] = None
                
        form = ClientForm()
        
        if request.method == 'GET':
            # Pre-fill form
            form.company_name.data = client.get('company_name')
            form.contact_person.data = client.get('contact_person')
            form.email.data = client.get('email')
            form.phone.data = client.get('phone')
            form.address.data = client.get('address')
            form.notes.data = client.get('notes')
        
        if form.validate_on_submit():
            # Update client data
            update_data = {
                'company_name': form.company_name.data,
                'contact_person': form.contact_person.data,
                'email': form.email.data,
                'phone': form.phone.data,
                'address': form.address.data,
                'notes': form.notes.data,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = supabase_admin.table('clients').update(
                update_data
            ).eq('id', id).execute()
            
            if result.data:
                flash('✅ Client updated successfully', 'success')
                return redirect(url_for('clients.view_client', id=id))
            
            flash('❌ Failed to update client', 'danger')
        
        return render_template(
            'clients/form.html',
            form=form,
            client=client,
            title='Edit Client'
        )
            
    except Exception as e:
        print(f"❌ ERROR: Failed to load client for editing: {e}")
        flash('❌ Error loading client details', 'danger')
        return redirect(url_for('clients.clients'))  # Note: changed from index to clients

@clients_bp.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def delete_client(id):
    """Delete client with comprehensive validation and logging"""
    try:
        print(f"🔍 DEBUG: Attempting to delete client ID {id}")
        
        # Get client data for logging
        client = get_client_by_id_from_db(id)
        if not client:
            flash('❌ Client not found.', 'danger')
            return redirect(url_for('clients.clients'))
        
        # Check if client has bookings
        bookings = get_client_bookings_from_db(id)
        if bookings:
            flash(f'❌ Cannot delete client "{client.get("contact_person", "Unknown")}" because they have {len(bookings)} booking(s). Please cancel or reassign the bookings first.', 'danger')
            return redirect(url_for('clients.view_client', id=id))
        
        # Attempt deletion
        success, message = delete_client_from_db(id)
        
        if success:
            # Log successful deletion
            try:
                log_user_activity(
                    ActivityTypes.DELETE_CLIENT,
                    f"Deleted client: {client.get('contact_person', 'Unknown')} ({client.get('company_name', 'No company')})",
                    resource_type='client',
                    resource_id=id,
                    metadata={
                        'contact_person': client.get('contact_person'),
                        'company_name': client.get('company_name'),
                        'email': client.get('email')
                    }
                )
            except Exception as log_error:
                print(f"⚠️ WARNING: Failed to log activity: {log_error}")
            
            flash(f'✅ Client "{client.get("contact_person", "Unknown")}" deleted successfully.', 'success')
        else:
            flash(f'❌ {message}', 'danger')
            return redirect(url_for('clients.view_client', id=id))
        
    except Exception as e:
        print(f"❌ ERROR: Failed to delete client: {e}")
        flash('❌ Unexpected error deleting client. Please try again.', 'danger')
        return redirect(url_for('clients.view_client', id=id))
    
    return redirect(url_for('clients.clients'))

# ===============================
# CLIENT ANALYTICS AND REPORTS
# ===============================

@clients_bp.route('/clients/<int:id>/analytics')
@login_required
def client_analytics(id):
    """Detailed client analytics and performance dashboard"""
    try:
        print(f"🔍 DEBUG: Loading client analytics for ID {id}")
        
        # Get client data
        client = get_client_by_id_from_db(id)
        if not client:
            flash('❌ Client not found.', 'danger')
            return redirect(url_for('clients.clients'))
        
        # Get comprehensive analytics
        analytics_data = get_comprehensive_client_analytics(id)
        
        # Get booking trends
        booking_trends = get_client_booking_trends(id)
        
        # Get revenue trends
        revenue_trends = get_client_revenue_trends(id)
        
        # Get seasonal patterns
        seasonal_patterns = get_client_seasonal_patterns(id)
        
        # Log analytics view
        try:
            log_user_activity(
                ActivityTypes.GENERATE_REPORT,
                f"Viewed client analytics: {client.get('contact_person', 'Unknown')}",
                resource_type='client_analytics',
                resource_id=id
            )
        except Exception as log_error:
            print(f"⚠️ WARNING: Failed to log activity: {log_error}")
        
        return render_template('clients/analytics.html',
                             title=f"Analytics: {client.get('contact_person', 'Unknown')}",
                             client=client,
                             analytics=analytics_data,
                             booking_trends=booking_trends,
                             revenue_trends=revenue_trends,
                             seasonal_patterns=seasonal_patterns)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load client analytics: {e}")
        flash('❌ Error loading client analytics. Please try again.', 'danger')
        return redirect(url_for('clients.view_client', id=id))

@clients_bp.route('/clients/export')
@login_required
def export_clients():
    """Export client list with comprehensive data"""
    try:
        print("🔍 DEBUG: Exporting client data")
        
        # Get export parameters
        format_type = request.args.get('format', 'csv')
        include_bookings = request.args.get('include_bookings', 'false').lower() == 'true'
        
        # Get all clients with enhanced data
        clients_data = get_enhanced_clients_list()
        
        if format_type == 'csv':
            return export_clients_csv(clients_data, include_bookings)
        else:
            flash('❌ Unsupported export format.', 'danger')
            return redirect(url_for('clients.clients'))
        
    except Exception as e:
        print(f"❌ ERROR: Failed to export clients: {e}")
        flash('❌ Error exporting client data. Please try again.', 'danger')
        return redirect(url_for('clients.clients'))

# ===============================
# HELPER FUNCTIONS - DATA RETRIEVAL
# ===============================

def get_enhanced_clients_list(search_query='', sort_by='company_name', order='asc', filter_by='all'):
    """Get enhanced client list with search, sorting, and filtering"""
    try:
        # Get base client data with booking counts
        clients_data = get_clients_with_booking_counts()
        
        if not clients_data:
            return []
        
        # Apply search filter
        if search_query:
            filtered_clients = []
            search_lower = search_query.lower()
            
            for client in clients_data:
                # Search in multiple fields
                searchable_text = ' '.join([
                    str(client.get('contact_person', '')).lower(),
                    str(client.get('company_name', '')).lower(),
                    str(client.get('email', '')).lower(),
                    str(client.get('phone', '')).lower()
                ])
                
                if search_lower in searchable_text:
                    filtered_clients.append(client)
            
            clients_data = filtered_clients
        
        # Apply additional filters
        if filter_by != 'all':
            clients_data = apply_client_filters(clients_data, filter_by)
        
        # Enhance with additional data
        for client in clients_data:
            enhance_client_data(client)
        
        # Apply sorting
        clients_data = sort_clients_data(clients_data, sort_by, order)
        
        return clients_data
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get enhanced clients list: {e}")
        return []

def apply_client_filters(clients_data, filter_by):
    """Apply specific filters to client data"""
    try:
        if filter_by == 'active':
            # Clients with bookings in the last 6 months
            six_months_ago = datetime.now(UTC) - timedelta(days=180)
            return [c for c in clients_data if has_recent_activity(c, six_months_ago)]
        
        elif filter_by == 'recent':
            # Clients created in the last 30 days
            thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
            return [c for c in clients_data if is_recent_client(c, thirty_days_ago)]
        
        elif filter_by == 'high_value':
            # Clients with high booking counts or revenue
            return [c for c in clients_data if c.get('booking_count', 0) >= 5]
        
        else:
            return clients_data
            
    except Exception as e:
        print(f"❌ ERROR: Failed to apply filters: {e}")
        return clients_data

def enhance_client_data(client):
    """Add enhanced data to client record"""
    try:
        client_id = client.get('id')
        if not client_id:
            return client
        
        # Get last booking date
        try:
            last_booking_response = supabase_admin.table('bookings').select(
                'start_time'
            ).eq('client_id', client_id).order('start_time', desc=True).limit(1).execute()
            
            if last_booking_response.data:
                last_booking_date = datetime.fromisoformat(
                    last_booking_response.data[0]['start_time'].replace('Z', '')
                ).date()
                client['last_booking_date'] = last_booking_date
                
                # Calculate days since last booking
                days_since = (datetime.now(UTC).date() - last_booking_date).days
                client['days_since_last_booking'] = days_since
            else:
                client['last_booking_date'] = None
                client['days_since_last_booking'] = None
        except Exception as e:
            print(f"⚠️ WARNING: Failed to get last booking date for client {client_id}: {e}")
            client['last_booking_date'] = None
            client['days_since_last_booking'] = None
        
        # Calculate total revenue
        try:
            revenue_response = supabase_admin.table('bookings').select(
                'total_price'
            ).eq('client_id', client_id).eq('status', 'confirmed').execute()
            
            total_revenue = sum(
                float(booking.get('total_price', 0)) 
                for booking in revenue_response.data if revenue_response.data
            )
            client['total_revenue'] = round(total_revenue, 2)
        except Exception as e:
            print(f"⚠️ WARNING: Failed to get total revenue for client {client_id}: {e}")
            client['total_revenue'] = 0
        
        # Add display helpers
        client['display_name'] = client.get('company_name') or client.get('contact_person', 'Unknown Client')
        client['primary_contact'] = client.get('contact_person', 'Unknown')
        
        return client
        
    except Exception as e:
        print(f"❌ ERROR: Failed to enhance client data: {e}")
        return client

def sort_clients_data(clients_data, sort_by, order):
    """Sort client data by specified criteria"""
    try:
        reverse_order = (order == 'desc')
        
        if sort_by == 'company_name':
            clients_data.sort(key=lambda x: (x.get('company_name') or '').lower(), reverse=reverse_order)
        elif sort_by == 'contact_person':
            clients_data.sort(key=lambda x: (x.get('contact_person') or '').lower(), reverse=reverse_order)
        elif sort_by == 'booking_count':
            clients_data.sort(key=lambda x: x.get('booking_count', 0), reverse=reverse_order)
        elif sort_by == 'total_revenue':
            clients_data.sort(key=lambda x: x.get('total_revenue', 0), reverse=reverse_order)
        elif sort_by == 'last_booking':
            clients_data.sort(key=lambda x: x.get('last_booking_date') or datetime.min.date(), reverse=reverse_order)
        elif sort_by == 'created_at':
            clients_data.sort(key=lambda x: x.get('created_at') or '', reverse=reverse_order)
        
        return clients_data
        
    except Exception as e:
        print(f"❌ ERROR: Failed to sort clients data: {e}")
        return clients_data

def get_client_directory_stats(clients_data):
    """Calculate directory-wide statistics"""
    try:
        total_clients = len(clients_data)
        
        if total_clients == 0:
            return get_empty_directory_stats()
        
        # Calculate statistics
        total_bookings = sum(client.get('booking_count', 0) for client in clients_data)
        total_revenue = sum(client.get('total_revenue', 0) for client in clients_data)
        
        # Active clients (with bookings in last 6 months)
        six_months_ago = datetime.now(UTC) - timedelta(days=180)
        active_clients = len([
            c for c in clients_data 
            if c.get('last_booking_date') and 
            c['last_booking_date'] >= six_months_ago.date()
        ])
        
        # New clients (created in last 30 days)
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        new_clients = len([
            c for c in clients_data 
            if c.get('created_at') and 
            datetime.fromisoformat(c['created_at'].replace('Z', '')) >= thirty_days_ago
        ])
        
        # Top performer
        top_client = max(clients_data, key=lambda x: x.get('total_revenue', 0)) if clients_data else None
        
        return {
            'total_clients': total_clients,
            'active_clients': active_clients,
            'new_clients': new_clients,
            'total_bookings': total_bookings,
            'total_revenue': round(total_revenue, 2),
            'average_revenue_per_client': round(total_revenue / total_clients, 2),
            'average_bookings_per_client': round(total_bookings / total_clients, 1),
            'top_client': top_client
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate directory stats: {e}")
        return get_empty_directory_stats()

def get_empty_directory_stats():
    """Return empty directory stats for error cases"""
    return {
        'total_clients': 0,
        'active_clients': 0,
        'new_clients': 0,
        'total_bookings': 0,
        'total_revenue': 0,
        'average_revenue_per_client': 0,
        'average_bookings_per_client': 0,
        'top_client': None
    }

def get_enhanced_client_bookings(client_id):
    """Get enhanced booking data for a specific client"""
    try:
        # Get bookings with room and additional details
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            event_type:event_types(id, name)
        """).eq('client_id', client_id).order('start_time', desc=True).execute()
        
        bookings = response.data if response.data else []
        
        # Convert datetime strings and enhance data
        try:
            bookings = convert_datetime_strings(bookings)
        except Exception as e:
            print(f"⚠️ WARNING: Failed to convert datetime strings: {e}")
        
        for booking in bookings:
            # Add calculated fields
            try:
                if booking.get('start_time') and booking.get('end_time'):
                    duration = booking['end_time'] - booking['start_time']
                    booking['duration_hours'] = round(duration.total_seconds() / 3600, 1)
            except:
                booking['duration_hours'] = 0
            
            # Add status badge info
            booking['status_badge_class'] = get_status_badge_class(booking.get('status', 'tentative'))
            
            # Calculate cost per attendee
            try:
                if booking.get('attendees', 0) > 0 and booking.get('total_price', 0) > 0:
                    booking['cost_per_attendee'] = round(
                        float(booking['total_price']) / booking['attendees'], 2
                    )
                else:
                    booking['cost_per_attendee'] = 0
            except:
                booking['cost_per_attendee'] = 0
        
        return bookings
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get enhanced client bookings: {e}")
        return []

def calculate_client_statistics(client, bookings):
    """Calculate comprehensive client statistics"""
    try:
        if not bookings:
            return get_empty_client_stats()
        
        # Basic counts
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.get('status') == 'confirmed'])
        tentative_bookings = len([b for b in bookings if b.get('status') == 'tentative'])
        cancelled_bookings = len([b for b in bookings if b.get('status') == 'cancelled'])
        
        # Financial metrics
        total_revenue = sum(
            float(b.get('total_price', 0)) 
            for b in bookings 
            if b.get('status') == 'confirmed'
        )
        
        average_booking_value = total_revenue / max(confirmed_bookings, 1)
        
        # Attendance metrics
        total_attendees = sum(int(b.get('attendees', 0)) for b in bookings if b.get('status') != 'cancelled')
        average_attendees = total_attendees / max(total_bookings - cancelled_bookings, 1)
        
        # Time-based metrics
        booking_dates = []
        for b in bookings:
            try:
                if b.get('start_time') and b.get('status') != 'cancelled':
                    if hasattr(b['start_time'], 'date'):
                        booking_dates.append(b['start_time'].date())
                    else:
                        # Handle string dates
                        date_obj = datetime.fromisoformat(str(b['start_time']).replace('Z', '')).date()
                        booking_dates.append(date_obj)
            except:
                continue
        
        if booking_dates:
            first_booking = min(booking_dates)
            last_booking = max(booking_dates)
            client_lifetime_days = (last_booking - first_booking).days
            
            # Calculate booking frequency
            if client_lifetime_days > 0:
                booking_frequency_days = client_lifetime_days / max(len(booking_dates) - 1, 1)
            else:
                booking_frequency_days = 0
        else:
            first_booking = None
            last_booking = None
            client_lifetime_days = 0
            booking_frequency_days = 0
        
        # Room preferences
        room_usage = defaultdict(int)
        for booking in bookings:
            if booking.get('room') and booking.get('status') != 'cancelled':
                room_name = booking['room'].get('name', 'Unknown Room')
                room_usage[room_name] += 1
        
        preferred_room = max(room_usage.items(), key=lambda x: x[1]) if room_usage else None
        
        # Conversion rate
        conversion_rate = (confirmed_bookings / max(total_bookings, 1)) * 100
        
        # Client value tier
        if total_revenue >= 10000:
            value_tier = 'Premium'
        elif total_revenue >= 5000:
            value_tier = 'Gold'
        elif total_revenue >= 1000:
            value_tier = 'Silver'
        else:
            value_tier = 'Standard'
        
        return {
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed_bookings,
            'tentative_bookings': tentative_bookings,
            'cancelled_bookings': cancelled_bookings,
            'total_revenue': round(total_revenue, 2),
            'average_booking_value': round(average_booking_value, 2),
            'total_attendees': total_attendees,
            'average_attendees': round(average_attendees, 1),
            'first_booking_date': first_booking,
            'last_booking_date': last_booking,
            'client_lifetime_days': client_lifetime_days,
            'booking_frequency_days': round(booking_frequency_days, 1),
            'preferred_room': preferred_room,
            'conversion_rate': round(conversion_rate, 1),
            'value_tier': value_tier,
            'room_usage': dict(room_usage)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate client statistics: {e}")
        return get_empty_client_stats()

def get_empty_client_stats():
    """Return empty client stats for error cases"""
    return {
        'total_bookings': 0,
        'confirmed_bookings': 0,
        'tentative_bookings': 0,
        'cancelled_bookings': 0,
        'total_revenue': 0,
        'average_booking_value': 0,
        'total_attendees': 0,
        'average_attendees': 0,
        'first_booking_date': None,
        'last_booking_date': None,
        'client_lifetime_days': 0,
        'booking_frequency_days': 0,
        'preferred_room': None,
        'conversion_rate': 0,
        'value_tier': 'Standard',
        'room_usage': {}
    }

def get_client_activity_timeline(client_id, limit=10):
    """Get client activity timeline"""
    try:
        # Get recent bookings for timeline
        response = supabase_admin.table('bookings').select("""
            id, title, status, start_time, created_at, total_price,
            room:rooms(name)
        """).eq('client_id', client_id).order('created_at', desc=True).limit(limit).execute()
        
        bookings = response.data if response.data else []
        
        try:
            bookings = convert_datetime_strings(bookings)
        except Exception as e:
            print(f"⚠️ WARNING: Failed to convert datetime strings in timeline: {e}")
        
        # Format timeline entries
        timeline = []
        for booking in bookings:
            timeline.append({
                'type': 'booking',
                'date': booking.get('created_at'),
                'title': f"Booked: {booking.get('title', 'Unknown Event')}",
                'description': f"Room: {booking.get('room', {}).get('name', 'Unknown')} | Status: {booking.get('status', 'Unknown')}",
                'status': booking.get('status'),
                'amount': booking.get('total_price'),
                'booking_id': booking.get('id')
            })
        
        return timeline
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get client activity timeline: {e}")
        return []

def get_related_clients(client):
    """Get clients related to the current client (same company, etc.)"""
    try:
        related = []
        
        # If client has a company, find other clients from same company
        if client.get('company_name'):
            response = supabase_admin.table('clients').select(
                'id, contact_person, email, phone'
            ).eq('company_name', client['company_name']).neq('id', client['id']).limit(5).execute()
            
            if response.data:
                for related_client in response.data:
                    related.append({
                        'id': related_client['id'],
                        'name': related_client.get('contact_person', 'Unknown'),
                        'email': related_client.get('email'),
                        'relationship': 'Same Company'
                    })
        
        return related
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get related clients: {e}")
        return []

# ===============================
# UTILITY FUNCTIONS
# ===============================

def check_duplicate_client_email(email):
    """Check if email already exists"""
    try:
        response = supabase_admin.table('clients').select('id, contact_person').eq('email', email.lower()).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"⚠️ WARNING: Failed to check duplicate email: {e}")
        return None

def track_client_changes(old_client, new_client):
    """Track what fields were changed"""
    changes = []
    
    fields_to_track = ['company_name', 'contact_person', 'email', 'phone', 'address', 'notes']
    
    for field in fields_to_track:
        old_value = old_client.get(field, '')
        new_value = new_client.get(field, '')
        
        if old_value != new_value:
            changes.append(field.replace('_', ' ').title())
    
    return changes

def has_recent_activity(client, since_date):
    """Check if client has recent activity"""
    last_booking_date = client.get('last_booking_date')
    if not last_booking_date:
        return False
    
    try:
        if isinstance(last_booking_date, str):
            last_booking_date = datetime.fromisoformat(last_booking_date).date()
        
        return last_booking_date >= since_date.date()
    except Exception as e:
        print(f"⚠️ WARNING: Failed to check recent activity: {e}")
        return False

def is_recent_client(client, since_date):
    """Check if client was created recently"""
    created_at = client.get('created_at')
    if not created_at:
        return False
    
    try:
        created_date = datetime.fromisoformat(created_at.replace('Z', ''))
        return created_date >= since_date
    except Exception as e:
        print(f"⚠️ WARNING: Failed to check if client is recent: {e}")
        return False

def get_status_badge_class(status):
    """Get Bootstrap badge class for status"""
    status_classes = {
        'confirmed': 'badge-success',
        'tentative': 'badge-warning',
        'cancelled': 'badge-danger'
    }
    return status_classes.get(status, 'badge-secondary')

# ===============================
# ANALYTICS FUNCTIONS (IMPROVED)
# ===============================

def get_comprehensive_client_analytics(client_id):
    """Get comprehensive analytics for a specific client"""
    try:
        # Get client bookings for analysis
        bookings = get_enhanced_client_bookings(client_id)
        
        if not bookings:
            return {
                'overview': 'No bookings found for analytics',
                'trends': {},
                'patterns': {},
                'recommendations': ['Start by creating your first booking!']
            }
        
        # Basic analytics
        total_revenue = sum(float(b.get('total_price', 0)) for b in bookings if b.get('status') == 'confirmed')
        total_attendees = sum(int(b.get('attendees', 0)) for b in bookings)
        
        # Monthly booking count
        monthly_bookings = defaultdict(int)
        for booking in bookings:
            try:
                if booking.get('start_time') and hasattr(booking['start_time'], 'strftime'):
                    month_key = booking['start_time'].strftime('%Y-%m')
                    monthly_bookings[month_key] += 1
            except:
                continue
        
        return {
            'overview': f'Total revenue: ${total_revenue:.2f}, Total attendees: {total_attendees}',
            'trends': {
                'monthly_bookings': dict(monthly_bookings),
                'total_revenue': total_revenue,
                'average_attendees': total_attendees / max(len(bookings), 1)
            },
            'patterns': {
                'most_booked_month': max(monthly_bookings.items(), key=lambda x: x[1]) if monthly_bookings else None,
                'booking_frequency': len(bookings)
            },
            'recommendations': [
                'Consider bulk booking discounts for frequent customers',
                'Plan events during peak months for better attendance'
            ]
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get client analytics: {e}")
        return {
            'overview': 'Analytics temporarily unavailable',
            'trends': {},
            'patterns': {},
            'recommendations': []
        }

def get_client_booking_trends(client_id):
    """Get client booking trends over time"""
    try:
        bookings = get_enhanced_client_bookings(client_id)
        
        # Monthly trends
        monthly_trends = defaultdict(int)
        for booking in bookings:
            try:
                if booking.get('start_time') and hasattr(booking['start_time'], 'strftime'):
                    month_key = booking['start_time'].strftime('%Y-%m')
                    monthly_trends[month_key] += 1
            except:
                continue
        
        return {
            'monthly_trends': dict(monthly_trends),
            'total_bookings': len(bookings)
        }
    except Exception as e:
        print(f"❌ ERROR: Failed to get booking trends: {e}")
        return {'monthly_trends': [], 'total_bookings': 0}

def get_client_revenue_trends(client_id):
    """Get client revenue trends over time"""
    try:
        bookings = get_enhanced_client_bookings(client_id)
        
        # Monthly revenue
        monthly_revenue = defaultdict(float)
        for booking in bookings:
            try:
                if (booking.get('start_time') and hasattr(booking['start_time'], 'strftime') and 
                    booking.get('status') == 'confirmed'):
                    month_key = booking['start_time'].strftime('%Y-%m')
                    monthly_revenue[month_key] += float(booking.get('total_price', 0))
            except:
                continue
        
        return {
            'monthly_revenue': dict(monthly_revenue),
            'total_revenue': sum(monthly_revenue.values())
        }
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue trends: {e}")
        return {'monthly_revenue': [], 'total_revenue': 0}

def get_client_seasonal_patterns(client_id):
    """Get client seasonal booking patterns"""
    try:
        bookings = get_enhanced_client_bookings(client_id)
        
        # Quarterly breakdown
        quarterly_breakdown = defaultdict(int)
        for booking in bookings:
            try:
                if booking.get('start_time') and hasattr(booking['start_time'], 'month'):
                    month = booking['start_time'].month
                    quarter = f"Q{((month - 1) // 3) + 1}"
                    quarterly_breakdown[quarter] += 1
            except:
                continue
        
        # Peak months
        monthly_counts = defaultdict(int)
        for booking in bookings:
            try:
                if booking.get('start_time') and hasattr(booking['start_time'], 'strftime'):
                    month_name = booking['start_time'].strftime('%B')
                    monthly_counts[month_name] += 1
            except:
                continue
        
        peak_months = sorted(monthly_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            'quarterly_breakdown': dict(quarterly_breakdown),
            'peak_months': peak_months
        }
    except Exception as e:
        print(f"❌ ERROR: Failed to get seasonal patterns: {e}")
        return {'quarterly_breakdown': [], 'peak_months': []}

# ===============================
# EXPORT FUNCTIONS
# ===============================

def export_clients_csv(clients_data, include_bookings=False):
    """Export clients to CSV format"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        if include_bookings:
            writer.writerow([
                'Client ID', 'Company Name', 'Contact Person', 'Email', 'Phone', 
                'Address', 'Total Bookings', 'Total Revenue', 'Last Booking Date',
                'Created Date', 'Notes'
            ])
        else:
            writer.writerow([
                'Client ID', 'Company Name', 'Contact Person', 'Email', 'Phone', 
                'Address', 'Booking Count', 'Created Date', 'Notes'
            ])
        
        # Write data
        for client in clients_data:
            if include_bookings:
                writer.writerow([
                    client.get('id', ''),
                    client.get('company_name', ''),
                    client.get('contact_person', ''),
                    client.get('email', ''),
                    client.get('phone', ''),
                    client.get('address', ''),
                    client.get('booking_count', 0),
                    client.get('total_revenue', 0),
                    client.get('last_booking_date', ''),
                    client.get('created_at', ''),
                    client.get('notes', '')
                ])
            else:
                writer.writerow([
                    client.get('id', ''),
                    client.get('company_name', ''),
                    client.get('contact_person', ''),
                    client.get('email', ''),
                    client.get('phone', ''),
                    client.get('address', ''),
                    client.get('booking_count', 0),
                    client.get('created_at', ''),
                    client.get('notes', '')
                ])
        
        output.seek(0)
        
        # Create filename
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        filename = f'clients_export_{timestamp}.csv'
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ ERROR: Failed to export clients CSV: {e}")
        raise

# ===============================
# API ENDPOINTS
# ===============================

@clients_bp.route('/api/clients/search')
@login_required
def api_search_clients():
    """API endpoint for client search"""
    try:
        query = request.args.get('q', '').strip()
        limit = request.args.get('limit', 10, type=int)
        
        if not query:
            return jsonify([])
        
        clients = get_enhanced_clients_list(search_query=query)
        
        # Format for API response
        results = []
        for client in clients[:limit]:
            results.append({
                'id': client.get('id'),
                'company_name': client.get('company_name'),
                'contact_person': client.get('contact_person'),
                'email': client.get('email'),
                'phone': client.get('phone'),
                'display_name': client.get('display_name'),
                'booking_count': client.get('booking_count', 0),
                'total_revenue': client.get('total_revenue', 0)
            })
        
        return jsonify(results)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to search clients via API: {e}")
        return jsonify([])

@clients_bp.route('/api/clients/<int:id>/stats')
@login_required
def api_client_stats(id):
    """API endpoint for client statistics"""
    try:
        client = get_client_by_id_from_db(id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        bookings = get_enhanced_client_bookings(id)
        stats = calculate_client_statistics(client, bookings)
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get client stats via API: {e}")
        return jsonify({'error': 'Failed to get client statistics'}), 500

# ===============================
# ERROR HANDLERS
# ===============================

@clients_bp.errorhandler(404)
def client_not_found(error):
    """Handle 404 errors in clients"""
    flash('⚠️ The requested client was not found.', 'warning')
    return redirect(url_for('clients.clients'))

@clients_bp.errorhandler(500)
def client_internal_error(error):
    """Handle internal server errors in clients"""
    print(f"❌ Client management error: {error}")
    
    try:
        log_user_activity(
            ActivityTypes.ERROR_OCCURRED,
            f"Client management internal error: {str(error)}",
            resource_type='clients',
            status='failed'
        )
    except Exception as log_error:
        print(f"⚠️ WARNING: Failed to log error activity: {log_error}")
    
    flash('⚠️ An error occurred while processing your request. Please try again.', 'danger')
    return redirect(url_for('clients.clients'))