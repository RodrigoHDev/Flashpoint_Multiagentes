import GameManager
import mesa
from mesa.batchrunner import batch_run
import matplotlib.pyplot as plt
import pandas as pd



model = GameManager.GameManager(num_firefighters=6, seed=42)
history = model.run_limited(max_turns=500, verbose=True, debug=True)

print(f"\nTurnos registrados en el historial: {len(history)}")


resultados = batch_run(
    GameManager.GameManager,
    parameters={"num_firefighters": 6, "seed": range(100), "strategy": "optimized"},
    iterations=1,
    max_steps=500,
    number_processes=1,
    data_collection_period=-1,
    display_progress=True,
)

df = pd.DataFrame(resultados)


# Como cada RunId tiene 6 filas (una por agente) para el mismo estado final,
# nos quedamos con una fila representativa por partida para las metricas
# de nivel-modelo (turnos, victimas, dano).
df_partidas = df.drop_duplicates(subset="RunId")[
    ["RunId", "turn", "buildingDam", "savedVictims", "lostVictims"]
].copy()

df_partidas["win"] = df_partidas["savedVictims"] >= 7


#Grafica No. 1

saved_counts = df_partidas["savedVictims"].value_counts().sort_index()

fig, ax = plt.subplots(figsize=(6, 4.5))
ax.bar(saved_counts.index.astype(str), saved_counts.values, color="#4C72B0")
ax.set_xlabel("Victimas salvadas")
ax.set_ylabel("Numero de partidas")
ax.set_title("Partidas segun victimas salvadas")
plt.tight_layout()
plt.savefig("victimas_salvadas.png", dpi=120)
plt.show()


#Grafica No.2
df_partidas["turn_bucket"] = (df_partidas["turn"] // 10) * 10
turn_counts = df_partidas["turn_bucket"].value_counts().sort_index()
turn_labels = [f"{b}-{b+9}" for b in turn_counts.index]

fig, ax = plt.subplots(figsize=(6, 4.5))
ax.bar(turn_labels, turn_counts.values, color="#DD8452")
ax.set_xlabel("Rango de turnos")
ax.set_ylabel("Numero de partidas")
ax.set_title("Partidas segun turnos hasta terminar")
plt.tight_layout()
plt.savefig("turnos_hasta_terminar.png", dpi=120)
plt.show()



#Grafica No.3


df_partidas = df.drop_duplicates(subset="RunId")[
    ["RunId", "turn", "buildingDam", "savedVictims", "lostVictims", "loseReason"]
].copy()

def categorizar(row):
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