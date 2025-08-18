"""Default notification templates for the system."""
from typing import Dict, List
from app.models import NotificationTemplate, NotificationType
from app.utils.database import db


class NotificationTemplateManager:
    """Manager for creating and managing notification templates."""
    
    DEFAULT_TEMPLATES = {
        # KYB Alert Templates
        'kyb_alert_email': {
            'type': NotificationType.EMAIL.value,
            'subject_template': '🔍 KYB Alert: {{ alert_type }} for {{ counterparty_name }}',
            'body_template': '''Dear {{ company_name }} team,

A KYB alert has been triggered for counterparty {{ counterparty_name }}:

Alert Type: {{ alert_type }}
Severity: {{ severity }}
Details: {{ details }}
Detected At: {{ detected_at }}

{% if recommendations %}
Recommended Actions:
{% for recommendation in recommendations %}
- {{ recommendation }}
{% endfor %}
{% endif %}

Please review this alert and take appropriate action.

Best regards,
AI Secretary KYB System''',
            'html_template': '''<html>
<body style="font-family: Arial, sans-serif;">
    <h2 style="color: #e74c3c;">🔍 KYB Alert: {{ alert_type }}</h2>
    <p>Dear {{ company_name }} team,</p>
    <p>A KYB alert has been triggered for counterparty <strong>{{ counterparty_name }}</strong>:</p>
    
    <div style="background-color: #fdf2f2; padding: 15px; border-left: 4px solid #e74c3c; margin: 20px 0;">
        <p><strong>Alert Type:</strong> {{ alert_type }}</p>
        <p><strong>Severity:</strong> {{ severity }}</p>
        <p><strong>Details:</strong> {{ details }}</p>
        <p><strong>Detected At:</strong> {{ detected_at }}</p>
    </div>
    
    {% if recommendations %}
    <p><strong>Recommended Actions:</strong></p>
    <ul>
        {% for recommendation in recommendations %}
        <li>{{ recommendation }}</li>
        {% endfor %}
    </ul>
    {% endif %}
    
    <p>Please review this alert and take appropriate action.</p>
    <p>Best regards,<br>AI Secretary KYB System</p>
</body>
</html>''',
            'variables': ['company_name', 'counterparty_name', 'alert_type', 'severity', 'details', 'detected_at', 'recommendations']
        },
        
        'kyb_alert_telegram': {
            'type': NotificationType.TELEGRAM.value,
            'subject_template': '🔍 KYB Alert: {{ alert_type }}',
            'body_template': '''🔍 *KYB Alert*

*Counterparty:* {{ counterparty_name }}
*Alert Type:* {{ alert_type }}
*Severity:* {{ severity }}
*Details:* {{ details }}
*Detected:* {{ detected_at }}

Please review and take appropriate action.''',
            'variables': ['counterparty_name', 'alert_type', 'severity', 'details', 'detected_at']
        },
        
        'kyb_alert_signal': {
            'type': NotificationType.SIGNAL.value,
            'subject_template': 'KYB Alert: {{ alert_type }}',
            'body_template': '''KYB Alert

Counterparty: {{ counterparty_name }}
Alert Type: {{ alert_type }}
Severity: {{ severity }}
Details: {{ details }}
Detected: {{ detected_at }}

Please review and take appropriate action.''',
            'variables': ['counterparty_name', 'alert_type', 'severity', 'details', 'detected_at']
        },
        
        # Invoice Notification Templates
        'invoice_update_email': {
            'type': NotificationType.EMAIL.value,
            'subject_template': '💰 Invoice {{ status }}: {{ invoice_number }}',
            'body_template': '''Dear {{ company_name }} team,

Your invoice has been {{ status }}:

Invoice Number: {{ invoice_number }}
Amount: {{ amount }}
Status: {{ status }}
{% if due_date %}Due Date: {{ due_date }}{% endif %}
{% if payment_date %}Payment Date: {{ payment_date }}{% endif %}

{% if status == 'paid' %}
Thank you for your payment!
{% elif status == 'overdue' %}
This invoice is now overdue. Please process payment as soon as possible.
{% endif %}

Best regards,
AI Secretary Billing System''',
            'html_template': '''<html>
<body style="font-family: Arial, sans-serif;">
    <h2 style="color: #27ae60;">💰 Invoice {{ status|title }}</h2>
    <p>Dear {{ company_name }} team,</p>
    <p>Your invoice has been <strong>{{ status }}</strong>:</p>
    
    <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #27ae60; margin: 20px 0;">
        <p><strong>Invoice Number:</strong> {{ invoice_number }}</p>
        <p><strong>Amount:</strong> {{ amount }}</p>
        <p><strong>Status:</strong> {{ status|title }}</p>
        {% if due_date %}<p><strong>Due Date:</strong> {{ due_date }}</p>{% endif %}
        {% if payment_date %}<p><strong>Payment Date:</strong> {{ payment_date }}</p>{% endif %}
    </div>
    
    {% if status == 'paid' %}
    <p style="color: #27ae60;"><strong>Thank you for your payment!</strong></p>
    {% elif status == 'overdue' %}
    <p style="color: #e74c3c;"><strong>This invoice is now overdue. Please process payment as soon as possible.</strong></p>
    {% endif %}
    
    <p>Best regards,<br>AI Secretary Billing System</p>
</body>
</html>''',
            'variables': ['company_name', 'invoice_number', 'amount', 'status', 'due_date', 'payment_date']
        },
        
        # System Notification Templates
        'system_notification_email': {
            'type': NotificationType.EMAIL.value,
            'subject_template': '📢 System Notification: {{ title }}',
            'body_template': '''Dear {{ company_name }} team,

{{ message }}

{% if action_required %}
Action Required: {{ action_required }}
{% endif %}

{% if deadline %}
Deadline: {{ deadline }}
{% endif %}

Best regards,
AI Secretary System''',
            'html_template': '''<html>
<body style="font-family: Arial, sans-serif;">
    <h2 style="color: #3498db;">📢 System Notification</h2>
    <p>Dear {{ company_name }} team,</p>
    <p>{{ message }}</p>
    
    {% if action_required %}
    <div style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
        <p><strong>Action Required:</strong> {{ action_required }}</p>
        {% if deadline %}<p><strong>Deadline:</strong> {{ deadline }}</p>{% endif %}
    </div>
    {% endif %}
    
    <p>Best regards,<br>AI Secretary System</p>
</body>
</html>''',
            'variables': ['company_name', 'title', 'message', 'action_required', 'deadline']
        },
        
        # Generic Templates
        'generic_email': {
            'type': NotificationType.EMAIL.value,
            'subject_template': '{{ subject }}',
            'body_template': '{{ message }}',
            'html_template': '''<html>
<body style="font-family: Arial, sans-serif;">
    <p>{{ message }}</p>
</body>
</html>''',
            'variables': ['subject', 'message']
        },
        
        'generic_telegram': {
            'type': NotificationType.TELEGRAM.value,
            'subject_template': '{{ subject }}',
            'body_template': '{{ message }}',
            'variables': ['subject', 'message']
        },
        
        'generic_signal': {
            'type': NotificationType.SIGNAL.value,
            'subject_template': '{{ subject }}',
            'body_template': '{{ message }}',
            'variables': ['subject', 'message']
        }
    }
    
    @classmethod
    def create_default_templates(cls, tenant_id: str) -> List[NotificationTemplate]:
        """Create default notification templates for a tenant."""
        created_templates = []
        
        for name, template_data in cls.DEFAULT_TEMPLATES.items():
            # Check if template already exists
            existing = NotificationTemplate.query.filter_by(
                tenant_id=tenant_id,
                name=name
            ).first()
            
            if existing:
                continue
            
            template = NotificationTemplate(
                tenant_id=tenant_id,
                name=name,
                type=template_data['type'],
                subject_template=template_data.get('subject_template'),
                body_template=template_data['body_template'],
                html_template=template_data.get('html_template'),
                variables=template_data.get('variables', [])
            )
            
            db.session.add(template)
            created_templates.append(template)
        
        db.session.commit()
        return created_templates
    
    @classmethod
    def get_template(cls, tenant_id: str, name: str) -> NotificationTemplate:
        """Get a specific template by name."""
        return NotificationTemplate.query.filter_by(
            tenant_id=tenant_id,
            name=name,
            is_active=True
        ).first()
    
    @classmethod
    def list_templates(cls, tenant_id: str, notification_type: str = None) -> List[NotificationTemplate]:
        """List all templates for a tenant, optionally filtered by type."""
        query = NotificationTemplate.query.filter_by(
            tenant_id=tenant_id,
            is_active=True
        )
        
        if notification_type:
            query = query.filter_by(type=notification_type)
        
        return query.all()
    
    @classmethod
    def update_template(
        cls,
        template_id: str,
        subject_template: str = None,
        body_template: str = None,
        html_template: str = None,
        variables: List[str] = None
    ) -> NotificationTemplate:
        """Update an existing template."""
        template = NotificationTemplate.query.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        if subject_template is not None:
            template.subject_template = subject_template
        if body_template is not None:
            template.body_template = body_template
        if html_template is not None:
            template.html_template = html_template
        if variables is not None:
            template.variables = variables
        
        template.updated_at = db.func.now()
        db.session.commit()
        
        return template
    
    @classmethod
    def delete_template(cls, template_id: str) -> bool:
        """Soft delete a template."""
        template = NotificationTemplate.query.get(template_id)
        if not template:
            return False
        
        template.is_active = False
        template.updated_at = db.func.now()
        db.session.commit()
        
        return True