import os
import json
import asyncio
import urllib.request
import urllib.parse
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.sandbox import DockerSandbox, E2BSandbox
from backend.agent import CodeActAgent

app = FastAPI(title="ActSandbox - Local Manus-like CodeAct Backend")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Project Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Ensure Workspace and Config exist
os.makedirs(WORKSPACE_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "provider": "local",
    "model": "docker.io/gemma4:latest",
    "api_key": "",
    "base_url": "http://localhost:12434/engines/v1/chat/completions",
    "sandbox_type": "docker",
    "docker_image": "python:3.11-slim",
    "e2b_api_key": "",
    "hitl_enabled": True
}

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                saved = json.load(f)
                # Merge saved config with defaults for missing keys
                return {**DEFAULT_CONFIG, **saved}
        except Exception:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)


class ConfigModel(BaseModel):
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    sandbox_type: str
    docker_image: str = "python:3.11-slim"
    e2b_api_key: str = ""
    hitl_enabled: bool


@app.get("/api/config")
def get_config():
    return load_config()


@app.post("/api/config")
def update_config(config: ConfigModel):
    save_config(config.model_dump())
    return {"status": "success", "message": "Configuration saved."}


def fetch_local_models_sync(endpoint_url: str) -> list:
    try:
        req = urllib.request.Request(endpoint_url, headers={"User-Agent": "ActSandbox"})
        with urllib.request.urlopen(req, timeout=1.5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = []
                
                # OpenAI list shape: {"data": [{"id": "..."}]}
                if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                    for item in data["data"]:
                        if isinstance(item, dict) and "id" in item:
                            models.append(item["id"])
                
                # Ollama list shape: {"models": [{"name": "..."}]}
                elif isinstance(data, dict) and "models" in data and isinstance(data["models"], list):
                    for item in data["models"]:
                        if isinstance(item, dict) and "name" in item:
                            models.append(item["name"])
                        elif isinstance(item, dict) and "model" in item:
                            models.append(item["model"])
                
                # Flat list shape: ["model1", "model2"] or list of dicts with tags (e.g. docker runner format)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, str):
                            models.append(item)
                        elif isinstance(item, dict):
                            if "tags" in item and isinstance(item["tags"], list):
                                for tag in item["tags"]:
                                    if isinstance(tag, str):
                                        models.append(tag)
                            elif "id" in item and isinstance(item["id"], str):
                                if not item["id"].startswith("sha256:"):
                                    models.append(item["id"])
                            elif "name" in item and isinstance(item["name"], str):
                                models.append(item["name"])
                            
                return models
    except Exception:
        pass
    return []


@app.get("/api/local-models")
async def get_local_models():
    cfg = load_config()
    base_url = cfg.get("base_url", "http://localhost:12434")
    try:
        parsed = urllib.parse.urlparse(base_url)
        host_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Probe OpenAI and Ollama typical endpoints
        endpoints = [f"{host_url}/models", f"{host_url}/v1/models", f"{host_url}/api/tags"]
        
        for ep in endpoints:
            models = await asyncio.to_thread(fetch_local_models_sync, ep)
            if models:
                # Deduplicate and sort
                unique_models = sorted(list(set(models)))
                return {"status": "success", "models": unique_models}
                
        return {"status": "empty", "models": []}
    except Exception as e:
        return {"status": "error", "message": str(e), "models": []}


@app.get("/api/files")
def list_workspace_files():
    """
    Returns a flat list of files in the workspace directory with metadata.
    """
    files_list = []
    for root, dirs, files in os.walk(WORKSPACE_DIR):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, WORKSPACE_DIR)
            
            # Simple metadata
            stat = os.stat(full_path)
            size = stat.st_size
            
            # Determine file type
            is_image = file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))
            
            files_list.append({
                "name": file,
                "path": rel_path.replace("\\", "/"),
                "size": size,
                "is_image": is_image
            })
    return files_list


