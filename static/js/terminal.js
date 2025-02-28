// terminal.js (Revised)
let socket;
let activeCommands = {};

function initializeSocket() {
    socket = io();

    socket.on('command_status', function(data) {
        const { command_id, status, returncode } = data;
        console.log("working: ",command_id)
        console.log(returncode);
        updateCommandStatus(command_id, status, returncode);
    });

    socket.on('command_output', function(data) {
        const { command_id, output, type } = data;
        console.log(output);
        console.log(command_id)
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
        return terminalId;  // Terminal already exists
    }

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
        return terminalId;
    } else {
        console.error("terminals-container element not found!"); // Crucial error handling
        return null; // Indicate failure
    }
}

function appendToTerminal(command_id, output, type) {
    const terminalId = `terminal-${command_id}`;
    const terminal = document.getElementById(terminalId);
    if (terminal) {
        const outputElement = document.createElement('div');
        outputElement.className = `terminal-line ${type}`;
        outputElement.textContent = output;
        terminal.appendChild(outputElement);
        terminal.scrollTop = terminal.scrollHeight;
    } else {
        console.warn(`Terminal ${terminalId} not found`);
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
            clearInterval(state.intervalID);
            document.getElementById(`terminal-${command_id}-container`).style.display='none';
        } else {
            showNotification(`Error: ${data.message}`, 'error');
            document.getElementById(`terminal-${command_id}-container`).style.display='none';
        }
    })
    .catch(error => {
        console.error('Error stopping command:', error);
        showNotification(`Error: ${error.message}`, 'error');
        document.getElementById(`terminal-${command_id}-container`).style.display='none';
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
                // Clear existing terminals (optional, depends on desired behavior)
                // document.getElementById('terminals-container').innerHTML = '';

                data.commands.forEach(command => {
                    // Create terminal *only* if it doesn't exist
                    if (!document.getElementById(`terminal-${command.command_id}-container`)) {
                         createTerminal(command.command_id, `Process ID: ${command.pid}`, true);
                    }
                    // Update status *even if it exists* (important!)
                    updateCommandStatus(command.command_id, command.status, command.returncode);
                });
                 const activeCount = data.commands.filter(cmd => cmd.status === 'running').length;
                document.getElementById('active-commands-count').textContent = activeCount;

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
        .replace(/&/g, "&")
        .replace(/</g, "<")
        .replace(/>/g, ">")
        .replace(/"/g, '"')
        .replace(/'/g, "'");
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
    document.getElementById("refresh_command").addEventListener('click',function (){
        listActiveCommands();
    })
    // setInterval(listActiveCommands, 5000);
});