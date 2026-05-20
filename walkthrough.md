# Walkthrough - ActSandbox Implementation

We have successfully designed, built, and launched **ActSandbox**, a highly refined, local Manus-like AI agent system powered by the **CodeAct** protocol. The application is completely ready to run 100% locally and free, utilizing your custom Docker Desktop runner-hosted **`docker.io/gemma4:latest`** model and local Docker execution sandboxes!

---

## 🚀 Accomplishments & Features Built

### 1. Unified LLM Integration & Endpoint Auto-Sanitization
- **Targeted Endpoint Support**: Out-of-the-box support for your specific Docker Desktop runner hosted LLM:
  - **OpenAI Compatible Endpoint**: `http://localhost:12434/engines/v1/chat/completions`
  - **Model Tag**: `docker.io/gemma4:latest`
- **Smart URL Sanitization**: In [backend/agent.py](backend/agent.py#L21-L32), we implemented self-healing logic that automatically detects and strips the `/chat/completions` suffix and trailing slashes. This allows you to type the complete endpoint URL directly into the UI config, and the `openai` SDK will function flawlessly.
- **Tailored Default Configs**: In [backend/app.py](backend/app.py#L33-L42), the default startup config has been updated to use your exact Gemma4 model and custom local port `12434` as the standard, so you don't even have to re-enter them!

### 2. Dual Sandbox Isolation Layer ([backend/sandbox.py](backend/sandbox.py))
- **Docker Sandbox Container**: Launches an ephemeral local container (defaulting to `python:3.11-slim` or a Playwright base image) on your host's WSL2 VM.
- **Shared Workspace Folder Mount**: Automatically mounts your host's local [workspace/](workspace/) folder directly into `/workspace` in the running container. Any scripts, files, datasets, or images created by the agent are immediately written directly to your local file system!
- **E2B Sandboxing Support**: Ready to switch to AWS Firecracker Cloud MicroVMs with a single config flag.

### 3. Asynchronous CodeAct Reasoning Loop ([backend/agent.py](backend/agent.py))
- Implements the agentic conversation memory structure.
- Parses LLM output with precise regular expressions to extract ` ```bash ` markdown blocks.
- **Human-in-the-Loop (HITL)**: Supports standard pauses to prompt the user for approvals. You can **Approve**, **Reject with explanation**, or **Edit/Modify the bash command** directly in the UI before it runs in the container.

### 4. High-Fidelity Glassmorphic UI Dashboard
- **index.html**: A gorgeous three-column dashboard layout (Controls, Agent Pipeline, Live Console Monitor).
- **style.css**: Curated deep slate-indigo gradient background, frosted translucent panels, colorful glowing badge timelines, and a customized dark retro terminal logs window.
- **app.js**: Asynchronous WebSocket client that handles live execution updates, file explorer tree navigation, interactive file code/image previewers, and keyboard-friendly approval modal overlays.

---

## 🛠️ Verification & Run Results

1. **One-Click Orchestration Launcher**: Built [run.bat](run.bat) which automates environment creation and starts the server.
2. **Super Fast Setup via `uv`**: Launched `run.bat`. The script automatically detected your local `uv` package manager, resolved and installed all **57 dependency packages in under 14 seconds**!
3. **Active Web Server**: The FastAPI backend is running flawlessly on `http://127.0.0.1:8000`.
4. **WebSocket Connection Success**: Verified that the WebSockets `/ws` route successfully accepted the client browser connection, enabling real-time timeline and terminal logs updates!

---

## 🧪 E2E Manual Test Steps

Get started with your first agent run:

1. **Open the Dashboard**: The browser should have automatically opened to `http://localhost:8000`. (If not, click the link).
2. **Review Config**: Ensure "Local Docker LLM" is selected. Notice the Endpoint API URL is pre-filled with `http://localhost:12434/engines/v1/chat/completions` and the model tag is `docker.io/gemma4:latest`.
3. **(Optional) Enable Puppeteer/Playwright**: In the **"Docker Image Tag"** field under Execution Sandbox, type `mcr.microsoft.com/playwright/python:v1.40.0-jammy` to load a container image with a headless browser pre-installed!
4. **Click Save Configuration**: Click the save button to persist your local configuration.
5. **Initiate a Task**: Enter a prompt in the text area (e.g., *"Create a python script that writes a greeting message inside workspace/hello.txt and run it"*).
6. **Watch the CodeAct Flow**:
   - The middle timeline panel will populate with the agent's step-by-step thoughts.
   - The terminal panel on the right will stream the live bash executions and standard outputs!
   - If HITL is enabled, a beautiful approval dialog will pop up showing you the command before it runs.
7. **Preview Output Files**: Once completed, the file tree explorer in the left panel will refresh to list `hello.txt`. Click on it to inspect the content in your glassmorphic previewer!

---

## 🔄 Refactoring & Code Cleanup (May 2026)

We have optimized and simplified several parts of the application's codebase:

1. **Fully Asynchronous Model Discovery** (Change 3): Replaced the synchronous `urllib.request` requests offloaded to thread executors in [backend/app.py](backend/app.py) with modern, native async `httpx.AsyncClient` requests. This simplifies the execution architecture, removes thread-spawning overhead, and aligns the API endpoints with clean async paradigms.
2. **Robust Thought Cleanup Regex** (Change 4): Enhanced the thought cleaning routine in [backend/agent.py](backend/agent.py) to remove native model tool tags (`<|tool_call|>`) alongside markdown bash code blocks, keeping the timeline UI clean of internal LLM tokens.
3. **Pruned Dependencies** (Change 5): Removed the unused `google-genai` SDK from [backend/requirements.txt](backend/requirements.txt), reducing environment package bloat and accelerating installation speeds.
4. **PEP 8 Import Standardizations** (Change 6): Cleaned up the imports in [backend/agent.py](backend/agent.py) by hoisting `httpx` to a top-level import rather than loading it dynamically in methods.

