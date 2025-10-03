// Handle ticket click to open modal
function openTicketModal(ticketId) {
    const modal = document.getElementById('ticket-modal');
    const modalContent = document.getElementById('ticket-modal-content');

    modal.classList.remove('hidden');

    // Load ticket content
    htmx.ajax('GET', `/ticket/${ticketId}`, {
        target: '#ticket-modal-content',
        swap: 'innerHTML'
    });
}

// Close modal
function closeTicketModal() {
    document.getElementById('ticket-modal').classList.add('hidden');
}

// Handle ticket status updates
function updateTicketStatus(ticketId, status) {
    htmx.ajax('POST', `/api/ticket/${ticketId}/mark-${status}`, {
        swap: 'none'
    }).then(function() {
        // Refresh ticket list
        htmx.trigger('#ticket-list', 'refresh');
        showToast(`Ticket marked as ${status}`, 'success');
    });
}

// Handle archive ticket
function archiveTicket(ticketId) {
    htmx.ajax('POST', `/api/ticket/${ticketId}/archive`, {
        swap: 'none'
    }).then(function() {
        // Refresh ticket list
        htmx.trigger('#ticket-list', 'refresh');
        showToast('Ticket archived', 'success');
        closeTicketModal();
    });
}

// Initialize inbox page
document.addEventListener('DOMContentLoaded', function() {
    // Close modal on escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeTicketModal();
        }
    });

    // Close modal when clicking outside
    const ticketModal = document.getElementById('ticket-modal');
    if (ticketModal) {
        ticketModal.addEventListener('click', function(event) {
            if (event.target === this) {
                closeTicketModal();
            }
        });
    }
});