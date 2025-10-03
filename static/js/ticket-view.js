/**
 * Ticket View JavaScript
 * Handles tag management, follower management, and other ticket interactions
 */

// Global variable to store ticket ID (set by template)
window.TICKET_ID = window.TICKET_ID || null;

// Utility function to escape HTML
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

function initializeTicketView(ticketId) {
    window.TICKET_ID = ticketId;
    setupKeyboardShortcuts();
    setupAutoSaveDrafts();
    initializeWysiwygEditor();
}

// Enhanced Follower Management
function addFollower() {
    // Get available agents that are not already followers
    const currentFollowers = Array.from(document.querySelectorAll('#followers-list [data-agent-id]')).map(el => el.dataset.agentId);

    fetch('/api/agents')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const availableAgents = data.agents.filter(agent =>
                    !currentFollowers.includes(String(agent.id))
                );

                if (availableAgents.length === 0) {
                    showToast('No available agents to add', 'info');
                    return;
                }

                // Create enhanced modal for agent selection
                const modalHtml = `
                    <div id="follower-modal" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50 p-4">
                        <div class="bg-white rounded-xl shadow-2xl max-w-md w-full max-h-[80vh] flex flex-col transform transition-all duration-200 ease-out scale-100 opacity-100">
                            <div class="p-6 border-b border-gray-200">
                                <div class="flex items-center justify-between">
                                    <h3 class="text-lg font-semibold text-gray-900">Add Follower</h3>
                                    <button onclick="closeFollowerModal()" class="text-gray-400 hover:text-gray-500 transition-colors">
                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                        </svg>
                                    </button>
                                </div>
                                <p class="text-sm text-gray-600 mt-1">Select an agent to follow this ticket</p>
                            </div>

                            <div class="p-4 border-b border-gray-200">
                                <div class="relative">
                                    <input type="text" id="follower-search" placeholder="Search agents..."
                                           class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <svg class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                                        </svg>
                                    </div>
                                </div>
                            </div>

                            <div class="flex-1 overflow-y-auto p-4">
                                <div id="follower-list" class="space-y-2">
                                    ${availableAgents.map(agent => `
                                        <div class="follower-option p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 cursor-pointer transition-all duration-150"
                                             data-agent-id="${agent.id}" data-search="${agent.full_name.toLowerCase()} ${agent.email.toLowerCase()}">
                                            <div class="flex items-center space-x-3">
                                                <div class="flex-shrink-0">
                                                    ${agent.avatar_url ?
                                                        `<img class="h-8 w-8 rounded-full" src="${agent.avatar_url}" alt="${agent.full_name}">` :
                                                        `<div class="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-sm font-medium">
                                                            ${agent.first_name ? agent.first_name[0] : ''}${agent.last_name ? agent.last_name[0] : ''}
                                                         </div>`
                                                    }
                                                </div>
                                                <div class="flex-1 min-w-0">
                                                    <p class="text-sm font-medium text-gray-900 truncate">${agent.full_name}</p>
                                                    <p class="text-sm text-gray-500 truncate">${agent.email}</p>
                                                    ${agent.role ? `<p class="text-xs text-gray-400 capitalize">${agent.role}</p>` : ''}
                                                </div>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>

                            <div class="p-6 border-t border-gray-200">
                                <div class="flex justify-end space-x-3">
                                    <button onclick="closeFollowerModal()" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 transition-colors">Cancel</button>
                                    <button id="add-follower-btn" disabled onclick="submitSelectedFollower()" class="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">Add Follower</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                document.body.insertAdjacentHTML('beforeend', modalHtml);

                // Setup follower modal interactions
                setupFollowerModal();
            }
        })
        .catch(error => {
            showToast('Failed to load agents', 'error');
            console.error('Error:', error);
        });
}

// Enhanced follower modal setup
function setupFollowerModal() {
    const searchInput = document.getElementById('follower-search');
    const followerOptions = document.querySelectorAll('.follower-option');
    const addButton = document.getElementById('add-follower-btn');
    let selectedAgentId = null;

    // Search functionality
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        followerOptions.forEach(option => {
            const searchText = option.dataset.search;
            if (searchText.includes(searchTerm)) {
                option.style.display = 'block';
            } else {
                option.style.display = 'none';
            }
        });
    });

    // Selection functionality
    followerOptions.forEach(option => {
        option.addEventListener('click', () => {
            // Clear previous selection
            followerOptions.forEach(opt => {
                opt.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-50', 'border-blue-500');
                opt.classList.add('border-gray-200');
            });

            // Select current option
            option.classList.add('ring-2', 'ring-blue-500', 'bg-blue-50', 'border-blue-500');
            option.classList.remove('border-gray-200');

            selectedAgentId = option.dataset.agentId;
            addButton.disabled = false;
        });
    });

    // Store selected agent ID globally
    window.selectedFollowerAgentId = null;
    window.setSelectedFollowerAgent = (agentId) => {
        window.selectedFollowerAgentId = agentId;
        addButton.disabled = false;
    };

    // Focus search input
    setTimeout(() => searchInput.focus(), 100);
}

