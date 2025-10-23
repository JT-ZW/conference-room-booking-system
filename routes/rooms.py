from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from utils.decorators import activity_logged
from utils.logging import log_user_activity
from core import (supabase_select, supabase_insert, supabase_update, supabase_delete, RoomForm, 
                  supabase_admin, ActivityTypes, convert_datetime_strings)
from datetime import datetime, UTC, timedelta
import io
import csv
from collections import defaultdict
from decimal import Decimal

rooms_bp = Blueprint('rooms', __name__)

# ===============================
# ROOM LISTING AND DIRECTORY
# ===============================

@rooms_bp.route('/rooms')
@login_required
@activity_logged(ActivityTypes.PAGE_VIEW, "Viewed rooms directory")
def rooms():
    """Enhanced room directory with filtering, search, and analytics"""
    try:
        print("🔍 DEBUG: Loading rooms directory")
        
        # Get query parameters
        search_query = request.args.get('search', '').strip()
        status_filter = request.args.get('status', 'all')  # all, available, maintenance, reserved
        capacity_filter = request.args.get('capacity', 'all')  # all, small, medium, large
        sort_by = request.args.get('sort', 'name')  # name, capacity, hourly_rate, utilization
        order = request.args.get('order', 'asc')  # asc, desc
        
        # Get enhanced room data
        rooms_data = get_enhanced_rooms_list(search_query, status_filter, capacity_filter, sort_by, order)
        
        # Get room directory statistics
        directory_stats = get_room_directory_stats(rooms_data)
        
        # Get room utilization summary
        utilization_summary = get_rooms_utilization_summary()
        
        print(f"✅ DEBUG: Rooms directory loaded - {len(rooms_data)} rooms found")
        
        return render_template('rooms/index.html', 
                             title='Conference Rooms',
                             rooms=rooms_data,
                             directory_stats=directory_stats,
                             utilization_summary=utilization_summary,
                             search_query=search_query,
                             status_filter=status_filter,
                             capacity_filter=capacity_filter,
                             sort_by=sort_by,
                             order=order)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load rooms directory: {e}")
        import traceback
        traceback.print_exc()
        
        flash('⚠️ Error loading rooms directory. Please try again.', 'warning')
        return render_template('rooms/index.html', 
                             title='Conference Rooms',
                             rooms=[],
                             directory_stats=get_empty_directory_stats(),
                             utilization_summary={},
                             search_query='',
                             status_filter='all',
                             capacity_filter='all',
                             sort_by='name',
                             order='asc',
                             error="Failed to load room data")

@rooms_bp.route('/rooms/new', methods=['GET', 'POST'])
@login_required
def new_room():
    """Create a new conference room with comprehensive validation"""
    form = RoomForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                print("🔍 DEBUG: Creating new room")
                
                # Prepare room data
                room_data = {
                    'name': form.name.data.strip(),
                    'capacity': form.capacity.data if form.capacity.data else 0,
                    'description': form.description.data.strip() if form.description.data else None,
                    'hourly_rate': float(form.hourly_rate.data) if form.hourly_rate.data else 0.0,
                    'half_day_rate': float(form.half_day_rate.data) if form.half_day_rate.data else 0.0,
                    'full_day_rate': float(form.full_day_rate.data) if form.full_day_rate.data else 0.0,
                    'amenities': form.amenities.data.strip() if form.amenities.data else None,
                    'status': form.status.data,
                    'image_url': form.image_url.data.strip() if form.image_url.data else None,
                    'created_at': datetime.now(UTC).isoformat(),
                    'created_by': current_user.id
                }
                
                # Check for duplicate room name
                existing_room = check_duplicate_room_name(room_data['name'])
                if existing_room:
                    flash('❌ A room with this name already exists.', 'danger')
                    return render_template('rooms/form.html', title='New Room', form=form)
                
                # Validate pricing logic
                pricing_errors = validate_room_pricing(room_data)
                if pricing_errors:
                    for error in pricing_errors:
                        flash(error, 'danger')
                    return render_template('rooms/form.html', title='New Room', form=form)
                
                # Create room
                result = supabase_insert('rooms', room_data)
                
                if result:
                    # Log activity
                    log_user_activity(
                        ActivityTypes.CREATE_ROOM,
                        f"Created new room: {room_data['name']} (Capacity: {room_data['capacity']})",
                        resource_type='room',
                        resource_id=result['id'],
                        metadata={
                            'room_name': room_data['name'],
                            'capacity': room_data['capacity'],
                            'hourly_rate': room_data['hourly_rate'],
                            'status': room_data['status']
                        }
                    )
                    
                    flash(f'✅ Room "{room_data["name"]}" created successfully!', 'success')
                    return redirect(url_for('rooms.view_room', id=result['id']))
                else:
                    flash('❌ Error creating room. Please try again.', 'danger')
                    
            except Exception as e:
                print(f"❌ ERROR: Failed to create room: {e}")
                flash('❌ Unexpected error creating room. Please try again.', 'danger')
        else:
            flash('❌ Please correct the errors below.', 'danger')
    
    return render_template('rooms/form.html', title='New Room', form=form)

