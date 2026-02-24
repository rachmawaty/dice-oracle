#!/usr/bin/env python3
"""
Dice Oracle - Auto-playing Agent Bot
Runs in background, auto-joins games and submits guesses.
"""

import requests
import time
import random
import sys
import os

# Configuration
BASE_URL = os.environ.get("DICE_ORACLE_URL", "http://localhost:8000")
AGENT_NAME = os.environ.get("AGENT_NAME", f"Bot-{random.randint(100,999)}")
POLL_INTERVAL = 3  # seconds

# Agent state
player_id = None
has_guessed = False
last_phase = None

def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{AGENT_NAME}] {msg}", flush=True)

def get_state():
    try:
        resp = requests.get(f"{BASE_URL}/state", timeout=5)
        return resp.json()
    except Exception as e:
        log(f"Error getting state: {e}")
        return None

def join_game():
    global player_id
    try:
        resp = requests.post(
            f"{BASE_URL}/join",
            json={"name": AGENT_NAME},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            player_id = data["player_id"]
            log(f"✅ Joined! ID: {player_id}")
            return True
        else:
            log(f"❌ Join failed: {resp.json().get('detail', resp.text)}")
            return False
    except Exception as e:
        log(f"Error joining: {e}")
        return False

def submit_guess():
    global has_guessed
    if not player_id:
        return False
    
    # Strategy: randomize a bit around expected value
    total = random.randint(15, 20)  # Expected is 17.5
    individual = [random.randint(2, 5) for _ in range(5)]  # Favor middle values
    
    try:
        resp = requests.post(
            f"{BASE_URL}/guess",
            json={
                "player_id": player_id,
                "total": total,
                "individual": individual
            },
            timeout=5
        )
        if resp.status_code == 200:
            has_guessed = True
            log(f"🎯 Guessed! Total: {total}, Dice: {individual}")
            return True
        else:
            log(f"❌ Guess failed: {resp.json().get('detail', resp.text)}")
            return False
    except Exception as e:
        log(f"Error guessing: {e}")
        return False

def check_results():
    try:
        resp = requests.get(f"{BASE_URL}/results", timeout=5)
        if resp.status_code == 200:
            results = resp.json()
            log(f"🎲 Results: {results['rolls']} = {results['total']}")
            
            # Find our ranking
            for r in results.get("rankings", []):
                if r["player_id"] == player_id:
                    log(f"🏆 Rank #{r['rank']} - Score: {r['score']} pts")
                    break
            
            if results.get("winner", {}).get("player_id") == player_id:
                log("🥇 WE WON!")
    except:
        pass

def reset_state():
    global player_id, has_guessed
    player_id = None
    has_guessed = False
    log("🔄 State reset for new game")

def run():
    global last_phase
    
    log(f"🤖 Starting agent: {AGENT_NAME}")
    log(f"📡 Server: {BASE_URL}")
    
    while True:
        state = get_state()
        
        if state is None:
            time.sleep(POLL_INTERVAL * 2)
            continue
        
        phase = state.get("phase", "unknown")
        
        # Detect game reset
        if last_phase == "results" and phase == "waiting":
            reset_state()
        
        last_phase = phase
        
        # Take action based on phase
        if phase in ["waiting", "guessing"]:
            # Check if we're already in the game
            my_player = None
            for p in state.get("players", []):
                if p.get("id") == player_id:
                    my_player = p
                    break
            
            if player_id is None:
                # Need to join
                if join_game():
                    time.sleep(0.5)  # Brief pause before guessing
                    submit_guess()
            elif my_player and not my_player.get("has_guessed", False):
                # Joined but haven't guessed
                submit_guess()
        
        elif phase == "results":
            if player_id:
                check_results()
                # Wait a bit before checking for reset
                time.sleep(5)
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        AGENT_NAME = sys.argv[1]
    
    try:
        run()
    except KeyboardInterrupt:
        log("👋 Shutting down")