function submitSelectedFollower() {
    const selectedOption = document.querySelector('.follower-option.ring-2');
    if (!selectedOption) {
        showToast('Please select an agent', 'error');
        return;
    }

    const agentId = selectedOption.dataset.agentId;
    const addButton = document.getElementById('add-follower-btn');

    addButton.disabled = true;
    addButton.textContent = 'Adding...';

    fetch(`/api/ticket/${window.TICKET_ID}/followers`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({agent_id: agentId})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            closeFollowerModal();
            refreshFollowersInline(data.agent);
        } else {
            showToast(data.message || 'Failed to add follower', 'error');
            addButton.disabled = false;
            addButton.textContent = 'Add Follower';
        }
    })
    .catch(error => {
        showToast('Failed to add follower', 'error');
        console.error('Error:', error);
        addButton.disabled = false;
        addButton.textContent = 'Add Follower';
    });
}

function closeFollowerModal() {
    const modal = document.getElementById('follower-modal');
    if (modal) {
        modal.classList.add('opacity-0', 'scale-95');
        setTimeout(() => modal.remove(), 150);
    }
}

// Inline refresh for followers (avoids full page reload)
function refreshFollowersInline(newAgent) {
    const followersList = document.getElementById('followers-list');
    const noFollowersMsg = followersList.querySelector('.text-center');

    if (noFollowersMsg) {
        noFollowersMsg.remove();
    }

    const followerHtml = `
        <div class="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg" data-agent-id="${newAgent.id}">
            <div class="flex items-center space-x-2">
                <div class="flex-shrink-0 h-5 w-5">
                    ${newAgent.avatar_url ?
                        `<img class="h-5 w-5 rounded-full" src="${newAgent.avatar_url}" alt="${newAgent.full_name}">` :
                        `<div class="h-5 w-5 rounded-full bg-gradient-to-br from-green-500 to-teal-600 flex items-center justify-center text-white text-xs font-medium">
                            ${newAgent.first_name ? newAgent.first_name[0] : ''}
                         </div>`
                    }
                </div>
                <span class="text-sm text-gray-700">${newAgent.full_name}</span>
            </div>
            <button hx-delete="/api/ticket/${window.TICKET_ID}/followers/${newAgent.id}"
                    hx-swap="none"
                    hx-on:htmx:after-request="refreshFollowers()"
                    class="text-gray-400 hover:text-red-500 transition-colors">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
    `;

    followersList.insertAdjacentHTML('beforeend', followerHtml);

    // Reinitialize HTMX for the new element
    if (typeof htmx !== 'undefined') {
        htmx.process(followersList.lastElementChild);
    }
}

