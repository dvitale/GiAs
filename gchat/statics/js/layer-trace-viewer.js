/**
 * Layer Trace Viewer - Real-time Layered Architecture Visualization
 *
 * Visualizza il flusso attraverso i 4 layer dell'architettura:
 * - Layer 1: NLU (LLM Router)
 * - Layer 1.5: Orchestrator (Dispatcher)
 * - Layer 2: Domain Agents
 * - Layer 3: Response Generation
 */

class LayerTraceViewer {
    constructor() {
        this.currentTrace = null;
        this.traceHistory = [];
        this.maxHistory = 10;

        this.domainColors = {
            'piano': '#667eea',
            'priority': '#f59e0b',
            'comparison': '#10b981',
            'details': '#ec4899',
            'system': '#6366f1',
            'unknown': '#9ca3af'
        };
    }

    /**
     * Inizializza il trace con i dati del messaggio
     */
    startTrace(message) {
        this.currentTrace = {
            timestamp: new Date(),
            message: message,
            layers: {
                nlu: { status: 'processing', data: null },
                orchestrator: { status: 'pending', data: null },
                domain_agent: { status: 'pending', data: null },
                response: { status: 'pending', data: null }
            }
        };

        this.updateLayerStatus('nlu', 'processing');
        this.renderArchitectureDiagram();
    }

    /**
     * Aggiorna dati Layer 1 (NLU)
     */
    updateNLULayer(intentData) {
        if (!this.currentTrace) return;

        this.currentTrace.layers.nlu = {
            status: 'completed',
            data: {
                intent: intentData.name,
                confidence: intentData.confidence,
                entities: intentData.entities || []
            }
        };

        this.updateLayerStatus('nlu', 'completed');
        this.updateLayerStatus('orchestrator', 'processing');
        this.renderNLUDetails(intentData);
    }

    /**
     * Aggiorna dati Layer 1.5 (Orchestrator)
     */
    updateOrchestratorLayer(orchestratorData) {
        if (!this.currentTrace) return;

        this.currentTrace.layers.orchestrator = {
            status: 'completed',
            data: {
                intent: orchestratorData.intent,
                domain: orchestratorData.domain,
                agent: orchestratorData.agent,
                routing_time: orchestratorData.routing_time || 0
            }
        };

        this.updateLayerStatus('orchestrator', 'completed');
        this.updateLayerStatus('domain_agent', 'processing');
        this.renderOrchestratorDetails(orchestratorData);
    }

    /**
     * Aggiorna dati Layer 2 (Domain Agent)
     */
    updateDomainAgentLayer(agentData) {
        if (!this.currentTrace) return;

        this.currentTrace.layers.domain_agent = {
            status: 'completed',
            data: {
                agent: agentData.agent,
                operation: agentData.operation,
                data_retrieved: agentData.data_retrieved || {},
                processing_time: agentData.processing_time || 0
            }
        };

        this.updateLayerStatus('domain_agent', 'completed');
        this.updateLayerStatus('response', 'processing');
        this.renderDomainAgentDetails(agentData);
    }

    /**
     * Aggiorna dati Layer 3 (Response)
     */
    updateResponseLayer(responseData) {
        if (!this.currentTrace) return;

        this.currentTrace.layers.response = {
            status: 'completed',
            data: {
                formatted_text: responseData.text,
                suggestions: responseData.suggestions || [],
                generation_time: responseData.generation_time || 0
            }
        };

        this.updateLayerStatus('response', 'completed');
        this.renderResponseDetails(responseData);

        // Salva trace completo nella history
        this.saveToHistory();
    }

    /**
     * Aggiorna stato visuale layer
     */
    updateLayerStatus(layerName, status) {
        const layerElement = document.getElementById(`layer-${layerName}`);
        if (!layerElement) return;

        layerElement.classList.remove('pending', 'processing', 'completed', 'error');
        layerElement.classList.add(status);

        // Animazione pulse per processing
        if (status === 'processing') {
            layerElement.classList.add('pulse');
        } else {
            layerElement.classList.remove('pulse');
        }
    }

