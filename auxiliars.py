import heapq
import numpy as np

def triage_factor(building, fire, dam_threshold=6, cell_threshold=10, factor=2):
    """
    Nombre: triage_factor
    Descripcion: multiplicador de prioridad dependiente del estado
                 del tablero. Cuando el dano estructural acumulado
                 supera dam_threshold, o el numero de celdas con
                 fuego activo supera cell_threshold, regresa un
                 factor > 1 para escalar las prioridades de tipo
                 fuego en build_cost_matrix; en caso contrario
                 regresa 1.0 (sin cambio). Deja que el estado del
                 tablero mismo module el trade-off POI-vs-fuego en
                 vez de tener una rama de estrategia separada.
    Entradas: building (BuildingManager), fire (FireManager),
              dam_threshold (int, default 12), cell_threshold
              (int, default 10), factor (float, default 1.5)
    Salidas: float -> 1.0 en estado normal, `factor` en triage
    Uso: llamado una vez por turno dentro de build_cost_matrix,
         antes del doble ciclo agente x candidato (no dentro, para
         no recalcularlo por cada par).
    """
    fire_cells = int(np.count_nonzero(fire.fireGrid == 2))
    if building.buildingDam > dam_threshold or fire_cells > cell_threshold:
        return factor
    return 1.0
 
 
# Tipos de candidato relacionados con fuego, para saber a cuales
# aplicarles el triage_factor dentro de build_cost_matrix. Los tipos
# de POI (poi_sin_revelar) quedan fuera a proposito: la idea es subir
# el peso del fuego bajo presion, no bajar el de los POI.
FIRE_CANDIDATE_TYPES = {
    "fuego_amenaza", "punto_de_brecha", "romper_cadena",
    "fuego_general", "humo_general",
}



def manhattan(a, b):
    """
    Nombre: manhattan
    Descripcion: calcula la distancia Manhattan entre dos coordenadas
                 (metrica correcta para movimiento en 4 direcciones).
    Entradas: a, b (tuple[int,int])
    Salidas: int
    Uso: llamado por nearest_target() para comparar candidatos.
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def nearest_target(agent_pos, targets):
    """
    Nombre: nearest_target
    Descripcion: elige, de una lista de coordenadas candidatas, la
                 mas cercana por distancia Manhattan.
    Entradas: agent_pos (tuple[int,int]), targets (list[tuple[int,int]])
    Salidas: tuple[int,int] o None si targets esta vacia
    Uso: llamado por Firefighter._act_primitive() para elegir el
         proximo POI o salida a perseguir.
    """
    if not targets:
        return None
    return min(targets, key=lambda t: manhattan(agent_pos, t))


def greedy_direction(agent_pos, target_pos):
    """
    Nombre: greedy_direction
    Descripcion: elige una unica direccion (up/down/left/right) que
                 acerque a agent_pos hacia target_pos, priorizando el
                 eje con mayor diferencia. No calcula ruta optima.
    Entradas: agent_pos, target_pos (tuple[int,int])
    Salidas: str -> "up" | "down" | "left" | "right"
    Uso: llamado por Firefighter._act_primitive() en cada paso del
         ciclo, antes de intentar avanzar.
    """
    dx = target_pos[0] - agent_pos[0]
    dy = target_pos[1] - agent_pos[1]
    if abs(dx) >= abs(dy):
        if dx != 0:
            return "right" if dx > 0 else "left"
        return "up" if dy < 0 else "down"
    else:
        if dy != 0:
            return "up" if dy < 0 else "down"
        return "right" if dx > 0 else "left"


def edge_cost(building, fire, x, y, dir, next_pos):
    base = building.getCost(x, y, dir)
    if base == float("inf"):
        return base
    nx, ny = next_pos
    fire_state = fire.get(nx, ny)
    penalty = 2 if fire_state == 2 else (1 if fire_state == 1 else 0)
    return base + penalty


def a_star(start, goal, building, fire):
    open_set = [(manhattan(start, goal), start)]
    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            return reconstruct_path(came_from, current), g_score[current]

        for dir in ["up", "down", "left", "right"]:
            neighbor = building.getNext(current[0], current[1], dir)
            if neighbor is None:
                continue

            cost = edge_cost(building, fire, current[0], current[1], dir, neighbor)
            if cost == float("inf"):
                continue

            tentative_g = g_score[current] + cost
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current
                heapq.heappush(open_set, (tentative_g + manhattan(neighbor, goal), neighbor))

    return None, float("inf")

def get_next_step_direction(agent_pos, path):
      """
      Nombre: get_next_step_direction
      Descripcion: extrae la direccion del primer paso real de una
                  ruta calculada por a_star (solo se usa path[1], el
                  resto se descarta porque se recalcula el siguiente
                  turno).
      Entradas: agent_pos (tuple[int,int]), path (list o None)
      Salidas: str o None
      Uso: llamado por Firefighter._act_primitive_astar() justo
          despues de a_star().
      """
      if path is None or len(path) < 2:
          return None
      dx = path[1][0] - agent_pos[0]
      dy = path[1][1] - agent_pos[1]
      if dx == 1: return "right"
      if dx == -1: return "left"
      if dy == -1: return "up"
      if dy == 1: return "down"

def reconstruct_path(came_from, current):
      """
      Nombre: reconstruct_path
      Descripcion: reconstruye la ruta completa siguiendo los
                  predecesores desde el destino hasta el origen.
      Entradas: came_from (dict), current (tuple[int,int], el destino)
      Salidas: list[tuple[int,int]] -> ruta ordenada de inicio a fin
      Uso: llamado por a_star() al alcanzar el destino.
      """
      path = [current]
      while current in came_from:
          current = came_from[current]
          path.append(current)
      path.reverse()
      return path