// Enhanced Tag Management
function addTag() {
    // Get available tags that are not already applied
    const currentTags = Array.from(document.querySelectorAll('#tags-container [data-tag-id]')).map(el => el.dataset.tagId);

    fetch('/api/tags')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const availableTags = data.tags.filter(tag =>
                    !currentTags.includes(String(tag.id))
                );

                if (availableTags.length === 0) {
                    showToast('No available tags to add', 'info');
                    return;
                }

                // Create enhanced modal for tag selection
                const modalHtml = `
                    <div id="tag-modal" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50 p-4">
                        <div class="bg-white rounded-xl shadow-2xl max-w-md w-full max-h-[80vh] flex flex-col transform transition-all duration-200 ease-out scale-100 opacity-100">
                            <div class="p-6 border-b border-gray-200">
                                <div class="flex items-center justify-between">
                                    <h3 class="text-lg font-semibold text-gray-900">Add Tag</h3>
                                    <button onclick="closeTagModal()" class="text-gray-400 hover:text-gray-500 transition-colors">
                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                        </svg>
                                    </button>
                                </div>
                                <p class="text-sm text-gray-600 mt-1">Select tags to categorize this ticket</p>
                            </div>

                            <div class="p-4 border-b border-gray-200">
                                <div class="relative">
                                    <input type="text" id="tag-search" placeholder="Search tags..."
                                           class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <svg class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                                        </svg>
                                    </div>
                                </div>
                            </div>

                            <div class="flex-1 overflow-y-auto p-4">
                                <div id="tag-grid" class="grid grid-cols-1 gap-2">
                                    ${availableTags.map(tag => `
                                        <div class="tag-option p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 cursor-pointer transition-all duration-150"
                                             data-tag-id="${tag.id}" data-search="${tag.name.toLowerCase()}">
                                            <div class="flex items-center space-x-3">
                                                <div class="w-4 h-4 rounded-full border-2 border-gray-300 flex items-center justify-center transition-colors tag-checkbox">
                                                    <div class="w-2 h-2 rounded-full bg-blue-600 opacity-0 transition-opacity"></div>
                                                </div>
                                                <div class="flex-1 flex items-center justify-between">
                                                    <span class="text-sm font-medium text-gray-900">${tag.name}</span>
                                                    <div class="flex items-center space-x-2">
                                                        <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium"
                                                              style="background-color: ${tag.color}20; color: ${tag.color}; border: 1px solid ${tag.color}40;">
                                                            ${tag.name}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                            ${tag.description ? `<p class="text-xs text-gray-500 mt-1 ml-7">${tag.description}</p>` : ''}
                                        </div>
                                    `).join('')}
                                </div>
                            </div>

                            <div class="p-6 border-t border-gray-200">
                                <div class="flex items-center justify-between">
                                    <div class="text-sm text-gray-500">
                                        <span id="selected-count">0</span> tag(s) selected
                                    </div>
                                    <div class="flex space-x-3">
                                        <button onclick="closeTagModal()" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 transition-colors">Cancel</button>
                                        <button id="add-tags-btn" disabled onclick="submitSelectedTags()" class="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">Add Tags</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                document.body.insertAdjacentHTML('beforeend', modalHtml);

                // Setup tag modal interactions
                setupTagModal();
            }
        })
        .catch(error => {
            showToast('Failed to load tags', 'error');
            console.error('Error:', error);
        });
}

// Enhanced tag modal setup
function setupTagModal() {
    const searchInput = document.getElementById('tag-search');
    const tagOptions = document.querySelectorAll('.tag-option');
    const addButton = document.getElementById('add-tags-btn');
    const selectedCount = document.getElementById('selected-count');
    let selectedTags = new Set();

    // Search functionality
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        tagOptions.forEach(option => {
            const searchText = option.dataset.search;
            if (searchText.includes(searchTerm)) {
                option.style.display = 'block';
            } else {
                option.style.display = 'none';
            }
        });
    });

    // Selection functionality
    tagOptions.forEach(option => {
        option.addEventListener('click', () => {
            const tagId = option.dataset.tagId;
            const checkbox = option.querySelector('.tag-checkbox');
            const checkmark = checkbox.querySelector('div');

            if (selectedTags.has(tagId)) {
                // Deselect
                selectedTags.delete(tagId);
                option.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-50', 'border-blue-500');
                option.classList.add('border-gray-200');
                checkbox.classList.remove('border-blue-500', 'bg-blue-500');
                checkbox.classList.add('border-gray-300');
                checkmark.classList.add('opacity-0');
            } else {
                // Select
                selectedTags.add(tagId);
                option.classList.add('ring-2', 'ring-blue-500', 'bg-blue-50', 'border-blue-500');
                option.classList.remove('border-gray-200');
                checkbox.classList.add('border-blue-500', 'bg-blue-500');
                checkbox.classList.remove('border-gray-300');
                checkmark.classList.remove('opacity-0');
            }

            // Update button state
            selectedCount.textContent = selectedTags.size;
            addButton.disabled = selectedTags.size === 0;
            addButton.textContent = selectedTags.size === 1 ? 'Add Tag' : 'Add Tags';
        });
    });

    // Focus search input
    setTimeout(() => searchInput.focus(), 100);
}

function submitSelectedTags() {
    const selectedOptions = document.querySelectorAll('.tag-option.ring-2');
    if (selectedOptions.length === 0) {
        showToast('Please select at least one tag', 'error');
        return;
    }

    const tagIds = Array.from(selectedOptions).map(option => option.dataset.tagId);
    const addButton = document.getElementById('add-tags-btn');

    addButton.disabled = true;
    addButton.textContent = 'Adding...';

    // Add tags one by one (or modify API to accept multiple)
    const addTagPromises = tagIds.map(tagId =>
        fetch(`/api/ticket/${window.TICKET_ID}/tags`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tag_id: tagId})
        })
    );

    Promise.all(addTagPromises)
        .then(responses => Promise.all(responses.map(r => r.json())))
        .then(results => {
            const successful = results.filter(r => r.success);
            const failed = results.filter(r => !r.success);

            if (successful.length > 0) {
                showToast(`${successful.length} tag(s) added successfully`, 'success');
                closeTagModal();
                // Refresh tags inline
                setTimeout(() => location.reload(), 500); // For now, reload to show updates
            }

            if (failed.length > 0) {
                showToast(`Failed to add ${failed.length} tag(s)`, 'error');
            }
        })
        .catch(error => {
            showToast('Failed to add tags', 'error');
            console.error('Error:', error);
            addButton.disabled = false;
            addButton.textContent = tagIds.length === 1 ? 'Add Tag' : 'Add Tags';
        });
}

function closeTagModal() {
    const modal = document.getElementById('tag-modal');
    if (modal) {
        modal.classList.add('opacity-0', 'scale-95');
        setTimeout(() => modal.remove(), 150);
    }
}

// Refresh functions (for HTMX compatibility)
function refreshFollowers() {
    // Refresh followers list
    if (typeof htmx !== 'undefined') {
        htmx.trigger('#followers-list', 'refresh');
    } else {
        location.reload();
    }
}

function refreshTags() {
    // Refresh tags container
    if (typeof htmx !== 'undefined') {
        htmx.trigger('#tags-container', 'refresh');
    } else {
        location.reload();
    }
}

function refreshTicketStatus() {
    // Refresh the entire properties panel
    location.reload();
}

// Reply handling
function handleReplySubmit() {
    // Clear the form and refresh replies
    const replyContent = document.getElementById('reply-content');
    if (replyContent) {
        replyContent.value = '';
    }

    showToast('Reply sent successfully', 'success');

    // Refresh timeline and replies section
    setTimeout(() => {
        // Trigger timeline refresh
        document.body.dispatchEvent(new CustomEvent('refreshTimeline'));
        // Refresh the entire page for now (can be optimized later)
        location.reload();
    }, 1000);
}

// Keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(event) {
        // Ctrl/Cmd + Enter to send reply
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            const replyForm = document.getElementById('reply-form');
            if (replyForm) {
                replyForm.dispatchEvent(new Event('submit'));
            }
        }

        // Escape to close modals
        if (event.key === 'Escape') {
            closeFollowerModal();
            closeTagModal();
        }
    });
}

// Auto-save drafts (future enhancement)
function setupAutoSaveDrafts() {
    let draftTimer;
    const replyContent = document.getElementById('reply-content');

    if (replyContent) {
        replyContent.addEventListener('input', function() {
            clearTimeout(draftTimer);
            draftTimer = setTimeout(() => {
                // Auto-save draft logic here
                console.log('Draft saved');
            }, 2000);
        });
    }
}

// Minimalist WYSIWYG Editor
function initializeWysiwygEditor() {
    const replyContent = document.getElementById('reply-content');
    const container = document.getElementById('reply-editor-container');
    if (!replyContent || !container) return;

    // Check if editor already exists to avoid double initialization
    if (container.querySelector('.wysiwyg-editor')) {
        return;
    }

    // Create editor container
    const editorContainer = document.createElement('div');
    editorContainer.className = 'wysiwyg-editor border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500';

    // Create toolbar
    const toolbar = document.createElement('div');
    toolbar.className = 'flex items-center space-x-1 p-2 border-b border-gray-200 bg-gray-50 rounded-t-lg';
    toolbar.innerHTML = `
        <button type="button" class="wysiwyg-btn" data-command="bold" title="Bold (Ctrl+B)">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 4h8a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"></path>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 12h9a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"></path>
            </svg>
        </button>
        <button type="button" class="wysiwyg-btn" data-command="italic" title="Italic (Ctrl+I)">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 4h-9m4 16H5m4-8h6"></path>
            </svg>
        </button>
        <button type="button" class="wysiwyg-btn" data-command="underline" title="Underline (Ctrl+U)">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l7-7 3 3-7 7-3-3z"></path>
            </svg>
        </button>
        <div class="w-px h-4 bg-gray-300 mx-1"></div>
        <button type="button" class="wysiwyg-btn" data-command="insertUnorderedList" title="Bullet List">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
            </svg>
        </button>
        <button type="button" class="wysiwyg-btn" data-command="insertOrderedList" title="Numbered List">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>
            </svg>
        </button>
        <div class="w-px h-4 bg-gray-300 mx-1"></div>
        <button type="button" class="wysiwyg-btn" data-command="createLink" title="Insert Link">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path>
            </svg>
        </button>
        <div class="w-px h-4 bg-gray-300 mx-1"></div>
        <button type="button" class="wysiwyg-btn" data-action="source" title="View Source">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
            </svg>
        </button>
    `;

    // Create editable content area
    const editorContent = document.createElement('div');
    editorContent.className = 'p-3 min-h-[150px] outline-none resize-none overflow-auto max-h-[300px]';
    editorContent.contentEditable = true;
    editorContent.innerHTML = replyContent.value || '<p>Write your reply...</p>';
    editorContent.setAttribute('data-placeholder', 'Write your reply...');

    // Replace textarea with editor
    editorContainer.appendChild(toolbar);
    editorContainer.appendChild(editorContent);

    // Clear the container and add the new editor
    container.innerHTML = '';
    container.appendChild(editorContainer);

    // Create hidden textarea for form submission
    const hiddenTextarea = document.createElement('textarea');
    hiddenTextarea.name = 'content';
    hiddenTextarea.id = 'reply-content';
    hiddenTextarea.required = true;
    hiddenTextarea.style.display = 'none';
    hiddenTextarea.value = replyContent.value || '';
    container.appendChild(hiddenTextarea);

    // Store reference to hidden textarea
    editorContent._hiddenTextarea = hiddenTextarea;

    setupWysiwygToolbar(toolbar, editorContent);
    setupWysiwygContent(editorContent);

    // Add CSS for editor
    if (!document.getElementById('wysiwyg-styles')) {
        const styles = document.createElement('style');
        styles.id = 'wysiwyg-styles';
        styles.textContent = `
            .wysiwyg-btn {
                padding: 6px 8px;
                border: 1px solid transparent;
                border-radius: 4px;
                color: #6B7280;
                background: transparent;
                transition: all 0.15s;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .wysiwyg-btn:hover {
                background-color: #E5E7EB;
                color: #374151;
            }
            .wysiwyg-btn.active {
                background-color: #DBEAFE;
                color: #1D4ED8;
                border-color: #93C5FD;
            }
            .wysiwyg-editor [contenteditable]:empty:not(:focus)::before {
                content: attr(data-placeholder);
                color: #9CA3AF;
                pointer-events: none;
            }
            .wysiwyg-editor [contenteditable] {
                outline: none;
            }
            .wysiwyg-editor [contenteditable] p {
                margin: 0;
                padding: 4px 0;
            }
            .wysiwyg-editor [contenteditable] ul, .wysiwyg-editor [contenteditable] ol {
                margin: 8px 0;
                padding-left: 20px;
            }
            .wysiwyg-editor [contenteditable] li {
                margin: 4px 0;
            }
            .wysiwyg-editor [contenteditable] strong {
                font-weight: 600;
            }
            .wysiwyg-editor [contenteditable] a {
                color: #2563EB;
                text-decoration: underline;
            }
            .wysiwyg-source {
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                font-size: 13px;
                line-height: 1.4;
                background: #F9FAFB;
            }
        `;
        document.head.appendChild(styles);
    }
}

function setupWysiwygToolbar(toolbar, editorContent) {
    const buttons = toolbar.querySelectorAll('.wysiwyg-btn');

    buttons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const command = button.dataset.command;
            const action = button.dataset.action;

            if (action === 'source') {
                toggleSourceMode(editorContent, button);
            } else if (command === 'createLink') {
                insertLink(editorContent);
            } else if (command) {
                document.execCommand(command, false, null);
                editorContent.focus();
            }

            updateToolbarState(toolbar, editorContent);
            syncWithTextarea(editorContent);
        });
    });

    // Update toolbar state on selection change
    editorContent.addEventListener('mouseup', () => updateToolbarState(toolbar, editorContent));
    editorContent.addEventListener('keyup', () => updateToolbarState(toolbar, editorContent));
}

function setupWysiwygContent(editorContent) {
    // Handle keyboard shortcuts
    editorContent.addEventListener('keydown', (e) => {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'b':
                    e.preventDefault();
                    document.execCommand('bold');
                    break;
                case 'i':
                    e.preventDefault();
                    document.execCommand('italic');
                    break;
                case 'u':
                    e.preventDefault();
                    document.execCommand('underline');
                    break;
            }
        }

        // Handle Enter key for better paragraph handling
        if (e.key === 'Enter' && !e.shiftKey) {
            if (document.queryCommandState('insertOrderedList') || document.queryCommandState('insertUnorderedList')) {
                // Let default list behavior handle this
                return;
            }

            e.preventDefault();
            document.execCommand('insertHTML', false, '<p><br></p>');
        }
    });

    // Sync content with hidden textarea
    editorContent.addEventListener('input', () => {
        syncWithTextarea(editorContent);
    });

    // Handle paste events
    editorContent.addEventListener('paste', (e) => {
        e.preventDefault();
        const text = (e.clipboardData || window.clipboardData).getData('text/plain');
        document.execCommand('insertText', false, text);
    });
}

function updateToolbarState(toolbar, editorContent) {
    const buttons = toolbar.querySelectorAll('.wysiwyg-btn[data-command]');

    buttons.forEach(button => {
        const command = button.dataset.command;
        if (command && document.queryCommandState(command)) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });
}

function syncWithTextarea(editorContent) {
    const textarea = editorContent._hiddenTextarea;
    if (textarea) {
        // Convert HTML to a cleaner format for backend
        let content = editorContent.innerHTML;

        // Simple HTML to text conversion for now
        // In production, you might want more sophisticated HTML processing
        content = content
            .replace(/<p><br><\/p>/g, '\n')
            .replace(/<p>/g, '')
            .replace(/<\/p>/g, '\n')
            .replace(/<br>/g, '\n')
            .replace(/<strong>(.*?)<\/strong>/g, '**$1**')
            .replace(/<em>(.*?)<\/em>/g, '*$1*')
            .replace(/<u>(.*?)<\/u>/g, '_$1_')
            .replace(/<li>/g, '• ')
            .replace(/<\/li>/g, '\n')
            .replace(/<\/?[uo]l>/g, '')
            .replace(/<a href="(.*?)">(.*?)<\/a>/g, '[$2]($1)');

        textarea.value = content.trim();
    }
}

function toggleSourceMode(editorContent, button) {
    const isSource = editorContent.classList.contains('wysiwyg-source');

    if (isSource) {
        // Switch back to WYSIWYG mode
        const htmlContent = editorContent.textContent;
        editorContent.innerHTML = htmlContent;
        editorContent.classList.remove('wysiwyg-source');
        editorContent.contentEditable = true;
        button.classList.remove('active');
    } else {
        // Switch to source mode
        const htmlContent = editorContent.innerHTML;
        editorContent.textContent = htmlContent;
        editorContent.classList.add('wysiwyg-source');
        editorContent.contentEditable = true;
        button.classList.add('active');
    }

    editorContent.focus();
}

function insertLink(editorContent) {
    const selection = window.getSelection();
    const selectedText = selection.toString();
    const url = prompt('Enter URL:', 'https://');

    if (url && url !== 'https://') {
        if (selectedText) {
            document.execCommand('createLink', false, url);
        } else {
            document.execCommand('insertHTML', false, `<a href="${url}">${url}</a>`);
        }
        editorContent.focus();
    }
}

function closeWysiwygModal() {
    // Placeholder for any WYSIWYG-related modals
}

// Utility functions
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.remove();
    }
}

// Enhanced modal creation with better UX
function createModal(id, title, content, actions) {
    const modalHtml = `
        <div id="${id}" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50 modal-enter">
            <div class="bg-white rounded-lg px-6 py-4 max-w-md w-full shadow-xl">
                <h3 class="text-lg font-medium text-gray-900 mb-4">${title}</h3>
                ${content}
                <div class="mt-4 flex justify-end space-x-3">
                    ${actions}
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

// ========================================
// Ticket Relationships Functions
// ========================================

function toggleRelationshipMenu() {
    const menu = document.getElementById('relationship-menu');
    menu.classList.toggle('hidden');
}

// Close relationship menu when clicking outside
document.addEventListener('click', function(event) {
    const container = document.getElementById('relationships-section');
    const menu = document.getElementById('relationship-menu');

    if (container && menu && !container.contains(event.target)) {
        menu.classList.add('hidden');
    }
});

function openMergeModal() {
    toggleRelationshipMenu();

    const modalHtml = `
        <div id="merge-modal" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
            <div class="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-semibold text-gray-900">Merge Ticket</h3>
                    <button onclick="closeMergeModal()" class="text-gray-400 hover:text-gray-600">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <p class="text-sm text-gray-600 mb-4">Merge this ticket into another ticket. All replies, tags, and followers will be transferred.</p>

                <form onsubmit="submitMerge(event)">
                    <div class="mb-4 relative">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Search Target Ticket</label>
                        <input type="text" id="merge-target-search"
                               oninput="searchTicketsForMerge(this.value)"
                               placeholder="Type ticket number or subject..."
                               autocomplete="off"
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500">
                        <input type="hidden" id="merge-target-ticket-id" required>
                        <div id="merge-search-results" class="hidden absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto"></div>
                        <p class="text-xs text-gray-500 mt-1">Search by ticket number or subject</p>
                        <div id="merge-selected-ticket" class="hidden mt-2 p-2 bg-blue-50 border border-blue-200 rounded text-sm"></div>
                    </div>

                    <div class="mb-4 space-y-2">
                        <label class="flex items-center">
                            <input type="checkbox" id="merge-replies" checked class="rounded text-blue-600">
                            <span class="ml-2 text-sm text-gray-700">Merge replies</span>
                        </label>
                        <label class="flex items-center">
                            <input type="checkbox" id="merge-tags" checked class="rounded text-blue-600">
                            <span class="ml-2 text-sm text-gray-700">Merge tags</span>
                        </label>
                        <label class="flex items-center">
                            <input type="checkbox" id="close-source" checked class="rounded text-blue-600">
                            <span class="ml-2 text-sm text-gray-700">Close this ticket after merge</span>
                        </label>
                    </div>

                    <div class="flex justify-end space-x-3">
                        <button type="button" onclick="closeMergeModal()"
                                class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">
                            Cancel
                        </button>
                        <button type="submit" id="merge-submit-btn"
                                class="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                disabled>
                            Merge Tickets
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

let mergeSearchTimeout;
async function searchTicketsForMerge(query) {
    clearTimeout(mergeSearchTimeout);

    const resultsDiv = document.getElementById('merge-search-results');
    const submitBtn = document.getElementById('merge-submit-btn');

    if (query.length < 2) {
        resultsDiv.classList.add('hidden');
        submitBtn.disabled = true;
        return;
    }

    mergeSearchTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`/api/tickets/search?search=${encodeURIComponent(query)}&per_page=10`);
            const data = await response.json();

            if (data.tickets && data.tickets.length > 0) {
                // Filter out current ticket
                const filteredTickets = data.tickets.filter(t => t.id !== window.TICKET_ID);

                if (filteredTickets.length === 0) {
                    resultsDiv.innerHTML = '<div class="p-3 text-sm text-gray-500">No other tickets found</div>';
                    resultsDiv.classList.remove('hidden');
                    return;
                }

                resultsDiv.innerHTML = filteredTickets.map(ticket => `
                    <button type="button" onclick="selectMergeTicket(${ticket.id}, '${ticket.ticket_number}', '${escapeHtml(ticket.subject)}')"
                            class="w-full text-left px-3 py-2 hover:bg-gray-100 border-b border-gray-100 last:border-b-0">
                        <div class="font-mono text-sm text-blue-600">#${ticket.ticket_number}</div>
                        <div class="text-sm text-gray-900 truncate">${escapeHtml(ticket.subject)}</div>
                        <div class="text-xs text-gray-500">${ticket.status} • Priority: ${ticket.priority}</div>
                    </button>
                `).join('');
                resultsDiv.classList.remove('hidden');
            } else {
                resultsDiv.innerHTML = '<div class="p-3 text-sm text-gray-500">No tickets found</div>';
                resultsDiv.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Error searching tickets:', error);
        }
    }, 300);
}

function selectMergeTicket(id, number, subject) {
    document.getElementById('merge-target-ticket-id').value = id;
    document.getElementById('merge-target-search').value = `#${number}`;
    document.getElementById('merge-search-results').classList.add('hidden');
    document.getElementById('merge-submit-btn').disabled = false;

    const selectedDiv = document.getElementById('merge-selected-ticket');
    selectedDiv.innerHTML = `
        <div class="flex items-center justify-between">
            <div>
                <div class="font-mono text-sm text-blue-600">#${number}</div>
                <div class="text-sm text-gray-900">${subject}</div>
            </div>
            <button type="button" onclick="clearMergeSelection()" class="text-red-600 hover:text-red-800">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
    `;
    selectedDiv.classList.remove('hidden');
}

function clearMergeSelection() {
    document.getElementById('merge-target-ticket-id').value = '';
    document.getElementById('merge-target-search').value = '';
    document.getElementById('merge-selected-ticket').classList.add('hidden');
    document.getElementById('merge-submit-btn').disabled = true;
}

function closeMergeModal() {
    const modal = document.getElementById('merge-modal');
    if (modal) modal.remove();
}

async function submitMerge(event) {
    event.preventDefault();

    const targetTicketId = document.getElementById('merge-target-ticket-id').value;

    if (!targetTicketId) {
        showToast('Please select a target ticket', 'error');
        return;
    }

    try {
        // Perform merge
        const response = await fetch(`/api/ticket/${window.TICKET_ID}/merge`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                target_ticket_id: parseInt(targetTicketId),
                merge_replies: document.getElementById('merge-replies').checked,
                merge_tags: document.getElementById('merge-tags').checked,
                close_source: document.getElementById('close-source').checked,
                agent_id: null
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('Tickets merged successfully', 'success');
            closeMergeModal();

            // Redirect to target ticket
            setTimeout(() => {
                window.location.href = `/ticket/${targetTicketId}`;
            }, 1500);
        } else {
            showToast(data.message || 'Failed to merge tickets', 'error');
        }
    } catch (error) {
        console.error('Error merging tickets:', error);
        showToast('Error merging tickets', 'error');
    }
}

function openSplitModal() {
    toggleRelationshipMenu();

    const modalHtml = `
        <div id="split-modal" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
            <div class="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-semibold text-gray-900">Split Ticket</h3>
                    <button onclick="closeSplitModal()" class="text-gray-400 hover:text-gray-600">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <p class="text-sm text-gray-600 mb-4">Split this ticket into multiple child tickets.</p>

                <form onsubmit="submitSplit(event)">
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Number of Tickets</label>
                        <input type="number" id="split-count" min="2" max="10" value="2"
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                               required>
                        <p class="text-xs text-gray-500 mt-1">Split into 2-10 tickets</p>
                    </div>

                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Reason (optional)</label>
                        <input type="text" id="split-criteria"
                               placeholder="e.g., By department, By priority..."
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500">
                    </div>

                    <div class="flex justify-end space-x-3">
                        <button type="button" onclick="closeSplitModal()"
                                class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">
                            Cancel
                        </button>
                        <button type="submit"
                                class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">
                            Split Ticket
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

function closeSplitModal() {
    const modal = document.getElementById('split-modal');
    if (modal) modal.remove();
}

async function submitSplit(event) {
    event.preventDefault();

    const numTickets = parseInt(document.getElementById('split-count').value);
    const criteria = document.getElementById('split-criteria').value;

    try {
        const response = await fetch(`/api/ticket/${window.TICKET_ID}/split`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                num_tickets: numTickets,
                split_criteria: criteria || null,
                agent_id: null
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast(`Ticket split into ${numTickets} tickets`, 'success');
            closeSplitModal();

            // Refresh relationships
            document.body.dispatchEvent(new CustomEvent('refreshRelationships'));

            // Optionally show created tickets
            const ticketList = data.child_tickets.map(t => `#${t.ticket_number}`).join(', ');
            setTimeout(() => {
                showToast(`Created: ${ticketList}`, 'info');
            }, 1000);
        } else {
            showToast(data.message || 'Failed to split ticket', 'error');
        }
    } catch (error) {
        console.error('Error splitting ticket:', error);
        showToast('Error splitting ticket', 'error');
    }
}