    /**
     * Renderizza diagramma architettura
     */
    renderArchitectureDiagram() {
        const container = document.getElementById('architectureDiagram');
        if (!container) return;

        container.innerHTML = `
            <div class="layer-diagram">
                <div class="layer-box" id="layer-nlu" data-layer="nlu">
                    <div class="layer-header">
                        <span class="layer-icon">🧠</span>
                        <span class="layer-name">Layer 1: NLU</span>
                    </div>
                    <div class="layer-subtitle">LLM Intent Recognition</div>
                    <div class="layer-details" id="nlu-details"></div>
                </div>

                <div class="layer-arrow">↓</div>

                <div class="layer-box" id="layer-orchestrator" data-layer="orchestrator">
                    <div class="layer-header">
                        <span class="layer-icon">🎯</span>
                        <span class="layer-name">Layer 1.5: Orchestrator</span>
                    </div>
                    <div class="layer-subtitle">Agent Dispatcher</div>
                    <div class="layer-details" id="orchestrator-details"></div>
                </div>

                <div class="layer-arrow">↓</div>

                <div class="layer-box" id="layer-domain_agent" data-layer="domain_agent">
                    <div class="layer-header">
                        <span class="layer-icon">⚙️</span>
                        <span class="layer-name">Layer 2: Domain Agent</span>
                    </div>
                    <div class="layer-subtitle">Specialized Business Logic</div>
                    <div class="layer-details" id="domain-agent-details"></div>
                </div>

                <div class="layer-arrow">↓</div>

                <div class="layer-box" id="layer-response" data-layer="response">
                    <div class="layer-header">
                        <span class="layer-icon">💬</span>
                        <span class="layer-name">Layer 3: Response</span>
                    </div>
                    <div class="layer-subtitle">Template Formatting</div>
                    <div class="layer-details" id="response-details"></div>
                </div>
            </div>
        `;
    }

