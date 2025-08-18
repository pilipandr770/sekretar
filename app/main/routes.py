"""Main web interface routes."""
from flask import render_template, jsonify, redirect, url_for, request, flash
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from app.main import main_bp
from app.utils.response import success_response, error_response

# Import WebSocket handlers to register them
from app.main import websocket_handlers


@main_bp.route('/')
def home():
    """Home page - redirect to dashboard if authenticated, otherwise to login."""
    try:
        verify_jwt_in_request(optional=True)
        current_user = get_jwt_identity()
        if current_user:
            return redirect(url_for('main.dashboard'))
        else:
            return redirect(url_for('main.login'))
    except:
        return redirect(url_for('main.login'))


@main_bp.route('/login')
def login():
    """Login page."""
    return render_template('auth/login.html')


@main_bp.route('/register')
def register():
    """Registration page."""
    return render_template('auth/register.html')


@main_bp.route('/dashboard')
@jwt_required(optional=True)
def dashboard():
    """Main dashboard page."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return redirect(url_for('main.login'))
        return render_template('main/dashboard.html')
    except:
        return redirect(url_for('main.login'))


@main_bp.route('/inbox')
@jwt_required(optional=True)
def inbox():
    """Inbox management page."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return redirect(url_for('main.login'))
        return render_template('main/inbox.html')
    except:
        return redirect(url_for('main.login'))


@main_bp.route('/crm')
@jwt_required(optional=True)
def crm():
    """CRM management page."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return redirect(url_for('main.login'))
        return render_template('main/crm.html')
    except:
        return redirect(url_for('main.login'))


@main_bp.route('/calendar')
@jwt_required(optional=True)
def calendar():
    """Calendar integration page."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return redirect(url_for('main.login'))
        return render_template('main/calendar.html')
    except:
        return redirect(url_for('main.login'))


@main_bp.route('/settings')
@jwt_required(optional=True)
def settings():
    """Tenant settings page."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return redirect(url_for('main.login'))
        return render_template('main/settings.html')
    except:
        return redirect(url_for('main.login'))


@main_bp.route('/users')
@jwt_required(optional=True)
def users():
    """User management page."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return redirect(url_for('main.login'))
        return render_template('main/users.html')
    except:
        return redirect(url_for('main.login'))


@main_bp.route('/web')
def index():
    """Main web interface for API testing."""
    return render_template('main/index.html')


@main_bp.route('/web/api-tester')
def api_tester():
    """API testing interface."""
    return render_template('main/api_tester.html')


@main_bp.route('/web/docs')
def documentation():
    """Documentation page."""
    return render_template('main/docs.html')


@main_bp.route('/docs/<path:filename>')
def serve_docs(filename):
    """Serve documentation files."""
    from flask import send_from_directory
    import os
    
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'docs')
    return send_from_directory(docs_dir, filename)


@main_bp.route('/web/secretary-setup')
def secretary_setup():
    """AI Secretary setup page."""
    return render_template('main/secretary_setup.html')


@main_bp.route('/web/kyb-dashboard')
def kyb_dashboard():
    """KYB monitoring dashboard."""
    return render_template('main/kyb_dashboard.html')


@main_bp.route('/widget-demo')
def widget_demo():
    """Web widget demonstration page."""
    return render_template('widget_demo.html')