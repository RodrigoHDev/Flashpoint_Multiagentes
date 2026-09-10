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
y produce tres gráficas de resumen. Estas son las estadísticas obtenidas en la corrida
más reciente del batch, ya con las correcciones al algoritmo aplicadas (validación de
accesibilidad por pared/puerta en `_reaccion_fuego_adyacente`, extensión de esa función
para apagar también humo, y acumulación de AP entre turnos).

### Tasa de victoria

Con el modelo de estrategia actual, modelo `optimized` **ganó ~21.5% de las partidas** (215/1000)
— más del doble de la tasa reportada en el modelo anterior (~10%). El resto de las
partidas (~78.5%) terminó en derrota, y en todas por la misma causa: no se registró
ninguna partida perdida por víctimas. Este salto es consistente con haber corregido un
bug que dejaba apagar fuego "a través" de paredes/puertas cerradas — el algoritmo
anterior sobreestimaba su propia efectividad conteniendo el fuego, y esa sobreestimación
se traducía en victorias que en una partida real no se habrían dado.

### Causa del resultado final

<div align=center>
<img width="400" height="auto" alt="Causa del resultado final" src="https://github.com/user-attachments/assets/b619418e-efd2-4164-9a04-3666c302a8ad" />
</div>
<br>

De las 1000 partidas, **785 se perdieron por colapso estructural** (≥24 puntos de daño)
y **215 se ganaron**; ninguna terminó en derrota por pérdida de víctimas. La proporción
de derrotas por daño estructural bajó de ~88% a ~78.5% respecto a la corrida anterior,
pero sigue siendo, por un margen amplio, la causa dominante de derrota. El cuello de
botella del algoritmo sigue siendo el mismo: la logística de rescate funciona bien (cero
víctimas perdidas), pero contener el fuego real —sin el bug que lo abarataba— todavía no
alcanza para evitar que la mayoría de los edificios colapse.

### Duración de las partidas

<div align=center>
<img width="400" height="auto" alt="Duración de pasos de las partidas" src="https://github.com/user-attachments/assets/c9096a9b-39f9-4734-9e75-cee0111f0a54" />
</div>

<br>

La distribución cambió de forma: el pico ahora está en el rango **50-59** turnos
(~115 partidas), más temprano que el pico anterior (70-79). Sin embargo, aparece un
segundo grupo casi tan alto entre **80-99** turnos (~108 y ~104 partidas
respectivamente), dando una forma **bimodal**: un cúmulo de partidas que se resuelven
rápido (probablemente derrotas tempranas por colapso estructural) y otro cúmulo de
partidas más largas (probablemente los rescates que sí llegan a las 7 víctimas). Muy
pocas partidas superan los 150 turnos o terminan antes del turno 20.

### Víctimas salvadas por partida

<div align=center>
<img width="400" height="auto" alt="Victimas salvadas por partida" src="https://github.com/user-attachments/assets/cd3f45b9-6970-415b-b8b4-22dfaf11cb29" />
</div>
<br>

Este es el cambio más marcado: la distribución dejó de concentrarse en la zona media
(2-3 víctimas, como en la corrida anterior) y ahora tiene su **moda en 7 víctimas
salvadas** (216 partidas, el resultado más común de todos), seguida de 1 víctima (176)
y 2 víctimas (153). El resultado es una forma más bimodal que antes: las partidas
tienden a **rescatar casi todo o casi nada**, con menos casos de rescates parciales
"a medias" (4, 5 o 6 víctimas) que en la corrida anterior. Esto es coherente con la
duración bimodal de arriba — cuando el equipo logra contener el fuego lo suficiente
como para sobrevivir los primeros turnos críticos, tiende a terminar el trabajo casi
por completo; cuando no, colapsa temprano habiendo rescatado poco.

### Lectura general

Las correcciones aplicadas al algoritmo subieron la tasa de victoria de ~10% a ~21.5%
en esta corrida, confirmando que el bug de accesibilidad estaba inflando artificialmente
el desempeño reportado antes. El colapso estructural sigue siendo, con amplio margen, la
principal causa de derrota (ninguna partida se pierde ya por víctimas), pero ahora
explica una porción menor del total que antes. El patrón de resultados también se volvió
más polarizado: las partidas tienden a ganarse casi por completo o perderse temprano,
sugiriendo que existe una ventana crítica (aprox. los primeros 50-60 turnos) donde se
decide si el equipo logra estabilizar el fuego o el edificio entra en una espiral de
daño de la que ya no se recupera. Seguir bajando esa tasa de colapso temprano —por
ejemplo con las mejoras discutidas sobre `scan_chain_breaks`, `triage_factor` gradual, o
gestión activa de puertas para compartimentar zonas— sigue siendo la palanca con más
margen para subir el win rate por encima del ~20% actual.

---

## Diagrama de clases

El diagrama de clases completo (relaciones, atributos y métodos de cada clase) se
encuentra en `ClassDiagram_Flashpoint-ClassDiagram_FinalCut_drawio.png`, incluido en
el repositorio.

<br>
<div align=center>
<img width="800" height="auto" alt="ClassDiagram_Flashpoint-ClassDiagram_FinalCut drawio" src="https://github.com/user-attachments/assets/2854b2a0-fefe-49e8-af3c-484b3969728e" />
</div>
</div>
