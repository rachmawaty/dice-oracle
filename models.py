# models.py - Data models for the dice game
from pydantic import BaseModel
from enum import Enum
from typing import Optional
import time


class GamePhase(str, Enum):
    WAITING = "waiting"        # Waiting for players to join
    GUESSING = "guessing"      # Players submitting guesses
    ROLLING = "rolling"        # Dice being rolled (reveals one by one)
    RESULTS = "results"        # Final scores shown


class Player(BaseModel):
    id: str
    name: str
    guess_total: Optional[int] = None       # Guess for sum of 5 dice
    guess_individual: Optional[list[int]] = None  # Guess for each die
    guess_timestamp: Optional[float] = None
    score: int = 0
    rank: Optional[int] = None


class JoinRequest(BaseModel):
    name: str


class JoinResponse(BaseModel):
    player_id: str
    message: str


class GuessRequest(BaseModel):
    player_id: str
    total: int              # Guess for sum (5-30)
    individual: list[int]   # Guess for each die (5 values, each 1-6)


class GameState(BaseModel):
    phase: GamePhase
    players_count: int
    max_players: int = 100
    revealed_rolls: list[int]  # Rolls revealed so far
    total_rolls: int = 5
    time_remaining: Optional[float] = None


class PlayerResult(BaseModel):
    player_id: str
    name: str
    guess_total: int
    guess_individual: list[int]
    score: int
    rank: int
    total_accuracy: int      # Score from total guess
    individual_accuracy: int  # Score from individual guesses
    speed_bonus: int


class GameResults(BaseModel):
    rolls: list[int]
    total: int
    rankings: list[PlayerResult]
    winner: Optional[PlayerResult] = None
