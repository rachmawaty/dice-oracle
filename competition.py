"""
Daily Competition - Backend Logic
Runs daily from registration through 3 rolling rounds.

Schedule (Eastern Time):
- 9:00 AM - 12:00 PM: Registration
- 12:00 PM - 1:00 PM: Guessing Round 1
- 1:00 PM: Roll #1
- 1:00 PM - 2:00 PM: Guessing Round 2
- 2:00 PM: Roll #2
- 2:00 PM - 3:00 PM: Guessing Round 3
- 3:00 PM: Roll #3 + Final Results
"""

import json
import random
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from zoneinfo import ZoneInfo

# Timezone
ET = ZoneInfo("America/New_York")

# Data directory
DATA_DIR = Path(__file__).parent / "competition_data"
DATA_DIR.mkdir(exist_ok=True)

# Competition end date
COMPETITION_END_DATE = date(2026, 3, 5)


class CompetitionPlayer(BaseModel):
    id: str
    name: str
    registered_at: str
    guesses: dict = {}  # round_num -> {"total": int, "individual": list, "timestamp": str}
    scores: dict = {}   # round_num -> {"total_acc": int, "individual_acc": int, "speed_bonus": int, "total": int}
    total_score: int = 0


class RoundResult(BaseModel):
    round_num: int
    rolls: list[int]
    total: int
    rolled_at: str


