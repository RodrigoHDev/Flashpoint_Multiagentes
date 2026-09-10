"""
Title: export_simulation
Author: Claude Sonnet 5
Description:

Bridge between the Mesa model and Unity: runs one full game headlessly
and dumps every turn as a JSON "frame" matching the schema Unity's
MapGenerator/TileController/HudController already parse (see
FLASHPOINT_CUSTOM/Assets/JSONtest/mapa.json for a hand-written example
of a single frame). Unity has no live connection to Python here -- it
just plays back the exported frames in order (see SimulationPlayer.cs
on the Unity side).

Frame shape (one per turn, top-level fields match MapData + HudData
combined so a single JsonUtility.ToJson(frame) round-trip on the Unity
side satisfies both parsers unmodified):
{
  "turn": int, "width": int, "height": int,
  "buildingDamage": int, "saved": int, "lost": int, "focus": int,
  "cells": [ {"x", "y", "walls": {"up","down","left","right"},
              "fire", "poi", "firefighter": bool}, .. ]
}

The whole file is {"frames": [frame0, frame1, ..]} -- wrapped in an
object because Unity's JsonUtility cannot parse a bare top-level JSON
array.

Functions:
frame_from_model
run_and_export
"""

import argparse
import json
import os

import  GameManager as GameManager


def frame_from_model(model):
    """
    Name: frame_from_model
    Description: Serializes the model's CURRENT state into one frame
                 matching Unity's expected JSON schema. Unlike
                 GameManager._tile_to_dict (which lists agentIds per
                 cell for a richer future contract), this collapses
                 agent presence to a single bool per cell, since
                 TileController only toggles one firefighter object
                 per tile today.
    Inputs: model (GameManager)
    Outputs: dict -> one frame, JSON-serializable (plain int/bool,
             no numpy scalars)
    Usage: called once per turn by run_and_export().
    """
    cells = []
    for x in range(GameManager.WIDTH):
        for y in range(GameManager.HEIGHT):
            walls = model.buildingManager.get(x, y)
            has_firefighter = any(a.x == x and a.y == y for a in model.agentsList)
            cells.append({
                "x": x,
                "y": y,
                "walls": {
                    "up": int(walls[0]),
                    "down": int(walls[1]),
                    "left": int(walls[2]),
                    "right": int(walls[3]),
                },
                "fire": int(model.fireManager.get(x, y)),
                "poi": int(model.poiManager.get(x, y)),
                "firefighter": has_firefighter,
            })

    return {
        "turn": model.turn,
        "width": GameManager.WIDTH,
        "height": GameManager.HEIGHT,
        "buildingDamage": model.buildingManager.buildingDam,
        "saved": model.poiManager.getVictimsSaved(),
        "lost": model.poiManager.getVictimsLost(),
        "focus": model.focus,
        "cells": cells,
    }


def run_and_export(output_path, num_firefighters=6, seed=42, strategy="optimized", max_turns=500):
    """
    Name: run_and_export
    Description: Runs one full game turn-by-turn (same loop shape as
                 GameManager.run_limited, without the console
                 printing), capturing one frame per individual turn,
                 and writes them all to a single JSON file for Unity
                 to play back.
    Inputs: output_path (str, where to write the JSON file),
            num_firefighters (int), seed (int or None),
            strategy (str), max_turns (int, safety cap)
    Outputs: list[dict] -> the frames written (also returned for
             inspection/tests)
    Usage: `python export_simulation.py --out simulation.json`
    """
    model = GameManager.GameManager(num_firefighters=num_firefighters, seed=seed, strategy=strategy)
    frames = [frame_from_model(model)]

    turnos = 0
    while turnos < max_turns and not (model.win() or model.lose()):
        for agent in model.agentsList:
            model.turn += 1
            model.steps += 1
            turnos += 1

            terminado = model.step_agent(agent)
            frames.append(frame_from_model(model))

            if terminado or turnos >= max_turns:
                break

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"frames": frames}, f)

    print(f"Exported {len(frames)} frames ({turnos} turns) to {output_path}")
    return frames


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export a Flashpoint game as a JSON frame sequence for Unity playback.")
    parser.add_argument("--out", default="export/simulation.json", help="Output JSON path.")
    parser.add_argument("--firefighters", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strategy", default="optimized")
    parser.add_argument("--max-turns", type=int, default=500)
    args = parser.parse_args()

    run_and_export(
        args.out,
        num_firefighters=args.firefighters,
        seed=args.seed,
        strategy=args.strategy,
        max_turns=args.max_turns,
    )
