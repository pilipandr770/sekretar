/**
 * Inbox Features Module
 * Lazy-loaded features specific to the inbox page
 */

class InboxFeatures {
    constructor() {
        this.initialized = false;
        this.messageHandlers = new Map();
        this.conversationCache = new Map();
        
        this.init();
    }
    
    init() {
        if (this.initialized) return;
        
        console.log('Initializing inbox features...');
        
        // Initialize inbox-specific UI components
        this.initializeMessageList();
        this.initializeComposer();
        this.initializeFilters();
        this.initializeSearch();
        
        // Setup WebSocket handlers for real-time updates
        this.setupRealtimeHandlers();
        
        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();
        
        this.initialized = true;
        console.log('Inbox features initialized');
    }
    
    initializeMessageList() {
        const messageList = document.getElementById('message-list');
        if (!messageList) return;
        
        // Setup infinite scroll
        this.setupInfiniteScroll(messageList);
        
        // Setup message actions
        this.setupMessageActions(messageList);
        
        // Setup drag and drop for attachments
        this.setupDragAndDrop(messageList);
    }
    
    setupInfiniteScroll(container) {
        if (!window.browserCompatibility.isSupported('intersectionObserver')) {
            console.log('IntersectionObserver not supported, using scroll events');
            this.setupScrollBasedLoading(container);
            return;
        }
        
        const loadingTrigger = document.createElement('div');
        loadingTrigger.className = 'loading-trigger';
        loadingTrigger.style.height = '1px';
        container.appendChild(loadingTrigger);
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadMoreMessages();
                }
            });
        }, {
            rootMargin: '100px'
        });
        
        observer.observe(loadingTrigger);
    }
    
    setupScrollBasedLoading(container) {
        let loading = false;
        
        container.addEventListener('scroll', () => {
            if (loading) return;
            
            const { scrollTop, scrollHeight, clientHeight } = container;
            if (scrollTop + clientHeight >= scrollHeight - 100) {
                loading = true;
                this.loadMoreMessages().finally(() => {
                    loading = false;
                });
            }
        });
    }
    
    async loadMoreMessages() {
        try {
            const response = await fetch('/api/v1/inbox/messages?offset=' + this.getMessageCount());
            const data = await response.json();
            
            if (data.success && data.data.messages.length > 0) {
                this.appendMessages(data.data.messages);
            }
        } catch (error) {
            console.error('Failed to load more messages:', error);
        }
    }
    
    getMessageCount() {
        return document.querySelectorAll('.message-item').length;
    }
    
    appendMessages(messages) {
        const messageList = document.getElementById('message-list');
        if (!messageList) return;
        
        messages.forEach(message => {
            const messageElement = this.createMessageElement(message);
            messageList.appendChild(messageElement);
        });
    }
    
    createMessageElement(message) {
        const div = document.createElement('div');
        div.className = 'message-item';
        div.dataset.messageId = message.id;
        div.innerHTML = `
            <div class="message-header">
                <span class="message-sender">${message.sender}</span>
                <span class="message-time">${this.formatTime(message.timestamp)}</span>
            </div>
            <div class="message-subject">${message.subject}</div>
            <div class="message-preview">${message.preview}</div>
        `;
        
        return div;
    }
    
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffHours = diffMs / (1000 * 60 * 60);
        
        if (diffHours < 24) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else {
            return date.toLocaleDateString();
        }
    }
    
    setupMessageActions(container) {
        container.addEventListener('click', (e) => {
            const messageItem = e.target.closest('.message-item');
            if (!messageItem) return;
            
            const messageId = messageItem.dataset.messageId;
            
            if (e.target.matches('.btn-reply')) {
                this.replyToMessage(messageId);
            } else if (e.target.matches('.btn-delete')) {
                this.deleteMessage(messageId);
            } else if (e.target.matches('.btn-archive')) {
                this.archiveMessage(messageId);
            } else {
                this.openMessage(messageId);
            }
        });
    }
    
    setupDragAndDrop(container) {
        container.addEventListener('dragover', (e) => {
            e.preventDefault();
            container.classList.add('drag-over');
        });
        
        container.addEventListener('dragleave', (e) => {
            if (!container.contains(e.relatedTarget)) {
                container.classList.remove('drag-over');
            }
        });
        
        container.addEventListener('drop', (e) => {
            e.preventDefault();
            container.classList.remove('drag-over');
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                this.handleFileUpload(files);
            }
        });
    }
    
    initializeComposer() {
        const composer = document.getElementById('message-composer');
        if (!composer) return;
        
        // Setup auto-save
        this.setupAutoSave(composer);
        
        // Setup attachment handling
        this.setupAttachments(composer);
        
        // Setup send button
        this.setupSendButton(composer);
    }
    
    setupAutoSave(composer) {
        const textarea = composer.querySelector('textarea');
        if (!textarea) return;
        
        let autoSaveTimer;
        
        textarea.addEventListener('input', () => {
            clearTimeout(autoSaveTimer);
            autoSaveTimer = setTimeout(() => {
                this.saveDraft(textarea.value);
            }, 2000);
        });
    }
    
    saveDraft(content) {
        if (window.browserCompatibility.isSupported('localStorage')) {
            localStorage.setItem('inbox_draft', content);
        }
    }
    
    loadDraft() {
        if (window.browserCompatibility.isSupported('localStorage')) {
            return localStorage.getItem('inbox_draft') || '';
        }
        return '';
    }
    
    setupAttachments(composer) {
        const attachmentInput = composer.querySelector('input[type="file"]');
        const attachmentList = composer.querySelector('.attachment-list');
        
        if (attachmentInput && attachmentList) {
            attachmentInput.addEventListener('change', (e) => {
                const files = Array.from(e.target.files);
                this.displayAttachments(files, attachmentList);
            });
        }
    }
    
    displayAttachments(files, container) {
        container.innerHTML = '';
        
        files.forEach(file => {
            const attachmentDiv = document.createElement('div');
            attachmentDiv.className = 'attachment-item';
            attachmentDiv.innerHTML = `
                <span class="attachment-name">${file.name}</span>
                <span class="attachment-size">${this.formatFileSize(file.size)}</span>
                <button type="button" class="btn btn-sm btn-outline-danger btn-remove">×</button>
            `;
            
            attachmentDiv.querySelector('.btn-remove').addEventListener('click', () => {
                attachmentDiv.remove();
            });
            
            container.appendChild(attachmentDiv);
        });
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    setupSendButton(composer) {
        const sendButton = composer.querySelector('.btn-send');
        if (!sendButton) return;
        
        sendButton.addEventListener('click', (e) => {
            e.preventDefault();
            this.sendMessage(composer);
        });
    }
    
    async sendMessage(composer) {
        const formData = new FormData(composer);
        
        try {
            const response = await fetch('/api/v1/inbox/send', {
                method: 'POST',
                body: formData,
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.clearComposer(composer);
                this.showSuccess('Message sent successfully');
            } else {
                this.showError(data.error?.message || 'Failed to send message');
            }
        } catch (error) {
            console.error('Failed to send message:', error);
            this.showError('Network error occurred');
        }
    }
    
    clearComposer(composer) {
        composer.reset();
        const attachmentList = composer.querySelector('.attachment-list');
        if (attachmentList) {
            attachmentList.innerHTML = '';
        }
        
        // Clear draft
        if (window.browserCompatibility.isSupported('localStorage')) {
            localStorage.removeItem('inbox_draft');
        }
    }
    
    initializeFilters() {
        const filterButtons = document.querySelectorAll('.filter-btn');
        
        filterButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const filter = button.dataset.filter;
                this.applyFilter(filter);
                
                // Update active state
                filterButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
            });
        });
    }
    
    applyFilter(filter) {
        const messageItems = document.querySelectorAll('.message-item');
        
        messageItems.forEach(item => {
            const shouldShow = this.messageMatchesFilter(item, filter);
            item.style.display = shouldShow ? '' : 'none';
        });
    }
    
    messageMatchesFilter(messageItem, filter) {
        switch (filter) {
            case 'all':
                return true;
            case 'unread':
                return !messageItem.classList.contains('read');
            case 'important':
                return messageItem.classList.contains('important');
            case 'archived':
                return messageItem.classList.contains('archived');
            default:
                return true;
        }
    }
    
    initializeSearch() {
        const searchInput = document.getElementById('message-search');
        if (!searchInput) return;
        
        let searchTimer;
        
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                this.performSearch(e.target.value);
            }, 300);
        });
    }
    
    performSearch(query) {
        if (!query.trim()) {
            this.clearSearch();
            return;
        }
        
        const messageItems = document.querySelectorAll('.message-item');
        
        messageItems.forEach(item => {
            const text = item.textContent.toLowerCase();
            const matches = text.includes(query.toLowerCase());
            item.style.display = matches ? '' : 'none';
        });
    }
    
    clearSearch() {
        const messageItems = document.querySelectorAll('.message-item');
        messageItems.forEach(item => {
            item.style.display = '';
        });
    }
    
    setupRealtimeHandlers() {
        if (!window.wsClient) return;
        
        // Listen for new messages
        document.addEventListener('message:new', (e) => {
            this.handleNewMessage(e.detail);
        });
        
        // Listen for message updates
        document.addEventListener('message:updated', (e) => {
            this.handleMessageUpdate(e.detail);
        });
    }
    
    handleNewMessage(data) {
        const messageElement = this.createMessageElement(data.message);
        const messageList = document.getElementById('message-list');
        
        if (messageList) {
            messageList.insertBefore(messageElement, messageList.firstChild);
            
            // Show notification
            this.showNotification('New Message', {
                body: data.message.subject,
                icon: '/static/images/message-icon.png'
            });
        }
    }
    
    handleMessageUpdate(data) {
        const messageElement = document.querySelector(`[data-message-id="${data.message.id}"]`);
        if (messageElement) {
            // Update message element
            this.updateMessageElement(messageElement, data.message);
        }
    }
    
    updateMessageElement(element, message) {
        const subjectElement = element.querySelector('.message-subject');
        const previewElement = element.querySelector('.message-preview');
        
        if (subjectElement) subjectElement.textContent = message.subject;
        if (previewElement) previewElement.textContent = message.preview;
        
        // Update read status
        if (message.read) {
            element.classList.add('read');
        } else {
            element.classList.remove('read');
        }
    }
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Only handle shortcuts when not in input fields
            if (e.target.matches('input, textarea, select')) return;
            
            switch (e.key) {
                case 'c':
                    if (e.ctrlKey || e.metaKey) return; // Don't interfere with copy
                    this.openComposer();
                    e.preventDefault();
                    break;
                case 'r':
                    this.replyToSelectedMessage();
                    e.preventDefault();
                    break;
                case 'Delete':
                case 'Backspace':
                    this.deleteSelectedMessage();
                    e.preventDefault();
                    break;
                case 'a':
                    this.archiveSelectedMessage();
                    e.preventDefault();
                    break;
            }
        });
    }
    
    openComposer() {
        const composer = document.getElementById('message-composer');
        if (composer) {
            composer.scrollIntoView({ behavior: 'smooth' });
            const textarea = composer.querySelector('textarea');
            if (textarea) textarea.focus();
        }
    }
    
    replyToSelectedMessage() {
        const selected = document.querySelector('.message-item.selected');
        if (selected) {
            this.replyToMessage(selected.dataset.messageId);
        }
    }
    
    deleteSelectedMessage() {
        const selected = document.querySelector('.message-item.selected');
        if (selected) {
            this.deleteMessage(selected.dataset.messageId);
        }
    }
    
    archiveSelectedMessage() {
        const selected = document.querySelector('.message-item.selected');
        if (selected) {
            this.archiveMessage(selected.dataset.messageId);
        }
    }
    
    // Message actions
    async replyToMessage(messageId) {
        try {
            const response = await fetch(`/api/v1/inbox/messages/${messageId}`);
            const data = await response.json();
            
            if (data.success) {
                this.populateReply(data.data.message);
            }
        } catch (error) {
            console.error('Failed to load message for reply:', error);
        }
    }
    
    populateReply(message) {
        const composer = document.getElementById('message-composer');
        if (!composer) return;
        
        const subjectInput = composer.querySelector('input[name="subject"]');
        const bodyTextarea = composer.querySelector('textarea[name="body"]');
        
        if (subjectInput) {
            subjectInput.value = `Re: ${message.subject}`;
        }
        
        if (bodyTextarea) {
            bodyTextarea.value = `\n\n--- Original Message ---\n${message.body}`;
        }
        
        this.openComposer();
    }
    
    async deleteMessage(messageId) {
        if (!confirm('Are you sure you want to delete this message?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/v1/inbox/messages/${messageId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                if (messageElement) {
                    messageElement.remove();
                }
                this.showSuccess('Message deleted');
            } else {
                this.showError(data.error?.message || 'Failed to delete message');
            }
        } catch (error) {
            console.error('Failed to delete message:', error);
            this.showError('Network error occurred');
        }
    }
    
    async archiveMessage(messageId) {
        try {
            const response = await fetch(`/api/v1/inbox/messages/${messageId}/archive`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                if (messageElement) {
                    messageElement.classList.add('archived');
                }
                this.showSuccess('Message archived');
            } else {
                this.showError(data.error?.message || 'Failed to archive message');
            }
        } catch (error) {
            console.error('Failed to archive message:', error);
            this.showError('Network error occurred');
        }
    }
    
    openMessage(messageId) {
        window.location.href = `/inbox/message/${messageId}`;
    }
    
    handleFileUpload(files) {
        console.log('File upload not implemented:', files);
    }
    
    showNotification(title, options) {
        if (window.browserCompatibility.isSupported('notifications')) {
            new Notification(title, options);
        } else {
            console.log(`Notification: ${title}`, options.body);
        }
    }
    
    showSuccess(message) {
        this.showAlert('success', message);
    }
    
    showError(message) {
        this.showAlert('danger', message);
    }
    
    showAlert(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 1050; max-width: 300px;';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

// Initialize inbox features
window.InboxFeatures = InboxFeatures;

// Auto-initialize if on inbox page
if (document.body.dataset.page === 'inbox') {
    document.addEventListener('DOMContentLoaded', () => {
        window.inboxFeatures = new InboxFeatures();
    });
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = InboxFeatures;
}