// Shared settings page functionality
let currentEntityData = {};
let deleteItemId = null;
let entityConfigs = {};

// Common utility functions
function showLoading(entityType) {
    const loading = document.getElementById(`${entityType}-loading`);
    const empty = document.getElementById(`${entityType}-empty`);
    const tableBody = document.getElementById(`${entityType}-table-body`);

    if (loading) loading.classList.remove('hidden');
    if (empty) empty.classList.add('hidden');
    if (tableBody) tableBody.innerHTML = '';
}

function hideLoading(entityType) {
    const loading = document.getElementById(`${entityType}-loading`);
    if (loading) loading.classList.add('hidden');
}

function showEmpty(entityType) {
    const empty = document.getElementById(`${entityType}-empty`);
    if (empty) empty.classList.remove('hidden');
}

function hideEmpty(entityType) {
    const empty = document.getElementById(`${entityType}-empty`);
    if (empty) empty.classList.add('hidden');
}

// Modal management functions
function openCreateModal(entityType) {
    const modal = document.getElementById(`${entityType}-modal`);
    const modalTitle = document.getElementById(`${entityType}-modal-title`);
    const form = document.getElementById(`${entityType}-form`);
    const idField = document.getElementById(`${entityType}-id`);

    if (modalTitle) modalTitle.textContent = `Add ${entityConfigs[entityType]?.entitySingular || entityType}`;
    if (form) form.reset();
    if (idField) idField.value = '';

    generateFormFields(entityType, null);

    if (modal) modal.classList.remove('hidden');
}

function openEditModal(entityType, itemId) {
    const modal = document.getElementById(`${entityType}-modal`);
    const modalTitle = document.getElementById(`${entityType}-modal-title`);
    const idField = document.getElementById(`${entityType}-id`);

    // Find the item data
    const itemData = currentEntityData[entityType]?.find(item => item.id == itemId);

    if (!itemData) {
        showToast('Item not found', 'error');
        return;
    }

    if (modalTitle) modalTitle.textContent = `Edit ${entityConfigs[entityType]?.entitySingular || entityType}`;
    if (idField) idField.value = itemId;

    generateFormFields(entityType, itemData);

    if (modal) modal.classList.remove('hidden');
}

function closeModal(entityType) {
    const modal = document.getElementById(`${entityType}-modal`);
    if (modal) modal.classList.add('hidden');
}

function confirmDelete(entityType, itemId) {
    deleteItemId = itemId;
    const modal = document.getElementById(`${entityType}-delete-modal`);
    if (modal) modal.classList.remove('hidden');
}

function closeDeleteModal(entityType) {
    deleteItemId = null;
    const modal = document.getElementById(`${entityType}-delete-modal`);
    if (modal) modal.classList.add('hidden');
}

