/**
 * GIAS LangGraph Debug Visualizer
 * Interactive SVG-based workflow visualization with real-time execution tracking
 *
 * Graph architecture matches actual graph.py _build_graph():
 * classify -> dialogue_manager -> {ask_user | fallback_tool | tool_node} -> response_generator -> END
 */

class LangGraphDebugVisualizer {
    constructor() {
        this.initializeElements();
        this.initializeGraph();
        this.initializeEventListeners();
        this.initializeTabs();
        // Don't overwrite HTML content - let it show initially
        // this.loadInitialContent();
        this.currentExecution = null;
        this.executionHistory = [];
        this.selectedNode = null;
        // Sender ID stabile per sessione (necessario per two-phase e memoria conversazionale)
        this.senderId = 'debug_visualizer_' + Date.now();
        // Query history for quick re-execution
        this.queryHistory = [];
        this.lastQuery = '';
        this.lastResponse = null;
    }

    initializeElements() {
        // Main elements
        this.graphSvg = document.getElementById('graphSvg');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.loadingOverlay = document.getElementById('loadingOverlay');

        // Panel elements
        this.executionPanel = document.getElementById('executionPanel');
        this.nodesPanel = document.getElementById('nodesPanel');
        this.metricsPanel = document.getElementById('metricsPanel');

        // Content areas
        this.executionSteps = document.getElementById('executionSteps');
        this.nodeDetails = document.getElementById('nodeDetails');
        this.detailedMetrics = document.getElementById('detailedMetrics');

        // Metrics display
        this.totalExecutionTime = document.getElementById('totalExecutionTime');
        this.nodesExecuted = document.getElementById('nodesExecuted');
        this.confidence = document.getElementById('confidence');
        this.entitiesFound = document.getElementById('entitiesFound');

        // Execution status (bottom-right area for response display)
        this.executionStatus = document.getElementById('executionStatus');

        // Tab system
        this.panelTabs = document.querySelectorAll('.panel-tab');
        this.tabPanels = document.querySelectorAll('.tab-panel');
    }

    initializeGraph() {
        // Node structure matching actual graph.py _build_graph()
        // Real flow: classify -> dialogue_manager -> {ask_user | fallback_tool | tool_node} -> response_generator -> END
        this.nodes = {
            input: {
                id: 'input', type: 'input', label: 'User Query',
                x: 180, y: 10, radius: 32,
                description: 'Natural language query entry point',
                icon: '\u{1F4AC}'
            },
            classify: {
                id: 'classify', type: 'router', label: 'Classify (Router)',
                x: 280, y: 10, radius: 38,
                description: 'Hybrid 4-level router: heuristics \u2192 pre-parsing \u2192 cache \u2192 LLM',
                icon: '\u{1F3AF}'
            },
            dialogue_manager: {
                id: 'dialogue_manager', type: 'state', label: 'Dialogue Manager',
                x: 280, y: 175, radius: 36,
                description: 'Rule-based decision engine: tool, chiarimenti, o fallback',
                icon: '\u{1F500}'
            },
            ask_user: {
                id: 'ask_user', type: 'response', label: 'Ask User',
                x: 30, y: 270, radius: 30,
                description: 'Chiede chiarimenti (slot mancanti, ambiguit\u00E0) \u2192 END',
                icon: '\u{2753}'
            },
            fallback_tool: {
                id: 'fallback_tool', type: 'response', label: 'Fallback',
                x: 140, y: 270, radius: 30,
                description: 'Recovery a 3 fasi: keyword \u2192 LLM \u2192 menu categorie',
                icon: '\u{1F504}'
            },
            piano_tools: {
                id: 'piano_tools', type: 'agent', label: 'Piano Tools',
                x: 250, y: 270, radius: 38,
                description: 'Piano description, stabilimenti, generic, statistics (4 tool)',
                icon: '\u{1F4CB}'
            },
            search_tool: {
                id: 'search_tool', type: 'agent', label: 'Semantic Search',
                x: 370, y: 270, radius: 38,
                description: 'Ricerca semantica vettoriale su piani di monitoraggio',
                icon: '\u{1F50D}'
            },
            priority_tools: {
                id: 'priority_tools', type: 'agent', label: 'Priority & Controls',
                x: 490, y: 270, radius: 38,
                description: 'Priority, delayed plans, suggest controls, history (5 tool)',
                icon: '\u{1F4C5}'
            },
            ml_risk_manager: {
                id: 'ml_risk_manager', type: 'ml', label: 'ML Risk Manager',
                x: 600, y: 240, radius: 48,
                description: 'ML risk prediction + analisi NC per categoria (XGBoost v4)',
                icon: '\u{1F9E0}'
            },
            response_generator: {
                id: 'response_generator', type: 'response', label: 'Response Generator',
                x: 370, y: 390, radius: 40,
                description: 'LLM response formatting con two-phase (sommario + dettagli)',
                icon: '\u{1F916}'
            }
        };

        // Connections matching actual graph.py edges
        this.connections = [
            { from: 'input', to: 'classify', type: 'main' },
            { from: 'classify', to: 'dialogue_manager', type: 'main' },
            // dialogue_manager conditional edges
            { from: 'dialogue_manager', to: 'ask_user', type: 'route' },
            { from: 'dialogue_manager', to: 'fallback_tool', type: 'route' },
            { from: 'dialogue_manager', to: 'piano_tools', type: 'route' },
            { from: 'dialogue_manager', to: 'search_tool', type: 'route' },
            { from: 'dialogue_manager', to: 'priority_tools', type: 'route' },
            { from: 'dialogue_manager', to: 'ml_risk_manager', type: 'route-ml' },
            // ask_user -> END (no further connection)
            // fallback_tool + tools -> response_generator
            { from: 'fallback_tool', to: 'response_generator', type: 'output' },
            { from: 'piano_tools', to: 'response_generator', type: 'output' },
            { from: 'search_tool', to: 'response_generator', type: 'output' },
            { from: 'priority_tools', to: 'response_generator', type: 'output' },
            { from: 'ml_risk_manager', to: 'response_generator', type: 'output-ml' }
        ];

        // Map backend tool names (TOOL_REGISTRY) to visualization node groups
        this.toolToVisualNode = {
            'piano_description_tool': 'piano_tools',
            'piano_stabilimenti_tool': 'piano_tools',
            'piano_generic_tool': 'piano_tools',
            'piano_statistics_tool': 'piano_tools',
            'search_piani_tool': 'search_tool',
            'priority_establishment_tool': 'priority_tools',
            'suggest_controls_tool': 'priority_tools',
            'delayed_plans_tool': 'priority_tools',
            'check_plan_delayed_tool': 'priority_tools',
            'establishment_history_tool': 'priority_tools',
            'risk_predictor_tool': 'ml_risk_manager',
            'top_risk_activities_tool': 'ml_risk_manager',
            'analyze_nc_tool': 'ml_risk_manager',
            'greet_tool': null,
            'goodbye_tool': null,
            'help_tool': null,
            'confirm_details_tool': null,
            'decline_details_tool': null
        };

        // Map INTENT_TO_TOOL for fallback path resolution
        this.intentToTool = {
            'ask_piano_description': 'piano_description_tool',
            'ask_piano_stabilimenti': 'piano_stabilimenti_tool',
            'ask_piano_generic': 'piano_generic_tool',
            'ask_piano_statistics': 'piano_statistics_tool',
            'search_piani_by_topic': 'search_piani_tool',
            'ask_priority_establishment': 'priority_establishment_tool',
            'ask_risk_based_priority': 'risk_predictor_tool',
            'ask_suggest_controls': 'suggest_controls_tool',
            'ask_delayed_plans': 'delayed_plans_tool',
            'check_if_plan_delayed': 'check_plan_delayed_tool',
            'ask_establishment_history': 'establishment_history_tool',
            'ask_top_risk_activities': 'top_risk_activities_tool',
            'analyze_nc_by_category': 'analyze_nc_tool',
            'info_procedure': 'info_procedure_tool',
            'confirm_show_details': 'confirm_details_tool',
            'decline_show_details': 'decline_details_tool',
            'greet': 'greet_tool',
            'goodbye': 'goodbye_tool',
            'ask_help': 'help_tool'
        };

        this.renderGraph();
    }

