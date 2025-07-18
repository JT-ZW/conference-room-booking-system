from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from utils.logging import log_user_activity
from utils.decorators import activity_logged
from core import supabase_admin, convert_datetime_strings, ActivityTypes
from datetime import datetime, UTC, timedelta
import io
import csv
from collections import defaultdict
from decimal import Decimal

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

reports_bp = Blueprint('reports', __name__)

# ===============================
# MAIN REPORTS DASHBOARD
# ===============================

@reports_bp.route('/reports')
@login_required
@activity_logged(ActivityTypes.GENERATE_REPORT, "Accessed reports dashboard")
def reports():
    """Enhanced reports dashboard with quick stats and navigation"""
    try:
        print("🔍 DEBUG: Loading reports dashboard")
        
        # Get quick statistics for dashboard
        quick_stats = get_reports_quick_stats()
        
        # Get available date ranges
        date_ranges = get_available_date_ranges()
        
        print(f"✅ DEBUG: Reports dashboard loaded with stats")
        
        return render_template('reports/index.html', 
                             title='Reports Dashboard',
                             quick_stats=quick_stats,
                             date_ranges=date_ranges)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to load reports dashboard: {e}")
        import traceback
        traceback.print_exc()
        
        flash('⚠️ Error loading reports dashboard. Please try again.', 'warning')
        return render_template('reports/index.html', 
                             title='Reports Dashboard',
                             quick_stats=get_empty_quick_stats(),
                             date_ranges={},
                             error="Failed to load reports data")

# ===============================
# REVENUE REPORTS
# ===============================

@reports_bp.route('/reports/revenue')
@login_required
@activity_logged(ActivityTypes.GENERATE_REPORT, "Generated revenue report")
def revenue_report():
    """Comprehensive revenue report with analytics"""
    try:
        print("🔍 DEBUG: Generating revenue report")
        
        # Get date filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'this_month')
        
        # Calculate date range
        date_range = calculate_date_range(period, start_date, end_date)
        
        # Get revenue data
        revenue_data = get_revenue_analytics(date_range['start'], date_range['end'])
        
        # Get revenue by room
        revenue_by_room = get_revenue_by_room(date_range['start'], date_range['end'])
        
        # Get revenue by client
        revenue_by_client = get_revenue_by_client(date_range['start'], date_range['end'])
        
        # Get revenue trends
        revenue_trends = get_revenue_trends_detailed(date_range['start'], date_range['end'])
        
        report_data = {
            'summary': revenue_data,
            'by_room': revenue_by_room,
            'by_client': revenue_by_client,
            'trends': revenue_trends,
            'date_range': date_range,
            'period': period
        }
        
        print(f"✅ DEBUG: Revenue report generated successfully")
        
        return render_template('reports/revenue.html', 
                             title='Revenue Report',
                             report_data=report_data)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to generate revenue report: {e}")
        import traceback
        traceback.print_exc()
        
        flash('❌ Error generating revenue report. Please try again.', 'danger')
        return redirect(url_for('reports.reports'))

@reports_bp.route('/reports/revenue/export')
@login_required
def export_revenue_report():
    """Export revenue report as CSV or PDF"""
    try:
        # Get parameters
        format_type = request.args.get('format', 'csv')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'this_month')
        
        # Calculate date range
        date_range = calculate_date_range(period, start_date, end_date)
        
        # Get revenue data
        revenue_data = get_revenue_analytics(date_range['start'], date_range['end'])
        revenue_by_room = get_revenue_by_room(date_range['start'], date_range['end'])
        
        if format_type == 'pdf' and REPORTLAB_AVAILABLE:
            return export_revenue_pdf(revenue_data, revenue_by_room, date_range)
        else:
            return export_revenue_csv(revenue_data, revenue_by_room, date_range)
            
    except Exception as e:
        print(f"❌ ERROR: Failed to export revenue report: {e}")
        flash('❌ Error exporting report. Please try again.', 'danger')
        return redirect(url_for('reports.revenue_report'))

# ===============================
# CLIENT ANALYSIS REPORTS
# ===============================

@reports_bp.route('/reports/client-analysis')
@login_required
@activity_logged(ActivityTypes.GENERATE_REPORT, "Generated client analysis report")
def client_analysis_report():
    """Comprehensive client analysis with booking patterns and revenue"""
    try:
        print("🔍 DEBUG: Generating client analysis report")
        
        # Get date filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'this_year')
        
        # Calculate date range
        date_range = calculate_date_range(period, start_date, end_date)
        
        # Get client analytics
        client_analytics = get_client_analytics(date_range['start'], date_range['end'])
        
        # Get top clients by revenue
        top_clients_revenue = get_top_clients_by_revenue(date_range['start'], date_range['end'])
        
        # Get top clients by bookings
        top_clients_bookings = get_top_clients_by_bookings(date_range['start'], date_range['end'])
        
        # Get client retention data
        client_retention = get_client_retention_data(date_range['start'], date_range['end'])
        
        report_data = {
            'analytics': client_analytics,
            'top_revenue': top_clients_revenue,
            'top_bookings': top_clients_bookings,
            'retention': client_retention,
            'date_range': date_range,
            'period': period
        }
        
        print(f"✅ DEBUG: Client analysis report generated successfully")
        
        return render_template('reports/client_analysis.html', 
                             title='Client Analysis Report',
                             report_data=report_data)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to generate client analysis report: {e}")
        import traceback
        traceback.print_exc()
        
        flash('❌ Error generating client analysis report. Please try again.', 'danger')
        return redirect(url_for('reports.reports'))

# ===============================
# ROOM UTILIZATION REPORTS
# ===============================

