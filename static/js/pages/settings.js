// Handle connection test response
function handleConnectionTest(event) {
    const xhr = event.detail.xhr;
    const response = JSON.parse(xhr.responseText);

    const statusElement = document.getElementById('connection-status');

    if (response.success) {
        statusElement.textContent = 'Connected ✓';
        statusElement.className = 'text-sm text-green-600';
        showToast('Connection successful!', 'success');
    } else {
        statusElement.textContent = 'Failed ✗';
        statusElement.className = 'text-sm text-red-600';
        showToast('Connection failed: ' + response.message, 'error');
    }
}

// Load settings from database
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();

        if (data.success) {
            // Load email settings
            const emailSettings = data.settings.email || {};
            document.getElementById('imap_server').value = emailSettings.IMAP_SERVER || '';
            document.getElementById('imap_port').value = emailSettings.IMAP_PORT || '';
            document.getElementById('imap_username').value = emailSettings.IMAP_USERNAME || '';
            document.getElementById('imap_password').value = emailSettings.IMAP_PASSWORD || '';
            document.getElementById('imap_use_ssl').checked = (emailSettings.IMAP_USE_SSL || 'true') === 'true';
            document.getElementById('imap_folder').value = emailSettings.IMAP_FOLDER || 'INBOX';

            // Load sync settings
            const syncSettings = data.settings.sync || {};
            document.getElementById('fetch_interval').value = Math.floor((syncSettings.FETCH_INTERVAL || 300) / 60);
            document.getElementById('max_emails_per_sync').value = syncSettings.MAX_EMAILS_PER_SYNC || '';
            document.getElementById('auto_sync_enabled').checked = (syncSettings.SCHEDULER_ENABLED || 'true') === 'true';

            // Load file settings
            const fileSettings = data.settings.files || {};
            document.getElementById('max_attachment_size').value = Math.floor((fileSettings.ATTACHMENT_MAX_SIZE || 10485760) / 1048576);
            document.getElementById('attachment_storage_path').value = fileSettings.ATTACHMENT_STORAGE_PATH || '';
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
        showToast('Failed to load settings', 'error');
    }
}

// Save settings to database
async function saveSettings(category, formData) {
    try {
        const response = await fetch(`/api/settings/${category}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            return true;
        } else {
            showToast('Failed to save: ' + data.message, 'error');
            return false;
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
        showToast('Failed to save settings', 'error');
        return false;
    }
}

// Initialize settings page
document.addEventListener('DOMContentLoaded', function() {
    // Load settings on page load
    loadSettings();

    // Form submissions
    document.getElementById('email-config-form').addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = {
            IMAP_SERVER: document.getElementById('imap_server').value,
            IMAP_PORT: document.getElementById('imap_port').value,
            IMAP_USERNAME: document.getElementById('imap_username').value,
            IMAP_PASSWORD: document.getElementById('imap_password').value,
            IMAP_USE_SSL: document.getElementById('imap_use_ssl').checked.toString(),
            IMAP_FOLDER: document.getElementById('imap_folder').value
        };

        await saveSettings('email', formData);
    });

    document.getElementById('sync-settings-form').addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = {
            FETCH_INTERVAL: (parseInt(document.getElementById('fetch_interval').value) * 60).toString(),
            MAX_EMAILS_PER_SYNC: document.getElementById('max_emails_per_sync').value,
            SCHEDULER_ENABLED: document.getElementById('auto_sync_enabled').checked.toString()
        };

        await saveSettings('sync', formData);
    });

    document.getElementById('file-settings-form').addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = {
            ATTACHMENT_MAX_SIZE: (parseInt(document.getElementById('max_attachment_size').value) * 1048576).toString()
        };

        await saveSettings('files', formData);
    });
});