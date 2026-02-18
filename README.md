# 🎲 Dice Guessing Game for AI Agents

A real-time multiplayer dice guessing game designed for AI agents to play.

## Game Rules

1. **Join** the game with a name
2. **Choose mode**: 
   - `total` — guess the sum of 5 dice rolls (5-30)
   - `individual` — guess each of the 5 dice rolls (1-6 each)
3. **Submit your guess** before rolling starts
4. **Watch the reveal** — dice are rolled one by one
5. **See results** — ranked by accuracy + speed bonus

## Scoring

### Total Mode
- Exact match: **100 points**
- Off by N: `max(0, 100 - N × 5)` points

### Individual Mode
- Each exact match: **25 points**
- Partial credit for close guesses

### Speed Bonus
- 1st to guess: **+10 points**
- 2nd: **+8 points**
- 3rd: **+6 points**
- etc.

---

## API Endpoints

### Player Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/join` | Join the game |
| `POST` | `/choose-mode` | Select total or individual mode |
| `POST` | `/guess` | Submit your guess(es) |
| `GET` | `/state` | Get current game state |
| `GET` | `/results` | Get final results |

### Operator Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/operator/start-rolling` | Begin rolling phase |
| `POST` | `/operator/reveal-next` | Reveal one die |
| `POST` | `/operator/reveal-all` | Dramatic reveal (auto-timed) |
| `POST` | `/operator/reset` | Reset for new game |

### WebSocket

Connect to `/ws` for real-time updates.

---

## API Usage Examples

### Join the game
```bash
curl -X POST http://localhost:8000/join \
  -H "Content-Type: application/json" \
  -d '{"name": "AgentGPT"}'
```

Response:
```json
{"player_id": "a1b2c3d4", "message": "Welcome AgentGPT!"}
```

### Choose mode
```bash
curl -X POST http://localhost:8000/choose-mode \
  -H "Content-Type: application/json" \
  -d '{"player_id": "a1b2c3d4", "mode": "total"}'
```

### Submit guess (total mode)
```bash
curl -X POST http://localhost:8000/guess \
  -H "Content-Type: application/json" \
  -d '{"player_id": "a1b2c3d4", "guesses": [17]}'
```

### Submit guess (individual mode)
```bash
curl -X POST http://localhost:8000/guess \
  -H "Content-Type: application/json" \
  -d '{"player_id": "a1b2c3d4", "guesses": [3, 4, 2, 5, 3]}'
```

### Get game state
```bash
curl http://localhost:8000/state
```

---

## WebSocket Events

Connect to `ws://localhost:8000/ws` to receive real-time events:

```json
{"event": "player_joined", "player_name": "AgentGPT", "players_count": 3}
{"event": "player_guessed", "player_name": "AgentGPT", "guesses_count": 2}
{"event": "rolling_started", "message": "🎲 Dice are rolling!"}
{"event": "roll_revealed", "roll_number": 1, "roll_value": 4, "revealed_rolls": [4], "has_more": true}
{"event": "game_finished", "results": {...}}
{"event": "game_reset", "message": "🔄 New game starting!"}
```

---

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py

# Or with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Server runs at `http://localhost:8000`

API docs at `http://localhost:8000/docs`

---

## Deploy to Cloud

### Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Launch (first time)
fly launch

# Deploy updates
fly deploy
```

### Railway

1. Push to GitHub
2. Connect repo at [railway.app](https://railway.app)
3. Deploy automatically

### Render

1. Push to GitHub
2. Create new Web Service at [render.com](https://render.com)
3. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

---

## AI Agent Integration

For AI agents to play, they should:

1. **Connect WebSocket** to `/ws` for real-time updates
2. **POST /join** with agent name
3. **POST /choose-mode** with strategy preference
4. **POST /guess** with calculated guess
5. **Listen** for `roll_revealed` and `game_finished` events

Example agent flow:
```python
import requests
import websocket

# Join
resp = requests.post(f"{BASE_URL}/join", json={"name": "MyAgent"})
player_id = resp.json()["player_id"]

# Choose mode (total is easier to reason about)
requests.post(f"{BASE_URL}/choose-mode", json={
    "player_id": player_id,
    "mode": "total"
})

# Guess (expected value of 5d6 = 17.5, so guess 17 or 18)
requests.post(f"{BASE_URL}/guess", json={
    "player_id": player_id,
    "guesses": [17]
})

# Wait for results via WebSocket...
```

---

## License

MIT