@app.get("/api/files/content")
def get_file_content(path: str):
    """
    Safely reads file content from the workspace folder.
    """
    # Prevent directory traversal attacks
    safe_path = os.path.abspath(os.path.join(WORKSPACE_DIR, path))
    if not safe_path.startswith(os.path.abspath(WORKSPACE_DIR)):
        raise HTTPException(status_code=400, detail="Invalid workspace path")
        
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    if os.path.isdir(safe_path):
        raise HTTPException(status_code=400, detail="Path is a directory")

    # If it is an image, we should ideally handle it or let the client load it directly
    # For text files, read and return content
    try:
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"content": content, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[WebSocket] Client connected.")
    
    active_sandbox = None
    agent_task = None
    
    try:
        while True:
            # 1. Wait for start message
            data_str = await websocket.receive_text()
            data = json.loads(data_str)
            
            action = data.get("action")
            
            if action == "start":
                task_desc = data.get("task")
                cfg = data.get("config", load_config())
                
                if not task_desc:
                    await websocket.send_json({"type": "error", "message": "No task specified."})
                    continue
                
                # Cleanup previous sandbox if running
                if active_sandbox:
                    try:
                        active_sandbox.close()
                    except Exception:
                        pass
                
                # Instantiate selected Sandbox
                sandbox_type = cfg.get("sandbox_type", "docker")
                await websocket.send_json({"type": "status", "message": f"Spawning isolated {sandbox_type.upper()} Sandbox..."})
                
                try:
                    if sandbox_type == "docker":
                        active_sandbox = DockerSandbox(
                            workspace_host_path=WORKSPACE_DIR,
                            image_name=cfg.get("docker_image", "python:3.11-slim")
                        )
                    elif sandbox_type == "e2b":
                        e2b_key = cfg.get("e2b_api_key")
                        if not e2b_key:
                            raise ValueError("E2B API Key is required for cloud Firecracker sandboxing.")
                        active_sandbox = E2BSandbox(api_key=e2b_key)
                    else:
                        raise ValueError(f"Unknown sandbox type: {sandbox_type}")
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": f"Failed to initialize Sandbox: {str(e)}"})
                    continue

                # Instantiate CodeAct Agent
                agent = CodeActAgent(
                    provider=cfg.get("provider", "local"),
                    model=cfg.get("model", "docker.io/gemma4:latest"),
                    api_key=cfg.get("api_key", ""),
                    base_url=cfg.get("base_url", "http://localhost:12434/engines/v1/chat/completions"),
                    hitl_enabled=cfg.get("hitl_enabled", True)
                )
                
                # Start Agent run loop
                agent_generator = agent.run(task_desc, active_sandbox)
                
                events_history = []
                try:
                    event = await agent_generator.__anext__()
                    
                    while True:
                        # Forward event to UI
                        await websocket.send_json(event)
                        events_history.append(event)
                        
                        if event["type"] == "completed":
                            break
                        
                        if event["type"] == "require_approval":
                            # Pause agent loop and wait for user websocket response (approve, reject, edit)
                            user_response_str = await websocket.receive_text()
                            user_response = json.loads(user_response_str)
                            
                            # Send the action back into the agent's generator
                            event = await agent_generator.asend(user_response)
                        else:
                            # Advance the generator normally
                            event = await agent_generator.__anext__()
                            
                except StopAsyncIteration:
                    pass
                except Exception as agent_err:
                    import traceback
                    import sys
                    print("[WebSocket] Exception in agent loop:", flush=True)
                    traceback.print_exc(file=sys.stdout)
                    sys.stdout.flush()
                    await websocket.send_json({"type": "error", "message": f"Agent error: {str(agent_err)}"})
                finally:
                    # Always save the markdown execution diary if we recorded events
                    if events_history:
                        try:
                            import datetime
                            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Check status of execution
                            status_str = "Completed successfully! 🏁"
                            final_outcome = "Task complete!"
                            
                            completed_event = next((ev for ev in events_history if ev.get("type") == "completed"), None)
                            if completed_event:
                                final_outcome = completed_event.get("summary", completed_event.get("message", "Task complete!"))
                            else:
                                status_str = "Aborted / Closed early ⚠️"
                                final_outcome = "The session was closed before the agent could formulate a final conclusion."
                            
                            md_lines = [
                                "# 🤖 ActSandbox Agent Execution Summary",
                                f"\n* **Task**: {task_desc}",
                                f"* **Model**: {cfg.get('model', 'docker.io/gemma4:latest')}",
                                f"* **Date**: {now}",
                                f"* **Status**: {status_str}",
                                "\n---",
                                "\n## 🛠️ Step-by-Step Execution Transcript\n"
                            ]
                            
                            # Gather steps
                            steps_data = {}
                            for ev in events_history:
                                if ev.get("type") == "step_start":
                                    st_num = ev["step"]
                                    steps_data[st_num] = {"thought": "", "command": "", "exit_code": None, "output": ""}
                                elif ev.get("type") == "thought":
                                    st_num = ev.get("step")
                                    if st_num in steps_data:
                                        steps_data[st_num]["thought"] = ev.get("clean_thought", ev.get("content", ""))
                                        steps_data[st_num]["command"] = ev.get("command", "")
                                elif ev.get("type") == "observation":
                                    st_num = ev.get("step")
                                    if st_num in steps_data:
                                        steps_data[st_num]["exit_code"] = ev.get("exit_code")
                                        steps_data[st_num]["output"] = ev.get("output", "")
                            
                            # Write step details
                            for st_num in sorted(steps_data.keys()):
                                step_info = steps_data[st_num]
                                md_lines.append(f"### 📍 Step {st_num}")
                                if step_info["thought"]:
                                    md_lines.append(f"\n**AI Thought**:\n{step_info['thought']}")
                                if step_info["command"]:
                                    md_lines.append(f"\n**Command Executed**:\n```bash\n{step_info['command']}\n```")
                                if step_info["exit_code"] is not None:
                                    md_lines.append(f"\n**Observation** (Exit Code: `{step_info['exit_code']}`):\n```text\n{step_info['output']}\n```")
                                md_lines.append("\n---")
                            
                            # Add final summary
                            md_lines.append("\n## 🏁 Final Conclusion")
                            md_lines.append(final_outcome)
                            
                            # Write file to /workspace
                            summary_path = os.path.join(WORKSPACE_DIR, "agent_summary.md")
                            with open(summary_path, "w", encoding="utf-8") as f:
                                f.write("\n".join(md_lines))
                            print(f"[Server] Saved robust execution summary to: {summary_path}")
                        except Exception as sum_err:
                            print(f"[Server] Failed to write agent summary in finally block: {sum_err}")
                            
                    # Cleanup sandbox when task completes or fails
                    if active_sandbox:
                        active_sandbox.close()
                        active_sandbox = None
                        try:
                            await websocket.send_json({"type": "status", "message": "Sandbox closed."})
                        except Exception:
                            pass

    except WebSocketDisconnect:
        print("[WebSocket] Client disconnected.")
    except Exception as ws_err:
        print(f"[WebSocket] Error: {ws_err}")
    finally:
        if active_sandbox:
            active_sandbox.close()
            active_sandbox = None

# Mount Static Files (Frontend UI & Workspace Files)
if os.path.exists(FRONTEND_DIR):
    app.mount("/workspace", StaticFiles(directory=WORKSPACE_DIR), name="workspace")
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    print(f"[Warning] Frontend directory '{FRONTEND_DIR}' does not exist yet. Please create it.")
