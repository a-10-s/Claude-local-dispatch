import os
import sys
from pathlib import Path

def detect_verify_command(workdir: str) -> str | None:
    """
    Auto-detects the right verify/test command for a project directory.
    
    Returns:
        str | None: The appropriate test command or None if no known project type found
    """
    workdir_path = Path(workdir)
    
    # Check for Python project indicators
    python_indicators = (
        any(workdir_path.glob('test_*.py')) or
        any(workdir_path.glob('*_test.py')) or
        (workdir_path / 'pyproject.toml').exists() or
        (workdir_path / 'setup.py').exists()
    )
    
    # Check for Node.js project indicator
    node_indicator = (workdir_path / 'package.json').exists()
    
    # Check for Rust project indicator
    rust_indicator = (workdir_path / 'Cargo.toml').exists()
    
    # Check for Go project indicator
    go_indicator = (workdir_path / 'go.mod').exists()
    
    if python_indicators:
        return 'python -m pytest -q'
    elif node_indicator:
        return 'npm test'
    elif rust_indicator:
        return 'cargo test'
    elif go_indicator:
        return 'go test ./...'
    else:
        return None

def detect_language(workdir: str) -> str:
    """
    Detects the programming language of a project based on files present.
    
    Returns:
        str: One of 'python', 'node', 'rust', 'go', 'unknown'
    """
    workdir_path = Path(workdir)
    
    # Check for Python project indicators
    python_indicators = (
        any(workdir_path.glob('test_*.py')) or
        any(workdir_path.glob('*_test.py')) or
        (workdir_path / 'pyproject.toml').exists() or
        (workdir_path / 'setup.py').exists()
    )
    
    # Check for Node.js project indicator
    node_indicator = (workdir_path / 'package.json').exists()
    
    # Check for Rust project indicator
    rust_indicator = (workdir_path / 'Cargo.toml').exists()
    
    # Check for Go project indicator
    go_indicator = (workdir_path / 'go.mod').exists()
    
    if python_indicators:
        return 'python'
    elif node_indicator:
        return 'node'
    elif rust_indicator:
        return 'rust'
    elif go_indicator:
        return 'go'
    else:
        return 'unknown'

if __name__ == '__main__':
    # Create a temporary directory with a fake package.json for testing
    import tempfile
    import shutil
    
    test_dir = tempfile.mkdtemp()
    try:
        # Create a fake package.json
        package_json_path = os.path.join(test_dir, 'package.json')
        with open(package_json_path, 'w') as f:
            f.write('{"name": "test-project", "scripts": {"test": "echo test"}}')
        
        # Test the function
        result = detect_verify_command(test_dir)
        assert result == 'npm test', f'Expected "npm test", got "{result}"'
        
        print('OK')
    finally:
        # Clean up
        shutil.rmtree(test_dir)