    renderGraph() {
        // Clear existing content (keep defs)
        const existingElements = this.graphSvg.querySelectorAll('g, path, circle, text');
        existingElements.forEach(el => el.remove());

        // Create container group
        const container = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        container.setAttribute('id', 'graph-container');
        container.setAttribute('transform', 'translate(50, 50)');

        // Render connections first (so they appear under nodes)
        this.renderConnections(container);

        // Render nodes
        this.renderNodes(container);

        this.graphSvg.appendChild(container);
    }

    renderConnections(container) {
        this.connections.forEach(conn => {
            const fromNode = this.nodes[conn.from];
            const toNode = this.nodes[conn.to];

            if (!fromNode || !toNode) return;

            const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');

            // Calculate center positions based on node radius
            const fromRadius = fromNode.radius || 35;
            const toRadius = toNode.radius || 35;

            const startX = fromNode.x + fromRadius;
            const startY = fromNode.y + fromRadius;
            const endX = toNode.x + toRadius;
            const endY = toNode.y + toRadius;

            const controlX1 = startX;
            const controlY1 = startY + (endY - startY) * 0.5;
            const controlX2 = endX;
            const controlY2 = startY + (endY - startY) * 0.5;

            const pathData = `M ${startX} ${startY} C ${controlX1} ${controlY1} ${controlX2} ${controlY2} ${endX} ${endY}`;

            line.setAttribute('d', pathData);

            // Style based on connection type
            let lineClass = 'connection-line';
            if (conn.type === 'route-ml' || conn.type === 'output-ml') {
                lineClass += ' connection-ml';
            } else if (conn.type === 'state') {
                lineClass += ' connection-state';
            }
            line.setAttribute('class', lineClass);
            line.setAttribute('id', `connection-${conn.from}-${conn.to}`);
            line.setAttribute('data-from', conn.from);
            line.setAttribute('data-to', conn.to);

            container.appendChild(line);
        });
    }

