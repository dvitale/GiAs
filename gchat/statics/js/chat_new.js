// New simplified formatMessage function
function formatMessage(message) {
    if (!message || typeof message !== 'string') return '';

    console.log('=== NEW formatMessage START ===');
    console.log('Original:', message);

    // Step 1: Escape HTML but preserve structure
    let formatted = message
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Step 2: Parse into logical blocks
    const blocks = parseContentBlocks(formatted);

    // Step 3: Convert blocks to clean HTML
    const htmlBlocks = blocks.map(block => convertBlockToHTML(block));

    // Step 4: Join with minimal spacing
    const result = htmlBlocks.filter(block => block.trim()).join('');

    console.log('=== NEW formatMessage END ===');
    return result;
}

function parseContentBlocks(text) {
    const lines = text.split('\n').map(line => line.trim()).filter(line => line);
    const blocks = [];
    let currentBlock = null;

    for (const line of lines) {
        const blockType = identifyLineType(line);

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

function identifyLineType(line) {
    if (/^\d+\.\s+/.test(line)) return 'list-item';
    if (/^[•-]\s+/.test(line)) return 'bullet-item';
    if (/^\*\*[^*]+:\*\*$/.test(line)) return 'header';
    if (/^\*\*[^*]+:\*\*\s+/.test(line)) return 'field';
    if (/^[A-Za-zÀ-ÿ\s]+:\s*\w/.test(line)) return 'field';
    if (/^[A-Za-zÀ-ÿ\s]+:$/.test(line)) return 'subheader';
    return 'text';
}

function convertBlockToHTML(block) {
    switch (block.type) {
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
                    const processedContent = processListItemContent(content);
                    return `<div class="list-item-new" data-number="${number}">${processedContent}</div>`;
                }
                return `<div class="list-item-new">${item}</div>`;
            }).join('');
            return `<div class="list-container">${listItems}</div>`;

        case 'field-group':
            const fields = block.content.map(field => formatField(field)).join('');
            return `<div class="field-group">${fields}</div>`;

        case 'field':
            return `<div class="field-group">${formatField(block.content)}</div>`;

        case 'bullet-item':
            const bulletContent = block.content.replace(/^[•-]\s+/, '');
            return `<div class="bullet-item-new">${bulletContent}</div>`;

        case 'text':
            return `<div class="text-content">${block.content}</div>`;

        default:
            return `<div class="default-content">${block.content}</div>`;
    }
}

function processListItemContent(content) {
    // Extract establishment info using more specific patterns
    const patterns = [
        { regex: /^([^-]+)\s-\s(.+)$/, format: '<div class="establishment-header"><strong>$1</strong> - $2</div>' },
        { regex: /Comune:\s*(.+)/i, format: '<div class="detail-line">📍 <span class="label">Comune:</span> <span class="value">$1</span></div>' },
        { regex: /Indirizzo:\s*(.+)/i, format: '<div class="detail-line">🏠 <span class="label">Indirizzo:</span> <span class="value">$1</span></div>' },
        { regex: /ID:\s*(.+)/i, format: '<div class="detail-line">🆔 <span class="label">ID:</span> <span class="value">$1</span></div>' },
        { regex: /Punteggio rischio[^:]*:\s*\*\*(\d+)\*\*/i, format: '<div class="risk-score">🎯 <span class="label">Punteggio rischio:</span> <span class="score high">$1</span></div>' },
        { regex: /NC storiche[^:]*:\s*(\d+)\s+gravi\s*\|\s*(\d+)\s+non gravi/i, format: '<div class="nc-line">⚠️ <span class="label">NC:</span> <span class="severe">$1 gravi</span> | <span class="minor">$2 non gravi</span></div>' },
        { regex: /Controlli[^:]*:\s*(\d+)/i, format: '<div class="controls-line">📊 <span class="label">Controlli:</span> <span class="value">$1</span></div>' },
        { regex: /Attivo dal:\s*(.+)/i, format: '<div class="date-line">📅 <span class="label">Attivo dal:</span> <span class="value">$1</span></div>' }
    ];

    let processed = content;
    for (const pattern of patterns) {
        processed = processed.replace(pattern.regex, pattern.format);
    }

    return processed;
}

function formatField(fieldText) {
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