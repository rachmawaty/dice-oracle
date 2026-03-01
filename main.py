# main.py - FastAPI server with REST + WebSocket
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from models import (
    JoinRequest, JoinResponse, GuessRequest,
    GameState, GameResults
)
from game import DiceGame
from competition import daily_competition
from run_agents import start_agents, stop_agents

# Timezone
ET = ZoneInfo("America/New_York")

# Enable/disable bot agents
ENABLE_AGENTS = False


# Competition request models
class CompetitionRegisterRequest(BaseModel):
    name: str


class CompetitionGuessRequest(BaseModel):
    player_id: str
    round_num: int
    total: int
    individual: list[int]

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


# Global game instance
game = DiceGame(max_players=100)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                dead_connections.append(connection)
        
        # Clean up dead connections
        for conn in dead_connections:
            self.disconnect(conn)


manager = ConnectionManager()

# Scheduler for automatic competition rolls
scheduler = AsyncIOScheduler(timezone=ET)

# Store the event loop for scheduler callbacks
event_loop = None


async def scheduled_roll(round_num: int):
    """Execute scheduled dice roll for competition."""
    print(f"🎲 [Scheduler] Rolling round {round_num}...")
    success, message, result = daily_competition.roll_round(round_num)
    
    if success:
        print(f"✅ [Scheduler] Round {round_num}: {result}")
        # Broadcast to WebSocket clients
        await manager.broadcast({
            "event": "competition_round_rolled",
            "round_num": round_num,
            "result": result
        })
        
        # Update leaderboard after final round
        if round_num == 3:
            daily_competition.update_leaderboard()
            print("✅ [Scheduler] Leaderboard updated")
    else:
        print(f"⚠️ [Scheduler] Roll skipped: {message}")


def roll_round_1():
    if event_loop:
        asyncio.run_coroutine_threadsafe(scheduled_roll(1), event_loop)

def roll_round_2():
    if event_loop:
        asyncio.run_coroutine_threadsafe(scheduled_roll(2), event_loop)

