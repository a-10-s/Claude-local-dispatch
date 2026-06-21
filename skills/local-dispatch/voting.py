import urllib.request
import urllib.parse
import json
import re

def generate_with_model(prompt: str, base_url: str, model: str, temperature: float = 0.2) -> str:
    url = base_url + '/chat/completions'
    data = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': temperature
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'))
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    except Exception:
        return ''

def score_candidate(candidate: str, base_url: str, judge_model: str, task: str) -> float:
    prompt = f"Rate how well the following answer solves the task '{task}' on a scale of 0 to 10. Answer with only a number.\n\nTask: {task}\nAnswer: {candidate}"
    try:
        response = generate_with_model(prompt, base_url, judge_model)
        match = re.search(r'\d+(?:\.\d+)?', response)
        if match:
            return float(match.group())
        return 0.0
    except Exception:
        return 0.0

def pick_best(task: str, base_url: str, models: list[str], judge_model: str | None = None) -> dict:
    if judge_model is None:
        judge_model = models[0]
    
    candidates = []
    for model in models:
        text = generate_with_model(task, base_url, model)
        score = score_candidate(text, base_url, judge_model, task)
        candidates.append({'model': model, 'score': score, 'text': text})
    
    # Sort by score descending
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    best = candidates[0]
    return {
        'best_model': best['model'],
        'best_text': best['text'],
        'best_score': best['score'],
        'all': candidates
    }

if __name__ == '__main__':
    # Monkey patch for testing
    original_generate_with_model = generate_with_model
    original_score_candidate = score_candidate
    
    def mock_generate_with_model(prompt, base_url, model, temperature=0.2):
        # Simple mock that returns different responses based on model name
        if 'model1' in model.lower():
            return "This is the first model's response to the task."
        else:
            return "This is the second model's superior response to the task."
    
    def mock_score_candidate(candidate, base_url, judge_model, task):
        # Simple mock that gives higher score to second model's response
        if 'second' in candidate.lower():
            return 8.5
        else:
            return 6.0
    
    # Replace functions with mocks
    generate_with_model = mock_generate_with_model
    score_candidate = mock_score_candidate
    
    # Test the pick_best function
    result = pick_best(
        task="What is the capital of France?",
        base_url="http://localhost:1234",
        models=["model1", "model2"]
    )
    
    # Assertions
    assert result['best_model'] == 'model2', f"Expected model2 as best, got {result['best_model']}"
    print("OK")
    
    # Restore original functions
    generate_with_model = original_generate_with_model
    score_candidate = original_score_candidate