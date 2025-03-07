// Create completion hint element
const completionHint = document.createElement('div');
completionHint.className = 'cm-completion-hint';
completionHint.style.display = 'none';
completionHint.style.position = 'absolute';
completionHint.style.background = '#1e1e1e';
completionHint.style.color = '#ffffff';
completionHint.style.padding = '4px 8px';
completionHint.style.borderRadius = '4px';
completionHint.style.fontSize = '14px';
completionHint.style.border = '1px solid #444';
completionHint.style.zIndex = '1000';
completionHint.style.whiteSpace = 'pre';
document.body.appendChild(completionHint);

let hintTimeout;


function showCompletionHint(cm, hint) {
    clearTimeout(hintTimeout);

    const cursor = cm.getCursor();
    const coords = cm.cursorCoords(cursor, "page");
    const viewportHeight = window.innerHeight;

    // Set the hint content **first**
    completionHint.textContent = hint;
    completionHint.style.display = 'block';  // Make it visible to measure height

    // Now get the correct height
    const hintHeight = completionHint.offsetHeight;
    console.log("Hint Height:", hintHeight);

    // Check if it fits below; if not, move it above
    if (coords.bottom + hintHeight > viewportHeight) {
        let newTop = coords.top - hintHeight - 5;
        if (newTop < 0) newTop = 5; // Prevent negative positioning
        completionHint.style.top = `${newTop}px`;
    } else {
        completionHint.style.top = `${coords.bottom + 5}px`;
    }

    completionHint.style.left = `${coords.left + 5}px`;

    // Hide after 5 seconds
    hintTimeout = setTimeout(() => {
        completionHint.style.display = 'none';
    }, 8000);
}




// Function to accept completion
function acceptCompletion(cm) {
    if (completionHint.style.display === 'none') return false;

    const cursor = cm.getCursor();
    const suggestedText = completionHint.textContent;

    // Get the existing text *after* the cursor
    const existingText = cm.getRange(cursor, { line: cm.lineCount() - 1, ch: Infinity });

    // Combine the suggested text and the existing text
    const finalText = suggestedText + existingText;


    // Handle multi-line suggestions for correct end position
    const lines = finalText.split('\n'); // Split combined text
    cm.replaceRange(finalText, cursor, {
        line: cursor.line + lines.length - 1,
        ch: lines[lines.length - 1].length,
    });



    completionHint.style.display = 'none';
    clearTimeout(hintTimeout);
    return true;
}



// Add custom key binding for accepting completion
codeMirrorEditor.addKeyMap({
    'Tab': function (cm) {
        if (!acceptCompletion(cm)) {
            cm.execCommand('insertTab'); // Default tab behavior if no completion
        }
    }
});

// Hide hint on blur
codeMirrorEditor.on('blur', () => {
    completionHint.style.display = 'none';
    clearTimeout(hintTimeout);
});


let debounceTimer;

codeMirrorEditor.on('inputRead', (cm, change) => {
    if (change.origin !== '+input') return;

    if (document.getElementById('autocomplete').classList.contains('active')) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            const cursor = cm.getCursor();
            const linesAbove = cm.getRange({ line: 0, ch: 0 }, cursor);
            const currentLine = cm.getLine(cursor.line);

            if (currentLine.trim().length > 10) {
                try {
                    const completion = await getAICompletions(linesAbove, cm.getOption("mode")); // Pass language mode
                    if (completion) showCompletionHint(cm, completion);
                    else completionHint.style.display = 'none'; // Hide if no completion
                } catch (error) {
                    console.error('Autocomplete error:', error);
                }
            } else {
                completionHint.style.display = 'none';
            }
        }, 1000);
    }
    else
    {
        return
    }
});


// Fetch completion from backend
async function getAICompletions(linesAbove, language) {
    try {
        const response = await fetch('/autocomplete', {  // Use relative URL for Flask
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: linesAbove, language: language }), // Send language
        });

        if (!response.ok) {
            console.error("Error fetching completions:", response.status, response.statusText);
            return null; // or throw an error
        }


        const data = await response.json();
        hint = data.completion;
        const regex = /```(\w+)\n(.*?)```/s;
        const match = hint.match(regex);
        var extractedCode = match ? match[2].trim() : data.completion
        extractedCode = "\n" + extractedCode;
        return extractedCode;

    } catch (error) {
        console.error('Error fetching AI completion:', error);
        return null;
    }
}