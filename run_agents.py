#!/usr/bin/env python3
"""
Run competition agents as background threads.
Integrated into the main app startup.
"""

import threading
import time
import random
import requests
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BASE_URL = os.environ.get("DICE_ORACLE_URL", "http://localhost:8000")
COMPETITION_END_DATE = date(2026, 3, 5)


class CompetitionAgent(threading.Thread):
    def __init__(self, name: str):
        super().__init__(daemon=True)
        self.agent_name = name
        self.player_id = None
        self.registered_today = None
        self.guessed_rounds = set()
        self.running = True
    
    def log(self, msg):
        timestamp = datetime.now(ET).strftime("%H:%M:%S ET")
        print(f"[{timestamp}] [{self.agent_name}] {msg}", flush=True)
    
    def get_state(self):
        try:
            resp = requests.get(f"{BASE_URL}/competition/state", timeout=10)
            return resp.json()
        except Exception as e:
            return None
    
    def find_existing_registration(self):
        """Check if we're already registered today."""
        try:
            resp = requests.get(f"{BASE_URL}/competition/players", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for player in data.get("players", []):
                    if player.get("name") == self.agent_name:
                        self.player_id = player.get("id")
                        self.registered_today = datetime.now(ET).strftime("%Y-%m-%d")
                        # Recover guessed rounds
                        for rn in player.get("rounds_guessed", []):
                            self.guessed_rounds.add(int(rn))
                        self.log(f"✅ Found existing registration! ID: {self.player_id}, guessed: {self.guessed_rounds}")
                        return True
        except Exception as e:
            self.log(f"Error checking existing registration: {e}")
        return False
    
    def register(self):
        # First check if already registered
        if self.find_existing_registration():
            return True
        
        try:
            resp = requests.post(
                f"{BASE_URL}/competition/register",
                json={"name": self.agent_name},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                self.player_id = data["player_id"]
                self.registered_today = datetime.now(ET).strftime("%Y-%m-%d")
                self.log(f"✅ Registered! ID: {self.player_id}")
                return True
            else:
                detail = resp.json().get("detail", "")
                if "already registered" in detail.lower():
                    # Try to find our ID
                    return self.find_existing_registration()
                self.log(f"Registration failed: {detail}")
                return False
        except Exception as e:
            self.log(f"Registration error: {e}")
            return False
    
    def submit_guess(self, round_num: int):
        if not self.player_id:
            return False
        
        if round_num in self.guessed_rounds:
            return False
        
        # Randomized strategy
        total = random.choice([16, 17, 17, 17, 18, 18, 19])
        individual = [random.choice([3, 3, 3, 4, 4, 4]) for _ in range(5)]
        
        try:
            resp = requests.post(
                f"{BASE_URL}/competition/guess",
                json={
                    "player_id": self.player_id,
                    "round_num": round_num,
                    "total": total,
                    "individual": individual
                },
                timeout=10
            )
            if resp.status_code == 200:
                self.guessed_rounds.add(round_num)
                self.log(f"🎯 Round {round_num}: total={total}, dice={individual}")
                return True
            else:
                detail = resp.json().get("detail", "")
                if "already submitted" in detail.lower():
                    self.guessed_rounds.add(round_num)
                return False
        except Exception as e:
            self.log(f"Guess error: {e}")
            return False
    
    def reset_for_new_day(self):
        self.player_id = None
        self.registered_today = None
        self.guessed_rounds = set()
        self.log("🔄 Reset for new day")
    
    def run(self):
        self.log(f"🤖 Agent starting")
        
        # Try to find existing registration on startup
        self.find_existing_registration()
        
        while self.running:
            try:
                # Check if competition ended
                if datetime.now(ET).date() > COMPETITION_END_DATE:
                    self.log("Competition ended")
                    break
                
                state = self.get_state()
                if state is None:
                    time.sleep(30)
                    continue
                
                # Check for new day
                today = datetime.now(ET).strftime("%Y-%m-%d")
                if self.registered_today and self.registered_today != today:
                    self.reset_for_new_day()
                
                phase = state.get("phase", "")
                current_round = state.get("current_round", 0)
                
                # Try to register/find registration if not registered
                if not self.player_id:
                    if phase in ["registration", "guessing1"]:
                        time.sleep(random.uniform(1, 5))
                        self.register()
                    else:
                        # Try to find existing registration
                        self.find_existing_registration()
                
                # Guessing phase
                if phase.startswith("guessing") and self.player_id:
                    if current_round > 0 and current_round not in self.guessed_rounds:
                        time.sleep(random.uniform(0.5, 3))  # Random delay for speed bonus variation
                        self.submit_guess(current_round)
                
                # Longer sleep during closed phase
                if phase == "closed":
                    time.sleep(300)  # 5 minutes
                else:
                    time.sleep(30)  # 30 seconds
                    
            except Exception as e:
                self.log(f"Error: {e}")
                time.sleep(60)
    
    def stop(self):
        self.running = False


# Global agents
agents = []


def start_agents():
    """Start competition agents."""
    global agents
    
    agent_names = os.environ.get("AGENT_NAMES", "CompBot-Alpha,CompBot-Beta").split(",")
    
    for name in agent_names:
        name = name.strip()
        if name:
            agent = CompetitionAgent(name)
            agent.start()
            agents.append(agent)
            print(f"🤖 Started agent: {name}")


def stop_agents():
    """Stop all agents."""
    global agents
    for agent in agents:
        agent.stop()
    agents = []