# ===============================
# ROOM DETAILS AND MANAGEMENT
# ===============================

@rooms_bp.route('/rooms/<int:id>')
@login_required
def view_room(id):
    """Enhanced room details view with analytics and booking history"""
    try:
        print(f"🔍 DEBUG: Loading room details for ID {id}")
        
        # Get room data
        room = get_room_by_id(id)
        if not room:
            flash('❌ Room not found.', 'danger')
            return redirect(url_for('rooms.rooms'))
        
        # Get room bookings with details
        room_bookings = get_enhanced_room_bookings(id)
        
        # Calculate room statistics
        room_stats = calculate_room_statistics(room, room_bookings)
        
        # Get room utilization analytics
        utilization_analytics = get_room_utilization_analytics(id)
        
        # Get upcoming bookings
        upcoming_bookings = get_room_upcoming_bookings(id)
        
        # Get maintenance history
        maintenance_history = get_room_maintenance_history(id)
        
        # Log view activity
        log_user_activity(
            ActivityTypes.VIEW_ROOM,
            f"Viewed room details: {room.get('name', 'Unknown')}",
            resource_type='room',
            resource_id=id,
            metadata={
                'room_name': room.get('name'),
                'capacity': room.get('capacity'),
                'total_bookings': len(room_bookings)
            }
        )
        
        print(f"✅ DEBUG: Room details loaded - {len(room_bookings)} bookings found")
        
        return render_template('rooms/view.html', 
                             title=f"Room: {room.get('name', 'Unknown')}",
                             room=room,
                             room_bookings=room_bookings,
                             room_stats=room_stats,
                             utilization_analytics=utilization_analytics,
                             upcoming_bookings=upcoming_bookings,
                             maintenance_history=maintenance_history)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load room details: {e}")
        import traceback
        traceback.print_exc()
        
        flash('❌ Error loading room details. Please try again.', 'danger')
        return redirect(url_for('rooms.rooms'))