class DailyCompetition:
    def __init__(self):
        self.today = self._get_today()
        self.players: dict[str, CompetitionPlayer] = {}
        self.rounds: dict[int, RoundResult] = {}  # 1, 2, 3
        self.phase = "before"  # before, registration, guessing1, rolling1, guessing2, rolling2, guessing3, rolling3, closed
        self._load_today()
    
    def _get_today(self) -> str:
        return datetime.now(ET).strftime("%Y-%m-%d")
    
    def _get_data_file(self, day: str) -> Path:
        return DATA_DIR / f"competition_{day}.json"
    
    def _get_leaderboard_file(self) -> Path:
        return DATA_DIR / "leaderboard.json"
    
    def _load_today(self):
        """Load today's competition data if exists."""
        today = self._get_today()
        if today != self.today:
            # New day - reset
            self.today = today
            self.players = {}
            self.rounds = {}
        
        data_file = self._get_data_file(self.today)
        if data_file.exists():
            try:
                data = json.loads(data_file.read_text())
                self.players = {k: CompetitionPlayer(**v) for k, v in data.get("players", {}).items()}
                self.rounds = {int(k): RoundResult(**v) for k, v in data.get("rounds", {}).items()}
            except Exception as e:
                print(f"Error loading competition data: {e}")
        
        self._update_phase()
    
    def _save(self):
        """Save current competition state."""
        data = {
            "date": self.today,
            "players": {k: v.model_dump() for k, v in self.players.items()},
            "rounds": {k: v.model_dump() for k, v in self.rounds.items()}
        }
        self._get_data_file(self.today).write_text(json.dumps(data, indent=2))
    
    def _update_phase(self):
        """Determine current phase based on time."""
        now = datetime.now(ET)
        hour = now.hour
        minute = now.minute
        
        # Check if competition has ended
        if now.date() > COMPETITION_END_DATE:
            self.phase = "ended"
            return
        
        # Determine phase based on time and completed rounds
        if hour < 9:
            self.phase = "before"
        elif 9 <= hour < 12:
            self.phase = "registration"
        elif 12 <= hour < 13:
            if 1 in self.rounds:
                self.phase = "guessing2"  # Roll 1 done, guessing for round 2
            else:
                self.phase = "guessing1"
        elif hour == 13 and minute < 5 and 1 not in self.rounds:
            self.phase = "rolling1"
        elif 13 <= hour < 14:
            if 2 in self.rounds:
                self.phase = "guessing3"
            elif 1 in self.rounds:
                self.phase = "guessing2"
            else:
                self.phase = "guessing1"  # Late roll
        elif hour == 14 and minute < 5 and 2 not in self.rounds:
            self.phase = "rolling2"
        elif 14 <= hour < 15:
            if 3 in self.rounds:
                self.phase = "closed"
            elif 2 in self.rounds:
                self.phase = "guessing3"
            else:
                self.phase = "guessing2"
        elif hour == 15 and minute < 5 and 3 not in self.rounds:
            self.phase = "rolling3"
        elif hour >= 15:
            self.phase = "closed"
        else:
            self.phase = "closed"
    
    def get_current_round(self) -> int:
        """Get which round we're currently on (1, 2, or 3)."""
        if self.phase in ["guessing1", "rolling1"]:
            return 1
        elif self.phase in ["guessing2", "rolling2"]:
            return 2
        elif self.phase in ["guessing3", "rolling3"]:
            return 3
        return 0
    
    def is_active(self) -> bool:
        """Check if competition is currently active."""
        now = datetime.now(ET)
        return now.date() <= COMPETITION_END_DATE
    
    def register(self, player_id: str, name: str) -> tuple[bool, str]:
        """
        Register a player for today's competition using their permanent player_id.
        Can register anytime before competition closes.
        """
        self._load_today()
        self._update_phase()
        
        if not self.is_active():
            return False, "Competition has ended"
        
        # Allow registration anytime except when competition is closed or ended
        if self.phase in ["closed", "ended"]:
            return False, f"Registration is closed for today (current phase: {self.phase})"
        
        # Check if player_id already registered today
        if player_id in self.players:
            return False, f"Player ID {player_id} is already registered for today"
        
        # Check if name already registered today (prevent duplicate names per day)
        for p in self.players.values():
            if p.name.lower() == name.lower():
                return False, f"Name '{name}' is already registered for today"
        
        player = CompetitionPlayer(
            id=player_id,
            name=name,
            registered_at=datetime.now(ET).isoformat()
        )
        self.players[player_id] = player
        self._save()
        
        return True, f"Welcome to today's competition, {name}!"
    
    def submit_guess(self, player_id: str, round_num: int, total: int, individual: list[int]) -> tuple[bool, str]:
        """Submit a guess for a specific round."""
        self._load_today()
        self._update_phase()
        
        if player_id not in self.players:
            return False, "Player not found. Please register first."
        
        player = self.players[player_id]
        current_round = self.get_current_round()
        
        # Validate round
        if round_num != current_round:
            return False, f"Cannot submit for round {round_num}. Current round is {current_round}."
        
        if not self.phase.startswith("guessing"):
            return False, f"Not in guessing phase (current: {self.phase})"
        
        # Check if already guessed this round
        if str(round_num) in player.guesses:
            return False, f"Already submitted guess for round {round_num}"
        
        # Validate guess
        if not (5 <= total <= 30):
            return False, "Total must be between 5 and 30"
        
        if len(individual) != 5:
            return False, "Must provide exactly 5 individual guesses"
        
        for g in individual:
            if not (1 <= g <= 6):
                return False, "Each individual guess must be between 1 and 6"
        
        # Record guess
        player.guesses[str(round_num)] = {
            "total": total,
            "individual": individual,
            "timestamp": datetime.now(ET).isoformat()
        }
        self._save()
        
        return True, f"Guess submitted for round {round_num}!"
    
    def roll_round(self, round_num: int) -> tuple[bool, str, Optional[dict]]:
        """Execute a dice roll for a round (called by scheduler)."""
        self._load_today()
        
        if round_num in self.rounds:
            return False, f"Round {round_num} already rolled", None
        
        # Generate rolls
        rolls = [random.randint(1, 6) for _ in range(5)]
        total = sum(rolls)
        
        result = RoundResult(
            round_num=round_num,
            rolls=rolls,
            total=total,
            rolled_at=datetime.now(ET).isoformat()
        )
        self.rounds[round_num] = result
        
        # Calculate scores for all players who guessed
        self._calculate_round_scores(round_num, rolls, total)
        
        self._save()
        self._update_phase()
        
        return True, f"Round {round_num} rolled: {rolls} = {total}", result.model_dump()
    
    def _calculate_round_scores(self, round_num: int, rolls: list[int], total: int):
        """Calculate scores for a round."""
        # Get players who guessed, sorted by timestamp for speed bonus
        guessers = []
        for player in self.players.values():
            if str(round_num) in player.guesses:
                guess = player.guesses[str(round_num)]
                guessers.append((player, guess))
        
        guessers.sort(key=lambda x: x[1]["timestamp"])
        
        for i, (player, guess) in enumerate(guessers):
            # Total accuracy (max 100)
            total_diff = abs(guess["total"] - total)
            total_acc = max(0, 100 - total_diff * 5)
            
            # Individual accuracy (max 100: 20 per die)
            individual_acc = 0
            for g, actual in zip(guess["individual"], rolls):
                if g == actual:
                    individual_acc += 20
                else:
                    diff = abs(g - actual)
                    individual_acc += max(0, 16 - diff * 4)
            
            # Speed bonus (max 10)
            speed_bonus = max(0, 10 - i * 2)
            
            round_total = total_acc + individual_acc + speed_bonus
            
            player.scores[str(round_num)] = {
                "total_acc": total_acc,
                "individual_acc": individual_acc,
                "speed_bonus": speed_bonus,
                "total": round_total
            }
            
            # Update total score
            player.total_score = sum(
                s.get("total", 0) for s in player.scores.values()
            )
    
    def get_state(self) -> dict:
        """Get current competition state."""
        self._load_today()
        self._update_phase()
        
        now = datetime.now(ET)
        
        # Calculate time until next phase
        next_phase_time = None
        if self.phase == "before":
            next_phase_time = "9:00 AM"
        elif self.phase == "registration":
            next_phase_time = "12:00 PM"
        elif self.phase == "guessing1":
            next_phase_time = "1:00 PM"
        elif self.phase == "guessing2":
            next_phase_time = "2:00 PM"
        elif self.phase == "guessing3":
            next_phase_time = "3:00 PM"
        
        return {
            "date": self.today,
            "phase": self.phase,
            "current_round": self.get_current_round(),
            "players_count": len(self.players),
            "rounds_completed": list(self.rounds.keys()),
            "next_phase_time": next_phase_time,
            "server_time": now.strftime("%I:%M %p ET"),
            "competition_ends": COMPETITION_END_DATE.isoformat(),
            "is_active": self.is_active()
        }
    
    def get_players(self) -> list[dict]:
        """Get list of registered players."""
        self._load_today()
        return [
            {
                "id": p.id,
                "name": p.name,
                "rounds_guessed": list(p.guesses.keys()),
                "total_score": p.total_score
            }
            for p in sorted(self.players.values(), key=lambda x: -x.total_score)
        ]
    
    def get_round_result(self, round_num: int) -> Optional[dict]:
        """Get result for a specific round."""
        self._load_today()
        if round_num not in self.rounds:
            return None
        
        result = self.rounds[round_num]
        
        # Get player rankings for this round
        rankings = []
        for player in self.players.values():
            if str(round_num) in player.scores:
                score = player.scores[str(round_num)]
                guess = player.guesses.get(str(round_num), {})
                rankings.append({
                    "player_id": player.id,
                    "name": player.name,
                    "guess_total": guess.get("total"),
                    "guess_individual": guess.get("individual"),
                    **score
                })
        
        rankings.sort(key=lambda x: -x["total"])
        for i, r in enumerate(rankings):
            r["rank"] = i + 1
        
        return {
            "round_num": round_num,
            "rolls": result.rolls,
            "total": result.total,
            "rolled_at": result.rolled_at,
            "rankings": rankings
        }
    
    def get_today_results(self) -> dict:
        """Get full results for today."""
        self._load_today()
        
        rounds_data = {}
        for rn in [1, 2, 3]:
            result = self.get_round_result(rn)
            if result:
                rounds_data[rn] = result
        
        # Overall rankings
        rankings = []
        for player in self.players.values():
            rankings.append({
                "player_id": player.id,
                "name": player.name,
                "total_score": player.total_score,
                "rounds_played": len(player.guesses),
                "scores_by_round": player.scores
            })
        
        rankings.sort(key=lambda x: -x["total_score"])
        for i, r in enumerate(rankings):
            r["rank"] = i + 1
        
        return {
            "date": self.today,
            "phase": self.phase,
            "rounds": rounds_data,
            "rankings": rankings,
            "winner": rankings[0] if rankings else None
        }
    
    def get_leaderboard(self) -> dict:
        """Get overall leaderboard across all days."""
        leaderboard_file = self._get_leaderboard_file()
        
        if leaderboard_file.exists():
            try:
                return json.loads(leaderboard_file.read_text())
            except:
                pass
        
        return {"players": {}, "last_updated": None}
    
    def get_history(self) -> dict:
        """Get competition history for all days, grouped by date with actual rolls."""
        history_by_date = {}
        
        # Read all competition data files
        for data_file in sorted(DATA_DIR.glob("competition_*.json"), reverse=True):
            try:
                data = json.loads(data_file.read_text())
                date = data.get("date")
                
                # Get actual dice rolls for each round
                rounds_rolls = {}
                for rn in [1, 2, 3]:
                    round_data = data.get("rounds", {}).get(str(rn))
                    if round_data:
                        rounds_rolls[rn] = {
                            "rolls": round_data.get("rolls"),
                            "total": round_data.get("total"),
                            "rolled_at": round_data.get("rolled_at")
                        }
                
                # Get all players with their results
                players = []
                for player_id, player_data in data.get("players", {}).items():
                    # Build round details
                    rounds_data = []
                    for rn in [1, 2, 3]:
                        guess = player_data.get("guesses", {}).get(str(rn))
                        score = player_data.get("scores", {}).get(str(rn))
                        
                        if guess:
                            rounds_data.append({
                                "round": rn,
                                "guess_total": guess.get("total"),
                                "guess_individual": guess.get("individual"),
                                "score": score.get("total") if score else 0
                            })
                    
                    players.append({
                        "player_id": player_data.get("id"),
                        "player_name": player_data.get("name"),
                        "rounds": rounds_data,
                        "total_score": player_data.get("total_score", 0)
                    })
                
                # Sort players by score (highest first)
                players.sort(key=lambda p: -p["total_score"])
                
                # Assign ranks
                for i, player in enumerate(players):
                    player["rank"] = i + 1
                
                history_by_date[date] = {
                    "date": date,
                    "rounds_rolls": rounds_rolls,
                    "players": players
                }
            except Exception as e:
                print(f"Error reading {data_file}: {e}")
        
        return history_by_date
    
    def update_leaderboard(self):
        """Update overall leaderboard with today's results."""
        if self.phase != "closed":
            return
        
        leaderboard = self.get_leaderboard()
        players_data = leaderboard.get("players", {})
        
        for player in self.players.values():
            if player.name not in players_data:
                players_data[player.name] = {
                    "total_score": 0,
                    "days_played": 0,
                    "rounds_played": 0,
                    "wins": 0
                }
            
            players_data[player.name]["total_score"] += player.total_score
            players_data[player.name]["days_played"] += 1
            players_data[player.name]["rounds_played"] += len(player.guesses)
        
        # Check for winner
        if self.players:
            winner = max(self.players.values(), key=lambda x: x.total_score)
            if winner.name in players_data:
                players_data[winner.name]["wins"] += 1
        
        leaderboard["players"] = players_data
        leaderboard["last_updated"] = datetime.now(ET).isoformat()
        
        self._get_leaderboard_file().write_text(json.dumps(leaderboard, indent=2))
    
    def _get_all_time_agents_file(self) -> Path:
        """Get path to all-time agents file."""
        return DATA_DIR / "all_time_agents.json"
    
    def _update_all_time_agents(self, agent_name: str):
        """Update the all-time agents list with a new or existing agent."""
        all_time_file = self._get_all_time_agents_file()
        
        if all_time_file.exists():
            try:
                all_time_data = json.loads(all_time_file.read_text())
            except:
                all_time_data = {"agents": []}
        else:
            all_time_data = {"agents": []}
        
        # Check if agent already exists
        agent_exists = any(a["name"].lower() == agent_name.lower() for a in all_time_data["agents"])
        
        if not agent_exists:
            all_time_data["agents"].append({
                "name": agent_name,
                "first_joined": datetime.now(ET).isoformat(),
                "last_seen": datetime.now(ET).isoformat()
            })
        else:
            # Update last_seen for existing agent
            for agent in all_time_data["agents"]:
                if agent["name"].lower() == agent_name.lower():
                    agent["last_seen"] = datetime.now(ET).isoformat()
                    break
        
        all_time_file.write_text(json.dumps(all_time_data, indent=2))
    
    def get_all_time_agents(self) -> list[dict]:
        """Get list of all agents who have ever participated."""
        all_time_file = self._get_all_time_agents_file()
        
        if not all_time_file.exists():
            return []
        
        try:
            all_time_data = json.loads(all_time_file.read_text())
            agents = all_time_data.get("agents", [])
            
            # Sort by first_joined (oldest first)
            agents.sort(key=lambda a: a.get("first_joined", ""))
            
            return agents
        except:
            return []


# Global instance
daily_competition = DailyCompetition()
