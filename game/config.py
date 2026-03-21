import json
import os

class Config:
    def __init__(self, filename='config.json'):
        self.filename = filename
        self.openrouter_api_key = ""
        self.api_base_url = "https://openrouter.ai/api/v1"
        self.available_models = []
        self.load()

    def load(self):
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
                self.openrouter_api_key = config_data.get("openrouter_api_key", "")
                self.api_base_url = config_data.get("api_base_url", "https://openrouter.ai/api/v1")
                if not self.api_base_url: # prevent empty string overriding default
                    self.api_base_url = "https://openrouter.ai/api/v1"
                
                models = config_data.get("available_models", [])
                if isinstance(models, list):
                    self.available_models = models
                else:
                    print("Warning: 'available_models' in config.json is not a list.")
        except FileNotFoundError:
            print("Config not found. Using defaults.")
        except json.JSONDecodeError:
            print("CRITICAL: Could not decode config.json. Please check for syntax errors.")

    def save(self):
        config_data = {
            "openrouter_api_key": self.openrouter_api_key,
            "api_base_url": self.api_base_url,
            "available_models": self.available_models
        }
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)

# Global instance
cfg = Config()
