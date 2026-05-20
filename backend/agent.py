import re
import asyncio
import httpx
from typing import AsyncGenerator, Dict, Any, List
from openai import AsyncOpenAI
from backend.sandbox import BaseSandbox

class CodeActAgent:
    def __init__(self, 
                 provider: str, 
                 model: str, 
                 api_key: str = "", 
                 base_url: str = "", 
                 hitl_enabled: bool = True):
        self.provider = provider
        self.model = model
        self.hitl_enabled = hitl_enabled
        self.history: List[Dict[str, Any]] = []
        
        # Configure the unified OpenAI client based on the provider
        client_kwargs = {}
        
        if provider == "local":
            # For local Docker LLMs (Ollama, vLLM, Docker Model Runner)
            local_url = base_url if base_url else "http://localhost:11434/v1"
            # Clean up url if user entered full chat endpoint
            if local_url.endswith("/chat/completions"):
                local_url = local_url[:-17]
            if local_url.endswith("/"):
                local_url = local_url[:-1]
                
            client_kwargs["base_url"] = local_url
            client_kwargs["api_key"] = api_key if api_key else "not-needed"
        elif provider == "gemini":
            # Gemini OpenAI-compatible API
            client_kwargs["base_url"] = "https://generativelanguage.googleapis.com/v1beta/openai/"
            client_kwargs["api_key"] = api_key
        elif provider == "openai":
            # Standard OpenAI API
            if api_key:
                client_kwargs["api_key"] = api_key
            if base_url:
                client_kwargs["base_url"] = base_url
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

        print(f"[Agent] Initializing OpenAI Client for provider={provider}, base_url={client_kwargs.get('base_url', 'default')}")
        self.client = AsyncOpenAI(http_client=httpx.AsyncClient(trust_env=False), **client_kwargs)

        self.system_prompt = (
            "You are ActSandbox, an advanced agentic AI coding assistant designed to solve tasks "
            "by executing shell commands inside a secure local sandbox container (microVM).\n\n"
            "SYSTEM INSTRUCTIONS:\n"
            "1. You have access to a bash terminal. You can execute any shell command by writing a single bash code block:\n"
            "   ```bash\n"
            "   <command here>\n"
            "   ```\n"
            "2. Execute commands step-by-step. Let the environment respond with the execution results (Observation) "
            "before outputting your next plan or command.\n"
            "3. If a command fails (returns non-zero exit code), diagnose the error, modify the command, and try again.\n"
            "4. Your terminal directory `/workspace` is shared with the host workspace. Feel free to create and edit files, "
            "install pip/npm packages, run tests, or execute scripts.\n"
            "5. To edit files, prefer standard bash utilities like `cat << 'EOF' > file.txt` or python script edits rather "
            "than interactive editors like vim/nano.\n"
            "6. DO NOT explain your terminal commands excessively. Keep thoughts concise and actionable.\n"
            "7. When you are completely done with the task, present your final response summarizing what you accomplished. "
            "Do NOT output any more bash code blocks once the task is finished.\n"
        )

    def _extract_bash_command(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return ""
        
        # 1. Standard markdown ```bash ... ```
        pattern_md = re.compile(r"```bash\s*\n(.*?)\n\s*```", re.DOTALL)
        match_md = pattern_md.search(text)
        if match_md:
            return match_md.group(1).strip()
            
        # 2. Native tool call tokens: <|tool_call>call:bash\n... or <|tool_call>bash\n...
        pattern_tool = re.compile(r"<\|tool_call\|?>\s*(?:call:)?bash\s*\n?(.*?)(?:\n?\s*<\||$)", re.DOTALL)
        match_tool = pattern_tool.search(text)
        if match_tool:
            return match_tool.group(1).strip()
            
        # 3. Fallback: Check if there's a raw <|tool_call> containing command inside
        if "<|tool_call>" in text:
            # Strip tags and try to find the inner text
            clean = text.replace("<|tool_call>", "").replace("<|", "").replace("|>", "").replace("call:bash", "")
            return clean.strip()

        return ""

    async def run(self, task: str, sandbox: BaseSandbox) -> AsyncGenerator[Dict[str, Any], Any]:
        """
        Runs the CodeAct reasoning loop. Yields status reports to stream to the WebSocket.
        """
        # Build situational awareness block based on sandbox image capabilities
        image_tag = getattr(sandbox, "image", "python:3.11-slim")
        
        awareness = "\n\nSITUATIONAL AWARENESS (YOUR CURRENT SANDBOX ENVIRONMENT):\n"
        if "playwright" in image_tag or "puppeteer" in image_tag:
            awareness += (
                f"- You are running in a PLAYWRIGHT BROWSER SANDBOX container ({image_tag}).\n"
                "- A FULL HEADLESS CHROMIUM BROWSER is pre-installed in the container environment!\n"
                "- If the task requires visiting, examining, or scraping a website, DO NOT use simple static 'curl' or 'requests' "
                "python calls which fail on JavaScript-heavy websites. Instead, WRITE A PYTHON SCRIPT USING PLAYWRIGHT (e.g. using `async_playwright` "
                "or standard Playwright APIs) to visit the site, let the JavaScript execute, read the dynamic DOM, take screenshots, or click buttons!\n"
                "- Remember to execute standard python scripts to launch Playwright. Example script format:\n"
                "  ```python\n"
                "  import asyncio\n"
                "  from playwright.async_api import async_playwright\n"
                "  async def run():\n"
                "      async with async_playwright() as p:\n"
                "          browser = await p.chromium.launch(headless=True)\n"
                "          page = await browser.new_page()\n"
                "          await page.goto('https://example.com')\n"
                "          content = await page.content()\n"
                "          print(content)\n"
                "          await browser.close()\n"
                "  asyncio.run(run())\n"
                "  ```\n"
            )
        else:
            awareness += (
                f"- You are running in a LIGHTWEIGHT PYTHON SANDBOX container ({image_tag}).\n"
                "- You have standard bash terminal access, Python 3.11, and basic CLI utilities like curl, wget, and zip.\n"
                "- You do NOT have a graphical web browser installed in this environment. For basic web requests, "
                "prefer standard Python 'requests' calls, 'urllib', or bash 'curl' commands.\n"
            )
            
        full_system_prompt = self.system_prompt + awareness

        # Reset and prepare history
        self.history = [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": f"Please complete the following task:\n{task}"}
        ]

        step = 1
        max_steps = 15
        
        yield {
            "type": "status",
            "message": f"Starting CodeAct Agent with {self.model}..."
        }

        while step <= max_steps:
            yield {
                "type": "step_start",
                "step": step
            }

            # 1. Ask LLM for thoughts & actions
            yield {
                "type": "status",
                "message": "AI is thinking..."
            }
            
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=self.history,
                    temperature=0.2,
                )
            except Exception as e:
                yield {
                    "type": "error",
                    "message": f"LLM API Error: {str(e)}"
                }
                return

            # 2. Extract response text safely
            print(f"[Agent] Raw completions response: {response}")
            response_text = ""
            try:
                if response and getattr(response, "choices", None) is not None and len(response.choices) > 0:
                    choice = response.choices[0]
                    if choice and getattr(choice, "message", None) is not None:
                        response_text = getattr(choice.message, "content", "") or ""
                elif isinstance(response, dict) and "choices" in response and response["choices"]:
                    choice = response["choices"][0]
                    if isinstance(choice, dict) and "message" in choice:
                        response_text = choice["message"].get("content", "") or ""
            except Exception as parse_err:
                print(f"[Agent] Error parsing LLM response: {parse_err}")

            if not response_text:
                yield {
                    "type": "error",
                    "message": "LLM API Error: Local runner returned an empty or invalid response. Please ensure the local model has enough context/memory."
                }
                return

            # Extract bash command if exists
            command = self._extract_bash_command(response_text)
            
            # Send current thoughts/explanations to client
            # Strip bash block and native tool calls for thought rendering in timeline
            clean_thought = re.sub(r"```bash\s*\n.*?\n\s*```", "[Terminal Action Executing]", response_text, flags=re.DOTALL)
            clean_thought = re.sub(r"<\|tool_call\|?>.*?(?:<\||$)", "[Terminal Action Executing]", clean_thought, flags=re.DOTALL).strip()
            
            yield {
                "type": "thought",
                "step": step,
                "content": response_text,
                "clean_thought": clean_thought,
                "command": command,
                "context_history": list(self.history)  # Send the full active context history including the system prompt!
            }

            # Append LLM thought to history
            self.history.append({"role": "assistant", "content": response_text})

            if not command:
                # No command generated, agent is finished!
                yield {
                    "type": "completed",
                    "message": "Task complete! The agent has finished.",
                    "summary": response_text
                }
                break

            # 2. Command execution phase (HITL vs Auto)
            final_command = command
            
            if self.hitl_enabled:
                # Wait for response from generator's asend()
                # The caller must send back {"action": "approve" | "reject" | "edit", "command": str, "reason": str}
                user_action = yield {
                    "type": "require_approval",
                    "step": step,
                    "command": command
                }
                
                # Safety fallback
                if not user_action or not isinstance(user_action, dict) or "action" not in user_action:
                    user_action = {"action": "approve"}

                action_type = user_action["action"]
                
                if action_type == "reject":
                    reason = user_action.get("reason", "No reason provided.")
                    observation = f"Command execution was REJECTED by the user.\nReason: {reason}"
                    yield {
                        "type": "status",
                        "message": f"Command rejected: {reason}"
                    }
                    self.history.append({"role": "user", "content": f"Observation:\n{observation}"})
                    step += 1
                    continue
                
                elif action_type == "edit":
                    final_command = user_action.get("command", command)
                    yield {
                        "type": "status",
                        "message": f"Executing edited command: {final_command}"
                    }
                else:
                    yield {
                        "type": "status",
                        "message": f"Executing command: {final_command}"
                    }
            else:
                yield {
                    "type": "status",
                    "message": f"Executing command: {final_command}"
                }

            # 3. Run command in Sandbox
            # We run it in a separate thread/executor to prevent blocking the asyncio event loop.
            # For safety, let's wrap execution in a try-except
            try:
                exit_code, output = await asyncio.to_thread(sandbox.execute, final_command)
            except Exception as e:
                exit_code = -1
                output = f"Execution failed: {str(e)}"

            observation = f"Observation:\nExit code: {exit_code}\nOutput:\n{output}"
            self.history.append({"role": "user", "content": observation})

            yield {
                "type": "observation",
                "step": step,
                "exit_code": exit_code,
                "output": output
            }

            step += 1
            await asyncio.sleep(0.5)

        if step > max_steps:
            yield {
                "type": "completed",
                "message": "Execution stopped. Reached maximum agent steps (15).",
                "summary": "Agent timed out after 15 steps."
            }