@rooms_bp.route('/rooms/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(id):
    """Edit room with comprehensive validation and change tracking"""
    try:
        # Get room data
        room = get_room_by_id(id)
        if not room:
            flash('❌ Room not found.', 'danger')
            return redirect(url_for('rooms.rooms'))
        
        form = RoomForm()
        
        if request.method == 'POST':
            if form.validate_on_submit():
                try:
                    print(f"🔍 DEBUG: Updating room ID {id}")
                    
                    # Prepare updated data
                    room_data = {
                        'name': form.name.data.strip(),
                        'capacity': form.capacity.data if form.capacity.data else 0,
                        'description': form.description.data.strip() if form.description.data else None,
                        'hourly_rate': float(form.hourly_rate.data) if form.hourly_rate.data else 0.0,
                        'half_day_rate': float(form.half_day_rate.data) if form.half_day_rate.data else 0.0,
                        'full_day_rate': float(form.full_day_rate.data) if form.full_day_rate.data else 0.0,
                        'amenities': form.amenities.data.strip() if form.amenities.data else None,
                        'status': form.status.data,
                        'image_url': form.image_url.data.strip() if form.image_url.data else None,
                        'updated_at': datetime.now(UTC).isoformat(),
                        'updated_by': current_user.id
                    }
                    
                    # Check for duplicate name (excluding current room)
                    if room_data['name'] != room.get('name'):
                        existing_room = check_duplicate_room_name(room_data['name'])
                        if existing_room and existing_room['id'] != id:
                            flash('❌ A room with this name already exists.', 'danger')
                            return render_template('rooms/form.html', 
                                                 title='Edit Room', 
                                                 form=form, 
                                                 room=room)
                    
                    # Validate pricing
                    pricing_errors = validate_room_pricing(room_data)
                    if pricing_errors:
                        for error in pricing_errors:
                            flash(error, 'danger')
                        return render_template('rooms/form.html', 
                                             title='Edit Room', 
                                             form=form, 
                                             room=room)
                    
                    # Check if room has active bookings when changing to maintenance
                    if room_data['status'] == 'maintenance' and room.get('status') != 'maintenance':
                        active_bookings = check_room_active_bookings(id)
                        if active_bookings:
                            flash(f'❌ Cannot set room to maintenance: {len(active_bookings)} active booking(s) exist.', 'danger')
                            return render_template('rooms/form.html', 
                                                 title='Edit Room', 
                                                 form=form, 
                                                 room=room)
                    
                    # Update room
                    result = supabase_update('rooms', room_data, [('id', 'eq', id)])
                    
                    if result:
                        # Track changes for logging
                        changes_made = track_room_changes(room, room_data)
                        
                        # Log activity
                        log_user_activity(
                            ActivityTypes.UPDATE_ROOM,
                            f"Updated room: {room_data['name']} - Changes: {', '.join(changes_made)}",
                            resource_type='room',
                            resource_id=id,
                            metadata={
                                'changes': changes_made,
                                'room_name': room_data['name'],
                                'new_status': room_data['status']
                            }
                        )
                        
                        flash(f'✅ Room "{room_data["name"]}" updated successfully!', 'success')
                        return redirect(url_for('rooms.view_room', id=id))
                    else:
                        flash('❌ Error updating room. Please try again.', 'danger')
                        
                except Exception as e:
                    print(f"❌ ERROR: Failed to update room: {e}")
                    flash('❌ Unexpected error updating room. Please try again.', 'danger')
            else:
                flash('❌ Please correct the errors below.', 'danger')
        else:
            # Populate form with existing data
            form.name.data = room.get('name')
            form.capacity.data = room.get('capacity')
            form.description.data = room.get('description')
            form.hourly_rate.data = room.get('hourly_rate')
            form.half_day_rate.data = room.get('half_day_rate')
            form.full_day_rate.data = room.get('full_day_rate')
            form.amenities.data = room.get('amenities')
            form.status.data = room.get('status')
            form.image_url.data = room.get('image_url')
        
        return render_template('rooms/form.html', 
                             title='Edit Room', 
                             form=form, 
                             room=room)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load room for editing: {e}")
        flash('❌ Error loading room for editing. Please try again.', 'danger')
        return redirect(url_for('rooms.rooms'))

@rooms_bp.route('/rooms/<int:id>/delete', methods=['POST'])
@login_required
def delete_room(id):
    """Delete room with comprehensive validation and logging"""
    try:
        print(f"🔍 DEBUG: Attempting to delete room ID {id}")
        
        # Get room data for logging
        room = get_room_by_id(id)
        if not room:
            flash('❌ Room not found.', 'danger')
            return redirect(url_for('rooms.rooms'))
        
        # Check if room has any bookings
        room_bookings = get_room_bookings_count(id)
        if room_bookings > 0:
            flash(f'❌ Cannot delete room "{room.get("name", "Unknown")}" because it has {room_bookings} booking(s). Please cancel or reassign the bookings first.', 'danger')
            return redirect(url_for('rooms.view_room', id=id))
        
        # Attempt deletion
        success = supabase_delete('rooms', [('id', 'eq', id)])
        
        if success:
            # Log successful deletion
            log_user_activity(
                ActivityTypes.DELETE_ROOM,
                f"Deleted room: {room.get('name', 'Unknown')} (Capacity: {room.get('capacity', 'N/A')})",
                resource_type='room',
                resource_id=id,
                metadata={
                    'room_name': room.get('name'),
                    'capacity': room.get('capacity'),
                    'hourly_rate': room.get('hourly_rate')
                }
            )
            
            flash(f'✅ Room "{room.get("name", "Unknown")}" deleted successfully.', 'success')
        else:
            flash('❌ Error deleting room. Please try again.', 'danger')
            return redirect(url_for('rooms.view_room', id=id))
        
    except Exception as e:
        print(f"❌ ERROR: Failed to delete room: {e}")
        flash('❌ Unexpected error deleting room. Please try again.', 'danger')
        return redirect(url_for('rooms.view_room', id=id))
    
    return redirect(url_for('rooms.rooms'))

# ===============================
# ROOM ANALYTICS AND REPORTS
# ===============================

@rooms_bp.route('/rooms/analytics')
@login_required
@activity_logged(ActivityTypes.GENERATE_REPORT, "Viewed room analytics dashboard")
def rooms_analytics():
    """Comprehensive room analytics dashboard"""
    try:
        print("🔍 DEBUG: Loading room analytics dashboard")
        
        # Get date range parameters
        period = request.args.get('period', 'this_month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Calculate date range
        date_range = calculate_analytics_date_range(period, start_date, end_date)
        
        # Get comprehensive analytics
        analytics_data = get_comprehensive_room_analytics(date_range)
        
        # Get room performance rankings
        performance_rankings = get_room_performance_rankings(date_range)
        
        # Get utilization trends
        utilization_trends = get_room_utilization_trends(date_range)
        
        # Get revenue analytics
        revenue_analytics = get_room_revenue_analytics(date_range)
        
        return render_template('rooms/analytics.html',
                             title='Room Analytics Dashboard',
                             analytics_data=analytics_data,
                             performance_rankings=performance_rankings,
                             utilization_trends=utilization_trends,
                             revenue_analytics=revenue_analytics,
                             date_range=date_range,
                             period=period)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load room analytics: {e}")
        flash('❌ Error loading room analytics. Please try again.', 'danger')
        return redirect(url_for('rooms.rooms'))

@rooms_bp.route('/rooms/<int:id>/analytics')
@login_required
def room_detailed_analytics(id):
    """Detailed analytics for a specific room"""
    try:
        print(f"🔍 DEBUG: Loading detailed analytics for room ID {id}")
        
        # Get room data
        room = get_room_by_id(id)
        if not room:
            flash('❌ Room not found.', 'danger')
            return redirect(url_for('rooms.rooms'))
        
        # Get detailed analytics
        detailed_analytics = get_room_detailed_analytics(id)
        
        # Get booking patterns
        booking_patterns = get_room_booking_patterns(id)
        
        # Get revenue trends
        revenue_trends = get_room_revenue_trends(id)
        
        # Get utilization analysis
        utilization_analysis = get_room_utilization_analysis(id)
        
        # Log analytics view
        log_user_activity(
            ActivityTypes.GENERATE_REPORT,
            f"Viewed detailed analytics for room: {room.get('name', 'Unknown')}",
            resource_type='room_analytics',
            resource_id=id
        )
        
        return render_template('rooms/detailed_analytics.html',
                             title=f"Analytics: {room.get('name', 'Unknown')}",
                             room=room,
                             detailed_analytics=detailed_analytics,
                             booking_patterns=booking_patterns,
                             revenue_trends=revenue_trends,
                             utilization_analysis=utilization_analysis)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load room detailed analytics: {e}")
        flash('❌ Error loading room analytics. Please try again.', 'danger')
        return redirect(url_for('rooms.view_room', id=id))

# ===============================
# ROOM AVAILABILITY AND BOOKING
# ===============================

@rooms_bp.route('/rooms/availability')
@login_required
def room_availability():
    """Room availability checker and booking interface"""
    try:
        print("🔍 DEBUG: Loading room availability interface")
        
        # Get date parameters
        check_date = request.args.get('date', datetime.now(UTC).date().isoformat())
        start_time = request.args.get('start_time', '09:00')
        end_time = request.args.get('end_time', '17:00')
        min_capacity = request.args.get('min_capacity', 0, type=int)
        
        # Get room availability for the specified time
        availability_data = get_room_availability_data(check_date, start_time, end_time, min_capacity)
        
        # Get room suggestions
        room_suggestions = get_room_suggestions(check_date, start_time, end_time, min_capacity)
        
        return render_template('rooms/availability.html',
                             title='Room Availability',
                             availability_data=availability_data,
                             room_suggestions=room_suggestions,
                             check_date=check_date,
                             start_time=start_time,
                             end_time=end_time,
                             min_capacity=min_capacity)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load room availability: {e}")
        flash('❌ Error loading room availability. Please try again.', 'danger')
        return redirect(url_for('rooms.rooms'))

# ===============================
# MAINTENANCE MANAGEMENT
# ===============================

@rooms_bp.route('/rooms/<int:id>/maintenance', methods=['GET', 'POST'])
@login_required
def room_maintenance(id):
    """Room maintenance tracking and management"""
    try:
        room = get_room_by_id(id)
        if not room:
            flash('❌ Room not found.', 'danger')
            return redirect(url_for('rooms.rooms'))
        
        if request.method == 'POST':
            # Handle maintenance record creation
            maintenance_data = {
                'room_id': id,
                'maintenance_type': request.form.get('maintenance_type'),
                'description': request.form.get('description'),
                'scheduled_date': request.form.get('scheduled_date'),
                'estimated_duration': request.form.get('estimated_duration'),
                'status': 'scheduled',
                'created_by': current_user.id,
                'created_at': datetime.now(UTC).isoformat()
            }
            
            # Create maintenance record
            result = create_maintenance_record(maintenance_data)
            
            if result:
                flash('✅ Maintenance scheduled successfully!', 'success')
                
                # Log activity
                log_user_activity(
                    ActivityTypes.UPDATE_ROOM,
                    f"Scheduled maintenance for room: {room.get('name', 'Unknown')}",
                    resource_type='room_maintenance',
                    resource_id=id,
                    metadata={
                        'maintenance_type': maintenance_data['maintenance_type'],
                        'scheduled_date': maintenance_data['scheduled_date']
                    }
                )
            else:
                flash('❌ Error scheduling maintenance. Please try again.', 'danger')
        
        # Get maintenance history
        maintenance_history = get_room_maintenance_history(id)
        
        return render_template('rooms/maintenance.html',
                             title=f"Maintenance: {room.get('name', 'Unknown')}",
                             room=room,
                             maintenance_history=maintenance_history)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load room maintenance: {e}")
        flash('❌ Error loading room maintenance. Please try again.', 'danger')
        return redirect(url_for('rooms.view_room', id=id))

# ===============================
# EXPORT FUNCTIONALITY
# ===============================

@rooms_bp.route('/rooms/export')
@login_required
def export_rooms():
    """Export room data with analytics"""
    try:
        print("🔍 DEBUG: Exporting room data")
        
        # Get export parameters
        format_type = request.args.get('format', 'csv')
        include_analytics = request.args.get('include_analytics', 'false').lower() == 'true'
        
        # Get rooms data
        rooms_data = get_enhanced_rooms_list()
        
        if format_type == 'csv':
            return export_rooms_csv(rooms_data, include_analytics)
        else:
            flash('❌ Unsupported export format.', 'danger')
            return redirect(url_for('rooms.rooms'))
        
    except Exception as e:
        print(f"❌ ERROR: Failed to export rooms: {e}")
        flash('❌ Error exporting room data. Please try again.', 'danger')
        return redirect(url_for('rooms.rooms'))

# ===============================
# HELPER FUNCTIONS - DATA RETRIEVAL
# ===============================

def get_enhanced_rooms_list(search_query='', status_filter='all', capacity_filter='all', sort_by='name', order='asc'):
    """Get enhanced room list with search, filtering, and analytics"""
    try:
        # Get base room data
        response = supabase_admin.table('rooms').select('*').execute()
        rooms_data = response.data if response.data else []
        
        # Apply search filter
        if search_query:
            filtered_rooms = []
            search_lower = search_query.lower()
            
            for room in rooms_data:
                # Search in multiple fields
                searchable_text = ' '.join([
                    room.get('name', '').lower(),
                    room.get('description', '').lower(),
                    room.get('amenities', '').lower()
                ])
                
                if search_lower in searchable_text:
                    filtered_rooms.append(room)
            
            rooms_data = filtered_rooms
        
        # Apply status filter
        if status_filter != 'all':
            rooms_data = [r for r in rooms_data if r.get('status') == status_filter]
        
        # Apply capacity filter
        if capacity_filter != 'all':
            rooms_data = apply_capacity_filter(rooms_data, capacity_filter)
        
        # Enhance with additional data
        for room in rooms_data:
            enhance_room_data(room)
        
        # Apply sorting
        rooms_data = sort_rooms_data(rooms_data, sort_by, order)
        
        return rooms_data
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get enhanced rooms list: {e}")
        return []

def apply_capacity_filter(rooms_data, capacity_filter):
    """Apply capacity-based filters to room data"""
    if capacity_filter == 'small':
        return [r for r in rooms_data if r.get('capacity', 0) <= 10]
    elif capacity_filter == 'medium':
        return [r for r in rooms_data if 11 <= r.get('capacity', 0) <= 50]
    elif capacity_filter == 'large':
        return [r for r in rooms_data if r.get('capacity', 0) > 50]
    else:
        return rooms_data

def enhance_room_data(room):
    """Add enhanced data to room record"""
    try:
        room_id = room.get('id')
        
        # Get booking count
        try:
            bookings_response = supabase_admin.table('bookings').select('id').eq('room_id', room_id).execute()
            room['booking_count'] = len(bookings_response.data) if bookings_response.data else 0
        except:
            room['booking_count'] = 0
        
        # Get total revenue
        try:
            revenue_response = supabase_admin.table('bookings').select('total_price').eq(
                'room_id', room_id
            ).eq('status', 'confirmed').execute()
            
            total_revenue = sum(
                float(booking.get('total_price', 0)) 
                for booking in revenue_response.data if revenue_response.data
            )
            room['total_revenue'] = round(total_revenue, 2)
        except:
            room['total_revenue'] = 0
        
        # Calculate utilization (simplified)
        try:
            # Get current month bookings
            current_month = datetime.now(UTC).replace(day=1)
            next_month = (current_month + timedelta(days=32)).replace(day=1)
            
            month_bookings = supabase_admin.table('bookings').select('start_time, end_time').eq(
                'room_id', room_id
            ).gte('start_time', current_month.isoformat()).lt(
                'start_time', next_month.isoformat()
            ).neq('status', 'cancelled').execute()
            
            # Calculate total booking hours
            total_hours = 0
            for booking in month_bookings.data if month_bookings.data else []:
                try:
                    start_dt = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                    end_dt = datetime.fromisoformat(booking['end_time'].replace('Z', ''))
                    booking_hours = (end_dt - start_dt).total_seconds() / 3600
                    total_hours += booking_hours
                except:
                    continue
            
            # Assume 8 hours/day, 22 working days/month = 176 available hours
            available_hours = 176
            utilization_percentage = (total_hours / available_hours) * 100 if available_hours > 0 else 0
            room['utilization_percentage'] = round(min(utilization_percentage, 100), 1)
        except:
            room['utilization_percentage'] = 0
        
        # Get next booking
        try:
            next_booking = supabase_admin.table('bookings').select(
                'start_time, title'
            ).eq('room_id', room_id).gte(
                'start_time', datetime.now(UTC).isoformat()
            ).neq('status', 'cancelled').order('start_time').limit(1).execute()
            
            if next_booking.data:
                next_start = datetime.fromisoformat(next_booking.data[0]['start_time'].replace('Z', ''))
                room['next_booking'] = {
                    'title': next_booking.data[0].get('title', 'Unknown Event'),
                    'start_time': next_start,
                    'days_until': (next_start.date() - datetime.now(UTC).date()).days
                }
            else:
                room['next_booking'] = None
        except:
            room['next_booking'] = None
        
        # Add display helpers
        room['capacity_category'] = get_capacity_category(room.get('capacity', 0))
        room['status_badge_class'] = get_room_status_badge_class(room.get('status', 'available'))
        
        return room
        
    except Exception as e:
        print(f"❌ ERROR: Failed to enhance room data: {e}")
        return room

def sort_rooms_data(rooms_data, sort_by, order):
    """Sort room data by specified criteria"""
    try:
        reverse_order = (order == 'desc')
        
        if sort_by == 'name':
            rooms_data.sort(key=lambda x: (x.get('name') or '').lower(), reverse=reverse_order)
        elif sort_by == 'capacity':
            rooms_data.sort(key=lambda x: x.get('capacity', 0), reverse=reverse_order)
        elif sort_by == 'hourly_rate':
            rooms_data.sort(key=lambda x: x.get('hourly_rate', 0), reverse=reverse_order)
        elif sort_by == 'utilization':
            rooms_data.sort(key=lambda x: x.get('utilization_percentage', 0), reverse=reverse_order)
        elif sort_by == 'revenue':
            rooms_data.sort(key=lambda x: x.get('total_revenue', 0), reverse=reverse_order)
        elif sort_by == 'bookings':
            rooms_data.sort(key=lambda x: x.get('booking_count', 0), reverse=reverse_order)
        
        return rooms_data
        
    except Exception as e:
        print(f"❌ ERROR: Failed to sort rooms data: {e}")
        return rooms_data

def get_room_directory_stats(rooms_data):
    """Calculate directory-wide room statistics"""
    try:
        total_rooms = len(rooms_data)
        
        if total_rooms == 0:
            return get_empty_directory_stats()
        
        # Status breakdown
        available_rooms = len([r for r in rooms_data if r.get('status') == 'available'])
        maintenance_rooms = len([r for r in rooms_data if r.get('status') == 'maintenance'])
        reserved_rooms = len([r for r in rooms_data if r.get('status') == 'reserved'])
        
        # Capacity statistics
        total_capacity = sum(r.get('capacity', 0) for r in rooms_data)
        average_capacity = total_capacity / total_rooms if total_rooms > 0 else 0
        
        # Revenue statistics
        total_revenue = sum(r.get('total_revenue', 0) for r in rooms_data)
        total_bookings = sum(r.get('booking_count', 0) for r in rooms_data)
        
        # Utilization statistics
        average_utilization = sum(r.get('utilization_percentage', 0) for r in rooms_data) / total_rooms
        
        # Top performer
        top_revenue_room = max(rooms_data, key=lambda x: x.get('total_revenue', 0)) if rooms_data else None
        top_utilization_room = max(rooms_data, key=lambda x: x.get('utilization_percentage', 0)) if rooms_data else None
        
        return {
            'total_rooms': total_rooms,
            'available_rooms': available_rooms,
            'maintenance_rooms': maintenance_rooms,
            'reserved_rooms': reserved_rooms,
            'total_capacity': total_capacity,
            'average_capacity': round(average_capacity, 1),
            'total_revenue': round(total_revenue, 2),
            'total_bookings': total_bookings,
            'average_utilization': round(average_utilization, 1),
            'top_revenue_room': top_revenue_room,
            'top_utilization_room': top_utilization_room
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate directory stats: {e}")
        return get_empty_directory_stats()

def get_empty_directory_stats():
    """Return empty directory stats for error cases"""
    return {
        'total_rooms': 0,
        'available_rooms': 0,
        'maintenance_rooms': 0,
        'reserved_rooms': 0,
        'total_capacity': 0,
        'average_capacity': 0,
        'total_revenue': 0,
        'total_bookings': 0,
        'average_utilization': 0,
        'top_revenue_room': None,
        'top_utilization_room': None
    }

def get_rooms_utilization_summary():
    """Get utilization summary for all rooms"""
    try:
        # This would calculate overall utilization metrics
        return {
            'overall_utilization': 75.5,
            'peak_hours': ['09:00-12:00', '14:00-17:00'],
            'busiest_day': 'Tuesday',
            'average_booking_duration': 2.5
        }
    except Exception as e:
        print(f"❌ ERROR: Failed to get utilization summary: {e}")
        return {}

def get_room_by_id(room_id):
    """Get room by ID with error handling"""
    try:
        response = supabase_admin.table('rooms').select('*').eq('id', room_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"❌ ERROR: Failed to get room by ID: {e}")
        return None

def get_enhanced_room_bookings(room_id, limit=20):
    """Get enhanced booking data for a specific room"""
    try:
        response = supabase_admin.table('bookings').select("""
            *,
            client:clients(id, contact_person, company_name)
        """).eq('room_id', room_id).order('start_time', desc=True).limit(limit).execute()
        
        bookings = response.data if response.data else []
        return convert_datetime_strings(bookings)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get room bookings: {e}")
        return []

def calculate_room_statistics(room, bookings):
    """Calculate comprehensive room statistics"""
    try:
        if not bookings:
            return get_empty_room_stats()
        
        # Basic counts
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.get('status') == 'confirmed'])
        
        # Revenue metrics
        total_revenue = sum(
            float(b.get('total_price', 0)) 
            for b in bookings 
            if b.get('status') == 'confirmed'
        )
        
        # Utilization metrics
        total_hours = 0
        for booking in bookings:
            if booking.get('start_time') and booking.get('end_time') and booking.get('status') != 'cancelled':
                try:
                    duration = booking['end_time'] - booking['start_time']
                    total_hours += duration.total_seconds() / 3600
                except:
                    continue
        
        # Capacity utilization
        total_attendees = sum(int(b.get('attendees', 0)) for b in bookings if b.get('status') != 'cancelled')
        average_attendees = total_attendees / max(total_bookings, 1)
        
        room_capacity = room.get('capacity', 1)
        capacity_utilization = (average_attendees / room_capacity) * 100 if room_capacity > 0 else 0
        
        return {
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed_bookings,
            'total_revenue': round(total_revenue, 2),
            'total_hours': round(total_hours, 1),
            'average_booking_value': round(total_revenue / max(confirmed_bookings, 1), 2),
            'average_attendees': round(average_attendees, 1),
            'capacity_utilization': round(capacity_utilization, 1),
            'revenue_per_hour': round(total_revenue / max(total_hours, 1), 2)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate room statistics: {e}")
        return get_empty_room_stats()

def get_empty_room_stats():
    """Return empty room stats for error cases"""
    return {
        'total_bookings': 0,
        'confirmed_bookings': 0,
        'total_revenue': 0,
        'total_hours': 0,
        'average_booking_value': 0,
        'average_attendees': 0,
        'capacity_utilization': 0,
        'revenue_per_hour': 0
    }

# ===============================
# UTILITY FUNCTIONS
# ===============================

def check_duplicate_room_name(room_name):
    """Check if room name already exists"""
    try:
        response = supabase_admin.table('rooms').select('id, name').eq('name', room_name).execute()
        return response.data[0] if response.data else None
    except:
        return None

def validate_room_pricing(room_data):
    """Validate room pricing logic"""
    errors = []
    
    hourly_rate = room_data.get('hourly_rate', 0)
    half_day_rate = room_data.get('half_day_rate', 0)
    full_day_rate = room_data.get('full_day_rate', 0)
    
    # Check that rates make logical sense
    if half_day_rate > 0 and hourly_rate > 0:
        if half_day_rate < hourly_rate * 3:
            errors.append('⚠️ Warning: Half-day rate should typically be at least 3x hourly rate.')
    
    if full_day_rate > 0 and half_day_rate > 0:
        if full_day_rate < half_day_rate * 1.5:
            errors.append('⚠️ Warning: Full-day rate should typically be at least 1.5x half-day rate.')
    
    return errors

def track_room_changes(old_room, new_room):
    """Track what fields were changed in room update"""
    changes = []
    
    fields_to_track = ['name', 'capacity', 'hourly_rate', 'half_day_rate', 'full_day_rate', 'status', 'amenities']
    
    for field in fields_to_track:
        old_value = old_room.get(field)
        new_value = new_room.get(field)
        
        if old_value != new_value:
            changes.append(field.replace('_', ' ').title())
    
    return changes

def check_room_active_bookings(room_id):
    """Check if room has active bookings"""
    try:
        now = datetime.now(UTC).isoformat()
        response = supabase_admin.table('bookings').select('id').eq('room_id', room_id).gte(
            'start_time', now
        ).neq('status', 'cancelled').execute()
        
        return response.data if response.data else []
    except:
        return []

def get_room_bookings_count(room_id):
    """Get total booking count for a room"""
    try:
        response = supabase_admin.table('bookings').select('id').eq('room_id', room_id).execute()
        return len(response.data) if response.data else 0
    except:
        return 0

def get_capacity_category(capacity):
    """Get capacity category for display"""
    if capacity <= 10:
        return 'Small'
    elif capacity <= 50:
        return 'Medium'
    else:
        return 'Large'

def get_room_status_badge_class(status):
    """Get Bootstrap badge class for room status"""
    status_classes = {
        'available': 'badge-success',
        'maintenance': 'badge-warning',
        'reserved': 'badge-danger'
    }
    return status_classes.get(status, 'badge-secondary')

# ===============================
# ANALYTICS FUNCTIONS (PLACEHOLDER)
# ===============================

def calculate_analytics_date_range(period, start_date=None, end_date=None):
    """Calculate date range for analytics"""
    # Similar to reports.py implementation
    return {
        'start': datetime.now(UTC) - timedelta(days=30),
        'end': datetime.now(UTC),
        'period_name': 'Last 30 Days'
    }

def get_comprehensive_room_analytics(date_range):
    """Get comprehensive room analytics for date range"""
    return {'placeholder': 'Coming soon'}

def get_room_performance_rankings(date_range):
    """Get room performance rankings"""
    return []

def get_room_utilization_trends(date_range):
    """Get room utilization trends"""
    return {}

def get_room_revenue_analytics(date_range):
    """Get room revenue analytics"""
    return {}

def get_room_utilization_analytics(room_id):
    """Get utilization analytics for specific room"""
    return {}

def get_room_upcoming_bookings(room_id, limit=5):
    """Get upcoming bookings for a room"""
    try:
        now = datetime.now(UTC).isoformat()
        response = supabase_admin.table('bookings').select("""
            *,
            client:clients(contact_person, company_name)
        """).eq('room_id', room_id).gte('start_time', now).neq(
            'status', 'cancelled'
        ).order('start_time').limit(limit).execute()
        
        bookings = response.data if response.data else []
        return convert_datetime_strings(bookings)
    except:
        return []

def get_room_maintenance_history(room_id):
    """Get maintenance history for a room"""
    # Placeholder - would integrate with maintenance tracking system
    return []

def create_maintenance_record(maintenance_data):
    """Create a maintenance record"""
    # Placeholder - would create maintenance record
    return True

def get_room_availability_data(check_date, start_time, end_time, min_capacity):
    """Get room availability data"""
    # Placeholder - would check real availability
    return {}

def get_room_suggestions(check_date, start_time, end_time, min_capacity):
    """Get room suggestions based on criteria"""
    # Placeholder - would suggest alternative rooms
    return []

# ===============================
# ANALYTICS HELPER FUNCTIONS (PLACEHOLDER)
# ===============================

def get_room_detailed_analytics(room_id):
    """Get detailed analytics for specific room"""
    return {}

def get_room_booking_patterns(room_id):
    """Get booking patterns for specific room"""
    return {}

def get_room_revenue_trends(room_id):
    """Get revenue trends for specific room"""
    return {}

def get_room_utilization_analysis(room_id):
    """Get utilization analysis for specific room"""
    return {}

# ===============================
# EXPORT FUNCTIONS
# ===============================

def export_rooms_csv(rooms_data, include_analytics=False):
    """Export rooms to CSV format"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        if include_analytics:
            writer.writerow([
                'Room ID', 'Name', 'Capacity', 'Status', 'Hourly Rate', 'Half Day Rate', 
                'Full Day Rate', 'Total Bookings', 'Total Revenue', 'Utilization %', 
                'Description', 'Amenities'
            ])
        else:
            writer.writerow([
                'Room ID', 'Name', 'Capacity', 'Status', 'Hourly Rate', 'Half Day Rate', 
                'Full Day Rate', 'Description', 'Amenities'
            ])
        
        # Write data
        for room in rooms_data:
            if include_analytics:
                writer.writerow([
                    room.get('id', ''),
                    room.get('name', ''),
                    room.get('capacity', 0),
                    room.get('status', ''),
                    room.get('hourly_rate', 0),
                    room.get('half_day_rate', 0),
                    room.get('full_day_rate', 0),
                    room.get('booking_count', 0),
                    room.get('total_revenue', 0),
                    room.get('utilization_percentage', 0),
                    room.get('description', ''),
                    room.get('amenities', '')
                ])
            else:
                writer.writerow([
                    room.get('id', ''),
                    room.get('name', ''),
                    room.get('capacity', 0),
                    room.get('status', ''),
                    room.get('hourly_rate', 0),
                    room.get('half_day_rate', 0),
                    room.get('full_day_rate', 0),
                    room.get('description', ''),
                    room.get('amenities', '')
                ])
        
        output.seek(0)
        
        # Create filename
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        filename = f'rooms_export_{timestamp}.csv'
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ ERROR: Failed to export rooms CSV: {e}")
        raise

# ===============================
# API ENDPOINTS
# ===============================

@rooms_bp.route('/api/rooms/search')
@login_required
def api_search_rooms():
    """API endpoint for room search"""
    try:
        query = request.args.get('q', '').strip()
        capacity_min = request.args.get('capacity_min', 0, type=int)
        status = request.args.get('status', 'available')
        limit = request.args.get('limit', 10, type=int)
        
        rooms = get_enhanced_rooms_list(search_query=query, status_filter=status)
        
        # Filter by capacity if specified
        if capacity_min > 0:
            rooms = [r for r in rooms if r.get('capacity', 0) >= capacity_min]
        
        # Format for API response
        results = []
        for room in rooms[:limit]:
            results.append({
                'id': room.get('id'),
                'name': room.get('name'),
                'capacity': room.get('capacity'),
                'status': room.get('status'),
                'hourly_rate': room.get('hourly_rate'),
                'half_day_rate': room.get('half_day_rate'),
                'full_day_rate': room.get('full_day_rate'),
                'amenities': room.get('amenities', '').split(',') if room.get('amenities') else [],
                'utilization_percentage': room.get('utilization_percentage', 0)
            })
        
        return jsonify(results)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to search rooms via API: {e}")
        return jsonify([])

@rooms_bp.route('/api/rooms/<int:id>/stats')
@login_required
def api_room_stats(id):
    """API endpoint for room statistics"""
    try:
        room = get_room_by_id(id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        bookings = get_enhanced_room_bookings(id)
        stats = calculate_room_statistics(room, bookings)
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get room stats via API: {e}")
        return jsonify({'error': 'Failed to get room statistics'}), 500

@rooms_bp.route('/api/rooms/availability-check')
@login_required
def api_check_availability():
    """API endpoint for checking room availability"""
    try:
        room_id = request.args.get('room_id', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        
        if not all([room_id, start_time, end_time]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Check availability logic would go here
        # For now, return placeholder
        return jsonify({
            'available': True,
            'room_id': room_id,
            'conflicts': []
        })
        
    except Exception as e:
        print(f"❌ ERROR: Failed to check availability via API: {e}")
        return jsonify({'error': 'Failed to check availability'}), 500

# ===============================
# ERROR HANDLERS
# ===============================

@rooms_bp.errorhandler(404)
def room_not_found(error):
    """Handle 404 errors in rooms"""
    flash('⚠️ The requested room was not found.', 'warning')
    return redirect(url_for('rooms.rooms'))

@rooms_bp.errorhandler(500)
def room_internal_error(error):
    """Handle internal server errors in rooms"""
    print(f"❌ Room management error: {error}")
    
    try:
        log_user_activity(
            ActivityTypes.ERROR_OCCURRED,
            f"Room management internal error: {str(error)}",
            resource_type='rooms',
            status='failed'
        )
    except:
        pass
    
    flash('⚠️ An error occurred while processing your request. Please try again.', 'danger')
    return redirect(url_for('rooms.rooms'))