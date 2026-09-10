"""
Title: main
Author: Rodrigo Hurtado
Description:

Entry point script for running the firefighting simulation and
producing analysis charts. Runs two separate kinds of trials:

1. SINGLE RUN (verbose/debug): one full game, run turn-by-turn via
   run_limited(), printing a live trace to the console. Used to
   visually inspect / sanity-check that a single game behaves
   correctly (useful while developing or debugging Coordinator
   logic).

2. BATCH RUN (statistical): 100 independent games (seeds 0-99), run
   headless via Mesa's batch_run(), used to gather aggregate
   statistics across many games and produce the 3 summary charts
   below. This is what actually answers "how good is the strategy
   on average", as opposed to the single run, which only tells you
   whether one specific game worked.

Sections:
SINGLE RUN (TRIAL)
BATCH RUN (TRIAL)
DATA PREPARATION
CHART 1 - GAMES BY VICTIMS SAVED
CHART 2 - GAMES BY TURNS TO FINISH
CHART 3 - GAMES BY OUTCOME

"""

import  GameManager as GameManager
import mesa
from mesa.batchrunner import batch_run
import matplotlib.pyplot as plt
import pandas as pd


#------------------------------ SINGLE RUN (TRIAL) ---------------------------------
# Runs ONE game from start to finish (max 500 individual turns),
# printing per-turn state and per-agent debug traces to the console
# as it goes (verbose=True, debug=True). This is a manual/visual
# trial: it's not used for the charts below, it exists so a human
# can watch a single game unfold and catch obviously wrong behavior
# (e.g. an agent stuck, a POI never resolved) before trusting the
# aggregate statistics from the batch run.

model = GameManager.GameManager(num_firefighters=6, seed=42)
history = model.run_limited(max_turns=500, verbose=True, debug=True)

print(f"\nTurnos registrados en el historial: {len(history)}")


#------------------------------ BATCH RUN (TRIAL) ---------------------------------
# Runs 100 independent games (one per seed in range(100)), each
# capped at 500 individual turns (max_steps=500, matching the
# per-turn granularity of model.step()), using a single process
# (number_processes=1) and collecting data only ONCE per game at the
# end (data_collection_period=-1) instead of every turn, since only
# the final outcome of each game matters for these charts. Unlike
# the single run above, this trial is headless (no per-turn
# printing) and its only purpose is to produce a big enough sample
# of finished games to compute meaningful statistics.

resultados = batch_run(
    GameManager.GameManager,
    parameters={"num_firefighters": 6, "seed": range(1000), "strategy": "optimized"},
    iterations=1,
    max_steps=500,
    number_processes=1,
    data_collection_period=-1,
    display_progress=True,
)

df = pd.DataFrame(resultados)


#------------------------------ DATA PREPARATION ---------------------------------
# batch_run() returns one row per (RunId, agent) combination, since
# Mesa's DataCollector also records per-agent reporters (pos, ap,
# etc. -- see GameManager's agent_reporters). That means each game
# (RunId) appears 6 times (once per firefighter) with identical
# model-level columns (turn, buildingDam, savedVictims, lostVictims).
# For any metric that is about the GAME as a whole rather than about
# individual agents, we must first collapse back down to one row per
# RunId, or every count below would be inflated 6x.

# Como cada RunId tiene 6 filas (una por agente) para el mismo estado final,
# nos quedamos con una fila representativa por partida para las metricas
# de nivel-modelo (turnos, victimas, dano).
df_partidas = df.drop_duplicates(subset="RunId")[
    ["RunId", "turn", "buildingDam", "savedVictims", "lostVictims"]
].copy()

df_partidas["win"] = df_partidas["savedVictims"] >= 7


#------------------------------ CHART 1 - GAMES BY VICTIMS SAVED ---------------------------------
# Bar chart: how many games ended with each possible count of
# victims saved (0 through 7). Shows how consistently the strategy
# reaches the win threshold (7 saved) versus falling short by a
# little or a lot.

saved_counts = df_partidas["savedVictims"].value_counts().sort_index()

fig, ax = plt.subplots(figsize=(6, 4.5))
ax.bar(saved_counts.index.astype(str), saved_counts.values, color="#4C72B0")
ax.set_xlabel("Victimas salvadas")
ax.set_ylabel("Numero de partidas")
ax.set_title("Partidas segun victimas salvadas")
plt.tight_layout()
plt.savefig("victimas_salvadas.png", dpi=120)
plt.show()


#------------------------------ CHART 2 - GAMES BY TURNS TO FINISH ---------------------------------
# Bar chart: distribution of how many turns each game took before
# ending (win or lose), grouped into buckets of 10 turns each (e.g.
# "30-39", "40-49"). Useful to see whether games tend to resolve
# quickly or drag on close to the 500-turn cap.

df_partidas["turn_bucket"] = (df_partidas["turn"] // 10) * 10
turn_counts = df_partidas["turn_bucket"].value_counts().sort_index()
turn_labels = [f"{b}-{b+9}" for b in turn_counts.index]

fig, ax = plt.subplots(figsize=(6, 4.5))
ax.bar(turn_labels, turn_counts.values, color="#DD8452")
ax.set_xlabel("Rango de turnos")
ax.set_ylabel("Numero de partidas")
ax.set_title("Partidas segun turnos hasta terminar")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("turnos_hasta_terminar.png", dpi=120)
plt.show()


#------------------------------ CHART 3 - GAMES BY OUTCOME ---------------------------------
# Bar chart: how games broke down by final outcome category (won,
# lost to victims, lost to structural damage, or never finished
# within the turn cap). Re-derives df_partidas including
# "loseReason" (not selected in the first df_partidas above) so this
# chart can distinguish the two lose conditions from GameManager.lose().

df_partidas = df.drop_duplicates(subset="RunId")[
    ["RunId", "turn", "buildingDam", "savedVictims", "lostVictims", "loseReason"]
].copy()

def categorizar(row):
    """
    Name: categorizar
    Description: Classifies a single game's final row into one of
                 four outcome categories: "Gano" (won, 7+ victims
                 saved), "Perdio -- victimas" (lost, 4+ victims
                 lost), "Perdio -- dano estructural" (lost, 24+
                 structural damage), or "Sin terminar" (hit the
                 max_turns cap without winning or losing).
    Inputs: row (pandas.Series, one row of df_partidas)
    Outputs: str -> one of the four category labels above
    Usage: applied row-wise via df_partidas.apply() to build the
           "categoria" column used by Chart 3.
    """
    if row["savedVictims"] >= 7:
        return "Gano"
    elif row["loseReason"] == "victims":
        return "Perdio -- victimas"
    elif row["loseReason"] == "structural":
        return "Perdio -- dano estructural"
    else:
        return "Sin terminar"

df_partidas["categoria"] = df_partidas.apply(categorizar, axis=1)

conteo = df_partidas["categoria"].value_counts()

fig, ax = plt.subplots(figsize=(7, 4.5))
colores = {
    "Gano": "#55A868",
    "Perdio -- victimas": "#C44E52",
    "Perdio -- dano estructural": "#8172B2",
    "Sin terminar": "#999999",
}
ax.bar(conteo.index, conteo.values, color=[colores.get(c, "#333333") for c in conteo.index])
ax.set_ylabel("Numero de partidas")
ax.set_title("Resultado final de las partidas, por causa")
plt.xticks(rotation=15, ha="right")
plt.tight_layout()
plt.savefig("causas_derrota.png", dpi=120)
plt.show()