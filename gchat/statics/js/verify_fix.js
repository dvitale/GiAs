
function formatMessage(message) {
    console.log('=== formatMessage START ===');

    // Escape HTML first
    let formatted = message
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Format emoji icons (preserve common emojis)
    const emojiMap = {
        '📊': '📊', '🔍': '🔍', '📋': '📋', '📌': '📌',
        '📝': '📝', '🎯': '🎯', '✅': '✅', '❌': '❌',
        '💡': '💡', '⚠️': '⚠️', '🏥': '🏥', '🏭': '🏭',
        '🔴': '🔴', '📍': '📍', '🏢': '🏢', '🆔': '🆔',
        '📉': '📉', '📅': '📅'
    };

    Object.keys(emojiMap).forEach(emoji => {
        formatted = formatted.replace(new RegExp(emoji, 'g'), emoji);
    });

    // Format numbered lists
    // We look for "1. text" potentially followed by sub-items
    // We use a regex that respects newlines for list items
    formatted = formatted.replace(/^(\d+)\.\s+(.+?)(?=\n\d+\.|\n\n|$)/gms, (match, number, content) => {
        let cleanContent = content.trim();

        // Format sub-items with dash/bullet within the list item
        cleanContent = cleanContent.replace(/^\s*-\s+\*\*([^*:]+):\*\*\s*(.+)$/gm,
            '<div class="sub-field"><span class="sub-label">$1:</span> <span class="sub-value">$2</span></div>');

        // Format specific fields within list items
        cleanContent = cleanContent.replace(/Aggregazione:\s*([^\n]+)/g, '<div class="sub-field"><span class="sub-label">Aggregazione:</span> <span class="sub-value">$1</span></div>');
        cleanContent = cleanContent.replace(/Attività:\s*([^\n]+)/g, '<div class="sub-field"><span class="sub-label">Attività:</span> <span class="sub-value">$1</span></div>');
        cleanContent = cleanContent.replace(/Controlli eseguiti:\s*([^\n]+)/g, '<div class="sub-field"><span class="sub-label">Controlli eseguiti:</span> <span class="sub-value highlight">$1</span></div>');
        cleanContent = cleanContent.replace(/Linea attività:\s*([^\n]+)/g, '<div class="activity-line">Linea attività: <em>$1</em></div>');
        cleanContent = cleanContent.replace(/Similarità:\s*(\d+\.\d+%)/g, '<span class="similarity">Similarità: <strong>$1</strong></span>');

        return `<div class="list-item"><span class="list-number">${number}.</span><div class="list-content">${cleanContent}</div></div>`;
    });

    // Format simple bullet points/dashes that are NOT part of a numbered list
    // and probably start on a new line
    formatted = formatted.replace(/^[•-]\s+(.+)$/gm, '<div class="list-item"><span class="list-number">•</span><div class="list-content">$1</div></div>');

    // Format headers without asterisks (Header: value)
    // Only if they start line, look like a header, and are not inside other tags
    formatted = formatted.replace(/^(?!\*\*)([A-Za-zÀ-ÿ\s]+:)\s*(.*)$/gm, (match, header, value) => {
        // Avoid matching inside HTML tags we just created
        if (header.includes('<') || header.includes('>')) return match;

        if (value.trim() && !value.startsWith('*')) {
            return `<div class="description-field"><span class="field-label"><strong>${header}</strong></span><span class="field-value">${value}</span></div>`;
        } else if (!value.trim()) {
            return `<div class="section-header"><strong>${header}</strong></div>`;
        }
        return match;
    });

    // Format main headers (standalone **text:** on their own line)
    formatted = formatted.replace(/^(\*\*[^*]+:\*\*)$/gm, '<div class="section-header">$1</div>');

    // Format description fields (**Field:** value on same line)
    formatted = formatted.replace(/^(\*\*[^*]+:\*\*)\s+(.+)$/gm, '<div class="description-field"><span class="field-label">$1</span><span class="field-value">$2</span></div>');

    // Format bold text (**text**)
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Format specific standalone fields if they weren't caught in lists
    formatted = formatted.replace(/^Aggregazione:\s*([^\n<]+)/gm, '<div class="sub-field"><span class="sub-label">Aggregazione:</span> <span class="sub-value">$1</span></div>');
    formatted = formatted.replace(/^Attività:\s*([^\n<]+)/gm, '<div class="sub-field"><span class="sub-label">Attività:</span> <span class="sub-value">$1</span></div>');
    formatted = formatted.replace(/^Controlli eseguiti:\s*([^\n<]+)/gm, '<div class="sub-field"><span class="sub-label">Controlli eseguiti:</span> <span class="sub-value highlight">$1</span></div>');
    formatted = formatted.replace(/^Linea attività:\s*([^\n<]+)/gm, '<div class="activity-line">Linea attività: <em>$1</em></div>');
    formatted = formatted.replace(/Similarità:\s*(\d+\.\d+%)/g, '<span class="similarity">Similarità: <strong>$1</strong></span>');

    // FINAL STEP: Convert newlines to HTML breaks
    // 1. Convert double newlines to section breaks (visual spacing)
    formatted = formatted.replace(/\n\s*\n/g, '<div class="section-break"></div>');

    // 2. Convert remaining single newlines to <br>
    formatted = formatted.replace(/\n/g, '<br>');

    console.log('=== formatMessage END ===');
    return formatted;
}

// TEST CASES
const tests = [
    {
        name: "Simple Newline",
        input: "Hello\nWorld",
        expected: "Hello<br>World"
    },
    {
        name: "Double Newline",
        input: "Para 1\n\nPara 2",
        expected: "Para 1<div class=\"section-break\"></div>Para 2"
    },
    {
        name: "Usage with Header",
        input: "Header:\nValue",
        expected: "<div class=\"section-header\"><strong>Header:</strong></div><br>Value" // Or similar
    },
    {
        name: "Numbered List",
        input: "1. First item\n2. Second item",
        // Note: The numbered list regex puts content in divs, and might consume the newline.
        shouldContain: ["<div class=\"list-item\">", "First item", "Second item"]
    }
];

tests.forEach(test => {
    console.log(`\n--- TEST: ${test.name} ---`);
    console.log(`Input: ${JSON.stringify(test.input)}`);
    const result = formatMessage(test.input);
    console.log(`Result: ${result}`);

    if (test.expected) {
        if (result === test.expected || result.includes(test.expected)) {
            console.log("PASS");
        } else {
            console.log("FAIL - Expected:", test.expected);
            // Doing a loose check because indentation/logic might vary slightly
        }
    } else if (test.shouldContain) {
        const allFound = test.shouldContain.every(s => result.includes(s));
        if (allFound) {
            console.log("PASS");
        } else {
            console.log("FAIL - Missing content");
        }
    }
});
