# game.py - Core game logic
import random
import time
import uuid
from typing import Optional
from models import Player, GamePhase, PlayerResult, GameResults


class DiceGame:
    def __init__(self, max_players: int = 100):
        self.max_players = max_players
        self.players: dict[str, Player] = {}
        self.phase = GamePhase.WAITING
        self.rolls: list[int] = []
        self.revealed_rolls: list[int] = []
        self.guess_start_time: Optional[float] = None
        self.results: Optional[GameResults] = None
    
    def reset(self):
        """Reset game for a new round."""
        self.players = {}
        self.phase = GamePhase.WAITING
        self.rolls = []
        self.revealed_rolls = []
        self.guess_start_time = None
        self.results = None
    
    def join(self, name: str) -> tuple[bool, str, Optional[str]]:
        """Player joins the game. Returns (success, message, player_id)."""
        if self.phase not in [GamePhase.WAITING, GamePhase.GUESSING]:
            return False, "Game already in progress (rolling or finished)", None
        
        if len(self.players) >= self.max_players:
            return False, "Game is full", None
        
        player_id = str(uuid.uuid4())[:8]
        self.players[player_id] = Player(id=player_id, name=name)
        return True, f"Welcome {name}!", player_id
    
    def submit_guess(self, player_id: str, total: int, individual: list[int]) -> tuple[bool, str]:
        """Player submits both guesses (total and individual)."""
        if player_id not in self.players:
            return False, "Player not found"
        
        player = self.players[player_id]
        
        if self.phase not in [GamePhase.WAITING, GamePhase.GUESSING]:
            return False, "Guessing phase is over"
        
        # Validate total guess
        if not (5 <= total <= 30):
            return False, "Total must be between 5 and 30"
        
        # Validate individual guesses
        if len(individual) != 5:
            return False, "Individual guesses must be exactly 5 numbers"
        for g in individual:
            if not (1 <= g <= 6):
                return False, "Each individual guess must be between 1 and 6"
        
        player.guess_total = total
        player.guess_individual = individual
        player.guess_timestamp = time.time()
        
        # Start guessing phase if not already
        if self.phase == GamePhase.WAITING:
            self.phase = GamePhase.GUESSING
            self.guess_start_time = time.time()
        
        return True, "Guesses submitted!"
    
    def start_rolling(self) -> tuple[bool, str]:
        """Transition to rolling phase and generate dice rolls."""
        if self.phase != GamePhase.GUESSING:
            return False, "Not in guessing phase"
        
        # Generate all 5 rolls
        self.rolls = [random.randint(1, 6) for _ in range(5)]
        self.revealed_rolls = []
        self.phase = GamePhase.ROLLING
        return True, "Rolling dice!"
    
    def reveal_next_roll(self) -> tuple[bool, Optional[int]]:
        """Reveal the next dice roll. Returns (has_more, roll_value)."""
        if self.phase != GamePhase.ROLLING:
            return False, None
        
        if len(self.revealed_rolls) >= 5:
            return False, None
        
        next_roll = self.rolls[len(self.revealed_rolls)]
        self.revealed_rolls.append(next_roll)
        
        has_more = len(self.revealed_rolls) < 5
        return has_more, next_roll
    
    def calculate_results(self) -> GameResults:
        """Calculate final scores and rankings."""
        self.phase = GamePhase.RESULTS
        actual_total = sum(self.rolls)
        
        player_results: list[PlayerResult] = []
        
        # Sort players by guess timestamp for speed bonus calculation
        guessing_players = [
            p for p in self.players.values() 
            if p.guess_total is not None and p.guess_individual is not None
        ]
        guessing_players.sort(key=lambda p: p.guess_timestamp or float('inf'))
        
        for i, player in enumerate(guessing_players):
            # Calculate TOTAL accuracy (max 100 points)
            total_diff = abs(player.guess_total - actual_total)
            total_accuracy = max(0, 100 - total_diff * 5)
            
            # Calculate INDIVIDUAL accuracy (max 100 points: 20 per die)
            individual_accuracy = 0
            for guess, actual in zip(player.guess_individual, self.rolls):
                if guess == actual:
                    individual_accuracy += 20  # Exact match
                else:
                    diff = abs(guess - actual)
                    individual_accuracy += max(0, 16 - diff * 4)  # Partial credit
            
            # Speed bonus (first = +10, second = +8, third = +6, etc.)
            speed_bonus = max(0, 10 - i * 2)
            
            # Combined score: both accuracies + speed
            total_score = total_accuracy + individual_accuracy + speed_bonus
            
            player_results.append(PlayerResult(
                player_id=player.id,
                name=player.name,
                guess_total=player.guess_total,
                guess_individual=player.guess_individual,
                score=total_score,
                rank=0,  # Will be set after sorting
                total_accuracy=total_accuracy,
                individual_accuracy=individual_accuracy,
                speed_bonus=speed_bonus
            ))
        
        # Sort by score descending and assign ranks
        player_results.sort(key=lambda p: p.score, reverse=True)
        for i, result in enumerate(player_results):
            result.rank = i + 1
            # Update player object too
            if result.player_id in self.players:
                self.players[result.player_id].score = result.score
                self.players[result.player_id].rank = result.rank
        
        self.results = GameResults(
            rolls=self.rolls,
            total=actual_total,
            rankings=player_results,
            winner=player_results[0] if player_results else None
        )
        
        return self.results
    
    def get_state(self) -> dict:
        """Get current game state for API response."""
        return {
            "phase": self.phase.value,
            "players_count": len(self.players),
            "max_players": self.max_players,
            "revealed_rolls": self.revealed_rolls,
            "total_rolls": 5,
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "has_guessed": p.guess_total is not None and p.guess_individual is not None
                }
                for p in self.players.values()
            ]
        }
