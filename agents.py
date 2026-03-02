"""
Permanent Agent Registration System
Agents register once and get a permanent player_id.
They use this player_id to join daily competitions.
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Data directory
DATA_DIR = Path(__file__).parent / "competition_data"
DATA_DIR.mkdir(exist_ok=True)

AGENTS_FILE = DATA_DIR / "agents_registry.json"


class Agent(BaseModel):
    player_id: str
    name: str
    registered_at: str
    last_active: str
    total_competitions: int = 0
    total_score: int = 0


class AgentRegistry:
    """Manages permanent agent registrations."""
    
    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self._load()
    
    def _load(self):
        """Load agents from file."""
        if AGENTS_FILE.exists():
            try:
                data = json.loads(AGENTS_FILE.read_text())
                self.agents = {k: Agent(**v) for k, v in data.get("agents", {}).items()}
            except Exception as e:
                print(f"Error loading agents registry: {e}")
                self.agents = {}
    
    def _save(self):
        """Save agents to file."""
        data = {
            "agents": {k: v.model_dump() for k, v in self.agents.items()},
            "last_updated": datetime.now(ET).isoformat()
        }
        AGENTS_FILE.write_text(json.dumps(data, indent=2))
    
    def register_agent(self, name: str) -> tuple[bool, str, Optional[str]]:
        """
        Register a new agent and get a permanent player_id.
        Can be called anytime.
        """
        # Check if name already exists
        for agent in self.agents.values():
            if agent.name.lower() == name.lower():
                return False, f"Agent name '{name}' is already registered (player_id: {agent.player_id})", None
        
        # Generate unique player_id
        player_id = f"{random.randint(10000, 99999)}"
        while player_id in self.agents:
            player_id = f"{random.randint(10000, 99999)}"
        
        # Create agent
        agent = Agent(
            player_id=player_id,
            name=name,
            registered_at=datetime.now(ET).isoformat(),
            last_active=datetime.now(ET).isoformat()
        )
        
        self.agents[player_id] = agent
        self._save()
        
        return True, f"Agent '{name}' registered successfully!", player_id
    
    def get_agent(self, player_id: str) -> Optional[Agent]:
        """Get agent by player_id."""
        self._load()  # Reload to get latest data
        return self.agents.get(player_id)
    
    def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Get agent by name."""
        self._load()
        for agent in self.agents.values():
            if agent.name.lower() == name.lower():
                return agent
        return None
    
    def update_activity(self, player_id: str):
        """Update agent's last active timestamp."""
        if player_id in self.agents:
            self.agents[player_id].last_active = datetime.now(ET).isoformat()
            self._save()
    
    def update_stats(self, player_id: str, competition_score: int):
        """Update agent's competition stats."""
        if player_id in self.agents:
            self.agents[player_id].total_competitions += 1
            self.agents[player_id].total_score += competition_score
            self.agents[player_id].last_active = datetime.now(ET).isoformat()
            self._save()
    
    def list_all_agents(self) -> list[dict]:
        """Get list of all registered agents."""
        self._load()
        agents_list = []
        for agent in self.agents.values():
            agents_list.append({
                "player_id": agent.player_id,
                "name": agent.name,
                "registered_at": agent.registered_at,
                "last_active": agent.last_active,
                "total_competitions": agent.total_competitions,
                "total_score": agent.total_score
            })
        
        # Sort by registration date (oldest first)
        agents_list.sort(key=lambda a: a["registered_at"])
        
        return agents_list


# Global instance
agent_registry = AgentRegistry()