    renderNodes(container) {
        // Create separate groups for nodes and labels to ensure labels are always on top
        const nodesLayer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        nodesLayer.setAttribute('id', 'nodes-layer');

        const labelsLayer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        labelsLayer.setAttribute('id', 'labels-layer');

        Object.values(this.nodes).forEach(node => {
            const nodeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            nodeGroup.setAttribute('class', `graph-node node-${node.type}`);
            nodeGroup.setAttribute('id', `node-${node.id}`);
            nodeGroup.setAttribute('data-node-id', node.id);
            nodeGroup.setAttribute('transform', `translate(${node.x}, ${node.y})`);

            const radius = node.radius || 35;
            const centerX = radius;
            const centerY = radius;

            // ML node has larger radius, no glow effect for cleaner appearance

            // Node circle
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', centerX);
            circle.setAttribute('cy', centerY);
            circle.setAttribute('r', radius);
            circle.setAttribute('class', `node-circle ${node.type}`);

            // Set gradient fill based on node type
            switch(node.type) {
                case 'input':
                    circle.setAttribute('fill', 'url(#inputGradient)');
                    break;
                case 'router':
                    circle.setAttribute('fill', 'url(#routerGradient)');
                    break;
                case 'agent':
                    circle.setAttribute('fill', 'url(#agentGradient)');
                    break;
                case 'ml':
                    circle.setAttribute('fill', 'url(#mlGradient)');
                    break;
                case 'response':
                    circle.setAttribute('fill', 'url(#responseGradient)');
                    break;
                case 'state':
                    circle.setAttribute('fill', 'url(#stateGradient)');
                    break;
                default:
                    circle.setAttribute('fill', '#6b7280');
            }

            // Node icon (centered in circle)
            const icon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            icon.setAttribute('x', centerX);
            icon.setAttribute('y', centerY + 4);
            icon.setAttribute('class', 'node-text');
            const iconSize = Math.round(radius * 0.6);
            icon.setAttribute('font-size', iconSize);
            icon.textContent = node.icon;

            // Add circle and icon to nodes layer
            nodeGroup.appendChild(circle);
            nodeGroup.appendChild(icon);

            // Add click handler
            nodeGroup.addEventListener('click', (e) => {
                this.selectNode(node.id);
            });

            // Add hover handlers
            nodeGroup.addEventListener('mouseenter', (e) => {
                this.showTooltip(e, node);
            });

            nodeGroup.addEventListener('mouseleave', (e) => {
                this.hideTooltip();
            });

            nodesLayer.appendChild(nodeGroup);

            // Create label group (will be added to labels layer)
            const labelGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            labelGroup.setAttribute('class', 'node-label-group');
            labelGroup.setAttribute('transform', `translate(${node.x}, ${node.y})`);
            labelGroup.setAttribute('pointer-events', 'none'); // Labels don't block clicks

            // Node name below circle with background rectangle for better readability
            const fontSize = node.type === 'ml' ? 13 : 11;
            const labelY = centerY + radius + 16;

            // Estimate text width (rough approximation: char count * font size * 0.6)
            const estimatedWidth = node.label.length * fontSize * 0.6;
            const padding = 6;

            // Create background rectangle
            const labelBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            labelBg.setAttribute('x', centerX - estimatedWidth / 2 - padding);
            labelBg.setAttribute('y', labelY - fontSize + 2);
            labelBg.setAttribute('width', estimatedWidth + padding * 2);
            labelBg.setAttribute('height', fontSize + padding);
            labelBg.setAttribute('rx', 4); // Rounded corners
            labelBg.setAttribute('fill', '#1e293b'); // Dark background
            labelBg.setAttribute('opacity', '0.9'); // Increased opacity for better visibility

            // Create the text
            const name = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            name.setAttribute('x', centerX);
            name.setAttribute('y', labelY);
            name.setAttribute('class', `node-text node-label-outer ${node.type === 'ml' ? 'ml-label' : ''}`);
            name.setAttribute('font-size', fontSize);
            name.setAttribute('fill', node.type === 'ml' ? '#f9a8d4' : '#e2e8f0');
            name.setAttribute('font-weight', node.type === 'ml' ? '700' : '600');
            name.textContent = node.label;

            labelGroup.appendChild(labelBg);
            labelGroup.appendChild(name);
            labelsLayer.appendChild(labelGroup);
        });

        // Add layers to container in order: nodes first, then labels on top
        container.appendChild(nodesLayer);
        container.appendChild(labelsLayer);
    }

