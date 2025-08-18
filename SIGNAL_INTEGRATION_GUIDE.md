# Signal Integration Guide for AI Secretary

## Overview

This guide explains how to set up and use the Signal integration in AI Secretary. The Signal integration allows your AI Secretary to send and receive messages through Signal, providing another communication channel for your customers.

## Architecture

The Signal integration consists of several components:

### 1. Signal CLI Service (`app/services/signal_cli_service.py`)
- Downloads and manages Signal CLI installation
- Handles phone number registration and verification
- Manages Signal accounts and message operations

### 2. Signal Bot Handler (`app/channels/signal_bot.py`)
- Processes incoming and outgoing Signal messages
- Integrates with the AI orchestrator for automated responses
- Handles message polling and delivery

### 3. Signal API (`app/api/signal.py`)
- REST API endpoints for Signal management
- User interface for setup and configuration
- Channel management and testing

### 4. Frontend Interface (`app/templates/channels/signal_setup.html`)
- Step-by-step setup wizard
- Channel management interface
- Testing and monitoring tools

## Setup Process

### Prerequisites

1. **Java Runtime Environment (JRE)**
   - Signal CLI requires Java 8 or higher
   - Install Java: `sudo apt install openjdk-11-jre` (Ubuntu/Debian)

2. **Phone Number**
   - A phone number that can receive SMS messages
   - The number will be registered with Signal

### Step 1: Install Signal CLI

The system will automatically download and install Signal CLI:

```bash
# Automatic installation through the web interface
# Or manual installation:
curl -L https://github.com/AsamK/signal-cli/releases/download/v0.11.5/signal-cli-0.11.5.tar.gz | tar xz
```

### Step 2: Register Phone Number

1. Navigate to `/channels/signal/setup` in the web interface
2. Enter your phone number with country code (e.g., `+1234567890`)
3. Click "Register Phone Number"
4. You'll receive an SMS with a verification code

### Step 3: Verify Phone Number

1. Enter the 6-digit verification code from SMS
2. Click "Verify Phone Number"
3. Your phone number is now registered with Signal

### Step 4: Create Signal Channel

1. Give your channel a descriptive name
2. Enable/disable AI auto-response
3. Set polling interval (default: 2 seconds)
4. Click "Create Signal Channel"

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Signal Configuration
SIGNAL_CLI_PATH=signal-cli
SIGNAL_PHONE_NUMBER=+1234567890
SIGNAL_AUTO_INSTALL=true
SIGNAL_POLLING_INTERVAL=2
```

### Channel Configuration

Each Signal channel has the following configuration options:

```json
{
  "phone_number": "+1234567890",
  "auto_response": true,
  "polling_interval": 2,
  "enabled": true
}
```

## API Endpoints

### Installation and Setup

```http
GET /api/v1/signal/status
POST /api/v1/signal/install
POST /api/v1/signal/register
POST /api/v1/signal/verify
```

### Channel Management

```http
POST /api/v1/signal/channels
GET /api/v1/signal/channels/{id}
PUT /api/v1/signal/channels/{id}
DELETE /api/v1/signal/channels/{id}
```

### Messaging

```http
POST /api/v1/signal/send
GET /api/v1/signal/accounts
POST /api/v1/signal/test
```

## Usage Examples

### Send a Message via API

```bash
curl -X POST http://localhost:5000/api/v1/signal/send \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": "+0987654321",
    "message": "Hello from AI Secretary!"
  }'
```

### Check Signal Status

```bash
curl -X GET http://localhost:5000/api/v1/signal/status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Register New Phone Number

```bash
curl -X POST http://localhost:5000/api/v1/signal/register \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+1234567890"
  }'
```

## Message Flow

### Incoming Messages

1. **Polling**: Signal CLI polls for new messages every 2 seconds (configurable)
2. **Processing**: Messages are processed through the AI orchestrator
3. **Response**: AI generates appropriate responses based on message content
4. **Delivery**: Responses are sent back through Signal

### Outgoing Messages

1. **API Call**: Messages sent via REST API or web interface
2. **Validation**: Phone numbers and content are validated
3. **Delivery**: Messages sent through Signal CLI
4. **Logging**: All messages are logged in the database

## AI Integration

### Agent Routing

Signal messages are processed through the same AI agent system as other channels:

- **Router Agent**: Detects intent and routes to appropriate specialist
- **Supervisor Agent**: Filters content and ensures compliance
- **Specialist Agents**: Handle specific domains (sales, support, billing)

### Context Preservation

Each Signal conversation maintains context including:

- Customer phone number
- Conversation history
- Previous interactions
- Customer preferences

## Troubleshooting

### Common Issues

#### 1. Signal CLI Not Found

**Error**: `Signal CLI not installed`

