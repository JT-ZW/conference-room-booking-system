from flask import Blueprint, render_template, flash, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.logging import log_user_activity
from settings.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from core import supabase_admin, convert_datetime_strings, ActivityTypes, get_booking_calendar_events_supabase
from datetime import datetime, timedelta, UTC

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """Enhanced main dashboard view with comprehensive statistics and recent activity"""
    try:
        print("🔍 DEBUG: Loading enhanced dashboard")
        
        # Log dashboard view
        log_user_activity(
            ActivityTypes.PAGE_VIEW, 
            "Viewed enhanced dashboard", 
            resource_type='dashboard'
        )
        
        # Get comprehensive dashboard statistics
        stats = get_dashboard_stats()
        
        # Get recent bookings
        recent_bookings = get_recent_bookings()
        
        # Get upcoming bookings
        upcoming_bookings = get_upcoming_bookings()
        
        # Get today's bookings
        today_bookings = get_today_bookings()
        
        # Get revenue trends
        revenue_trends = get_revenue_trends(30)  # Last 30 days
        
        print(f"✅ DEBUG: Enhanced dashboard loaded successfully")
        print(f"   - Total bookings: {stats.get('total_bookings', 0)}")
        print(f"   - Recent bookings: {len(recent_bookings)}")
        print(f"   - Upcoming bookings: {len(upcoming_bookings)}")
        print(f"   - Today's bookings: {len(today_bookings)}")
        
        # Debug the first recent booking to check data structure
        if recent_bookings:
            print(f"   - Sample recent booking: {recent_bookings[0]}")
        
        return render_template('dashboard.html',
                             title='Dashboard',
                             stats=stats,
                             recent_bookings=recent_bookings,
                             upcoming_bookings=upcoming_bookings,
                             today_bookings=today_bookings,
                             revenue_trends=revenue_trends,
                             now=datetime.now(UTC))
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load enhanced dashboard: {e}")
        import traceback
        traceback.print_exc()
        
        # Log the error
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Dashboard loading failed: {str(e)}",
                resource_type='dashboard',
                status='failed'
            )
        except:
            pass
        
        # Return basic dashboard with error handling
        flash('⚠️ Some dashboard data could not be loaded. Please refresh the page.', 'warning')
        return render_template('dashboard.html',
                             title='Dashboard',
                             stats=get_empty_stats(),
                             recent_bookings=[],
                             upcoming_bookings=[],
                             today_bookings=[],
                             revenue_trends=get_empty_revenue_trends(),
                             error="Failed to load dashboard data",
                             now=datetime.now(UTC))

def get_dashboard_stats():
    """Get comprehensive dashboard statistics with improved error handling"""
    try:
        print("🔍 DEBUG: Calculating dashboard statistics")
        
        # Get all bookings with status and revenue data
        bookings_response = supabase_admin.table('bookings').select(
            'id, status, total_price, created_at, start_time'
        ).execute()
        bookings = bookings_response.data if bookings_response.data else []
        
        # Get clients count
        clients_response = supabase_admin.table('clients').select('id').execute()
        clients_count = len(clients_response.data) if clients_response.data else 0
        
        # Get rooms data
        rooms_response = supabase_admin.table('rooms').select('id, status').execute()
        rooms = rooms_response.data if rooms_response.data else []
        
        # Calculate booking statistics
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.get('status') == 'confirmed'])
        tentative_bookings = len([b for b in bookings if b.get('status') == 'tentative'])
        cancelled_bookings = len([b for b in bookings if b.get('status') == 'cancelled'])
        
        # Calculate revenue (only from confirmed bookings)
        total_revenue = sum(
            float(b.get('total_price', 0)) 
            for b in bookings 
            if b.get('status') == 'confirmed' and b.get('total_price')
        )
        
        # Calculate this month's statistics
        current_month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_bookings = []
        this_month_revenue = 0
        
        for b in bookings:
            if b.get('created_at'):
                try:
                    created_date = datetime.fromisoformat(b['created_at'].replace('Z', ''))
                    if created_date >= current_month:
                        this_month_bookings.append(b)
                        if b.get('status') == 'confirmed' and b.get('total_price'):
                            this_month_revenue += float(b.get('total_price', 0))
                except:
                    continue
        
        # Calculate today's bookings
        today = datetime.now(UTC).date()
        today_bookings = []
        
        for b in bookings:
            if b.get('start_time'):
                try:
                    start_date = datetime.fromisoformat(b['start_time'].replace('Z', '')).date()
                    if start_date == today:
                        today_bookings.append(b)
                except:
                    continue
        
        # Room statistics
        available_rooms = len([r for r in rooms if r.get('status') == 'available'])
        maintenance_rooms = len([r for r in rooms if r.get('status') == 'maintenance'])
        reserved_rooms = len([r for r in rooms if r.get('status') == 'reserved'])
        
        # Calculate occupancy rate and other metrics
        occupancy_rate = round((confirmed_bookings / max(total_bookings, 1)) * 100, 1)
        average_booking_value = round(total_revenue / max(confirmed_bookings, 1), 2)
        
        stats = {
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed_bookings,
            'tentative_bookings': tentative_bookings,
            'cancelled_bookings': cancelled_bookings,
            'this_month_bookings': len(this_month_bookings),
            'today_bookings': len(today_bookings),
            'total_clients': clients_count,
            'total_revenue': round(total_revenue, 2),
            'this_month_revenue': round(this_month_revenue, 2),
            'average_booking_value': average_booking_value,
            'available_rooms': available_rooms,
            'maintenance_rooms': maintenance_rooms,
            'reserved_rooms': reserved_rooms,
            'total_rooms': len(rooms),
            'occupancy_rate': occupancy_rate,
            'conversion_rate': round((confirmed_bookings / max(confirmed_bookings + tentative_bookings, 1)) * 100, 1)
        }
        
        print(f"✅ DEBUG: Dashboard stats calculated successfully")
        return stats
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate dashboard stats: {e}")
        import traceback
        traceback.print_exc()
        return get_empty_stats()

