import urllib.request
import json
import re

def _extract_json_array(text: str) -> list:
    # Find the outermost square-bracket JSON array
    # Look for the first [ and match it with its corresponding ]
    start = text.find('[')
    if start == -1:
        return []
    
    # Find matching closing bracket
    bracket_count = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == '[':
            bracket_count += 1
        elif text[i] == ']':
            bracket_count -= 1
            if bracket_count == 0:
                end = i
                break
    
    if end == -1:
        return []
    
    json_str = text[start:end+1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return []

def decompose_task(task: str, base_url: str, model: str, max_subtasks: int = 8, temperature: float = 0.2) -> list[dict]:
    url = base_url + '/chat/completions'
    
    system_prompt = f"""You are a task decomposition assistant. Break the following software task into ordered sub-tasks.

Return ONLY a JSON array of subtasks in this exact format:
[
  {{
    "id": 1,
    "title": "short title",
    "description": "what to build",
    "depends_on": []
  }}
]

Each subtask must have:
- id: integer (1-based)
- title: short descriptive string
- description: what to build for this subtask
- depends_on: list of ids this task depends on (empty if none)

Cap the number of subtasks at {max_subtasks}.

Task: {task}
"""
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Break down this task into subtasks."}
        ],
        "temperature": temperature,
        "stream": False
    }
    
    try:
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json')
        data = json.dumps(payload).encode('utf-8')
        req.data = data
        
        with urllib.request.urlopen(req) as response:
            result = response.read().decode('utf-8')
            
        # Parse the JSON from the response
        response_data = json.loads(result)
        content = response_data['choices'][0]['message']['content']
        
        # Extract JSON array from content
        subtasks = _extract_json_array(content)
        
        return subtasks
    except Exception as e:
        # Return empty list on error
        return []

if __name__ == "__main__":
    # Self-test for _extract_json_array function
    test_input = 'here is the plan: [{"id":1,"title":"x","description":"y","depends_on":[]}] done'
    result = _extract_json_array(test_input)
    assert isinstance(result, list), "Result should be a list"
    assert len(result) == 1, "Should contain exactly one subtask"
    assert result[0]['id'] == 1, "First task ID should be 1"
    print("OK")