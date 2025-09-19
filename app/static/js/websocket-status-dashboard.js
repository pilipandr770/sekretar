/**
 * WebSocket Status Dashboard
 * Provides detailed connection information and controls
 */
class WebSocketStatusDashboard {
    constructor() {
        this.isVisible = false;
        this.dashboard = null;
        this.updateInterval = null;
        
        this.init();
    }
    
    init() {
        this.createDashboard();
        this.bindEvents();
        this.startUpdating();
    }
    
    createDashboard() {
        this.dashboard = document.createElement('div');
        this.dashboard.id = 'ws-dashboard';
        this.dashboard.className = 'ws-dashboard';
        this.dashboard.innerHTML = `
            <div class="ws-dashboard-header">
                <h6>WebSocket Status</h6>
                <button class="btn-close" aria-label="Close"></button>
            </div>
            <div class="ws-dashboard-content">
                <div class="ws-stat">
                    <label>Status:</label>
                    <span id="ws-dash-status">Unknown</span>
                </div>
                <div class="ws-stat">
                    <label>Quality:</label>
                    <span id="ws-dash-quality">Unknown</span>
                </div>
                <div class="ws-stat">
                    <label>Avg Ping:</label>
                    <span id="ws-dash-ping">-</span>
                </div>
                <div class="ws-stat">
                    <label>Reconnect Attempts:</label>
                    <span id="ws-dash-attempts">0</span>
                </div>
                <div class="ws-stat">
                    <label>Current Room:</label>
                    <span id="ws-dash-room">None</span>
                </div>
                <div class="ws-dashboard-actions">
                    <button id="ws-dash-reconnect" class="btn btn-sm btn-primary">Reconnect</button>
                    <button id="ws-dash-disconnect" class="btn btn-sm btn-secondary">Disconnect</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.dashboard);
    }
    
    bindEvents() {
        // Close button
        this.dashboard.querySelector('.btn-close').addEventListener('click', () => {
            this.hide();
        });
        
        // Reconnect button
        this.dashboard.querySelector('#ws-dash-reconnect').addEventListener('click', () => {
            if (window.wsClient) {
                window.wsClient.reconnectManually();
            }
        });
        
        // Disconnect button
        this.dashboard.querySelector('#ws-dash-disconnect').addEventListener('click', () => {
            if (window.wsClient) {
                window.wsClient.disconnect();
            }
        });
        
        // Listen for WebSocket events
        document.addEventListener('websocket:connected', () => this.updateStatus());
        document.addEventListener('websocket:disconnected', () => this.updateStatus());
        document.addEventListener('websocket:quality_change', () => this.updateStatus());
        document.addEventListener('websocket:status_change', () => this.updateStatus());
        
        // Toggle dashboard with Ctrl+Shift+W
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'W') {
                e.preventDefault();
                this.toggle();
            }
        });
    }
    
    startUpdating() {
        this.updateInterval = setInterval(() => {
            if (this.isVisible) {
                this.updateStatus();
            }
        }, 2000);
    }
    
    updateStatus() {
        if (!window.wsClient || !this.isVisible) return;
        
        const stats = window.wsClient.getConnectionStats();
        
        // Update status
        const statusElement = this.dashboard.querySelector('#ws-dash-status');
        statusElement.textContent = stats.isConnected ? 'Connected' : 'Disconnected';
        statusElement.className = stats.isConnected ? 'status-connected' : 'status-disconnected';
        
        // Update quality
        const qualityElement = this.dashboard.querySelector('#ws-dash-quality');
        qualityElement.textContent = stats.connectionQuality || 'Unknown';
        qualityElement.className = `quality-${stats.connectionQuality || 'unknown'}`;
        
        // Update ping
        const pingElement = this.dashboard.querySelector('#ws-dash-ping');
        pingElement.textContent = stats.averagePing ? `${stats.averagePing}ms` : '-';
        
        // Update attempts
        const attemptsElement = this.dashboard.querySelector('#ws-dash-attempts');
        attemptsElement.textContent = `${stats.reconnectAttempts}/${stats.maxReconnectAttempts}`;
        
        // Update room
        const roomElement = this.dashboard.querySelector('#ws-dash-room');
        roomElement.textContent = stats.currentConversation || 'None';
        
        // Update button states
        const reconnectBtn = this.dashboard.querySelector('#ws-dash-reconnect');
        const disconnectBtn = this.dashboard.querySelector('#ws-dash-disconnect');
        
        reconnectBtn.disabled = stats.isConnected;
        disconnectBtn.disabled = !stats.isConnected;
    }
    
    show() {
        this.isVisible = true;
        this.dashboard.style.display = 'block';
        this.updateStatus();
    }
    
    hide() {
        this.isVisible = false;
        this.dashboard.style.display = 'none';
    }
    
    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }
    
    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        if (this.dashboard) {
            this.dashboard.remove();
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.wsDashboard = new WebSocketStatusDashboard();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketStatusDashboard;
}