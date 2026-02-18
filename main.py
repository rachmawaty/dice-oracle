# main.py - FastAPI server with REST + WebSocket
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional

from models import (
    JoinRequest, JoinResponse, GuessRequest,
    GameState, GameResults
)
from game import DiceGame

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🎲 Dice Game Server starting...")
    yield
    # Shutdown
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


@app.get("/skill", include_in_schema=False)
async def serve_skill_md():
    """Serve the SKILL.md documentation."""
    skill_path = Path(__file__).parent / "SKILL.md"
    return FileResponse(skill_path, media_type="text/markdown")


# ============== REST API ENDPOINTS ==============

@app.get("/")
async def root():
    """Health check and game info."""
    return {
        "game": "Dice Guessing Game",
        "version": "2.0.0",
        "description": "Guess BOTH the total AND each individual die roll!",
        "status": "running",
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
