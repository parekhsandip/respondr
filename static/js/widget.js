/*!
 * Respondr Support Widget
 * Embeddable customer support widget for websites
 */

(function() {
    'use strict';

    // Capture user configuration IMMEDIATELY before anything else
    var userConfig = window.RespondrWidget || {};

    // Default configuration
    var defaultConfig = {
        apiUrl: '',
        primaryColor: '#3B82F6',
        position: 'bottom-right',
        welcomeMessage: 'Hi! How can we help you today?',
        requireName: true,
        requireSubject: true,
        allowAttachments: true,
        debug: false
    };

    // Widget state
    var widget = {
        config: {},
        isOpen: false,
        isLoaded: false,
        elements: {}
    };

    // Initialize the widget
    function init() {
        // Merge configuration with captured user config
        widget.config = Object.assign({}, defaultConfig, userConfig);

        // Ensure apiUrl is properly set (override empty string if user provided one)
        if (userConfig.apiUrl) {
            widget.config.apiUrl = userConfig.apiUrl;
        }

        if (widget.config.debug) {
            console.log('Respondr Widget: Configuration merged:', widget.config);
            console.log('User config apiUrl:', userConfig.apiUrl);
            console.log('Final config apiUrl:', widget.config.apiUrl);
        }

        if (!widget.config.apiUrl) {
            console.error('Respondr Widget: apiUrl is required');
            console.log('Available userConfig:', userConfig);
            return;
        }

        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', createWidget);
        } else {
            createWidget();
        }
    }

    // Create the widget elements
    function createWidget() {
        if (widget.isLoaded) return;

        createStyles();
        createButton();
        createModal();

        widget.isLoaded = true;

        if (widget.config.debug) {
            console.log('Respondr Widget: Initialized with config', widget.config);
        }
    }

    // Create widget styles
    function createStyles() {
        var css = `
            .respondr-widget * {
                box-sizing: border-box;
            }

            .respondr-button {
                position: fixed;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: ${widget.config.primaryColor};
                border: none;
                cursor: pointer;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                z-index: 9999;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.3s ease;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                color: white;
            }

            .respondr-button svg {
                width: 24px;
                height: 24px;
                color: white;
            }

            .respondr-button:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 25px rgba(0, 0, 0, 0.2);
            }

            .respondr-button.bottom-right {
                bottom: 20px;
                right: 20px;
            }

            .respondr-button.bottom-left {
                bottom: 20px;
                left: 20px;
            }

            .respondr-button.top-right {
                top: 20px;
                right: 20px;
            }

            .respondr-button.top-left {
                top: 20px;
                left: 20px;
            }

            .respondr-button svg {
                width: 24px;
                height: 24px;
                fill: white;
                stroke: white;
                transition: transform 0.3s ease;
            }

            .respondr-button.open svg {
                transform: rotate(45deg);
            }

            .respondr-modal {
                position: fixed;
                z-index: 10000;
                width: 380px;
                max-height: 600px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                transform: scale(0.8);
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                overflow: hidden;
            }

            .respondr-modal.open {
                transform: scale(1);
                opacity: 1;
                visibility: visible;
            }

            .respondr-modal.bottom-right {
                bottom: 100px;
                right: 20px;
            }

            .respondr-modal.bottom-left {
                bottom: 100px;
                left: 20px;
            }

            .respondr-modal.top-right {
                top: 100px;
                right: 20px;
            }

            .respondr-modal.top-left {
                top: 100px;
                left: 20px;
            }

            .respondr-header {
                background: ${widget.config.primaryColor};
                color: white;
                padding: 20px;
                border-radius: 12px 12px 0 0;
            }

            .respondr-header h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 600;
            }

            .respondr-header p {
                margin: 5px 0 0 0;
                font-size: 14px;
                opacity: 0.9;
            }

            .respondr-form {
                padding: 20px;
                max-height: 450px;
                overflow-y: auto;
            }

            .respondr-form-group {
                margin-bottom: 16px;
            }

            .respondr-form-group label {
                display: block;
                margin-bottom: 6px;
                font-size: 14px;
                font-weight: 500;
                color: #374151;
            }

            .respondr-form-group label.required::after {
                content: ' *';
                color: #EF4444;
            }

            .respondr-form-group input,
            .respondr-form-group textarea {
                width: 100%;
                padding: 10px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                font-size: 14px;
                font-family: inherit;
                transition: border-color 0.2s ease;
            }

            .respondr-form-group input:focus,
            .respondr-form-group textarea:focus {
                outline: none;
                border-color: ${widget.config.primaryColor};
                box-shadow: 0 0 0 2px ${widget.config.primaryColor}20;
            }

            .respondr-form-group textarea {
                resize: vertical;
                min-height: 80px;
            }

            .respondr-submit {
                width: 100%;
                background: ${widget.config.primaryColor};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: background-color 0.2s ease;
            }

            .respondr-submit:hover {
                opacity: 0.9;
            }

            .respondr-submit:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }

            .respondr-file-input {
                border: 2px dashed #D1D5DB;
                border-radius: 6px;
                padding: 12px;
                background: #F9FAFB;
                cursor: pointer;
                transition: border-color 0.2s ease;
            }

            .respondr-file-input:hover {
                border-color: ${widget.config.primaryColor};
            }

            .respondr-file-info {
                margin-top: 4px;
            }

            .respondr-file-info small {
                color: #6B7280;
                font-size: 12px;
            }

            .respondr-file-error {
                color: #DC2626;
                font-size: 12px;
                margin-top: 4px;
            }

            .respondr-loading {
                display: none;
                text-align: center;
                padding: 20px;
                color: #6B7280;
                font-size: 14px;
            }

            .respondr-success {
                display: none;
                text-align: center;
                padding: 30px 20px;
                color: #059669;
            }

            .respondr-success svg {
                width: 48px;
                height: 48px;
                margin-bottom: 16px;
                color: #10B981;
            }

            .respondr-error {
                display: none;
                background: #FEF2F2;
                color: #DC2626;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
                margin-bottom: 16px;
            }

            .respondr-close {
                position: absolute;
                top: 20px;
                right: 20px;
                background: none;
                border: none;
                color: white;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                opacity: 0.7;
                transition: opacity 0.2s ease;
            }

            .respondr-close:hover {
                opacity: 1;
            }

            .respondr-close svg {
                width: 18px;
                height: 18px;
            }

            @media (max-width: 480px) {
                .respondr-modal {
                    width: calc(100vw - 40px);
                    left: 20px !important;
                    right: 20px !important;
                }
            }
        `;

        var style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    }

    // Create the toggle button
    function createButton() {
        var button = document.createElement('button');
        button.className = 'respondr-button ' + widget.config.position;
        button.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
            </svg>
        `;

        button.addEventListener('click', toggleWidget);
        document.body.appendChild(button);

        widget.elements.button = button;
    }

    // Create the modal
    function createModal() {
        var modal = document.createElement('div');
        modal.className = 'respondr-modal respondr-widget ' + widget.config.position;

        modal.innerHTML = `
            <div class="respondr-header">
                <button class="respondr-close" onclick="RespondrWidget.close()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
                <h3>Contact Support</h3>
                <p>${widget.config.welcomeMessage}</p>
            </div>

            <div class="respondr-error" id="respondr-error"></div>

            <form class="respondr-form" id="respondr-form">
                ${widget.config.requireName ? `
                <div class="respondr-form-group">
                    <label for="respondr-name" class="required">Name</label>
                    <input type="text" id="respondr-name" name="name" required>
                </div>
                ` : ''}

                <div class="respondr-form-group">
                    <label for="respondr-email" class="required">Email</label>
                    <input type="email" id="respondr-email" name="email" required>
                </div>

                ${widget.config.requireSubject ? `
                <div class="respondr-form-group">
                    <label for="respondr-subject" class="required">Subject</label>
                    <input type="text" id="respondr-subject" name="subject" required>
                </div>
                ` : ''}

                <div class="respondr-form-group">
                    <label for="respondr-message" class="required">Message</label>
                    <textarea id="respondr-message" name="message" required placeholder="How can we help you?"></textarea>
                </div>

                ${widget.config.allowAttachments ? `
                <div class="respondr-form-group">
                    <label for="respondr-attachment">Attachment</label>
                    <input type="file" id="respondr-attachment" name="attachment" accept=".jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.txt,.zip" class="respondr-file-input">
                    <div class="respondr-file-info">
                        <small>Maximum file size: 1MB</small>
                    </div>
                    <div id="respondr-file-error" class="respondr-file-error" style="display: none;"></div>
                </div>
                ` : ''}

                <button type="submit" class="respondr-submit">Send Message</button>
            </form>

            <div class="respondr-loading" id="respondr-loading">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    <path d="M21 12a9 9 0 01-9 9"/>
                </svg>
                Sending your message...
            </div>

            <div class="respondr-success" id="respondr-success">
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <h4 style="margin: 0 0 8px 0; font-size: 16px;">Message Sent!</h4>
                <p style="margin: 0; font-size: 14px; color: #6B7280;">We'll get back to you as soon as possible.</p>
            </div>
        `;

        // Add form submission handler
        modal.querySelector('#respondr-form').addEventListener('submit', handleSubmit);

        // Add file input validation if attachments are allowed
        if (widget.config.allowAttachments) {
            var fileInput = modal.querySelector('#respondr-attachment');
            var fileError = modal.querySelector('#respondr-file-error');

            if (fileInput) {
                fileInput.addEventListener('change', function(e) {
                    var file = e.target.files[0];
                    var maxSize = 1024 * 1024; // 1MB in bytes

                    if (file && file.size > maxSize) {
                        fileError.textContent = 'File size must be less than 1MB';
                        fileError.style.display = 'block';
                        e.target.value = ''; // Clear the input
                    } else {
                        fileError.style.display = 'none';
                    }
                });
            }
        }

        document.body.appendChild(modal);
        widget.elements.modal = modal;
    }

    // Toggle widget open/close
    function toggleWidget() {
        if (widget.isOpen) {
            closeWidget();
        } else {
            openWidget();
        }
    }

    // Open widget
    function openWidget() {
        widget.elements.modal.classList.add('open');
        widget.elements.button.classList.add('open');
        widget.isOpen = true;

        // Focus first input
        setTimeout(function() {
            var firstInput = widget.elements.modal.querySelector('input, textarea');
            if (firstInput) firstInput.focus();
        }, 300);
    }

    // Close widget
    function closeWidget() {
        widget.elements.modal.classList.remove('open');
        widget.elements.button.classList.remove('open');
        widget.isOpen = false;
    }

    // Handle form submission
    function handleSubmit(e) {
        e.preventDefault();

        var form = e.target;
        var formData = new FormData(form);
        var fileInput = form.querySelector('#respondr-attachment');
        var hasFile = fileInput && fileInput.files && fileInput.files.length > 0;

        showLoading();
        hideError();

        if (widget.config.debug) {
            console.log('Submitting widget form to:', widget.config.apiUrl + '/api/widget/submit');
            console.log('Has file attachment:', hasFile);
            if (hasFile) {
                console.log('File:', fileInput.files[0].name, fileInput.files[0].size + ' bytes');
            }
        }

        var requestOptions = {
            method: 'POST'
        };

        // If we have a file, send as FormData, otherwise send as JSON
        if (hasFile) {
            requestOptions.body = formData;
            // Don't set Content-Type header - let the browser set it with boundary
        } else {
            var data = {};
            // Convert FormData to object for JSON submission
            for (var pair of formData.entries()) {
                if (pair[0] !== 'attachment') { // Skip empty file field
                    data[pair[0]] = pair[1];
                }
            }
            requestOptions.headers = {
                'Content-Type': 'application/json',
            };
            requestOptions.body = JSON.stringify(data);
        }

        // Submit to API
        fetch(widget.config.apiUrl + '/api/widget/submit', requestOptions)
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + response.statusText);
            }
            return response.json();
        })
        .then(function(result) {
            if (widget.config.debug) {
                console.log('Widget submission response:', result);
            }

            if (result.success) {
                showSuccess();
                form.reset();

                // Close widget after 3 seconds
                setTimeout(function() {
                    closeWidget();
                    hideSuccess();
                    showForm();
                }, 3000);
            } else {
                throw new Error(result.message || 'Failed to send message');
            }
        })
        .catch(function(error) {
            console.error('Widget submission error:', error);
            showError(error.message || 'Failed to send message. Please try again.');
            showForm();
        });
    }

    // Show loading state
    function showLoading() {
        document.getElementById('respondr-form').style.display = 'none';
        document.getElementById('respondr-loading').style.display = 'block';
    }

    // Show form
    function showForm() {
        document.getElementById('respondr-form').style.display = 'block';
        document.getElementById('respondr-loading').style.display = 'none';
    }

    // Show success state
    function showSuccess() {
        document.getElementById('respondr-form').style.display = 'none';
        document.getElementById('respondr-loading').style.display = 'none';
        document.getElementById('respondr-success').style.display = 'block';
    }

    // Hide success state
    function hideSuccess() {
        document.getElementById('respondr-success').style.display = 'none';
    }

    // Show error
    function showError(message) {
        var errorEl = document.getElementById('respondr-error');
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }

    // Hide error
    function hideError() {
        document.getElementById('respondr-error').style.display = 'none';
    }

    // Public API
    window.RespondrWidget = {
        open: openWidget,
        close: closeWidget,
        toggle: toggleWidget,
        config: widget.config,
        init: init
    };

    // Initialize when script loads
    init();

})();