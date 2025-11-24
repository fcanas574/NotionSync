// NotionSync Web Interface JavaScript

// Add any shared JavaScript functionality here
console.log('NotionSync Web Interface loaded');

// Utility function for making API calls
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(endpoint, options);
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Add smooth scrolling to all anchor links
document.addEventListener('DOMContentLoaded', () => {
    // Highlight active navigation link
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.style.fontWeight = 'bold';
            link.style.borderBottom = '2px solid var(--primary-color)';
        }
    });
});