def get_empty_stats():
    """Return empty stats structure for error cases"""
    return {
        'total_bookings': 0,
        'confirmed_bookings': 0,
        'tentative_bookings': 0,
        'cancelled_bookings': 0,
        'this_month_bookings': 0,
        'today_bookings': 0,
        'total_clients': 0,
        'total_revenue': 0,
        'this_month_revenue': 0,
        'average_booking_value': 0,
        'available_rooms': 0,
        'maintenance_rooms': 0,
        'reserved_rooms': 0,
        'total_rooms': 0,
        'occupancy_rate': 0,
        'conversion_rate': 0
    }

def get_recent_bookings(limit=5):
    """Get recent bookings for dashboard with improved data fetching"""
    try:
        print(f"🔍 DEBUG: Fetching {limit} recent bookings")
        
        # Try to fetch with joins first
        response = supabase_admin.table('bookings').select("""
            id, title, status, start_time, total_price, created_at, room_id, client_id,
            client_name, company_name, client_email,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name, email)
        """).order('created_at', desc=True).limit(limit).execute()
        
        bookings = response.data if response.data else []
        print(f"📊 DEBUG: Raw booking data received: {len(bookings)} bookings")
        
        # If no bookings, try without joins as fallback
        if not bookings:
            print("⚠️ DEBUG: No bookings with joins, trying basic query")
            response = supabase_admin.table('bookings').select('*').order('created_at', desc=True).limit(limit).execute()
            bookings = response.data if response.data else []
        
        # Get all rooms and clients for lookup (fallback if joins fail)
        rooms_response = supabase_admin.table('rooms').select('*').execute()
        rooms_lookup = {room['id']: room for room in (rooms_response.data or [])}
        
        clients_response = supabase_admin.table('clients').select('*').execute()
        clients_lookup = {client['id']: client for client in (clients_response.data or [])}
        
        # Format bookings for display
        formatted_bookings = []
        for booking in bookings:
            print(f"🔍 DEBUG: Processing booking {booking.get('id')}")
            
            # Get client information - multiple fallback strategies
            client_name = 'Unknown Client'
            client_id = None
            
            # Strategy 1: Use joined client data
            if booking.get('client'):
                client = booking['client']
                client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                client_id = client.get('id')
                print(f"   ✅ Client from join: {client_name}")
            
            # Strategy 2: Use stored client name fields
            elif booking.get('client_name') or booking.get('company_name'):
                client_name = booking.get('company_name') or booking.get('client_name', 'Unknown Client')
                client_id = booking.get('client_id')
                print(f"   ✅ Client from stored fields: {client_name}")
            
            # Strategy 3: Lookup by client_id
            elif booking.get('client_id') and booking['client_id'] in clients_lookup:
                client = clients_lookup[booking['client_id']]
                client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                client_id = client.get('id')
                print(f"   ✅ Client from lookup: {client_name}")
            
            # Get room information - multiple fallback strategies
            room_name = 'Unknown Room'
            room_id = None
            
            # Strategy 1: Use joined room data
            if booking.get('room'):
                room = booking['room']
                room_name = room.get('name', 'Unknown Room')
                room_id = room.get('id')
                print(f"   ✅ Room from join: {room_name}")
            
            # Strategy 2: Lookup by room_id
            elif booking.get('room_id') and booking['room_id'] in rooms_lookup:
                room = rooms_lookup[booking['room_id']]
                room_name = room.get('name', 'Unknown Room')
                room_id = room.get('id')
                print(f"   ✅ Room from lookup: {room_name}")
            
            # Format datetime for display
            created_at_formatted = 'Unknown'
            start_time_formatted = 'Unknown'
            time_ago = 'Unknown'
            
            try:
                if booking.get('created_at'):
                    created_dt = datetime.fromisoformat(booking['created_at'].replace('Z', ''))
                    created_at_formatted = created_dt.strftime('%Y-%m-%d %H:%M')
                    
                    # Calculate time ago
                    now = datetime.now(UTC)
                    time_diff = now - created_dt
                    
                    if time_diff.days > 0:
                        time_ago = f'{time_diff.days} days ago'
                    elif time_diff.seconds > 3600:
                        hours = time_diff.seconds // 3600
                        time_ago = f'{hours} hours ago'
                    elif time_diff.seconds > 60:
                        minutes = time_diff.seconds // 60
                        time_ago = f'{minutes} minutes ago'
                    else:
                        time_ago = 'Just now'
                
                if booking.get('start_time'):
                    start_dt = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                    start_time_formatted = start_dt.strftime('%Y-%m-%d %H:%M')
            except Exception as dt_error:
                print(f"   ⚠️ Datetime parsing error: {dt_error}")
            
            formatted_booking = {
                'id': booking.get('id'),
                'title': booking.get('title', 'Unknown Event'),
                'status': booking.get('status', 'tentative'),
                'start_time': start_time_formatted,
                'created_at': created_at_formatted,
                'time_ago': time_ago,
                'total_price': booking.get('total_price', 0),
                'client_name': client_name,
                'room_name': room_name,
                'client_id': client_id,
                'room_id': room_id
            }
            
            formatted_bookings.append(formatted_booking)
            print(f"   ✅ Formatted booking: {formatted_booking['title']} - {formatted_booking['client_name']} - {formatted_booking['room_name']}")
        
        print(f"✅ DEBUG: Successfully formatted {len(formatted_bookings)} recent bookings")
        return formatted_bookings
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get recent bookings: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_upcoming_bookings(limit=5):
    """Get upcoming bookings for dashboard with improved data fetching"""
    try:
        print(f"🔍 DEBUG: Fetching {limit} upcoming bookings")
        
        # Get bookings starting from now
        now = datetime.now(UTC).isoformat()
        
        # Try to fetch with joins first
        response = supabase_admin.table('bookings').select("""
            id, title, status, start_time, end_time, attendees, room_id, client_id,
            client_name, company_name, client_email,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name, email)
        """).gte('start_time', now).neq('status', 'cancelled').order('start_time').limit(limit).execute()
        
        bookings = response.data if response.data else []
        print(f"📊 DEBUG: Raw upcoming booking data received: {len(bookings)} bookings")
        
        # If no bookings, try without joins as fallback
        if not bookings:
            print("⚠️ DEBUG: No upcoming bookings with joins, trying basic query")
            response = supabase_admin.table('bookings').select('*').gte('start_time', now).neq('status', 'cancelled').order('start_time').limit(limit).execute()
            bookings = response.data if response.data else []
        
        # Get all rooms and clients for lookup (fallback if joins fail)
        rooms_response = supabase_admin.table('rooms').select('*').execute()
        rooms_lookup = {room['id']: room for room in (rooms_response.data or [])}
        
        clients_response = supabase_admin.table('clients').select('*').execute()
        clients_lookup = {client['id']: client for client in (clients_response.data or [])}
        
        # Format bookings for display
        formatted_bookings = []
        for booking in bookings:
            print(f"🔍 DEBUG: Processing upcoming booking {booking.get('id')}")
            
            # Get client information - multiple fallback strategies
            client_name = 'Unknown Client'
            client_id = None
            
            if booking.get('client'):
                client = booking['client']
                client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                client_id = client.get('id')
            elif booking.get('client_name') or booking.get('company_name'):
                client_name = booking.get('company_name') or booking.get('client_name', 'Unknown Client')
                client_id = booking.get('client_id')
            elif booking.get('client_id') and booking['client_id'] in clients_lookup:
                client = clients_lookup[booking['client_id']]
                client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                client_id = client.get('id')
            
            # Get room information - multiple fallback strategies
            room_name = 'Unknown Room'
            room_capacity = 0
            room_id = None
            
            if booking.get('room'):
                room = booking['room']
                room_name = room.get('name', 'Unknown Room')
                room_capacity = room.get('capacity', 0)
                room_id = room.get('id')
            elif booking.get('room_id') and booking['room_id'] in rooms_lookup:
                room = rooms_lookup[booking['room_id']]
                room_name = room.get('name', 'Unknown Room')
                room_capacity = room.get('capacity', 0)
                room_id = room.get('id')
            
            # Format datetime for display
            start_time_formatted = 'Unknown'
            end_time_formatted = 'Unknown'
            days_until = 'Unknown'
            
            try:
                if booking.get('start_time'):
                    start_dt = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                    start_time_formatted = start_dt.strftime('%Y-%m-%d %H:%M')
                    
                    # Calculate days until
                    days_diff = (start_dt.date() - datetime.now(UTC).date()).days
                    if days_diff == 0:
                        days_until = 'Today'
                    elif days_diff == 1:
                        days_until = 'Tomorrow'
                    else:
                        days_until = f'{days_diff} days'
                
                if booking.get('end_time'):
                    end_dt = datetime.fromisoformat(booking['end_time'].replace('Z', ''))
                    end_time_formatted = end_dt.strftime('%Y-%m-%d %H:%M')
            except Exception as dt_error:
                print(f"   ⚠️ Datetime parsing error: {dt_error}")
            
            formatted_booking = {
                'id': booking.get('id'),
                'title': booking.get('title', 'Unknown Event'),
                'status': booking.get('status', 'tentative'),
                'start_time': start_time_formatted,
                'end_time': end_time_formatted,
                'days_until': days_until,
                'attendees': booking.get('attendees', 0),
                'client_name': client_name,
                'room_name': room_name,
                'room_capacity': room_capacity,
                'client_id': client_id,
                'room_id': room_id
            }
            
            formatted_bookings.append(formatted_booking)
            print(f"   ✅ Formatted upcoming booking: {formatted_booking['title']} - {formatted_booking['client_name']} - {formatted_booking['room_name']}")
        
        print(f"✅ DEBUG: Successfully formatted {len(formatted_bookings)} upcoming bookings")
        return formatted_bookings
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get upcoming bookings: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_today_bookings():
    """Get today's bookings with improved data fetching"""
    try:
        print("🔍 DEBUG: Fetching today's bookings")
        
        # Get today's date range
        today = datetime.now(UTC).date()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
        today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=UTC)
        
        # Try to fetch with joins first
        response = supabase_admin.table('bookings').select("""
            id, title, status, start_time, end_time, attendees, room_id, client_id,
            client_name, company_name, client_email,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name, email)
        """).gte('start_time', today_start.isoformat()).lte(
            'start_time', today_end.isoformat()
        ).neq('status', 'cancelled').order('start_time').execute()
        
        bookings = response.data if response.data else []
        print(f"📊 DEBUG: Raw today's booking data received: {len(bookings)} bookings")
        
        # If no bookings, try without joins as fallback
        if not bookings:
            print("⚠️ DEBUG: No today's bookings with joins, trying basic query")
            response = supabase_admin.table('bookings').select('*').gte('start_time', today_start.isoformat()).lte(
                'start_time', today_end.isoformat()
            ).neq('status', 'cancelled').order('start_time').execute()
            bookings = response.data if response.data else []
        
        # Get all rooms and clients for lookup (fallback if joins fail)
        rooms_response = supabase_admin.table('rooms').select('*').execute()
        rooms_lookup = {room['id']: room for room in (rooms_response.data or [])}
        
        clients_response = supabase_admin.table('clients').select('*').execute()
        clients_lookup = {client['id']: client for client in (clients_response.data or [])}
        
        # Format bookings for display
        formatted_bookings = []
        for booking in bookings:
            print(f"🔍 DEBUG: Processing today's booking {booking.get('id')}")
            
            # Get client information - multiple fallback strategies
            client_name = 'Unknown Client'
            client_id = None
            
            if booking.get('client'):
                client = booking['client']
                client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                client_id = client.get('id')
            elif booking.get('client_name') or booking.get('company_name'):
                client_name = booking.get('company_name') or booking.get('client_name', 'Unknown Client')
                client_id = booking.get('client_id')
            elif booking.get('client_id') and booking['client_id'] in clients_lookup:
                client = clients_lookup[booking['client_id']]
                client_name = client.get('company_name') or client.get('contact_person', 'Unknown Client')
                client_id = client.get('id')
            
            # Get room information - multiple fallback strategies
            room_name = 'Unknown Room'
            room_id = None
            
            if booking.get('room'):
                room = booking['room']
                room_name = room.get('name', 'Unknown Room')
                room_id = room.get('id')
            elif booking.get('room_id') and booking['room_id'] in rooms_lookup:
                room = rooms_lookup[booking['room_id']]
                room_name = room.get('name', 'Unknown Room')
                room_id = room.get('id')
            
            # Format time for display
            start_time_formatted = 'Unknown'
            end_time_formatted = 'Unknown'
            
            try:
                if booking.get('start_time'):
                    start_dt = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                    start_time_formatted = start_dt.strftime('%H:%M')
                
                if booking.get('end_time'):
                    end_dt = datetime.fromisoformat(booking['end_time'].replace('Z', ''))
                    end_time_formatted = end_dt.strftime('%H:%M')
            except Exception as dt_error:
                print(f"   ⚠️ Datetime parsing error: {dt_error}")
            
            formatted_booking = {
                'id': booking.get('id'),
                'title': booking.get('title', 'Unknown Event'),
                'status': booking.get('status', 'tentative'),
                'start_time': start_time_formatted,
                'end_time': end_time_formatted,
                'time_range': f"{start_time_formatted} - {end_time_formatted}",
                'attendees': booking.get('attendees', 0),
                'client_name': client_name,
                'room_name': room_name,
                'client_id': client_id,
                'room_id': room_id
            }
            
            formatted_bookings.append(formatted_booking)
            print(f"   ✅ Formatted today's booking: {formatted_booking['title']} - {formatted_booking['client_name']} - {formatted_booking['room_name']}")
        
        print(f"✅ DEBUG: Successfully formatted {len(formatted_bookings)} today's bookings")
        return formatted_bookings
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get today's bookings: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_revenue_trends(days=30):
    """Get revenue trends for the last N days"""
    try:
        # Get date range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)
        
        # Get confirmed bookings in date range
        response = supabase_admin.table('bookings').select(
            'total_price, created_at'
        ).eq('status', 'confirmed').gte(
            'created_at', start_date.isoformat()
        ).lte(
            'created_at', end_date.isoformat()
        ).execute()
        
        bookings = response.data if response.data else []
        
        # Group by day
        daily_revenue = {}
        for booking in bookings:
            try:
                created_date = datetime.fromisoformat(booking['created_at'].replace('Z', '')).date()
                revenue = float(booking.get('total_price', 0))
                
                date_str = created_date.isoformat()
                if date_str not in daily_revenue:
                    daily_revenue[date_str] = 0
                daily_revenue[date_str] += revenue
            except:
                continue
        
        # Format for chart
        dates = []
        revenues = []
        
        current_date = start_date.date()
        while current_date <= end_date.date():
            date_str = current_date.isoformat()
            dates.append(date_str)
            revenues.append(daily_revenue.get(date_str, 0))
            current_date += timedelta(days=1)
        
        return {
            'dates': dates,
            'revenues': revenues,
            'total_revenue': sum(revenues),
            'average_daily': sum(revenues) / len(revenues) if revenues else 0,
            'max_daily': max(revenues) if revenues else 0,
            'period_days': days
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue trends: {e}")
        return get_empty_revenue_trends()

def get_empty_revenue_trends():
    """Return empty revenue trends for error cases"""
    return {
        'dates': [],
        'revenues': [],
        'total_revenue': 0,
        'average_daily': 0,
        'max_daily': 0,
        'period_days': 30
    }

@dashboard_bp.route('/calendar')
@login_required
def calendar():
    """Enhanced calendar view with better error handling"""
    try:
        print("🔍 DEBUG: Loading calendar view")
        
        # Fetch events for the calendar from Supabase
        events = get_booking_calendar_events_supabase()
        
        # Get rooms for filtering
        rooms_response = supabase_admin.table('rooms').select('*').order('name').execute()
        rooms = rooms_response.data if rooms_response.data else []
        
        # Log calendar view
        log_user_activity(
            ActivityTypes.PAGE_VIEW,
            "Viewed booking calendar",
            resource_type='calendar',
            metadata={'events_count': len(events), 'rooms_count': len(rooms)}
        )
        
        print(f"✅ DEBUG: Calendar loaded with {len(events)} events and {len(rooms)} rooms")
        
        return render_template('calendar.html', 
                             title='Booking Calendar', 
                             events=events, 
                             rooms=rooms)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load calendar: {e}")
        import traceback
        traceback.print_exc()
        
        # Log the error
        try:
            log_user_activity(
                ActivityTypes.ERROR_OCCURRED,
                f"Calendar loading failed: {str(e)}",
                resource_type='calendar',
                status='failed'
            )
        except:
            pass
        
        # Return basic calendar view with error
        flash('⚠️ Calendar data could not be loaded. Please refresh the page.', 'warning')
        return render_template('calendar.html', 
                             title='Booking Calendar', 
                             events=[], 
                             rooms=[],
                             error="Failed to load calendar data")

@dashboard_bp.route('/dashboard/events')
@login_required
def get_events():
    """API endpoint for calendar events"""
    try:
        events = get_booking_calendar_events_supabase()
        
        # Log API access
        log_user_activity(
            ActivityTypes.API_CALL,
            "Fetched calendar events via API",
            resource_type='api',
            metadata={'events_count': len(events)}
        )
        
        return jsonify(events)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get events via API: {e}")
        return jsonify([])

# ===============================
# API ENDPOINTS FOR AJAX REQUESTS
# ===============================

@dashboard_bp.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """API endpoint for dashboard statistics"""
    try:
        stats = get_dashboard_stats()
        return jsonify(stats)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get dashboard stats via API: {e}")
        return jsonify(get_empty_stats())

@dashboard_bp.route('/api/dashboard/recent-bookings')
@login_required
def api_recent_bookings():
    """API endpoint for recent bookings"""
    try:
        limit = request.args.get('limit', 5, type=int)
        recent_bookings = get_recent_bookings(limit)
        return jsonify(recent_bookings)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get recent bookings via API: {e}")
        return jsonify([])

@dashboard_bp.route('/api/dashboard/upcoming-bookings')
@login_required
def api_upcoming_bookings():
    """API endpoint for upcoming bookings"""
    try:
        limit = request.args.get('limit', 5, type=int)
        upcoming_bookings = get_upcoming_bookings(limit)
        return jsonify(upcoming_bookings)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get upcoming bookings via API: {e}")
        return jsonify([])

@dashboard_bp.route('/api/dashboard/today-bookings')
@login_required
def api_today_bookings():
    """API endpoint for today's bookings"""
    try:
        today_bookings = get_today_bookings()
        return jsonify(today_bookings)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get today's bookings via API: {e}")
        return jsonify([])

@dashboard_bp.route('/api/dashboard/revenue-trends')
@login_required
def api_revenue_trends():
    """API endpoint for revenue trends"""
    try:
        days = request.args.get('days', 30, type=int)
        trends = get_revenue_trends(days)
        return jsonify(trends)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue trends via API: {e}")
        return jsonify(get_empty_revenue_trends())

@dashboard_bp.route('/api/dashboard/refresh')
@login_required
def api_refresh_dashboard():
    """API endpoint to refresh all dashboard data"""
    try:
        print("🔄 DEBUG: Refreshing dashboard data")
        
        # Get all dashboard data
        stats = get_dashboard_stats()
        recent_bookings = get_recent_bookings()
        upcoming_bookings = get_upcoming_bookings()
        today_bookings = get_today_bookings()
        revenue_trends = get_revenue_trends(30)
        
        # Log refresh action
        log_user_activity(
            ActivityTypes.API_CALL,
            "Refreshed dashboard data",
            resource_type='dashboard',
            metadata={'total_bookings': stats.get('total_bookings', 0)}
        )
        
        return jsonify({
            'success': True,
            'stats': stats,
            'recent_bookings': recent_bookings,
            'upcoming_bookings': upcoming_bookings,
            'today_bookings': today_bookings,
            'revenue_trends': revenue_trends,
            'timestamp': datetime.now(UTC).isoformat()
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to refresh dashboard data: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to refresh dashboard data',
            'timestamp': datetime.now(UTC).isoformat()
        }), 500

# ===============================
# DASHBOARD ANALYTICS HELPERS
# ===============================

def get_booking_trends(days=7):
    """Get booking trends for the last N days"""
    try:
        # Get date range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)
        
        # Get bookings in date range
        response = supabase_admin.table('bookings').select(
            'id, status, created_at'
        ).gte('created_at', start_date.isoformat()).lte(
            'created_at', end_date.isoformat()
        ).execute()
        
        bookings = response.data if response.data else []
        
        # Group by day and status
        daily_bookings = {}
        
        for booking in bookings:
            try:
                created_date = datetime.fromisoformat(booking['created_at'].replace('Z', '')).date()
                status = booking.get('status', 'tentative')
                
                date_str = created_date.isoformat()
                if date_str not in daily_bookings:
                    daily_bookings[date_str] = {'confirmed': 0, 'tentative': 0, 'cancelled': 0}
                
                daily_bookings[date_str][status] += 1
            except:
                continue
        
        # Format for chart
        dates = []
        confirmed_counts = []
        tentative_counts = []
        cancelled_counts = []
        
        current_date = start_date.date()
        while current_date <= end_date.date():
            date_str = current_date.isoformat()
            dates.append(date_str)
            
            day_data = daily_bookings.get(date_str, {'confirmed': 0, 'tentative': 0, 'cancelled': 0})
            confirmed_counts.append(day_data['confirmed'])
            tentative_counts.append(day_data['tentative'])
            cancelled_counts.append(day_data['cancelled'])
            
            current_date += timedelta(days=1)
        
        return {
            'dates': dates,
            'confirmed': confirmed_counts,
            'tentative': tentative_counts,
            'cancelled': cancelled_counts,
            'total_bookings': len(bookings)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get booking trends: {e}")
        return {
            'dates': [],
            'confirmed': [],
            'tentative': [],
            'cancelled': [],
            'total_bookings': 0
        }

@dashboard_bp.route('/api/dashboard/booking-trends')
@login_required
def api_booking_trends():
    """API endpoint for booking trends"""
    try:
        days = request.args.get('days', 7, type=int)
        trends = get_booking_trends(days)
        return jsonify(trends)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get booking trends via API: {e}")
        return jsonify({
            'dates': [],
            'confirmed': [],
            'tentative': [],
            'cancelled': [],
            'total_bookings': 0
        })

def get_room_utilization():
    """Get room utilization statistics"""
    try:
        # Get all rooms
        rooms_response = supabase_admin.table('rooms').select('id, name, capacity').execute()
        rooms = rooms_response.data if rooms_response.data else []
        
        # Get current month's bookings
        current_month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (current_month + timedelta(days=32)).replace(day=1)
        
        bookings_response = supabase_admin.table('bookings').select(
            'room_id, start_time, end_time, status'
        ).gte('start_time', current_month.isoformat()).lt(
            'start_time', next_month.isoformat()
        ).neq('status', 'cancelled').execute()
        
        bookings = bookings_response.data if bookings_response.data else []
        
        # Calculate utilization per room
        room_utilization = []
        
        for room in rooms:
            room_id = room['id']
            room_bookings = [b for b in bookings if b.get('room_id') == room_id]
            
            # Calculate total booking hours
            total_hours = 0
            for booking in room_bookings:
                try:
                    start_dt = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                    end_dt = datetime.fromisoformat(booking['end_time'].replace('Z', ''))
                    booking_hours = (end_dt - start_dt).total_seconds() / 3600
                    total_hours += booking_hours
                except:
                    continue
            
            # Calculate utilization percentage (assuming 8 hours/day, 30 days/month = 240 hours available)
            available_hours = 240  # This could be made configurable
            utilization_percentage = round((total_hours / available_hours) * 100, 1) if available_hours > 0 else 0
            
            room_utilization.append({
                'room_id': room_id,
                'room_name': room['name'],
                'capacity': room['capacity'],
                'total_bookings': len(room_bookings),
                'total_hours': round(total_hours, 1),
                'utilization_percentage': utilization_percentage
            })
        
        # Sort by utilization
        room_utilization.sort(key=lambda x: x['utilization_percentage'], reverse=True)
        
        return room_utilization
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get room utilization: {e}")
        return []

@dashboard_bp.route('/api/dashboard/room-utilization')
@login_required
def api_room_utilization():
    """API endpoint for room utilization statistics"""
    try:
        utilization = get_room_utilization()
        return jsonify(utilization)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get room utilization via API: {e}")
        return jsonify([])

# ===============================
# DEBUG ROUTES FOR TROUBLESHOOTING
# ===============================

@dashboard_bp.route('/debug/dashboard-data')
@login_required
def debug_dashboard_data():
    """Debug endpoint to check dashboard data fetching"""
    try:
        print("🔧 DEBUG: Testing dashboard data fetching")
        
        # Test basic database connections
        debug_results = {}
        
        # Test bookings table
        bookings_response = supabase_admin.table('bookings').select('id, title, client_id, room_id, client_name, company_name').limit(3).execute()
        debug_results['bookings_test'] = {
            'success': bool(bookings_response.data),
            'count': len(bookings_response.data) if bookings_response.data else 0,
            'sample_data': bookings_response.data[:2] if bookings_response.data else []
        }
        
        # Test rooms table
        rooms_response = supabase_admin.table('rooms').select('id, name').limit(3).execute()
        debug_results['rooms_test'] = {
            'success': bool(rooms_response.data),
            'count': len(rooms_response.data) if rooms_response.data else 0,
            'sample_data': rooms_response.data[:2] if rooms_response.data else []
        }
        
        # Test clients table
        clients_response = supabase_admin.table('clients').select('id, contact_person, company_name').limit(3).execute()
        debug_results['clients_test'] = {
            'success': bool(clients_response.data),
            'count': len(clients_response.data) if clients_response.data else 0,
            'sample_data': clients_response.data[:2] if clients_response.data else []
        }
        
        # Test joined query
        try:
            joined_response = supabase_admin.table('bookings').select("""
                id, title, client_name, room_id, client_id,
                room:rooms(id, name),
                client:clients(id, contact_person, company_name)
            """).limit(2).execute()
            
            debug_results['joined_query_test'] = {
                'success': bool(joined_response.data),
                'count': len(joined_response.data) if joined_response.data else 0,
                'sample_data': joined_response.data
            }
        except Exception as join_error:
            debug_results['joined_query_test'] = {
                'success': False,
                'error': str(join_error)
            }
        
        # Test recent bookings function
        try:
            recent_bookings = get_recent_bookings(2)
            debug_results['recent_bookings_function'] = {
                'success': bool(recent_bookings),
                'count': len(recent_bookings),
                'sample_data': recent_bookings
            }
        except Exception as recent_error:
            debug_results['recent_bookings_function'] = {
                'success': False,
                'error': str(recent_error)
            }
        
        return jsonify({
            'debug_results': debug_results,
            'timestamp': datetime.now(UTC).isoformat()
        })
        
    except Exception as e:
        print(f"❌ ERROR: Debug dashboard data failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# ===============================
# ERROR HANDLERS
# ===============================

@dashboard_bp.errorhandler(500)
def dashboard_internal_error(error):
    """Handle internal server errors in dashboard"""
    print(f"❌ Dashboard error: {error}")
    
    try:
        log_user_activity(
            ActivityTypes.ERROR_OCCURRED,
            f"Dashboard internal error: {str(error)}",
            resource_type='dashboard',
            status='failed'
        )
    except:
        pass
    
    flash('⚠️ An error occurred while loading the dashboard. Please try again.', 'danger')
    return redirect(url_for('dashboard.dashboard'))

@dashboard_bp.errorhandler(404)
def dashboard_not_found(error):
    """Handle 404 errors in dashboard"""
    flash('⚠️ The requested page was not found.', 'warning')
    return redirect(url_for('dashboard.dashboard'))

# ===============================
# CONTEXT PROCESSORS
# ===============================

@dashboard_bp.context_processor
def inject_dashboard_helpers():
    """Inject helper functions into dashboard templates"""
    return {
        'format_currency': lambda x: f"${float(x):,.2f}" if x else "$0.00",
        'format_percentage': lambda x: f"{float(x):.1f}%" if x else "0.0%",
        'format_large_number': lambda x: f"{int(x):,}" if x else "0",
        'get_status_badge_class': get_status_badge_class,
        'get_trend_icon': get_trend_icon
    }

def get_status_badge_class(status):
    """Get Bootstrap badge class for booking status"""
    status_classes = {
        'confirmed': 'badge-success',
        'tentative': 'badge-warning',
        'cancelled': 'badge-danger'
    }
    return status_classes.get(status, 'badge-secondary')

def get_trend_icon(current, previous):
    """Get trend icon based on comparison"""
    if current > previous:
        return 'fas fa-arrow-up text-success'
    elif current < previous:
        return 'fas fa-arrow-down text-danger'
    else:
        return 'fas fa-minus text-muted'