function openLinkModal() {
    toggleRelationshipMenu();

    const modalHtml = `
        <div id="link-modal" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
            <div class="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-semibold text-gray-900">Link Ticket</h3>
                    <button onclick="closeLinkModal()" class="text-gray-400 hover:text-gray-600">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <p class="text-sm text-gray-600 mb-4">Link this ticket to another ticket.</p>

                <form onsubmit="submitLink(event)">
                    <div class="mb-4 relative">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Search Target Ticket</label>
                        <input type="text" id="link-target-search"
                               oninput="searchTicketsForLink(this.value)"
                               placeholder="Type ticket number or subject..."
                               autocomplete="off"
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500">
                        <input type="hidden" id="link-target-ticket-id" required>
                        <div id="link-search-results" class="hidden absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto"></div>
                        <p class="text-xs text-gray-500 mt-1">Search by ticket number or subject</p>
                        <div id="link-selected-ticket" class="hidden mt-2 p-2 bg-green-50 border border-green-200 rounded text-sm"></div>
                    </div>

                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">Relationship Type</label>
                        <select id="link-type" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500">
                            <option value="linked_to">Linked To</option>
                            <option value="related_to">Related To</option>
                            <option value="duplicate_of">Duplicate Of</option>
                        </select>
                    </div>

                    <div class="flex justify-end space-x-3">
                        <button type="button" onclick="closeLinkModal()"
                                class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">
                            Cancel
                        </button>
                        <button type="submit" id="link-submit-btn"
                                class="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                disabled>
                            Link Tickets
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

let linkSearchTimeout;
async function searchTicketsForLink(query) {
    clearTimeout(linkSearchTimeout);

    const resultsDiv = document.getElementById('link-search-results');
    const submitBtn = document.getElementById('link-submit-btn');

    if (query.length < 2) {
        resultsDiv.classList.add('hidden');
        submitBtn.disabled = true;
        return;
    }

    linkSearchTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`/api/tickets/search?search=${encodeURIComponent(query)}&per_page=10`);
            const data = await response.json();

            if (data.tickets && data.tickets.length > 0) {
                // Filter out current ticket
                const filteredTickets = data.tickets.filter(t => t.id !== window.TICKET_ID);

                if (filteredTickets.length === 0) {
                    resultsDiv.innerHTML = '<div class="p-3 text-sm text-gray-500">No other tickets found</div>';
                    resultsDiv.classList.remove('hidden');
                    return;
                }

                resultsDiv.innerHTML = filteredTickets.map(ticket => `
                    <button type="button" onclick="selectLinkTicket(${ticket.id}, '${ticket.ticket_number}', '${escapeHtml(ticket.subject)}')"
                            class="w-full text-left px-3 py-2 hover:bg-gray-100 border-b border-gray-100 last:border-b-0">
                        <div class="font-mono text-sm text-blue-600">#${ticket.ticket_number}</div>
                        <div class="text-sm text-gray-900 truncate">${escapeHtml(ticket.subject)}</div>
                        <div class="text-xs text-gray-500">${ticket.status} • Priority: ${ticket.priority}</div>
                    </button>
                `).join('');
                resultsDiv.classList.remove('hidden');
            } else {
                resultsDiv.innerHTML = '<div class="p-3 text-sm text-gray-500">No tickets found</div>';
                resultsDiv.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Error searching tickets:', error);
        }
    }, 300);
}

function selectLinkTicket(id, number, subject) {
    document.getElementById('link-target-ticket-id').value = id;
    document.getElementById('link-target-search').value = `#${number}`;
    document.getElementById('link-search-results').classList.add('hidden');
    document.getElementById('link-submit-btn').disabled = false;

    const selectedDiv = document.getElementById('link-selected-ticket');
    selectedDiv.innerHTML = `
        <div class="flex items-center justify-between">
            <div>
                <div class="font-mono text-sm text-green-600">#${number}</div>
                <div class="text-sm text-gray-900">${subject}</div>
            </div>
            <button type="button" onclick="clearLinkSelection()" class="text-red-600 hover:text-red-800">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
    `;
    selectedDiv.classList.remove('hidden');
}

