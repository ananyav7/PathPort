/**
 * PathBot - AI Logistics Assistant Floating Widget
 * Provides real-time parcel tracking by Order ID, commuter earnings calculations,
 * and logistics FAQs with interactive prompt chips.
 */

document.addEventListener('DOMContentLoaded', function () {
    const launcher = document.getElementById('pathbot-launcher');
    const chatWindow = document.getElementById('pathbot-window');
    const closeBtn = document.getElementById('pathbot-close');
    const clearBtn = document.getElementById('pathbot-clear');
    const inputField = document.getElementById('pathbot-input');
    const sendBtn = document.getElementById('pathbot-send');
    const messagesContainer = document.getElementById('pathbot-messages');
    const chipsContainer = document.getElementById('pathbot-chips');
    const tooltip = document.getElementById('pathbot-tooltip');

    if (!launcher || !chatWindow) return;

    let hasGreeted = false;

    // Default Quick Chips
    const defaultChips = [
        'Track PP202611153010',
        'How do commuters earn?',
        'Calculate CO2 savings',
        'Safety & OTPs',
        'View Demo Orders'
    ];

    function toggleChat() {
        const isHidden = chatWindow.style.display === 'none' || !chatWindow.style.display;
        if (isHidden) {
            chatWindow.style.display = 'flex';
            if (tooltip) tooltip.style.display = 'none';
            if (!hasGreeted) {
                initGreeting();
                hasGreeted = true;
            }
            setTimeout(() => inputField && inputField.focus(), 150);
        } else {
            chatWindow.style.display = 'none';
        }
    }

    function initGreeting() {
        appendMessage('bot', "👋 Hi! I'm **PathBot**, your AI Logistics Assistant. Ask me to track an order (e.g. `PP202611153010`), explain how commuters earn, or calculate crowdsourced CO₂ savings!");
        renderChips(defaultChips);
    }

    function renderChips(chips) {
        if (!chipsContainer) return;
        chipsContainer.innerHTML = '';
        chips.forEach(chipText => {
            const btn = document.createElement('button');
            btn.className = 'pathbot-chip';
            btn.type = 'button';
            btn.textContent = chipText;
            btn.onclick = () => {
                if (inputField) inputField.value = chipText;
                handleSend();
            };
            chipsContainer.appendChild(btn);
        });
    }

    function appendMessage(sender, text, orderData = null) {
        if (!messagesContainer) return;

        const msgDiv = document.createElement('div');
        msgDiv.className = `pathbot-msg pathbot-msg-${sender}`;

        const bubble = document.createElement('div');
        bubble.className = 'bubble';

        // Parse basic markdown: bold **text**, `code`
        let formattedText = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/`(.*?)`/g, '<code style="background:#e2e8f0; padding:2px 5px; border-radius:4px; font-size:0.8rem; color:#0f172a;">$1</code>')
            .replace(/\n/g, '<br>');

        bubble.innerHTML = formattedText;

        // If parcel order data is provided, append a mini track card
        if (orderData && orderData.order_id) {
            const card = document.createElement('div');
            card.className = 'pathbot-card';

            const statusColors = {
                'pending': '#f59e0b',
                'assigned': '#3b82f6',
                'picked_up': '#8b5cf6',
                'delivered': '#10b981'
            };
            const color = statusColors[orderData.status] || '#10b981';

            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <strong style="color:#0f172a;">#${orderData.order_id}</strong>
                    <span style="background:${color}22; color:${color}; font-size:0.75rem; font-weight:700; padding:2px 8px; border-radius:12px;">
                        ${(orderData.status || '').toUpperCase()}
                    </span>
                </div>
                <div style="color:#475569; font-size:0.8rem; margin-bottom:8px;">
                    ${orderData.title || 'Parcel'}<br>
                    <small style="color:#64748b;">📍 ${orderData.route || ''}</small>
                </div>
                <a href="${orderData.track_url}" class="btn btn-primary" style="font-size:0.75rem; padding:0.35rem 0.75rem; display:inline-block; text-decoration:none; text-align:center; width:100%; border-radius:6px;">
                    <i class="fas fa-map-marked-alt"></i> Open Full Route Tracker
                </a>
            `;
            bubble.appendChild(card);
        }

        msgDiv.appendChild(bubble);
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function showTypingIndicator() {
        const id = 'pathbot-typing-indicator';
        if (document.getElementById(id)) return;

        const typingDiv = document.createElement('div');
        typingDiv.id = id;
        typingDiv.className = 'pathbot-msg pathbot-msg-bot';
        typingDiv.innerHTML = `
            <div class="bubble" style="display:inline-flex; align-items:center; gap:5px; padding:0.6rem 0.9rem; color:#64748b;">
                <span class="fas fa-circle-notch fa-spin" style="color:var(--primary-green);"></span>
                <small>PathBot is thinking...</small>
            </div>
        `;
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function removeTypingIndicator() {
        const el = document.getElementById('pathbot-typing-indicator');
        if (el) el.remove();
    }

    async function handleSend() {
        if (!inputField) return;
        const text = inputField.value.trim();
        if (!text) return;

        appendMessage('user', text);
        inputField.value = '';
        showTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: text })
            });

            removeTypingIndicator();

            if (!response.ok) {
                appendMessage('bot', "⚠️ Sorry, I could not process that request right now. Please try again.");
                return;
            }

            const data = await response.json();
            if (data.reply) {
                appendMessage('bot', data.reply, data.order || null);
            }
            if (data.suggestions && data.suggestions.length > 0) {
                renderChips(data.suggestions);
            }
        } catch (err) {
            removeTypingIndicator();
            appendMessage('bot', "⚠️ Connection error. Please check your connection or try again.");
            console.error('PathBot Error:', err);
        }
    }

    // Event Listeners
    launcher.addEventListener('click', toggleChat);
    if (closeBtn) closeBtn.addEventListener('click', toggleChat);

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            if (messagesContainer) messagesContainer.innerHTML = '';
            initGreeting();
        });
    }

    if (sendBtn) sendBtn.addEventListener('click', handleSend);
    if (inputField) {
        inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleSend();
            }
        });
    }
});
