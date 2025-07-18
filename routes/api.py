from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from core import (supabase_admin, get_clients_with_booking_counts, get_client_by_id_from_db, 
                  get_client_bookings_from_db, get_booking_calendar_events_supabase, supabase_select,
                  get_booking_with_details, calculate_booking_totals)
from utils.logging import log_user_activity
from core import ActivityTypes
from datetime import datetime, UTC, timedelta

api_bp = Blueprint('api', __name__)

# ===============================
# CLIENT API ENDPOINTS
# ===============================

@api_bp.route('/api/clients/search')
@login_required
def search_clients():
    """Search clients with safe string handling"""
    try:
        # Safely get and process query
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify([])

        print(f"🔍 DEBUG: Searching for clients with query: {query}")
        
        # Get all clients
        response = supabase_admin.table('clients').select(
            'id, contact_person, company_name, email'
        ).execute()

        if not response.data:
            print("ℹ️ No clients found in database")
            return jsonify([])

        # Safe string comparison
        results = []
        query = query.lower()
        
        for client in response.data:
            # Safely get client fields with fallbacks
            contact = (client.get('contact_person') or '').lower()
            company = (client.get('company_name') or '').lower()
            email = (client.get('email') or '').lower()

            # Check for matches
            if (query in contact or 
                query in company or 
                query in email):
                
                results.append({
                    'id': client.get('id'),
                    'name': client.get('contact_person', ''),
                    'company': client.get('company_name', ''),
                    'email': client.get('email', '')
                })

        print(f"✅ Found {len(results)} matching clients")
        return jsonify(results)

    except Exception as e:
        print(f"❌ ERROR: Failed to get enhanced clients list: {e}")
        return jsonify([])
@api_bp.route('/api/companies/search')
@login_required
def api_search_companies():
    """Search companies specifically"""
    query = request.args.get('q', '').strip().lower()
    limit = request.args.get('limit', 10, type=int)
    
    if not query:
        return jsonify([])
    
    try:
        print(f"🔍 DEBUG: Searching companies with query: '{query}'")
        
        # Search only by company name
        response = supabase_admin.table('clients').select('*').execute()
        clients = response.data if response.data else []
        
        matches = []
        for client in clients:
            company = (client.get('company_name') or '').lower()
            
            if company and query in company:
                matches.append({
                    'id': client.get('id'),
                    'company_name': client.get('company_name'),
                    'contact_person': client.get('contact_person'),
                    'email': client.get('email'),
                    'phone': client.get('phone'),
                    'relevance': 10 if company.startswith(query) else 5
                })
        
        # Sort by relevance
        matches.sort(key=lambda x: x['relevance'], reverse=True)
        matches = matches[:limit]
        
        print(f"✅ DEBUG: Found {len(matches)} matching companies")
        return jsonify(matches)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to search companies: {e}")
        return jsonify([])

@api_bp.route('/api/clients/<int:client_id>')
@login_required
def api_get_client(client_id):
    """Get specific client details"""
    try:
        client = get_client_by_id_from_db(client_id)
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Get client's booking count
        bookings = get_client_bookings_from_db(client_id)
        client['booking_count'] = len(bookings)
        
        return jsonify(client)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get client {client_id}: {e}")
        return jsonify({'error': 'Failed to get client details'}), 500

@api_bp.route('/api/clients/<int:client_id>/bookings')
@login_required
def api_get_client_bookings(client_id):
    """Get bookings for a specific client"""
    try:
        bookings = get_client_bookings_from_db(client_id)
        return jsonify(bookings)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get client bookings: {e}")
        return jsonify([])

# ===============================
# ROOM API ENDPOINTS
# ===============================