function clearLinkSelection() {
    document.getElementById('link-target-ticket-id').value = '';
    document.getElementById('link-target-search').value = '';
    document.getElementById('link-selected-ticket').classList.add('hidden');
    document.getElementById('link-submit-btn').disabled = true;
}

function closeLinkModal() {
    const modal = document.getElementById('link-modal');
    if (modal) modal.remove();
}

async function submitLink(event) {
    event.preventDefault();

    const targetTicketId = document.getElementById('link-target-ticket-id').value;
    const relationType = document.getElementById('link-type').value;

    if (!targetTicketId) {
        showToast('Please select a target ticket', 'error');
        return;
    }

    try {
        // Create link
        const response = await fetch(`/api/ticket/${window.TICKET_ID}/link`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                target_ticket_id: parseInt(targetTicketId),
                relationship_type: relationType,
                agent_id: null
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('Tickets linked successfully', 'success');
            closeLinkModal();

            // Refresh relationships
            document.body.dispatchEvent(new CustomEvent('refreshRelationships'));
        } else {
            showToast(data.message || 'Failed to link tickets', 'error');
        }
    } catch (error) {
        console.error('Error linking tickets:', error);
        showToast('Error linking tickets', 'error');
    }
}

async function unlinkTicket(relationshipId, currentTicketId) {
    if (!confirm('Are you sure you want to unlink these tickets?')) {
        return;
    }

    try {
        const response = await fetch(`/api/ticket/${currentTicketId}/unlink/${relationshipId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast('Tickets unlinked successfully', 'success');

            // Refresh relationships
            document.body.dispatchEvent(new CustomEvent('refreshRelationships'));
        } else {
            showToast(data.message || 'Failed to unlink tickets', 'error');
        }
    } catch (error) {
        console.error('Error unlinking tickets:', error);
        showToast('Error unlinking tickets', 'error');
    }
}