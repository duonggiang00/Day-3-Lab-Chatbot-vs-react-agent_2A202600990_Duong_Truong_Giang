// State Management
let currentMode = 'agent';

// UI Elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const chatForm = document.getElementById('chat-form');
const sendButton = document.getElementById('send-button');
const modeDescription = document.getElementById('mode-description');
const chatTitle = document.getElementById('chat-title');
const badgeProvider = document.getElementById('badge-provider');

// Telemetry Elements
const metricLatency = document.getElementById('metric-latency');
const metricTokens = document.getElementById('metric-tokens');
const promptTokens = document.getElementById('prompt-tokens');
const completionTokens = document.getElementById('completion-tokens');
const metricCost = document.getElementById('metric-cost');

// On Page Load
document.addEventListener('DOMContentLoaded', () => {
    fetchSystemStatus();
});

// Fetch provider and model configuration from server
async function fetchSystemStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        if (data.provider && data.model) {
            const labels = { mimo: 'MiMo', google: 'Gemini', openai: 'OpenAI', local: 'Local' };
            const providerStr = labels[data.provider] || data.provider.toUpperCase();
            badgeProvider.textContent = `${providerStr} (${data.model})`;
        } else {
            badgeProvider.textContent = 'Lỗi cấu hình LLM';
            badgeProvider.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
            badgeProvider.style.color = '#ef4444';
            badgeProvider.style.borderColor = 'rgba(239, 68, 68, 0.2)';
        }
    } catch (err) {
        console.error('Failed to fetch status:', err);
        badgeProvider.textContent = 'Ngoại tuyến';
    }
}

