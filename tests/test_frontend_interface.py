"""Tests for frontend interface functionality."""
import pytest
import os
from pathlib import Path


def get_template_path(template_name):
    """Get the full path to a template file."""
    base_dir = Path(__file__).parent.parent
    return base_dir / 'app' / 'templates' / template_name


class TestTemplateFiles:
    """Test that template files exist and have correct structure."""
    
    def test_login_template_exists(self):
        """Test login template file exists."""
        template_path = get_template_path('auth/login.html')
        assert template_path.exists(), f"Login template not found at {template_path}"
    
    def test_register_template_exists(self):
        """Test registration template file exists."""
        template_path = get_template_path('auth/register.html')
        assert template_path.exists(), f"Register template not found at {template_path}"
    
    def test_dashboard_template_exists(self):
        """Test dashboard template file exists."""
        template_path = get_template_path('main/dashboard.html')
        assert template_path.exists(), f"Dashboard template not found at {template_path}"
    
    def test_inbox_template_exists(self):
        """Test inbox template file exists."""
        template_path = get_template_path('main/inbox.html')
        assert template_path.exists(), f"Inbox template not found at {template_path}"
    
    def test_crm_template_exists(self):
        """Test CRM template file exists."""
        template_path = get_template_path('main/crm.html')
        assert template_path.exists(), f"CRM template not found at {template_path}"
    
    def test_calendar_template_exists(self):
        """Test calendar template file exists."""
        template_path = get_template_path('main/calendar.html')
        assert template_path.exists(), f"Calendar template not found at {template_path}"
    
    def test_settings_template_exists(self):
        """Test settings template file exists."""
        template_path = get_template_path('main/settings.html')
        assert template_path.exists(), f"Settings template not found at {template_path}"
    
    def test_users_template_exists(self):
        """Test users template file exists."""
        template_path = get_template_path('main/users.html')
        assert template_path.exists(), f"Users template not found at {template_path}"
    
    def test_base_template_exists(self):
        """Test base template file exists."""
        template_path = get_template_path('base.html')
        assert template_path.exists(), f"Base template not found at {template_path}"


class TestTemplateContent:
    """Test template content and structure."""
    
    def test_login_template_content(self):
        """Test login template has required form elements."""
        template_path = get_template_path('auth/login.html')
        content = template_path.read_text(encoding='utf-8')
        
        assert 'type="email"' in content
        assert 'type="password"' in content
        assert 'required' in content
        assert '<form' in content
        assert 'loginForm' in content
    
    def test_register_template_content(self):
        """Test registration template has required form elements."""
        template_path = get_template_path('auth/register.html')
        content = template_path.read_text(encoding='utf-8')
        
        assert 'type="email"' in content
        assert 'type="password"' in content
        assert 'organization_name' in content
        assert 'required' in content
        assert '<form' in content
        assert 'registerForm' in content
    
    def test_dashboard_template_content(self):
        """Test dashboard template has required elements."""
        template_path = get_template_path('main/dashboard.html')
        content = template_path.read_text(encoding='utf-8')
        
        assert 'Welcome back' in content
        assert 'Messages Today' in content
        assert 'Active Leads' in content
        assert 'Appointments' in content
        assert 'loadDashboardMetrics' in content
    
    def test_inbox_template_content(self):
        """Test inbox template has required elements."""
        template_path = get_template_path('main/inbox.html')
        content = template_path.read_text(encoding='utf-8')
        
        assert 'Inbox' in content
        assert 'Conversations' in content
        assert 'loadConversations' in content
        assert 'sendMessage' in content
        assert 'composeModal' in content
    
    def test_crm_template_content(self):
        """Test CRM template has required elements."""
        template_path = get_template_path('main/crm.html')
        content = template_path.read_text(encoding='utf-8')
        
        assert 'CRM' in content
        assert 'Pipeline Overview' in content
        assert 'Add Lead' in content
        assert 'loadLeads' in content
        assert 'Table View' in content
        assert 'Kanban View' in content
    
    def test_calendar_template_content(self):
        """Test calendar template has required elements."""
        template_path = get_template_path('main/calendar.html')
        content = template_path.read_text(encoding='utf-8')
        
        assert 'Calendar' in content
        assert 'Book Appointment' in content
        assert 'Connect Google Calendar' in content
        assert 'renderCalendar' in content
        assert 'Month' in content
        assert 'Week' in content
        assert 'Day' in content
    
    def test_settings_template_content(self):
        """Test settings template has required elements."""
        template_path = get_template_path('main/settings.html')
        content = template_path.read_text(encoding='utf-8')
        
        assert 'Settings' in content
        assert 'Organization' in content
        assert 'Channels' in content
        assert 'AI Settings' in content
        assert 'Billing' in content
        assert 'Security' in content
        assert 'organizationForm' in content
    
    def test_users_template_content(self):
        """Test users template has required elements."""
        template_path = get_template_path('main/users.html')
        content = template_path.read_text(encoding='utf-8')
        
        assert 'User Management' in content
        assert 'Invite User' in content
        assert 'Total Users' in content
        assert 'loadUsers' in content
        assert 'inviteUserModal' in content
    
    def test_base_template_content(self):
        """Test base template has required elements."""
        template_path = get_template_path('base.html')
        content = template_path.read_text(encoding='utf-8')
        
        assert 'bootstrap' in content
        assert 'navbar' in content
        assert 'AI Secretary' in content
        assert 'container' in content
        assert 'checkAuthStatus' in content
        assert 'logout' in content


