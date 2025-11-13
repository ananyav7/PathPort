// PathPort - Main JavaScript File
// Handles global functionality and interactions

document.addEventListener('DOMContentLoaded', function() {
    
    // Global variables
    let isLoading = false;
    
    // Utility functions
    function showLoading(element) {
        if (element) {
            element.classList.add('loading');
            isLoading = true;
        }
    }
    
    function hideLoading(element) {
        if (element) {
            element.classList.remove('loading');
            isLoading = false;
        }
    }
    
    function showAlert(message, type = 'success') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} fade-in`;
        alertDiv.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-triangle' : 'info-circle'}"></i>
            ${message}
        `;
        
        // Position alert
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '20px';
        alertDiv.style.right = '20px';
        alertDiv.style.zIndex = '9999';
        
        document.body.appendChild(alertDiv);
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            alertDiv.style.opacity = '0';
            setTimeout(() => alertDiv.remove(), 300);
        }, 5000);
    }
    
    // Mobile menu toggle
    const mobileToggle = document.querySelector('.mobile-menu-toggle');
    const sidebar = document.querySelector('.sidebar');
    const navLinks = document.querySelector('.nav-links');
    
    if (mobileToggle) {
        mobileToggle.addEventListener('click', function() {
            if (sidebar) {
                sidebar.classList.toggle('active');
            }
            if (navLinks) {
                navLinks.classList.toggle('active');
            }
        });
    }
    
    // Close mobile menu when clicking outside
    document.addEventListener('click', function(event) {
        if (sidebar && sidebar.classList.contains('active') && 
            !sidebar.contains(event.target) && 
            !mobileToggle.contains(event.target)) {
            sidebar.classList.remove('active');
        }
    });
    
    // Form validation enhancement
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (isLoading) {
                e.preventDefault();
                return;
            }
            
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                showLoading(submitButton);
                
                // Restore button after form submission
                setTimeout(() => {
                    hideLoading(submitButton);
                }, 3000);
            }
        });
    });
    
    // Enhanced form field interactions
    const formControls = document.querySelectorAll('.form-control');
    formControls.forEach(control => {
        control.addEventListener('focus', function() {
            this.parentNode.classList.add('focused');
        });
        
        control.addEventListener('blur', function() {
            this.parentNode.classList.remove('focused');
            if (this.value.trim()) {
                this.parentNode.classList.add('has-value');
            } else {
                this.parentNode.classList.remove('has-value');
            }
        });
        
        // Initial check for pre-filled values
        if (control.value.trim()) {
            control.parentNode.classList.add('has-value');
        }
    });
    
    // Parcel status update functionality
    window.updateParcelStatus = function(parcelId, status) {
        if (isLoading) return;
        
        const statusElement = document.querySelector(`[data-parcel-id="${parcelId}"]`);
        if (statusElement) {
            showLoading(statusElement);
        }
        
        fetch(`/api/update-parcel-status/${parcelId}/${status}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert(`Parcel status updated to ${status.replace('_', ' ')}!`);
                    
                    // Update UI elements
                    const statusBadges = document.querySelectorAll(`[data-parcel="${parcelId}"] .status-badge`);
                    statusBadges.forEach(badge => {
                        badge.className = `status-badge status-${status.replace('_', '-')}`;
                        badge.textContent = status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                    });
                    
                    setTimeout(() => {
                        location.reload();
                    }, 1500);
                } else {
                    showAlert('Failed to update status. Please try again.', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('An error occurred. Please try again.', 'error');
            })
            .finally(() => {
                if (statusElement) {
                    hideLoading(statusElement);
                }
            });
    };
    
    // Accept parcel functionality
    window.acceptParcel = function(parcelId) {
        if (isLoading) return;
        
        if (!confirm('Are you sure you want to accept this parcel delivery?')) {
            return;
        }
        
        const acceptButton = document.querySelector(`[onclick="acceptParcel('${parcelId}')"]`);
        if (acceptButton) {
            showLoading(acceptButton);
        }
        
        window.location.href = `/api/accept-parcel/${parcelId}`;
    };
    
    // Real-time updates for dashboards
    function updateDashboardStats() {
        const statNumbers = document.querySelectorAll('.stat-number');
        statNumbers.forEach(stat => {
            if (Math.random() > 0.95) { // 5% chance of update
                const currentValue = parseInt(stat.textContent);
                const change = Math.floor(Math.random() * 3) - 1; // -1, 0, or 1
                const newValue = Math.max(0, currentValue + change);
                
                if (newValue !== currentValue) {
                    stat.textContent = newValue;
                    stat.classList.add('pulse');
                    setTimeout(() => stat.classList.remove('pulse'), 1000);
                }
            }
        });
    }
    
    // Start real-time updates for dashboard pages
    if (document.querySelector('.stats-section') || document.querySelector('.stats-grid')) {
        setInterval(updateDashboardStats, 30000); // Update every 30 seconds
    }
    
    // Enhanced table interactions
    const tables = document.querySelectorAll('.table');
    tables.forEach(table => {
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            row.addEventListener('mouseenter', function() {
                this.style.backgroundColor = 'var(--bg-light)';
                this.style.transform = 'scale(1.01)';
            });
            
            row.addEventListener('mouseleave', function() {
                this.style.backgroundColor = '';
                this.style.transform = '';
            });
        });
    });
    
    // Modal functionality
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
    };
    
    window.closeModal = function(modalId) {
        const modal = modalId ? document.getElementById(modalId) : document.querySelector('.modal[style*="block"]');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    };
    
    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target.classList.contains('modal')) {
            closeModal();
        }
    });
    
    // Escape key to close modal
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeModal();
        }
    });
    
    // Search functionality
    window.performSearch = function(searchTerm, targetTable) {
        const table = document.getElementById(targetTable);
        if (!table) return;
        
        const rows = table.querySelectorAll('tbody tr');
        const term = searchTerm.toLowerCase();
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            if (text.includes(term)) {
                row.style.display = '';
                row.classList.add('fade-in');
            } else {
                row.style.display = 'none';
                row.classList.remove('fade-in');
            }
        });
        
        // Update results count
        const visibleRows = table.querySelectorAll('tbody tr[style=""], tbody tr:not([style])');
        console.log(`Found ${visibleRows.length} results`);
    };
    
    // Auto-save functionality for forms
    const autoSaveForms = document.querySelectorAll('[data-autosave]');
    autoSaveForms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                const formData = new FormData(form);
                const data = Object.fromEntries(formData);
                
                // Save to localStorage
                localStorage.setItem(`pathport_autosave_${form.id}`, JSON.stringify(data));
                
                // Show save indicator
                showAlert('Changes saved automatically', 'info');
            });
        });
        
        // Load saved data on page load
        const savedData = localStorage.getItem(`pathport_autosave_${form.id}`);
        if (savedData) {
            try {
                const data = JSON.parse(savedData);
                Object.keys(data).forEach(key => {
                    const input = form.querySelector(`[name="${key}"]`);
                    if (input && !input.value) {
                        input.value = data[key];
                    }
                });
            } catch (e) {
                console.error('Error loading saved form data:', e);
            }
        }
    });
    
    // Notification system
    class NotificationSystem {
        constructor() {
            this.notifications = [];
            this.container = this.createContainer();
        }
        
        createContainer() {
            const container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                max-width: 300px;
            `;
            document.body.appendChild(container);
            return container;
        }
        
        show(message, type = 'info', duration = 5000) {
            const notification = document.createElement('div');
            notification.className = `alert alert-${type} fade-in`;
            notification.innerHTML = `
                <i class="fas fa-${this.getIcon(type)}"></i>
                <span>${message}</span>
                <button onclick="this.parentElement.remove()" style="background: none; border: none; color: inherit; float: right; cursor: pointer;">×</button>
            `;
            
            this.container.appendChild(notification);
            
            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                    }
                }, 300);
            }, duration);
        }
        
        getIcon(type) {
            const icons = {
                success: 'check-circle',
                error: 'exclamation-triangle',
                warning: 'exclamation-circle',
                info: 'info-circle'
            };
            return icons[type] || 'info-circle';
        }
    }
    
    // Initialize notification system
    window.notifications = new NotificationSystem();
    
    // Enhanced user feedback
    const clickableElements = document.querySelectorAll('button, .btn, .action-card, .stat-card');
    clickableElements.forEach(element => {
        element.addEventListener('click', function(e) {
            // Add ripple effect
            const ripple = document.createElement('span');
            ripple.className = 'ripple-effect';
            ripple.style.cssText = `
                position: absolute;
                border-radius: 50%;
                background: rgba(255,255,255,0.6);
                transform: scale(0);
                animation: ripple 0.6s linear;
                pointer-events: none;
            `;
            
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.height, rect.width);
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (e.clientX - rect.left - size/2) + 'px';
            ripple.style.top = (e.clientY - rect.top - size/2) + 'px';
            
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            
            setTimeout(() => {
                if (ripple.parentElement) {
                    ripple.remove();
                }
            }, 600);
        });
    });
    
    // Add CSS for ripple effect
    const style = document.createElement('style');
    style.textContent = `
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
    
    // Performance monitoring
    if ('performance' in window) {
        window.addEventListener('load', function() {
            setTimeout(function() {
                const perfData = performance.timing;
                const loadTime = perfData.loadEventEnd - perfData.navigationStart;
                console.log(`PathPort loaded in ${loadTime}ms`);
            }, 0);
        });
    }
    
    // Initialize tooltips for buttons
    const buttonsWithTooltips = document.querySelectorAll('[data-tooltip]');
    buttonsWithTooltips.forEach(button => {
        button.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = this.getAttribute('data-tooltip');
            tooltip.style.cssText = `
                position: absolute;
                background: rgba(0,0,0,0.8);
                color: white;
                padding: 0.5rem;
                border-radius: 4px;
                font-size: 0.8rem;
                z-index: 10000;
                pointer-events: none;
                white-space: nowrap;
            `;
            
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = (rect.left + rect.width/2 - tooltip.offsetWidth/2) + 'px';
            tooltip.style.top = (rect.top - tooltip.offsetHeight - 5) + 'px';
            
            this._tooltip = tooltip;
        });
        
        button.addEventListener('mouseleave', function() {
            if (this._tooltip) {
                this._tooltip.remove();
                this._tooltip = null;
            }
        });
    });
    
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Add loading states to all links
    const links = document.querySelectorAll('a[href]:not([href^="#"]):not([href^="javascript:"])');
    links.forEach(link => {
        link.addEventListener('click', function() {
            if (!this.target || this.target === '_self') {
                const loadingIndicator = document.createElement('div');
                loadingIndicator.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
                loadingIndicator.style.cssText = `
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: white;
                    padding: 2rem;
                    border-radius: 10px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                    z-index: 10001;
                    color: var(--primary-green);
                    font-weight: bold;
                `;
                document.body.appendChild(loadingIndicator);
                
                setTimeout(() => {
                    if (loadingIndicator.parentElement) {
                        loadingIndicator.remove();
                    }
                }, 3000);
            }
        });
    });
    
    // Initialize page-specific functionality
    const currentPage = window.location.pathname;
    
    if (currentPage.includes('dashboard')) {
        initializeDashboard();
    } else if (currentPage.includes('create-parcel')) {
        initializeParcelCreation();
    } else if (currentPage.includes('track')) {
        initializeTracking();
    }
    
    function initializeDashboard() {
        // Dashboard-specific functionality
        console.log('Dashboard initialized');
        
        // Auto-refresh dashboard data
        setInterval(() => {
            if (document.hasFocus()) {
                // Refresh dashboard stats
                updateDashboardStats();
            }
        }, 60000); // Every minute
    }
    
    function initializeParcelCreation() {
        // Parcel creation form enhancements
        console.log('Parcel creation form initialized');
        
        // Real-time form validation
        const form = document.getElementById('parcelForm');
        if (form) {
            const inputs = form.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                input.addEventListener('blur', validateField);
                input.addEventListener('input', clearValidation);
            });
        }
    }
    
    function initializeTracking() {
        // Tracking page functionality
        console.log('Tracking page initialized');
        
        // Auto-refresh tracking data
        setInterval(() => {
            if (document.hasFocus()) {
                // Update parcel statuses
                refreshParcelStatuses();
            }
        }, 30000); // Every 30 seconds
    }
    
    function validateField(event) {
        const field = event.target;
        const value = field.value.trim();
        
        // Remove existing validation classes
        field.classList.remove('is-valid', 'is-invalid');
        
        if (field.hasAttribute('required') && !value) {
            field.classList.add('is-invalid');
            showFieldError(field, 'This field is required');
        } else if (field.type === 'email' && value && !isValidEmail(value)) {
            field.classList.add('is-invalid');
            showFieldError(field, 'Please enter a valid email address');
        } else if (field.type === 'number' && value) {
            const num = parseFloat(value);
            const min = parseFloat(field.getAttribute('min'));
            const max = parseFloat(field.getAttribute('max'));
            
            if (min && num < min) {
                field.classList.add('is-invalid');
                showFieldError(field, `Value must be at least ${min}`);
            } else if (max && num > max) {
                field.classList.add('is-invalid');
                showFieldError(field, `Value must not exceed ${max}`);
            } else {
                field.classList.add('is-valid');
                clearFieldError(field);
            }
        } else if (value) {
            field.classList.add('is-valid');
            clearFieldError(field);
        }
    }
    
    function clearValidation(event) {
        const field = event.target;
        field.classList.remove('is-valid', 'is-invalid');
        clearFieldError(field);
    }
    
    function showFieldError(field, message) {
        clearFieldError(field);
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        errorDiv.style.cssText = `
            color: var(--danger);
            font-size: 0.8rem;
            margin-top: 0.25rem;
            display: flex;
            align-items: center;
            gap: 0.25rem;
        `;
        errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        
        field.parentNode.appendChild(errorDiv);
    }
    
    function clearFieldError(field) {
        const existingError = field.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }
    }
    
    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
    
    function refreshParcelStatuses() {
        const parcelElements = document.querySelectorAll('[data-parcel-id]');
        parcelElements.forEach(element => {
            const parcelId = element.getAttribute('data-parcel-id');
            // In a real app, you would fetch updated status from the server
            console.log(`Refreshing status for parcel ${parcelId}`);
        });
    }
    
    // Error handling for fetch requests
    window.addEventListener('unhandledrejection', function(event) {
        console.error('Unhandled promise rejection:', event.reason);
        showAlert('An unexpected error occurred. Please refresh the page.', 'error');
    });
    
    // Connection status monitoring
    let isOnline = navigator.onLine;
    
    window.addEventListener('online', function() {
        if (!isOnline) {
            isOnline = true;
            showAlert('Connection restored!', 'success');
        }
    });
    
    window.addEventListener('offline', function() {
        isOnline = false;
        showAlert('Connection lost. Some features may not work.', 'warning');
    });
    
    // Initialize service worker for offline functionality (if available)
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(function(error) {
            console.log('Service Worker registration failed:', error);
        });
    }
    
    console.log('PathPort application initialized successfully');
});

// Additional utility functions available globally
window.PathPort = {
    version: '1.0.0',
    
    utils: {
        formatDate: function(date) {
            return new Date(date).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        },
        
        formatDistance: function(meters) {
            if (meters < 1000) {
                return `${meters}m`;
            }
            return `${(meters / 1000).toFixed(1)}km`;
        },
        
        generateTrackingCode: function() {
            return 'PP' + Date.now().toString(36).toUpperCase() + Math.random().toString(36).substr(2, 5).toUpperCase();
        },
        
        calculateEstimatedTime: function(distance, urgency) {
            const baseTime = distance / 1000 * 0.5; // 30 minutes per km base
            const multipliers = {
                'express': 0.5,
                'urgent': 0.75,
                'normal': 1.5
            };
            
            return Math.ceil(baseTime * (multipliers[urgency] || 1));
        }
    },
    
    api: {
        baseUrl: window.location.origin,
        
        get: function(endpoint) {
            return fetch(`${this.baseUrl}/api${endpoint}`)
                .then(response => response.json());
        },
        
        post: function(endpoint, data) {
            return fetch(`${this.baseUrl}/api${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            }).then(response => response.json());
        }
    }
};