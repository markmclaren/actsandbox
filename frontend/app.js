/* ==========================================================================
   ActSandbox Frontend Client Logic
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // UI Element Selectors
    const providerSelect = document.getElementById('provider-select');
    const baseUrlInput = document.getElementById('base-url-input');
    const modelInput = document.getElementById('model-input');
    const apiKeyInput = document.getElementById('api-key-input');
    
    const sandboxSelect = document.getElementById('sandbox-select');
    const dockerImageInput = document.getElementById('docker-image-input');
    const e2bKeyInput = document.getElementById('e2b-key-input');
    const e2bKeyGroup = document.getElementById('e2b-key-group');
    const dockerImageGroup = document.getElementById('docker-image-group');
    const hitlToggle = document.getElementById('hitl-toggle');
    const saveConfigBtn = document.getElementById('save-config-btn');
    
    const fileExplorerTree = document.getElementById('file-explorer-tree');
    const refreshFilesBtn = document.getElementById('refresh-files-btn');
    
    const taskPromptInput = document.getElementById('task-prompt-input');
    const startTaskBtn = document.getElementById('start-task-btn');
    const stopTaskBtn = document.getElementById('stop-task-btn');
    
    const connectionStatus = document.getElementById('connection-status');
    const stepCounter = document.getElementById('step-counter');
    const agentStatusBanner = document.getElementById('agent-status-banner');
    const timelineStream = document.getElementById('timeline-stream');
    const terminalLogs = document.getElementById('terminal-logs');
    const clearTerminalBtn = document.getElementById('clear-terminal-btn');
    
    // Tab toggles
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Previewer Selectors
    const previewFilename = document.getElementById('preview-filename');
    const previewFilesize = document.getElementById('preview-filesize');
    const previewCodeBlock = document.getElementById('preview-code-block');
    const previewImageContainer = document.getElementById('preview-image-container');
    const previewImage = document.getElementById('preview-image');
    const previewEmptyState = document.getElementById('preview-empty-state');
    const previewMarkdownBlock = document.getElementById('preview-markdown-block');
    
    // HITL Modal Selectors
    const hitlModal = document.getElementById('hitl-modal');
    const hitlStepNumber = document.getElementById('hitl-step-number');
    const hitlCommandTextarea = document.getElementById('hitl-command-textarea');
    const hitlApproveBtn = document.getElementById('hitl-approve-btn');
    const hitlRejectBtn = document.getElementById('hitl-reject-btn');
    const hitlEditBtn = document.getElementById('hitl-edit-btn');
    const rejectionReasonContainer = document.getElementById('rejection-reason-container');
    const rejectionReasonInput = document.getElementById('rejection-reason-input');

    // State Variables
    let socket = null;
    let currentConfig = null;
    let isTaskRunning = false;
    let selectedFilePath = null;
    let rejectionMode = false;
    let hitlStep = 1;
    let originalModelValue = '';

    // Initialize Page
    init();

    async function init() {
        setupTabNavigation();
        setupSandboxToggle();
        setupProviderToggle();
        await loadConfiguration();
        setupWebSocketConnection();
        loadWorkspaceFiles();
        
        // Trigger live local models fetch on load
        if (providerSelect.value === 'local') {
            refreshLocalModelsList();
        }
        
        // Focus Clear-Filter Trick: Clear value temporarily on focus so browser displays all options
        modelInput.addEventListener('focus', () => {
            originalModelValue = modelInput.value;
            modelInput.value = ''; 
            
            if (providerSelect.value === 'local') {
                refreshLocalModelsList();
            }
        });
        
        modelInput.addEventListener('blur', () => {
            // Restore previous value after a short delay so datalist click events can register
            setTimeout(() => {
                if (!modelInput.value) {
                    modelInput.value = originalModelValue;
                }
            }, 180);
        });
        
        // Button Click Event Listeners
        saveConfigBtn.addEventListener('click', saveConfiguration);
        refreshFilesBtn.addEventListener('click', loadWorkspaceFiles);
        startTaskBtn.addEventListener('click', startAgentTask);
        stopTaskBtn.addEventListener('click', stopAgentTask);
        clearTerminalBtn.addEventListener('click', () => {
            terminalLogs.innerHTML = '';
            appendTerminalLine('Terminal cleared.', 'system-msg');
        });
        
        // HITL modal listeners
        hitlApproveBtn.addEventListener('click', approveCommand);
        hitlRejectBtn.addEventListener('click', rejectCommand);
        hitlEditBtn.addEventListener('click', toggleEditCommandMode);
    }

    // Tab Navigation logic
    function setupTabNavigation() {
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.getAttribute('data-tab');
                
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                button.classList.add('active');
                document.getElementById(targetTab).classList.add('active');
            });
        });
    }

    // Toggle execution sandbox fields
    function setupSandboxToggle() {
        sandboxSelect.addEventListener('change', () => {
            if (sandboxSelect.value === 'e2b') {
                e2bKeyGroup.classList.remove('hidden');
                dockerImageGroup.classList.add('hidden');
            } else {
                e2bKeyGroup.classList.add('hidden');
                dockerImageGroup.classList.remove('hidden');
            }
        });
    }

    // Toggle LLM Provider inputs (defaults helper)
    function setupProviderToggle() {
        providerSelect.addEventListener('change', () => {
            const val = providerSelect.value;
            if (val === 'local') {
                baseUrlInput.value = 'http://localhost:12434/engines/v1/chat/completions';
                modelInput.placeholder = 'docker.io/gemma4:latest';
                modelInput.value = 'docker.io/gemma4:latest';
                document.getElementById('url-group').classList.remove('hidden');
                document.getElementById('api-key-group').classList.remove('hidden');
                refreshLocalModelsList();
            } else if (val === 'gemini') {
                baseUrlInput.value = 'https://generativelanguage.googleapis.com/v1beta/openai/';
                modelInput.placeholder = 'gemini-2.5-flash';
                modelInput.value = 'gemini-2.5-flash';
                document.getElementById('url-group').classList.add('hidden');
                document.getElementById('api-key-group').classList.remove('hidden');
            } else if (val === 'openai') {
                baseUrlInput.value = '';
                modelInput.placeholder = 'gpt-4o-mini';
                modelInput.value = 'gpt-4o-mini';
                document.getElementById('url-group').classList.add('hidden');
                document.getElementById('api-key-group').classList.remove('hidden');
            }
        });
    }

    // Dynamic model fetch and UI datalist renderer
    async function refreshLocalModelsList() {
        try {
            const datalist = document.getElementById('model-options');
            if (!datalist) return;
            
            // Clear existing options
            datalist.innerHTML = '';
            
            const isLocal = (providerSelect.value === 'local');
            
            if (isLocal) {
                let liveModels = [];
                try {
                    const res = await fetch('/api/local-models');
                    if (res.ok) {
                        const data = await res.json();
                        if (data.status === 'success' && data.models) {
                            liveModels = data.models;
                        }
                    }
                } catch (fetchErr) {
                    console.warn("Background model fetch failed:", fetchErr);
                }
                
                // Add STRICTLY the live fetched local models!
                liveModels.forEach(modelName => {
                    const opt = document.createElement('option');
                    opt.value = modelName;
                    opt.textContent = `${modelName} (Local Docker Model)`;
                    datalist.appendChild(opt);
                });
                
                if (liveModels.length > 0) {
                    console.log(`[Frontend] Successfully loaded ${liveModels.length} live models from local host!`);
                } else {
                    // Fallback to default if no local models are detected yet
                    const opt = document.createElement('option');
                    opt.value = "docker.io/gemma4:latest";
                    opt.textContent = "docker.io/gemma4:latest (Default Local Gemma 4)";
                    datalist.appendChild(opt);
                }
            } else {
                // Show ONLY the specific cloud recommendations for Gemini or OpenAI
                const fallbacks = [];
                if (providerSelect.value === 'gemini') {
                    fallbacks.push({ val: "gemini-2.5-flash", text: "gemini-2.5-flash (Gemini 2.5 Flash)" });
                    fallbacks.push({ val: "gemini-2.5-pro", text: "gemini-2.5-pro (Gemini 2.5 Pro)" });
                } else if (providerSelect.value === 'openai') {
                    fallbacks.push({ val: "gpt-4o", text: "gpt-4o (OpenAI GPT-4o)" });
                    fallbacks.push({ val: "gpt-4o-mini", text: "gpt-4o-mini (OpenAI GPT-4o-mini)" });
                }
                
                fallbacks.forEach(fb => {
                    const opt = document.createElement('option');
                    opt.value = fb.val;
                    opt.textContent = fb.text;
                    datalist.appendChild(opt);
                });
            }
        } catch (err) {
            console.warn("Could not fetch models list:", err);
        }
    }

    // REST API calls: Config management
    async function loadConfiguration() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();
            currentConfig = data;
            
            // Map values to fields
            providerSelect.value = data.provider;
            baseUrlInput.value = data.base_url;
            modelInput.value = data.model;
            apiKeyInput.value = data.api_key;
            sandboxSelect.value = data.sandbox_type;
            dockerImageInput.value = data.docker_image;
            e2bKeyInput.value = data.e2b_api_key;
            hitlToggle.checked = data.hitl_enabled;
            
            // Trigger UI updates
            sandboxSelect.dispatchEvent(new Event('change'));
        } catch (err) {
            console.error("Error loading config:", err);
            appendTerminalLine("Error loading saved configurations from backend.", "err-msg");
        }
    }

    async function saveConfiguration() {
        const config = {
            provider: providerSelect.value,
            base_url: baseUrlInput.value,
            model: modelInput.value,
            api_key: apiKeyInput.value,
            sandbox_type: sandboxSelect.value,
            docker_image: dockerImageInput.value,
            e2b_api_key: e2bKeyInput.value,
            hitl_enabled: hitlToggle.checked
        };
        
        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const data = await res.json();
            if (data.status === 'success') {
                currentConfig = config;
                appendTerminalLine("Configurations successfully saved to server.", "system-msg");
                showBannerMessage("Configuration saved successfully!", "pulsing-green");
                setTimeout(() => hideBannerMessage(), 2000);
            }
        } catch (err) {
            console.error("Error saving config:", err);
            appendTerminalLine("Error saving configurations to server.", "err-msg");
        }
    }

    // WebSockets Handler
    function setupWebSocketConnection() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        connectionStatus.textContent = "Connecting...";
        connectionStatus.className = "";
        
        socket = new WebSocket(wsUrl);
        
        socket.onopen = () => {
            connectionStatus.textContent = "Online";
            connectionStatus.className = "badge neon-cyan";
            const indicator = document.querySelector('.status-indicator-dot');
            indicator.className = "status-indicator-dot pulsing-green";
            appendTerminalLine("Connected to ActSandbox backend WebSockets server.", "system-msg");
        };
        
        socket.onclose = () => {
            connectionStatus.textContent = "Offline";
            connectionStatus.className = "badge neon-violet";
            const indicator = document.querySelector('.status-indicator-dot');
            indicator.className = "status-indicator-dot pulsing-red";
            appendTerminalLine("Disconnected from ActSandbox backend WebSockets server. Retrying...", "err-msg");
            
            // Retry connection
            setTimeout(setupWebSocketConnection, 4000);
        };
        
        socket.onerror = (err) => {
            console.error("WS error:", err);
        };
        
        socket.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleAgentMessage(msg);
        };
    }

    // WebSocket Message Router
    function handleAgentMessage(msg) {
        switch (msg.type) {
            case 'status':
                updateAgentStatus(msg.message, true);
                appendTerminalLine(`[System] ${msg.message}`, 'system-msg');
                break;
                
            case 'step_start':
                hitlStep = msg.step;
                stepCounter.textContent = `Step ${msg.step}`;
                stepCounter.classList.remove('hidden');
                appendTerminalLine(`\n--- Step ${msg.step} ---`, 'system-msg');
                break;
                
            case 'thought':
                renderThoughtCard(msg);
                appendTerminalLine(`\nThoughts:\n${msg.clean_thought}`, 'cmd-sent');
                if (msg.command) {
                    appendTerminalLine(`Proposed Action:\n$ ${msg.command}`, 'cmd-sent');
                }
                break;
                
            case 'require_approval':
                showHITLModal(msg.step, msg.command);
                break;
                
            case 'observation':
                appendTerminalObservation(msg.output, msg.exit_code);
                updateThoughtCardObservation(msg.step, msg.output, msg.exit_code);
                break;
                
            case 'completed':
                renderCompletedCard(msg);
                finishTaskState();
                break;
                
            case 'error':
                renderErrorCard(msg.message);
                appendTerminalLine(`[LLM Error] ${msg.message}`, 'err-msg');
                finishTaskState();
                break;
        }
    }

    // Start Task Execution
    function startAgentTask() {
        const taskPrompt = taskPromptInput.value.trim();
        if (!taskPrompt) {
            alert("Please enter a valid task prompt first.");
            return;
        }

        if (!socket || socket.readyState !== WebSocket.OPEN) {
            alert("Websocket server is offline. Please wait for connection.");
            return;
        }

        // Clean UI
        timelineStream.innerHTML = '';
        terminalLogs.innerHTML = '';
        stepCounter.classList.add('hidden');
        appendTerminalLine("Starting CodeAct reasoning session...", "system-msg");

        // UI state toggle
        isTaskRunning = true;
        startTaskBtn.classList.add('hidden');
        stopTaskBtn.classList.remove('hidden');
        taskPromptInput.disabled = true;
        
        let modelVal = modelInput.value.trim();
        if (!modelVal && originalModelValue) {
            modelVal = originalModelValue;
            modelInput.value = originalModelValue;
        }

        // Gather current config values dynamically from UI inputs
        const liveConfig = {
            provider: providerSelect.value,
            base_url: baseUrlInput.value,
            model: modelVal || currentConfig?.model || "docker.io/gemma4:latest",
            api_key: apiKeyInput.value,
            sandbox_type: sandboxSelect.value,
            docker_image: dockerImageInput.value,
            e2b_api_key: e2bKeyInput.value,
            hitl_enabled: hitlToggle.checked
        };

        // Send config overrides & start
        const startMessage = {
            action: "start",
            task: taskPrompt,
            config: liveConfig
        };
        
        socket.send(JSON.stringify(startMessage));
        updateAgentStatus("Starting Sandbox...", true);
    }

    // Terminate Task Session
    function stopAgentTask() {
        if (socket && socket.readyState === WebSocket.OPEN) {
            // Simply closing the websocket forces the backend standard cleanup loops to run!
            // But we can also send an abort signal, or reconstruct the WS.
            // Let's close and reopen WS for absolute safety and clean cancellation.
            socket.close();
            appendTerminalLine("Task aborted. Reconnecting sandboxes...", "err-msg");
        }
        finishTaskState();
    }

    function finishTaskState() {
        isTaskRunning = false;
        startTaskBtn.classList.remove('hidden');
        stopTaskBtn.classList.add('hidden');
        taskPromptInput.disabled = false;
        stepCounter.classList.add('hidden');
        updateAgentStatus("Session Complete", false);
        loadWorkspaceFiles();
    }

    // Terminal Logging helpers
    function appendTerminalLine(text, className = '') {
        const line = document.createElement('div');
        line.className = `terminal-line ${className}`;
        line.textContent = text;
        terminalLogs.appendChild(line);
        terminalLogs.scrollTop = terminalLogs.scrollHeight;
    }

    function appendTerminalObservation(output, exitCode) {
        if (exitCode === 0) {
            appendTerminalLine(output || "[Command completed successfully with no stdout]");
        } else {
            appendTerminalLine(`Exit Code: ${exitCode}`, 'err-msg');
            appendTerminalLine(output || "[Command failed with no stdout]", 'err-msg');
        }
    }

    // UI Agent status banner
    function updateAgentStatus(text, showSpinner) {
        agentStatusBanner.classList.remove('hidden');
        const statusText = agentStatusBanner.querySelector('.status-text');
        const spinner = agentStatusBanner.querySelector('.spinner');
        
        statusText.textContent = text;
        if (showSpinner) {
            spinner.classList.remove('hidden');
        } else {
            spinner.classList.add('hidden');
        }
    }

    function showBannerMessage(text, badgeClass) {
        updateAgentStatus(text, false);
    }

    function hideBannerMessage() {
        agentStatusBanner.classList.add('hidden');
    }

    // Rendering Timeline Cards
    function renderThoughtCard(msg) {
        // Remove empty state
        const emptyState = timelineStream.querySelector('.empty-timeline-state');
        if (emptyState) emptyState.remove();

        const card = document.createElement('div');
        card.id = `thought-step-${msg.step}`;
        card.className = "timeline-card card-thought";
        
        const timestamp = new Date().toLocaleTimeString();
        
        let commandPreview = '';
        if (msg.command) {
            commandPreview = `
                <div class="timeline-command-preview">
                    <strong>🐚 Proposed Terminal Command:</strong>
                    <pre><code>$ ${escapeHtml(msg.command)}</code></pre>
                </div>
            `;
        }

        // Parse markdown content cleanly with marked library
        let renderedHtml = '';
        try {
            renderedHtml = marked.parse(msg.clean_thought);
        } catch (e) {
            renderedHtml = `<p>${escapeHtml(msg.clean_thought)}</p>`;
        }

        // Construct interactive LLM prompt history payload accordion if available
        let payloadInspectorHtml = '';
        if (msg.context_history && Array.isArray(msg.context_history)) {
            let messagesHtml = msg.context_history.map(item => {
                const roleClass = `role-${item.role}`;
                return `
                    <div class="payload-message-item">
                        <div class="payload-message-role-bar">
                            <span class="role-badge ${roleClass}">${item.role}</span>
                        </div>
                        <div class="payload-message-body">${escapeHtml(item.content)}</div>
                    </div>
                `;
            }).join('');

            payloadInspectorHtml = `
                <div class="payload-inspector-container">
                    <div class="payload-inspector-header" id="payload-header-${msg.step}">
                        <span><i class="fa-solid fa-code"></i> Inspect LLM Payload (${msg.context_history.length} messages)</span>
                        <i class="fa-solid fa-chevron-right chevron-icon"></i>
                    </div>
                    <div class="payload-inspector-content hidden" id="payload-content-${msg.step}">
                        ${messagesHtml}
                    </div>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="card-meta">
                <span class="card-step-num">Step ${msg.step} - Thinking Phase</span>
                <span class="card-timestamp">${timestamp}</span>
            </div>
            <div class="card-content">
                <div class="card-thought-tag">${renderedHtml}</div>
                ${commandPreview}
                <div class="observation-area hidden"></div>
                ${payloadInspectorHtml}
            </div>
        `;
        
        timelineStream.appendChild(card);
        timelineStream.scrollTop = timelineStream.scrollHeight;

        // Wire up accordion toggle events
        if (msg.context_history && Array.isArray(msg.context_history)) {
            const header = document.getElementById(`payload-header-${msg.step}`);
            const content = document.getElementById(`payload-content-${msg.step}`);
            if (header && content) {
                header.addEventListener('click', () => {
                    const isHidden = content.classList.contains('hidden');
                    if (isHidden) {
                        content.classList.remove('hidden');
                        header.classList.add('expanded');
                    } else {
                        content.classList.add('hidden');
                        header.classList.remove('expanded');
                    }
                });
            }
        }
    }

    function updateThoughtCardObservation(step, output, exitCode) {
        const card = document.getElementById(`thought-step-${step}`);
        if (!card) return;
        
        const obsArea = card.querySelector('.observation-area');
        if (!obsArea) return;
        
        obsArea.classList.remove('hidden');
        
        const escapedOutput = escapeHtml(output.slice(0, 500) + (output.length > 500 ? '\n... (truncated for UI, see console logs)' : ''));
        const badgeClass = exitCode === 0 ? 'neon-cyan' : 'badge-err';
        const badgeText = exitCode === 0 ? 'Success' : `Failed (Exit ${exitCode})`;
        const borderStyle = exitCode === 0 ? 'border-color: rgba(16, 185, 129, 0.2);' : 'border-color: rgba(239, 68, 68, 0.2);';
        
        obsArea.innerHTML = `
            <div class="observation-preview" style="${borderStyle}">
                <strong>🔍 Observation (${badgeText}):</strong>
                <pre><code>${escapedOutput || '[No output]'}</code></pre>
            </div>
        `;
        
        timelineStream.scrollTop = timelineStream.scrollHeight;
        
        // Refresh files explorer tree in case the agent created something
        loadWorkspaceFiles();
    }

    function renderCompletedCard(msg) {
        const card = document.createElement('div');
        card.className = "timeline-card card-completed";
        const timestamp = new Date().toLocaleTimeString();
        
        let renderedHtml = '';
        try {
            renderedHtml = marked.parse(msg.summary);
        } catch (e) {
            renderedHtml = `<p>${escapeHtml(msg.summary)}</p>`;
        }

        card.innerHTML = `
            <div class="card-meta">
                <span class="card-step-num" style="color: var(--accent-green)">Session Completed Successfully</span>
                <span class="card-timestamp">${timestamp}</span>
            </div>
            <div class="card-content">
                <p><strong>🏁 Final Outcome:</strong></p>
                <div class="card-thought-tag">${renderedHtml}</div>
            </div>
        `;
        timelineStream.appendChild(card);
        timelineStream.scrollTop = timelineStream.scrollHeight;
    }

    function renderErrorCard(errText) {
        const card = document.createElement('div');
        card.className = "timeline-card card-error";
        const timestamp = new Date().toLocaleTimeString();
        
        card.innerHTML = `
            <div class="card-meta">
                <span class="card-step-num" style="color: var(--accent-danger)">Execution Interrupted</span>
                <span class="card-timestamp">${timestamp}</span>
            </div>
            <div class="card-content">
                <p><strong>⚠️ Error Encountered:</strong></p>
                <div class="card-thought-tag"><p>${escapeHtml(errText)}</p></div>
            </div>
        `;
        timelineStream.appendChild(card);
        timelineStream.scrollTop = timelineStream.scrollHeight;
    }

    // HITL Approval Dialog Modal logic
    function showHITLModal(step, command) {
        hitlStepNumber.textContent = step;
        hitlCommandTextarea.value = command;
        hitlCommandTextarea.readOnly = true;
        rejectionReasonContainer.classList.add('hidden');
        rejectionReasonInput.value = '';
        
        // Reset modal buttons layout
        hitlRejectBtn.innerHTML = '<i class="fa-solid fa-xmark"></i> Reject Action';
        hitlEditBtn.innerHTML = '<i class="fa-solid fa-pen-to-square"></i> Modify Command';
        rejectionMode = false;
        
        hitlModal.classList.remove('hidden');
        
        // Focus approve button for keyboard efficiency
        hitlApproveBtn.focus();
    }

    function hideHITLModal() {
        hitlModal.classList.add('hidden');
    }

    function approveCommand() {
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        
        const actionMsg = {
            action: "approve",
            command: hitlCommandTextarea.value
        };
        
        socket.send(JSON.stringify(actionMsg));
        hideHITLModal();
        updateAgentStatus("Executing Approved Command...", true);
    }

    function rejectCommand() {
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        
        if (!rejectionMode) {
            // First click: slide down explanation input field
            rejectionReasonContainer.classList.remove('hidden');
            rejectionReasonInput.focus();
            hitlRejectBtn.innerHTML = '<i class="fa-solid fa-ban"></i> Confirm Rejection';
            rejectionMode = true;
        } else {
            // Second click: submit rejection explanation
            const reason = rejectionReasonInput.value.trim() || "Rejected by user instruction.";
            const actionMsg = {
                action: "reject",
                reason: reason
            };
            socket.send(JSON.stringify(actionMsg));
            hideHITLModal();
            updateAgentStatus("Rejection fed back to Agent...", true);
        }
    }

    function toggleEditCommandMode() {
        if (hitlCommandTextarea.readOnly) {
            // Enable editing
            hitlCommandTextarea.readOnly = false;
            hitlCommandTextarea.focus();
            hitlEditBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Finished Editing';
            hitlCommandTextarea.style.borderColor = 'var(--accent-indigo)';
        } else {
            // Return to read-only but keep edits
            hitlCommandTextarea.readOnly = true;
            hitlEditBtn.innerHTML = '<i class="fa-solid fa-pen-to-square"></i> Modify Command';
            hitlCommandTextarea.style.borderColor = 'rgba(255, 255, 255, 0.1)';
        }
    }

    // Live Workspace file browser tree API integration
    async function loadWorkspaceFiles() {
        try {
            const res = await fetch('/api/files');
            const files = await res.json();
            
            renderWorkspaceExplorer(files);
        } catch (err) {
            console.error("Error loading workspace files:", err);
        }
    }

    function renderWorkspaceExplorer(files) {
        if (!files || files.length === 0) {
            fileExplorerTree.innerHTML = '<div class="empty-state">No files generated yet.</div>';
            return;
        }
        
        fileExplorerTree.innerHTML = '';
        
        files.forEach(file => {
            const item = document.createElement('div');
            item.className = "file-item";
            if (selectedFilePath === file.path) {
                item.classList.add('selected');
            }
            
            // Choose right icon
            let iconClass = 'fa-file';
            if (file.is_image) {
                iconClass = 'fa-file-image';
            } else if (file.name.endsWith('.py') || file.name.endsWith('.js') || file.name.endsWith('.json') || file.name.endsWith('.html') || file.name.endsWith('.css') || file.name.endsWith('.sh') || file.name.endsWith('.bat')) {
                iconClass = 'fa-file-code';
            }
            
            const sizeStr = formatBytes(file.size);
            
            item.innerHTML = `
                <div class="file-name-container">
                    <i class="fa-solid ${iconClass}"></i>
                    <span>${file.name}</span>
                </div>
                <span class="file-size">${sizeStr}</span>
            `;
            
            // Click to preview file in Right Tab Column
            item.addEventListener('click', () => {
                // Remove previous selected indicators
                document.querySelectorAll('.file-item').forEach(el => el.classList.remove('selected'));
                item.classList.add('selected');
                selectedFilePath = file.path;
                
                openFilePreview(file);
            });
            
            fileExplorerTree.appendChild(item);
        });
    }

    // Load selected file in Workspace Previewer
    async function openFilePreview(file) {
        // Toggle tabs to Previewer automatically
        document.querySelector('.tab-btn[data-tab="preview-tab"]').click();
        
        previewEmptyState.classList.add('hidden');
        previewCodeBlock.className = "hidden"; // Reset classes
        previewMarkdownBlock.classList.add('hidden');
        previewImageContainer.classList.add('hidden');
        
        previewFilename.innerHTML = `<i class="fa-solid fa-file-lines"></i> ${file.name}`;
        previewFilesize.textContent = formatBytes(file.size);
        
        if (file.is_image) {
            // Load image using our FastAPI mounted /workspace route statically!
            previewImage.src = `/workspace/${file.path}?t=${new Date().getTime()}`; // cache-buster
            previewImageContainer.classList.remove('hidden');
        } else {
            // Fetch text content via REST API
            try {
                const res = await fetch(`/api/files/content?path=${encodeURIComponent(file.path)}`);
                if (!res.ok) throw new Error("Could not fetch file content.");
                const data = await res.json();
                
                const isMarkdown = file.name.endsWith('.md') || file.name.endsWith('.markdown');
                if (isMarkdown) {
                    let renderedMarkdown = '';
                    try {
                        renderedMarkdown = marked.parse(data.content);
                    } catch (parseErr) {
                        renderedMarkdown = `<p>${escapeHtml(data.content)}</p>`;
                    }
                    previewMarkdownBlock.innerHTML = renderedMarkdown;
                    previewMarkdownBlock.classList.remove('hidden');
                } else {
                    const codeEl = previewCodeBlock.querySelector('code');
                    
                    // Determine appropriate Prism language tag
                    let langClass = 'language-plaintext';
                    const ext = file.name.split('.').pop().toLowerCase();
                    if (ext === 'py') langClass = 'language-python';
                    else if (ext === 'js') langClass = 'language-javascript';
                    else if (ext === 'html' || ext === 'htm') langClass = 'language-markup';
                    else if (ext === 'css') langClass = 'language-css';
                    else if (ext === 'sh' || ext === 'bash') langClass = 'language-bash';
                    else if (ext === 'json') langClass = 'language-json';
                    else if (ext === 'bat') langClass = 'language-batch';
                    
                    // Apply Prism classes
                    previewCodeBlock.className = langClass;
                    codeEl.className = langClass;
                    codeEl.textContent = data.content;
                    
                    previewCodeBlock.classList.remove('hidden');
                    
                    // Trigger Prism Pretty-Print highlighting
                    if (window.Prism) {
                        Prism.highlightElement(codeEl);
                    }
                }
            } catch (err) {
                console.error("Preview err:", err);
                const codeEl = previewCodeBlock.querySelector('code');
                codeEl.className = 'language-plaintext';
                codeEl.textContent = `Error reading file content: ${err.message}`;
                previewCodeBlock.className = 'hidden';
                previewCodeBlock.classList.remove('hidden');
            }
        }
    }

    // Helper functions
    function formatBytes(bytes, decimals = 1) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    function escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
