// Toast notification system
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');

    // Minimalist color scheme - subtle backgrounds with contrasting text
    let bgColor, textColor, borderColor;
    if (type === 'success') {
        bgColor = 'bg-green-50';
        textColor = 'text-green-800';
        borderColor = 'border-l-green-400';
    } else if (type === 'error') {
        bgColor = 'bg-red-50';
        textColor = 'text-red-800';
        borderColor = 'border-l-red-400';
    } else {
        bgColor = 'bg-blue-50';
        textColor = 'text-blue-800';
        borderColor = 'border-l-blue-400';
    }

    toast.className = `${bgColor} ${textColor} border-l-4 ${borderColor} px-4 py-3 rounded-r-md shadow-sm transform transition-all duration-500 ease-out translate-y-2 opacity-0 backdrop-blur-sm`;
    toast.innerHTML = `
        <div class="flex items-center justify-between">
            <span class="text-sm font-medium">${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-3 ${textColor} hover:opacity-70 transition-opacity duration-200">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
    `;

    container.appendChild(toast);

    // Animate in with subtle slide up
    setTimeout(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    }, 100);

    // Auto-remove after 4 seconds (shorter for less intrusion)
    setTimeout(() => {
        toast.classList.add('translate-y-2', 'opacity-0', 'scale-95');
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 500);
    }, 4000);
}

// HTMX Event Handlers
document.body.addEventListener('htmx:responseError', function(event) {
    showToast('An error occurred. Please try again.', 'error');
});

document.body.addEventListener('htmx:beforeRequest', function(event) {
    const target = event.target;
    if (target.classList.contains('htmx-indicator-toggle')) {
        target.classList.add('htmx-request');
    }
});

document.body.addEventListener('htmx:afterRequest', function(event) {
    const target = event.target;
    if (target.classList.contains('htmx-indicator-toggle')) {
        target.classList.remove('htmx-request');
    }
});

// Auto-refresh functionality
setInterval(function() {
    if (document.getElementById('ticket-list')) {
        htmx.trigger('#ticket-list', 'refresh');
    }
}, 120000);