def roll_round_3():
    if event_loop:
        asyncio.run_coroutine_threadsafe(scheduled_roll(3), event_loop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global event_loop
    
    # Startup
    print("🎲 Dice Game Server starting...")
    
    # Capture the event loop for scheduler callbacks
    event_loop = asyncio.get_running_loop()
    
    # Schedule competition rolls (Eastern Time)
    # Round 1 at 1:00 PM ET
    scheduler.add_job(roll_round_1, CronTrigger(hour=13, minute=0, timezone=ET), id="roll_1")
    # Round 2 at 2:00 PM ET
    scheduler.add_job(roll_round_2, CronTrigger(hour=14, minute=0, timezone=ET), id="roll_2")
    # Round 3 at 3:00 PM ET
    scheduler.add_job(roll_round_3, CronTrigger(hour=15, minute=0, timezone=ET), id="roll_3")
    
    scheduler.start()
    print("🕐 Competition scheduler started (rolls at 1 PM, 2 PM, 3 PM ET)")
    print(f"📅 Server time: {datetime.now(ET).strftime('%Y-%m-%d %I:%M %p ET')}")
    
    # Start bot agents
    if ENABLE_AGENTS:
        start_agents()
    
    yield
    
    # Shutdown
    if ENABLE_AGENTS:
        stop_agents()
    scheduler.shutdown()
    print("🎲 Dice Game Server shutting down...")


app = FastAPI(
    title="Dice Guessing Game",
    description="A real-time dice guessing game for AI agents - guess BOTH total and individual rolls!",
    version="2.0.0",
    lifespan=lifespan
)

# CORS for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== STATIC FILES ==============

@app.get("/game", include_in_schema=False)
async def serve_game_ui():
    """Serve the game monitoring UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/agents", include_in_schema=False)
async def serve_agents_ui():
    """Serve the agent control panel."""
    return FileResponse(STATIC_DIR / "agents.html")


@app.get("/competition", include_in_schema=False)
async def serve_competition_ui():
    """Serve the daily dice roll competition page."""
    return FileResponse(STATIC_DIR / "competition.html")


@app.get("/history", include_in_schema=False)
async def serve_history_ui():
    """Serve the competition history page."""
    return FileResponse(STATIC_DIR / "history.html")


@app.get("/skill", include_in_schema=False)
async def serve_skill_md():
    """Serve the SKILL.md documentation."""
    skill_path = Path(__file__).parent / "SKILL.md"
    return FileResponse(skill_path, media_type="text/markdown")


@app.get("/heartbeat", include_in_schema=False)
async def serve_heartbeat_md():
    """Serve the HEARTBEAT.md documentation."""
    heartbeat_path = Path(__file__).parent / "HEARTBEAT.md"
    return FileResponse(heartbeat_path, media_type="text/markdown")


@app.get("/guide", include_in_schema=False)
async def serve_guide():
    """Documentation hub for AI agents."""
    return FileResponse(STATIC_DIR / "guide.html")


# ============== REST API ENDPOINTS ==============

@app.get("/")
async def root():
    """Health check and game info."""
    return {
        "game": "Dice Guessing Game",
        "version": "2.0.0",
        "description": "Guess BOTH the total AND each individual die roll!",
        "status": "running",
        "documentation": {
            "guide": "/guide - Documentation hub",
            "skill": "/skill - Full API reference (SKILL.md)",
            "heartbeat": "/heartbeat - Polling guide (HEARTBEAT.md)",
            "swagger": "/docs - Interactive API docs"
        },
        "endpoints": {
            "join": "POST /join",
            "guess": "POST /guess (requires total + individual)",
            "state": "GET /state",
            "results": "GET /results",
            "websocket": "WS /ws"
        },
        "scoring": {
            "total_accuracy": "max 100 pts (exact=100, -5 per off)",
            "individual_accuracy": "max 100 pts (20 per die, partial credit)",
            "speed_bonus": "max 10 pts (1st=10, 2nd=8, ...)",
            "max_possible": 210
        }
    }


@app.post("/join", response_model=JoinResponse)
async def join_game(request: JoinRequest):
    """Join the game as a player."""
    success, message, player_id = game.join(request.name)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Broadcast player joined
    await manager.broadcast({
        "event": "player_joined",
        "player_name": request.name,
        "players_count": len(game.players)
    })
    
    return JoinResponse(player_id=player_id, message=message)


@app.post("/guess")
async def submit_guess(request: GuessRequest):
    """Submit your guesses - BOTH total and individual required."""
    success, message = game.submit_guess(
        request.player_id, 
        request.total, 
        request.individual
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Broadcast that someone guessed (without revealing the guess)
    player = game.players.get(request.player_id)
    await manager.broadcast({
        "event": "player_guessed",
        "player_name": player.name if player else "Unknown",
        "guesses_count": sum(
            1 for p in game.players.values() 
            if p.guess_total is not None and p.guess_individual is not None
        )
    })
    
    return {"success": True, "message": message}


@app.get("/state")
async def get_state():
    """Get current game state."""
    return game.get_state()


@app.get("/results")
async def get_results():
    """Get game results (only available in results phase)."""
    if game.results is None:
        raise HTTPException(status_code=400, detail="Results not available yet")
    
    return game.results.model_dump()


# ============== COMPETITION API ENDPOINTS ==============

@app.get("/competition/state")
async def competition_state():
    """Get current daily competition state."""
    return daily_competition.get_state()


@app.get("/competition/players")
async def competition_players():
    """Get list of registered players for today."""
    return {"players": daily_competition.get_players()}


@app.post("/competition/register")
async def competition_register(request: CompetitionRegisterRequest):
    """Register for today's competition."""
    success, message, player_id = daily_competition.register(request.name)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    await manager.broadcast({
        "event": "competition_player_joined",
        "player_name": request.name,
        "players_count": len(daily_competition.players)
    })
    
    return {"success": True, "message": message, "player_id": player_id}


@app.post("/competition/guess")
async def competition_guess(request: CompetitionGuessRequest):
    """Submit a guess for current competition round."""
    success, message = daily_competition.submit_guess(
        request.player_id,
        request.round_num,
        request.total,
        request.individual
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    await manager.broadcast({
        "event": "competition_guess_submitted",
        "round_num": request.round_num
    })
    
    return {"success": True, "message": message}


@app.get("/competition/round/{round_num}")
async def competition_round_result(round_num: int):
    """Get result for a specific round."""
    result = daily_competition.get_round_result(round_num)
    
    if result is None:
        raise HTTPException(status_code=404, detail=f"Round {round_num} not rolled yet")
    
    return result


@app.get("/competition/results")
async def competition_results():
    """Get full results for today's competition."""
    return daily_competition.get_today_results()


@app.get("/competition/leaderboard")
async def competition_leaderboard():
    """Get overall leaderboard across all days."""
    leaderboard = daily_competition.get_leaderboard()
    
    # Sort players by total score
    players_list = [
        {"name": name, **data}
        for name, data in leaderboard.get("players", {}).items()
    ]
    players_list.sort(key=lambda x: -x.get("total_score", 0))
    
    return {
        "players": players_list,
        "last_updated": leaderboard.get("last_updated")
    }


@app.get("/competition/history")
async def competition_history():
    """Get full competition history across all days, grouped by date with actual rolls."""
    history_by_date = daily_competition.get_history()
    
    # Convert to list sorted by date (newest first)
    history_list = [
        {"date": date, **data}
        for date, data in sorted(history_by_date.items(), reverse=True)
    ]
    
    return {"history": history_list}


@app.post("/competition/operator/roll/{round_num}")
async def competition_roll(round_num: int):
    """[Operator] Manually trigger a roll for a round."""
    success, message, result = daily_competition.roll_round(round_num)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    await manager.broadcast({
        "event": "competition_round_rolled",
        "round_num": round_num,
        "result": result
    })
    
    return {"success": True, "message": message, "result": result}


@app.post("/competition/operator/update-leaderboard")
async def competition_update_leaderboard():
    """[Operator] Update the overall leaderboard with today's results."""
    daily_competition.update_leaderboard()
    return {"success": True, "message": "Leaderboard updated"}


# ============== GAME OPERATOR ENDPOINTS ==============

@app.post("/operator/start-rolling")
async def operator_start_rolling():
    """[Operator] Start the rolling phase."""
    success, message = game.start_rolling()
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    await manager.broadcast({
        "event": "rolling_started",
        "message": "🎲 Dice are rolling!"
    })
    
    return {"success": True, "message": message}


@app.post("/operator/reveal-next")
async def operator_reveal_next():
    """[Operator] Reveal the next dice roll."""
    has_more, roll_value = game.reveal_next_roll()
    
    if roll_value is None:
        raise HTTPException(status_code=400, detail="No more rolls to reveal")
    
    roll_number = len(game.revealed_rolls)
    
    await manager.broadcast({
        "event": "roll_revealed",
        "roll_number": roll_number,
        "roll_value": roll_value,
        "revealed_rolls": game.revealed_rolls,
        "has_more": has_more
    })
    
    return {
        "roll_number": roll_number,
        "roll_value": roll_value,
        "has_more": has_more
    }


@app.post("/operator/reveal-all")
async def operator_reveal_all():
    """[Operator] Reveal all dice with delays (dramatic mode)."""
    success, message = game.start_rolling()
    
    if not success and game.phase.value != "rolling":
        raise HTTPException(status_code=400, detail=message)
    
    await manager.broadcast({
        "event": "rolling_started",
        "message": "🎲 Dice are rolling!"
    })
    
    # Reveal each die with a delay
    for i in range(5):
        await asyncio.sleep(1.5)  # 1.5 second delay between reveals
        has_more, roll_value = game.reveal_next_roll()
        
        if roll_value is not None:
            await manager.broadcast({
                "event": "roll_revealed",
                "roll_number": i + 1,
                "roll_value": roll_value,
                "revealed_rolls": game.revealed_rolls,
                "has_more": has_more
            })
    
    # Calculate and broadcast results
    await asyncio.sleep(1)
    results = game.calculate_results()
    
    await manager.broadcast({
        "event": "game_finished",
        "results": results.model_dump()
    })
    
    return {"success": True, "message": "All rolls revealed", "results": results.model_dump()}


@app.post("/operator/reset")
async def operator_reset():
    """[Operator] Reset the game for a new round."""
    game.reset()
    
    await manager.broadcast({
        "event": "game_reset",
        "message": "🔄 New game starting!"
    })
    
    return {"success": True, "message": "Game reset"}


# ============== WEBSOCKET ==============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await manager.connect(websocket)
    
    # Send current state on connect
    await websocket.send_json({
        "event": "connected",
        "state": game.get_state()
    })
    
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            
            # Echo back or handle commands
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except:
                pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============== RUN ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
