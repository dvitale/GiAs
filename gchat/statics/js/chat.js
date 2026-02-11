class ChatBot {
    constructor() {
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.chatMessages = document.getElementById('chatMessages');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.questionsContainer = document.getElementById('questionsContainer');
        this.themeToggle = document.getElementById('themeToggle');

        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];

        this.COLLAPSE_THRESHOLD = 10;  // Mostra N item, collassa il resto

        this.initializeEventListeners();
        this.initializeTheme();
        this.initSpeechRecognition();
        this.initLogoDebugLink();
        this.setWelcomeTime();
        this.loadPredefinedQuestions();
        this.initScrollToBottom();
        this.initAccessibility();
    }

    initializeEventListeners() {
        this.sendButton.addEventListener('click', () => this.sendMessage());

        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.messageInput.addEventListener('input', () => {
            this.sendButton.disabled = this.messageInput.value.trim() === '';
        });

        this.themeToggle.addEventListener('click', () => this.toggleTheme());

        this.sendButton.disabled = true;

        // Render welcome message
        this.renderWelcomeMessage();
    }

    renderWelcomeMessage() {
        const welcomeContent = document.getElementById('welcomeContent');
        if (welcomeContent && window.welcomeData) {
            const greeting = window.welcomeData.userName
                ? `Ciao ${window.welcomeData.userName}! `
                : 'Ciao! ';
            const fullMessage = greeting + window.welcomeData.message;
            welcomeContent.innerHTML = this.formatMessage(fullMessage);

            // Convert quoted questions in bullet items to clickable links
            welcomeContent.querySelectorAll('.bullet-item-compact').forEach(el => {
                const text = el.textContent.trim();
                const match = text.match(/^"(.+)"$/);
                if (match) {
                    const question = match[1];
                    const link = document.createElement('a');
                    link.href = '#';
                    link.className = 'question-link';
                    link.setAttribute('data-question', question);
                    link.textContent = question;
                    el.textContent = '';
                    el.appendChild(link);
                }
            });

            // Attach click handlers to question links (same behavior as predefined questions)
            welcomeContent.querySelectorAll('.question-link').forEach(link => {
                link.title = `${link.getAttribute('data-question')}\n\n💡 Ctrl+Click per inviare direttamente`;
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const question = link.getAttribute('data-question');
                    if (e.ctrlKey || e.metaKey) {
                        this.sendQuestionDirectly(question);
                    } else {
                        this.handleQuestionClick(question);
                    }
                });
            });
        }
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
                    // Ctrl+Click: Navigate to debug page preserving querystring
                    const debugUrl = window.basePath + '/debug' + window.location.search;
                    window.location.href = debugUrl;
                } else if (e.shiftKey) {
                    e.preventDefault();
                    // Shift+Click: Navigate to langgraph debug page preserving querystring
                    const langgraphUrl = window.basePath + '/debug/langgraph' + window.location.search;
                    window.location.href = langgraphUrl;
                }
            });
        }
    }

    setWelcomeTime() {
        const welcomeTimeElement = document.getElementById('welcomeTime');
        if (welcomeTimeElement) {
            welcomeTimeElement.textContent = this.formatTime(new Date());
        }
    }

    formatTime(date) {
        return date.toLocaleTimeString('it-IT', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Feature detection: use streaming if enabled and supported
        if (this.isStreamingEnabled() && this.supportsStreaming()) {
            return this.sendMessageStreaming();
        }

        // Fallback to synchronous mode
        this.addUserMessage(message);
        this.messageInput.value = '';
        this.sendButton.disabled = true;
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

            // Show specific error message based on error type
            let errorMessage;
            if (error.message && error.message.includes('Timeout:')) {
                errorMessage = '⏱️ La richiesta ha impiegato troppo tempo. Il sistema LLM potrebbe essere sovraccarico. Riprova tra qualche minuto.';
            } else if (error.message && error.message.includes('Server error (5')) {
                errorMessage = '🔧 Il server LLM non è disponibile al momento. Riprova più tardi o contatta l\'amministratore.';
            } else if (error.message && error.message.includes('Request timeout (408)')) {
                errorMessage = '⏳ Il server ha impiegato troppo tempo a elaborare la richiesta. Riprova con una domanda più semplice.';
            } else {
                errorMessage = 'Mi dispiace, non riesco a connettermi al server dopo diversi tentativi. Verifica la tua connessione e riprova.';
            }

            this.addBotMessage(errorMessage);
            console.error('Network error after retries:', error);
        } finally {
            this.sendButton.disabled = false;
            this.messageInput.focus();
        }
    }

    async sendToServerWithRetry(message, maxRetries = 3) {
        let lastError;

        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                console.log(`Attempt ${attempt}/${maxRetries} to send message`);

                // Update typing indicator with retry info
                if (attempt > 1) {
                    this.updateTypingIndicator(`Tentativo ${attempt}/${maxRetries}...`);
                }

                const response = await this.sendToServer(message);

                // Reset typing indicator on success
                if (attempt > 1) {
                    this.updateTypingIndicator('Il bot sta scrivendo...');
                }

                return response;
            } catch (error) {
                lastError = error;
                console.warn(`Attempt ${attempt} failed:`, error.message);

                // Don't retry timeout errors - they won't get better with retry
                if (error.message && (error.message.includes('Timeout:') || error.message.includes('timeout'))) {
                    throw error;
                }

                // Don't retry if it's not a network error
                if (error.message && !error.message.includes('HTTP error') && !error.message.includes('fetch') && !error.message.includes('Server error')) {
                    throw error;
                }

                // Don't wait after the last attempt
                if (attempt < maxRetries) {
                    const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000); // Exponential backoff, max 5s
                    console.log(`Waiting ${delay}ms before retry...`);
                    this.updateTypingIndicator(`Riconnessione in corso... (${attempt}/${maxRetries})`);
                    await this.sleep(delay);
                }
            }
        }

        // All retries failed
        throw lastError;
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    updateTypingIndicator(text) {
        const indicator = document.querySelector('#typingIndicator span');
        if (indicator) {
            indicator.textContent = text;
        }
    }

    async sendToServer(message) {
        // Prepare the payload with additional context if available
        const payload = {
            message: message,
            sender: 'user'
        };

        // Add ASL context if available from query parameters - prioritize asl_name over asl_id
        if (window.queryParams) {
            if (window.queryParams.asl_name) {
                payload.asl = window.queryParams.asl_name;
            } else if (window.queryParams.asl_id) {
                payload.asl_id = window.queryParams.asl_id;
            }
        }

        // Add other context parameters if needed
        if (window.queryParams) {
            if (window.queryParams.user_id) payload.user_id = window.queryParams.user_id;
            if (window.queryParams.codice_fiscale) payload.codice_fiscale = window.queryParams.codice_fiscale;
            if (window.queryParams.username) payload.username = window.queryParams.username;
        }

        // Create AbortController for timeout (75 seconds - maggiore del server Go 60s)
        const controller = new AbortController();
        const timeoutMs = 75000; // 75 seconds
        const timeoutId = setTimeout(() => {
            controller.abort();
        }, timeoutMs);

        try {
            const response = await fetch(window.basePath + '/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
                signal: controller.signal
            });

            clearTimeout(timeoutId); // Clear timeout on success

            if (!response.ok) {
                const errorText = await response.text();
                if (response.status >= 500) {
                    throw new Error(`Server error (${response.status}): ${errorText}`);
                } else if (response.status === 408) {
                    throw new Error(`Request timeout (${response.status}): Il server ha impiegato troppo tempo a rispondere`);
                } else {
                    throw new Error(`HTTP error (${response.status}): ${errorText}`);
                }
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId); // Always clear timeout

            if (error.name === 'AbortError') {
                throw new Error('Timeout: La richiesta ha impiegato troppo tempo (>75s)');
            }
            throw error; // Re-throw other errors
        }
    }

    addUserMessage(message) {
        const messageElement = this.createMessageElement(message, 'user-message');
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addBotMessage(message, userQuestion = null, fullData = null, dataType = null, suggestions = null) {
        const messageElement = this.createMessageElement(message, 'bot-message', userQuestion, fullData, dataType, suggestions);
        this.chatMessages.appendChild(messageElement);
        // Applica collapsing per liste lunghe
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
            const questionLinks = contentDiv.querySelectorAll('.question-link');
            questionLinks.forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const question = link.getAttribute('data-question');
                    this.handleQuestionClick(question);
                });
            });
        }

        return messageDiv;
    }

    isFallbackMessage(message) {
        const fallbackKeywords = [
            'non ho capito',
            'mi dispiace',
            'non riesco',
            'si è verificato un errore',
            'riprova più tardi',
            'controlla la tua connessione'
        ];
        const lowerMessage = message.toLowerCase();
        return fallbackKeywords.some(keyword => lowerMessage.includes(keyword));
    }

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

        if (fullData && fullData.length > 0) {
            downloadBtn.title = `Scarica tutti i ${fullData.length} risultati in formato testo`;
        } else {
            downloadBtn.title = 'Scarica conversazione in formato testo';
        }

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
            const suggestionLink = document.createElement('a');
            suggestionLink.className = 'suggestion-link';
            suggestionLink.href = '#';
            suggestionLink.innerHTML = this.formatMessage(suggestion.text);

            suggestionLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.messageInput.value = suggestion.query;
                this.sendButton.disabled = false;
                this.messageInput.focus();
            });

            container.appendChild(suggestionLink);
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
            if (window.queryParams.codice_fiscale) parts.push(`Codice Fiscale: ${window.queryParams.codice_fiscale}`);
            if (window.queryParams.username) parts.push(`Username: ${window.queryParams.username}`);

            if (parts.length > 0) {
                userInfo = '\n' + parts.join('\n') + '\n';
            }
        }

        let content = `Conversazione Chatbot GIAS
Data: ${timestamp}${userInfo}
DOMANDA:
${question}

RISPOSTA (Visualizzazione Chat):
${cleanAnswer}
`;

        // Se ci sono full_data, aggiungi tutti i record
        if (fullData && fullData.length > 0) {
            content += `\n\n${'='.repeat(80)}\n`;
            content += `DATI COMPLETI (${fullData.length} risultati)\n`;
            content += `${'='.repeat(80)}\n\n`;

            if (dataType === 'priority_establishments') {
                fullData.forEach((item, idx) => {
                    content += `${idx + 1}. ${item.macroarea}\n`;
                    content += `   Comune: ${item.comune}\n`;
                    content += `   Indirizzo: ${item.indirizzo}\n`;
                    content += `   N. Riconoscimento: ${item.num_riconoscimento}\n`;
                    content += `   Piano in ritardo: ${item.piano} (ritardo: ${item.diff} controlli)\n`;
                    content += `   Attività correlata: ${item.attivita}\n`;
                    content += `   Aggregazione: ${item.aggregazione}\n`;
                    content += `\n${'-'.repeat(80)}\n\n`;
                });
            } else if (dataType === 'risk_based_priority') {
                fullData.forEach((item, idx) => {
                    content += `${idx + 1}. ${item.macroarea} - ${item.aggregazione}\n`;
                    content += `   Comune: ${item.comune}\n`;
                    content += `   Indirizzo: ${item.indirizzo}\n`;
                    content += `   ID: ${item.numero_id}\n`;
                    content += `   Punteggio rischio attività: ${item.punteggio_rischio}\n`;
                    content += `   NC storiche attività: ${item.nc_gravi} gravi | ${item.nc_non_gravi} non gravi\n`;
                    content += `   Controlli regionali su questa attività: ${item.controlli_regionali}\n`;
                    if (item.data_inizio_attivita !== 'N/D') {
                        content += `   Attivo dal: ${item.data_inizio_attivita}\n`;
                    }
                    content += `\n${'-'.repeat(80)}\n\n`;
                });
            }
        }

        content += `\n---\nGenerato da Chatbot GIAS - Sistema di Supporto Veterinario\n`;

        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `gias-conversazione-${Date.now()}.txt`;
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

    formatMessage(message) {
        if (!message || typeof message !== 'string') return '';

        // Step 1: Escape HTML but preserve structure
        let formatted = message
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Step 2: Parse into logical blocks
        const blocks = this.parseContentBlocks(formatted);

        // Step 3: Convert blocks to clean HTML
        const htmlBlocks = blocks.map(block => this.convertBlockToHTML(block));

        // Step 4: Join with minimal spacing
        const result = htmlBlocks.filter(block => block.trim()).join('');

        return result;
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
                // Start new block
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
                        return `<div class="list-item-compact" data-number="${number}">${processedContent}</div>`;
                    }
                    return `<div class="list-item-compact">${item}</div>`;
                }).join('');
                return `<div class="list-container">${listItems}</div>`;

            case 'field-group':
                const fields = block.content.map(field => this.formatField(field)).join('');
                return `<div class="field-group">${fields}</div>`;

            case 'field':
                return `<div class="field-group">${this.formatField(block.content)}</div>`;

            case 'bullet-item':
                const bulletContent = block.content.replace(/^[•-]\s+/, '');
                return `<div class="bullet-item-compact">${bulletContent}</div>`;

            case 'text':
                // Convert markdown bold **text** to HTML <strong>text</strong>
                const boldConverted = block.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                return `<div class="text-content">${boldConverted}</div>`;

            default:
                return `<div class="default-content">${block.content}</div>`;
        }
    }

    processListItemContent(content) {
        // Extract establishment info using more specific patterns
        const patterns = [
            { regex: /^([^-]+)\s-\s(.+)$/, format: '<div class="establishment-header"><strong>$1</strong> - $2</div>' },
            { regex: /Comune:\s*(.+)/i, format: '<div class="detail-line"><span class="label">Comune:</span> <span class="value">$1</span></div>' },
            { regex: /Indirizzo:\s*(.+)/i, format: '<div class="detail-line"><span class="label">Indirizzo:</span> <span class="value">$1</span></div>' },
            { regex: /ID:\s*(.+)/i, format: '<div class="detail-line"><span class="label">ID:</span> <span class="value">$1</span></div>' },
            { regex: /Punteggio rischio[^:]*:\s*\*\*(\d+)\*\*/i, format: '<div class="risk-score"><span class="label">Punteggio rischio:</span> <span class="score high">$1</span></div>' },
            { regex: /NC storiche[^:]*:\s*(\d+)\s+gravi\s*\|\s*(\d+)\s+non gravi/i, format: '<div class="nc-line"><span class="label">NC:</span> <span class="severe">$1 gravi</span> | <span class="minor">$2 non gravi</span></div>' },
            { regex: /Controlli[^:]*:\s*(\d+)/i, format: '<div class="controls-line"><span class="label">Controlli:</span> <span class="value">$1</span></div>' },
            { regex: /Attivo dal:\s*(.+)/i, format: '<div class="date-line"><span class="label">Attivo dal:</span> <span class="value">$1</span></div>' }
        ];

        let processed = content;
        for (const pattern of patterns) {
            processed = processed.replace(pattern.regex, pattern.format);
        }

        return processed;
    }

    formatField(fieldText) {
        // Handle markdown bold fields
        const boldMatch = fieldText.match(/^\*\*([^*]+):\*\*\s+(.+)$/);
        if (boldMatch) {
            return `<div class="field-line"><strong class="field-label">${boldMatch[1]}:</strong> <span class="field-value">${boldMatch[2]}</span></div>`;
        }

        // Handle simple colon fields
        const colonMatch = fieldText.match(/^([^:]+):\s*(.+)$/);
        if (colonMatch) {
            return `<div class="field-line"><span class="field-label">${colonMatch[1]}:</span> <span class="field-value">${colonMatch[2]}</span></div>`;
        }

        return `<div class="field-line">${fieldText}</div>`;
    }

    showTypingIndicator() {
        this.typingIndicator.style.display = 'flex';
        this.chatMessages.appendChild(this.typingIndicator);
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.typingIndicator.style.display = 'none';
        if (this.typingIndicator.parentNode) {
            this.typingIndicator.parentNode.removeChild(this.typingIndicator);
        }
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
        // Crea pulsante scroll-to-bottom
        this.scrollToBottomBtn = document.createElement('button');
        this.scrollToBottomBtn.className = 'scroll-to-bottom';
        this.scrollToBottomBtn.innerHTML = '↓';
        this.scrollToBottomBtn.title = 'Vai in fondo';
        this.scrollToBottomBtn.addEventListener('click', () => this.scrollToBottom());

        // Posiziona relativamente al container dei messaggi
        const chatMessagesParent = this.chatMessages.parentElement;
        if (chatMessagesParent) {
            chatMessagesParent.style.position = 'relative';
            chatMessagesParent.appendChild(this.scrollToBottomBtn);
        }

        // Rileva scroll position
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

    initAccessibility() {
        // Aggiungi attributi ARIA alla chat area
        if (this.chatMessages) {
            this.chatMessages.setAttribute('role', 'log');
            this.chatMessages.setAttribute('aria-live', 'polite');
            this.chatMessages.setAttribute('aria-label', 'Conversazione');
        }
        // ARIA sui pulsanti
        if (this.sendButton) {
            this.sendButton.setAttribute('aria-label', 'Invia messaggio');
        }
        if (this.themeToggle) {
            this.themeToggle.setAttribute('aria-label', 'Cambia tema');
        }
    }

    applyCollapsing(messageElement) {
        /**
         * Applica il collapsing progressivo alle liste lunghe
         * dentro un messaggio bot. Mostra i primi N item e nasconde il resto
         * con un pulsante "Mostra tutti".
         */
        const listContainers = messageElement.querySelectorAll('.list-container');

        listContainers.forEach(container => {
            const items = container.querySelectorAll('.list-item-compact');
            if (items.length <= this.COLLAPSE_THRESHOLD) return;

            // Nascondi item oltre la soglia
            items.forEach((item, i) => {
                if (i >= this.COLLAPSE_THRESHOLD) {
                    item.classList.add('collapsible-item');
                }
            });

            // Crea pulsante toggle
            const toggle = document.createElement('button');
            toggle.className = 'expand-toggle';
            const hiddenCount = items.length - this.COLLAPSE_THRESHOLD;
            toggle.textContent = `▼ Mostra tutti i ${items.length} risultati (altri ${hiddenCount})`;

            toggle.addEventListener('click', () => {
                const isExpanded = toggle.classList.contains('expanded');

                items.forEach((item, i) => {
                    if (i >= this.COLLAPSE_THRESHOLD) {
                        if (isExpanded) {
                            item.classList.remove('expanded');
                        } else {
                            item.classList.add('expanded');
                        }
                    }
                });

                if (isExpanded) {
                    toggle.classList.remove('expanded');
                    toggle.textContent = `▼ Mostra tutti i ${items.length} risultati (altri ${hiddenCount})`;
                } else {
                    toggle.classList.add('expanded');
                    toggle.textContent = `▲ Mostra meno`;
                }
            });

            container.appendChild(toggle);
        });
    }

    async loadPredefinedQuestions() {
        try {
            const response = await fetch(window.basePath + '/api/predefined-questions');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (data.status === 'success' && data.questions) {
                this.renderQuestionButtons(data.questions);
            }
        } catch (error) {
            console.error('Failed to load predefined questions:', error);
            // Hide the questions section if loading fails
            const questionsSection = document.getElementById('predefinedQuestions');
            if (questionsSection) {
                questionsSection.style.display = 'none';
            }
        }
    }

    renderQuestionButtons(questions) {
        if (!this.questionsContainer) {
            console.error('questionsContainer element not found!');
            return;
        }

        // Sort questions by order
        const sortedQuestions = questions.sort((a, b) => a.order - b.order);

        // Clear existing buttons
        this.questionsContainer.innerHTML = '';

        // Create and add buttons
        sortedQuestions.forEach(question => {
            const button = document.createElement('button');
            button.className = 'question-button';
            button.textContent = question.text;
            // Use title field if available, fallback to question, add Ctrl+click hint
            const baseTitle = question.title || question.question;
            button.title = `${baseTitle}\n\n💡 Ctrl+Click per inviare direttamente`;
            button.dataset.question = question.question;
            button.dataset.questionId = question.id;
            button.dataset.category = question.category;

            // Apply category-specific color if available
            if (question.color) {
                button.style.setProperty('--button-color', question.color);
                button.classList.add('colored-button');
            }

            // Add click handler with Ctrl+click support
            button.addEventListener('click', (e) => {
                if (e.ctrlKey || e.metaKey) {
                    // Ctrl+click or Cmd+click: send directly
                    this.sendQuestionDirectly(question.question);
                } else {
                    // Normal click: populate input field
                    this.handleQuestionClick(question.question);
                }
            });

            this.questionsContainer.appendChild(button);
        });
    }

    handleQuestionClick(question) {
        // Set the question in the input field without sending
        this.messageInput.value = question;
        this.sendButton.disabled = false;
        this.messageInput.focus();
    }

    async sendQuestionDirectly(question) {
        // Alternative method: send question directly without showing in input
        this.addUserMessage(question);
        this.showTypingIndicator();

        try {
            const response = await this.sendToServer(question);
            this.hideTypingIndicator();

            if (response.status === 'success') {
                this.addBotMessage(response.message, question);
            } else {
                this.addBotMessage('Mi dispiace, si è verificato un errore. Riprova più tardi.');
                console.error('Server error:', response.error);
            }
        } catch (error) {
            this.hideTypingIndicator();

            // Show specific error message based on error type
            let errorMessage;
            if (error.message && error.message.includes('Timeout:')) {
                errorMessage = '⏱️ La richiesta ha impiegato troppo tempo. Il sistema LLM potrebbe essere sovraccarico. Riprova tra qualche minuto.';
            } else if (error.message && error.message.includes('Server error (5')) {
                errorMessage = '🔧 Il server LLM non è disponibile al momento. Riprova più tardi o contatta l\'amministratore.';
            } else if (error.message && error.message.includes('Request timeout (408)')) {
                errorMessage = '⏳ Il server ha impiegato troppo tempo a elaborare la richiesta. Riprova con una domanda più semplice.';
            } else {
                errorMessage = 'Mi dispiace, non riesco a connettermi al server. Controlla la tua connessione.';
            }

            this.addBotMessage(errorMessage);
            console.error('Network error:', error);
        }
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (m) => map[m]);
    }

    initSpeechRecognition() {
        // Check if transcription is enabled
        if (typeof window.transcriptionEnabled === 'undefined' || !window.transcriptionEnabled) {
            console.log('Transcription disabled in config');
            return;
        }

        const inputContainer = document.querySelector('.input-container');
        if (!inputContainer) return;

        const micButton = document.createElement('button');
        micButton.id = 'mic-button';
        micButton.className = 'mic-button';
        micButton.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                <line x1="12" y1="19" x2="12" y2="23"></line>
                <line x1="8" y1="23" x2="16" y2="23"></line>
            </svg>
        `;
        micButton.title = 'Registra messaggio vocale';

        const sendButton = this.sendButton;
        inputContainer.insertBefore(micButton, sendButton);

        micButton.addEventListener('click', () => this.toggleRecording());
    }

    async toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000
                }
            });

            const options = {
                mimeType: 'audio/webm;codecs=opus',
                audioBitsPerSecond: 32000
            };
            this.mediaRecorder = new MediaRecorder(stream, options);
            this.audioChunks = [];
            this.silenceTimeout = null;
            this.silenceStart = null;

            const audioContext = new AudioContext();
            const source = audioContext.createMediaStreamSource(stream);
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048;
            source.connect(analyser);

            const bufferLength = analyser.fftSize;
            const dataArray = new Uint8Array(bufferLength);

            const detectSilence = () => {
                if (!this.isRecording) return;

                analyser.getByteTimeDomainData(dataArray);

                let sum = 0;
                for (let i = 0; i < bufferLength; i++) {
                    const normalized = (dataArray[i] - 128) / 128;
                    sum += normalized * normalized;
                }
                const rms = Math.sqrt(sum / bufferLength);
                const volume = rms * 100;

                const silenceThreshold = 2.0;
                const silenceDuration = 1200;

                if (volume < silenceThreshold) {
                    if (!this.silenceStart) {
                        this.silenceStart = Date.now();
                    } else if (Date.now() - this.silenceStart > silenceDuration) {
                        console.log('Silenzio rilevato, stop registrazione');
                        this.stopRecording();
                        audioContext.close();
                        return;
                    }
                } else {
                    this.silenceStart = null;
                }

                requestAnimationFrame(detectSilence);
            };

            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm;codecs=opus' });
                await this.transcribeAudio(audioBlob);

                stream.getTracks().forEach(track => track.stop());
                if (audioContext.state !== 'closed') {
                    audioContext.close();
                }
            };

            this.mediaRecorder.start();
            this.isRecording = true;

            const micButton = document.getElementById('mic-button');
            micButton.classList.add('recording');
            micButton.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="red">
                    <circle cx="12" cy="12" r="8"></circle>
                </svg>
            `;

            detectSilence();

            setTimeout(() => {
                if (this.isRecording) this.stopRecording();
            }, 30000);

        } catch (error) {
            console.error('Errore accesso microfono:', error);
            this.showError('Impossibile accedere al microfono. Verifica i permessi del browser.');
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;

            const micButton = document.getElementById('mic-button');
            micButton.classList.remove('recording');
            micButton.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                    <line x1="12" y1="19" x2="12" y2="23"></line>
                    <line x1="8" y1="23" x2="16" y2="23"></line>
                </svg>
            `;
        }
    }

    async transcribeAudio(audioBlob) {
        this.showTypingIndicator('Trascrizione audio in corso...');

        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            formData.append('language', 'it');

            const response = await fetch(window.basePath + '/api/transcribe', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            if (data.text) {
                this.messageInput.value = data.text;
                this.messageInput.focus();
                this.sendButton.disabled = false;

                this.showTranscriptionPreview(data.text);
            } else {
                throw new Error('Nessun testo trascritto');
            }

        } catch (error) {
            console.error('Errore trascrizione:', error);
            this.showError('Errore durante la trascrizione audio. Riprova.');
        } finally {
            this.hideTypingIndicator();
        }
    }

    showTranscriptionPreview(text) {
        const toast = document.createElement('div');
        toast.className = 'transcription-toast';
        toast.innerHTML = `
            <div class="toast-content">
                <strong>Trascritto:</strong>
                <p>${this.escapeHtml(text)}</p>
            </div>
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('show');
        }, 10);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    showError(message) {
        const toast = document.createElement('div');
        toast.className = 'transcription-toast error';
        toast.innerHTML = `
            <div class="toast-content">
                <strong>⚠️ Errore:</strong>
                <p>${this.escapeHtml(message)}</p>
            </div>
        `;
        document.body.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ============= SSE STREAMING METHODS =============

    isStreamingEnabled() {
        // Feature detection: check if streaming is enabled in config
        return typeof window.streamingEnabled === 'undefined' || window.streamingEnabled !== false;
    }

    supportsStreaming() {
        // Check if browser supports ReadableStream (needed for fetch streaming)
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
        if (textSpan) {
            textSpan.textContent = text;
        }
    }

    hideThinkingMessage(div) {
        if (div && div.parentNode) {
            div.classList.add('fade-out');
            setTimeout(() => {
                if (div.parentNode) {
                    div.parentNode.removeChild(div);
                }
            }, 300);
        }
    }

    async sendMessageStreaming() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        this.addUserMessage(message);
        this.messageInput.value = '';
        this.sendButton.disabled = true;

        // Create and show thinking message
        const thinkingDiv = this.createThinkingMessage();
        this.chatMessages.appendChild(thinkingDiv);
        this.scrollToBottom();

        try {
            await this.connectSSE(message, thinkingDiv);
        } catch (error) {
            console.error('Streaming error:', error);
            this.hideThinkingMessage(thinkingDiv);

            // Fallback to sync endpoint
            console.log('Falling back to synchronous endpoint');
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
                this.addBotMessage('Mi dispiace, non riesco a connettermi al server. Verifica la tua connessione e riprova.');
                console.error('Fallback error:', fallbackError);
            }
        } finally {
            this.sendButton.disabled = false;
        }
    }

    async connectSSE(message, thinkingDiv) {
        const payload = {
            message: message,
            sender: 'user',
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

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalContent = '';
        let finalMetadata = null;

        while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, {stream: true});
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            let eventType = 'status';
            let dataLines = [];

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    // Accumula le linee data (potrebbero essere multi-linea per JSON lunghi)
                    dataLines.push(line.slice(6));
                } else if (line === '') {
                    // Linea vuota = fine evento, processa i dati accumulati
                    if (dataLines.length > 0) {
                        try {
                            // Concatena tutte le linee data con newline (standard SSE)
                            const dataStr = dataLines.join('\n');
                            const data = JSON.parse(dataStr);
                            data.type = eventType; // Set type from event: field
                            this.handleSSEEvent(data, thinkingDiv);

                            if (data.type === 'final') {
                                finalContent = data.content;
                                finalMetadata = data.metadata || {};
                                console.log('[SSE] Received final event, content length:', finalContent.length);
                            }
                        } catch (e) {
                            console.error('Failed to parse SSE data:', e, 'Data lines:', dataLines);
                        }
                        dataLines = [];
                    }
                }
            }
        }

        // Hide thinking and show final response
        this.hideThinkingMessage(thinkingDiv);

        if (finalContent) {
            console.log('[SSE] Showing final message, length:', finalContent.length);
            this.addBotMessage(
                finalContent,
                message,
                finalMetadata.full_data,
                finalMetadata.data_type,
                finalMetadata.suggestions
            );
        } else {
            console.warn('[SSE] No final content received!');
        }
    }

    handleSSEEvent(event, thinkingDiv) {
        switch (event.type) {
            case 'status':
                this.updateThinkingMessage(thinkingDiv, event.message || 'Elaborazione in corso...');
                break;
            case 'reasoning':
                this.updateThinkingMessage(thinkingDiv, `💭 ${event.message}`);
                break;
            case 'token':
                // Token streaming - for now we ignore tokens and just show final
                // Future: could accumulate tokens for progressive display
                break;
            case 'error':
                this.hideThinkingMessage(thinkingDiv);
                this.addBotMessage(`Si è verificato un errore: ${event.error}`);
                break;
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ChatBot();
});