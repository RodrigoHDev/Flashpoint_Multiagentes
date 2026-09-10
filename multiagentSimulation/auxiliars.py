"""
Title: Auxiliars
Author: Rodrigo Hurtado
Description:

Collection of common functions used among more than one class that go in more than one category.

Functions:
TRIAGE
triage_factors

PRIMITIVE METHODS
get_next_step_direction
greedy_direction
nearest_target
manhattan

PATH FINDING
edge_cost
a_star
reconstruct_path
dijkstra_from
best_exit_by_cost

"""

#------------------------------ TRIAGE ---------------------------------

import heapq
import numpy as np

def triage_factor(building, fire, dam_threshold=6, cell_threshold=10, factor=2):
    """
    Name: triage_factor
    Descripcion: Priority multiplier dependant on the condition of the
                game board. When damage surpasses dam_threshold or
                number of cells on fire surpasses cell_threshold
                returns a factor > 1 to be multiplied for fire related
                goals declared in the function build_cost_matrix; 
                Otherwise, returns 1.
    Inputs:  building (BuildingManager), fire (FireManager),
            dam_threshold (int, default 12), cell_threshold
            (int, default 10), factor (float, default 1.5)
    Output: float -> 1.0 normal, 1 > in triage.
    Usages: Called inside the function build_cost_matrix.
    """
    fire_cells = int(np.count_nonzero(fire.fireGrid == 2))
    if building.buildingDam > dam_threshold or fire_cells > cell_threshold:
        return factor
    return 1.0


# Fire related goals declared in Coordinator.
FIRE_CANDIDATE_TYPES = {
    "fuego_amenaza", "punto_de_brecha", "romper_cadena",
    "fuego_general", "humo_general",
}


#------------------------------ PRIMITIVE METHODS  ---------------------------------

def manhattan(a, b):
    """
    Name: manhattan
    Description: Calculates Manhattan distance between two points.
    Input: a, b (tuple[int,int])
    Output: int (Manhattan Distance)
    Usage: Usage to compare distances to determine a better objetive based only
    on distance, or applied as an heuristics for pathfinding.
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def nearest_target(agent_pos, targets):
    """
    Name: nearest_target
    Description: Returns the closer target to the agent position based
                on Manhattan distance calculation.
    Input: agent_pos (tuple[int,int]), targets (list[tuple[int,int]])
    Output: tuple[int,int] or None if target is empty.
    Usage: Used Firefighter._act_primitive() to chose among POIS or exits.
    """
    if not targets:
        return None
    return min(targets, key=lambda t: manhattan(agent_pos, t))



def greedy_direction(agent_pos, target_pos):
    """
    Name: greedy_direction
    Description: Chooses one direction that makes the agent be closer to
                the target based on greater reduction over the Manhattan
                distance.
    Input: agent_pos, target_pos (tuple[int,int])
    Output: str -> "up" | "down" | "left" | "right"
    Usage: Used by Firefighter._act_primitive() to decide in which direction
    to advance
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


def get_next_step_direction(agent_pos, path):
        """
        Name: get_next_step_direction
        Description: Function responsible for returning the next
                    position in X and Y depending on the orientated 
                    direction.
        Inputs: agent_pos (tuple[int,int]), path (list o None)
        Outputs: str o None
        Usage: Used by Firefighter
        """
        if path is None or len(path) < 2:
            return None
        dx = path[1][0] - agent_pos[0]
        dy = path[1][1] - agent_pos[1]
        if dx == 1: return "right"
        if dx == -1: return "left"
        if dy == -1: return "up"
        if dy == 1: return "down"

#------------------------------ PATH FINDING  ---------------------------------


def edge_cost(building, fire, x, y, dir, next_pos):
        """
        Name: edge_cost
        Description: Function resposible for returning the value addition
                    of the building section in one direction of a specific location
                    and the fire related object stored there.
        Inputs: x(int), y (int), dir string
        Output: base + penalty (int)
        Usage: Used in pathfinding algoritm A* to determine a traverse cost.

        """
        base = building.getCost(x, y, dir)
        if base == float("inf"):
            return base
        nx, ny = next_pos
        fire_state = fire.get(nx, ny)
        penalty = 2 if fire_state == 2 else (1 if fire_state == 1 else 0)
        return base + penalty


def a_star(start, goal, building, fire):
        """
        Name: a_star
        Description: Pathfinding algoritm responsible for finding one of the sortest path from
                    a start to a goal being limited and determined by fire and the building 
                    manager.
        Inouts: start, goal tupla[int, int], building, fire.
        Outputs: path from start to goal.
        Usage:  Used to determine the best path to go to an specific point in the board. This 
                function is used by Firefighter to determine routes to follow.
        """

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

def reconstruct_path(came_from, current):
        """
        Name: reconstruct_path
        Description: Auxiliar method responsible for reconstructs path
        from an array of positions from
        goal until came_from.
        Inputs: came_from (dict), current (tuple[int,int], el destino)
        Outputs: list[tuple[int,int]] -> Sortes route
        Usage: called for a_star to assemble given path.
        """
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path


def dijkstra_from(start, building, fire):
        """
        Name: dijkstra_from
        Description: Pathfinding algorithm that returns the cost from
                    the position of start to all possible spots of the
                    board. Usage of the same cost function as A*(edge_cost).
                    No heuristics.
        Inputs: start (tuple[int,int]), building (BuildingManager),
                fire (FireManager)
        Outputs: dict {tuple[int,int]: float} -> list of min cost from
                origin to any place in board.
        Usage:Used in coordinator to traverse all positions and obtain certain 
        costs.
        """
        g_score = {start: 0}
        visited = set()
        open_set = [(0, start)]

        while open_set:
            dist, current = heapq.heappop(open_set)

            if current in visited:
                continue
            visited.add(current)

            for dir in ["up", "down", "left", "right"]:
                neighbor = building.getNext(current[0], current[1], dir)
                if neighbor is None or neighbor in visited:
                    continue

                cost = edge_cost(building, fire, current[0], current[1], dir, neighbor)
                if cost == float("inf"):
                    continue

                tentative_g = dist + cost
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    heapq.heappush(open_set, (tentative_g, neighbor))

        return g_score



def best_exit_by_cost(pos, exits, building, fire):
    """
        Name: best_exit_by_cost
        Description: Returns closest door to given position based on
        A* cost evaluation.
        Inputs: pos (tuple[int,int]), exits (list[tuple[int,int]]),
                building (BuildingManager), fire (FireManager)
        Outputs: tuple[int,int] o None -> Exit with lowest price or None
        Usage: Used in act_optimized to move victim once carried by the
                agent.
    """
    best = None
    best_cost = float("inf")
    for exit in exits:
        _, best = a_star(pos, exit, building, fire)
        if best < best_cost:
            best_cost = best
            best = exit
    return best