/**
 * Debug Chat Bot per GiAs-llm (LangGraph Architecture)
 *
 * Architettura LLM-based (sostituisce la precedente):
 * - Intent classification via LLM Router invece di Rasa NLU
 * - Agent execution invece di Rasa Actions
 * - ConversationState invece di Rasa Tracker
 * - Response generation via LLM invece di template
 */

class LangGraphDebugChatBot {
    constructor() {
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.chatMessages = document.getElementById('chatMessages');
        this.typingIndicator = document.getElementById('typingIndicator');

        // Debug panel elements - aggiornati per LangGraph
        this.intentDisplay = document.getElementById('intentDisplay');
        this.entitiesDisplay = document.getElementById('entitiesDisplay');
        this.agentsDisplay = document.getElementById('agentsDisplay');
        this.stateDisplay = document.getElementById('stateDisplay');

        // Sender ID stabile per sessione (necessario per two-phase e memoria conversazionale)
        this.senderId = 'debug_user_' + Date.now();

        this.initializeEventListeners();
        this.setWelcomeTime();
        this.loadInitialState();
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

        this.sendButton.disabled = true;
    }

    setWelcomeTime() {
        const welcomeTimeElement = document.getElementById('welcomeTime');
        if (welcomeTimeElement) {
            welcomeTimeElement.textContent = this.formatTime(new Date());
        }
    }

    formatTime(date) {
        return date.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    }

    async loadInitialState() {
        // Mostra metadata iniziale nella sezione state
        if (window.queryParams) {
            this.updateStateDisplay({
                metadata: {
                    asl: window.queryParams.asl_name,
                    asl_id: window.queryParams.asl_id,
                    user_id: window.queryParams.user_id,
                    codice_fiscale: window.queryParams.codice_fiscale,
                    username: window.queryParams.username
                }
            });
        }
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        this.addUserMessage(message);
        this.messageInput.value = '';
        this.sendButton.disabled = true;
        this.showTypingIndicator();

        try {
            const response = await this.sendToDebugServer(message);
            this.hideTypingIndicator();

            if (response.status === 'success') {
                this.addBotMessage(response.message);
                this.updateDebugPanels(response);
            } else {
                this.addBotMessage('Mi dispiace, si è verificato un errore. Riprova più tardi.');
                console.error('Server error:', response.error);
            }
        } catch (error) {
            this.hideTypingIndicator();
            this.addBotMessage('Errore di connessione al server.');
            console.error('Network error:', error);
        }
    }

