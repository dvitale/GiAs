/**
 * GIAS Chat History - Client-side logic
 */
class ChatHistory {
    constructor() {
        this.conversations = [];
        this.filteredConversations = [];
        this.currentSessionId = null;
        this.offset = 0;
        this.limit = 50;
        this.total = 0;
        this.searchTimeout = null;

        this.init();
    }

    init() {
        this.initTheme();
        this.bindEvents();

        if (!window.queryParams.codice_fiscale) {
            this.showError('Codice fiscale non disponibile. Accedi dalla pagina principale.');
            return;
        }

        this.loadConversations();
    }

    // =========================================================================
    // Theme
    // =========================================================================

    initTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-theme');
        }

        document.getElementById('themeToggle').addEventListener('click', () => {
            document.body.classList.toggle('dark-theme');
            const isDark = document.body.classList.contains('dark-theme');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        });
    }

    // =========================================================================
    // Events
    // =========================================================================

    bindEvents() {
        // Search with debounce
        const searchInput = document.getElementById('searchInput');
        searchInput.addEventListener('input', () => {
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(() => this.filterConversations(), 300);
        });

        // Load more
        document.getElementById('loadMoreBtn').addEventListener('click', () => this.loadMore());

        // Mobile sidebar
        document.getElementById('sidebarToggleBtn').addEventListener('click', () => this.openSidebar());
        document.getElementById('sidebarCloseBtn').addEventListener('click', () => this.closeSidebar());
        document.getElementById('sidebarOverlay').addEventListener('click', () => this.closeSidebar());
    }

    // =========================================================================
    // API
    // =========================================================================

    async loadConversations() {
        const list = document.getElementById('conversationList');
        list.innerHTML = '<div class="loading-state"><div class="loading-spinner-small"></div><span>Caricamento...</span></div>';

        try {
            const cf = encodeURIComponent(window.queryParams.codice_fiscale);
            const url = `${window.basePath}/api/chat-log/user-conversations?codice_fiscale=${cf}&limit=${this.limit}&offset=${this.offset}`;
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            this.total = data.total;

            if (this.offset === 0) {
                this.conversations = data.conversations;
            } else {
                this.conversations = this.conversations.concat(data.conversations);
            }

            this.filteredConversations = this.conversations;
            this.renderConversationList();
            this.updateLoadMore();
        } catch (e) {
            list.innerHTML = `<div class="loading-state"><span>Errore: ${e.message}</span></div>`;
        }
    }

    async loadConversation(sessionId) {
        this.currentSessionId = sessionId;

        // Update active state in sidebar
        document.querySelectorAll('.conversation-item').forEach(el => {
            el.classList.toggle('active', el.dataset.sessionId === sessionId);
        });

        // Show conversation view
        document.getElementById('emptyState').classList.add('hidden');
        const view = document.getElementById('conversationView');
        view.classList.remove('hidden');

        const msgs = document.getElementById('conversationMessages');
        msgs.innerHTML = '<div class="loading-state"><div class="loading-spinner-small"></div><span>Caricamento messaggi...</span></div>';

        // Close sidebar on mobile
        this.closeSidebar();

        try {
            const cf = encodeURIComponent(window.queryParams.codice_fiscale);
            const sid = encodeURIComponent(sessionId);
            const url = `${window.basePath}/api/chat-log/conversation/${sid}?codice_fiscale=${cf}`;
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            this.renderConversation(data);
        } catch (e) {
            msgs.innerHTML = `<div class="loading-state"><span>Errore: ${e.message}</span></div>`;
        }
    }

    // =========================================================================
    // Rendering
    // =========================================================================

    renderConversationList() {
        const list = document.getElementById('conversationList');

        if (this.filteredConversations.length === 0) {
            list.innerHTML = '<div class="loading-state"><span>Nessuna conversazione trovata</span></div>';
            return;
        }

        list.innerHTML = this.filteredConversations.map(conv => {
            const date = conv.started_at ? this.formatDate(conv.started_at) : '';
            const isActive = conv.session_id === this.currentSessionId;
            const title = this.truncate(conv.title, 60);

            return `
                <div class="conversation-item ${isActive ? 'active' : ''}"
                     data-session-id="${this.escapeHtml(conv.session_id)}"
                     onclick="chatHistory.loadConversation('${this.escapeJs(conv.session_id)}')">
                    <div class="conv-title">${this.escapeHtml(title)}</div>
                    <div class="conv-meta">
                        <span>${date}</span>
                        <span>${conv.message_count} msg</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderConversation(data) {
        // Header
        const header = document.getElementById('conversationHeader');
        const conv = this.conversations.find(c => c.session_id === data.session_id);
        const title = conv ? conv.title : data.session_id;
        const msgCount = data.messages.length;

        header.innerHTML = `
            <h3 class="conv-view-title">${this.escapeHtml(this.truncate(title, 80))}</h3>
            <span class="conv-view-meta">${msgCount} messaggi</span>
        `;

        // Messages
        const msgs = document.getElementById('conversationMessages');
        if (data.messages.length === 0) {
            msgs.innerHTML = '<div class="loading-state"><span>Nessun messaggio in questa conversazione</span></div>';
            return;
        }

        msgs.innerHTML = data.messages.map(msg => {
            const time = msg.timestamp ? this.formatTime(msg.timestamp) : '';
            const parts = [];

            // User message (ask)
            if (msg.ask) {
                parts.push(`
                    <div class="message user-message">
                        <div class="message-content">${this.escapeHtml(msg.ask)}</div>
                        <div class="message-time">${time}</div>
                    </div>
                `);
            }

            // Bot message (answer)
            if (msg.answer) {
                const meta = [];
                if (msg.intent) meta.push(msg.intent);
                if (msg.response_time_ms) meta.push(`${msg.response_time_ms}ms`);

                parts.push(`
                    <div class="message bot-message">
                        <div class="message-content">${this.formatAnswer(msg.answer)}</div>
                        ${meta.length ? `<div class="message-time">${meta.join(' - ')}</div>` : ''}
                        ${msg.error ? `<div class="message-error">Errore: ${this.escapeHtml(msg.error)}</div>` : ''}
                    </div>
                `);
            }

            return parts.join('');
        }).join('');

        msgs.scrollTop = 0;
    }

    // =========================================================================
    // Search
    // =========================================================================

    filterConversations() {
        const query = document.getElementById('searchInput').value.trim().toLowerCase();
        if (!query) {
            this.filteredConversations = this.conversations;
        } else {
            this.filteredConversations = this.conversations.filter(c =>
                (c.title && c.title.toLowerCase().includes(query)) ||
                (c.asl && c.asl.toLowerCase().includes(query))
            );
        }
        this.renderConversationList();
    }

    // =========================================================================
    // Pagination
    // =========================================================================

    updateLoadMore() {
        const container = document.getElementById('loadMoreContainer');
        const loaded = this.conversations.length;
        container.style.display = loaded < this.total ? 'block' : 'none';
    }

    async loadMore() {
        this.offset += this.limit;
        const btn = document.getElementById('loadMoreBtn');
        btn.textContent = 'Caricamento...';
        btn.disabled = true;
        await this.loadConversations();
        btn.textContent = 'Carica altre';
        btn.disabled = false;
    }

    // =========================================================================
    // Mobile sidebar
    // =========================================================================

    openSidebar() {
        document.getElementById('historySidebar').classList.add('open');
        document.getElementById('sidebarOverlay').classList.add('visible');
        document.body.style.overflow = 'hidden';
    }

    closeSidebar() {
        document.getElementById('historySidebar').classList.remove('open');
        document.getElementById('sidebarOverlay').classList.remove('visible');
        document.body.style.overflow = '';
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    showError(msg) {
        const empty = document.getElementById('emptyState');
        empty.querySelector('p').textContent = msg;
    }

    formatDate(isoStr) {
        try {
            const d = new Date(isoStr);
            const now = new Date();
            const diffDays = Math.floor((now - d) / 86400000);

            if (diffDays === 0) return 'Oggi ' + d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
            if (diffDays === 1) return 'Ieri ' + d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
            if (diffDays < 7) return d.toLocaleDateString('it-IT', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
            return d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' });
        } catch { return isoStr; }
    }

    formatTime(isoStr) {
        try {
            const d = new Date(isoStr);
            return d.toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
        } catch { return isoStr; }
    }

    formatAnswer(text) {
        if (!text) return '';
        // Escape HTML then apply basic formatting
        let html = this.escapeHtml(text);
        // Bold: **text**
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Newlines
        html = html.replace(/\n/g, '<br>');
        return html;
    }

    truncate(str, max) {
        if (!str) return '';
        return str.length > max ? str.substring(0, max) + '...' : str;
    }

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    escapeJs(str) {
        if (!str) return '';
        return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    }
}

// Initialize
const chatHistory = new ChatHistory();
