"""
Title: server
Author: Claude Sonnet 5
Description:

Live bridge between the Mesa model and Unity: a FastAPI server that
keeps ONE GameManager instance alive in memory and lets Unity drive it
turn by turn over HTTP, instead of the offline export_simulation.py
flow (which runs a whole game upfront and hands Unity a fixed replay).

Reuses frame_from_model() from export_simulation.py, so a live frame
and an exported/replayed frame are byte-for-byte the same JSON shape
that MapGenerator/TileController/HudController already parse -- the
Unity-side scripts don't need to know whether they're talking to a
live server or replaying a file.

Run with: uvicorn server:app --reload --port 8000
Docs (Swagger UI, useful to test without Unity): http://localhost:8000/docs

Endpoints:
POST /game/new           -> start a new game
GET  /game/state         -> current frame, no side effects
POST /game/step          -> advance {count} individual agent-turns
POST /game/focus/{id}    -> mark an agent as focused
POST /game/focus/clear   -> clear focus

Functions:
_build_response
"""

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import  GameManager as GameManager

app = FastAPI(title="Flashpoint Bridge")

# Permite pegarle desde un build WebGL (que corre en el navegador y sí
# aplica CORS) sin tener que tocar esto despues. En un build de
# escritorio (standalone) o desde el editor no hace falta, pero no
# molesta dejarlo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Unica partida viva en memoria. Un proyecto escolar de un jugador no
# necesita manejar varias partidas/sesiones concurrentes; si hiciera
# falta, esto se cambiaria por un dict {session_id: GameManager}.
game: Optional[GameManager.GameManager] = None


class NewGameRequest(BaseModel):
    num_firefighters: int = 6
    seed: Optional[int] = None
    strategy: str = "optimized"


class StepRequest(BaseModel):
    count: int = 1


def _build_response(model):
    """
    Name: _build_response
    Description: Builds the JSON body returned by every endpoint that
                 touches the game. Uses GameManager.to_dict() directly
                 -- Unity's MapGenerator/AgentManager/MovementPlayer
                 were built against exactly that shape (tiles with
                 agentIds, top-level agents[], top-level movements[]),
                 so this must stay a straight passthrough rather than
                 a hand-rolled reshaping of the state. Adds 3 fields
                 Unity uses to know when to stop asking for more turns
                 (JsonUtility ignores fields it doesn't recognize, so
                 this is safe to feed straight into
                 GameManager.ApplyGameUpdate(json) on the Unity side).
    Inputs: model (GameManager)
    Outputs: dict -> to_dict() + {gameOver, win, loseReason}
    Usage: called by every route handler below.
    """
    data = model.to_dict()
    data["gameOver"] = model.win() or model.lose()
    data["win"] = model.win()
    data["loseReason"] = model.get_lose_reason()
    return data


def _require_game():
    if game is None:
        raise HTTPException(status_code=400, detail="No hay partida activa. Llama primero a /game/new.")
    return game


@app.post("/game/new")
def new_game(body: NewGameRequest):
    global game
    game = GameManager.GameManager(
        num_firefighters=body.num_firefighters,
        seed=body.seed,
        strategy=body.strategy,
    )
    return _build_response(game)


@app.get("/game/state")
def get_state():
    return _build_response(_require_game())


@app.post("/game/step")
def step(body: StepRequest = StepRequest()):
    model = _require_game()
    count = max(1, body.count)

    for _ in range(count):
        if model.win() or model.lose():
            break
        model.step()

    return _build_response(model)


@app.post("/game/focus/clear")
def clear_focus():
    # DEBE ir antes de /game/focus/{agent_id}: FastAPI matchea rutas en
    # orden de declaracion, y si esta fuera, "clear" caeria en la ruta
    # parametrizada e intentaria convertirse (sin exito) a int.
    model = _require_game()
    model.clear_focus()
    return _build_response(model)


@app.post("/game/focus/{agent_id}")
def focus(agent_id: int):
    model = _require_game()
    model.set_focus(agent_id)
    return _build_response(model)