    async sendToDebugServer(message) {
        const payload = {
            message: message,
            sender: this.senderId
        };

        // Add context from query parameters
        if (window.queryParams) {
            if (window.queryParams.asl_name) payload.asl = window.queryParams.asl_name;
            if (window.queryParams.asl_id) payload.asl_id = window.queryParams.asl_id;
            if (window.queryParams.user_id) payload.user_id = window.queryParams.user_id;
            if (window.queryParams.codice_fiscale) payload.codice_fiscale = window.queryParams.codice_fiscale;
            if (window.queryParams.username) payload.username = window.queryParams.username;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 75000);

        try {
            const response = await fetch(window.basePath + '/debug/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: controller.signal
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } finally {
            clearTimeout(timeoutId);
        }
    }

    updateDebugPanels(response) {
        this.updateIntentDisplay(response);
        this.updateEntitiesDisplay(response);
        this.updateAgentsDisplay(response);
        this.updateStateDisplay(response);
    }

    updateIntentDisplay(response) {
        if (response.intent) {
            const intentName = response.intent.name || 'unknown';
            const confidence = (response.confidence * 100).toFixed(1);

            // Mappa intent a descrizioni user-friendly (allineata a VALID_INTENTS in router.py)
            const intentDescriptions = {
                'greet': 'Saluto',
                'goodbye': 'Congedo',
                'ask_help': 'Richiesta aiuto',
                'ask_piano_stabilimenti': 'Richiesta stabilimenti piano',
                'ask_piano_generic': 'Informazioni generiche piano',
                'ask_piano_description': 'Richiesta descrizione piano',
                'ask_piano_statistics': 'Statistiche piano di monitoraggio',
                'search_piani_by_topic': 'Ricerca piani per argomento',
                'ask_priority_establishment': 'Priorità basate su programmazione',
                'ask_risk_based_priority': 'Priorità basate su rischio ML',
                'ask_suggest_controls': 'Suggerimenti controlli',
                'ask_delayed_plans': 'Piani in ritardo',
                'check_if_plan_delayed': 'Verifica ritardo piano specifico',
                'ask_establishment_history': 'Storico controlli stabilimento',
                'ask_top_risk_activities': 'Attività a maggior rischio',
                'analyze_nc_by_category': 'Analisi non conformità per categoria',
                'info_procedure': 'Informazioni procedura operativa (RAG)',
                'confirm_show_details': 'Conferma visualizzazione dettagli',
                'decline_show_details': 'Rifiuto visualizzazione dettagli',
                'fallback': 'Intent non riconosciuto'
            };

            const description = intentDescriptions[intentName] || intentName;

            this.intentDisplay.innerHTML = `
                <div class="intent-display">${intentName}</div>
                <div style="font-size: 0.85em; color: var(--text-muted, #6b7280); margin-top: 4px;">${description}</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${confidence}%"></div>
                </div>
                <div class="confidence-text">
                    Confidence: ${confidence}%
                    <span style="margin-left: 8px; color: var(--text-muted, #9ca3af);">
                        (LLM Router)
                    </span>
                </div>
            `;
        } else {
            this.intentDisplay.innerHTML = '<div class="empty-state">Nessun intent classificato</div>';
        }
    }

    updateEntitiesDisplay(response) {
        if (response.entities && response.entities.length > 0) {
            const entitiesHTML = response.entities.map(entity => `
                <div class="entity-item">
                    <span class="entity-name">${entity.entity}:</span>
                    <span class="entity-value">${entity.value}</span>
                </div>
            `).join('');
            this.entitiesDisplay.innerHTML = entitiesHTML;
        } else {
            this.entitiesDisplay.innerHTML = '<div class="empty-state">Nessuna entity estratta</div>';
        }
    }

    updateAgentsDisplay(response) {
        const categoryColors = {
            'piano': '#3b82f6',
            'search': '#10b981',
            'priority': '#f59e0b',
            'risk': '#ef4444',
            'nc': '#8b5cf6',
            'history': '#06b6d4',
            'conversation': '#6b7280'
        };

        // Mappa tool names dal backend (TOOL_REGISTRY) a agent info
        const pathToAgent = {
            'piano_description_tool': { name: 'Piano Description', category: 'piano' },
            'piano_stabilimenti_tool': { name: 'Piano Stabilimenti', category: 'piano' },
            'piano_generic_tool': { name: 'Piano Generic', category: 'piano' },
            'piano_statistics_tool': { name: 'Piano Statistics', category: 'piano' },
            'search_piani_tool': { name: 'Semantic Search', category: 'search' },
            'priority_establishment_tool': { name: 'Priority Scheduler', category: 'priority' },
            'risk_predictor_tool': { name: 'ML Risk Manager', category: 'risk' },
            'suggest_controls_tool': { name: 'Suggest Controls', category: 'priority' },
            'delayed_plans_tool': { name: 'Delayed Plans', category: 'priority' },
            'check_plan_delayed_tool': { name: 'Check Plan Delayed', category: 'priority' },
            'establishment_history_tool': { name: 'Establishment History', category: 'history' },
            'top_risk_activities_tool': { name: 'Top Risk Activities', category: 'risk' },
            'analyze_nc_tool': { name: 'NC Analysis', category: 'nc' },
            'confirm_details_tool': { name: 'Confirm Details', category: 'conversation' },
            'decline_details_tool': { name: 'Decline Details', category: 'conversation' },
            'greet_tool': { name: 'Greet', category: 'conversation' },
            'goodbye_tool': { name: 'Goodbye', category: 'conversation' },
            'help_tool': { name: 'Help', category: 'conversation' }
        };

        // Mappa intent a tool (allineata a INTENT_TO_TOOL in tool_nodes.py)
        const intentToAgent = {
            'ask_piano_description': { name: 'piano_description_tool', category: 'piano' },
            'ask_piano_stabilimenti': { name: 'piano_stabilimenti_tool', category: 'piano' },
            'ask_piano_generic': { name: 'piano_generic_tool', category: 'piano' },
            'ask_piano_statistics': { name: 'piano_statistics_tool', category: 'piano' },
            'search_piani_by_topic': { name: 'search_piani_tool', category: 'search' },
            'ask_priority_establishment': { name: 'priority_establishment_tool', category: 'priority' },
            'ask_risk_based_priority': { name: 'risk_predictor_tool', category: 'risk' },
            'ask_suggest_controls': { name: 'suggest_controls_tool', category: 'priority' },
            'ask_delayed_plans': { name: 'delayed_plans_tool', category: 'priority' },
            'check_if_plan_delayed': { name: 'check_plan_delayed_tool', category: 'priority' },
            'ask_establishment_history': { name: 'establishment_history_tool', category: 'history' },
            'ask_top_risk_activities': { name: 'top_risk_activities_tool', category: 'risk' },
            'analyze_nc_by_category': { name: 'analyze_nc_tool', category: 'nc' },
            'info_procedure': { name: 'info_procedure_tool', category: 'procedure' },
            'confirm_show_details': { name: 'confirm_details_tool', category: 'conversation' },
            'decline_show_details': { name: 'decline_details_tool', category: 'conversation' }
        };

        const intent = response.intent?.name;
        const executionPath = response.execution_path || [];
        const executedActions = response.executed_actions || [];

        // 1. Try execution_path first (most reliable)
        const agentsFromPath = executionPath
            .filter(node => pathToAgent[node])
            .map(node => pathToAgent[node]);

        // 2. Try executed_actions from tracker
        const agentsFromActions = executedActions
            .filter(action => action !== 'action_listen')
            .map(action => ({ name: action, category: 'priority' }));

        // 3. Fallback to intent mapping
        const agentFromIntent = (intent && intentToAgent[intent]) ? intentToAgent[intent] : null;

        // Choose best source
        let agentsToShow = [];
        if (agentsFromPath.length > 0) {
            agentsToShow = agentsFromPath;
        } else if (agentsFromActions.length > 0) {
            agentsToShow = agentsFromActions;
        } else if (agentFromIntent) {
            agentsToShow = [agentFromIntent];
        }

        if (agentsToShow.length > 0) {
            const agentsHTML = agentsToShow.map(agent => {
                const color = categoryColors[agent.category] || '#6b7280';
                return `
                    <div class="agent-item">
                        <span class="agent-name">${agent.name}</span>
                        <span class="agent-badge" style="background-color: ${color}20; color: ${color};">
                            ${agent.category}
                        </span>
                    </div>
                `;
            }).join('');

            this.agentsDisplay.innerHTML = `
                ${agentsHTML}
                <div style="font-size: 0.75em; color: var(--text-muted, #6b7280); margin-top: 8px;">
                    → Eseguito nel workflow LangGraph
                </div>
            `;
        } else if (['greet', 'goodbye', 'fallback', 'confirm_show_details', 'decline_show_details'].includes(intent)) {
            this.agentsDisplay.innerHTML = `
                <div class="empty-state">Nessun agent eseguito</div>
                <div style="font-size: 0.75em; color: var(--text-muted, #6b7280); margin-top: 8px;">
                    Gestito direttamente dal router
                </div>
            `;
        } else {
            this.agentsDisplay.innerHTML = '<div class="empty-state">Nessun agent eseguito</div>';
        }
    }

    updateStateDisplay(response) {
        const relevantKeys = ['asl', 'asl_id', 'user_id', 'codice_fiscale', 'username'];
        let displayData = [];

        // Metadata from response (ConversationState)
        if (response.metadata) {
            relevantKeys.forEach(key => {
                const value = response.metadata[key];
                if (value !== null && value !== undefined && value !== '') {
                    displayData.push({
                        key: key,
                        value: value,
                        source: 'metadata'
                    });
                }
            });
        }

        // Slots from classification (intent slots)
        if (response.slots) {
            const otherSlots = ['piano_code', 'topic', 'piano_id', 'num_registrazione', 'partita_iva', 'ragione_sociale', 'categoria'];
            otherSlots.forEach(key => {
                const value = response.slots[key];
                if (value !== null && value !== undefined && value !== false) {
                    displayData.push({
                        key: key,
                        value: value,
                        source: 'slot'
                    });
                }
            });
        }

        if (displayData.length > 0) {
            const stateHTML = displayData.map(item => {
                const sourceLabel = item.source === 'metadata' ? 'context' : 'extracted';
                return `
                    <div class="slot-item">
                        <span class="slot-name">${item.key}:</span>
                        <span class="slot-value">${this.formatSlotValue(item.value)}</span>
                        <span class="slot-source">(${sourceLabel})</span>
                    </div>
                `;
            }).join('');

            this.stateDisplay.innerHTML = `
                ${stateHTML}
                <div style="font-size: 0.75em; color: var(--text-muted, #6b7280); margin-top: 12px; padding-top: 8px; border-top: 1px solid #e5e7eb;">
                    💡 ConversationState gestito da LangGraph
                </div>
            `;
        } else {
            this.stateDisplay.innerHTML = '<div class="empty-state">Nessun contesto disponibile</div>';
        }
    }

    formatSlotValue(value) {
        if (typeof value === 'object') return JSON.stringify(value);
        if (typeof value === 'boolean') return value ? 'true' : 'false';
        return String(value);
    }

    addUserMessage(message) {
        const messageElement = this.createMessageElement(message, 'user-message');
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addBotMessage(message) {
        const messageElement = this.createMessageElement(message, 'bot-message');
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    createMessageElement(message, className) {
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

        return messageDiv;
    }

    formatMessage(message) {
        let formatted = message
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Format headers
        formatted = formatted.replace(/^([A-Za-z\s]+:)\s*(.*)$/gm, (match, header, value) => {
            if (value.trim()) {
                return `<div class="description-field"><span class="field-label"><strong>${header}</strong></span><span class="field-value">${value}</span></div>`;
            }
            return `<div class="section-header"><strong>${header}</strong></div>`;
        });

        // Format bold
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // Format line breaks
        formatted = formatted.replace(/\n\n/g, '<div class="section-break"></div>');
        formatted = formatted.replace(/\n/g, '<br>');

        return formatted;
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

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    new LangGraphDebugChatBot();
});