@api_bp.route('/api/rooms/availability')
@login_required
def api_check_room_availability():
    """Check room availability for given time period"""
    try:
        room_id = request.args.get('room_id', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        exclude_booking_id = request.args.get('exclude_booking_id', type=int)
        
        if not all([room_id, start_time, end_time]):
            return jsonify({'error': 'Missing required parameters: room_id, start_time, end_time'}), 400
        
        from datetime import datetime
        from core import is_room_available_supabase
        
        # Parse datetime strings
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', ''))
            end_dt = datetime.fromisoformat(end_time.replace('Z', ''))
        except ValueError:
            return jsonify({'error': 'Invalid datetime format'}), 400
        
        # Check availability
        is_available = is_room_available_supabase(room_id, start_dt, end_dt, exclude_booking_id)
        
        # Get conflicting bookings if not available
        conflicting_bookings = []
        if not is_available:
            try:
                conflicts_response = supabase_admin.table('bookings').select(
                    'id, title, start_time, end_time, status'
                ).eq('room_id', room_id).neq('status', 'cancelled').lt(
                    'start_time', end_dt.isoformat()
                ).gt('end_time', start_dt.isoformat()).execute()
                
                conflicting_bookings = conflicts_response.data if conflicts_response.data else []
            except:
                pass
        
        return jsonify({
            'available': is_available,
            'room_id': room_id,
            'start_time': start_time,
            'end_time': end_time,
            'conflicting_bookings': conflicting_bookings
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to check room availability: {e}")
        return jsonify({'error': 'Failed to check availability'}), 500

@api_bp.route('/api/rooms/<int:room_id>/rates')
@login_required
def api_get_room_rates(room_id):
    """Get room pricing rates and details"""
    try:
        room_data = supabase_select('rooms', filters=[('id', 'eq', room_id)])
        
        if not room_data:
            return jsonify({'error': 'Room not found'}), 404
        
        room = room_data[0]
        
        return jsonify({
            'room_id': room_id,
            'name': room.get('name'),
            'description': room.get('description'),
            'capacity': room.get('capacity'),
            'hourly_rate': float(room.get('hourly_rate', 0)),
            'half_day_rate': float(room.get('half_day_rate', 0)),
            'full_day_rate': float(room.get('full_day_rate', 0)),
            'amenities': room.get('amenities', '').split(',') if room.get('amenities') else [],
            'status': room.get('status', 'available'),
            'image_url': room.get('image_url')
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get room rates: {e}")
        return jsonify({'error': 'Failed to get room rates'}), 500

@api_bp.route('/api/rooms')
@login_required
def api_get_rooms():
    """Get all rooms with basic information"""
    try:
        rooms_response = supabase_admin.table('rooms').select('*').order('name').execute()
        rooms = rooms_response.data if rooms_response.data else []
        
        # Format rooms for API response
        formatted_rooms = []
        for room in rooms:
            formatted_rooms.append({
                'id': room.get('id'),
                'name': room.get('name'),
                'capacity': room.get('capacity'),
                'status': room.get('status', 'available'),
                'hourly_rate': float(room.get('hourly_rate', 0)),
                'half_day_rate': float(room.get('half_day_rate', 0)),
                'full_day_rate': float(room.get('full_day_rate', 0)),
                'description': room.get('description', ''),
                'amenities': room.get('amenities', '').split(',') if room.get('amenities') else []
            })
        
        return jsonify(formatted_rooms)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get rooms: {e}")
        return jsonify([])

# ===============================
# BOOKING API ENDPOINTS
# ===============================

@api_bp.route('/api/bookings/calendar')
@login_required
def api_get_calendar_events():
    """Get calendar events for booking calendar"""
    try:
        # Get date range filters if provided
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        room_id = request.args.get('room_id', type=int)
        
        events = get_booking_calendar_events_supabase()
        
        # Filter events if parameters provided
        if start_date or end_date or room_id:
            filtered_events = []
            for event in events:
                # Filter by date range
                if start_date and event.get('start'):
                    if event['start'] < start_date:
                        continue
                
                if end_date and event.get('end'):
                    if event['end'] > end_date:
                        continue
                
                # Filter by room
                if room_id and event.get('extendedProps', {}).get('roomId') != room_id:
                    continue
                
                filtered_events.append(event)
            
            events = filtered_events
        
        # Log API access
        log_user_activity(
            ActivityTypes.API_CALL,
            "Fetched calendar events via API",
            resource_type='api',
            metadata={'events_count': len(events)}
        )
        
        return jsonify(events)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get calendar events: {e}")
        return jsonify([])

@api_bp.route('/api/bookings/<int:booking_id>')
@login_required
def api_get_booking(booking_id):
    """Get specific booking details"""
    try:
        booking = get_booking_with_details(booking_id)
        
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Calculate totals
        totals = calculate_booking_totals(booking)
        booking['calculated_totals'] = totals
        
        return jsonify(booking)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get booking {booking_id}: {e}")
        return jsonify({'error': 'Failed to get booking details'}), 500

@api_bp.route('/api/bookings/<int:booking_id>/pricing')
@login_required
def api_calculate_booking_pricing(booking_id):
    """Calculate pricing for a booking"""
    try:
        booking = get_booking_with_details(booking_id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        totals = calculate_booking_totals(booking)
        
        return jsonify({
            'booking_id': booking_id,
            'totals': totals,
            'room_rate': totals.get('room_rate', 0),
            'addons_total': totals.get('addons_total', 0),
            'total': totals.get('total', 0),
            'duration_hours': totals.get('duration_hours', 0),
            'rate_type': totals.get('rate_type', 'Unknown')
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate booking pricing: {e}")
        return jsonify({'error': 'Failed to calculate pricing'}), 500

@api_bp.route('/api/bookings/recent')
@login_required
def api_recent_bookings():
    """Get recent bookings for dashboard"""
    try:
        limit = request.args.get('limit', 5, type=int)
        
        response = supabase_admin.table('bookings').select("""
            id, title, status, start_time, total_price, created_at,
            client:clients(contact_person, company_name),
            room:rooms(name)
        """).order('created_at', desc=True).limit(limit).execute()
        
        bookings = response.data if response.data else []
        
        # Format for frontend
        recent_bookings = []
        for booking in bookings:
            client = booking.get('client', {})
            room = booking.get('room', {})
            
            # Format datetime
            created_at_formatted = 'Unknown'
            try:
                if booking.get('created_at'):
                    created_dt = datetime.fromisoformat(booking['created_at'].replace('Z', ''))
                    created_at_formatted = created_dt.strftime('%Y-%m-%d %H:%M')
            except:
                pass
            
            recent_bookings.append({
                'id': booking.get('id'),
                'title': booking.get('title', 'Unknown Event'),
                'status': booking.get('status', 'tentative'),
                'start_time': booking.get('start_time'),
                'created_at': created_at_formatted,
                'total_price': booking.get('total_price', 0),
                'client_name': client.get('company_name') or client.get('contact_person', 'Unknown Client'),
                'room_name': room.get('name', 'Unknown Room')
            })
        
        return jsonify(recent_bookings)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get recent bookings: {e}")
        return jsonify([])

# ===============================
# STATISTICS API ENDPOINTS
# ===============================

@api_bp.route('/api/stats/dashboard')
@login_required
def api_dashboard_stats():
    """Get comprehensive dashboard statistics"""
    try:
        # Get basic counts
        bookings_response = supabase_admin.table('bookings').select('id, status, total_price, created_at').execute()
        bookings = bookings_response.data if bookings_response.data else []
        
        clients_response = supabase_admin.table('clients').select('id').execute()
        clients_count = len(clients_response.data) if clients_response.data else 0
        
        rooms_response = supabase_admin.table('rooms').select('id, status').execute()
        rooms = rooms_response.data if rooms_response.data else []
        
        # Calculate stats
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.get('status') == 'confirmed'])
        tentative_bookings = len([b for b in bookings if b.get('status') == 'tentative'])
        cancelled_bookings = len([b for b in bookings if b.get('status') == 'cancelled'])
        
        # Calculate revenue
        total_revenue = sum(float(b.get('total_price', 0)) for b in bookings if b.get('status') == 'confirmed')
        
        # This month's stats
        current_month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_bookings = []
        this_month_revenue = 0
        
        for b in bookings:
            if b.get('created_at'):
                try:
                    created_date = datetime.fromisoformat(b['created_at'].replace('Z', ''))
                    if created_date >= current_month:
                        this_month_bookings.append(b)
                        if b.get('status') == 'confirmed':
                            this_month_revenue += float(b.get('total_price', 0))
                except:
                    continue
        
        # Room stats
        available_rooms = len([r for r in rooms if r.get('status') == 'available'])
        maintenance_rooms = len([r for r in rooms if r.get('status') == 'maintenance'])
        
        return jsonify({
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed_bookings,
            'tentative_bookings': tentative_bookings,
            'cancelled_bookings': cancelled_bookings,
            'this_month_bookings': len(this_month_bookings),
            'total_clients': clients_count,
            'available_rooms': available_rooms,
            'maintenance_rooms': maintenance_rooms,
            'total_rooms': len(rooms),
            'total_revenue': round(total_revenue, 2),
            'this_month_revenue': round(this_month_revenue, 2),
            'occupancy_rate': round((confirmed_bookings / max(total_bookings, 1)) * 100, 1),
            'average_booking_value': round(total_revenue / max(confirmed_bookings, 1), 2)
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get dashboard stats: {e}")
        return jsonify({'error': 'Failed to get statistics'}), 500

@api_bp.route('/api/dashboard/refresh')
@login_required
def api_dashboard_refresh():
    """Refresh dashboard data - returns updated statistics for AJAX refresh"""
    try:
        from core import get_dashboard_stats
        
        # Get comprehensive stats using the core function
        stats = get_dashboard_stats()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.now(UTC).isoformat(),
            'message': 'Dashboard data refreshed successfully'
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to refresh dashboard: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to refresh dashboard data',
            'message': str(e)
        }), 500

@api_bp.route('/api/stats/revenue-trends')
@login_required
def api_revenue_trends():
    """Get revenue trends over time"""
    try:
        days = request.args.get('days', 30, type=int)
        
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
        
        return jsonify({
            'dates': dates,
            'revenues': revenues,
            'total_revenue': sum(revenues),
            'average_daily': sum(revenues) / len(revenues) if revenues else 0,
            'max_daily': max(revenues) if revenues else 0,
            'period_days': days
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue trends: {e}")
        return jsonify({
            'dates': [],
            'revenues': [],
            'total_revenue': 0,
            'average_daily': 0,
            'max_daily': 0,
            'period_days': days
        })

# ===============================
# ADDON API ENDPOINTS
# ===============================

@api_bp.route('/api/addons')
@login_required
def api_get_addons():
    """Get all available addons"""
    try:
        response = supabase_admin.table('addons').select("""
            id, name, description, price, is_active,
            category:addon_categories(id, name)
        """).eq('is_active', True).order('name').execute()
        
        addons = response.data if response.data else []
        
        # Format for frontend
        formatted_addons = []
        for addon in addons:
            category = addon.get('category', {})
            formatted_addons.append({
                'id': addon.get('id'),
                'name': addon.get('name'),
                'description': addon.get('description'),
                'price': float(addon.get('price', 0)),
                'is_active': addon.get('is_active', True),
                'category_id': category.get('id'),
                'category_name': category.get('name', 'Other')
            })
        
        return jsonify(formatted_addons)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get addons: {e}")
        return jsonify([])

@api_bp.route('/api/addons/categories')
@login_required
def api_get_addon_categories():
    """Get all addon categories"""
    try:
        response = supabase_admin.table('addon_categories').select('*').order('name').execute()
        categories = response.data if response.data else []
        
        return jsonify(categories)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get addon categories: {e}")
        return jsonify([])

# ===============================
# UTILITY API ENDPOINTS
# ===============================

@api_bp.route('/api/calculate-pricing')
@login_required
def api_calculate_pricing():
    """Calculate pricing for booking parameters"""
    try:
        room_id = request.args.get('room_id', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        addon_ids = request.args.getlist('addon_ids', type=int)
        
        if not all([room_id, start_time, end_time]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        from datetime import datetime
        from core import calculate_booking_total
        
        # Parse datetime strings
        start_dt = datetime.fromisoformat(start_time.replace('Z', ''))
        end_dt = datetime.fromisoformat(end_time.replace('Z', ''))
        
        # Calculate total
        total = calculate_booking_total(room_id, start_dt, end_dt, addon_ids)
        
        # Get room details for breakdown
        room_data = supabase_select('rooms', filters=[('id', 'eq', room_id)])
        room = room_data[0] if room_data else {}
        
        # Calculate duration and rate type
        duration_hours = (end_dt - start_dt).total_seconds() / 3600
        
        if duration_hours <= 4:
            rate_type = "Hourly Rate"
            room_rate = float(room.get('hourly_rate', 0)) * duration_hours
        elif duration_hours <= 6:
            rate_type = "Half-day Rate"
            room_rate = float(room.get('half_day_rate', 0))
        else:
            rate_type = "Full-day Rate"
            room_rate = float(room.get('full_day_rate', 0))
        
        # Calculate addons total
        addons_total = 0
        addon_items = []
        
        if addon_ids:
            for addon_id in addon_ids:
                addon_data = supabase_select('addons', filters=[('id', 'eq', addon_id)])
                if addon_data:
                    addon = addon_data[0]
                    price = float(addon.get('price', 0))
                    addons_total += price
                    addon_items.append({
                        'id': addon_id,
                        'name': addon.get('name'),
                        'price': price
                    })
        
        return jsonify({
            'room_rate': round(room_rate, 2),
            'rate_type': rate_type,
            'addons_total': round(addons_total, 2),
            'addon_items': addon_items,
            'duration_hours': round(duration_hours, 1),
            'total': round(total, 2)
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate pricing: {e}")
        return jsonify({'error': 'Failed to calculate pricing'}), 500

@api_bp.route('/api/health')
@login_required
def api_health_check():
    """API health check endpoint"""
    try:
        # Test database connection
        test_response = supabase_admin.table('rooms').select('id').limit(1).execute()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(UTC).isoformat(),
            'database_connected': True,
            'user_authenticated': current_user.is_authenticated,
            'user_id': current_user.id if current_user.is_authenticated else None
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now(UTC).isoformat(),
            'database_connected': False,
            'error': str(e)
        }), 500

# ===============================
# ERROR HANDLERS
# ===============================

@api_bp.errorhandler(400)
def api_bad_request(error):
    return jsonify({'error': 'Bad request', 'message': str(error)}), 400

@api_bp.errorhandler(404)
def api_not_found(error):
    return jsonify({'error': 'Not found', 'message': 'Resource not found'}), 404

@api_bp.errorhandler(500)
def api_internal_error(error):
    return jsonify({'error': 'Internal server error', 'message': 'Something went wrong'}), 500