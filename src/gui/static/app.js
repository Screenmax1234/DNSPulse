/**
 * DNS Speed Checker - Frontend Application
 * Handles WebSocket communication, UI updates, and Chart.js visualizations
 */

// State
let ws = null;
let latencyChart = null;
let selectedResolvers = new Set();
let customResolvers = [];
let lastResults = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadResolvers();
    initWebSocket();
});

// WebSocket Connection
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(initWebSocket, 2000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

// Handle WebSocket Messages
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'started':
            showProgress();
            break;

        case 'progress':
            updateProgress(data);
            break;

        case 'complete':
            hideProgress();
            showResults(data);
            break;

        case 'error':
            hideProgress();
            showToast(data.message, 'error');
            enableStartButton();
            break;

        case 'pong':
            // Keepalive response
            break;
    }
}

// Load Resolvers from API
async function loadResolvers() {
    try {
        const response = await fetch('/api/resolvers');
        const data = await response.json();

        const container = document.getElementById('resolver-list');
        container.innerHTML = '';

        data.resolvers.forEach(resolver => {
            const isDefault = data.defaults.includes(resolver.id);
            if (isDefault) {
                selectedResolvers.add(resolver.id);
            }

            const div = document.createElement('div');
            div.className = `resolver-item ${isDefault ? 'selected' : ''}`;
            div.onclick = () => toggleResolver(resolver.id, div);

            div.innerHTML = `
                <input type="checkbox" ${isDefault ? 'checked' : ''} 
                       onclick="event.stopPropagation(); toggleResolver('${resolver.id}', this.parentElement)">
                <div class="resolver-info">
                    <div class="resolver-name">${resolver.name}</div>
                    <div class="resolver-ip">${resolver.ip}</div>
                </div>
                <div class="resolver-badges">
                    ${resolver.dot ? '<span class="badge active">DoT</span>' : ''}
                    ${resolver.doh ? '<span class="badge active">DoH</span>' : ''}
                </div>
            `;

            container.appendChild(div);
        });
    } catch (error) {
        console.error('Failed to load resolvers:', error);
        showToast('Failed to load resolvers', 'error');
    }
}

// Toggle Resolver Selection
function toggleResolver(id, element) {
    const checkbox = element.querySelector('input[type="checkbox"]');

    if (selectedResolvers.has(id)) {
        selectedResolvers.delete(id);
        element.classList.remove('selected');
        checkbox.checked = false;
    } else {
        selectedResolvers.add(id);
        element.classList.add('selected');
        checkbox.checked = true;
    }
}

// Add Custom Resolver
function addCustomResolver() {
    const input = document.getElementById('custom-ip');
    const ip = input.value.trim();

    if (!ip) return;

    // Basic IP validation
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipRegex.test(ip)) {
        showToast('Invalid IP address format', 'error');
        return;
    }

    if (customResolvers.includes(ip)) {
        showToast('Resolver already added', 'error');
        return;
    }

    customResolvers.push(ip);

    // Add to list
    const container = document.getElementById('resolver-list');
    const div = document.createElement('div');
    div.className = 'resolver-item selected';
    div.innerHTML = `
        <input type="checkbox" checked>
        <div class="resolver-info">
            <div class="resolver-name">Custom</div>
            <div class="resolver-ip">${ip}</div>
        </div>
        <button class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;" 
                onclick="removeCustomResolver('${ip}', this.parentElement)">✕</button>
    `;
    container.appendChild(div);

    input.value = '';
    showToast(`Added custom resolver: ${ip}`, 'success');
}

// Remove Custom Resolver
function removeCustomResolver(ip, element) {
    customResolvers = customResolvers.filter(r => r !== ip);
    element.remove();
}

// Start Benchmark
function startBenchmark() {
    if (selectedResolvers.size === 0 && customResolvers.length === 0) {
        showToast('Please select at least one resolver', 'error');
        return;
    }

    if (!ws || ws.readyState !== WebSocket.OPEN) {
        showToast('Not connected to server', 'error');
        return;
    }

    // Get configuration
    const transport = document.querySelector('input[name="transport"]:checked').value;
    const mode = document.getElementById('test-mode').value;
    const domains = parseInt(document.getElementById('domains').value) || 30;
    const runs = parseInt(document.getElementById('runs').value) || 2;
    const parallel = parseInt(document.getElementById('parallel').value) || 10;

    // Disable start button
    disableStartButton();

    // Send benchmark request
    ws.send(JSON.stringify({
        action: 'start_benchmark',
        resolvers: Array.from(selectedResolvers),
        custom_resolvers: customResolvers,
        transport: transport,
        mode: mode,
        domains: domains,
        runs: runs,
        parallel: parallel,
    }));
}

// UI Updates
function showProgress() {
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('results-section').style.display = 'none';
    updateProgress({ percent: 0, message: 'Starting benchmark...' });
}

