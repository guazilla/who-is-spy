import os
import random
import datetime
import threading
import concurrent.futures
from .player import Player
from .prompts import SYSTEM_PROMPT, STATE_PROMPT, VOTE_PROMPT, REVIEW_PROMPT

class GameEngine:
    def __init__(self, log_cb=None, status_cb=None, panel_cb=None, ask_retry_cb=None, init_cb=None, api_call_wrapper=None):
        self._external_log_cb = log_cb or (lambda msg, **kwargs: print(msg))
        self.status_cb = status_cb or (lambda msg: print(f"[{msg}]"))
        self._external_panel_cb = panel_cb or (lambda title, **kwargs: print(f"[{title}]"))
        self.ask_retry_cb = ask_retry_cb or (lambda msg, pid: True)
        self.init_cb = init_cb or (lambda players: None)
        self.api_call_wrapper = api_call_wrapper or (lambda func, pid: func())
        
        def wrapped_log_cb(msg, **kwargs):
            self.append_log(msg)
            self._external_log_cb(msg, **kwargs)
            
        def wrapped_panel_cb(title, analysis="", speech="", action="", role="player"):
            panel_msg = f"【{title}】\n"
            if analysis: panel_msg += f"战术分析: {analysis}\n"
            if speech: panel_msg += f"发言: {speech}\n"
            if action: panel_msg += f"行动: {action}"
            self.append_log(panel_msg.strip())
            self._external_panel_cb(title=title, analysis=analysis, speech=speech, action=action, role=role)
            
        self.log_cb = wrapped_log_cb
        self.panel_cb = wrapped_panel_cb

        self.players = []
        self.history = []
        self.full_log = []
        self.spy_id = 0
        self.civilian_word = ""
        self.spy_word = ""
        self.game_result = ""
        self._is_running = True
        self.interrupt_flag = threading.Event()
        self.log_file = None
        self.filename = ""

    def append_log(self, msg):
        self.full_log.append(msg)
        if self.log_file:
            self.log_file.write(msg + "\n")
            self.log_file.flush()

    def stop(self):
        self._is_running = False
        self.interrupt_flag.set()

    def _setup_players(self, selected_models: list):
        random.shuffle(selected_models)
        for i in range(1, 5):
            word = self.spy_word if i == self.spy_id else self.civilian_word
            player = Player(player_id=i, keyword=word, model_name=selected_models[i-1])
            player.set_system_prompt(SYSTEM_PROMPT.format(player_id=i, keyword=word))
            self.players.append(player)

    def setup(self, civilian_word: str, spy_word: str, selected_models: list):
        if not os.path.exists("logs"): os.makedirs("logs")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"logs/game_{civilian_word}_{spy_word}_{timestamp}.txt"
        self.log_file = open(self.filename, "w", encoding="utf-8")
        self.log_file.write("=== 对局记录 ===\n")
        self.log_cb("欢迎来到《谁是卧底》AI 法官系统！", level="success")
        self.civilian_word = civilian_word
        self.spy_word = spy_word
        self.spy_id = random.randint(1, 4)
        self._setup_players(selected_models)
        self.log_cb(f"已悄悄分配身份... (调试信息：卧底是 {self.spy_id} 号)", level="info_dim")
        self.append_log("【游戏初始化】")
        for p in self.players:
            role = "卧底" if p.player_id == self.spy_id else "平民"
            self.append_log(f"{p.player_id}号玩家: {role} (模型: {p.model})")
        self.append_log("---对局开始---\n")
        self.init_cb([(p.player_id, p.model) for p in self.players])

    def run(self, civilian_word: str, spy_word: str, selected_models: list):
        self.setup(civilian_word, spy_word, selected_models)
        for round_num in range(1, 4):
            if not self._is_running: return
            self.log_cb(f"\n=== 第 {round_num} 轮 ===", level="highlight")
            self.history.append(f"【第{round_num}轮】")

            for player in self.players:
                if not self._is_running: return
                state_prompt = STATE_PROMPT.format(history="\n".join(self.history), current_speaker=player.player_id)
                
                while self._is_running:
                    self.status_cb(f"等待 {player.player_id} 号玩家 <{player.model}> 思考中...")
                    self.interrupt_flag.clear()
                    response = self.api_call_wrapper(lambda: player.get_action(state_prompt, self.interrupt_flag), player.player_id)
                    self.status_cb("")
                    
                    if self.interrupt_flag.is_set() or "API调用失败" in response['analysis']:
                        if self.interrupt_flag.is_set():
                            error_raw = "操作被中断或超时"
                        else:
                            error_raw = response.get('raw', '未知错误')

                        retry = self.ask_retry_cb(error_raw, player.player_id)
                        if retry:
                            continue
                        else:
                            self.log_cb(f"玩家 {player.player_id} 已跳过。", level="error_dim")
                            break
                    
                    self.panel_cb(title=f"玩家 {player.player_id} 号 <{player.model}>", analysis=response['analysis'], speech=response['speech'], action=response['action'], role="player")
                    record = f"{player.player_id}号玩家发言：“{response['speech']}”"
                    self.history.append(record)
                    
                    if response['action'] == "BOOM":
                        self.append_log(f"{player.player_id}号玩家行动为BOOM，猜测平民词是“{response['target_word']}”。")
                        self.handle_boom(player.player_id, response['target_word'])
                        self.finish_game()
                        return
                    elif response['action'] == "VOTE":
                        self.append_log(f"{player.player_id}号玩家发起VOTE。")
                        self.handle_vote()
                        self.finish_game()
                        return
                    break
                    
        if self._is_running:
            self.log_cb("\n三轮发言结束，强制进入投票环节！", level="error")
            self.handle_vote()
            self.finish_game()

    def handle_boom(self, player_id, target_word):
        self.log_cb(f"\n!!! {player_id} 号玩家发起了 BOOM 自爆 !!!", level="error")
        self.log_cb(f"Ta 猜测平民词是: {target_word}", level="highlight_dim")
        if player_id == self.spy_id:
            result_text = "卧底猜对平民词，卧底胜利！" if target_word and self.civilian_word in target_word else f"卧底猜错了！真正的平民词是 {self.civilian_word}。平民胜利！"
            self.game_result = f"实际上，其他玩家拿到的是平民词“{self.civilian_word}”，{player_id}号玩家胜利，{player_id}号玩家的卧底词是“{self.spy_word}”。"
        else:
            result_text = f"笑死，{player_id} 号其实是平民！平民自爆，卧底躺赢！真正的卧底是 {self.spy_id} 号。"
            self.game_result = f"实际上，{player_id}号拿到的是平民词“{self.civilian_word}”，真正的卧底是 {self.spy_id} 号玩家，卧底躺赢！"
        self.log_cb(result_text, level="success" if "胜利" in result_text else "error", bold=True)
        self.append_log(self.game_result)

    def handle_vote(self):
        self.log_cb("\n=== 开始投票 ===", level="highlight")
        vote_prompt = VOTE_PROMPT.format(history="\n".join(self.history))
        votes = {}
        vote_records = []
        for player in self.players:
            if not self._is_running: return
            while self._is_running:
                self.status_cb(f"等待 {player.player_id} 号玩家投票...")
                self.interrupt_flag.clear()
                vote_target = self.api_call_wrapper(lambda: player.get_vote(vote_prompt, self.interrupt_flag), player.player_id)
                self.status_cb("")
                
                if vote_target == -1:
                    retry = self.ask_retry_cb("API调用失败或超时", player.player_id)
                    if retry:
                        continue
                    vote_target = 0 # Skip vote
                
                if vote_target > 0:
                    self.log_cb(f"玩家 {player.player_id} 投票给了 {vote_target} 号", level="info")
                    vote_records.append(f"{player.player_id}号投给了{vote_target}号")
                    votes[vote_target] = votes.get(vote_target, 0) + 1
                else:
                    self.log_cb(f"玩家 {player.player_id} 跳过了投票。", level="info_dim")
                break
        
        self.append_log(f"投票结束，{', '.join(vote_records) if vote_records else '无人投票'}。")
            
        if not votes:
            self.game_result = f"无人生效投票，真正的卧底是 {self.spy_id} 号玩家，卧底胜利！"
            self.log_cb("无人生效投票，卧底胜利！", level="error")
        else:
            max_votes = max(votes.values())
            candidates = [k for k, v in votes.items() if v == max_votes]
            if len(candidates) > 1:
                self.game_result = f"平票！真正的卧底是 {self.spy_id} 号玩家，卧底胜利！"
                self.log_cb("平票！卧底胜利！", level="error")
            else:
                voted_out = candidates[0]
                self.log_cb(f"\n最终被投出的玩家是: {voted_out} 号", level="critical")
                if voted_out == self.spy_id:
                    self.game_result = f"{voted_out}号是卧底，平民胜利。"
                    self.log_cb(f"成功投出卧底，平民胜利！(平民词：{self.civilian_word}，卧底词：{self.spy_word})", level="success")
                else:
                    self.game_result = f"{voted_out}号是平民，卧底胜利。"
                    self.log_cb(f"投错了！{voted_out} 号是平民。真正的卧底是 {self.spy_id} 号。卧底胜利！", level="error")
        self.append_log(self.game_result)

    def finish_game(self):
        self.log_cb("\n=== 赛后复盘阶段 ===", level="highlight")
        full_log_text = "\n".join(self.full_log)
        
        self.status_cb("等待所有玩家生成复盘 (并行请求中)...")
        self.interrupt_flag.clear()
        
        def fetch_review(player):
            review_prompt = REVIEW_PROMPT.format(full_log=full_log_text, player_id=player.player_id, keyword=player.keyword, civilian_word=self.civilian_word, spy_word=self.spy_word, spy_id=self.spy_id, result=self.game_result)
            review_content = self.api_call_wrapper(lambda: player.get_review(review_prompt, self.interrupt_flag), player.player_id)
            if review_content.startswith("复盘生成失败:") or "error" in review_content:
                review_content = "（API失败或超时，未生成复盘）"
            return player, review_content

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_player = {executor.submit(fetch_review, p): p for p in self.players}
            for future in concurrent.futures.as_completed(future_to_player):
                if not self._is_running: break
                player = future_to_player[future]
                try:
                    p, review_content = future.result()
                    self.panel_cb(title=f"玩家 {p.player_id} 号 <{p.model}> 复盘总结", analysis="", speech=review_content, action="", role="review")
                except Exception as e:
                    self.log_cb(f"玩家 {player.player_id} 复盘异常: {e}", level="error_dim")

        self.status_cb("")
        
        if self.log_file:
            self.log_file.close()
            self.log_file = None
        self.log_cb(f"\n对局记录及复盘已保存至: {self.filename}", level="success")
        self.status_cb("游戏结束")
