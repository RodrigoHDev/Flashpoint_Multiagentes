# Flash Point Fire Rescue — Simulación Multi-Agente

Simulación del juego de mesa *Flash Point Fire Rescue* implementada como un modelo
multi-agente con el framework **Mesa**. Un equipo de bomberos (agentes) debe rescatar
víctimas, controlar el fuego y evitar el colapso estructural del edificio, mientras un
**Coordinator** central les asigna objetivos de forma dinámica turno a turno usando un
algoritmo de generación de candidatos + matriz de costos + backtracking con poda.

El proyecto puede correrse de forma headless para análisis estadístico (`main.py`),
exportarse como una secuencia de frames JSON para reproducirse en Unity
(`export_simulation.py`), o transmitirse en vivo a un cliente externo vía un servidor
HTTP (`server.py`).

## Tabla de contenido

- [Arquitectura general](#arquitectura-general)
- [¿Qué pasa en cada step?](#qué-pasa-en-cada-step)
- [El algoritmo de coordinación](#el-algoritmo-de-coordinación)
- [Comportamiento del agente](#comportamiento-del-agente)
- [Servidor para transmisión JSON](#servidor-para-transmisión-json)
- [Diagrama de clases](#diagrama-de-clases)

---

## Arquitectura general

| Clase | Responsabilidad |
|---|---|
| `GameManager` (`mesa.Model`) | Orquesta la partida: crea managers y agentes, corre el ciclo de turnos, evalúa victoria/derrota, serializa el estado. |
| `BuildingManager` | Grid de `Tile` (paredes/puertas), daño estructural acumulado, costos de movimiento. |
| `FireManager` | Grid de fuego/humo, propagación, explosiones, shockwaves. |
| `PoiManager` | Puntos de interés (víctimas/falsas alarmas), su revelado y reposición. |
| `Coordinator` | Genera candidatos de tarea y decide qué agente va a dónde cada turno. |
| `Candidate` | Objeto ligero `(pos, tipo, prioridad)`: "esto existe y así de urgente es". |
| `Firefighter` (`mesa.Agent`) | Ejecuta su turno según la estrategia activa (`primitive`, `primitive_astar`, `optimized`). |
| `auxiliars.py` | Funciones compartidas: distancias, A*, Dijkstra, `triage_factor`, etc. (no es una clase). |
| `Dice` / `Tile` | Utilidades de bajo nivel (coordenadas aleatorias, celda individual). |

---

## ¿Qué pasa en cada step?

Un **step** de Mesa (`GameManager.step()`) equivale a **un turno de un solo agente**
(no una ronda completa), avanzando round-robin sobre `agentsList`. Internamente llama
a `step_agent(agent)`, que hace, en orden:

1. **Chequeo de fin de partida**: `lose()` (≥4 víctimas perdidas o ≥24 de daño
   estructural) y `win()` (≥7 víctimas salvadas). Si alguno se cumple, el turno no se
   ejecuta y se reporta que el juego terminó.
2. **`coordinator.coordinate_turn(...)`**: antes de que el agente actúe, el Coordinator
   revisa si hay agentes libres y, si hace falta, recalcula y aplica asignaciones de
   objetivo (`objetivo_actual`, `tipo_objetivo`) sobre ellos.
3. **`agent.act()`**: el bombero enfocado consume sus 4 puntos de acción moviéndose,
   derribando paredes, abriendo puertas, apagando fuego/humo, revelando POIs o
   salvando víctimas, según su `objetivo_actual` (o comportamiento primitivo de respaldo).
4. **`fireManager.putSmoke()`**: se tira el dado de fuego; la celda resultante avanza
   (vacía→humo/fuego, humo→fuego, fuego→explosión con posible daño en cadena).
5. **`poiManager.set()`**: se reponen POIs hasta tener 3 activos en el tablero.

Cada acción individual del agente (mover, cortar, apagar, etc.) dispara además
`GameManager.record_step()`, que registra un delta (`movements`) para poder reconstruir
la partida paso a paso más adelante (replay/análisis), no solo turno a turno.

---

## El algoritmo de coordinación

El `Coordinator` es quien decide **qué hace cada bombero libre**. Se ejecuta una vez
por turno (`coordinate_turn`) y sigue esta secuencia:

### 1. Liberación por triage
Si el tablero entra en estado crítico (`triage_factor(...) > 1`, por daño estructural
o cantidad de fuego activo) — ya sea porque **acaba de** volverse crítico o porque
**hubo una explosión** desde la última reoptimización — se liberan (`_liberar_comprometidos`)
todos los agentes que no cargan víctima ni están derribados, para que vuelvan a
competir por los objetivos más urgentes. Esto evita quedarse "casado" con asignaciones
viejas mientras el edificio se sigue quemando.

### 2. Generación de candidatos (`generate_candidates`)
Un **candidato** (`Candidate`) es una celda + tipo + prioridad: algo que un agente
podría ir a atender. Se generan combinando cuatro fuentes:

| Función | Qué detecta | Prioridad base |
|---|---|---|
| `scan_poi_candidates` | Cada POI sin revelar aún no asignado. | 10 |
| `scan_breach_points` | Vía BFS desde cada POI/víctima, la celda de fuego alcanzable más cercana por camino libre — el punto exacto por donde el fuego podría llegar a esa víctima. Generaliza al antiguo "fuego_amenaza". | hasta 20, según distancia |
| `scan_chain_breaks` | El "eslabón débil" de una cadena de fuego contigua (mínimo de la racha a cada lado + 1): romperlo ahí parte la cadena en dos más cortas en vez de solo atacar la orilla. | 8 + 3×score |
| `scan_general_fire` | Cualquier celda con fuego (prioridad sube con el daño estructural alrededor) o humo activo, sin importar si amenaza un POI — llena huecos que las otras fuentes no cubren. | fuego: 5+daño, humo: 1 |

Después se aplica un **bono de densidad** (`_apply_density_bonus`): candidatos de tipo
fuego cerca de zonas con mucho fuego contiguo suben de prioridad, para que el
backtracking mande más de un agente a una misma zona caliente en vez de repartirlos
parejo. Finalmente `_deduplicar_candidatos` colapsa candidatos que cayeron en la misma
celda (varias fuentes fácilmente coinciden ahí), quedándose solo con el de mayor
prioridad.

### 3. ¿Vale la pena recalcular? (`necesita_recalcular`)
Se compara el conjunto de posiciones candidatas, los agentes libres y el estado de
triage contra el último turno. Si nada cambió, no se repite el trabajo caro de armar
matriz + backtracking.

### 4. Matriz de costo efectivo (`build_cost_matrix`)
Para cada par (agente, candidato) se calcula una ruta real (A*) y se define:

```
costo_efectivo = costo_de_ruta / prioridad_ajustada
```

donde `prioridad_ajustada` es la prioridad del candidato, multiplicada por
`triage_factor` si el candidato es de tipo fuego. Así, una prioridad alta puede hacer
que un candidato "gane" aunque esté más lejos que uno de menor urgencia — la
prioridad participa directamente en la asignación, no solo la distancia.

### 5. Backtracking con poda (`backtrack` / `_explorar`)
Se exploran combinaciones agente-candidato (sin repetir candidato) recursivamente,
podando cualquier rama cuyo costo acumulado ya supere la mejor solución completa
encontrada hasta el momento. Si sobran agentes respecto a candidatos, también se
explora la opción de dejarlos sin asignar. El resultado es la asignación de costo total
mínimo.

### 6. Aplicación y red de seguridad
`apply_assignment` escribe la asignación en cada agente. Los agentes que quedaron sin
candidato (más agentes que tareas) reciben, sin volver a correr backtracking, el
candidato restante de mayor prioridad más cercano (`fill_remaining`) — desempatando por
distancia solo entre candidatos de igual prioridad.

---

## Comportamiento del agente

Con `strategy="optimized"` (`Firefighter._act_optimized`), cada bombero, en orden de
prioridad:

1. **Si carga una víctima**: ignora por completo lo asignado por el Coordinator y
   persigue la salida más cercana — sacar a la víctima es prioridad absoluta e
   individual.
2. **Si no tiene `objetivo_actual`**: cae de respaldo al comportamiento primitivo
   (persigue el POI sin revelar más cercano).
3. **Si ya está en su objetivo**: lo resuelve (revela el POI si aplica; el fuego/humo
   en el camino ya se apaga solo durante el trayecto) y limpia el objetivo.
4. **En otro caso**: avanza hacia `objetivo_actual` usando una ruta A* cacheada
   (recalculada solo cuando cambia el destino, no en cada paso, para evitar vaivenes),
   resolviendo obstáculos uno a uno (`_advance`): pared → cortar, puerta cerrada →
   abrir, fuego/humo en la celda destino → apagar, celda libre → mover. Antes de
   resolver el paso planeado, también reacciona a fuego activo en los otros 3 lados
   adyacentes si le sobran AP, para no dejar pasar fuego que podría explotar después.

---

## Servidor para transmisión JSON

`server.py` expone un `GameManager` vivo en memoria vía HTTP (FastAPI), pensado para
que un cliente externo (p. ej. Unity) avance la partida turno a turno y reciba el
estado como JSON, en vez de reproducir un archivo fijo generado por
`export_simulation.py`.

### Instalación

```bash
pip install fastapi uvicorn
```

### Encender el servidor

```bash
uvicorn server:app --reload --port 8000
```

Documentación interactiva (Swagger UI) disponible en:
`http://localhost:8000/docs`

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/game/new` | Inicia una partida nueva. Body: `{"num_firefighters": 6, "seed": null, "strategy": "optimized"}` |
| `GET` | `/game/state` | Devuelve el frame actual, sin efectos secundarios. |
| `POST` | `/game/step` | Avanza `{"count": N}` turnos individuales de agente. |
| `POST` | `/game/focus/{agent_id}` | Marca un agente como enfocado (para UI externa). |
| `POST` | `/game/focus/clear` | Limpia el foco actual. |

### Exportar una partida completa a archivo (alternativa sin servidor)

```bash
python export_simulation.py --out export/simulation.json --firefighters 6 --seed 42 --strategy optimized --max-turns 500
```

Genera un único JSON `{"frames": [...]}` con un frame por turno, listo para
reproducirse offline.

---
 
## Resultados del algoritmo sobre 1000 partidas
 
`main.py` corre un **batch de 1000 partidas independientes** (una por semilla,
`seed=range(1000)`, estrategia `optimized`, tope de 500 turnos) vía `mesa.batch_run()`
y produce tres gráficas de resumen. Estas son las estadísticas obtenidas en una corrida
representativa de ese batch.
 
### Tasa de victoria
 
En promedio, la estrategia `optimized` **gana alrededor del 10% de las partidas**.
Entre distintas corridas del mismo batch, la tasa observada varía: en los peores casos
baja hasta **7%**, y en los mejores llega a **15%**. Esta variabilidad es esperable —
cada partida depende de dónde caen las tiradas de fuego y de qué tan rápido escala el
daño estructural antes de que el Coordinator pueda reaccionar.
 
### Causa del resultado final

<div align=center>
<img width="500" height="auto" alt="Figure_3" src="https://github.com/user-attachments/assets/22067e26-4c53-4e3c-b01c-8b7cbefc1f30" />
</div>

<br>
 
La inmensa mayoría de las derrotas (~88% del total) ocurre por **colapso estructural**
(≥24 puntos de daño), no por pérdida de víctimas — el conteo de partidas perdidas por
víctimas es prácticamente nulo. Esto sugiere que el cuello de botella actual del
algoritmo no es la logística de rescate en sí (el Coordinator sí llega a las víctimas a
tiempo), sino la contención del fuego: las explosiones acumulan daño estructural más
rápido de lo que el equipo puede apagar fuego general, incluso con el bono de triage.
 
### Duración de las partidas

<div align=center>
<img width="500" height="auto" alt="Figure_2" src="https://github.com/user-attachments/assets/82e23c3b-7c7d-4934-8c07-d5385b4e2e3a" />
</div>

<br>

La mayoría de las partidas termina entre los turnos **50 y 119**, con un pico
claro en el rango **70-79**. Muy pocas partidas se extienden más allá de 150 turnos o
terminan antes del turno 30 — es decir, el resultado (ganar o perder) tiende a
definirse en una ventana relativamente consistente de la partida, ni demasiado
temprano ni cerca del límite de 500 turnos.
 
### Víctimas salvadas por partida

 <div align=center>
<img width="500" height="auto" alt="Figure_1" src="https://github.com/user-attachments/assets/90d58e68-69f8-4096-8ab9-46858381ce37" />
 </div>

<br>
 
La distribución de víctimas salvadas (de 0 a 7, el umbral de victoria) está
concentrada en la zona media: **2 y 3 víctimas salvadas son los resultados más
comunes**, seguidos de cerca por 1 y 4. Llegar a las 7 necesarias para ganar ocurre en
una porción visible pero minoritaria de las partidas, coherente con la tasa de
victoria de ~10% reportada arriba — el equipo suele avanzar bien en rescates parciales,
pero rara vez sostiene ese ritmo el tiempo suficiente sin que el edificio colapse antes.
 
### Lectura general
 
En conjunto, las tres gráficas apuntan a la misma conclusión: el algoritmo de
coordinación es efectivo salvando víctimas de forma parcial y consistente, pero el
daño estructural acumulado por explosiones es, hoy, la principal causa de derrota muy
por encima de la pérdida directa de víctimas. Cualquier mejora futura al Coordinator
enfocada en frenar el daño estructural (p. ej. afinar `scan_chain_breaks`,
`scan_general_fire` o el peso del `triage_factor`) es la palanca con más margen para
subir la tasa de victoria por encima del ~10-15% actual.
 
---
 
## Diagrama de clases
 
El diagrama de clases completo (relaciones, atributos y métodos de cada clase) se
encuentra en `ClassDiagram_Flashpoint-ClassDiagram_FinalCut_drawio.png`, incluido en
el repositorio.

<br>
<div align=center>
<img width="800" height="auto" alt="ClassDiagram_Flashpoint-ClassDiagram_FinalCut drawio" src="https://github.com/user-attachments/assets/2854b2a0-fefe-49e8-af3c-484b3969728e" />
</div>