@reports_bp.route('/reports/room-utilization')
@login_required
@activity_logged(ActivityTypes.GENERATE_REPORT, "Generated room utilization report")
def room_utilization_report():
    """Comprehensive room utilization analysis"""
    try:
        print("🔍 DEBUG: Generating room utilization report")
        
        # Get date filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'this_month')
        
        # Calculate date range
        date_range = calculate_date_range(period, start_date, end_date)
        
        # Get room utilization data
        room_utilization = get_room_utilization_analytics(date_range['start'], date_range['end'])
        
        # Get peak usage times
        peak_usage = get_peak_usage_analysis(date_range['start'], date_range['end'])
        
        # Get room efficiency metrics
        efficiency_metrics = get_room_efficiency_metrics(date_range['start'], date_range['end'])
        
        report_data = {
            'utilization': room_utilization,
            'peak_usage': peak_usage,
            'efficiency': efficiency_metrics,
            'date_range': date_range,
            'period': period
        }
        
        print(f"✅ DEBUG: Room utilization report generated successfully")
        
        return render_template('reports/room_utilization.html', 
                             title='Room Utilization Report',
                             report_data=report_data)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to generate room utilization report: {e}")
        import traceback
        traceback.print_exc()
        
        flash('❌ Error generating room utilization report. Please try again.', 'danger')
        return redirect(url_for('reports.reports'))

# ===============================
# DAILY/WEEKLY/MONTHLY SUMMARY REPORTS
# ===============================

@reports_bp.route('/reports/daily-summary')
@login_required
@activity_logged(ActivityTypes.GENERATE_REPORT, "Generated daily summary report")
def daily_summary_report():
    """Enhanced daily summary with detailed analytics"""
    try:
        # Get date parameter
        date_str = request.args.get('date', datetime.now(UTC).date().isoformat())
        report_date = datetime.fromisoformat(date_str).date()
        
        print(f"🔍 DEBUG: Generating daily summary for {report_date}")
        
        # Get daily data
        daily_data = get_daily_summary_data(report_date)
        
        return render_template('reports/daily_summary.html', 
                             title=f'Daily Summary - {report_date}',
                             daily_data=daily_data,
                             report_date=report_date)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to generate daily summary: {e}")
        flash('❌ Error generating daily summary. Please try again.', 'danger')
        return redirect(url_for('reports.reports'))

@reports_bp.route('/reports/weekly-summary')
@login_required
@activity_logged(ActivityTypes.GENERATE_REPORT, "Generated weekly summary report")
def weekly_summary_report():
    """Enhanced weekly summary with trends"""
    try:
        # Get week parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            # Default to current week
            today = datetime.now(UTC).date()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            start_date = start_of_week.isoformat()
            end_date = end_of_week.isoformat()
        
        print(f"🔍 DEBUG: Generating weekly summary for {start_date} to {end_date}")
        
        # Get weekly data
        weekly_data = get_weekly_summary_data(start_date, end_date)
        
        return render_template('reports/weekly_summary.html', 
                             title=f'Weekly Summary - {start_date} to {end_date}',
                             weekly_data=weekly_data,
                             start_date=start_date,
                             end_date=end_date)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to generate weekly summary: {e}")
        flash('❌ Error generating weekly summary. Please try again.', 'danger')
        return redirect(url_for('reports.reports'))

@reports_bp.route('/reports/monthly-summary')
@login_required
@activity_logged(ActivityTypes.GENERATE_REPORT, "Generated monthly summary report")
def monthly_summary_report():
    """Enhanced monthly summary with comprehensive analytics"""
    try:
        # Get month parameters
        year = request.args.get('year', datetime.now(UTC).year, type=int)
        month = request.args.get('month', datetime.now(UTC).month, type=int)
        
        print(f"🔍 DEBUG: Generating monthly summary for {year}-{month:02d}")
        
        # Calculate month date range
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        # Get monthly data
        monthly_data = get_monthly_summary_data(start_date, end_date)
        
        return render_template('reports/monthly_summary.html', 
                             title=f'Monthly Summary - {start_date.strftime("%B %Y")}',
                             monthly_data=monthly_data,
                             year=year,
                             month=month,
                             start_date=start_date,
                             end_date=end_date)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to generate monthly summary: {e}")
        flash('❌ Error generating monthly summary. Please try again.', 'danger')
        return redirect(url_for('reports.reports'))

# ===============================
# HELPER FUNCTIONS - DATA RETRIEVAL
# ===============================

