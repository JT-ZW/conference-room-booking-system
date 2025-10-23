from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from core import supabase_select, supabase_insert, supabase_update, supabase_delete, AddonForm, AddonCategoryForm

addons_bp = Blueprint('addons', __name__)

@addons_bp.route('/addons')
@login_required
def addons():
    try:
        response = supabase_admin.table('addons').select('*').order('name').execute()
        addons_data = response.data if response.data else []
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch addons from Supabase: {e}")
        addons_data = []
        flash('Error loading addons from database', 'danger')
    return render_template('addons/index.html', title='Add-ons', addons=addons_data)

@addons_bp.route('/addons/new', methods=['GET', 'POST'])
@login_required
def new_addon():
    # ... (new addon logic here)
    return render_template('addons/form.html', title='New Add-on')

@addons_bp.route('/addons/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_addon(id):
    # ... (edit addon logic here)
    return render_template('addons/form.html', title='Edit Add-on')

@addons_bp.route('/addons/<int:id>/delete', methods=['POST'])
@login_required
def delete_addon(id):
    # ... (delete addon logic here)
    return redirect(url_for('addons.addons'))

@addons_bp.route('/addon_categories/new', methods=['GET', 'POST'])
@login_required
def new_addon_category():
    # ... (new addon category logic here)
    return render_template('addons/new_category.html', title='New Add-on Category') 