# 🌟 ActSandbox: Simple Narrative Walkthrough

Here is a simple, high-level guide to understanding exactly what happened when you clicked **Initiate** and approved the command in your browser!

---

## 🧠 1. What Did the AI (Gemma4) Actually Do?
The local LLM acted as the **"Brain"** (or the Decision Maker) of the operation:
* **Analyzed the Goal**: Your local `docker.io/gemma4:latest` model parsed your instruction (e.g., *"Create a python script and run it"*).
* **Determined the Shell Command**: It reasoned that the best way to accomplish this was to execute a bash script.
* **Wrote the Code**: Instead of just *explaining* it to you, it generated a raw, executable Markdown bash block:
  ```bash
  cat << 'EOF' > hello.py
  print("Hello from Gemma4 and ActSandbox!")
  EOF
  python hello.py
  ```
* **Inspected the Observation**: After you approved the command, Gemma4 was fed the execution result (Exit code: `0`, Output: `"Hello from Gemma4 and ActSandbox!"`). It analyzed this terminal feedback, confirmed the script executed successfully, and concluded the task by writing a friendly final summary.

---

## 🐳 2. What Did Docker Contribute?
Docker acted as the **"Secure Muscle"** (the Sandbox):
* **Total Isolation**: The moment you clicked Initiate, ActSandbox spun up an ephemeral, lightweight Linux container (`python:3.11-slim`) in milliseconds. This is like spinning up a brand-new, sterile virtual computer inside your WSL2/Docker VM.
* **Shared Workspace Mount**: We mounted your local [workspace/](file:///C:/Sourcecode/codeact/workspace) folder directly into `/workspace` inside the running Docker container. This is a **two-way mirror mount**:
  - Any files or folders the AI created inside the Docker container instantly materialized in your Windows host's folder!
  - Any files you put in there are instantly readable by the AI.
* **Execution Guard**: The AI's commands executed *inside* this container. If the AI had made a mistake, generated an infinite loop, or run something destructive, **it could never affect your actual Windows system.** 

---

## ⚙️ 3. What Else Happened (Under the Hood)?
The FastAPI Python server and your browser operated as the **"Nervous System"** (the Orchestrator):
* **High-Speed WebSocket Pipe**: When the dashboard loaded, your browser established a live WebSocket (`/ws`) connection. This allowed the server to stream thoughts and console logs to your screen instantly without needing page refreshes.
* **Human-in-the-Loop (HITL) Pause**: When the AI yielded a `"require_approval"` state, the FastAPI server **paused the Python generator process** mid-execution, popped up the modal on your screen, and waited.
* **Resuming the Loop**: When you clicked **Approve**, the browser sent a socket signal. The backend resumed the generator using Python's advanced `.asend(user_response)` method, executed the command inside Docker, and streamed the terminal stdout directly to your dark-mode console logs.
* **Automatic Garbage Collection**: The split-second the task completed or failed, the backend ran a cleanup sequence, terminating and deleting the temporary Docker container so it uses **zero RAM or CPU** when idle.

---

## 💡 Real-World Example: "Create a Bootstrap 5 HTML Page"
Even when you ask the agent to do a seemingly simple task like **creating an HTML page with Bootstrap**, it still runs 100% inside the Docker container!

Here is how that specific flow works:
1. **The Write Command Executes Inside Linux**: Gemma4 writes a command like `cat << 'EOF' > index.html ...`. This command is executed by the Linux shell *inside the Docker container*, not your Windows OS.
2. **Synchronization via Volume Mounts**: Because your local `workspace/` folder is mounted into the container's `/workspace/` folder, the moment the container writes `index.html` on its virtual disk, the file **instantly materializes** in your host's Windows folder.
3. **Safety Guarantee**: If the AI had a bug or a destructive script, it could never escape `/workspace` or touch your actual Windows system files (like `C:\Windows\System32`).

---

## 🚀 What Controls How Complex the Problems ActSandbox Can Solve?
You can scale ActSandbox to handle incredibly advanced tasks (like doing live web searches, web scraping, or setting up databases and server software) by adjusting three core pillars:

### 1. The LLM Capability (The "Brain")
* **Reasoning & Planning**: A highly advanced model excels at self-debugging. If a shell command fails, a smart LLM will parse the terminal error, search for the correct dependencies, reformulate the command, and try again.
* **Context Length**: Multi-turn reasoning loops require the LLM to remember 10+ steps of thought and execution output. A large context window allows the agent to maintain perfect recall of the entire conversation.
* **Hardware & Memory Footprint (16GB RAM constraint)**: On a 16GB machine, WSL2/Docker and the host OS share RAM. Stick to models between **7B and 9B parameters** (4GB-6GB size) to keep the system fully responsive and fast:
  - **`docker.io/mistral:latest` (Mistral 7B)**: ~4.1 GB. Highly reliable, lightweight, and an exceptional general fallback.
  - **`qwen2.5-coder:7b`**: ~4.7 GB. Currently the undisputed king of local code generation. It is extremely good at writing precise bash syntax and self-debugging!
  - **`llama3:8b`**: ~4.7 GB. Meta's powerhouse general reasoning model, great at planning and multi-turn loops.
  - **`docker.io/gemma4:latest`**: Your custom high-performance model.

### 2. The Docker Container Image (The "Body" & Tools)
You can directly control what tools the agent has access to by selecting the **"Docker Image Tag"** dropdown select in your configuration panel:
* **Default Image (`python:3.11-slim`)**: Lightweight and fast, but limited to command-line scripts and standard API calls (no visual browser).
* **Advanced Web-Scraping Image (`mcr.microsoft.com/playwright/python:v1.40.0-jammy`)**: Selecting the Playwright Browser option instantly grants the agent a **headless Chromium browser**! It can write scripts to visit websites, click elements, capture screenshots, and scrape modern dynamic React apps.

### 3. Network & System Privileges (The "Environment")
Because Docker containers run as isolated Linux kernels:
* **Root Access**: The AI executes commands as `root` within the container. It can easily run package managers to install database servers, proxy servers, or libraries:
  ```bash
  apt-get update && apt-get install -y nginx redis-server postgresql
  ```
* **Internet Connectivity**: The container shares your host machine's network by default, letting the AI query external search engines, download npm packages, or scrape documentation in real time.
* **Port Mapping**: If the AI starts a local web server (like Nginx on port 80) inside the container, you can expose that port to your Windows machine, letting you load the server the AI built directly in your host's browser!

---

## 🤖 Is This an Agent or Something Else?
Yes! This is a true **Autonomous AI Agent**, which is vastly different from a standard "chatbot."

### The Key Difference: Chatbot vs. Agent
A standard chatbot (like standard ChatGPT or Claude) is just a **text generator**. It reads your text and outputs descriptive advice. 

An **Agent** is an active loop of **Perception ➡️ Reasoning ➡️ Action**:
* **Perception**: It reads your prompt *and* the real Linux terminal output (Observations).
* **Reasoning**: It holds memory history of its previous attempts, logs dependencies, and plans its next step.
* **Action**: It executes physical code inside a container to alter its environment (e.g. creating files, installing software).

### The Three Components of the Agent
An agent is never just a raw LLM. An LLM on its own is like a "brain in a jar" with no arms or legs. To build a functioning agentic system, ActSandbox connects three layers:
1. **The Brain (The LLM)**: The model tag (`gemma4`). It does language processing, planning, and code writing.
2. **The Nervous System (The Scaffold)**: Our Python backend ([backend/agent.py](file:///C:/Sourcecode/codeact/backend/agent.py)). It drives the loop: it takes the LLM's text, extracts the bash code blocks, pauses for your approval, feeds the commands into Docker, and returns the console results back to the LLM's memory history.
3. **The Body (The Sandbox)**: The Docker container. The isolated operating system where actions take place safely.

### Why It's Called a "CodeAct" Agent
Most agents use complex, pre-defined custom APIs called **tool calls** (like calling a special JSON function to read a folder). 

ActSandbox uses the **CodeAct protocol**. CodeAct is a state-of-the-art approach where the agent **uses code (bash/python) as its only tool**. By giving the AI a raw bash terminal, it doesn't need pre-built, custom tools to make files or check directories—it can simply write standard Linux command-line code for everything, giving it **infinite flexibility**!

---

## 🧠 Situational Awareness (The Ultimate AI Booster)
One of the most powerful features we built into ActSandbox is **Dynamic Situational Awareness**.

If the AI doesn't know *what* image is running in its Docker sandbox, it might make bad assumptions—like trying to use static Python `requests` or shell `curl` on a dynamic, JavaScript-heavy website. 

To solve this, our Python backend ([backend/agent.py](file:///C:/Sourcecode/codeact/backend/agent.py)) dynamically updates the system instructions at the start of every run:
* **If a Playwright Image is Selected**: The backend automatically injects a notice telling the AI that a **Full Headless Chromium Browser** is pre-installed. It also gives the AI a working **Python Async Playwright template** so it doesn't have to code browser automation from scratch!
* **If a standard Python Image is Selected**: It tells the AI it is in a lightweight container and should prefer standard python requests or curl.

This allows the AI "brain" to instantly adapt its planning to the exact execution body it is running in!

---

## 📝 Automatic Markdown Execution Summary (`agent_summary.md`)
To give you a permanent, high-fidelity record of your agent's reasoning and execution history, our FastAPI backend ([backend/app.py](file:///C:/Sourcecode/codeact/backend/app.py)) automatically compiles a complete, structured Markdown diary of the entire session and writes it directly to `workspace/agent_summary.md` upon completion!

This report includes:
* The original task description and configuration parameters.
* A step-by-step transcript, mapping each step's **AI thoughts**, **bash commands executed**, and **stdout/stderr exit code outputs** chronologically.
* The AI's final conclusion and summary.

Because your local `workspace/` folder is synchronized, this file instantly materializes in your host system. Furthermore, because of our dashboard's built-in file tree, you can click on `agent_summary.md` in the sidebar and preview the entire run recapped beautifully directly inside your UI!

---

## 🔍 Live Local Models Autodiscovery (`/api/local-models`)
Instead of having to copy-paste or guess the exact model names loaded in your local runner (such as Ollama or vLLM), our server automatically autodiscovers your local models!

Our FastAPI backend:
1. Dynamically parses your configured **LLM Endpoint URL** to locate the host machine IP/Port.
2. Automatically probes the standard local API routes (including `/models`, `/v1/models`, and `/api/tags`).
3. Extracts and deduplicates the names of all active local engines (like `gemma4:latest`, `mistral:latest`, etc.).

On the frontend, the UI triggers a search when the page loads, when you select the "local" provider, or **whenever you focus/click on the Model Tag input field**. The custom `<datalist>` selector is instantly populated with the exact live local models running on your system!