    /**
     * Renderizza dettagli NLU
     */
    renderNLUDetails(intentData) {
        const container = document.getElementById('nlu-details');
        if (!container) return;

        const confidencePercent = Math.round(intentData.confidence * 100);

        container.innerHTML = `
            <div class="detail-item">
                <span class="detail-label">Intent:</span>
                <span class="detail-value intent-badge">${intentData.name}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Confidence:</span>
                <div class="confidence-bar-mini">
                    <div class="confidence-fill" style="width: ${confidencePercent}%"></div>
                </div>
                <span class="detail-value">${confidencePercent}%</span>
            </div>
            ${intentData.entities && intentData.entities.length > 0 ? `
                <div class="detail-item">
                    <span class="detail-label">Entities:</span>
                    <div class="entity-list">
                        ${intentData.entities.map(e => `
                            <span class="entity-chip">${e.entity}: <strong>${e.value}</strong></span>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
        `;
    }

    /**
     * Renderizza dettagli Orchestrator
     */
    renderOrchestratorDetails(orchestratorData) {
        const container = document.getElementById('orchestrator-details');
        if (!container) return;

        const domainColor = this.domainColors[orchestratorData.domain] || this.domainColors.unknown;

        container.innerHTML = `
            <div class="detail-item">
                <span class="detail-label">Domain:</span>
                <span class="detail-value domain-badge" style="background-color: ${domainColor}20; color: ${domainColor}; border: 1px solid ${domainColor}">
                    ${orchestratorData.domain.toUpperCase()}
                </span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Agent Selected:</span>
                <span class="detail-value">${orchestratorData.agent}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Routing Time:</span>
                <span class="detail-value">${orchestratorData.routing_time}ms</span>
            </div>
        `;
    }

    /**
     * Renderizza dettagli Domain Agent
     */
    renderDomainAgentDetails(agentData) {
        const container = document.getElementById('domain-agent-details');
        if (!container) return;

        container.innerHTML = `
            <div class="detail-item">
                <span class="detail-label">Agent:</span>
                <span class="detail-value">${agentData.agent}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Operation:</span>
                <span class="detail-value operation-badge">${agentData.operation}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Data Retrieved:</span>
                <div class="data-stats">
                    ${Object.entries(agentData.data_retrieved || {}).map(([key, value]) => `
                        <div class="stat-item">
                            <span class="stat-key">${key}:</span>
                            <span class="stat-value">${value}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="detail-item">
                <span class="detail-label">Processing Time:</span>
                <span class="detail-value">${agentData.processing_time}ms</span>
            </div>
        `;
    }

    /**
     * Renderizza dettagli Response
     */
    renderResponseDetails(responseData) {
        const container = document.getElementById('response-details');
        if (!container) return;

        const textPreview = responseData.text.substring(0, 100) + '...';

        container.innerHTML = `
            <div class="detail-item">
                <span class="detail-label">Text Preview:</span>
                <div class="text-preview">${textPreview}</div>
            </div>
            <div class="detail-item">
                <span class="detail-label">Suggestions:</span>
                <span class="detail-value">${responseData.suggestions.length} generated</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Generation Time:</span>
                <span class="detail-value">${responseData.generation_time}ms</span>
            </div>
        `;
    }

    /**
     * Salva trace completo nella history
     */
    saveToHistory() {
        if (!this.currentTrace) return;

        this.traceHistory.unshift(this.currentTrace);

        if (this.traceHistory.length > this.maxHistory) {
            this.traceHistory = this.traceHistory.slice(0, this.maxHistory);
        }

        this.renderTraceHistory();
    }

    /**
     * Renderizza storico trace
     */
    renderTraceHistory() {
        const container = document.getElementById('traceHistory');
        if (!container) return;

        if (this.traceHistory.length === 0) {
            container.innerHTML = '<div class="empty-state">Nessun trace disponibile</div>';
            return;
        }

        container.innerHTML = this.traceHistory.map((trace, index) => `
            <div class="trace-item" data-index="${index}">
                <div class="trace-header">
                    <span class="trace-time">${this.formatTime(trace.timestamp)}</span>
                    <span class="trace-message">${trace.message.substring(0, 50)}...</span>
                </div>
                <div class="trace-flow">
                    ${this.renderMiniFlow(trace)}
                </div>
            </div>
        `).join('');
    }

    /**
     * Renderizza mini flow per history item
     */
    renderMiniFlow(trace) {
        return Object.keys(trace.layers).map(layerName => {
            const layer = trace.layers[layerName];
            let icon = '○';
            if (layer.status === 'completed') icon = '✓';
            else if (layer.status === 'error') icon = '✗';

            return `<span class="mini-layer ${layer.status}">${icon}</span>`;
        }).join('→');
    }

    /**
     * Formatta timestamp
     */
    formatTime(date) {
        return date.toLocaleTimeString('it-IT', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    /**
     * Simula trace da response LLM server (parsing euristic)
     */
    simulateTraceFromResponse(message, response) {
        this.startTrace(message);

        // Simula NLU layer
        setTimeout(() => {
            this.updateNLULayer({
                name: this.inferIntent(message),
                confidence: 0.95,
                entities: this.extractEntities(message)
            });
        }, 100);

        // Simula Orchestrator layer
        setTimeout(() => {
            const domain = this.inferDomain(message);
            this.updateOrchestratorLayer({
                intent: this.inferIntent(message),
                domain: domain,
                agent: this.getAgentForDomain(domain),
                routing_time: Math.floor(Math.random() * 10) + 5
            });
        }, 300);

        // Simula Domain Agent layer
        setTimeout(() => {
            this.updateDomainAgentLayer({
                agent: this.getAgentForDomain(this.inferDomain(message)),
                operation: this.inferOperation(message),
                data_retrieved: {
                    'records': Math.floor(Math.random() * 100),
                    'datasets': Math.floor(Math.random() * 3) + 1
                },
                processing_time: Math.floor(Math.random() * 50) + 20
            });
        }, 500);

        // Simula Response layer
        setTimeout(() => {
            this.updateResponseLayer({
                text: response,
                suggestions: [],
                generation_time: Math.floor(Math.random() * 20) + 10
            });
        }, 700);
    }

    /**
     * Inferisce intent da messaggio (euristic)
     */
    inferIntent(message) {
        const msg = message.toLowerCase();
        if (msg.includes('piano') && msg.includes('stabilimenti')) return 'ask_piano_stabilimenti';
        if (msg.includes('piano') && msg.includes('attività')) return 'ask_piano_attivita';
        if (msg.includes('piano') && msg.includes('tratta')) return 'ask_piano_description';
        if (msg.includes('controllare') && msg.includes('primo')) return 'ask_priority_establishment';
        if (msg.includes('rischio')) return 'ask_risk_based_priority';
        if (msg.includes('piani') && msg.includes('ritardo')) return 'ask_delayed_plans';
        if (msg.includes('confronta')) return 'compare_plans';
        if (msg.includes('aiuto') || msg.includes('help')) return 'ask_help';
        return 'unknown';
    }

    /**
     * Inferisce dominio da messaggio o intent
     */
    inferDomain(messageOrIntent) {
        // Se è già un intent name, usalo direttamente
        let intent = messageOrIntent;

        // Altrimenti, inferisci l'intent dal messaggio
        if (!messageOrIntent.startsWith('ask_') && !messageOrIntent.startsWith('compare') &&
            !messageOrIntent.startsWith('greet') && !messageOrIntent.startsWith('goodbye') &&
            !messageOrIntent.startsWith('search_') && !messageOrIntent.startsWith('provide_') &&
            !messageOrIntent.startsWith('activity_') && !messageOrIntent.startsWith('show_') &&
            !messageOrIntent.startsWith('specific_') && !messageOrIntent.startsWith('export_') &&
            !messageOrIntent.startsWith('bot_') && !messageOrIntent.startsWith('projections')) {
            intent = this.inferIntent(messageOrIntent);
        }

        // Piano domain
        if (intent.startsWith('ask_piano') || intent.startsWith('search_piani')) return 'piano';

        // Priority domain
        if (intent.startsWith('ask_priority') || intent.startsWith('ask_risk') ||
            intent.startsWith('ask_delayed') || intent.startsWith('ask_suggest')) return 'priority';

        // Comparison domain
        if (intent.startsWith('compare') || intent.includes('temporal')) return 'comparison';

        // Details domain
        if (intent.startsWith('provide_') || intent.startsWith('activity_') ||
            intent.startsWith('show_') || intent.startsWith('specific_') ||
            intent.startsWith('export_') || intent.startsWith('projections')) return 'details';

        // System domain
        if (intent === 'greet' || intent === 'goodbye' || intent === 'ask_help' ||
            intent.startsWith('bot_')) return 'system';

        return 'unknown';
    }

    /**
     * Ottiene agent per dominio
     */
    getAgentForDomain(domain) {
        const agentMap = {
            'piano': 'PianoAgent',
            'priority': 'PriorityAgent',
            'comparison': 'ComparisonAgent',
            'details': 'DetailsAgent',
            'system': 'SystemAgent'
        };
        return agentMap[domain] || 'UnknownAgent';
    }

    /**
     * Inferisce operazione da messaggio
     */
    inferOperation(message) {
        const msg = message.toLowerCase();
        if (msg.includes('stabilimenti')) return 'get_stabilimenti';
        if (msg.includes('attività')) return 'get_piano_attivita';
        if (msg.includes('tratta')) return 'get_description';
        if (msg.includes('primo') && msg.includes('controllare')) return 'find_priority_establishments';
        if (msg.includes('rischio')) return 'analyze_risk';
        if (msg.includes('ritardo')) return 'find_delayed_plans';
        return 'execute';
    }

    /**
     * Estrae entities da messaggio (euristic)
     */
    extractEntities(message) {
        const entities = [];
        const pianoMatch = message.match(/piano\s+([A-Z0-9_]+)/i);
        if (pianoMatch) {
            entities.push({
                entity: 'piano_id',
                value: pianoMatch[1].toUpperCase()
            });
        }
        return entities;
    }
}

// Export globale
window.LayerTraceViewer = LayerTraceViewer;
