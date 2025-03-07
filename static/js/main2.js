document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const projectPathInput = document.getElementById('project-path');
    const setPathBtn = document.getElementById('set-path-btn');
    const refreshFilesBtn = document.getElementById('refresh-files-btn');
    const fileList = document.getElementById('file-list');
    const fileSearch = document.getElementById('file-search');
    const fileTabs = document.getElementById('file-tabs');
    const fileEditor = document.getElementById('file-editor');
    const editorPlaceholder = document.getElementById('editor-placeholder');
    const editorContent = document.getElementById('editor-content');
    const saveFileBtn = document.getElementById('save-file-btn');
    const userPrompt = document.getElementById('user-prompt');
    const analyzeBtn = document.getElementById('analyze-btn');
    const runCommandBtn = document.getElementById('run-command-btn');
    const commandInputContainer = document.getElementById('command-input-container');
    const commandInput = document.getElementById('command-input');
    const executeCommandBtn = document.getElementById('execute-command-btn');
    const analysisResults = document.getElementById('analysis-results');
    const analysisSummary = document.getElementById('analysis-summary');
    const suggestedChanges = document.getElementById('suggested-changes');
    const suggestedCommands = document.getElementById('suggested-commands'); // New element for suggested commands
    const applyAllChangesBtn = document.getElementById('apply-all-changes-btn');
    const closeAnalysisBtn = document.getElementById('close-analysis-btn');
    const commandOutput = document.getElementById('command-output');
    const commandOutputText = document.getElementById('command-output-text');
    const closeOutputBtn = document.getElementById('close-output-btn');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingMessage = document.getElementById('loading-message');
    const apiKeyInput = document.getElementById('api-key-input');
    const saveApiKeyBtn = document.getElementById('save-api-key-btn');
    const apiKeyStatus = document.getElementById('api-key-status');
    const resolve_error = document.getElementById('resolve_command_error');

    // State
    const state = {
        projectPath: '',
        command_output_f: '',
        superagent: false,
        initial_query: "",
        files: [],
        openFiles: {},  // Map of file paths to their contents
        activeFile: null,
        pendingChanges: {},  // Map of file paths to their pending changes
        pendingCommands: []  // Array of suggested commands
    };

    // Initialize highlight.js
    hljs.configure({
        languages: ['javascript', 'python', 'html', 'css', 'json', 'bash']
    });

    // File Icons mapping based on extension
    const fileIcons = {
        js: 'fab fa-js-square',
        py: 'fab fa-python',
        html: 'fab fa-html5',
        css: 'fab fa-css3-alt',
        json: 'fas fa-code',
        md: 'fas fa-file-alt',
        txt: 'fas fa-file-alt',
        default: 'fas fa-file-code'
    };

    // Helper to get file icon based on extension
    function getFileIcon(filePath) {
        const ext = filePath.split('.').pop().toLowerCase();
        return fileIcons[ext] || fileIcons.default;
    }

    // Helper to show loading overlay with a message
    function showLoading(message = 'Processing your request...') {
        loadingMessage.textContent = message;
        loadingOverlay.classList.remove('hidden');
    }

    // Helper to hide loading overlay
    function hideLoading() {
        loadingOverlay.classList.add('hidden');
    }

    // Helper to show notifications
    function showNotification(message, type = 'info') {
        // Simple notification implementation
        const notification = document.createElement('div');
        notification.textContent = message;
        notification.style.position = 'fixed';
        notification.style.bottom = '20px';
        notification.style.right = '20px';
        notification.style.padding = '10px 15px';
        notification.style.borderRadius = '4px';
        notification.style.zIndex = '1001';
        notification.style.maxWidth = '300px';

        // Set color based on type
        if (type === 'success') {
            notification.style.backgroundColor = '#10b981';
        } else if (type === 'error') {
            notification.style.backgroundColor = '#ef4444';
        } else {
            notification.style.backgroundColor = '#3b82f6';
        }
        notification.style.color = 'white';

        document.body.appendChild(notification);

        // Remove notification after 3 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.5s';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 500);
        }, 3000);
    }

    // Helper to make API requests
    async function apiRequest(endpoint, method = 'GET', body = null) {
        try {
            const options = {
                method,
                headers: {
                    'Content-Type': 'application/json'
                }
            };

            if (body) {
                options.body = JSON.stringify(body);
            }

            const response = await fetch(`/api/${endpoint}`, options);
            const data = await response.json();

            if (!data.success) {
                throw new Error(data.message || 'API request failed');
            }

            return data;
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            showNotification(error.message || 'An error occurred', 'error');
            throw error;
        }
    }

    // Set project path
    async function setProjectPath() {
        const path = projectPathInput.value.trim();
        if (!path) {
            showNotification('Please enter a valid project path', 'error');
            return;
        }

        try {
            showLoading('Setting project path...');
            await apiRequest('set-project-path', 'POST', { path });
            state.projectPath = path;
            showNotification('Project path set successfully', 'success');
            refreshFileList();
        } catch (error) {
            // Error is already logged and shown in apiRequest
        } finally {
            hideLoading();
        }
    }

    // Refresh file list
    async function refreshFileList() {
        try {
            showLoading('Loading files...');
            const data = await apiRequest('list-files');
            state.files = data.files || [];
            renderFileList();
        } catch (error) {
            // Error is already logged and shown in apiRequest
        } finally {
            hideLoading();
        }
    }

    async function saveApiKey() {
        const apiKey = apiKeyInput.value.trim();
        if (!apiKey) {
            showNotification('Please enter a valid API key', 'error');
            return;
        }

        try {
            showLoading('Saving API key...');
            const response = await apiRequest('set-api-key', 'POST', { api_key: apiKey });

            // Update status indicator
            apiKeyStatus.textContent = 'API key saved and verified';
            apiKeyStatus.className = 'api-key-status success';
            apiKeyStatus.style.backgroundColor = 'rgba(47, 255, 71, 0.586)';


            showNotification('API key saved successfully', 'success');
        } catch (error) {
            // Error is already logged and shown in apiRequest
            apiKeyStatus.textContent = 'Failed to save API key: ' + error.message;
            apiKeyStatus.className = 'api-key-status error';
        } finally {
            hideLoading();
        }
    }

    // Render file list in the sidebar
    function renderFileList() {
        fileList.innerHTML = '';

        if (state.files.length === 0) {
            const noFilesMsg = document.createElement('div');
            noFilesMsg.className = 'file-item';
            noFilesMsg.textContent = 'No files found';
            fileList.appendChild(noFilesMsg);
            return;
        }

        // Filter files based on search
        const searchTerm = fileSearch.value.toLowerCase();
        const filteredFiles = searchTerm
            ? state.files.filter(file => file.toLowerCase().includes(searchTerm))
            : state.files;

        // Sort files - directories first, then alphabetically
        filteredFiles.sort((a, b) => {
            const aIsDir = a.includes('/');
            const bIsDir = b.includes('/');

            if (aIsDir && !bIsDir) return -1;
            if (!aIsDir && bIsDir) return 1;

            return a.localeCompare(b);
        });

        // Group files by directory
        const filesByDir = {};
        filteredFiles.forEach(file => {
            const parts = file.split('/');
            if (parts.length === 1) {
                // Root file
                if (!filesByDir['root']) filesByDir['root'] = [];
                filesByDir['root'].push(file);
            } else {
                // Files in directories
                const dir = parts.slice(0, -1).join('/');
                if (!filesByDir[dir]) filesByDir[dir] = [];
                filesByDir[dir].push(file);
            }
        });

        // Render directories and files
        Object.keys(filesByDir).sort().forEach(dir => {
            if (dir !== 'root') {
                const dirItem = document.createElement('div');
                dirItem.className = 'file-item';
                dirItem.innerHTML = `<i class="fas fa-folder"></i> ${dir}`;
                fileList.appendChild(dirItem);
            }

            filesByDir[dir].forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.dataset.path = file;

                // Add indentation for files in directories
                const indentation = dir !== 'root' ? ' style="padding-left: 24px;"' : '';

                fileItem.innerHTML = `
                    <div${indentation}>
                        <i class="${getFileIcon(file)}"></i>
                        ${file.split('/').pop()}
                    </div>
                `;

                if (state.activeFile === file) {
                    fileItem.classList.add('selected');
                }

                fileItem.addEventListener('click', () => openFile(file));
                fileList.appendChild(fileItem);
            });
        });
    }

    // Open a file in the editor

    // Create a new file tab
    function createFileTab(filePath) {
        const fileTab = document.createElement('div');
        fileTab.className = 'file-tab';
        fileTab.dataset.path = filePath;

        const fileName = filePath.split('/').pop();
        fileTab.innerHTML = `
            <i class="${getFileIcon(filePath)}"></i>
            <span>${fileName}</span>
            <span class="file-tab-close"><i class="fas fa-times"></i></span>
        `;

        // Add click event to switch to this tab
        fileTab.addEventListener('click', (e) => {
            // Don't switch if clicking the close button
            if (!e.target.closest('.file-tab-close')) {
                switchToFile(filePath);
            }
        });

        // Add click event to close button
        const closeBtn = fileTab.querySelector('.file-tab-close');
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            closeFileTab(filePath);
        });

        fileTabs.appendChild(fileTab);
    }

    // Switch to a specific file
    // Close a file tab
    function closeFileTab(filePath) {
        // Check if the file exists in open files
        if (!state.openFiles.hasOwnProperty(filePath)) {
            console.warn(`Attempted to close non-existent file: ${filePath}`);
            return;
        }

        // Remove file from open files
        delete state.openFiles[filePath];

        // Remove tab from DOM
        const tab = document.querySelector(`.file-tab[data-path="${CSS.escape(filePath)}"]`);
        if (tab) {
            tab.remove();
        }

        // If we closed the active file
        if (state.activeFile === filePath) {
            // Set active file to the next available tab, or null if none
            const remainingTabs = document.querySelectorAll('.file-tab');
            if (remainingTabs.length > 0) {
                // Get the path of the next tab
                const nextFilePath = remainingTabs[0].dataset.path;

                // Verify that the next file exists in our open files
                if (state.openFiles.hasOwnProperty(nextFilePath)) {
                    switchToFile(nextFilePath);
                } else {
                    // Handle case where file data doesn't match DOM
                    resetEditor();
                }
            } else {
                // No tabs left, reset the editor
                resetEditor();
            }
        }
    }

    // Helper function to reset editor state when no files are open
    function resetEditor() {
        state.activeFile = null;
        editorPlaceholder.classList.remove('hidden');
        editorContent.classList.add('hidden');
        fileEditor.value = ''; // Clear the editor content
        codeMirrorEditor.setValue(fileEditor.value)

        // Clear any active selection in the file list
        document.querySelectorAll('.file-item.selected').forEach(item => {
            item.classList.remove('selected');
        });
    }

    // Modify switchToFile to handle potential edge cases
    function switchToFile(filePath) {
        // Verify the file exists in our open files
        if (!state.openFiles.hasOwnProperty(filePath)) {
            console.warn(`Attempted to switch to non-existent file: ${filePath}`);
            resetEditor();
            return;
        }

        // Update active file state
        state.activeFile = filePath;

        // Update file editor content - ensure it's not undefined
        fileEditor.value = state.openFiles[filePath] || '';
        codeMirrorEditor.setValue(fileEditor.value);
        // Show editor content, hide placeholder
        editorPlaceholder.classList.add('hidden');
        editorContent.classList.remove('hidden');

        // Update active tab
        document.querySelectorAll('.file-tab').forEach(tab => {
            if (tab.dataset.path === filePath) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Update selected file in the file list
        document.querySelectorAll('.file-item').forEach(item => {
            if (item.dataset.path === filePath) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
    }

    // Modify openFile to handle potential issues
    async function openFile(filePath) {
        try {
            // Check if file is already open
            if (state.openFiles[filePath] || state.openFiles[filePath]=='') {
                switchToFile(filePath);
                return;
            }
            console.log(state.openFiles);
            console.log(filePath)

            showLoading(`Loading ${filePath}...`);
            const data = await apiRequest('read-file', 'POST', { path: filePath });

            // Validate file content
            const fileContent = data.content || '';

            // Add to open files
            state.openFiles[filePath] = fileContent;

            // Create new tab
            createFileTab(filePath);

            // Switch to the file
            switchToFile(filePath);

            codeMirrorEditor.setValue(fileContent);

            showNotification(`File ${filePath} opened`, 'success');
        } catch (error) {
            // Error is already logged and shown in apiRequest
            // If we failed to open the file, ensure it's not in our state
            delete state.openFiles[filePath];
        } finally {
            hideLoading();
        }
    }

    // Close a file tab

    // Save current file
    async function saveCurrentFile() {
        if (!state.activeFile) {
            showNotification('No file is currently open', 'error');
            return;
        }
        const cont = codeMirrorEditor.getValue();
        const content = cont;

        try {
            showLoading(`Saving ${state.activeFile}...`);
            await apiRequest('write-file', 'POST', {
                path: state.activeFile,
                content: content
            });

            // Update in-memory content
            state.openFiles[state.activeFile] = content;

            showNotification(`File ${state.activeFile} saved successfully`, 'success');
        } catch (error) {
            // Error is already logged and shown in apiRequest
        } finally {
            hideLoading();
        }
    }

    // Analyze project based on prompt
    async function analyzeProject() {
        const prompt = userPrompt.value.trim();
        if (!prompt) {
            showNotification('Please enter a prompt describing what you want to achieve', 'error');
            return;
        }
        state.initial_query = userPrompt.value.trim();

        if (document.getElementById('super-agent').classList.contains('active')) {
            state.superagent = true;
        }
        else {
            state.superagent = false;
        }
        // console.log(state.superagent);
        // Get files to analyze (either selected files or all open files)
        const filesToAnalyze = Object.keys(state.openFiles);
        try {
            if (filesToAnalyze.length === 0) {
                // showNotification('Please open at least one file to analyze', 'error');

                showLoading('Analyzing project and generating suggestions...');
                const data = await apiRequest('analyze', 'POST', {
                    prompt: prompt,
                    files: [],
                    filenames: state.files
                });
                // console.log("app.py return ",data.data);
                // Display analysis results
                renderAnalysisResults(data.data);
                if (state.superagent == true) {
                    window.initialQuery = state.initial_query; // Make this accessible globally
                    window.commandOutput = state.command_output_f;
                    if (isStreaming == false) {
                        startStream()
                    }
                    else {
                        window.vison_stop_agent == "False"
                    }
                    // stopAllCommands()
                    await applyAllChanges()
                    await runAllPendingCommands()
                    setTimeout(function () {
                        if ((data.data.need_intervention == 'False' || data.data.need_intervention == false) && (window.vison_stop_agent == false || window.vison_stop_agent == 'False')) {
                            resolveerror()
                        }
                    }, 5000);
                }
                // if (state.superagent == true) {
                //     window.initialQuery = state.initial_query; // Make this accessible globally
                //     window.commandOutput = state.command_output_f; 
                //     startStream()
                //     setTimeout(applyAllChanges, 2000);
                //     setTimeout(runAllPendingCommands, 7000);
                //     setTimeout(function() {
                //         if ((data.data.need_intervention == 'False' || data.data.need_intervention == false) && ( window.vison_stop_agent == false || window.vison_stop_agent=='False')) {
                //             resolveerror()
                //         }
                //     }, 10000);
                // }
            }
            else {
                showLoading('Analyzing project and generating suggestions...');
                const data = await apiRequest('analyze', 'POST', {
                    prompt: prompt,
                    files: filesToAnalyze,
                    filenames: state.files
                });
                // console.log(data.data);
                // Display analysis results
                renderAnalysisResults(data.data);
                if (state.superagent == true) {
                    window.initialQuery = state.initial_query; // Make this accessible globally
                    window.commandOutput = state.command_output_f;
                    if (isStreaming == false) {
                        startStream()
                    }
                    else {
                        window.vison_stop_agent == 'False'
                    }
                    await applyAllChanges()
                    await comm
                    await runAllPendingCommands()
                    setTimeout(function () {
                        if ((data.data.need_intervention == 'False' || data.data.need_intervention == false) && (window.vison_stop_agent == false || window.vison_stop_agent == 'False')) {
                            resolveerror()
                        }
                    }, 5000);
                }
                // if (state.superagent == true) {
                //     window.initialQuery = state.initial_query; // Make this accessible globally
                //     window.commandOutput = state.command_output_f; 
                //     startStream()
                //     setTimeout(applyAllChanges, 1000);
                //     setTimeout(runAllPendingCommands, 3000);
                //     setTimeout(function() {
                //         if ((data.data.need_intervention == 'False' || data.data.need_intervention == false) && ( window.vison_stop_agent == false || window.vison_stop_agent=='False')) {
                //             resolveerror()
                //         }
                //     }, 10000);
                // }
            }
        } catch (error) {
            // Error is already logged and shown in apiRequest
        } finally {
            hideLoading();
        }
    }

    // Render analysis results
    function renderAnalysisResults(results) {
        // Clear previous results
        analysisSummary.innerHTML = '';
        suggestedChanges.innerHTML = '';
        if (suggestedCommands) {
            suggestedCommands.innerHTML = '';
        }

        // Add summary
        analysisSummary.innerHTML = marked.parse(results.summary) || 'Analysis complete. No summary provided.';

        // Check if we have changes
        if (!results.changes || results.changes.length === 0) {
            suggestedChanges.innerHTML = '<p>No changes suggested.</p>';
            applyAllChangesBtn.disabled = true;
        } else {
            // Reset pending changes
            state.pendingChanges = {};

            // Render each change
            results.changes.forEach((change, index) => {
                const changeItem = document.createElement('div');
                changeItem.className = 'change-item';
                changeItem.dataset.index = index;

                const header = document.createElement('div');
                header.className = 'change-item-header';

                const body = document.createElement('div');
                body.className = 'change-item-body';

                // Add file path to header
                const filePath = document.createElement('div');
                filePath.className = 'change-file-path';
                filePath.textContent = change.file;
                header.appendChild(filePath);

                // Add actions to header
                const actions = document.createElement('div');
                actions.className = 'change-actions';

                const applyBtn = document.createElement('button');
                applyBtn.className = 'secondary-btn';
                applyBtn.innerHTML = '<i class="fas fa-check"></i> Apply';
                applyBtn.addEventListener('click', () => applyChange(change.file, change.modified));
                actions.appendChild(applyBtn);

                const viewBtn = document.createElement('button');
                viewBtn.className = 'secondary-btn';
                viewBtn.innerHTML = '<i class="fas fa-eye"></i> View';
                viewBtn.addEventListener('click', () => {
                    // Toggle visibility of the body
                    body.classList.toggle('hidden');

                    // Change button text based on visibility
                    if (body.classList.contains('hidden')) {
                        viewBtn.innerHTML = '<i class="fas fa-eye"></i> View';
                    } else {
                        viewBtn.innerHTML = '<i class="fas fa-eye-slash"></i> Hide';
                    }
                });
                actions.appendChild(viewBtn);

                header.appendChild(actions);

                // Add explanation to body
                if (change.explanation) {
                    const explanation = document.createElement('div');
                    explanation.className = 'change-explanation';
                    explanation.innerHTML = marked.parse(change.explanation);
                    body.appendChild(explanation);
                }

                // Add code diff to body
                if (change.original && change.modified) {
                    // Create diff viewer
                    const diffContainer = document.createElement('div');
                    diffContainer.className = 'code-diff';

                    // Simple diff view: show both original and modified
                    const diffContent = document.createElement('div');
                    diffContent.style.display = 'flex';
                    diffContent.style.flexDirection = 'column';
                    diffContent.style.gap = '10px';

                    // Original code
                    const originalCode = document.createElement('div');
                    originalCode.innerHTML = `
                        <div style="padding: 8px; background-color: #303540; color: #e06c75; font-weight: 500; overflow-x:auto">Original</div>
                        <pre style="margin: 0; padding: 12px; overflow-x:auto"><code>${hljs.highlight(change.original, { language: 'python' }).value}</code></pre>
                    `;

                    // Modified code
                    const modifiedCode = document.createElement('div');
                    modifiedCode.innerHTML = `
                        <div style="padding: 8px; background-color: #303540; color: #98c379; font-weight: 500;overflow-x:auto">Modified</div>
                        <pre style="margin: 0; padding: 12px;overflow-x:auto"><code>${hljs.highlight(change.modified, { language: 'python' }).value}</code></pre>
                    `;

                    diffContent.appendChild(originalCode);
                    diffContent.appendChild(modifiedCode);
                    diffContainer.appendChild(diffContent);
                    body.appendChild(diffContainer);
                }

                // Hide body by default
                body.classList.add('hidden');

                // Add header and body to change item
                changeItem.appendChild(header);
                changeItem.appendChild(body);

                // Add change item to container
                suggestedChanges.appendChild(changeItem);

                // Store pending change
                state.pendingChanges[change.file] = change.modified;
            });

            // Enable apply all button
            applyAllChangesBtn.disabled = false;
        }

        // Check if we have commands
        if (results.commands && results.commands.length > 0) {
            // Reset pending commands
            state.pendingCommands = results.commands;

            // Create commands section header
            const commandsHeader = document.createElement('h3');
            commandsHeader.textContent = 'Suggested Commands';
            commandsHeader.className = 'section-title';
            suggestedCommands.appendChild(commandsHeader);

            // Render each command
            results.commands.forEach((command, index) => {
                const commandItem = document.createElement('div');
                commandItem.className = 'command-item';
                commandItem.dataset.index = index;

                const header = document.createElement('div');
                header.className = 'command-item-header';

                // Add command text to header
                const commandText = document.createElement('div');
                commandText.className = 'command-text';
                commandText.textContent = command.command;
                header.appendChild(commandText);

                // Add actions to header
                const actions = document.createElement('div');
                actions.className = 'command-actions';

                const runBtn = document.createElement('button');
                runBtn.className = 'secondary-btn';
                runBtn.innerHTML = '<i class="fas fa-play"></i> Run';
                runBtn.addEventListener('click', () => runSuggestedCommand(command.command));
                actions.appendChild(runBtn);

                const requiredBadge = document.createElement('span');
                requiredBadge.className = command.isRequired ? 'badge required' : 'badge optional';
                requiredBadge.textContent = command.isRequired ? 'Required' : 'Optional';
                actions.appendChild(requiredBadge);

                header.appendChild(actions);

                // Add explanation if available
                if (command.explanation) {
                    const explanation = document.createElement('div');
                    explanation.className = 'command-explanation';
                    explanation.innerHTML = marked.parse(command.explanation);
                    commandItem.appendChild(explanation);
                }

                // Add header to command item
                commandItem.appendChild(header);

                // Add command item to container
                suggestedCommands.appendChild(commandItem);
            });
        } else if (suggestedCommands) {
            suggestedCommands.innerHTML = '<p>No commands suggested.</p>';
        }

        // Show analysis results section
        analysisResults.classList.remove('hidden');
    }

    // Apply a single change
    async function applyChange(filePath, newContent) {
        try {
            showLoading(`Applying changes to ${filePath}...`);

            // Write changes to file
            await apiRequest('write-file', 'POST', {
                path: filePath,
                content: newContent
            });

            // Update if file is open
            if (state.openFiles[filePath]) {
                state.openFiles[filePath] = newContent;

                // Update editor content if this is the active file
                if (state.activeFile === filePath) {
                    fileEditor.value = newContent;
                    codeMirrorEditor.setValue(newContent);
                }
            } else {
                openFile(filePath)
            }

            showNotification(`Changes applied to ${filePath}`, 'success');
            refreshFileList()
        } catch (error) {
            // Error is already logged and shown in apiRequest
        } finally {
            hideLoading();
        }
    }

    // Run a suggested command
    async function runSuggestedCommand(command) {
        try {
            showLoading(`Running command: ${command}`);
            const data = await apiRequest('run-command', 'POST', { command });
            window.intervalID = setInterval(listActiveCommands, 5000);
            // Display command output
            commandOutputText.textContent = data.stdout || '';
            if (data.stderr) {
                commandOutputText.textContent += '\n\n' + data.stderr;
            }

            // Add return code
            commandOutputText.textContent += `\n\nExit code: ${data.returncode}`;
            state.command_output_f = commandOutputText.textContent;
            // Show output section
            commandOutput.classList.remove('hidden');

            showNotification(`Command executed: ${command}`, 'success');
        } catch (error) {
            // Error is already logged and shown in apiRequest
        } finally {
            hideLoading();
        }
    }

    // Apply all changes
    async function applyAllChanges() {
        const pendingFiles = Object.keys(state.pendingChanges);
        if (pendingFiles.length === 0) {
            showNotification('No changes to apply', 'info');
            return;
        }

        try {
            showLoading('Applying all changes...');

            // Apply each change sequentially
            for (const filePath of pendingFiles) {
                const newContent = state.pendingChanges[filePath];

                // Write changes to file
                await apiRequest('write-file', 'POST', {
                    path: filePath,
                    content: newContent
                });

                // Update if file is open
                if (state.openFiles[filePath]) {
                    state.openFiles[filePath] = newContent;

                    // Update editor content if this is the active file
                    if (state.activeFile === filePath) {
                        fileEditor.value = newContent;
                        codeMirrorEditor.setValue(fileEditor.value)

                    }
                } else {
                    openFile(filePath)
                }

            }

            showNotification(`Applied changes to ${pendingFiles.length} files`, 'success');

            // Clear pending changes
            state.pendingChanges = {};

            // Hide analysis results
            // analysisResults.classList.add('hidden');
        } catch (error) {
            // Error is already logged and shown in apiRequest
        } finally {
            hideLoading();
        }
    }

    // Run all pending commands
    async function runAllPendingCommands() {
        if (state.pendingCommands.length === 0) {
            showNotification('No commands to run', 'info');
            return;
        }

        try {
            showLoading('Running all suggested commands...');

            // Store all command outputs
            let combinedOutput = '';

            // Run each command sequentially
            for (const commandObj of state.pendingCommands) {
                const command = commandObj.command;

                // Show which command is currently running
                loadingMessage.textContent = `Running command: ${command}`;

                // Execute the command
                const data = await apiRequest('run-command', 'POST', { command });

                // Build command output
                let commandOutput = `\n\n=== COMMAND: ${command} ===\n`;
                commandOutput += data.stdout || '';
                if (data.stderr) {
                    commandOutput += '\n\n' + data.stderr;
                }
                commandOutput += `\n\nExit code: ${data.returncode}`;

                // Add to combined output
                combinedOutput += commandOutput;
            }

            // Display combined command output
            commandOutputText.textContent = combinedOutput.trim();
            state.command_output_f = combinedOutput.trim();

            // Show output section
            commandOutput.classList.remove('hidden');

            showNotification(`Executed ${state.pendingCommands.length} commands`, 'success');
        } catch (error) {
            // Error is already logged and shown in apiRequest
        } finally {
            hideLoading();
        }
    }

    // Run a command
    async function runCommand() {
        // Show command input
        commandInputContainer.classList.remove('hidden');
        commandInput.focus();
    }

    // Execute the command
    async function executeCommand() {
        const command = commandInput.value.trim();
        if (!command) {
            showNotification('Please enter a command to execute', 'error');
            return;
        }

        try {
            showLoading(`Running command: ${command}`);
            state.intervalID = setInterval(listActiveCommands, 5000);
            const data = await apiRequest('run-command', 'POST', { command });

            // Display command output
            commandOutputText.textContent = data.stdout || '';
            if (data.stderr) {
                commandOutputText.textContent += '\n\n' + data.stderr;
            }

            // Add return code
            commandOutputText.textContent += `\n\nExit code: ${data.returncode}`;

            // Show output section
            commandOutput.classList.remove('hidden');

            // Hide command input
            commandInputContainer.classList.add('hidden');
            commandInput.value = '';
        } catch (error) {
            // Error is already logged and shown in apiRequest
        } finally {
            hideLoading();
        }
    }

    // Close analysis results
    function closeAnalysis() {
        analysisResults.classList.add('hidden');
    }

    // Close command output
    function closeOutput() {
        commandOutput.classList.add('hidden');
    }

    // Search files on input change
    function searchFiles() {
        renderFileList();
    }

    // Add event listeners
    setPathBtn.addEventListener('click', setProjectPath);
    refreshFilesBtn.addEventListener('click', refreshFileList);
    fileSearch.addEventListener('input', searchFiles);
    saveFileBtn.addEventListener('click', saveCurrentFile);
    analyzeBtn.addEventListener('click', analyzeProject);
    runCommandBtn.addEventListener('click', runCommand);
    executeCommandBtn.addEventListener('click', executeCommand);
    applyAllChangesBtn.addEventListener('click', applyAllChanges);
    closeAnalysisBtn.addEventListener('click', closeAnalysis);
    closeOutputBtn.addEventListener('click', closeOutput);
    saveApiKeyBtn.addEventListener('click', saveApiKey);
    resolve_error.addEventListener('click', resolveerror);

    async function resolveerror() {
        await stopAllCommands();
        userPrompt.value = "desired task:\n" + userPrompt.value + "command output: " + state.command_output_f + "\n\n " + window.live_command_output + "\n vision model output: \n" + window.summary_vision;
        window.commandOutput = state.command_output_f;
        if (window.vison_stop_agent == 'False' || window.vison_stop_agent == false) {
            await analyzeProject();
        }
    }

    // Allow Enter key to submit command
    commandInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            executeCommand();
        }
    });

    async function checkApiKeyStatus() {
        try {
            const response = await apiRequest('check-api-key', 'GET');
            if (response.is_configured) {
                apiKeyStatus.textContent = 'API key is configured';
                apiKeyStatus.className = 'api-key-status success';
                apiKeyStatus.style.backgroundColor = 'rgba(47, 255, 71, 0.586)'; // Change text color to the provided RGBA value
                // document.body.style.backgroundColor = 'rgba(47, 255, 71, 0.586)'; // Change background to the provided RGBA value
            } else {
                apiKeyStatus.textContent = 'No API key is configured';
                apiKeyStatus.className = 'api-key-status warning';
                apiKeyStatus.style.backgroundColor = 'rgba(255, 47, 47, 0.586)'; // Change text color to a different RGBA value
                // document.body.style.backgroundColor = 'rgba(255, 47, 47, 0.586)'; // Change background to a different RGBA value
            }

        } catch (error) {
            console.error('Error checking API key status:', error);
        }
    }

    // Initialize the app
    function init() {
        // Try to restore project path from session
        // This would be implemented on the server side
        refreshFileList();
        checkApiKeyStatus();
        window.vison_stop_agent = 'False'
        window.live_command_output=""
    }

    // Start the app
    init();
});