    initializeEventListeners() {
        this.messageInput.addEventListener('input', () => {
            this.sendButton.disabled = this.messageInput.value.trim() === '';
        });

        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !this.sendButton.disabled) {
                e.preventDefault();
                this.executeWorkflow();
            }
        });

        this.sendButton.addEventListener('click', () => {
            this.executeWorkflow();
        });

        this.sendButton.disabled = true;

        // Quick Query Buttons
        document.querySelectorAll('.quick-query-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const query = btn.dataset.query;
                if (query) {
                    this.messageInput.value = query;
                    this.sendButton.disabled = false;
                    this.executeWorkflow();
                }
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl+Enter to execute from anywhere
            if (e.ctrlKey && e.key === 'Enter' && this.messageInput.value.trim()) {
                e.preventDefault();
                this.executeWorkflow();
            }
            // Escape to clear input
            if (e.key === 'Escape') {
                this.messageInput.value = '';
                this.sendButton.disabled = true;
                this.messageInput.focus();
            }
            // 1-6 number keys for quick queries (when not in input)
            if (document.activeElement !== this.messageInput && e.key >= '1' && e.key <= '6') {
                const btns = document.querySelectorAll('.quick-query-btn');
                const idx = parseInt(e.key) - 1;
                if (btns[idx]) {
                    btns[idx].click();
                }
            }
        });
    }

    initializeTabs() {
        this.panelTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
            });
        });
    }

    switchTab(tabName) {
        this.panelTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        this.tabPanels.forEach(panel => {
            if (panel.id === tabName + 'Panel') {
                panel.classList.add('active');
            } else {
                panel.classList.remove('active');
            }
        });
    }

    async executeWorkflow() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        this.clearExecution();
        this.showLoading();
        this.updateExecutionStatus('loading', message);

        this.messageInput.value = '';
        this.sendButton.disabled = true;

        try {
            const response = await this.sendDebugRequest(message);
            this.hideLoading();

            if (response.status === 'success') {
                this.lastResponse = response;  // Save for export/copy
                await this.visualizeExecution(response, message);
                this.updateMetrics(response);
                this.updateExecutionSteps(response, message);  // Update Execution tab
                this.updateExecutionStatus('success', response.message || 'Nessuna risposta');
            } else {
                const errMsg = response.error || 'Unknown error occurred';
                this.showError(errMsg);
                this.updateExecutionStatus('error', errMsg);
            }
        } catch (error) {
            this.hideLoading();
            let errMsg;
            if (error.name === 'AbortError') {
                errMsg = 'Request timeout: il backend non ha risposto entro 75 secondi';
            } else {
                errMsg = 'Network error: ' + error.message;
            }
            this.showError(errMsg);
            this.updateExecutionStatus('error', errMsg);
        }
    }

    async sendDebugRequest(message) {
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

    async visualizeExecution(response, message) {
        this.currentExecution = {
            message: message,
            response: response,
            steps: [],
            startTime: Date.now()
        };

        // Use backend execution_path if available, otherwise derive from intent
        const executionPath = this.determineExecutionPath(response);

        await this.animateExecutionFlow(executionPath, response);

        this.updateExecutionSteps();

        this.executionHistory.unshift(this.currentExecution);
        if (this.executionHistory.length > 10) {
            this.executionHistory.pop();
        }
    }

    determineExecutionPath(response) {
        // Use real execution_path from backend if available
        if (response.execution_path && response.execution_path.length > 0) {
            console.log('[LangGraph] Backend execution_path:', response.execution_path);
            const visualPath = this.mapBackendPathToVisual(response.execution_path);
            console.log('[LangGraph] Mapped visual path:', visualPath);
            return visualPath;
        }

        // Fallback: derive from intent using INTENT_TO_TOOL mapping
        console.log('[LangGraph] Using fallback path derivation for intent:', response.intent?.name);
        const intent = response.intent?.name || 'unknown';
        const path = ['input', 'classify', 'dialogue_manager'];

        const toolName = this.intentToTool[intent];
        if (toolName) {
            const visualNode = this.toolToVisualNode[toolName];
            if (visualNode) {
                path.push(visualNode);
                path.push('response_generator');
            } else {
                // Direct response intents (greet, goodbye, etc.) - tool runs but no visual agent node
                path.push('response_generator');
            }
        } else if (intent === 'fallback') {
            path.push('fallback_tool');
            path.push('response_generator');
        } else {
            path.push('response_generator');
        }

        console.log('[LangGraph] Final path:', path);
        return path;
    }

    mapBackendPathToVisual(backendPath) {
        const visualPath = [];
        const seen = new Set();

        for (const nodeName of backendPath) {
            let visualNode = null;

            // Map backend node names to visual nodes
            if (nodeName === 'input' || nodeName === '__start__') {
                visualNode = 'input';
            } else if (nodeName === 'classify') {
                visualNode = 'classify';
            } else if (nodeName === 'dialogue_manager') {
                visualNode = 'dialogue_manager';
            } else if (nodeName === 'ask_user') {
                visualNode = 'ask_user';
            } else if (nodeName === 'fallback_tool') {
                visualNode = 'fallback_tool';
            } else if (nodeName === 'piano_tools') {
                visualNode = 'piano_tools';
            } else if (nodeName === 'search_tool') {
                visualNode = 'search_tool';
            } else if (nodeName === 'priority_tools') {
                visualNode = 'priority_tools';
            } else if (nodeName === 'ml_risk_manager') {
                visualNode = 'ml_risk_manager';
            } else if (nodeName === 'response_generator') {
                visualNode = 'response_generator';
            } else if (this.toolToVisualNode[nodeName] !== undefined) {
                // Tool node -> map to visual group
                visualNode = this.toolToVisualNode[nodeName];
            }

            if (visualNode && !seen.has(visualNode)) {
                visualPath.push(visualNode);
                seen.add(visualNode);
            }
        }

        return visualPath;
    }

    async animateExecutionFlow(path, response) {
        const stepDelay = 600;
        // Use real node_timings from backend if available
        const nodeTimings = response.node_timings || {};

        for (let i = 0; i < path.length; i++) {
            const nodeId = path[i];
            const prevNodeId = i > 0 ? path[i - 1] : null;

            // Get real duration from backend if available
            const timing = nodeTimings[nodeId] || {};
            const realDuration = timing.duration || null;

            const step = {
                nodeId: nodeId,
                nodeLabel: this.nodes[nodeId]?.label || nodeId,
                startTime: Date.now(),
                status: 'executing'
            };

            this.currentExecution.steps.push(step);

            this.highlightNode(nodeId, 'executing');

            if (prevNodeId) {
                this.highlightConnection(prevNodeId, nodeId, 'active');
            }

            this.updateExecutionSteps();

            await this.sleep(stepDelay);

            step.status = 'completed';
            step.endTime = Date.now();
            // Use real duration from backend, or mark as animation-only
            step.duration = realDuration || null;
            step.durationLabel = realDuration ? `${realDuration}ms` : 'N/A';

            this.addStepData(step, response);

            this.highlightNode(nodeId, 'completed');
            this.updateExecutionSteps();
        }

        this.currentExecution.status = 'completed';
        this.currentExecution.endTime = Date.now();
        this.currentExecution.totalDuration = this.currentExecution.endTime - this.currentExecution.startTime;
    }

    addStepData(step, response) {
        // Estrai slots reali dalla risposta
        const slots = response.slots || {};
        const entities = response.entities || [];
        const intent = response.intent?.name || 'unknown';

        switch (step.nodeId) {
            case 'input':
                step.data = {
                    message: response.original_message || 'User query received',
                    message_length: (response.original_message || '').length
                };
                step.description = `Query: "${(response.original_message || '').substring(0, 50)}${(response.original_message || '').length > 50 ? '...' : ''}"`;
                break;

            case 'classify':
                step.data = {
                    intent: intent,
                    confidence: response.confidence || 0,
                    slots: slots
                };
                const slotKeys = Object.keys(slots).filter(k => slots[k]);
                const slotInfo = slotKeys.length > 0 ? ` | Slots: ${slotKeys.join(', ')}` : '';
                step.description = `Intent: ${intent} (${(response.confidence * 100 || 0).toFixed(1)}%)${slotInfo}`;
                break;

            case 'dialogue_manager':
                step.data = {
                    workflow_state: response.workflow_state || 'completed',
                    action: 'execute',
                    slots_count: Object.keys(slots).filter(k => slots[k]).length
                };
                step.description = `Decision: esegui tool per intent "${intent}"`;
                break;

            case 'ask_user':
                step.data = { reason: 'slot_mancanti' };
                step.description = 'Richiesta chiarimenti: slot mancanti per completare la query';
                break;

            case 'fallback_tool':
                step.data = { phase: 1, recovery_type: 'keyword_match' };
                step.description = 'Recovery fallback: tentativo di recupero query non riconosciuta';
                break;

            case 'piano_tools':
                const pianoCode = slots.piano_code || 'N/A';
                step.data = {
                    piano_code: pianoCode,
                    entities: entities,
                    tool_type: this._inferPianoToolType(intent)
                };
                step.description = `Piano ${pianoCode} - ${this._inferPianoToolType(intent)}`;
                break;

            case 'search_tool':
                const topic = slots.topic || 'N/A';
                step.data = {
                    topic: topic,
                    entities: entities
                };
                step.description = `Ricerca semantica: "${topic}"`;
                break;

            case 'priority_tools':
                step.data = {
                    entities: entities,
                    tool_type: this._inferPriorityToolType(intent)
                };
                step.description = `${this._inferPriorityToolType(intent)}`;
                break;

            case 'ml_risk_manager':
                step.data = {
                    entities: entities,
                    model: 'XGBoost v4',
                    features: ['historical_nc', 'control_patterns', 'temporal_risk'],
                    category: slots.categoria || 'tutte'
                };
                step.description = `\u{1F9E0} ML Risk Analysis - categoria: ${slots.categoria || 'tutte'}`;
                break;

            case 'response_generator':
                step.data = {
                    responseLength: response.message?.length || 0,
                    has_details: response.has_more_details || false
                };
                step.description = `Risposta generata (${response.message?.length || 0} chars)`;
                break;

            default:
                // Tool generico - estrai info dal nome
                step.data = { tool_name: step.nodeId, slots: slots };
                step.description = `Tool: ${step.nodeId}`;
        }
    }

    _inferPianoToolType(intent) {
        if (intent.includes('description')) return 'descrizione piano';
        if (intent.includes('stabilimenti')) return 'stabilimenti associati';
        if (intent.includes('statistics')) return 'statistiche piano';
        if (intent.includes('generic')) return 'info generiche';
        return 'query piano';
    }

    _inferPriorityToolType(intent) {
        if (intent.includes('risk')) return 'Analisi rischio storico';
        if (intent.includes('priority')) return 'Priorità programmazione';
        if (intent.includes('delayed')) return 'Piani in ritardo';
        if (intent.includes('suggest')) return 'Suggerimenti controlli';
        if (intent.includes('history')) return 'Storico stabilimento';
        return 'Analisi priorità';
    }

    highlightNode(nodeId, state) {
        const node = document.getElementById(`node-${nodeId}`);
        if (!node) return;

        node.classList.remove('executing', 'completed', 'active');

        if (state) {
            node.classList.add(state);
        }
    }

    highlightConnection(fromId, toId, state) {
        const connection = document.getElementById(`connection-${fromId}-${toId}`);
        if (!connection) return;

        connection.classList.remove('active', 'completed');

        if (state) {
            connection.classList.add(state);
        }
    }

    selectNode(nodeId) {
        const prevSelected = document.querySelector('.graph-node.selected');
        if (prevSelected) {
            prevSelected.classList.remove('selected');
        }

        const node = document.getElementById(`node-${nodeId}`);
        if (node) {
            node.classList.add('selected');
            this.selectedNode = nodeId;
            this.updateNodeDetails(nodeId);
            this.switchTab('nodes');
        }
    }

    updateNodeDetails(nodeId) {
        const node = this.nodes[nodeId];
        if (!node) return;

        const executionData = this.currentExecution?.steps.find(step => step.nodeId === nodeId);

        const isML = node.type === 'ml';
        const cardClass = isML ? 'node-detail-card ml-featured' : 'node-detail-card';
        const nameStyle = isML ? 'style="color: #f9a8d4;"' : '';
        const typeLabel = this.getNodeTypeLabel(node.type);

        let mlSection = '';
        if (isML && executionData?.data) {
            const category = executionData.data.category || 'tutte';
            mlSection = `
                <div class="node-detail-section">
                    <div class="section-label">ML Features</div>
                    <div class="section-content">
                        <span class="status-badge ml">historical_nc</span>
                        <span class="status-badge ml">control_patterns</span>
                        <span class="status-badge ml">temporal_risk</span>
                    </div>
                </div>
                <div class="node-detail-section">
                    <div class="section-label">Categoria Analisi</div>
                    <div class="section-content" style="color: #f9a8d4; font-weight: 600;">${category}</div>
                </div>
            `;
        } else if (isML) {
            mlSection = `
                <div class="node-detail-section">
                    <div class="section-label">ML Features</div>
                    <div class="section-content">
                        <span class="status-badge ml">historical_nc</span>
                        <span class="status-badge ml">control_patterns</span>
                        <span class="status-badge ml">temporal_risk</span>
                    </div>
                </div>
            `;
        }

        // Costruisci sezione dati formattata
        let dataSection = '';
        if (executionData?.data) {
            const data = executionData.data;
            let formattedItems = [];

            // Formatta i dati in modo leggibile
            if (data.intent) formattedItems.push(`<strong>Intent:</strong> ${data.intent}`);
            if (data.confidence !== undefined) formattedItems.push(`<strong>Confidence:</strong> ${(data.confidence * 100).toFixed(1)}%`);
            if (data.piano_code) formattedItems.push(`<strong>Piano:</strong> ${data.piano_code}`);
            if (data.topic) formattedItems.push(`<strong>Topic:</strong> ${data.topic}`);
            if (data.tool_type) formattedItems.push(`<strong>Tipo:</strong> ${data.tool_type}`);
            if (data.message) formattedItems.push(`<strong>Query:</strong> "${data.message.substring(0, 100)}${data.message.length > 100 ? '...' : ''}"`);
            if (data.responseLength) formattedItems.push(`<strong>Risposta:</strong> ${data.responseLength} caratteri`);
            if (data.slots && Object.keys(data.slots).length > 0) {
                const slotEntries = Object.entries(data.slots)
                    .filter(([k, v]) => v)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(', ');
                if (slotEntries) formattedItems.push(`<strong>Slots:</strong> ${slotEntries}`);
            }

            if (formattedItems.length > 0) {
                dataSection = `
                    <div class="node-detail-section">
                        <div class="section-label">Dati Esecuzione</div>
                        <div class="section-content" style="line-height: 1.8;">
                            ${formattedItems.join('<br>')}
                        </div>
                    </div>
                `;
            }
        }

        const detailsHtml = `
            <div class="${cardClass}">
                <div class="node-detail-header">
                    <div class="node-icon ${node.type}">
                        ${node.icon}
                    </div>
                    <div>
                        <div class="node-name" ${nameStyle}>${node.label}</div>
                        <div class="node-type">${typeLabel}</div>
                    </div>
                </div>

                <div class="node-detail-section">
                    <div class="section-label">Descrizione</div>
                    <div class="section-content">${node.description}</div>
                </div>

                ${mlSection}

                ${executionData ? `
                    <div class="node-detail-section">
                        <div class="section-label">Stato Esecuzione</div>
                        <div class="section-content">
                            <span class="status-badge ${executionData.status === 'completed' ? 'completed' : 'executing'}">
                                ${executionData.status === 'completed' ? '\u2713 Completato' : '\u23F3 In esecuzione'}
                            </span>
                            ${executionData.durationLabel ? `<span style="margin-left: 8px; color: var(--text-muted);">${executionData.durationLabel}</span>` : ''}
                        </div>
                    </div>

                    ${executionData.description ? `
                        <div class="node-detail-section">
                            <div class="section-label">Risultato</div>
                            <div class="section-content" style="font-weight: 500;">${executionData.description}</div>
                        </div>
                    ` : ''}

                    ${dataSection}
                ` : `
                    <div class="node-detail-section">
                        <div class="section-label">Stato</div>
                        <div class="section-content" style="color: var(--text-muted);">
                            \u{1F6C8} Non eseguito in questa query.<br>
                            <small>Esegui una query che attivi questo nodo per vedere i dettagli.</small>
                        </div>
                    </div>
                `}
            </div>
        `;

        this.nodeDetails.innerHTML = detailsHtml;
    }

    getNodeTypeLabel(type) {
        const labels = {
            'input': 'Input Node',
            'router': 'Classification Node',
            'agent': 'Tool Group',
            'ml': 'Machine Learning Node',
            'state': 'Decision Node',
            'response': 'Output Node'
        };
        return labels[type] || type;
    }

    updateExecutionSteps(response = null, query = '') {
        // Usa dati reali dal backend se disponibili
        const executionPath = response?.execution_path || [];
        const nodeTimings = response?.node_timings || {};
        const intent = response?.intent?.name || 'unknown';
        const confidence = response?.intent?.confidence || response?.confidence || 0;
        const slots = response?.slots || {};
        const entities = response?.entities || [];

        // Se non ci sono dati reali, fallback a currentExecution
        if (executionPath.length === 0 && this.currentExecution?.steps) {
            const stepsHtml = this.currentExecution.steps.map(step => `
                <div class="execution-step ${step.status}">
                    <div class="step-header">
                        <span class="step-title">${step.nodeLabel}</span>
                        ${step.durationLabel ? `<span class="step-duration">${step.durationLabel}</span>` : ''}
                    </div>
                    ${step.description ? `<div class="step-description">${step.description}</div>` : ''}
                </div>
            `).join('');
            this.executionSteps.innerHTML = stepsHtml;
            return;
        }

        // Costruisci HTML con dati reali dal backend
        let stepsHtml = '';

        // Step 0: Query originale
        stepsHtml += `
            <div class="execution-step completed">
                <div class="step-header">
                    <span class="step-number">0</span>
                    <span class="step-title">📝 Input Query</span>
                </div>
                <div class="step-description">
                    <code style="background: var(--bg-tertiary); padding: 4px 8px; border-radius: 4px; display: block; margin-top: 4px;">${this.escapeHtml(query || response?.original_message || 'N/A')}</code>
                </div>
            </div>
        `;

        // Steps dal execution_path reale
        executionPath.forEach((nodeName, index) => {
            const node = this.nodes[nodeName];
            const label = node?.label || nodeName;
            const icon = node?.icon || '⚙️';
            const timing = nodeTimings[nodeName];
            const durationMs = timing ? (typeof timing === 'object' ? timing.duration : timing) : null;
            const durationLabel = durationMs ? `${durationMs.toFixed(1)}ms` : '';

            // Descrizione specifica per nodo
            let description = node?.description || '';
            if (nodeName === 'classify') {
                description = `Intent: <strong>${intent}</strong> (${(confidence * 100).toFixed(1)}% confidence)`;
            } else if (nodeName === 'dialogue_manager') {
                const slotEntries = Object.entries(slots).filter(([k, v]) => v);
                if (slotEntries.length > 0) {
                    description = `Slots: ${slotEntries.map(([k, v]) => `<em>${k}=${v}</em>`).join(', ')}`;
                }
            } else if (nodeName.includes('tool') || nodeName.includes('piano') || nodeName.includes('search')) {
                if (entities.length > 0) {
                    description = `Entities: ${entities.map(e => `<em>${e.entity}=${e.value}</em>`).join(', ')}`;
                }
            }

            stepsHtml += `
                <div class="execution-step completed" data-node="${nodeName}">
                    <div class="step-header">
                        <span class="step-number">${index + 1}</span>
                        <span class="step-title">${icon} ${label}</span>
                        ${durationLabel ? `<span class="step-duration">${durationLabel}</span>` : ''}
                    </div>
                    ${description ? `<div class="step-description">${description}</div>` : ''}
                </div>
            `;
        });

        // Step finale: Risultato
        const totalMs = response?.total_execution_ms || 0;
        const hasError = response?.status !== 'success';
        stepsHtml += `
            <div class="execution-step ${hasError ? 'error' : 'completed'}">
                <div class="step-header">
                    <span class="step-number">✓</span>
                    <span class="step-title">${hasError ? '❌ Errore' : '✅ Completato'}</span>
                    ${totalMs ? `<span class="step-duration">Total: ${totalMs.toFixed(0)}ms</span>` : ''}
                </div>
                <div class="step-description">
                    ${hasError ? (response?.error || 'Errore sconosciuto') : `${executionPath.length} nodi eseguiti`}
                </div>
            </div>
        `;

        this.executionSteps.innerHTML = stepsHtml;

        // Click handler per evidenziare nodi nel grafo
        this.executionSteps.querySelectorAll('.execution-step[data-node]').forEach(stepEl => {
            stepEl.style.cursor = 'pointer';
            stepEl.addEventListener('click', () => {
                const nodeName = stepEl.dataset.node;
                this.highlightNode(nodeName);
                this.updateNodeDetails(nodeName);
                // Switch to Nodes tab
                this.switchTab('nodesPanel');
            });
        });
    }

    updateMetrics(response) {
        // Usa dati reali dal backend se disponibili
        const totalMs = response.total_execution_ms || this.currentExecution?.totalDuration || 0;
        const nodeTimings = response.node_timings || {};
        const executionPath = response.execution_path || [];
        const slots = response.slots || {};

        this.totalExecutionTime.textContent = totalMs > 0 ? `${totalMs.toFixed(0)}ms` : '0ms';
        this.nodesExecuted.textContent = executionPath.length || this.currentExecution?.steps.length || 0;
        this.confidence.textContent = response.confidence ?
            `${(response.confidence * 100).toFixed(1)}%` : '0%';
        this.entitiesFound.textContent = response.entities?.length || 0;

        const mlUsed = executionPath.includes('ml_risk_manager') ||
            this.currentExecution?.steps.some(step => step.nodeId === 'ml_risk_manager');

        // Costruisci timing breakdown HTML
        let timingBreakdownHtml = '';
        if (Object.keys(nodeTimings).length > 0) {
            const maxTime = Math.max(...Object.values(nodeTimings).map(t =>
                typeof t === 'object' ? t.duration : t
            ));

            const timingItems = Object.entries(nodeTimings).map(([nodeName, timing]) => {
                const duration = typeof timing === 'object' ? timing.duration : timing;
                const percentage = maxTime > 0 ? (duration / maxTime) * 100 : 0;
                const node = this.nodes[nodeName];
                const label = node?.label || nodeName;
                const icon = node?.icon || '⚡';
                const isML = nodeName === 'ml_risk_manager';
                const barColor = isML ? 'background: linear-gradient(90deg, #ec4899, #f472b6);' :
                    'background: linear-gradient(90deg, #3b82f6, #60a5fa);';

                return `
                    <div class="timing-item" style="margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                            <span style="font-size: 0.8rem; color: var(--text-primary);">${icon} ${label}</span>
                            <span style="font-size: 0.8rem; font-weight: 600; color: ${isML ? '#f472b6' : '#60a5fa'};">${duration.toFixed(1)}ms</span>
                        </div>
                        <div class="progress-bar" style="height: 6px;">
                            <div class="progress-fill" style="width: ${percentage}%; ${barColor}"></div>
                        </div>
                    </div>
                `;
            }).join('');

            timingBreakdownHtml = `
                <div class="info-section">
                    <h4>⏱️ Node Timing Breakdown</h4>
                    <div style="margin-top: 8px;">
                        ${timingItems}
                    </div>
                    <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--border-color);">
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                            <span style="color: var(--text-muted);">Tempo Totale</span>
                            <span style="font-weight: 700; color: var(--text-primary);">${totalMs.toFixed(1)}ms</span>
                        </div>
                    </div>
                </div>
            `;
        }

        // Costruisci slots HTML se presenti
        let slotsHtml = '';
        const filledSlots = Object.entries(slots).filter(([k, v]) => v);
        if (filledSlots.length > 0) {
            const slotItems = filledSlots.map(([key, value]) => `
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--border-color);">
                    <span style="color: var(--text-muted); font-size: 0.8rem;">${key}</span>
                    <span style="color: #4ade80; font-weight: 500; font-size: 0.8rem;">${value}</span>
                </div>
            `).join('');

            slotsHtml = `
                <div class="info-section" style="border-left-color: #4ade80;">
                    <h4>🎯 Slot Estratti</h4>
                    <div style="margin-top: 8px;">
                        ${slotItems}
                    </div>
                </div>
            `;
        }

        // Tool attivati
        const toolNodes = ['piano_tools', 'search_tool', 'priority_tools', 'ml_risk_manager',
            'ask_piano_description', 'ask_piano_stabilimenti', 'ask_priority_establishment',
            'ask_risk_analysis', 'search_piani_by_topic'];
        const agentsUsed = executionPath
            .filter(nodeName => toolNodes.some(t => nodeName.includes(t) || nodeName.startsWith('ask_')))
            .map(nodeName => this.nodes[nodeName]?.label || nodeName);

        // Execution path visual
        const pathVisual = executionPath.length > 0
            ? executionPath.map(n => {
                const node = this.nodes[n];
                return node ? `<span title="${node.label}">${node.icon || '⚙️'}</span>` : n;
            }).join(' → ')
            : 'N/A';

        const metricsHtml = `
            <div class="info-section" ${mlUsed ? 'style="border-left-color: #ec4899;"' : ''}>
                <h4>${mlUsed ? '🧠' : '📊'} Execution Summary</h4>
                <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.8;">
                    <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                        <span>Intent:</span>
                        <span style="color: var(--text-primary); font-weight: 500;">${response.intent?.name || 'Unknown'}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                        <span>Confidence:</span>
                        <span style="color: ${response.confidence > 0.8 ? '#4ade80' : response.confidence > 0.5 ? '#fbbf24' : '#f87171'}; font-weight: 600;">
                            ${((response.confidence || 0) * 100).toFixed(1)}%
                        </span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                        <span>Tool attivati:</span>
                        <span style="color: var(--text-primary);">${agentsUsed.length > 0 ? agentsUsed.length : 0}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                        <span>Risposta:</span>
                        <span style="color: var(--text-primary);">${response.message?.length || 0} chars</span>
                    </div>
                </div>
                <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--border-color);">
                    <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px;">Execution Path:</div>
                    <div style="font-size: 1.1rem; letter-spacing: 2px;">${pathVisual}</div>
                </div>
            </div>

            ${timingBreakdownHtml}

            ${slotsHtml}

            ${mlUsed ? `
            <div class="info-section" style="border-left-color: #ec4899;">
                <h4 style="color: #f9a8d4;">🧠 ML Risk Analysis</h4>
                <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6;">
                    <strong style="color: #f9a8d4;">Modello:</strong> XGBoost v4<br>
                    <strong style="color: #f9a8d4;">Features:</strong> NC storiche, pattern controlli, rischio temporale<br>
                    <strong style="color: #f9a8d4;">Output:</strong> Prioritizzazione rischio stabilimenti
                </div>
            </div>
            ` : ''}

            <div class="info-section">
                <h4>⚡ Performance Score</h4>
                <div class="progress-bar" style="height: 8px;">
                    <div class="progress-fill animated" style="width: ${Math.min(100, (response.confidence || 0) * 100)}%; ${mlUsed ? 'background: linear-gradient(90deg, #ec4899, #f472b6);' : ''}"></div>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 0.8rem; color: var(--text-muted);">
                    <span>Bassa</span>
                    <span style="color: ${response.confidence > 0.8 ? '#4ade80' : '#fbbf24'}; font-weight: 600;">
                        ${response.confidence > 0.8 ? '✓ Alta' : response.confidence > 0.5 ? '~ Media' : '⚠ Bassa'}
                    </span>
                    <span>Alta</span>
                </div>
            </div>
        `;

        this.detailedMetrics.innerHTML = metricsHtml;
    }

    clearExecution() {
        document.querySelectorAll('.graph-node').forEach(node => {
            node.classList.remove('executing', 'completed', 'active');
        });

        document.querySelectorAll('.connection-line').forEach(line => {
            line.classList.remove('active', 'completed');
        });

        this.executionSteps.innerHTML = '<div class="empty-state">No execution in progress</div>';
    }

    showLoading() {
        this.loadingOverlay.style.display = 'flex';
    }

    hideLoading() {
        this.loadingOverlay.style.display = 'none';
    }

    showError(message) {
        const errorHtml = `<div class="error-message">\u26A0\uFE0F ${message}</div>`;
        this.executionSteps.innerHTML = errorHtml;
    }

    updateExecutionStatus(state, content) {
        if (!this.executionStatus) return;

        if (state === 'loading') {
            this.lastQuery = content;
            this.executionStatus.innerHTML = `
                <span class="status-icon">⏳</span>
                <div>Elaborazione in corso...</div>
                <small class="status-query">"${this.escapeHtml(content)}"</small>
            `;
            this.executionStatus.className = 'execution-status status-loading';
        } else if (state === 'success') {
            // Save to history
            if (this.lastQuery && this.lastResponse) {
                this.addToHistory(this.lastQuery, this.lastResponse);
            }

            this.executionStatus.innerHTML = `
                <div class="response-header">
                    <span class="response-query">📝 "${this.escapeHtml(this.lastQuery)}"</span>
                    <div class="response-actions">
                        <button class="response-action-btn" onclick="window.langGraphVisualizer.copyResponse()" title="Copia risposta">
                            📋 Copia
                        </button>
                        <button class="response-action-btn" onclick="window.langGraphVisualizer.exportDebugInfo()" title="Esporta debug info">
                            📥 Export
                        </button>
                    </div>
                </div>
                <div class="response-display">${this.formatResponse(content)}</div>
            `;
            this.executionStatus.className = 'execution-status status-success';
        } else if (state === 'error') {
            this.executionStatus.innerHTML = `
                <span class="status-icon">⚠️</span>
                <div class="status-error-text">${this.escapeHtml(content)}</div>
                <button class="response-action-btn" onclick="window.langGraphVisualizer.retryLastQuery()" style="margin-top: 8px;">
                    🔄 Riprova
                </button>
            `;
            this.executionStatus.className = 'execution-status status-error';
        }
    }

    addToHistory(query, response) {
        // Add to beginning, limit to 10 items
        this.queryHistory.unshift({
            query: query,
            intent: response.intent?.name || 'unknown',
            timestamp: Date.now(),
            response: response
        });
        if (this.queryHistory.length > 10) {
            this.queryHistory.pop();
        }
    }

    copyResponse() {
        if (this.lastResponse?.message) {
            navigator.clipboard.writeText(this.lastResponse.message).then(() => {
                this.showToast('Risposta copiata negli appunti');
            }).catch(() => {
                this.showToast('Errore nella copia', 'error');
            });
        }
    }

    exportDebugInfo() {
        if (!this.lastResponse) return;

        const debugData = {
            timestamp: new Date().toISOString(),
            query: this.lastQuery,
            response: this.lastResponse.message,
            intent: this.lastResponse.intent,
            confidence: this.lastResponse.confidence,
            entities: this.lastResponse.entities,
            slots: this.lastResponse.slots,
            execution_path: this.lastResponse.execution_path,
            node_timings: this.lastResponse.node_timings,
            total_execution_ms: this.lastResponse.total_execution_ms
        };

        const blob = new Blob([JSON.stringify(debugData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `gias-debug-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('Debug info esportato');
    }

    retryLastQuery() {
        if (this.lastQuery) {
            this.messageInput.value = this.lastQuery;
            this.sendButton.disabled = false;
            this.executeWorkflow();
        }
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: ${type === 'error' ? '#ef4444' : '#10b981'};
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 0.85rem;
            z-index: 1000;
            animation: fadeInOut 2s ease;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatResponse(text) {
        // Convert markdown-like formatting to HTML
        let html = this.escapeHtml(text);
        // Bold: **text**
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Line breaks
        html = html.replace(/\n/g, '<br>');
        return html;
    }

    showTooltip(event, node) {
        let tooltip = document.querySelector('.interactive-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.className = 'interactive-tooltip';
            document.body.appendChild(tooltip);
        }

        tooltip.innerHTML = `
            <strong>${node.label}</strong><br>
            <small>${node.description}</small>
        `;

        const rect = event.target.getBoundingClientRect();
        tooltip.style.left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2 + 'px';
        tooltip.style.top = rect.top - tooltip.offsetHeight - 8 + 'px';

        tooltip.classList.add('visible');
    }

    hideTooltip() {
        const tooltip = document.querySelector('.interactive-tooltip');
        if (tooltip) {
            tooltip.classList.remove('visible');
        }
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    loadInitialContent() {
        this.executionSteps.innerHTML = `
            <div class="info-section">
                <h4>\u{1F3D7}\uFE0F LangGraph Workflow Architecture</h4>
                <p>Flusso reale: classify \u2192 dialogue_manager \u2192 {tool | ask_user | fallback} \u2192 response_generator</p>
                <ul style="margin: 8px 0; padding-left: 20px; font-size: 0.85rem; color: #4b5563;">
                    <li><strong>Classify</strong> - Router ibrido a 4 livelli</li>
                    <li><strong>Dialogue Manager</strong> - Decision engine rule-based</li>
                    <li><strong>Tool Nodes</strong> - 18 tool specializzati (piano, priority, search, ML)</li>
                    <li><strong>Response Generator</strong> - LLM response con two-phase</li>
                </ul>
            </div>
        `;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new LangGraphDebugVisualizer();
});