function updateProgress(data) {
    document.getElementById('progress-fill').style.width = `${data.percent}%`;
    document.getElementById('progress-percent').textContent = `${data.percent}%`;
    document.getElementById('progress-message').textContent = data.message;
}

function hideProgress() {
    document.getElementById('progress-section').style.display = 'none';
}

function showResults(data) {
    lastResults = data;

    document.getElementById('results-section').style.display = 'grid';

    // Update winner card
    if (data.winner) {
        document.getElementById('winner-name').textContent = data.winner.name;
        document.getElementById('winner-avg').textContent = `${data.winner.avg}ms`;
        document.getElementById('winner-success').textContent = `${data.winner.success_rate}%`;
    } else {
        document.getElementById('winner-name').textContent = 'No winner';
        document.getElementById('winner-avg').textContent = '-';
        document.getElementById('winner-success').textContent = '-';
    }

    // Update chart
    updateChart(data.resolvers);

    // Update table
    updateTable(data.resolvers);

    enableStartButton();
}

function updateChart(resolvers) {
    const ctx = document.getElementById('latency-chart').getContext('2d');

    // Destroy existing chart
    if (latencyChart) {
        latencyChart.destroy();
    }

    // Colors for resolvers
    const colors = [
        'rgba(99, 102, 241, 0.8)',
        'rgba(139, 92, 246, 0.8)',
        'rgba(16, 185, 129, 0.8)',
        'rgba(245, 158, 11, 0.8)',
        'rgba(239, 68, 68, 0.8)',
        'rgba(14, 165, 233, 0.8)',
    ];

    const backgroundColors = resolvers.map((_, i) => colors[i % colors.length]);

    latencyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: resolvers.map(r => r.name),
            datasets: [
                {
                    label: 'Average',
                    data: resolvers.map(r => r.avg),
                    backgroundColor: backgroundColors,
                    borderRadius: 8,
                },
                {
                    label: 'p95',
                    data: resolvers.map(r => r.p95),
                    backgroundColor: backgroundColors.map(c => c.replace('0.8', '0.4')),
                    borderRadius: 8,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#a0a0b0',
                    },
                },
                tooltip: {
                    callbacks: {
                        label: (context) => `${context.dataset.label}: ${context.raw}ms`,
                    },
                },
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                    },
                    ticks: {
                        color: '#a0a0b0',
                    },
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                    },
                    ticks: {
                        color: '#a0a0b0',
                        callback: (value) => `${value}ms`,
                    },
                },
            },
        },
    });
}

function updateTable(resolvers) {
    const tbody = document.getElementById('stats-body');
    tbody.innerHTML = '';

    resolvers.forEach(r => {
        const successClass = r.success_rate >= 99 ? 'success-high' :
            r.success_rate >= 95 ? 'success-medium' : 'success-low';

        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="resolver-cell">${r.name}</td>
            <td>${r.total}</td>
            <td class="${successClass}">${r.success_rate}%</td>
            <td>${r.avg}ms</td>
            <td>${r.p95}ms</td>
            <td>${r.p99}ms</td>
            <td>${r.jitter}ms</td>
        `;
        tbody.appendChild(row);
    });
}

// Button State
function disableStartButton() {
    const btn = document.getElementById('start-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Running...';
}

function enableStartButton() {
    const btn = document.getElementById('start-btn');
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">🚀</span> Start Benchmark';
}

// Export Functions
async function exportJSON() {
    if (!lastResults) {
        showToast('No results to export', 'error');
        return;
    }

    const blob = new Blob([JSON.stringify(lastResults, null, 2)], { type: 'application/json' });
    downloadBlob(blob, 'dns-benchmark-results.json');
    showToast('JSON exported', 'success');
}

function copyResults() {
    if (!lastResults) {
        showToast('No results to copy', 'error');
        return;
    }

    const text = formatResultsAsText(lastResults);
    navigator.clipboard.writeText(text).then(() => {
        showToast('Results copied to clipboard', 'success');
    }).catch(() => {
        showToast('Failed to copy results', 'error');
    });
}

function formatResultsAsText(data) {
    let text = '=== DNS Speed Checker Results ===\n\n';

    if (data.winner) {
        text += `🏆 Winner: ${data.winner.name} (${data.winner.avg}ms avg)\n\n`;
    }

    text += 'Resolver Results:\n';
    text += '-'.repeat(50) + '\n';

    data.resolvers.forEach(r => {
        text += `${r.name} (${r.ip})\n`;
        text += `  Avg: ${r.avg}ms | p95: ${r.p95}ms | p99: ${r.p99}ms\n`;
        text += `  Success: ${r.success_rate}% | Queries: ${r.total}\n\n`;
    });

    return text;
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Toast Notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Keepalive
setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'ping' }));
    }
}, 30000);
