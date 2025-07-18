from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from datetime import datetime, UTC
from core import get_dashboard_stats, get_recent_bookings, get_upcoming_bookings, get_todays_bookings, get_revenue_trends

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():  # Changed from dashboard to index
    """Display dashboard"""
    try:
        print("🔍 DEBUG: Loading enhanced dashboard")
        stats = get_dashboard_stats()
        recent_bookings = get_recent_bookings(5)
        upcoming_bookings = get_upcoming_bookings(5)
        todays_bookings = get_todays_bookings()
        revenue_trends = get_revenue_trends()

        print("✅ DEBUG: Enhanced dashboard loaded successfully")
        return render_template('dashboard.html',
                             title='Dashboard',
                             stats=stats,
                             recent_bookings=recent_bookings,
                             upcoming_bookings=upcoming_bookings,
                             todays_bookings=todays_bookings,
                             revenue_trends=revenue_trends,
                             now=datetime.now(UTC))

    except Exception as e:
        print(f"❌ ERROR: Failed to load enhanced dashboard: {e}")
        return render_template('dashboard.html',
                             title='Dashboard',
                             stats={},
                             recent_bookings=[],
                             upcoming_bookings=[],
                             todays_bookings=[],
                             revenue_trends=[],
                             now=datetime.now(UTC))