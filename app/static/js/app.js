// AI Secretary API Tester

class APITester {
    constructor() {
        this.baseURL = window.location.origin;
        this.init();
    }

    init() {
        // Toggle endpoint details
        document.querySelectorAll('.endpoint-header').forEach(header => {
            header.addEventListener('click', () => {
                const body = header.nextElementSibling;
                body.classList.toggle('show');
            });
        });

        // Test buttons
        document.querySelectorAll('.btn-test').forEach(button => {
            button.addEventListener('click', (e) => {
                const endpoint = e.target.dataset.endpoint;
                this.testEndpoint(endpoint, e.target);
            });
        });
    }

    async testEndpoint(endpoint, button) {
        const responseBox = button.parentElement.querySelector('.response-box');
        const statusBadge = button.parentElement.querySelector('.status-badge');
        
        button.disabled = true;
        button.textContent = 'Testing...';
        responseBox.textContent = 'Loading...';

        try {
            const response = await fetch(`${this.baseURL}${endpoint}`);
            const data = await response.json();
            
            // Update status badge
            statusBadge.textContent = response.status;
            statusBadge.className = `status-badge status-${response.status}`;
            
            // Update response box
            responseBox.textContent = JSON.stringify(data, null, 2);
            
        } catch (error) {
            statusBadge.textContent = 'ERROR';
            statusBadge.className = 'status-badge status-500';
            responseBox.textContent = `Error: ${error.message}`;
        } finally {
            button.disabled = false;
            button.textContent = 'Test';
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new APITester();
});

// Auto-refresh health status every 30 seconds
setInterval(() => {
    const healthButton = document.querySelector('[data-endpoint="/api/v1/health"]');
    if (healthButton) {
        healthButton.click();
    }
}, 30000);