def get_reports_quick_stats():
    """Get quick statistics for reports dashboard"""
    try:
        # Get current month data
        current_month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (current_month + timedelta(days=32)).replace(day=1)
        
        # Get bookings for current month
        bookings_response = supabase_admin.table('bookings').select(
            'id, status, total_price, created_at'
        ).gte('created_at', current_month.isoformat()).lt(
            'created_at', next_month.isoformat()
        ).execute()
        
        bookings = bookings_response.data if bookings_response.data else []
        
        # Calculate stats
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.get('status') == 'confirmed'])
        total_revenue = sum(float(b.get('total_price', 0)) for b in bookings if b.get('status') == 'confirmed')
        
        # Get total clients
        clients_response = supabase_admin.table('clients').select('id').execute()
        total_clients = len(clients_response.data) if clients_response.data else 0
        
        return {
            'this_month_bookings': total_bookings,
            'this_month_confirmed': confirmed_bookings,
            'this_month_revenue': round(total_revenue, 2),
            'total_clients': total_clients,
            'conversion_rate': round((confirmed_bookings / max(total_bookings, 1)) * 100, 1)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get quick stats: {e}")
        return get_empty_quick_stats()

def get_empty_quick_stats():
    """Return empty quick stats for error cases"""
    return {
        'this_month_bookings': 0,
        'this_month_confirmed': 0,
        'this_month_revenue': 0,
        'total_clients': 0,
        'conversion_rate': 0
    }

def calculate_date_range(period, start_date=None, end_date=None):
    """Calculate date range based on period or custom dates"""
    try:
        now = datetime.now(UTC)
        
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
        elif period == 'today':
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'yesterday':
            yesterday = now - timedelta(days=1)
            start_dt = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'this_week':
            start_dt = now - timedelta(days=now.weekday())
            start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = start_dt + timedelta(days=6, hours=23, minutes=59, seconds=59)
        elif period == 'last_week':
            start_dt = now - timedelta(days=now.weekday() + 7)
            start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = start_dt + timedelta(days=6, hours=23, minutes=59, seconds=59)
        elif period == 'this_month':
            start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = (start_dt + timedelta(days=32)).replace(day=1)
            end_dt = next_month - timedelta(seconds=1)
        elif period == 'last_month':
            start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_dt = (start_dt - timedelta(days=1)).replace(day=1)
            end_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        elif period == 'this_year':
            start_dt = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_dt = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        else:  # Default to last 30 days
            start_dt = now - timedelta(days=30)
            end_dt = now
        
        return {
            'start': start_dt,
            'end': end_dt,
            'start_str': start_dt.strftime('%Y-%m-%d'),
            'end_str': end_dt.strftime('%Y-%m-%d'),
            'period_name': get_period_name(period, start_dt, end_dt)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to calculate date range: {e}")
        # Fallback to last 30 days
        now = datetime.now(UTC)
        start_dt = now - timedelta(days=30)
        return {
            'start': start_dt,
            'end': now,
            'start_str': start_dt.strftime('%Y-%m-%d'),
            'end_str': now.strftime('%Y-%m-%d'),
            'period_name': 'Last 30 Days'
        }

def get_period_name(period, start_dt, end_dt):
    """Get display name for period"""
    period_names = {
        'today': 'Today',
        'yesterday': 'Yesterday',
        'this_week': 'This Week',
        'last_week': 'Last Week',
        'this_month': 'This Month',
        'last_month': 'Last Month',
        'this_year': 'This Year'
    }
    
    if period in period_names:
        return period_names[period]
    else:
        return f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}"

def get_available_date_ranges():
    """Get available date ranges based on data"""
    try:
        # Get earliest and latest booking dates
        earliest_response = supabase_admin.table('bookings').select('created_at').order('created_at').limit(1).execute()
        latest_response = supabase_admin.table('bookings').select('created_at').order('created_at', desc=True).limit(1).execute()
        
        earliest_date = None
        latest_date = None
        
        if earliest_response.data:
            earliest_date = datetime.fromisoformat(earliest_response.data[0]['created_at'].replace('Z', '')).date()
        
        if latest_response.data:
            latest_date = datetime.fromisoformat(latest_response.data[0]['created_at'].replace('Z', '')).date()
        
        return {
            'earliest_date': earliest_date.isoformat() if earliest_date else None,
            'latest_date': latest_date.isoformat() if latest_date else None,
            'has_data': bool(earliest_date and latest_date)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get date ranges: {e}")
        return {
            'earliest_date': None,
            'latest_date': None,
            'has_data': False
        }

# ===============================
# HELPER FUNCTIONS - ANALYTICS
# ===============================

def get_revenue_analytics(start_date, end_date):
    """Get comprehensive revenue analytics for date range"""
    try:
        # Get all confirmed bookings in date range
        response = supabase_admin.table('bookings').select(
            'id, total_price, created_at, start_time, attendees'
        ).eq('status', 'confirmed').gte(
            'created_at', start_date.isoformat()
        ).lte(
            'created_at', end_date.isoformat()
        ).execute()
        
        bookings = response.data if response.data else []
        
        # Calculate analytics
        total_revenue = sum(float(b.get('total_price', 0)) for b in bookings)
        total_bookings = len(bookings)
        average_booking_value = total_revenue / max(total_bookings, 1)
        total_attendees = sum(int(b.get('attendees', 0)) for b in bookings)
        
        # Calculate daily breakdown
        daily_revenue = defaultdict(float)
        for booking in bookings:
            try:
                created_date = datetime.fromisoformat(booking['created_at'].replace('Z', '')).date()
                daily_revenue[created_date] += float(booking.get('total_price', 0))
            except:
                continue
        
        # Calculate growth (compare with previous period)
        period_days = (end_date - start_date).days
        prev_start = start_date - timedelta(days=period_days)
        prev_end = start_date
        
        prev_response = supabase_admin.table('bookings').select(
            'total_price'
        ).eq('status', 'confirmed').gte(
            'created_at', prev_start.isoformat()
        ).lt(
            'created_at', prev_end.isoformat()
        ).execute()
        
        prev_bookings = prev_response.data if prev_response.data else []
        prev_revenue = sum(float(b.get('total_price', 0)) for b in prev_bookings)
        
        growth_rate = 0
        if prev_revenue > 0:
            growth_rate = ((total_revenue - prev_revenue) / prev_revenue) * 100
        
        return {
            'total_revenue': round(total_revenue, 2),
            'total_bookings': total_bookings,
            'average_booking_value': round(average_booking_value, 2),
            'total_attendees': total_attendees,
            'revenue_per_attendee': round(total_revenue / max(total_attendees, 1), 2),
            'daily_revenue': dict(daily_revenue),
            'growth_rate': round(growth_rate, 1),
            'previous_period_revenue': round(prev_revenue, 2)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue analytics: {e}")
        return {
            'total_revenue': 0,
            'total_bookings': 0,
            'average_booking_value': 0,
            'total_attendees': 0,
            'revenue_per_attendee': 0,
            'daily_revenue': {},
            'growth_rate': 0,
            'previous_period_revenue': 0
        }

def get_revenue_by_room(start_date, end_date):
    """Get revenue breakdown by room"""
    try:
        response = supabase_admin.table('bookings').select("""
            total_price, room_id,
            room:rooms(id, name, capacity)
        """).eq('status', 'confirmed').gte(
            'created_at', start_date.isoformat()
        ).lte(
            'created_at', end_date.isoformat()
        ).execute()
        
        bookings = response.data if response.data else []
        
        # Group by room
        room_revenue = defaultdict(lambda: {
            'revenue': 0,
            'bookings': 0,
            'room_name': 'Unknown Room',
            'capacity': 0
        })
        
        for booking in bookings:
            room_id = booking.get('room_id')
            revenue = float(booking.get('total_price', 0))
            room = booking.get('room', {})
            
            if room_id:
                room_revenue[room_id]['revenue'] += revenue
                room_revenue[room_id]['bookings'] += 1
                room_revenue[room_id]['room_name'] = room.get('name', 'Unknown Room')
                room_revenue[room_id]['capacity'] = room.get('capacity', 0)
        
        # Convert to list and sort by revenue
        revenue_list = []
        for room_id, data in room_revenue.items():
            revenue_list.append({
                'room_id': room_id,
                'room_name': data['room_name'],
                'capacity': data['capacity'],
                'revenue': round(data['revenue'], 2),
                'bookings': data['bookings'],
                'average_per_booking': round(data['revenue'] / max(data['bookings'], 1), 2)
            })
        
        revenue_list.sort(key=lambda x: x['revenue'], reverse=True)
        
        return revenue_list
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue by room: {e}")
        return []

def get_revenue_by_client(start_date, end_date):
    """Get revenue breakdown by client"""
    try:
        response = supabase_admin.table('bookings').select("""
            total_price, client_id,
            client:clients(id, contact_person, company_name)
        """).eq('status', 'confirmed').gte(
            'created_at', start_date.isoformat()
        ).lte(
            'created_at', end_date.isoformat()
        ).execute()
        
        bookings = response.data if response.data else []
        
        # Group by client
        client_revenue = defaultdict(lambda: {
            'revenue': 0,
            'bookings': 0,
            'client_name': 'Unknown Client',
            'company_name': None
        })
        
        for booking in bookings:
            client_id = booking.get('client_id')
            revenue = float(booking.get('total_price', 0))
            client = booking.get('client', {})
            
            if client_id:
                client_revenue[client_id]['revenue'] += revenue
                client_revenue[client_id]['bookings'] += 1
                client_revenue[client_id]['client_name'] = client.get('contact_person', 'Unknown Client')
                client_revenue[client_id]['company_name'] = client.get('company_name')
        
        # Convert to list and sort by revenue
        revenue_list = []
        for client_id, data in client_revenue.items():
            display_name = data['company_name'] or data['client_name']
            revenue_list.append({
                'client_id': client_id,
                'client_name': data['client_name'],
                'company_name': data['company_name'],
                'display_name': display_name,
                'revenue': round(data['revenue'], 2),
                'bookings': data['bookings'],
                'average_per_booking': round(data['revenue'] / max(data['bookings'], 1), 2)
            })
        
        revenue_list.sort(key=lambda x: x['revenue'], reverse=True)
        
        return revenue_list[:20]  # Top 20 clients
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue by client: {e}")
        return []

def get_revenue_trends_detailed(start_date, end_date):
    """Get detailed revenue trends for charting"""
    try:
        response = supabase_admin.table('bookings').select(
            'total_price, created_at'
        ).eq('status', 'confirmed').gte(
            'created_at', start_date.isoformat()
        ).lte(
            'created_at', end_date.isoformat()
        ).execute()
        
        bookings = response.data if response.data else []
        
        # Group by date
        daily_revenue = defaultdict(float)
        for booking in bookings:
            try:
                created_date = datetime.fromisoformat(booking['created_at'].replace('Z', '')).date()
                daily_revenue[created_date] += float(booking.get('total_price', 0))
            except:
                continue
        
        # Create complete date series
        dates = []
        revenues = []
        
        current_date = start_date.date()
        while current_date <= end_date.date():
            dates.append(current_date.isoformat())
            revenues.append(daily_revenue.get(current_date, 0))
            current_date += timedelta(days=1)
        
        return {
            'dates': dates,
            'revenues': revenues,
            'total_revenue': sum(revenues),
            'average_daily': sum(revenues) / len(revenues) if revenues else 0,
            'max_daily': max(revenues) if revenues else 0,
            'min_daily': min(revenues) if revenues else 0
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue trends: {e}")
        return {
            'dates': [],
            'revenues': [],
            'total_revenue': 0,
            'average_daily': 0,
            'max_daily': 0,
            'min_daily': 0
        }

def get_client_analytics(start_date, end_date):
    """Get comprehensive client analytics"""
    try:
        # Get all clients with their bookings
        response = supabase_admin.table('bookings').select("""
            client_id, total_price, status, created_at,
            client:clients(id, contact_person, company_name, created_at)
        """).gte('created_at', start_date.isoformat()).lte(
            'created_at', end_date.isoformat()
        ).execute()
        
        bookings = response.data if bookings_response.data else []
        
        # Analyze client data
        total_clients = len(set(b.get('client_id') for b in bookings if b.get('client_id')))
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.get('status') == 'confirmed'])
        
        # New vs returning clients
        all_clients_response = supabase_admin.table('clients').select('id, created_at').execute()
        all_clients = all_clients_response.data if all_clients_response.data else []
        
        new_clients = len([
            c for c in all_clients 
            if c.get('created_at') and 
            start_date <= datetime.fromisoformat(c['created_at'].replace('Z', '')) <= end_date
        ])
        
        return {
            'total_clients': total_clients,
            'new_clients': new_clients,
            'returning_clients': total_clients - new_clients,
            'total_bookings': total_bookings,
            'confirmed_bookings': confirmed_bookings,
            'average_bookings_per_client': round(total_bookings / max(total_clients, 1), 2),
            'client_conversion_rate': round((confirmed_bookings / max(total_bookings, 1)) * 100, 1)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get client analytics: {e}")
        return {
            'total_clients': 0,
            'new_clients': 0,
            'returning_clients': 0,
            'total_bookings': 0,
            'confirmed_bookings': 0,
            'average_bookings_per_client': 0,
            'client_conversion_rate': 0
        }

def get_top_clients_by_revenue(start_date, end_date, limit=10):
    """Get top clients by revenue"""
    revenue_by_client = get_revenue_by_client(start_date, end_date)
    return revenue_by_client[:limit]

def get_top_clients_by_bookings(start_date, end_date, limit=10):
    """Get top clients by number of bookings"""
    revenue_by_client = get_revenue_by_client(start_date, end_date)
    revenue_by_client.sort(key=lambda x: x['bookings'], reverse=True)
    return revenue_by_client[:limit]

def get_client_retention_data(start_date, end_date):
    """Get client retention analysis"""
    try:
        # This is a simplified retention analysis
        # In a real system, you'd want more sophisticated cohort analysis
        
        # Get clients who booked in the period
        response = supabase_admin.table('bookings').select("""
            client_id, created_at,
            client:clients(id, contact_person, company_name)
        """).gte('created_at', start_date.isoformat()).lte(
            'created_at', end_date.isoformat()
        ).execute()
        
        bookings = response.data if response.data else []
        
        # Group bookings by client
        client_bookings = defaultdict(list)
        for booking in bookings:
            client_id = booking.get('client_id')
            if client_id:
                client_bookings[client_id].append(booking)
        
        # Analyze retention
        one_time_clients = 0
        repeat_clients = 0
        
        for client_id, client_booking_list in client_bookings.items():
            if len(client_booking_list) == 1:
                one_time_clients += 1
            else:
                repeat_clients += 1
        
        total_clients = len(client_bookings)
        retention_rate = round((repeat_clients / max(total_clients, 1)) * 100, 1)
        
        return {
            'total_clients': total_clients,
            'one_time_clients': one_time_clients,
            'repeat_clients': repeat_clients,
            'retention_rate': retention_rate
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get retention data: {e}")
        return {
            'total_clients': 0,
            'one_time_clients': 0,
            'repeat_clients': 0,
            'retention_rate': 0
        }

def get_room_utilization_analytics(start_date, end_date):
    """Get comprehensive room utilization analytics"""
    try:
        # Get all rooms
        rooms_response = supabase_admin.table('rooms').select('*').execute()
        rooms = rooms_response.data if rooms_response.data else []
        
        # Get bookings for the period
        bookings_response = supabase_admin.table('bookings').select(
            'room_id, start_time, end_time, status'
        ).gte('start_time', start_date.isoformat()).lte(
            'end_time', end_date.isoformat()
        ).neq('status', 'cancelled').execute()
        
        bookings = bookings_response.data if bookings_response.data else []
        
        # Calculate utilization for each room
        room_utilization = []
        period_days = (end_date - start_date).days
        available_hours_per_day = 14  # 6 AM to 8 PM
        total_available_hours = period_days * available_hours_per_day
        
        for room in rooms:
            room_id = room['id']
            room_bookings = [b for b in bookings if b.get('room_id') == room_id]
            
            # Calculate total booking hours
            total_booking_hours = 0
            for booking in room_bookings:
                try:
                    start_dt = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                    end_dt = datetime.fromisoformat(booking['end_time'].replace('Z', ''))
                    booking_hours = (end_dt - start_dt).total_seconds() / 3600
                    total_booking_hours += booking_hours
                except:
                    continue
            
            utilization_percentage = round((total_booking_hours / total_available_hours) * 100, 1) if total_available_hours > 0 else 0
            
            room_utilization.append({
                'room_id': room_id,
                'room_name': room['name'],
                'capacity': room['capacity'],
                'total_bookings': len(room_bookings),
                'total_hours': round(total_booking_hours, 1),
                'available_hours': total_available_hours,
                'utilization_percentage': utilization_percentage,
                'status': room.get('status', 'available')
            })
        
        # Sort by utilization
        room_utilization.sort(key=lambda x: x['utilization_percentage'], reverse=True)
        
        return room_utilization
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get room utilization: {e}")
        return []

def get_peak_usage_analysis(start_date, end_date):
    """Analyze peak usage times"""
    try:
        bookings_response = supabase_admin.table('bookings').select(
            'start_time, end_time'
        ).gte('start_time', start_date.isoformat()).lte(
            'end_time', end_date.isoformat()
        ).neq('status', 'cancelled').execute()
        
        bookings = bookings_response.data if bookings_response.data else []
        
        # Analyze by hour of day
        hourly_usage = defaultdict(int)
        daily_usage = defaultdict(int)
        
        for booking in bookings:
            try:
                start_dt = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                
                # Count by hour
                hourly_usage[start_dt.hour] += 1
                
                # Count by day of week (0=Monday, 6=Sunday)
                daily_usage[start_dt.weekday()] += 1
                
            except:
                continue
        
        # Convert to sorted lists
        peak_hours = sorted(hourly_usage.items(), key=lambda x: x[1], reverse=True)[:5]
        peak_days = sorted(daily_usage.items(), key=lambda x: x[1], reverse=True)
        
        # Convert day numbers to names
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        peak_days_named = [(day_names[day], count) for day, count in peak_days]
        
        return {
            'peak_hours': peak_hours,
            'peak_days': peak_days_named,
            'hourly_distribution': dict(hourly_usage),
            'daily_distribution': dict(daily_usage)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get peak usage analysis: {e}")
        return {
            'peak_hours': [],
            'peak_days': [],
            'hourly_distribution': {},
            'daily_distribution': {}
        }

def get_room_efficiency_metrics(start_date, end_date):
    """Get room efficiency metrics"""
    try:
        # Get rooms with their bookings and revenue
        response = supabase_admin.table('bookings').select("""
            room_id, total_price, attendees, start_time, end_time, status,
            room:rooms(id, name, capacity)
        """).gte('start_time', start_date.isoformat()).lte(
            'end_time', end_date.isoformat()
        ).neq('status', 'cancelled').execute()
        
        bookings = response.data if response.data else []
        
        # Group by room and calculate metrics
        room_metrics = defaultdict(lambda: {
            'total_revenue': 0,
            'total_attendees': 0,
            'total_hours': 0,
            'bookings': 0,
            'room_name': 'Unknown',
            'capacity': 0
        })
        
        for booking in bookings:
            room_id = booking.get('room_id')
            if not room_id:
                continue
                
            room = booking.get('room', {})
            
            # Calculate booking duration
            try:
                start_dt = datetime.fromisoformat(booking['start_time'].replace('Z', ''))
                end_dt = datetime.fromisoformat(booking['end_time'].replace('Z', ''))
                duration_hours = (end_dt - start_dt).total_seconds() / 3600
            except:
                duration_hours = 0
            
            room_metrics[room_id]['total_revenue'] += float(booking.get('total_price', 0))
            room_metrics[room_id]['total_attendees'] += int(booking.get('attendees', 0))
            room_metrics[room_id]['total_hours'] += duration_hours
            room_metrics[room_id]['bookings'] += 1
            room_metrics[room_id]['room_name'] = room.get('name', 'Unknown')
            room_metrics[room_id]['capacity'] = room.get('capacity', 0)
        
        # Calculate efficiency metrics
        efficiency_list = []
        for room_id, metrics in room_metrics.items():
            if metrics['bookings'] > 0:
                efficiency_list.append({
                    'room_id': room_id,
                    'room_name': metrics['room_name'],
                    'capacity': metrics['capacity'],
                    'total_revenue': round(metrics['total_revenue'], 2),
                    'total_attendees': metrics['total_attendees'],
                    'total_hours': round(metrics['total_hours'], 1),
                    'bookings': metrics['bookings'],
                    'revenue_per_hour': round(metrics['total_revenue'] / max(metrics['total_hours'], 1), 2),
                    'average_occupancy': round(metrics['total_attendees'] / max(metrics['bookings'], 1), 1),
                    'capacity_utilization': round((metrics['total_attendees'] / max(metrics['bookings'], 1)) / max(metrics['capacity'], 1) * 100, 1)
                })
        
        # Sort by revenue per hour
        efficiency_list.sort(key=lambda x: x['revenue_per_hour'], reverse=True)
        
        return efficiency_list
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get efficiency metrics: {e}")
        return []

# ===============================
# SUMMARY REPORT FUNCTIONS
# ===============================

def get_daily_summary_data(report_date):
    """Get comprehensive daily summary data"""
    try:
        # Convert date to datetime range
        start_dt = datetime.combine(report_date, datetime.min.time()).replace(tzinfo=UTC)
        end_dt = datetime.combine(report_date, datetime.max.time()).replace(tzinfo=UTC)
        
        # Get bookings for the day
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name)
        """).gte('start_time', start_dt.isoformat()).lte(
            'start_time', end_dt.isoformat()
        ).order('start_time').execute()
        
        bookings = response.data if response.data else []
        
        # Convert datetime strings
        bookings = convert_datetime_strings(bookings)
        
        # Calculate summary statistics
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.get('status') == 'confirmed'])
        tentative_bookings = len([b for b in bookings if b.get('status') == 'tentative'])
        cancelled_bookings = len([b for b in bookings if b.get('status') == 'cancelled'])
        
        total_revenue = sum(float(b.get('total_price', 0)) for b in bookings if b.get('status') == 'confirmed')
        total_attendees = sum(int(b.get('attendees', 0)) for b in bookings if b.get('status') != 'cancelled')
        
        # Group by time slots
        time_slots = defaultdict(list)
        for booking in bookings:
            if booking.get('start_time'):
                hour = booking['start_time'].hour
                time_slots[hour].append(booking)
        
        return {
            'date': report_date,
            'bookings': bookings,
            'summary': {
                'total_bookings': total_bookings,
                'confirmed_bookings': confirmed_bookings,
                'tentative_bookings': tentative_bookings,
                'cancelled_bookings': cancelled_bookings,
                'total_revenue': round(total_revenue, 2),
                'total_attendees': total_attendees,
                'average_booking_value': round(total_revenue / max(confirmed_bookings, 1), 2)
            },
            'time_slots': dict(time_slots)
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get daily summary: {e}")
        return {
            'date': report_date,
            'bookings': [],
            'summary': {
                'total_bookings': 0,
                'confirmed_bookings': 0,
                'tentative_bookings': 0,
                'cancelled_bookings': 0,
                'total_revenue': 0,
                'total_attendees': 0,
                'average_booking_value': 0
            },
            'time_slots': {}
        }

def get_weekly_summary_data(start_date, end_date):
    """Get comprehensive weekly summary data"""
    try:
        # Convert to datetime
        start_dt = datetime.fromisoformat(start_date).replace(tzinfo=UTC)
        end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, tzinfo=UTC)
        
        # Get bookings for the week
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name)
        """).gte('start_time', start_dt.isoformat()).lte(
            'start_time', end_dt.isoformat()
        ).order('start_time').execute()
        
        bookings = response.data if response.data else []
        bookings = convert_datetime_strings(bookings)
        
        # Group by day
        daily_breakdown = defaultdict(list)
        for booking in bookings:
            if booking.get('start_time'):
                day = booking['start_time'].date()
                daily_breakdown[day].append(booking)
        
        # Calculate daily summaries
        daily_summaries = {}
        for day, day_bookings in daily_breakdown.items():
            confirmed = len([b for b in day_bookings if b.get('status') == 'confirmed'])
            revenue = sum(float(b.get('total_price', 0)) for b in day_bookings if b.get('status') == 'confirmed')
            
            daily_summaries[day] = {
                'date': day,
                'total_bookings': len(day_bookings),
                'confirmed_bookings': confirmed,
                'revenue': round(revenue, 2),
                'bookings': day_bookings
            }
        
        # Overall summary
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.get('status') == 'confirmed'])
        total_revenue = sum(float(b.get('total_price', 0)) for b in bookings if b.get('status') == 'confirmed')
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'bookings': bookings,
            'daily_summaries': daily_summaries,
            'overall_summary': {
                'total_bookings': total_bookings,
                'confirmed_bookings': confirmed_bookings,
                'total_revenue': round(total_revenue, 2),
                'average_daily_bookings': round(total_bookings / 7, 1),
                'average_daily_revenue': round(total_revenue / 7, 2)
            }
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get weekly summary: {e}")
        return {
            'start_date': start_date,
            'end_date': end_date,
            'bookings': [],
            'daily_summaries': {},
            'overall_summary': {
                'total_bookings': 0,
                'confirmed_bookings': 0,
                'total_revenue': 0,
                'average_daily_bookings': 0,
                'average_daily_revenue': 0
            }
        }

def get_monthly_summary_data(start_date, end_date):
    """Get comprehensive monthly summary data"""
    try:
        # Convert to datetime
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=UTC)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=UTC)
        
        # Get all bookings for the month
        response = supabase_admin.table('bookings').select("""
            *,
            room:rooms(id, name, capacity),
            client:clients(id, contact_person, company_name)
        """).gte('start_time', start_dt.isoformat()).lte(
            'start_time', end_dt.isoformat()
        ).order('start_time').execute()
        
        bookings = response.data if response.data else []
        bookings = convert_datetime_strings(bookings)
        
        # Group by week
        weekly_breakdown = defaultdict(list)
        for booking in bookings:
            if booking.get('start_time'):
                # Get week number
                week_start = booking['start_time'].date() - timedelta(days=booking['start_time'].weekday())
                weekly_breakdown[week_start].append(booking)
        
        # Calculate weekly summaries
        weekly_summaries = {}
        for week_start, week_bookings in weekly_breakdown.items():
            confirmed = len([b for b in week_bookings if b.get('status') == 'confirmed'])
            revenue = sum(float(b.get('total_price', 0)) for b in week_bookings if b.get('status') == 'confirmed')
            
            weekly_summaries[week_start] = {
                'week_start': week_start,
                'week_end': week_start + timedelta(days=6),
                'total_bookings': len(week_bookings),
                'confirmed_bookings': confirmed,
                'revenue': round(revenue, 2)
            }
        
        # Top performers
        revenue_by_room = get_revenue_by_room(start_dt, end_dt)
        revenue_by_client = get_revenue_by_client(start_dt, end_dt)
        
        # Overall summary
        total_bookings = len(bookings)
        confirmed_bookings = len([b for b in bookings if b.get('status') == 'confirmed'])
        total_revenue = sum(float(b.get('total_price', 0)) for b in bookings if b.get('status') == 'confirmed')
        total_attendees = sum(int(b.get('attendees', 0)) for b in bookings if b.get('status') != 'cancelled')
        
        days_in_month = (end_date - start_date).days + 1
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'month_name': start_date.strftime('%B %Y'),
            'bookings': bookings,
            'weekly_summaries': weekly_summaries,
            'top_rooms': revenue_by_room[:5],
            'top_clients': revenue_by_client[:5],
            'overall_summary': {
                'total_bookings': total_bookings,
                'confirmed_bookings': confirmed_bookings,
                'tentative_bookings': len([b for b in bookings if b.get('status') == 'tentative']),
                'cancelled_bookings': len([b for b in bookings if b.get('status') == 'cancelled']),
                'total_revenue': round(total_revenue, 2),
                'total_attendees': total_attendees,
                'average_daily_bookings': round(total_bookings / days_in_month, 1),
                'average_daily_revenue': round(total_revenue / days_in_month, 2),
                'average_booking_value': round(total_revenue / max(confirmed_bookings, 1), 2),
                'conversion_rate': round((confirmed_bookings / max(total_bookings, 1)) * 100, 1)
            }
        }
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get monthly summary: {e}")
        return {
            'start_date': start_date,
            'end_date': end_date,
            'month_name': start_date.strftime('%B %Y'),
            'bookings': [],
            'weekly_summaries': {},
            'top_rooms': [],
            'top_clients': [],
            'overall_summary': {
                'total_bookings': 0,
                'confirmed_bookings': 0,
                'tentative_bookings': 0,
                'cancelled_bookings': 0,
                'total_revenue': 0,
                'total_attendees': 0,
                'average_daily_bookings': 0,
                'average_daily_revenue': 0,
                'average_booking_value': 0,
                'conversion_rate': 0
            }
        }

