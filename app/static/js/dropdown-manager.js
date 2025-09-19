/**
 * Dropdown Manager
 * Handles dropdown menu functionality including opening/closing behavior,
 * click-outside-to-close, and proper action execution
 */

class DropdownManager {
    constructor() {
        this.dropdowns = new Map();
        this.isInitialized = false;
        this.activeDropdown = null;
        
        // Bind methods to preserve context
        this.handleDropdownToggle = this.handleDropdownToggle.bind(this);
        this.handleDropdownItemClick = this.handleDropdownItemClick.bind(this);
        this.handleDocumentClick = this.handleDocumentClick.bind(this);
        this.handleKeydown = this.handleKeydown.bind(this);
    }

    /**
     * Initialize the dropdown manager
     */
    init() {
        if (this.isInitialized) {
            return;
        }

        console.log('Initializing Dropdown Manager...');
        
        // Initialize Bootstrap dropdowns
        this.initializeBootstrapDropdowns();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Set up dropdown tracking
        this.setupDropdownTracking();
        
        this.isInitialized = true;
        console.log('Dropdown Manager initialized');
    }

    /**
     * Initialize Bootstrap dropdown components
     */
    initializeBootstrapDropdowns() {
        if (!window.bootstrap) {
            console.warn('Bootstrap not available, dropdown functionality may be limited');
            return;
        }

        // Find all dropdown toggles
        const dropdownToggles = document.querySelectorAll('[data-bs-toggle="dropdown"]');
        
        dropdownToggles.forEach(toggle => {
            try {
                // Initialize Bootstrap dropdown
                const dropdown = new bootstrap.Dropdown(toggle);
                
                // Store reference
                const dropdownId = toggle.id || `dropdown-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                if (!toggle.id) {
                    toggle.id = dropdownId;
                }
                
                this.dropdowns.set(dropdownId, {
                    element: toggle,
                    bootstrap: dropdown,
                    menu: toggle.nextElementSibling || document.querySelector(`[aria-labelledby="${toggle.id}"]`),
                    isOpen: false
                });
                
                console.log(`Initialized dropdown: ${dropdownId}`);
                
            } catch (error) {
                console.error('Failed to initialize dropdown:', toggle, error);
            }
        });
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Listen for dropdown toggle clicks
        document.addEventListener('click', (e) => {
            const toggle = e.target.closest('[data-bs-toggle="dropdown"]');
            if (toggle) {
                this.handleDropdownToggle(e, toggle);
            }
        });

        // Listen for dropdown item clicks
        document.addEventListener('click', (e) => {
            const dropdownItem = e.target.closest('.dropdown-item');
            if (dropdownItem) {
                this.handleDropdownItemClick(e, dropdownItem);
            }
        });

        // Listen for clicks outside dropdowns
        document.addEventListener('click', this.handleDocumentClick);

        // Listen for keyboard events
        document.addEventListener('keydown', this.handleKeydown);

        // Listen for Bootstrap dropdown events
        document.addEventListener('show.bs.dropdown', (e) => {
            this.onDropdownShow(e);
        });

        document.addEventListener('shown.bs.dropdown', (e) => {
            this.onDropdownShown(e);
        });

        document.addEventListener('hide.bs.dropdown', (e) => {
            this.onDropdownHide(e);
        });

        document.addEventListener('hidden.bs.dropdown', (e) => {
            this.onDropdownHidden(e);
        });
    }

    /**
     * Set up dropdown state tracking
     */
    setupDropdownTracking() {
        // Track dropdown states for better management
        this.dropdowns.forEach((dropdown, id) => {
            const { element, menu } = dropdown;
            
            // Add custom attributes for tracking
            element.setAttribute('data-dropdown-id', id);
            if (menu) {
                menu.setAttribute('data-dropdown-id', id);
            }
        });
    }

    /**
     * Handle dropdown toggle clicks
     */
    handleDropdownToggle(event, toggle) {
        const dropdownId = toggle.getAttribute('data-dropdown-id') || toggle.id;
        const dropdown = this.dropdowns.get(dropdownId);
        
        if (!dropdown) {
            console.warn('Dropdown not found:', dropdownId);
            return;
        }

        // Close other open dropdowns first
        this.closeAllDropdowns(dropdownId);

        // Let Bootstrap handle the toggle
        // We'll track the state in the Bootstrap event handlers
    }

    /**
     * Handle dropdown item clicks
     */
    handleDropdownItemClick(event, item) {
        const href = item.getAttribute('href');
        const action = item.getAttribute('data-action');
        
        // Handle different types of dropdown items
        if (action) {
            event.preventDefault();
            this.executeAction(action, item);
        } else if (href && href !== '#') {
            // Let navigation controller handle navigation
            // Don't prevent default for proper navigation
            console.log('Dropdown navigation:', href);
        } else if (href === '#') {
            // Prevent default for placeholder links
            event.preventDefault();
        }

        // Close dropdown after item click (unless it's a submenu)
        if (!item.closest('.dropdown-submenu')) {
            this.closeDropdownContaining(item);
        }
    }

    /**
     * Execute dropdown item actions
     */
    executeAction(action, item) {
        console.log('Executing dropdown action:', action);
        
        switch (action) {
            case 'logout':
                this.handleLogout();
                break;
                
            case 'settings':
                this.navigateToSettings();
                break;
                
            case 'profile':
                this.navigateToProfile();
                break;
                
            case 'users':
                this.navigateToUsers();
                break;
                
            default:
                console.warn('Unknown dropdown action:', action);
                
                // Try to find a global handler
                if (window[action] && typeof window[action] === 'function') {
                    window[action]();
                } else {
                    console.error('No handler found for action:', action);
                }
                break;
        }
    }

    /**
     * Handle logout action
     */
    handleLogout() {
        if (window.aiSecretaryApp && window.aiSecretaryApp.authManager) {
            window.aiSecretaryApp.authManager.handleLogout();
        } else if (window.logout && typeof window.logout === 'function') {
            window.logout();
        } else {
            console.error('No logout handler available');
            // Fallback to simple redirect
            window.location.href = '/logout';
        }
    }

    /**
     * Navigate to settings
     */
    navigateToSettings() {
        if (window.aiSecretaryApp && window.aiSecretaryApp.navigationController) {
            window.aiSecretaryApp.navigationController.navigateTo('/settings');
        } else {
            window.location.href = '/settings';
        }
    }

    /**
     * Navigate to profile
     */
    navigateToProfile() {
        if (window.aiSecretaryApp && window.aiSecretaryApp.navigationController) {
            window.aiSecretaryApp.navigationController.navigateTo('/profile');
        } else {
            window.location.href = '/profile';
        }
    }

    /**
     * Navigate to users
     */
    navigateToUsers() {
        if (window.aiSecretaryApp && window.aiSecretaryApp.navigationController) {
            window.aiSecretaryApp.navigationController.navigateTo('/users');
        } else {
            window.location.href = '/users';
        }
    }

    /**
     * Handle clicks outside dropdowns
     */
    handleDocumentClick(event) {
        // Check if click is outside all dropdowns
        const clickedDropdown = event.target.closest('.dropdown');
        
        if (!clickedDropdown) {
            // Click is outside all dropdowns, close any open ones
            this.closeAllDropdowns();
        }
    }

    /**
     * Handle keyboard events
     */
    handleKeydown(event) {
        // Close dropdowns on Escape key
        if (event.key === 'Escape') {
            this.closeAllDropdowns();
        }
        
        // Handle arrow key navigation within dropdowns
        if (this.activeDropdown && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
            event.preventDefault();
            this.handleArrowKeyNavigation(event.key);
        }
    }

    /**
     * Handle arrow key navigation within dropdowns
     */
    handleArrowKeyNavigation(key) {
        if (!this.activeDropdown) return;
        
        const dropdown = this.dropdowns.get(this.activeDropdown);
        if (!dropdown || !dropdown.menu) return;
        
        const items = dropdown.menu.querySelectorAll('.dropdown-item:not(.disabled)');
        if (items.length === 0) return;
        
        const currentFocus = dropdown.menu.querySelector('.dropdown-item:focus');
        let currentIndex = currentFocus ? Array.from(items).indexOf(currentFocus) : -1;
        
        if (key === 'ArrowDown') {
            currentIndex = (currentIndex + 1) % items.length;
        } else if (key === 'ArrowUp') {
            currentIndex = currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
        }
        
        items[currentIndex].focus();
    }

    /**
     * Bootstrap dropdown event handlers
     */
    onDropdownShow(event) {
        const toggle = event.target;
        const dropdownId = toggle.getAttribute('data-dropdown-id') || toggle.id;
        const dropdown = this.dropdowns.get(dropdownId);
        
        if (dropdown) {
            dropdown.isOpen = true;
            this.activeDropdown = dropdownId;
            console.log('Dropdown showing:', dropdownId);
        }
    }

    onDropdownShown(event) {
        const toggle = event.target;
        const dropdownId = toggle.getAttribute('data-dropdown-id') || toggle.id;
        
        console.log('Dropdown shown:', dropdownId);
        
        // Focus first item for keyboard navigation
        const dropdown = this.dropdowns.get(dropdownId);
        if (dropdown && dropdown.menu) {
            const firstItem = dropdown.menu.querySelector('.dropdown-item:not(.disabled)');
            if (firstItem) {
                // Don't auto-focus to avoid interfering with mouse users
                // firstItem.focus();
            }
        }
    }

    onDropdownHide(event) {
        const toggle = event.target;
        const dropdownId = toggle.getAttribute('data-dropdown-id') || toggle.id;
        const dropdown = this.dropdowns.get(dropdownId);
        
        if (dropdown) {
            dropdown.isOpen = false;
            console.log('Dropdown hiding:', dropdownId);
        }
    }

    onDropdownHidden(event) {
        const toggle = event.target;
        const dropdownId = toggle.getAttribute('data-dropdown-id') || toggle.id;
        
        console.log('Dropdown hidden:', dropdownId);
        
        if (this.activeDropdown === dropdownId) {
            this.activeDropdown = null;
        }
    }

    /**
     * Close all dropdowns except the specified one
     */
    closeAllDropdowns(exceptId = null) {
        this.dropdowns.forEach((dropdown, id) => {
            if (id !== exceptId && dropdown.isOpen && dropdown.bootstrap) {
                try {
                    dropdown.bootstrap.hide();
                } catch (error) {
                    console.error('Error closing dropdown:', id, error);
                }
            }
        });
    }

    /**
     * Close dropdown containing the specified element
     */
    closeDropdownContaining(element) {
        const dropdownMenu = element.closest('.dropdown-menu');
        if (dropdownMenu) {
            const dropdownId = dropdownMenu.getAttribute('data-dropdown-id');
            const dropdown = this.dropdowns.get(dropdownId);
            
            if (dropdown && dropdown.bootstrap) {
                try {
                    dropdown.bootstrap.hide();
                } catch (error) {
                    console.error('Error closing dropdown:', dropdownId, error);
                }
            }
        }
    }

    /**
     * Get dropdown state
     */
    getDropdownState(dropdownId) {
        const dropdown = this.dropdowns.get(dropdownId);
        return dropdown ? {
            id: dropdownId,
            isOpen: dropdown.isOpen,
            element: dropdown.element,
            menu: dropdown.menu
        } : null;
    }

    /**
     * Get all dropdown states
     */
    getAllDropdownStates() {
        const states = {};
        this.dropdowns.forEach((dropdown, id) => {
            states[id] = {
                isOpen: dropdown.isOpen,
                element: dropdown.element,
                menu: dropdown.menu
            };
        });
        return states;
    }

    /**
     * Refresh dropdown initialization (useful after DOM changes)
     */
    refresh() {
        console.log('Refreshing dropdown manager...');
        
        // Clear existing dropdowns
        this.dropdowns.clear();
        this.activeDropdown = null;
        
        // Re-initialize
        this.initializeBootstrapDropdowns();
        this.setupDropdownTracking();
        
        console.log('Dropdown manager refreshed');
    }

    /**
     * Cleanup
     */
    cleanup() {
        // Remove event listeners
        document.removeEventListener('click', this.handleDocumentClick);
        document.removeEventListener('keydown', this.handleKeydown);
        
        // Dispose Bootstrap dropdowns
        this.dropdowns.forEach((dropdown) => {
            if (dropdown.bootstrap && typeof dropdown.bootstrap.dispose === 'function') {
                try {
                    dropdown.bootstrap.dispose();
                } catch (error) {
                    console.error('Error disposing dropdown:', error);
                }
            }
        });
        
        // Clear references
        this.dropdowns.clear();
        this.activeDropdown = null;
        this.isInitialized = false;
        
        console.log('Dropdown manager cleaned up');
    }
}

// Export for use in other modules
window.DropdownManager = DropdownManager;