import os
import glob

def build_context_block(paths: list[str], max_total_chars: int = 24000) -> str:
    """Read each existing file path, format as a section like '### FILE: <path>\n\n', and concatenate them.

    Skip paths that do not exist. Stop adding files once the running total would exceed max_total_chars,
    and append a note '... (context truncated)' if any files were skipped due to the limit.

    Args:
        paths: List of file paths to include in context
        max_total_chars: Maximum total characters allowed in output

    Returns:
        Formatted context block string
    """
    result = []
    total_chars = 0
    truncated = False
    
    for path in paths:
        # Skip non-existent files
        if not os.path.exists(path):
            continue
        
        # Read file content
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, OSError):
            # Skip files that can't be read
            continue
        
        # Format the section header and content
        section = f"### FILE: {path}\n\n{content}"
        section_chars = len(section)
        
        # Check if adding this file would exceed the limit
        if total_chars + section_chars > max_total_chars:
            truncated = True
            break
        
        result.append(section)
        total_chars += section_chars
    
    output = ''.join(result)
    
    if truncated and output:
        output += "... (context truncated)"
    
    return output

def gather_files(root: str, patterns: list[str]) -> list[str]:
    """Return a sorted list of file paths under root matching any glob pattern.

    Args:
        root: Root directory to search
        patterns: List of glob patterns to match

    Returns:
        Sorted list of matching file paths
    """
    files = set()
    
    for pattern in patterns:
        # Use recursive glob to find all matching files
        pattern_path = os.path.join(root, '**', pattern)
        matches = glob.glob(pattern_path, recursive=True)
        
        # Filter out directories (keep only files)
        for match in matches:
            if os.path.isfile(match):
                files.add(match)
    
    return sorted(list(files))


if __name__ == "__main__":
    import tempfile
    import os
    
    # Create temporary files for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f1:
        f1.write("First file content")
        file1 = f1.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f2:
        f2.write("Second file content")
        file2 = f2.name
    
    try:
        # Test build_context_block
        result = build_context_block([file1, file2])
        
        # Assertions
        assert file1 in result, f"File path {file1} not found in output"
        assert file2 in result, f"File path {file2} not found in output"
        assert '### FILE:' in result, "'### FILE:' marker not found in output"
        assert 'First file content' in result, "First file content not found in output"
        assert 'Second file content' in result, "Second file content not found in output"
        
        print('OK')
    finally:
        # Clean up temp files
        os.unlink(file1)
        os.unlink(file2)