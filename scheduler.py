#!/usr/bin/env python3
"""
Competition Scheduler - Auto-rolls dice at scheduled times.
Run this as a background service or cron job.

Schedule (Eastern Time):
- 1:00 PM: Roll Round 1
- 2:00 PM: Roll Round 2
- 3:00 PM: Roll Round 3 + Update Leaderboard
"""

import time
import requests
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BASE_URL = os.environ.get("DICE_ORACLE_URL", "http://localhost:8000")
COMPETITION_END_DATE = date(2026, 3, 5)

def log(msg):
    timestamp = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")
    print(f"[{timestamp}] {msg}", flush=True)

def roll_round(round_num: int):
    """Trigger a competition round roll."""
    try:
        resp = requests.post(
            f"{BASE_URL}/competition/operator/roll/{round_num}",
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("result", {})
            log(f"✅ Round {round_num} rolled: {result.get('rolls')} = {result.get('total')}")
            return True
        else:
            log(f"❌ Roll failed: {resp.json().get('detail', resp.text)}")
            return False
    except Exception as e:
        log(f"❌ Error rolling round {round_num}: {e}")
        return False

def update_leaderboard():
    """Update the overall leaderboard."""
    try:
        resp = requests.post(
            f"{BASE_URL}/competition/operator/update-leaderboard",
            timeout=10
        )
        if resp.status_code == 200:
            log("✅ Leaderboard updated")
        else:
            log(f"⚠️ Leaderboard update issue: {resp.text}")
    except Exception as e:
        log(f"❌ Error updating leaderboard: {e}")

def check_and_roll():
    """Check current time and roll if needed."""
    now = datetime.now(ET)
    
    # Check if competition has ended
    if now.date() > COMPETITION_END_DATE:
        log("Competition has ended (past March 5, 2026)")
        return False
    
    hour = now.hour
    minute = now.minute
    
    # Roll windows (roll in first 2 minutes of the hour)
    if minute > 2:
        return True  # Not time to roll yet
    
    if hour == 13:  # 1 PM
        log("🎲 Time for Round 1!")
        roll_round(1)
    elif hour == 14:  # 2 PM
        log("🎲 Time for Round 2!")
        roll_round(2)
    elif hour == 15:  # 3 PM
        log("🎲 Time for Round 3!")
        if roll_round(3):
            # Update leaderboard after final round
            time.sleep(2)
            update_leaderboard()
    
    return True

def run_scheduler():
    """Main scheduler loop."""
    log("🕐 Competition Scheduler started")
    log(f"📡 Server: {BASE_URL}")
    log(f"📅 Competition runs until: {COMPETITION_END_DATE}")
    
    last_check_hour = -1
    
    while True:
        now = datetime.now(ET)
        
        # Only check once per hour at the start of the hour
        if now.hour != last_check_hour and now.minute < 3:
            if not check_and_roll():
                log("Scheduler stopping - competition ended")
                break
            last_check_hour = now.hour
        
        # Sleep for 30 seconds
        time.sleep(30)

if __name__ == "__main__":
    run_scheduler()
