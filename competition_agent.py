#!/usr/bin/env python3
"""
Competition Agent - Auto-joins daily competition and submits guesses.
"""

import requests
import time
import random
import sys
import os
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BASE_URL = os.environ.get("DICE_ORACLE_URL", "http://localhost:8000")
AGENT_NAME = os.environ.get("AGENT_NAME", f"CompBot-{random.randint(100,999)}")
POLL_INTERVAL = 30  # seconds

# Agent state
player_id = None
registered_today = None
guessed_rounds = set()

def log(msg):
    timestamp = datetime.now(ET).strftime("%H:%M:%S ET")
    print(f"[{timestamp}] [{AGENT_NAME}] {msg}", flush=True)

def get_state():
    try:
        resp = requests.get(f"{BASE_URL}/competition/state", timeout=10)
        return resp.json()
    except Exception as e:
        log(f"Error getting state: {e}")
        return None

def register():
    global player_id, registered_today
    try:
        resp = requests.post(
            f"{BASE_URL}/competition/register",
            json={"name": AGENT_NAME},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            player_id = data["player_id"]
            registered_today = datetime.now(ET).strftime("%Y-%m-%d")
            log(f"✅ Registered! ID: {player_id}")
            return True
        else:
            detail = resp.json().get("detail", resp.text)
            if "already registered" in detail.lower():
                log(f"Already registered today")
                return False
            log(f"❌ Registration failed: {detail}")
            return False
    except Exception as e:
        log(f"Error registering: {e}")
        return False

def submit_guess(round_num: int):
    global guessed_rounds
    
    if not player_id:
        log("Not registered yet!")
        return False
    
    if round_num in guessed_rounds:
        return False
    
    # Strategy: slightly randomized around expected value
    total = random.choice([16, 17, 17, 17, 18, 18, 19])
    individual = [random.choice([3, 3, 3, 4, 4, 4]) for _ in range(5)]
    
    try:
        resp = requests.post(
            f"{BASE_URL}/competition/guess",
            json={
                "player_id": player_id,
                "round_num": round_num,
                "total": total,
                "individual": individual
            },
            timeout=10
        )
        if resp.status_code == 200:
            guessed_rounds.add(round_num)
            log(f"🎯 Round {round_num} guess: total={total}, dice={individual}")
            return True
        else:
            detail = resp.json().get("detail", resp.text)
            if "already submitted" in detail.lower():
                guessed_rounds.add(round_num)
            log(f"❌ Guess failed: {detail}")
            return False
    except Exception as e:
        log(f"Error submitting guess: {e}")
        return False

def check_results():
    try:
        resp = requests.get(f"{BASE_URL}/competition/results", timeout=10)
        if resp.status_code == 200:
            results = resp.json()
            log(f"📊 Today's results:")
            for r in results.get("rankings", [])[:5]:
                marker = "👉" if r.get("player_id") == player_id else "  "
                log(f"  {marker} #{r['rank']} {r['name']}: {r['total_score']} pts")
    except:
        pass

def reset_for_new_day():
    global player_id, registered_today, guessed_rounds
    player_id = None
    registered_today = None
    guessed_rounds = set()
    log("🔄 Reset for new day")

def run():
    global registered_today
    
    log(f"🤖 Competition Agent starting: {AGENT_NAME}")
    log(f"📡 Server: {BASE_URL}")
    
    while True:
        state = get_state()
        
        if state is None:
            time.sleep(POLL_INTERVAL)
            continue
        
        # Check if it's a new day
        today = datetime.now(ET).strftime("%Y-%m-%d")
        if registered_today and registered_today != today:
            reset_for_new_day()
        
        phase = state.get("phase", "unknown")
        current_round = state.get("current_round", 0)
        
        if not state.get("is_active", True):
            log("Competition has ended!")
            break
        
        # Registration phase
        if phase == "registration" and not player_id:
            log("📝 Registration open - registering...")
            register()
        
        # Guessing phases
        elif phase.startswith("guessing") and player_id:
            if current_round > 0 and current_round not in guessed_rounds:
                log(f"🎯 Guessing phase for round {current_round}")
                # Add small random delay for varied speed bonus
                time.sleep(random.uniform(0.5, 3))
                submit_guess(current_round)
        
        # Check results at end of day
        elif phase == "closed" and player_id:
            check_results()
            # Wait longer during closed phase
            time.sleep(60 * 5)  # 5 minutes
            continue
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        AGENT_NAME = sys.argv[1]
    
    try:
        run()
    except KeyboardInterrupt:
        log("👋 Shutting down")