function executeDelete(entityType) {
    if (!deleteItemId) return;

    const config = entityConfigs[entityType];
    if (!config) return;

    fetch(`${config.apiEndpoint}/${deleteItemId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message || `${config.entitySingular} deleted successfully`, 'success');
            closeDeleteModal(entityType);
            // Reload the data
            if (window[`load${entityType.charAt(0).toUpperCase() + entityType.slice(1)}`]) {
                window[`load${entityType.charAt(0).toUpperCase() + entityType.slice(1)}`]();
            }
        } else {
            showToast(`Error deleting ${config.entitySingular.toLowerCase()}: ` + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error deleting item:', error);
        showToast(`Error deleting ${config.entitySingular.toLowerCase()}`, 'error');
    });
}

// Form field generation
function generateFormFields(entityType, itemData) {
    const config = entityConfigs[entityType];
    if (!config || !config.formFields) return;

    const fieldsContainer = document.getElementById(`${entityType}-form-fields`);
    if (!fieldsContainer) return;

    fieldsContainer.innerHTML = '';

    config.formFields.forEach(field => {
        const fieldElement = createFormField(field, itemData);
        fieldsContainer.appendChild(fieldElement);
    });
}

function createFormField(fieldConfig, itemData) {
    const fieldDiv = document.createElement('div');

    switch (fieldConfig.type) {
        case 'text':
        case 'email':
            fieldDiv.innerHTML = `
                <label for="${fieldConfig.name}" class="block text-sm font-medium text-gray-700 mb-1">
                    ${fieldConfig.label} ${fieldConfig.required ? '<span class="text-red-500">*</span>' : ''}
                </label>
                <input
                    type="${fieldConfig.type}"
                    id="${fieldConfig.name}"
                    name="${fieldConfig.name}"
                    ${fieldConfig.required ? 'required' : ''}
                    value="${itemData ? (itemData[fieldConfig.name] || '') : ''}"
                    placeholder="${fieldConfig.placeholder || ''}"
                    class="w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
                ${fieldConfig.help ? `<p class="mt-1 text-xs text-gray-500">${fieldConfig.help}</p>` : ''}
            `;
            break;

        case 'textarea':
            fieldDiv.innerHTML = `
                <label for="${fieldConfig.name}" class="block text-sm font-medium text-gray-700 mb-1">
                    ${fieldConfig.label} ${fieldConfig.required ? '<span class="text-red-500">*</span>' : ''}
                </label>
                <textarea
                    id="${fieldConfig.name}"
                    name="${fieldConfig.name}"
                    ${fieldConfig.required ? 'required' : ''}
                    rows="${fieldConfig.rows || 3}"
                    placeholder="${fieldConfig.placeholder || ''}"
                    class="w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">${itemData ? (itemData[fieldConfig.name] || '') : ''}</textarea>
                ${fieldConfig.help ? `<p class="mt-1 text-xs text-gray-500">${fieldConfig.help}</p>` : ''}
            `;
            break;

        case 'select':
            const options = fieldConfig.options.map(option =>
                `<option value="${option.value}" ${itemData && itemData[fieldConfig.name] === option.value ? 'selected' : ''}>${option.label}</option>`
            ).join('');

            fieldDiv.innerHTML = `
                <label for="${fieldConfig.name}" class="block text-sm font-medium text-gray-700 mb-1">
                    ${fieldConfig.label} ${fieldConfig.required ? '<span class="text-red-500">*</span>' : ''}
                </label>
                <select
                    id="${fieldConfig.name}"
                    name="${fieldConfig.name}"
                    ${fieldConfig.required ? 'required' : ''}
                    class="w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
                    ${!fieldConfig.required ? '<option value="">Select an option</option>' : ''}
                    ${options}
                </select>
                ${fieldConfig.help ? `<p class="mt-1 text-xs text-gray-500">${fieldConfig.help}</p>` : ''}
            `;
            break;

        case 'number':
            fieldDiv.innerHTML = `
                <label for="${fieldConfig.name}" class="block text-sm font-medium text-gray-700 mb-1">
                    ${fieldConfig.label} ${fieldConfig.required ? '<span class="text-red-500">*</span>' : ''}
                </label>
                <input
                    type="number"
                    id="${fieldConfig.name}"
                    name="${fieldConfig.name}"
                    ${fieldConfig.required ? 'required' : ''}
                    ${fieldConfig.min !== undefined ? `min="${fieldConfig.min}"` : ''}
                    ${fieldConfig.max !== undefined ? `max="${fieldConfig.max}"` : ''}
                    ${fieldConfig.step !== undefined ? `step="${fieldConfig.step}"` : ''}
                    value="${itemData ? (itemData[fieldConfig.name] || '') : ''}"
                    placeholder="${fieldConfig.placeholder || ''}"
                    class="w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
                ${fieldConfig.help ? `<p class="mt-1 text-xs text-gray-500">${fieldConfig.help}</p>` : ''}
            `;
            break;

        case 'color':
            fieldDiv.innerHTML = `
                <label for="${fieldConfig.name}" class="block text-sm font-medium text-gray-700 mb-1">
                    ${fieldConfig.label} ${fieldConfig.required ? '<span class="text-red-500">*</span>' : ''}
                </label>
                <div class="flex items-center space-x-2">
                    <input
                        type="color"
                        id="${fieldConfig.name}-color"
                        value="${itemData ? (itemData[fieldConfig.name] || '#000000') : '#000000'}"
                        class="h-10 w-16 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        onchange="document.getElementById('${fieldConfig.name}').value = this.value">
                    <input
                        type="text"
                        id="${fieldConfig.name}"
                        name="${fieldConfig.name}"
                        ${fieldConfig.required ? 'required' : ''}
                        value="${itemData ? (itemData[fieldConfig.name] || '') : ''}"
                        placeholder="#000000"
                        class="flex-1 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        onchange="document.getElementById('${fieldConfig.name}-color').value = this.value">
                </div>
                ${fieldConfig.help ? `<p class="mt-1 text-xs text-gray-500">${fieldConfig.help}</p>` : ''}
            `;
            break;

        case 'checkbox':
            fieldDiv.innerHTML = `
                <div class="flex items-center">
                    <input
                        type="checkbox"
                        id="${fieldConfig.name}"
                        name="${fieldConfig.name}"
                        ${itemData && itemData[fieldConfig.name] ? 'checked' : ''}
                        class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded">
                    <label for="${fieldConfig.name}" class="ml-2 block text-sm text-gray-900">
                        ${fieldConfig.label}
                    </label>
                </div>
                ${fieldConfig.help ? `<p class="mt-1 text-xs text-gray-500">${fieldConfig.help}</p>` : ''}
            `;
            break;
    }

    return fieldDiv;
}

// Form submission handlers
function setupFormHandlers(entityType, config) {
    entityConfigs[entityType] = config;

    const form = document.getElementById(`${entityType}-form`);
    if (!form) return;

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        submitForm(entityType, e.target);
    });
}

function submitForm(entityType, form) {
    const config = entityConfigs[entityType];
    if (!config) return;

    const formData = new FormData(form);
    const jsonData = {};

    // Convert form data to JSON
    for (let [key, value] of formData.entries()) {
        jsonData[key] = value;
    }

    // Handle checkboxes (they won't be in FormData if unchecked)
    config.formFields.forEach(field => {
        if (field.type === 'checkbox' && !formData.has(field.name)) {
            jsonData[field.name] = false;
        } else if (field.type === 'checkbox' && formData.has(field.name)) {
            jsonData[field.name] = true;
        }
    });

    const itemId = document.getElementById(`${entityType}-id`).value;
    const isEdit = itemId && itemId !== '';

    const url = isEdit ? `${config.apiEndpoint}/${itemId}` : config.apiEndpoint;
    const method = isEdit ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(jsonData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message || `${config.entitySingular} ${isEdit ? 'updated' : 'created'} successfully`, 'success');
            closeModal(entityType);
            // Reload the data
            if (window[`load${entityType.charAt(0).toUpperCase() + entityType.slice(1)}`]) {
                window[`load${entityType.charAt(0).toUpperCase() + entityType.slice(1)}`]();
            }
        } else {
            showToast(`Error ${isEdit ? 'updating' : 'creating'} ${config.entitySingular.toLowerCase()}: ` + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error submitting form:', error);
        showToast(`Error ${isEdit ? 'updating' : 'creating'} ${config.entitySingular.toLowerCase()}`, 'error');
    });
}