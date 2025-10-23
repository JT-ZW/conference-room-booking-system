from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from utils.decorators import require_admin_or_manager
from utils.logging import log_user_activity
from core import supabase_admin, ActivityTypes
from datetime import datetime, UTC

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/activity-logs')
@login_required
@require_admin_or_manager
def activity_logs():
    try:
        logs = supabase_admin.table('user_activity_log').select('*').order('timestamp', desc=True).limit(100).execute().data
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch activity logs from Supabase: {e}")
        logs = []
        flash('Error loading activity logs from database', 'danger')
    return render_template('admin/activity_logs.html', title='User Activity Logs', logs=logs)

@admin_bp.route('/admin/activity-stats')
@login_required
@require_admin_or_manager
def activity_stats():
    # ... (activity stats logic here)
    return render_template('admin/activity_stats.html', title='Activity Statistics') 