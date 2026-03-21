import re
import httpx
import json
import threading
import concurrent.futures
from .config import cfg

class Player:
    def __init__(self, player_id: int, keyword: str, model_name: str):
        self.player_id = player_id
        self.keyword = keyword
        self.model = model_name
        self.messages = []

    def set_system_prompt(self, prompt: str):
        self.messages = [{"role": "system", "content": prompt}]

    def _make_api_call(self, interrupt_flag: threading.Event):
        client = httpx.Client(timeout=310)

        def _do_request():
            try:
                base_url = cfg.api_base_url.rstrip('/')
                url = f"{base_url}/chat/completions"
                response = client.post(
                    url,
                    headers={"Authorization": f"Bearer {cfg.openrouter_api_key}"},
                    json={"model": self.model, "messages": self.messages},
                )
                response.raise_for_status()
                if interrupt_flag.is_set():
                    return {"error": "Interrupted"}
                return response.json()
            except httpx.ReadTimeout:
                return {"error": "复盘生成失败: HTTP请求超时"}
            except httpx.HTTPStatusError as e:
                return {"error": f"复盘生成失败: HTTP错误 {e.response.status_code}"}
            except Exception as e:
                if interrupt_flag.is_set():
                    return {"error": "Interrupted"}
                return {"error": f"复盘生成失败: {e}"}
            finally:
                client.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_request)
            while not future.done():
                if interrupt_flag.is_set():
                    client.close()  # Force close connection to unblock the thread
                    return {"error": "Interrupted"}
                try:
                    future.result(timeout=0.2)
                except concurrent.futures.TimeoutError:
                    pass
            
            return future.result()

    def get_review(self, review_prompt: str, interrupt_flag: threading.Event) -> str:
        if not (self.messages and self.messages[-1]["role"] == "user" and self.messages[-1]["content"] == review_prompt):
            self.messages.append({"role": "user", "content": review_prompt})
        
        response_data = self._make_api_call(interrupt_flag)
        if "error" in response_data:
            return response_data["error"]
            
        return response_data["choices"][0]["message"]["content"]

    def get_action(self, state_prompt: str, interrupt_flag: threading.Event) -> dict:
        if not (self.messages and self.messages[-1]["role"] == "user" and self.messages[-1]["content"] == state_prompt):
            self.messages.append({"role": "user", "content": state_prompt})
        
        response_data = self._make_api_call(interrupt_flag)
        
        if "error" in response_data:
            return {"raw": response_data["error"], "analysis": "API调用失败", "speech": "思考被中断了...", "action": "NEXT", "target_word": None}
            
        content = response_data["choices"][0]["message"]["content"]
        self.messages.append({"role": "assistant", "content": content})
        return self._parse_response(content)

    def _parse_response(self, content: str) -> dict:
        analysis_pattern = r'\*?\*?\(?战术分析\)?\*?\*?\s*[:：]?\s*(.*?)(?=\n\s*\*?\*?发言\s*[:：]?\*?\*?)'
        speech_pattern = r'\n\s*\*?\*?发言\s*[:：]?\*?\*?\s*(.*?)(?=\n\s*\*?\*?行动\s*[:：]?\*?\*?)'
        action_pattern = r'\n\s*\*?\*?行动\s*[:：]?\*?\*?\s*(.*)'

        analysis_match = re.search(analysis_pattern, content, re.DOTALL)
        speech_match = re.search(speech_pattern, content, re.DOTALL)
        action_match = re.search(action_pattern, content, re.DOTALL)

        if not analysis_match:
            analysis_match = re.search(r'\*?\*?\(?战术分析\)?\*?\*?\s*[:：]?\s*(.*?)(?=\*?\*?发言\s*[:：]?\*?\*?)', content, re.DOTALL)
        if not speech_match:
            speech_match = re.search(r'\*?\*?发言\s*[:：]?\*?\*?\s*(.*?)(?=\*?\*?行动\s*[:：]?\*?\*?)', content, re.DOTALL)
        if not action_match:
            action_match = re.search(r'\*?\*?行动\s*[:：]?\*?\*?\s*(.*)', content, re.DOTALL)

        analysis = analysis_match.group(1).strip() if analysis_match else ""
        speech = speech_match.group(1).strip() if speech_match else "我不知道该说什么了。"
        
        action = "NEXT"
        target_word = None
        if action_match:
            action_raw = action_match.group(1).strip()
            if "BOOM" in action_raw:
                action = "BOOM"
                word_match = re.search(r"平民词[是为].*?['\"“‘\[【]?([a-zA-Z0-9\u4e00-\u9fa5]+)", action_raw)
                if word_match: target_word = word_match.group(1).strip()
            elif "VOTE" in action_raw:
                action = "VOTE"
                
        return {"raw": content, "analysis": analysis, "speech": speech, "action": action, "target_word": target_word}

    def get_vote(self, vote_prompt: str, interrupt_flag: threading.Event) -> int:
        if not (self.messages and self.messages[-1]["role"] == "user" and self.messages[-1]["content"] == vote_prompt):
            self.messages.append({"role": "user", "content": vote_prompt})
            
        response_data = self._make_api_call(interrupt_flag)

        if "error" in response_data:
            return -1
            
        content = response_data["choices"][0]["message"]["content"]
        self.messages.append({"role": "assistant", "content": content})
        
        match = re.search(r'(\d+)', content)
        return int(match.group(1)) if match else 0
