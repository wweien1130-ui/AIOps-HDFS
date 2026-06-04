import json

with open("/home/ubunto/.openclaw/openclaw.json", "r") as f:
    config = json.load(f)

# 1. Add Ollama provider
config["models"]["providers"]["ollama"] = {
    "baseUrl": "http://172.21.64.1:11434/v1",
    "api": "openai-completions",
    "models": [
        {
            "id": "qwen3:8b",
            "name": "Qwen3 8B (Ollama Local)",
            "reasoning": True,
            "input": ["text"],
            "contextWindow": 32768,
            "maxTokens": 4096
        }
    ]
}

# 2. Switch primary model to Ollama
config["agents"]["defaults"]["model"]["primary"] = "ollama/qwen3:8b"

# 3. Add ollama model entry
config["agents"]["defaults"]["models"]["ollama/qwen3:8b"] = {}

# 4. Add ollama auth profile (no API key needed for local)
config["auth"]["profiles"]["ollama:default"] = {
    "provider": "ollama",
    "mode": "none"
}

with open("/home/ubunto/.openclaw/openclaw.json", "w") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("Done")
