// terminal.js (Fixed)
let socket;
let activeCommands = {};

function initializeSocket() {
    socket = io();

    socket.on('command_status', function(data) {
        const { command_id, status, returncode, is_server } = data;
        console.log("Command status update:", command_id, status);
        
        // Create the terminal if it doesn't exist yet
        if (!document.getElementById(`terminal-${command_id}-container`)) {
            createTerminal(command_id, `Command: ${command_id}`, is_server);
        }
        
        updateCommandStatus(command_id, status, returncode);
    });

    socket.on('command_output', function(data) {
        const { command_id, output, type } = data;
        console.log("Command output:", command_id, type);
        
        // Create the terminal if it doesn't exist yet
        if (!document.getElementById(`terminal-${command_id}-container`)) {
            createTerminal(command_id, `Command: ${command_id}`, true);
        }
        
        appendToTerminal(command_id, output, type);
    });

    socket.on('connect_error', function(error) {
        console.error('Socket.IO connection error:', error);
        showNotification('Connection error: ' + error.message, 'status');
    });

    socket.on('reconnect', function(attemptNumber) {
        console.log('Reconnected to server after ' + attemptNumber + ' attempts');
        showNotification('Reconnected to server', 'success');
        listActiveCommands(); // Refresh on reconnect
    });
}

function createTerminal(command_id, command, is_server) {
    const terminalId = `terminal-${command_id}`;
    if (document.getElementById(terminalId + "-container")) {
        console.log(`Terminal ${terminalId} already exists`);
        return terminalId;  // Terminal already exists
    }

    console.log(`Creating new terminal: ${terminalId}`);
    
    const terminalHtml = `
        <div id="${terminalId}-container" class="terminal-container">
            <div class="terminal-header">
                <div class="terminal-title">
                    <span class="status-dot running"></span>
                    <span class="command-text">${escapeHtml(command)}</span>
                </div>
                <div class="terminal-controls">
                    <button class="btn btn-sm btn-outline-secondary clear-btn" data-terminal="${command_id}">
                        <i class="fas fa-eraser"></i> Clear
                    </button>
                    <button class="btn btn-sm btn-outline-danger stop-btn" data-terminal="${command_id}">
                        <i class="fas fa-stop"></i> Stop
                    </button>
                </div>
            </div>
            <div id="${terminalId}" class="terminal-output"></div>
            <div class="terminal-input-container">
                <div class="input-group">
                    <input type="text" id="${terminalId}-input" class="form-control terminal-input"
                           placeholder="Enter command input..." ${is_server ? '' : 'disabled'}>
                    <div class="input-group-append">
                        <button class="btn btn-primary send-input-btn primary-btn" data-terminal="${command_id}" ${is_server ? '' : 'disabled'}>
                            <i class="fas fa-paper-plane"></i> Send
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    const terminalsContainer = document.getElementById('terminals-container');
    if (terminalsContainer) {
        terminalsContainer.insertAdjacentHTML('afterbegin', terminalHtml); // Add to DOM!
        attachTerminalEventListeners(command_id);
        activeCommands[command_id] = { command: command, status: 'running', is_server: is_server };
        updateActiveCommandsCounter();
        console.log(`Terminal ${terminalId} created successfully`);
        return terminalId;
    } else {
        console.error("terminals-container element not found!"); // Crucial error handling
        return null; // Indicate failure
    }
}

function appendToTerminal(command_id, output, type) {
    const terminalId = `terminal-${command_id}`;
    const terminal = document.getElementById(terminalId);
    
    if (!terminal) {
        console.warn(`Terminal ${terminalId} not found, attempting to create it`);
        // Create the terminal if it doesn't exist
        createTerminal(command_id, `Command: ${command_id}`, true);
        
        // Try to get the terminal element again
        const newTerminal = document.getElementById(terminalId);
        if (!newTerminal) {
            console.error(`Failed to create terminal ${terminalId}`);
            return;
        }
        
        // Append output to the newly created terminal
        const outputElement = document.createElement('div');
        outputElement.className = `terminal-line ${type}`;
        outputElement.textContent = output;
        newTerminal.appendChild(outputElement);
        newTerminal.scrollTop = newTerminal.scrollHeight;
    } else {
        // Terminal exists, append output normally
        const outputElement = document.createElement('div');
        outputElement.className = `terminal-line ${type}`;
        outputElement.textContent = output;
        terminal.appendChild(outputElement);
        terminal.scrollTop = terminal.scrollHeight;
    }
}

function updateCommandStatus(command_id, status, returncode) {
    const terminalId = `terminal-${command_id}`;
    const statusDot = document.querySelector(`#${terminalId}-container .status-dot`);

    if (statusDot) {
        statusDot.classList.remove('running', 'completed', 'error', 'stopped');
        statusDot.classList.add(status === 'completed' && returncode === 0 ? 'completed' :
                               status === 'completed' && returncode !== 0 ? 'error' :
                               status === 'stopped' ? 'stopped' : 'running');

        const statusText = status === 'completed' ?
                          (returncode === 0 ? 'Completed successfully' : `Failed with code ${returncode}`) :
                          status === 'stopped' ? 'Stopped' :
                          status === 'running' ? 'Running' : status;
        appendToTerminal(command_id, `--- ${statusText} ---`, 'status');

        if (status !== 'running') {
            const inputField = document.getElementById(`${terminalId}-input`);
            const sendButton = document.querySelector(`button.send-input-btn[data-terminal="${command_id}"]`);
            if (inputField) inputField.disabled = true;
            if (sendButton) sendButton.disabled = true;
            if (activeCommands[command_id]) {
                activeCommands[command_id].status = status;
                updateActiveCommandsCounter();
            }
        }
    } else {
        console.warn(`Status dot for terminal ${terminalId} not found`);
    }
}

