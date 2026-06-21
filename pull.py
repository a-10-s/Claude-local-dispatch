import urllib.request
import json
import subprocess
import sys

def list_ollama_models(timeout: int = 5) -> list[str]:
    """Query http://localhost:11434/api/tags using urllib, return the list of model name strings."""
    try:
        with urllib.request.urlopen('http://localhost:11434/api/tags', timeout=timeout) as response:
            data = json.loads(response.read().decode())
            return [model['name'] for model in data.get('models', [])]
    except Exception:
        return []

def ensure_ollama_model(model: str) -> bool:
    """If model is already in list_ollama_models() return True; otherwise pull it."""
    if model in list_ollama_models():
        return True
    
    try:
        # Print progress to stderr
        print(f"Pulling model {model}...", file=sys.stderr)
        result = subprocess.run(['ollama', 'pull', model], 
                               capture_output=True, text=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def is_ollama_running() -> bool:
    """True if the tags endpoint is reachable."""
    try:
        with urllib.request.urlopen('http://localhost:11434/api/tags', timeout=5) as response:
            return response.getcode() == 200
    except Exception:
        return False

if __name__ == "__main__":
    # Self-test - just call the functions without pulling anything
    try:
        is_running = is_ollama_running()
        models = list_ollama_models()
        print("OK")
    except Exception as e:
        print(f"Error in self-test: {e}", file=sys.stderr)
        sys.exit(1)