# ===============================
# EXPORT FUNCTIONS
# ===============================

def export_revenue_csv(revenue_data, revenue_by_room, date_range):
    """Export revenue report as CSV"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Revenue Report'])
        writer.writerow(['Period:', f"{date_range['start_str']} to {date_range['end_str']}"])
        writer.writerow(['Generated:', datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['SUMMARY'])
        writer.writerow(['Total Revenue', f"${revenue_data['total_revenue']:.2f}"])
        writer.writerow(['Total Bookings', revenue_data['total_bookings']])
        writer.writerow(['Average Booking Value', f"${revenue_data['average_booking_value']:.2f}"])
        writer.writerow(['Growth Rate', f"{revenue_data['growth_rate']:.1f}%"])
        writer.writerow([])
        
        # Revenue by room
        writer.writerow(['REVENUE BY ROOM'])
        writer.writerow(['Room Name', 'Bookings', 'Revenue', 'Avg per Booking'])
        for room in revenue_by_room:
            writer.writerow([
                room['room_name'],
                room['bookings'],
                f"${room['revenue']:.2f}",
                f"${room['average_per_booking']:.2f}"
            ])
        
        output.seek(0)
        
        # Create response
        response = send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'revenue_report_{date_range["start_str"]}_to_{date_range["end_str"]}.csv'
        )
        
        return response
        
    except Exception as e:
        print(f"❌ ERROR: Failed to export CSV: {e}")
        raise

def export_revenue_pdf(revenue_data, revenue_by_room, date_range):
    """Export revenue report as PDF"""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Build content
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        story.append(Paragraph("<b>Revenue Report</b>", styles['Title']))
        story.append(Spacer(1, 12))
        
        # Period
        story.append(Paragraph(f"<b>Period:</b> {date_range['period_name']}", styles['Normal']))
        story.append(Paragraph(f"<b>Date Range:</b> {date_range['start_str']} to {date_range['end_str']}", styles['Normal']))
        story.append(Paragraph(f"<b>Generated:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}", styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Summary section
        story.append(Paragraph("<b>Summary</b>", styles['Heading2']))
        
        summary_data = [
            ['Metric', 'Value'],
            ['Total Revenue', f"${revenue_data['total_revenue']:,.2f}"],
            ['Total Bookings', f"{revenue_data['total_bookings']:,}"],
            ['Average Booking Value', f"${revenue_data['average_booking_value']:,.2f}"],
            ['Growth Rate', f"{revenue_data['growth_rate']:+.1f}%"]
        ]
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 12))
        
        # Revenue by room
        if revenue_by_room:
            story.append(Paragraph("<b>Revenue by Room</b>", styles['Heading2']))
            
            room_data = [['Room Name', 'Bookings', 'Revenue', 'Avg per Booking']]
            for room in revenue_by_room[:10]:  # Top 10 rooms
                room_data.append([
                    room['room_name'],
                    str(room['bookings']),
                    f"${room['revenue']:,.2f}",
                    f"${room['average_per_booking']:,.2f}"
                ])
            
            room_table = Table(room_data)
            room_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(room_table)
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'revenue_report_{date_range["start_str"]}_to_{date_range["end_str"]}.pdf'
        )
        
    except Exception as e:
        print(f"❌ ERROR: Failed to export PDF: {e}")
        raise

# ===============================
# API ENDPOINTS
# ===============================

@reports_bp.route('/api/reports/revenue-data')
@login_required
def api_revenue_data():
    """API endpoint for revenue data"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'this_month')
        
        date_range = calculate_date_range(period, start_date, end_date)
        revenue_data = get_revenue_analytics(date_range['start'], date_range['end'])
        
        return jsonify(revenue_data)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get revenue data via API: {e}")
        return jsonify({'error': 'Failed to get revenue data'}), 500

@reports_bp.route('/api/reports/client-analytics')
@login_required
def api_client_analytics():
    """API endpoint for client analytics"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        period = request.args.get('period', 'this_year')
        
        date_range = calculate_date_range(period, start_date, end_date)
        client_data = get_client_analytics(date_range['start'], date_range['end'])
        
        return jsonify(client_data)
        
    except Exception as e:
        print(f"❌ ERROR: Failed to get client analytics via API: {e}")
        return jsonify({'error': 'Failed to get client analytics'}), 500

# ===============================
# ERROR HANDLERS
# ===============================

@reports_bp.errorhandler(500)
def reports_internal_error(error):
    """Handle internal server errors in reports"""
    print(f"❌ Reports error: {error}")
    
    try:
        log_user_activity(
            ActivityTypes.ERROR_OCCURRED,
            f"Reports internal error: {str(error)}",
            resource_type='reports',
            status='failed'
        )
    except:
        pass
    
    flash('⚠️ An error occurred while generating the report. Please try again.', 'danger')
    return redirect(url_for('reports.reports'))

@reports_bp.errorhandler(404)
def reports_not_found(error):
    """Handle 404 errors in reports"""
    flash('⚠️ The requested report was not found.', 'warning')
    return redirect(url_for('reports.reports'))