// Toggle between Chatbot and Agent modes
function setMode(mode) {
    if (mode === currentMode) return;
    
    currentMode = mode;
    
    // Toggle active buttons
    document.getElementById('mode-chatbot').classList.toggle('active', mode === 'chatbot');
    document.getElementById('mode-agent').classList.toggle('active', mode === 'agent');
    
    // Update texts
    if (mode === 'chatbot') {
        chatTitle.textContent = 'G-BOT Chatbot';
        modeDescription.textContent = 'Chatbot cơ bản — trả lời nhanh nhưng không tra cứu giá thực tế từ GearVN. Nên dùng ReAct Agent để tư vấn chính xác.';
    } else {
        chatTitle.textContent = 'G-BOT Tư Vấn PC';
        modeDescription.textContent = 'ReAct Agent — tra cấu hình Steam, tìm sản phẩm và PC có sẵn trên GearVN, kèm link mua hàng.';
    }
    
    // Append system message to chat feed about mode change
    const systemMsg = document.createElement('div');
    systemMsg.className = 'message assistant';
    systemMsg.style.opacity = '0.7';
    systemMsg.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-circle-info"></i></div>
        <div class="message-content" style="background-color: rgba(59, 130, 246, 0.05); border-color: rgba(59, 130, 246, 0.1);">
            <p>Đã chuyển sang chế độ <strong>${mode === 'chatbot' ? 'Chatbot' : 'ReAct Agent'}</strong>.</p>
        </div>
    `;
    chatMessages.appendChild(systemMsg);
    scrollToBottom();
}

// Fill input and send suggestion query
function useSuggestion(text) {
    userInput.value = text;
    chatForm.dispatchEvent(new Event('submit'));
}

// Auto scroll chat feed to bottom
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Handle sending message
async function sendMessage(event) {
    event.preventDefault();
    
    const messageText = userInput.value.trim();
    if (!messageText) return;
    
    // Append User message bubble
    const userMsg = document.createElement('div');
    userMsg.className = 'message user';
    userMsg.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-user"></i></div>
        <div class="message-content">
            <p>${escapeHtml(messageText)}</p>
        </div>
    `;
    chatMessages.appendChild(userMsg);
    
    // Reset inputs
    userInput.value = '';
    scrollToBottom();
    
    // Show typing loader
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'message assistant typing';
    typingIndicator.id = 'typing-indicator';
    typingIndicator.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="message-content">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(typingIndicator);
    scrollToBottom();
    
    // Disable inputs during network request
    userInput.disabled = true;
    sendButton.disabled = true;
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText, mode: currentMode })
        });
        
        const data = await response.json();
        
        // Remove loading indicator
        const loader = document.getElementById('typing-indicator');
        if (loader) loader.remove();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Không thể kết nối hoặc xử lý câu trả lời.');
        }
        
        // Append Assistant answer bubble
        const assistantMsg = document.createElement('div');
        assistantMsg.className = 'message assistant';
        
        // Build message HTML
        let messageHtml = `
            <div class="avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-content">
                <p>${formatMessageContent(data.answer)}</p>
        `;
        
        // If ReAct steps are present, format them
        if (currentMode === 'agent' && data.steps && data.steps.length > 0) {
            messageHtml += `
                <div class="reasoning-details-container">
                    <details class="reasoning-details">
                        <summary class="reasoning-summary">
                            <i class="fa-solid fa-code-fork"></i> Xem nhật ký suy luận (${data.steps.length} bước)
                        </summary>
                        <div class="reasoning-steps">
                            ${data.steps.map(step => renderStep(step)).join('')}
                        </div>
                    </details>
                </div>
            `;
        }
        
        messageHtml += `</div>`;
        assistantMsg.innerHTML = messageHtml;
        chatMessages.appendChild(assistantMsg);
        
        // Update Telemetry Panel
        updateTelemetry(data.metrics);
        
    } catch (err) {
        console.error(err);
        const loader = document.getElementById('typing-indicator');
        if (loader) loader.remove();
        
        const errorMsg = document.createElement('div');
        errorMsg.className = 'message assistant';
        errorMsg.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-circle-exclamation text-rose"></i></div>
            <div class="message-content" style="background-color: rgba(244, 63, 94, 0.05); border-color: rgba(244, 63, 94, 0.1); color: #f43f5e;">
                <p><strong>Lỗi:</strong> ${escapeHtml(err.message)}</p>
            </div>
        `;
        chatMessages.appendChild(errorMsg);
    } finally {
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
        scrollToBottom();
    }
}

// Render individual ReAct step
function renderStep(step) {
    let html = `
        <div class="step-card">
            <div class="step-num">Bước ${step.step}</div>
    `;
    
    if (step.thought) {
        html += `<div class="step-thought">Thought: ${escapeHtml(step.thought)}</div>`;
    }
    
    if (step.action) {
        html += `
            <div class="step-action-box">
                <i class="fa-solid fa-terminal"></i> Action: ${escapeHtml(step.action)}(${escapeHtml(step.args || '')})
            </div>
        `;
    }
    
    if (step.observation) {
        html += `
            <div class="step-observation-box">Observation: ${escapeHtml(step.observation)}</div>
        `;
    }
    
    if (step.final_answer) {
        html += `
            <div class="step-thought" style="color: var(--success); font-weight: 500;">
                Final Answer Found: ${escapeHtml(step.final_answer)}
            </div>
        `;
    }
    
    html += `</div>`;
    return html;
}

// Update the telemetry sidebar cards
function updateTelemetry(metrics) {
    if (!metrics) return;
    
    metricLatency.innerHTML = `${metrics.latency_ms} <span class="unit">ms</span>`;
    metricTokens.textContent = metrics.total_tokens.toLocaleString();
    promptTokens.textContent = metrics.prompt_tokens.toLocaleString();
    completionTokens.textContent = metrics.completion_tokens.toLocaleString();
    metricCost.textContent = `$${metrics.cost.toFixed(5)}`;
}

function stripTrailingUrlPunctuation(url) {
    let cleaned = url;
    const trailing = new Set(['.', ',', ';', ':', '!', '?', ')', ']', '}', '"', "'"]);
    while (cleaned.length && trailing.has(cleaned[cleaned.length - 1])) {
        cleaned = cleaned.slice(0, -1);
    }
    return cleaned;
}

function linkifyBareUrls(html) {
    const parts = html.split(/(<a\b[^>]*>[\s\S]*?<\/a>)/gi);
    return parts.map((part) => {
        if (/^<a\b/i.test(part)) return part;
        return part.replace(
            /(https?:\/\/[a-zA-Z0-9\-._~:/?#@!$&'()*+,;=%]+)/g,
            (url) => linkifyUrl(url)
        );
    }).join('');
}

function linkifyUrl(url) {
    const href = stripTrailingUrlPunctuation(url);
    if (!href) return url;
    return `<a href="${href}" target="_blank" rel="noopener" class="msg-link">${href}</a>`;
}

// Format message: escape HTML, linkify markdown + bare URLs, preserve line breaks
function formatMessageContent(text) {
    if (!text) return '';
    const escaped = escapeHtml(text);
    const withBreaks = escaped.replace(/\n/g, '<br>');

    const withMarkdownLinks = withBreaks.replace(
        /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
        (_, label, url) => `<a href="${stripTrailingUrlPunctuation(url)}" target="_blank" rel="noopener" class="msg-link">${label}</a>`
    );

    return linkifyBareUrls(withMarkdownLinks);
}

// Helper to escape HTML and prevent XSS injections
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}