function attachTerminalEventListeners(command_id) {
     const terminalId = `terminal-${command_id}`;

    // Clear button
    const clearBtn = document.querySelector(`button.clear-btn[data-terminal="${command_id}"]`);
    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            const terminal = document.getElementById(terminalId);
            if (terminal) {
                terminal.innerHTML = '';
            }
        });
    }

    // Stop button
    const stopBtn = document.querySelector(`button.stop-btn[data-terminal="${command_id}"]`);
    if (stopBtn) {
        stopBtn.addEventListener('click', function() {
            stopCommand(command_id);
        });
    }

    // Input field enter key
    const inputField = document.getElementById(`${terminalId}-input`);
    if (inputField) {
        inputField.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                sendCommandInput(command_id, inputField.value);
                inputField.value = '';
            }
        });
    }

    // Send button
    const sendBtn = document.querySelector(`button.send-input-btn[data-terminal="${command_id}"]`);
    if (sendBtn) {
        sendBtn.addEventListener('click', function() {
            const inputField = document.getElementById(`${terminalId}-input`);
            if (inputField) {
                sendCommandInput(command_id, inputField.value);
                inputField.value = '';
            }
        });
    }
}

function stopCommand(command_id) {
    fetch('/api/stop-command', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ command_id: command_id })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(`Command stopped: ${command_id}`, 'success');
            clearInterval(window.intervalID);
            const terminalContainer = document.getElementById(`terminal-${command_id}-container`);
            if (terminalContainer) {
                terminalContainer.style.display = 'none';
            }
        } else {
            showNotification(`Error: ${data.message}`, 'error');
            const terminalContainer = document.getElementById(`terminal-${command_id}-container`);
            if (terminalContainer) {
                terminalContainer.style.display = 'none';
            }
        }
    })
    .catch(error => {
        console.error('Error stopping command:', error);
        showNotification(`Error: ${error.message}`, 'error');
        const terminalContainer = document.getElementById(`terminal-${command_id}-container`);
        if (terminalContainer) {
            terminalContainer.style.display = 'none';
        }
    });
}

function sendCommandInput(command_id, input) {
    if (!input.trim()) return;

    fetch('/api/send-input', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            command_id: command_id,
            input: input
        })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            showNotification(`Error: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Error sending input:', error);
        showNotification(`Error: ${error.message}`, 'error');
    });
}

function listActiveCommands() {
    fetch('/api/list-active-commands')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log("Active commands:", data.commands);
                
                data.commands.forEach(command => {
                    // Create terminal *only* if it doesn't exist
                    if (!document.getElementById(`terminal-${command.command_id}-container`)) {
                        console.log(`Creating terminal for existing command: ${command.command_id}`);
                        createTerminal(command.command_id, `Process ID: ${command.pid}`, true);
                    }
                    // Update status *even if it exists* (important!)
                    updateCommandStatus(command.command_id, command.status, command.returncode);
                });
                
                const activeCount = data.commands.filter(cmd => cmd.status === 'running').length;
                const countElement = document.getElementById('active-commands-count');
                if (countElement) {
                    countElement.textContent = activeCount;
                }
            } else {
                console.error("Error listing active commands:", data.message);
            }
        })
        .catch(error => {
            console.error('Error listing active commands:', error);
        });
}

function stopAllCommands() {
    const commandIds = Object.keys(activeCommands).filter(id =>
        activeCommands[id].status === 'running');

    if (commandIds.length === 0) {
        showNotification('No active commands to stop', 'info');
        return;
    }

    if (confirm(`Are you sure you want to stop all ${commandIds.length} active commands?`)) {
        commandIds.forEach(commandId => {
            stopCommand(commandId); // Use the existing stopCommand function
        });
    }
}

function updateActiveCommandsCounter() {
    const activeCount = Object.values(activeCommands)
        .filter(cmd => cmd.status === 'running').length;
    const counter = document.getElementById('active-commands-count');
    if (counter) {
        counter.textContent = activeCount;
    }
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' :
                                                               type === 'success' ? 'success' :
                                                               type === 'warning' ? 'warning' : 'info'}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${escapeHtml(message)}
            </div>
            <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;

    const toastContainer = document.getElementById('toast-container');
    if (toastContainer) {
        toastContainer.appendChild(toast);

        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 5000
        });

        bsToast.show();

        // Remove the toast after it's hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toastContainer.removeChild(toast);
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initializeSocket();
    listActiveCommands(); // Call immediately on load!

    const stopAllBtn = document.getElementById('stop-all-commands-btn');
    if (stopAllBtn) {
        stopAllBtn.addEventListener('click', stopAllCommands);
    }
    
    const refreshBtn = document.getElementById("refresh_command");
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            listActiveCommands();
        });
    }
    
    // Periodic refresh of active commands (optional)
    // const refreshInterval = setInterval(listActiveCommands, 10000);
});