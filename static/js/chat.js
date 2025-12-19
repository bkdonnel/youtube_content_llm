class ChatApp {
    constructor() {
        this.conversationHistory = [];
        this.apiUrl = window.location.origin;

        // DOM elements
        this.chatMessages = document.getElementById('chat-messages');
        this.chatInput = document.getElementById('chat-input');
        this.sendButton = document.getElementById('send-button');
        this.sourcesList = document.getElementById('sources-list');
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');

        this.init();
    }

    init() {
        // Event listeners
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });

        // Example queries
        document.querySelectorAll('.example-query').forEach(button => {
            button.addEventListener('click', () => {
                this.chatInput.value = button.textContent;
                this.sendMessage();
            });
        });

        // Check health
        this.checkHealth();
        setInterval(() => this.checkHealth(), 30000); // Check every 30 seconds

        // Welcome message
        this.addMessage('system', 'Welcome! Ask me anything about music production techniques from top YouTube creators.');
    }

    async checkHealth() {
        try {
            const response = await fetch(`${this.apiUrl}/api/health`);
            const data = await response.json();

            if (data.milvus_connected) {
                this.setStatus('online', 'Connected');
            } else {
                this.setStatus('offline', 'Milvus not connected');
            }
        } catch (error) {
            this.setStatus('offline', 'API unavailable');
        }
    }

    setStatus(status, text) {
        this.statusIndicator.className = `status-indicator ${status}`;
        this.statusText.textContent = text;
    }

    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message) return;

        // Clear input
        this.chatInput.value = '';

        // Add user message
        this.addMessage('user', message);

        // Show typing indicator
        const typingId = this.addTypingIndicator();

        try {
            // Send to API
            const response = await fetch(`${this.apiUrl}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    conversation_history: this.conversationHistory
                })
            });

            if (!response.ok) {
                throw new Error('API request failed');
            }

            const data = await response.json();

            // Remove typing indicator
            this.removeTypingIndicator(typingId);

            // Add assistant response
            this.addMessage('assistant', data.response);

            // Update conversation history
            this.conversationHistory.push(
                { role: 'user', content: message },
                { role: 'assistant', content: data.response }
            );

            // Keep only last 20 messages
            if (this.conversationHistory.length > 20) {
                this.conversationHistory = this.conversationHistory.slice(-20);
            }

            // Display sources
            this.displaySources(data.sources);

        } catch (error) {
            console.error('Error:', error);
            this.removeTypingIndicator(typingId);
            this.addMessage('system', 'Sorry, I encountered an error. Please try again.');
        }
    }

    addMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = content;
        this.chatMessages.appendChild(messageDiv);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    addTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant typing-indicator';
        typingDiv.innerHTML = '<span></span><span></span><span></span>';
        const id = Date.now();
        typingDiv.id = `typing-${id}`;
        this.chatMessages.appendChild(typingDiv);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        return id;
    }

    removeTypingIndicator(id) {
        const element = document.getElementById(`typing-${id}`);
        if (element) {
            element.remove();
        }
    }

    displaySources(sources) {
        if (!sources || sources.length === 0) {
            this.sourcesList.innerHTML = '<p class="empty-state">No sources found</p>';
            return;
        }

        this.sourcesList.innerHTML = '';

        sources.forEach((source, idx) => {
            const metadata = source.metadata || {};
            const youtubeId = metadata.youtube_id || '';
            const startTime = Math.floor(metadata.start_time || 0);
            const timestamp = metadata.timestamp || '';

            const sourceDiv = document.createElement('div');
            sourceDiv.className = 'source-item';

            const youtubeUrl = youtubeId ? `https://youtube.com/watch?v=${youtubeId}&t=${startTime}s` : '#';

            sourceDiv.innerHTML = `
                <div class="source-header">
                    <span class="source-channel">${source.channel_name || 'Unknown'}</span>
                    <span class="source-score">${(source.score * 100).toFixed(1)}%</span>
                </div>
                <div class="source-title">${metadata.video_title || 'Unknown Video'}</div>
                <div class="source-text">${source.text || ''}</div>
                ${youtubeId ? `<a href="${youtubeUrl}" target="_blank" class="source-link">
                    <i class="fas fa-play-circle"></i> Watch at ${timestamp}
                </a>` : ''}
            `;

            this.sourcesList.appendChild(sourceDiv);
        });
    }
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ChatApp();
});