**Solution**:
```bash
# Check Java installation
java -version

# Reinstall Signal CLI through web interface
# Or manually download and extract
```

#### 2. Phone Number Registration Failed

**Error**: `Registration failed: Captcha required`

**Solution**:
- Solve the captcha at https://signalcaptchas.org/registration/generate.html
- Enter the captcha token in the registration form

#### 3. Verification Code Invalid

**Error**: `Invalid verification code`

**Solution**:
- Check that you entered the correct 6-digit code
- Request a new verification code if expired
- Ensure SMS was received on the correct number

#### 4. Message Sending Failed

**Error**: `Failed to send message`

**Solution**:
```bash
# Check Signal CLI status
signal-cli -a +1234567890 receive --timeout 1

# Verify recipient number format
# Ensure phone number is registered
```

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger('signal').setLevel(logging.DEBUG)
```

Check Signal CLI logs:
```bash
# View recent logs
tail -f /var/log/ai-secretary/signal.log

# Check Signal CLI version
signal-cli --version
```

## Security Considerations

### Phone Number Privacy

- Phone numbers are stored encrypted in the database
- Access is restricted to authorized users only
- Audit logs track all phone number operations

### Message Security

- All messages are encrypted by Signal protocol
- Local message storage follows GDPR compliance
- Message retention policies are configurable

### Access Control

- Signal channel management requires `channels:manage` permission
- Message sending requires `messages:send` permission
- Status viewing requires `channels:read` permission

## Performance Optimization

### Polling Optimization

- Adjust polling interval based on message volume
- Use longer intervals (5-10 seconds) for low-traffic channels
- Use shorter intervals (1-2 seconds) for high-traffic channels

### Message Batching

- Process multiple messages in batches
- Implement message queuing for high volume
- Use async processing for better performance

### Resource Management

- Monitor Signal CLI memory usage
- Restart Signal CLI periodically if needed
- Clean up old message data regularly

## Monitoring and Metrics

### Key Metrics

- Messages received per hour
- Messages sent per hour
- Response time (message to AI response)
- Error rates and types
- Phone number registration success rate

### Health Checks

The system provides several health check endpoints:

```bash
# Overall Signal status
curl http://localhost:5000/api/v1/signal/status

# Test Signal connection
curl -X POST http://localhost:5000/api/v1/signal/test

# Check registered accounts
curl http://localhost:5000/api/v1/signal/accounts
```

### Alerting

Set up alerts for:

- Signal CLI process failures
- High error rates
- Message delivery failures
- Phone number verification issues

## Integration with Other Systems

### CRM Integration

Signal conversations automatically create:
- Lead records for new contacts
- Conversation threads
- Activity logs
- Contact information updates

### Calendar Integration

Signal can be used for:
- Appointment confirmations
- Meeting reminders
- Schedule updates
- Availability notifications

### Knowledge Base Integration

AI responses can include:
- Document references
- FAQ answers
- Product information
- Support articles

## Best Practices

### Phone Number Management

1. Use dedicated business phone numbers
2. Keep phone numbers consistent across channels
3. Document phone number ownership
4. Plan for number changes and migrations

### Message Templates

1. Create templates for common responses
2. Use consistent branding and tone
3. Include clear call-to-action items
4. Test templates with real users

### Customer Experience

1. Set clear expectations for response times
2. Provide fallback options for complex issues
3. Offer human handoff when needed
4. Maintain conversation context

### Compliance

1. Follow Signal's terms of service
2. Respect customer privacy preferences
3. Implement proper consent mechanisms
4. Maintain audit trails for compliance

## Future Enhancements

### Planned Features

- **Group Message Support**: Handle Signal group conversations
- **Media Messages**: Support for images, videos, and documents
- **Message Scheduling**: Schedule messages for later delivery
- **Bulk Messaging**: Send messages to multiple recipients
- **Advanced Analytics**: Detailed conversation analytics

### Integration Roadmap

- **WhatsApp Integration**: Similar setup for WhatsApp Business
- **Multi-Channel Routing**: Route messages between channels
- **Unified Inbox**: Single interface for all channels
- **Advanced AI**: Context-aware responses across channels

## Support

### Documentation

- API Reference: `/api/v1/docs`
- User Guide: Available in the web interface
- Video Tutorials: Coming soon

### Community

- GitHub Issues: Report bugs and feature requests
- Discord Community: Get help from other users
- Email Support: support@ai-secretary.com

### Professional Support

- Setup Assistance: Professional setup and configuration
- Custom Integration: Tailored integrations for enterprise
- Training: Team training and best practices
- SLA Support: Guaranteed response times and uptime

---

**Last Updated**: December 2024  
**Version**: 1.0  
**Maintained by**: AI Secretary Development Team