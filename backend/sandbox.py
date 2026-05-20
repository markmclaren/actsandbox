import os
import time
from abc import ABC, abstractmethod
from typing import Tuple, Generator

class BaseSandbox(ABC):
    @abstractmethod
    def execute(self, command: str) -> Tuple[int, str]:
        """
        Executes a command inside the sandbox and returns (exit_code, output).
        """
        pass

    @abstractmethod
    def read_file(self, path: str) -> str:
        """
        Reads a file from the sandbox and returns its content.
        """
        pass

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        """
        Writes content to a file inside the sandbox.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Cleans up and terminates the sandbox.
        """
        pass


class DockerSandbox(BaseSandbox):
    def __init__(self, workspace_host_path: str, image_name: str = "python:3.11-slim"):
        import docker
        self.workspace_host = os.path.abspath(workspace_host_path)
        self.workspace_container = "/workspace"
        self.image = image_name
        self.container = None

        # Ensure host workspace path exists
        os.makedirs(self.workspace_host, exist_ok=True)

        print(f"[DockerSandbox] Connecting to local Docker engine...")
        try:
            self.client = docker.from_env()
            # Ping the engine immediately to verify it is responsive and running
            self.client.ping()
        except Exception as e:
            raise RuntimeError(
                "🐳 Local Docker Desktop Daemon Not Found!\n\n"
                "ActSandbox could not connect to your local Docker socket/pipe. Please verify that:\n"
                "1. DOCKER DESKTOP IS ACTIVE: Open Docker Desktop and confirm the status icon is green.\n"
                "2. SOCKET INTEGRATION IS ENABLED: In Docker settings (General/Advanced), ensure the local connection socket is active.\n\n"
                "Alternative: If you do not have Docker running, you can switch 'Execution Sandbox' to 'E2B Sandbox' in your configuration console."
            ) from e

        print(f"[DockerSandbox] Initializing with image: {self.image}...")
        self._ensure_image()
        self._start_container()

    def _ensure_image(self):
        try:
            self.client.images.get(self.image)
            print(f"[DockerSandbox] Image '{self.image}' found locally.")
        except Exception:
            print(f"[DockerSandbox] Image '{self.image}' not found locally. Pulling...")
            self.client.images.pull(self.image)
            print(f"[DockerSandbox] Image '{self.image}' pulled successfully.")

    def _start_container(self):
        container_name = f"act-sandbox-{int(time.time())}"
        
        # Mount host workspace to container's /workspace folder
        volumes = {
            self.workspace_host: {
                'bind': self.workspace_container,
                'mode': 'rw'
            }
        }
        
        print(f"[DockerSandbox] Starting container {container_name}...")
        self.container = self.client.containers.run(
            self.image,
            command="tail -f /dev/null",  # Keeps container running indefinitely
            detach=True,
            name=container_name,
            volumes=volumes,
            working_dir=self.workspace_container,
            environment={"PYTHONUNBUFFERED": "1"}
        )
        print(f"[DockerSandbox] Container '{container_name}' is running.")

        # Pre-install common tools inside container if needed
        self.execute(
            "if ! command -v curl &>/dev/null || ! command -v git &>/dev/null; then "
            "apt-get update && apt-get install -y curl git wget zip unzip --no-install-recommends; "
            "fi"
        )

    def execute(self, command: str) -> Tuple[int, str]:
        if not self.container:
            raise RuntimeError("Sandbox container is not running.")
        
        print(f"[DockerSandbox] Executing: {command}")
        
        # Run command inside container
        # We run it via /bin/bash -c so pipeline commands, environment variables, etc. work properly.
        exec_res = self.container.exec_run(
            ["/bin/bash", "-c", command],
            workdir=self.workspace_container
        )
        
        exit_code = exec_res.exit_code
        output = exec_res.output.decode('utf-8', errors='replace')
        
        print(f"[DockerSandbox] Finished with code {exit_code}")
        return exit_code, output

    def _get_host_path(self, path: str) -> str:
        # Clean the container path to get a path relative to the workspace root
        rel_path = path
        if rel_path.startswith("/workspace/"):
            rel_path = rel_path[len("/workspace/"):]
        elif rel_path.startswith("workspace/"):
            rel_path = rel_path[len("workspace/"):]
        elif rel_path.startswith("/"):
            rel_path = rel_path.lstrip("/")
        
        # Resolve to an absolute path on the host to prevent directory traversal
        host_path = os.path.abspath(os.path.join(self.workspace_host, rel_path))
        
        # Ensure the resolved path remains inside the workspace_host directory
        if not host_path.startswith(self.workspace_host):
            raise PermissionError("Access denied: Path is outside the sandbox workspace.")
            
        return host_path

    def read_file(self, path: str) -> str:
        # Since the directory is mounted, we can read directly from the host workspace for performance
        try:
            host_file_path = self._get_host_path(path)
            if os.path.exists(host_file_path):
                with open(host_file_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
        except Exception:
            pass
        
        # Fallback to reading inside container
        exit_code, output = self.execute(f"cat '{path}'")
        if exit_code != 0:
            raise FileNotFoundError(f"File not found in sandbox: {path}")
        return output

    def write_file(self, path: str, content: str) -> None:
        # Write directly to host workspace (since it's mounted)
        host_file_path = self._get_host_path(path)
        os.makedirs(os.path.dirname(host_file_path), exist_ok=True)
        with open(host_file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def close(self) -> None:
        if self.container:
            container_name = self.container.name
            print(f"[DockerSandbox] Stopping and removing container '{container_name}'...")
            try:
                self.container.stop(timeout=2)
                self.container.remove()
                print(f"[DockerSandbox] Container '{container_name}' removed.")
            except Exception as e:
                print(f"[DockerSandbox] Error cleaning up container: {e}")
            self.container = None


class E2BSandbox(BaseSandbox):
    def __init__(self, api_key: str):
        from e2b import Sandbox
        self.api_key = api_key
        print("[E2BSandbox] Starting Cloud Firecracker MicroVM...")
        self.sandbox = Sandbox(api_key=self.api_key)
        print(f"[E2BSandbox] Sandbox '{self.sandbox.id}' started successfully.")

    def execute(self, command: str) -> Tuple[int, str]:
        print(f"[E2BSandbox] Running command: {command}")
        cmd_result = self.sandbox.commands.run(command)
        
        # Merge stdout and stderr for simple logging
        stdout = cmd_result.stdout or ""
        stderr = cmd_result.stderr or ""
        output = stdout + ("\n" + stderr if stderr else "")
        exit_code = cmd_result.exit_code
        
        return exit_code, output

    def read_file(self, path: str) -> str:
        return self.sandbox.files.read(path)

    def write_file(self, path: str, content: str) -> None:
        self.sandbox.files.write(path, content)

    def close(self) -> None:
        if self.sandbox:
            print(f"[E2BSandbox] Closing Sandbox '{self.sandbox.id}'...")
            self.sandbox.close()
            self.sandbox = None