class TestTemplateStructure:
    """Test template structure and accessibility."""
    
    def test_templates_extend_base(self):
        """Test that main templates extend base template."""
        templates_to_check = [
            'auth/login.html',
            'auth/register.html',
            'main/dashboard.html',
            'main/inbox.html',
            'main/crm.html',
            'main/calendar.html',
            'main/settings.html',
            'main/users.html'
        ]
        
        for template_name in templates_to_check:
            template_path = get_template_path(template_name)
            content = template_path.read_text(encoding='utf-8')
            assert '{% extends "base.html" %}' in content, f"{template_name} should extend base.html"
    
    def test_templates_have_titles(self):
        """Test that templates have proper title blocks."""
        templates_to_check = [
            'auth/login.html',
            'auth/register.html',
            'main/dashboard.html',
            'main/inbox.html',
            'main/crm.html',
            'main/calendar.html',
            'main/settings.html',
            'main/users.html'
        ]
        
        for template_name in templates_to_check:
            template_path = get_template_path(template_name)
            content = template_path.read_text(encoding='utf-8')
            assert '{% block title %}' in content, f"{template_name} should have a title block"
    
    def test_templates_have_content_blocks(self):
        """Test that templates have content blocks."""
        templates_to_check = [
            'auth/login.html',
            'auth/register.html',
            'main/dashboard.html',
            'main/inbox.html',
            'main/crm.html',
            'main/calendar.html',
            'main/settings.html',
            'main/users.html'
        ]
        
        for template_name in templates_to_check:
            template_path = get_template_path(template_name)
            content = template_path.read_text(encoding='utf-8')
            assert '{% block content %}' in content, f"{template_name} should have a content block"
    
    def test_forms_have_labels(self):
        """Test that form templates have proper labels."""
        form_templates = [
            'auth/login.html',
            'auth/register.html',
            'main/settings.html',
            'main/users.html'
        ]
        
        for template_name in form_templates:
            template_path = get_template_path(template_name)
            content = template_path.read_text(encoding='utf-8')
            assert '<label' in content, f"{template_name} should have form labels"
            assert 'for=' in content, f"{template_name} labels should have 'for' attributes"
    
    def test_responsive_design(self):
        """Test that templates use responsive design classes."""
        templates_to_check = [
            'auth/login.html',
            'auth/register.html',
            'main/dashboard.html',
            'main/inbox.html',
            'main/crm.html',
            'main/calendar.html',
            'main/settings.html',
            'main/users.html'
        ]
        
        for template_name in templates_to_check:
            template_path = get_template_path(template_name)
            content = template_path.read_text(encoding='utf-8')
            assert 'col-' in content, f"{template_name} should use Bootstrap grid classes"
            assert 'row' in content, f"{template_name} should use Bootstrap row classes"