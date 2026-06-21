import json
import hashlib
import os

def cache_key(task: str, model: str, role: str) -> str:
    """Generate a stable SHA256 hex digest of the inputs."""
    input_str = f"{task}:{model}:{role}"
    return hashlib.sha256(input_str.encode()).hexdigest()

def get_cached(key: str, cache_dir: str = '.dispatch-cache') -> dict | None:
    """Return the stored JSON dict for key, or None if missing."""
    try:
        file_path = os.path.join(cache_dir, f"{key}.json")
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def put_cached(key: str, value: dict, cache_dir: str = '.dispatch-cache') -> None:
    """Store value as JSON at cache_dir/<key>.json, creating the dir if needed."""
    os.makedirs(cache_dir, exist_ok=True)
    file_path = os.path.join(cache_dir, f"{key}.json")
    with open(file_path, 'w') as f:
        json.dump(value, f)

if __name__ == "__main__":
    # Test the cache functionality
    key = cache_key('test_task', 'test_model', 'test_role')
    
    # Initially should return None
    assert get_cached(key) is None, "Initial cache lookup should return None"
    
    # Put some data in cache
    put_cached(key, {'status': 'done'})
    
    # Should now return the cached data
    result = get_cached(key)
    assert result == {'status': 'done'}, f"Expected {{'status': 'done'}}, got {result}"
    
    # Clean up
    import shutil
    shutil.rmtree('.dispatch-cache', ignore_errors=True)
    
    print('OK')
