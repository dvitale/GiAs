/**
 * GIAS ChatBot - Claude-style UI
 * Interfaccia chat minimalista con welcome screen e chat mode
 */

class ChatBot {
    constructor() {
        // DOM Elements - Welcome Screen
        this.welcomeScreen = document.getElementById('welcomeScreen');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.quickActions = document.getElementById('quickActions');
        this.greetingText = document.getElementById('greetingText');

        // DOM Elements - Chat Screen
        this.chatScreen = document.getElementById('chatScreen');
        this.chatMessages = document.getElementById('chatMessages');
        this.chatMessageInput = document.getElementById('chatMessageInput');
        this.chatSendButton = document.getElementById('chatSendButton');
        this.chatQuickActions = document.getElementById('chatQuickActions');

        // DOM Elements - Shared
        this.appContainer = document.getElementById('appContainer');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.themeToggle = document.getElementById('themeToggle');

        // State
        this.isInChatMode = false;
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.COLLAPSE_THRESHOLD = 10;

        // Unique sender ID per session
        this.senderId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

        // Initialize
        this.initializeEventListeners();
        this.initializeTheme();
        this.initLogoDebugLink();
        this.setGreeting();
        this.loadPredefinedQuestions();
        this.initAccessibility();
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    initializeEventListeners() {
        // Welcome screen input
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.messageInput.addEventListener('input', () => {
            this.autoResizeTextarea(this.messageInput);
            this.sendButton.disabled = this.messageInput.value.trim() === '';
        });

        // Chat screen input
        this.chatSendButton.addEventListener('click', () => this.sendMessage());
        this.chatMessageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.chatMessageInput.addEventListener('input', () => {
            this.autoResizeTextarea(this.chatMessageInput);
            this.chatSendButton.disabled = this.chatMessageInput.value.trim() === '';
        });

        // Theme toggle
        this.themeToggle.addEventListener('click', () => this.toggleTheme());

        // Initial button state
        this.sendButton.disabled = true;
        this.chatSendButton.disabled = true;
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }

    setGreeting() {
        const hour = new Date().getHours();
        let greeting;

        if (hour >= 5 && hour < 12) {
            greeting = 'Buongiorno';
        } else if (hour >= 12 && hour < 18) {
            greeting = 'Buon pomeriggio';
        } else {
            greeting = 'Buonasera';
        }

        // Add user name if available
        if (window.welcomeData && window.welcomeData.userName) {
            greeting += `, ${window.welcomeData.userName}`;
        }

        this.greetingText.textContent = greeting;
    }

    initializeTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-theme');
        }
    }

    toggleTheme() {
        document.body.classList.toggle('dark-theme');
        const isDark = document.body.classList.contains('dark-theme');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    }

    initLogoDebugLink() {
        const giasLogo = document.getElementById('giasLogo');
        if (giasLogo) {
            giasLogo.style.cursor = 'pointer';
            giasLogo.addEventListener('click', (e) => {
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    window.location.href = window.basePath + '/debug' + window.location.search;
                } else if (e.shiftKey) {
                    e.preventDefault();
                    window.location.href = window.basePath + '/debug/langgraph' + window.location.search;
                }
            });
        }
    }

    initAccessibility() {
        if (this.chatMessages) {
            this.chatMessages.setAttribute('role', 'log');
            this.chatMessages.setAttribute('aria-live', 'polite');
            this.chatMessages.setAttribute('aria-label', 'Conversazione');
        }
    }

    // =========================================================================
    // Screen Transitions
    // =========================================================================

    switchToChatMode() {
        if (this.isInChatMode) return;

        this.isInChatMode = true;
        this.appContainer.classList.add('chat-mode');
        this.welcomeScreen.classList.add('hidden');
        this.chatScreen.classList.remove('hidden');

        // Move quick action buttons to chat screen
        if (this.quickActions && this.chatQuickActions) {
            while (this.quickActions.firstChild) {
                this.chatQuickActions.appendChild(this.quickActions.firstChild);
            }
        }

        // Focus on chat input
        setTimeout(() => {
            this.chatMessageInput.focus();
        }, 100);

        // Initialize scroll-to-bottom button
        this.initScrollToBottom();
    }

    // =========================================================================
    // Message Handling
    // =========================================================================

    getCurrentInput() {
        return this.isInChatMode ? this.chatMessageInput : this.messageInput;
    }

    getCurrentSendButton() {
        return this.isInChatMode ? this.chatSendButton : this.sendButton;
    }

    async sendMessage() {
        const input = this.getCurrentInput();
        const message = input.value.trim();
        if (!message) return;

        // Switch to chat mode on first message
        if (!this.isInChatMode) {
            this.switchToChatMode();
        }

        // Feature detection: use streaming if enabled and supported
        if (this.isStreamingEnabled() && this.supportsStreaming()) {
            return this.sendMessageStreaming(message);
        }

        // Fallback to synchronous mode
        this.addUserMessage(message);
        input.value = '';
        input.style.height = 'auto';
        this.getCurrentSendButton().disabled = true;
        this.showTypingIndicator();

        try {
            const response = await this.sendToServerWithRetry(message);
            this.hideTypingIndicator();

            if (response.status === 'success') {
                this.addBotMessage(response.message, message, response.full_data, response.data_type, response.suggestions);
            } else {
                this.addBotMessage('Mi dispiace, si è verificato un errore. Riprova più tardi.');
                console.error('Server error:', response.error);
            }
        } catch (error) {
            this.hideTypingIndicator();
            let errorMessage = this.getErrorMessage(error);
            this.addBotMessage(errorMessage);
            console.error('Network error after retries:', error);
        } finally {
            this.getCurrentSendButton().disabled = false;
            this.getCurrentInput().focus();
        }
    }

    getErrorMessage(error) {
        if (error.message && error.message.includes('Timeout:')) {
            return 'La richiesta ha impiegato troppo tempo. Il sistema potrebbe essere sovraccarico. Riprova tra qualche minuto.';
        } else if (error.message && error.message.includes('Server error (5')) {
            return 'Il server non è disponibile al momento. Riprova più tardi.';
        } else if (error.message && error.message.includes('Request timeout (408)')) {
            return 'Il server ha impiegato troppo tempo a elaborare la richiesta. Riprova con una domanda più semplice.';
        }
        return 'Non riesco a connettermi al server. Verifica la tua connessione e riprova.';
    }

    async sendToServerWithRetry(message, maxRetries = 3) {
        let lastError;

        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                if (attempt > 1) {
                    this.updateTypingIndicator(`Tentativo ${attempt}/${maxRetries}...`);
                }

                const response = await this.sendToServer(message);

                if (attempt > 1) {
                    this.updateTypingIndicator('Sto elaborando...');
                }

                return response;
            } catch (error) {
                lastError = error;

                if (error.message && (error.message.includes('Timeout:') || error.message.includes('timeout'))) {
                    throw error;
                }

                if (error.message && !error.message.includes('HTTP error') && !error.message.includes('fetch') && !error.message.includes('Server error')) {
                    throw error;
                }

                if (attempt < maxRetries) {
                    const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
                    this.updateTypingIndicator(`Riconnessione in corso...`);
                    await this.sleep(delay);
                }
            }
        }

        throw lastError;
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async sendToServer(message) {
        const payload = {
            message: message,
            sender: this.senderId
        };

        if (window.queryParams) {
            if (window.queryParams.asl_name) {
                payload.asl = window.queryParams.asl_name;
            } else if (window.queryParams.asl_id) {
                payload.asl_id = window.queryParams.asl_id;
            }
            if (window.queryParams.user_id) payload.user_id = window.queryParams.user_id;
            if (window.queryParams.codice_fiscale) payload.codice_fiscale = window.queryParams.codice_fiscale;
            if (window.queryParams.username) payload.username = window.queryParams.username;
        }

        const controller = new AbortController();
        const timeoutMs = 75000;
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const response = await fetch(window.basePath + '/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorText = await response.text();
                if (response.status >= 500) {
                    throw new Error(`Server error (${response.status}): ${errorText}`);
                } else if (response.status === 408) {
                    throw new Error(`Request timeout (${response.status})`);
                } else {
                    throw new Error(`HTTP error (${response.status}): ${errorText}`);
                }
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error('Timeout: La richiesta ha impiegato troppo tempo (>75s)');
            }
            throw error;
        }
    }

    // =========================================================================
    // Message Display
    // =========================================================================

    addUserMessage(message) {
        const messageElement = this.createMessageElement(message, 'user-message');
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addBotMessage(message, userQuestion = null, fullData = null, dataType = null, suggestions = null) {
        const messageElement = this.createMessageElement(message, 'bot-message', userQuestion, fullData, dataType, suggestions);
        this.chatMessages.appendChild(messageElement);
        this.applyCollapsing(messageElement);
        this.scrollToBottom();
    }

    createMessageElement(message, className, userQuestion = null, fullData = null, dataType = null, suggestions = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${className}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = this.formatMessage(message);

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = this.formatTime(new Date());

        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);

        if (className === 'bot-message' && userQuestion && !this.isFallbackMessage(message)) {
            const downloadBtn = this.createDownloadButton(userQuestion, message, fullData, dataType);
            messageDiv.appendChild(downloadBtn);
        }

        if (className === 'bot-message' && suggestions && suggestions.length > 0) {
            const suggestionsContainer = this.createSuggestionsContainer(suggestions);
            messageDiv.appendChild(suggestionsContainer);
        }

        if (className === 'bot-message') {
            this.attachQuestionLinkHandlers(contentDiv);
        }

        return messageDiv;
    }

    attachQuestionLinkHandlers(container) {
        container.querySelectorAll('.question-link').forEach(link => {
            const question = link.getAttribute('data-question');
            link.title = `${question}\n\nCtrl+Click per inviare direttamente`;
            link.addEventListener('click', (e) => {
                e.preventDefault();
                if (e.ctrlKey || e.metaKey) {
                    this.sendQuestionDirectly(question);
                } else {
                    this.handleQuestionClick(question);
                }
            });
        });
    }

    formatTime(date) {
        return date.toLocaleTimeString('it-IT', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    isFallbackMessage(message) {
        const fallbackKeywords = [
            'non ho capito', 'mi dispiace', 'non riesco',
            'si è verificato un errore', 'riprova più tardi',
            'controlla la tua connessione'
        ];
        const lowerMessage = message.toLowerCase();
        return fallbackKeywords.some(keyword => lowerMessage.includes(keyword));
    }

    // =========================================================================
    // Message Formatting
    // =========================================================================

    formatMessage(message) {
        if (!message || typeof message !== 'string') return '';

        let formatted = message
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        const blocks = this.parseContentBlocks(formatted);
        const htmlBlocks = blocks.map(block => this.convertBlockToHTML(block));
        return htmlBlocks.filter(block => block.trim()).join('');
    }

    parseContentBlocks(text) {
        const lines = text.split('\n').map(line => line.trim()).filter(line => line);
        const blocks = [];
        let currentBlock = null;

        for (const line of lines) {
            const blockType = this.identifyLineType(line);

            if (blockType === 'list-item' && currentBlock?.type === 'list') {
                currentBlock.content.push(line);
            } else if (blockType === 'field' && currentBlock?.type === 'field-group') {
                currentBlock.content.push(line);
            } else {
                if (currentBlock) blocks.push(currentBlock);

                if (blockType === 'list-item') {
                    currentBlock = { type: 'list', content: [line] };
                } else if (blockType === 'field') {
                    currentBlock = { type: 'field-group', content: [line] };
                } else {
                    currentBlock = { type: blockType, content: line };
                }
            }
        }

        if (currentBlock) blocks.push(currentBlock);
        return blocks;
    }

    identifyLineType(line) {
        if (/^\d+\.\s+/.test(line)) return 'list-item';
        if (/^[•-]\s+/.test(line)) return 'bullet-item';
        if (/^###\s+/.test(line)) return 'markdown-header';
        if (/^\*\*[^*]+:\*\*$/.test(line)) return 'header';
        if (/^\*\*[^*]+:\*\*\s+/.test(line)) return 'field';
        if (/^[A-Za-zÀ-ÿ\s]+:\s*\w/.test(line)) return 'field';
        if (/^[A-Za-zÀ-ÿ\s]+:$/.test(line)) return 'subheader';
        return 'text';
    }

    convertBlockToHTML(block) {
        switch (block.type) {
            case 'markdown-header':
                const markdownHeaderText = block.content.replace(/^###\s+/, '');
                return `<div class="section-header"><strong>${markdownHeaderText}</strong></div>`;

            case 'header':
                const headerText = block.content.replace(/^\*\*|\*\*$/g, '');
                return `<div class="section-header"><strong>${headerText}</strong></div>`;

            case 'subheader':
                return `<div class="sub-header"><strong>${block.content}</strong></div>`;

            case 'list':
                const listItems = block.content.map(item => {
                    const match = item.match(/^(\d+)\.\s+(.+)$/);
                    if (match) {
                        const [, number, content] = match;
                        const processedContent = this.processListItemContent(content);
                        return `<div class="list-item-compact"><span class="list-number">${number}.</span> ${processedContent}</div>`;
                    }
                    return `<div class="list-item-compact">${this.convertMarkdown(item)}</div>`;
                }).join('');
                return `<div class="list-container">${listItems}</div>`;

            case 'field-group':
                const fields = block.content.map(field => this.formatField(field)).join('');
                return `<div class="field-group">${fields}</div>`;

            case 'field':
                return `<div class="field-group">${this.formatField(block.content)}</div>`;

            case 'bullet-item':
                const bulletContent = block.content.replace(/^[•-]\s+/, '');
                return `<div class="bullet-item-compact">${this.convertMarkdown(bulletContent)}</div>`;

            case 'text':
                return `<div class="text-content">${this.convertMarkdown(block.content)}</div>`;

            default:
                return `<div class="default-content">${this.convertMarkdown(block.content)}</div>`;
        }
    }

    convertMarkdown(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/\[\[([^\]]+)\]\]/g, '<a href="#" class="question-link" data-question="$1">$1</a>');
    }

    processListItemContent(content) {
        const pipeMatch = content.match(/^(.+?)\s*\|\s*(.+?)\s*\|\s*(.+)$/);
        if (pipeMatch) {
            const [, header, desc, relevance] = pipeMatch;
            return `<span class="plan-header">${this.convertMarkdown(header)}</span><span class="plan-desc">${this.convertMarkdown(desc)}</span><span class="plan-relevance">${this.convertMarkdown(relevance)}</span>`;
        }
        return this.convertMarkdown(content);
    }

    formatField(fieldText) {
        const boldMatch = fieldText.match(/^\*\*([^*]+):\*\*\s+(.+)$/);
        if (boldMatch) {
            return `<div class="field-line"><strong class="field-label">${boldMatch[1]}:</strong> <span class="field-value">${this.convertMarkdown(boldMatch[2])}</span></div>`;
        }

        const colonMatch = fieldText.match(/^([^:]+):\s*(.+)$/);
        if (colonMatch) {
            return `<div class="field-line"><span class="field-label">${colonMatch[1]}:</span> <span class="field-value">${this.convertMarkdown(colonMatch[2])}</span></div>`;
        }

        return `<div class="field-line">${this.convertMarkdown(fieldText)}</div>`;
    }

    // =========================================================================
    // Quick Actions & Predefined Questions
    // =========================================================================

    async loadPredefinedQuestions() {
        try {
            const response = await fetch(window.basePath + '/api/predefined-questions');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();
            if (data.status === 'success' && data.questions) {
                this.renderQuickActions(data.questions);
            }
        } catch (error) {
            console.error('Failed to load predefined questions:', error);
        }
    }

    renderQuickActions(questions) {
        if (!this.quickActions) return;

        const sortedQuestions = questions.sort((a, b) => a.order - b.order);
        this.quickActions.innerHTML = '';

        // Category icons
        const categoryIcons = {
            help: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
            piani: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
            priorita: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
            default: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
        };

        sortedQuestions.forEach(question => {
            const button = document.createElement('button');
            button.className = 'quick-action-btn';

            const icon = categoryIcons[question.category] || categoryIcons.default;
            button.innerHTML = `${icon}<span>${question.text}</span>`;

            button.title = question.title || question.question;
            button.dataset.question = question.question;

            button.addEventListener('click', (e) => {
                if (e.ctrlKey || e.metaKey) {
                    this.sendQuestionDirectly(question.question);
                } else {
                    this.handleQuestionClick(question.question);
                }
            });

            this.quickActions.appendChild(button);
        });
    }

    handleQuestionClick(question) {
        const input = this.getCurrentInput();
        input.value = question;
        this.getCurrentSendButton().disabled = false;
        input.focus();
    }

    async sendQuestionDirectly(question) {
        if (!this.isInChatMode) {
            this.switchToChatMode();
        }

        this.addUserMessage(question);
        this.showTypingIndicator();

        try {
            const response = await this.sendToServer(question);
            this.hideTypingIndicator();

            if (response.status === 'success') {
                this.addBotMessage(response.message, question, response.full_data, response.data_type, response.suggestions);
            } else {
                this.addBotMessage('Mi dispiace, si è verificato un errore. Riprova più tardi.');
            }
        } catch (error) {
            this.hideTypingIndicator();
            this.addBotMessage(this.getErrorMessage(error));
            console.error('Network error:', error);
        }
    }

    // =========================================================================
    // Download & Suggestions
    // =========================================================================

    createDownloadButton(question, answer, fullData = null, dataType = null) {
        const btnContainer = document.createElement('div');
        btnContainer.className = 'download-btn-container';

        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'download-btn';
        downloadBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            <span>Scarica</span>
        `;

        downloadBtn.title = fullData && fullData.length > 0
            ? `Scarica tutti i ${fullData.length} risultati`
            : 'Scarica conversazione';

        downloadBtn.addEventListener('click', () => this.downloadConversation(question, answer, fullData, dataType));
        btnContainer.appendChild(downloadBtn);
        return btnContainer;
    }

    createSuggestionsContainer(suggestions) {
        const container = document.createElement('div');
        container.className = 'suggestions-container';

        const header = document.createElement('div');
        header.className = 'suggestions-header';
        header.textContent = 'Cosa vuoi fare ora?';
        container.appendChild(header);

        suggestions.forEach(suggestion => {
            const link = document.createElement('a');
            link.className = 'suggestion-link';
            link.href = '#';
            link.innerHTML = this.formatMessage(suggestion.text);
            link.title = `${suggestion.text}\n\nCtrl+Click per inviare direttamente`;

            link.addEventListener('click', (e) => {
                e.preventDefault();
                if (e.ctrlKey || e.metaKey) {
                    this.sendQuestionDirectly(suggestion.query);
                } else {
                    this.handleQuestionClick(suggestion.query);
                }
            });

            container.appendChild(link);
        });

        return container;
    }

    downloadConversation(question, answer, fullData = null, dataType = null) {
        const timestamp = new Date().toLocaleString('it-IT');
        const cleanAnswer = this.stripHtmlTags(answer);

        let userInfo = '';
        if (window.queryParams) {
            const parts = [];
            if (window.queryParams.user_id) parts.push(`User ID: ${window.queryParams.user_id}`);
            if (window.queryParams.asl_name) parts.push(`ASL: ${window.queryParams.asl_name}`);
            if (window.queryParams.asl_id && !window.queryParams.asl_name) parts.push(`ASL ID: ${window.queryParams.asl_id}`);
            if (parts.length > 0) userInfo = '\n' + parts.join('\n') + '\n';
        }

        let content = `Conversazione Chatbot GIAS
Data: ${timestamp}${userInfo}
DOMANDA:
${question}

RISPOSTA:
${cleanAnswer}
`;

        if (fullData && fullData.length > 0) {
            content += `\n${'='.repeat(60)}\nDATI COMPLETI (${fullData.length} risultati)\n${'='.repeat(60)}\n\n`;

            fullData.forEach((item, idx) => {
                content += `${idx + 1}. ${JSON.stringify(item, null, 2)}\n\n`;
            });
        }

        content += `\n---\nGenerato da Chatbot GIAS\n`;

        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `gias-${Date.now()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    stripHtmlTags(html) {
        const tmp = document.createElement('div');
        tmp.innerHTML = html;
        return tmp.textContent || tmp.innerText || '';
    }

    // =========================================================================
    // UI Helpers
    // =========================================================================

    showTypingIndicator() {
        this.typingIndicator.classList.add('visible');
        this.chatMessages.appendChild(this.typingIndicator);
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.typingIndicator.classList.remove('visible');
        if (this.typingIndicator.parentNode) {
            this.typingIndicator.parentNode.removeChild(this.typingIndicator);
        }
    }

    updateTypingIndicator(text) {
        const span = this.typingIndicator.querySelector('span');
        if (span) span.textContent = text;
    }

    scrollToBottom(smooth = true) {
        if (smooth) {
            this.chatMessages.scrollTo({
                top: this.chatMessages.scrollHeight,
                behavior: 'smooth'
            });
        } else {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }

    initScrollToBottom() {
        this.scrollToBottomBtn = document.createElement('button');
        this.scrollToBottomBtn.className = 'scroll-to-bottom';
        this.scrollToBottomBtn.innerHTML = '↓';
        this.scrollToBottomBtn.title = 'Vai in fondo';
        this.scrollToBottomBtn.addEventListener('click', () => this.scrollToBottom());

        document.body.appendChild(this.scrollToBottomBtn);

        this.chatMessages.addEventListener('scroll', () => {
            const isNearBottom = this.chatMessages.scrollHeight
                - this.chatMessages.scrollTop
                - this.chatMessages.clientHeight < 100;

            if (isNearBottom) {
                this.scrollToBottomBtn.classList.remove('visible');
            } else {
                this.scrollToBottomBtn.classList.add('visible');
            }
        });
    }

    applyCollapsing(messageElement) {
        const listContainers = messageElement.querySelectorAll('.list-container');

        listContainers.forEach(container => {
            const items = container.querySelectorAll('.list-item-compact');
            if (items.length <= this.COLLAPSE_THRESHOLD) return;

            items.forEach((item, i) => {
                if (i >= this.COLLAPSE_THRESHOLD) {
                    item.classList.add('collapsible-item');
                }
            });

            const toggle = document.createElement('button');
            toggle.className = 'expand-toggle';
            const hiddenCount = items.length - this.COLLAPSE_THRESHOLD;
            toggle.textContent = `Mostra tutti i ${items.length} risultati (+${hiddenCount})`;

            toggle.addEventListener('click', () => {
                const isExpanded = toggle.classList.contains('expanded');

                items.forEach((item, i) => {
                    if (i >= this.COLLAPSE_THRESHOLD) {
                        item.classList.toggle('expanded', !isExpanded);
                    }
                });

                if (isExpanded) {
                    toggle.classList.remove('expanded');
                    toggle.textContent = `Mostra tutti i ${items.length} risultati (+${hiddenCount})`;
                } else {
                    toggle.classList.add('expanded');
                    toggle.textContent = 'Mostra meno';
                }
            });

            container.appendChild(toggle);
        });
    }

    // =========================================================================
    // SSE Streaming
    // =========================================================================

    isStreamingEnabled() {
        return typeof window.streamingEnabled === 'undefined' || window.streamingEnabled !== false;
    }

    supportsStreaming() {
        return typeof ReadableStream !== 'undefined';
    }

    createThinkingMessage() {
        const div = document.createElement('div');
        div.className = 'message bot-message thinking-message';
        div.innerHTML = `
            <div class="thinking-content">
                <div class="thinking-dots">
                    <div></div>
                    <div></div>
                    <div></div>
                </div>
                <span class="thinking-text">Analizzando...</span>
            </div>
        `;
        return div;
    }

    updateThinkingMessage(div, text) {
        const textSpan = div.querySelector('.thinking-text');
        if (textSpan) textSpan.textContent = text;
    }

    hideThinkingMessage(div) {
        if (div && div.parentNode) {
            div.classList.add('fade-out');
            setTimeout(() => {
                if (div.parentNode) div.parentNode.removeChild(div);
            }, 300);
        }
    }

    async sendMessageStreaming(message) {
        if (!this.isInChatMode) {
            this.switchToChatMode();
        }

        const input = this.getCurrentInput();
        this.addUserMessage(message);
        input.value = '';
        input.style.height = 'auto';
        this.getCurrentSendButton().disabled = true;

        const thinkingDiv = this.createThinkingMessage();
        this.chatMessages.appendChild(thinkingDiv);
        this.scrollToBottom();

        try {
            await this.connectSSE(message, thinkingDiv);
        } catch (error) {
            console.error('Streaming error:', error);
            this.hideThinkingMessage(thinkingDiv);

            this.showTypingIndicator();
            try {
                const response = await this.sendToServerWithRetry(message);
                this.hideTypingIndicator();

                if (response.status === 'success') {
                    this.addBotMessage(response.message, message, response.full_data, response.data_type, response.suggestions);
                } else {
                    this.addBotMessage('Mi dispiace, si è verificato un errore. Riprova più tardi.');
                }
            } catch (fallbackError) {
                this.hideTypingIndicator();
                this.addBotMessage(this.getErrorMessage(fallbackError));
            }
        } finally {
            this.getCurrentSendButton().disabled = false;
        }
    }

    async connectSSE(message, thinkingDiv) {
        const payload = {
            message: message,
            sender: this.senderId,
            asl: window.queryParams?.asl_name || window.queryParams?.asl_id,
            asl_id: window.queryParams?.asl_id,
            user_id: window.queryParams?.user_id,
            codice_fiscale: window.queryParams?.codice_fiscale,
            username: window.queryParams?.username
        };

        const response = await fetch(window.basePath + '/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalContent = '';
        let finalMetadata = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            let eventType = 'status';
            let dataLines = [];

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    dataLines.push(line.slice(6));
                } else if (line === '') {
                    if (dataLines.length > 0) {
                        try {
                            const dataStr = dataLines.join('\n');
                            const data = JSON.parse(dataStr);
                            data.type = eventType;
                            this.handleSSEEvent(data, thinkingDiv);

                            if (data.type === 'final') {
                                if (data.result) {
                                    // Nuovo formato V1: result contiene ChatResult tipizzato
                                    finalContent = data.result.text;
                                    finalMetadata = {
                                        intent: data.result.intent,
                                        suggestions: data.result.suggestions,
                                        needs_clarification: data.result.needs_clarification,
                                    };
                                } else {
                                    // Fallback formato Rasa legacy
                                    finalContent = data.content;
                                    finalMetadata = data.metadata || {};
                                }
                            }
                        } catch (e) {
                            console.error('Failed to parse SSE data:', e);
                        }
                        dataLines = [];
                    }
                }
            }
        }

        this.hideThinkingMessage(thinkingDiv);

        if (finalContent) {
            this.addBotMessage(
                finalContent,
                message,
                finalMetadata.full_data,
                finalMetadata.data_type,
                finalMetadata.suggestions
            );
        }
    }

    handleSSEEvent(event, thinkingDiv) {
        switch (event.type) {
            case 'status':
                this.updateThinkingMessage(thinkingDiv, event.message || 'Elaborazione...');
                break;
            case 'reasoning':
                this.updateThinkingMessage(thinkingDiv, event.message);
                break;
            case 'error':
                this.hideThinkingMessage(thinkingDiv);
                this.addBotMessage(`Si è verificato un errore: ${event.error}`);
                break;
        }
    }

    // =========================================================================
    // Utility
    // =========================================================================

    escapeHtml(text) {
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return text.replace(/[&<>"']/g, (m) => map[m]);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ChatBot();
});
