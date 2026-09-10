"""
Title: Coordinator
Author: Rodrigo Hurtado
Description:

Orchestrates the optimized strategy: generates candidates from the
board state, builds the cost matrix via pathfinding, solves the
optimal assignment with backtracking and pruning, and applies it to
the agents. Keeps the last known state of candidates/free agents to
know when it is worth recalculating.

Functions:
CONSTRUCTOR
__init__

CANDIDATE GENERATION
scan_poi_candidates
_chain_run
scan_chain_breaks
scan_breach_points
scan_general_fire
fire_density
_apply_density_bonus
_deduplicar_candidates
bottleneck_door
count_relevant_objectives
scan_bottleneck_doors
generate_candidates

COST & ASSIGNMENT
build_cost_matrix
explore
backtrack
apply_assignment

COORDINATION
free_up_agents
trigger_candidates_recal
fill_remaining
coordinate_turn

"""

import  Candidate as Candidate
import numpy as np
from  auxiliars import triage_factor, a_star, manhattan, FIRE_CANDIDATE_TYPES, dijkstra_from

WIDTH, HEIGHT = 10, 8

class Coordinator:
    """
    Orchestrates the optimized strategy: generates candidates from
    the board state, builds the cost matrix via pathfinding, solves
    the optimal assignment with backtracking and pruning, and
    applies it to the agents. Keeps the last known state of
    candidates/free agents to know when it is worth recalculating.
    """

    #------------------------------ CONSTRUCTOR ---------------------------------

    def __init__(self):
        """
        Name: __init__
        Description: Initializes the coordinator with no previous
                     assignment registered.
        Inputs: none
        Outputs: none (constructor)
        Usage: instantiated once inside GameManager.__init__, same
               as the other managers.
        """
        self.prev_candidates = set()
        self.prev_free_agents = set()
        self.prev_triage = False
        self.damage_in_last_interrupt = 0

    #------------------------------ CANDIDATE GENERATION ---------------------------------

    def scan_poi_candidates(self, poi, assigned_agents):
        """
        Name: scan_poi_candidates
        Description: Generates one candidate per unrevealed POI that
                     does not already have an agent assigned.
        Inputs: poi (PoiManager), assigned_agents (set[tuple[int,int]])
        Outputs: list[Candidate]
        Usage: called by generate_candidates().
        """
        candidates = []
        for pos in poi.pois:
            if pos not in assigned_agents:
                candidates.append(Candidate.Candidate(pos, "poi_sin_revelar", 10))
        return candidates


    def _chain_run(self, building, fire, x, y, dir):
        """
        Name: _chain_run
        Description: Counts how many consecutive fire cells there
                     are starting right after (x, y) in the given
                     direction, walking only through open sides
                     (same criterion as shockwave: element in
                     (0, 3)). Does not count the origin cell.
        Inputs: building (BuildingManager), fire (FireManager),
                x, y (int), dir (str)
        Outputs: int -> length of the fire streak in that direction
        Usage: called by scan_chain_breaks() twice per axis (once
               per direction) to measure how much contiguous fire is
               on each side of a candidate cell.
        """
        count = 0
        cx, cy = x, y
        while True:
            element = building.getDir(cx, cy, dir)
            if element not in (0, 3):
                break
            next_pos = building.getNext(cx, cy, dir)
            if next_pos is None:
                break
            nx, ny = next_pos
            if fire.get(nx, ny) != 2:
                break
            count += 1
            cx, cy = nx, ny
        return count

    def scan_chain_breaks(self, fire, building, assigned_agents):
        """
        Name: scan_chain_breaks
        Description: For each active fire cell, measures (per
                     vertical and horizontal axis) how much
                     contiguous fire is on each side using
                     _chain_run, and computes a "break score" =
                     min(run_a, run_b) + 1. This score is maximal
                     near the center of a long chain and minimal (1)
                     at the ends, so it prioritizes the "weak link"
                     that splits a long chain into two short ones,
                     not just the edge of the cluster. Only
                     generates a candidate if at least one axis has
                     a chain of 3+ cells and the score is >= 2
                     (avoids flagging isolated or edge fire).
        Inputs: fire (FireManager), building (BuildingManager),
                assigned_agents (set[tuple[int,int]])
        Outputs: list[Candidate] -> type "romper_cadena"
        Usage: called by generate_candidates().
        """
        candidates = []
        axis = [("up", "down"), ("left", "right")]

        for x in range(WIDTH):
            for y in range(HEIGHT):
                if (x, y) in assigned_agents:
                    continue
                if fire.get(x, y) != 2:
                    continue

                best_score = 0
                for dir_a, dir_b in axis:
                    run_a = self._chain_run(building, fire, x, y, dir_a)
                    run_b = self._chain_run(building, fire, x, y, dir_b)
                    if run_a + run_b + 1 < 3:
                        continue
                    score = min(run_a, run_b) + 1
                    best_score = max(best_score, score)

                if best_score >= 2:
                    priority = 8 + best_score * 3
                    candidates.append(Candidate.Candidate((x, y), "romper_cadena", priority))

        return candidates

    def scan_breach_points(self, poi, fire, building, assigned_agents):
        """
        Name: scan_breach_points
        Description: For each unrevealed POI or victim (poi.get in
                     (1, 3)), runs a BFS out of that cell only
                     through open sides until
                     finding the nearest active fire cell along that
                     path, with no walls/closed doors in between.
                     That fire cell is the "breach point": the only
                     path by which fire could reach that POI without
                     needing a lucky explosion. If several POIs reach
                     the same fire cell, keeps the minimum distance
                     found. Higher priority the closer the breach
                     point is to the POI (distance 1 is the same case
                     previously covered by scan_fire_threats, but
                     with higher priority, and it also detects
                     threats 2+ steps away that scan_fire_threats
                     could not see). This function generalizes and
                     replaces scan_fire_threats.
        Inputs: poi (PoiManager), fire (FireManager),
                building (BuildingManager),
                assigned_agents (set[tuple[int,int]])
        Outputs: list[Candidate] -> type "punto_de_brecha"
        Usage: called by generate_candidates().
        """
        candidates = []
        directions = ["up", "down", "left", "right"]
        mejor_por_fuego = {}

        objetivos = [
            (x, y)
            for x in range(WIDTH)
            for y in range(HEIGHT)
            if poi.get(x, y) in (1, 3)
        ]

        for origin in objetivos:
            visitado = {origin}
            frontera = [origin]
            dist = 0
            encontrado = None

            while frontera and encontrado is None:
                siguiente_frontera = []
                dist += 1
                for (x, y) in frontera:
                    for dir in directions:
                        element = building.getDir(x, y, dir)
                        if element not in (0, 3):
                            continue
                        next_pos = building.getNext(x, y, dir)
                        if next_pos is None or next_pos in visitado:
                            continue
                        visitado.add(next_pos)
                        nx, ny = next_pos
                        if fire.get(nx, ny) == 2:
                            encontrado = (next_pos, dist)
                            break
                        siguiente_frontera.append(next_pos)
                    if encontrado is not None:
                        break
                frontera = siguiente_frontera

            if encontrado is None:
                continue

            fire_pos, distancia = encontrado
            if fire_pos in assigned_agents:
                continue
            anterior = mejor_por_fuego.get(fire_pos)
            if anterior is None or distancia < anterior:
                mejor_por_fuego[fire_pos] = distancia

        for fire_pos, distancia in mejor_por_fuego.items():
            priority = max(20 - 3 * (distancia - 1), 6)
            candidates.append(Candidate.Candidate(fire_pos, "punto_de_brecha", priority))

        return candidates

    def scan_general_fire(self, fire, building, assigned_agents):
        """
        Name: scan_general_fire
        Description: Generates one candidate per cell with active
                     fire or smoke, regardless of whether it
                     threatens a POI. Low priority: it serves to
                     occupy agents that the backtracking did not
                     assign to something more urgent, preventing the
                     building from taking uncontrolled damage.
        Inputs: fire (FireManager), assigned_agents (set[tuple[int,int]])
        Outputs: list[Candidate]
        Usage: called by generate_candidates().
        """
        candidates = []
        directions = ["up", "down", "left", "right"]
        for x in range(WIDTH):
            for y in range(HEIGHT):
                if (x, y) in assigned_agents:
                    continue
                estado = fire.get(x, y)
                buildDamage = 0
                if estado == 2:
                    for dir in directions:
                        element = building.getDir(x, y, dir)
                        if element in (1, 2, 4): buildDamage += 1
                        candidates.append(Candidate.Candidate((x, y), "fuego_general", 5 + buildDamage))
                elif estado == 1:
                    candidates.append(Candidate.Candidate((x, y), "humo_general", 1))

        return candidates


    def fire_density(self, fire, x, y, radio=2):
        """
        Name: fire_density
        Description: Counts how many active fire cells (state == 2)
                     lie within a Manhattan radius `radio` around
                     (x, y), not counting cell (x, y) itself. Does
                     not check walls/doors -- it is a measure of how
                     much fire is "nearby" on the board, not of how
                     much is reachable, on purpose: what matters here
                     is detecting zones already dense with fire to
                     reinforce them with more agents, regardless of
                     whether the direct path is blocked.
        Inputs: fire (FireManager), x, y (int), radio (int, default 2)
        Outputs: int -> number of neighboring cells on fire
        Usage: called by _apply_density_bonus() once per fire-type
               candidate.
        """
        count = 0
        for dx in range(-radio, radio + 1):
            for dy in range(-radio, radio + 1):
                if dx == 0 and dy == 0:
                    continue
                if abs(dx) + abs(dy) > radio:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                    if fire.get(nx, ny) == 2:
                        count += 1
        return count

    def _apply_density_bonus(self, candidates, fire, radio=2, peso=3):
        """
        Name: _apply_density_bonus
        Description: Raises the priority of each fire-type candidate
                     (FIRE_CANDIDATE_TYPES) according to how dense
                     with fire its neighborhood is (fire_density).
                     Applied ONCE over the already-combined list from
                     generate_candidates, not inside each scan
                     separately -- this way "punto_de_brecha" and
                     "romper_cadena" in a zone with an explosion
                     cascade receive the same boost as
                     "fuego_general" there, instead of each competing
                     solely on its own local merit. The idea is that
                     when several candidates from the same zone gain
                     priority simultaneously, the backtracking (which
                     does 1-to-1 candidate-agent matching) has reason
                     to send more than one agent to that zone instead
                     of spreading them evenly across the board.
        Inputs: candidates (list[Candidate]), fire (FireManager),
                radio (int, default 2), peso (float, default 3)
        Outputs: list[Candidate] -> the same objects, priority
                 modified in-place
        Usage: called by generate_candidates() right before
               returning the combined list.
        """
        for c in candidates:
            if c.type in FIRE_CANDIDATE_TYPES:
                densidad = self.fire_density(fire, c.pos[0], c.pos[1], radio)
                c.priority += densidad * peso
        return candidates


    def _deduplicar_candidates(self, candidates):
        """
        Name: _deduplicar_candidates
        Description: When two or more scan_* functions generate a
                     candidate on the SAME cell (a fire cell easily
                     qualifies at once as "fuego_general",
                     "romper_cadena", and "frontera_contencion"),
                     keeps only the one with the highest priority and
                     discards the rest. A physical cell is still a
                     single cell no matter how many different scans
                     detect it -- leaving it duplicated in the list
                     only inflates C (number of candidates) without
                     adding real information, making
                     build_cost_matrix (which runs pathfinding per
                     candidate) and backtrack()'s search tree more
                     expensive unnecessarily. It is purely a
                     reduction of repeated work: it does not change
                     any priority, does not discard any real cell,
                     only collapses exact position duplicates.
        Inputs: candidates (list[Candidate])
        Outputs: list[Candidate] -> at most one candidate per
                 position (the highest-priority one among those
                 competing there)
        Usage: called by generate_candidates() as the last step,
               after _apply_density_bonus() (order does not matter
               for correctness: candidates at the same position get
               the same density bonus, so their relative order does
               not change).
        """
        mejor_por_pos = {}
        for c in candidates:
            actual = mejor_por_pos.get(c.pos)
            if actual is None or c.priority > actual.priority:
                mejor_por_pos[c.pos] = c
        return list(mejor_por_pos.values())


    def bottleneck_door(self, building, origin, destino, max_hops=8):
            """
            Name: bottleneck_door
            Description: Topological connectivity test (BFS, no
                         weights) between origin and destino,
                         EXCLUDING the direct edge that connects
                         them. If no alternative route appears within
                         max_hops, that door is the only reasonable
                         path between the two zones -> it is a
                         bottleneck. Only element 5 (indestructible
                         exterior wall) is considered impassable;
                         everything else (0, 1, 2, 3, 4) is admitted
                         as a possible alternative route, because the
                         criterion here is TOPOLOGICAL (does another
                         path exist or not), not AP cost.
            Inputs: building (BuildingManager), origin, destino
                    (tuple[int,int]), max_hops (int, default 8)
            Outputs: bool -> True if there is no nearby alternative
                     route
            Usage: called by scan_bottleneck_doors() once per closed
                   door found.
            """
            directions = ["up", "down", "left", "right"]
            visitado = {origin}
            frontera = [origin]
            hops = 0

            while frontera and hops < max_hops:
                siguiente = []
                hops += 1
                for (x, y) in frontera:
                    for dir in directions:
                        if (x, y) == origin and building.getNext(x, y, dir) == destino:
                            continue  # excludes the edge being tested
                        if building.getDir(x, y, dir) == 5:
                            continue
                        next_pos = building.getNext(x, y, dir)
                        if next_pos is None or next_pos in visitado:
                            continue
                        if next_pos == destino:
                            return False  # alternative route found
                        visitado.add(next_pos)
                        siguiente.append(next_pos)
                frontera = siguiente

            return True

    def count_relevant_objectives(self, poi, fire, pos, radio=3):
        """
        Name: count_relevant_objectives
        Description: Counts unrevealed POIs/victims and active fire
                     cells within a Manhattan radius around pos.
                     Used to discard bottleneck doors that give
                     access to zones with nothing urgent on the other
                     side -- there is no point sending an agent to
                     open a door that leads to no real objective.
        Inputs: poi (PoiManager), fire (FireManager), pos
                (tuple[int,int]), radio (int, default 3)
        Outputs: int -> count of relevant nearby objectives
        Usage: called by scan_bottleneck_doors() to weigh priority.
        """
        x0, y0 = pos
        count = 0
        for x in range(max(0, x0 - radio), min(WIDTH, x0 + radio + 1)):
            for y in range(max(0, y0 - radio), min(HEIGHT, y0 + radio + 1)):
                if manhattan((x0, y0), (x, y)) > radio:
                    continue
                if poi.get(x, y) in (1, 3):
                    count += 1
                if fire.get(x, y) == 2:
                    count += 1
        return count

    def scan_bottleneck_doors(self, poi, fire, building, assigned_agents):
        """
        Name: scan_bottleneck_doors
        Description: Detects closed doors that are the only
                     reasonable connection between two zones of the
                     board (bottleneck_door) and that give
                     access to relevant objectives on the other side
                     (count_relevant_objectives). Generates a
                     candidate on the cell ON THE OTHER SIDE of the
                     door -- not on the door itself -- so that normal
                     pathfinding (a_star/dijkstra) crosses through
                     and opens the door along the way, with no need
                     for extra logic in Firefighter (_advance already
                     opens closed doors it finds along its route).
        Inputs: poi (PoiManager), fire (FireManager),
                building (BuildingManager),
                assigned_agents (set[tuple[int,int]])
        Outputs: list[Candidate] -> type "abrir_puerta"
        Usage: called by generate_candidates().
        """
        candidates = []
        directions = ["up", "down", "left", "right"]
        procesadas = set()

        for x in range(WIDTH):
            for y in range(HEIGHT):
                for dir in directions:
                    if building.getDir(x, y, dir) != 4:
                        continue
                    next_pos = building.getNext(x, y, dir)
                    if next_pos is None:
                        continue

                    clave = frozenset({(x, y), next_pos})
                    if clave in procesadas:
                        continue
                    procesadas.add(clave)

                    if next_pos in assigned_agents:
                        continue

                    if not self.bottleneck_door(building, (x, y), next_pos):
                        continue

                    relevancia = self.count_relevant_objectives(poi, fire, next_pos)
                    if relevancia == 0:
                        continue

                    priority = 6 + relevancia * 2
                    candidates.append(Candidate.Candidate(next_pos, "abrir_puerta", priority))

        return candidates

    def generate_candidates(self, poi, fire, building, assigned_agents):
        """
        Name: generate_candidates
        Description: Combines all candidate sources (POI, breach
                     points, chain breaks, general fire, and
                     bottleneck doors) into a single list, excluding
                     already-assigned positions, applies the density
                     bonus, and collapses position duplicates into
                     one (the highest priority) via
                     _deduplicar_candidates().
        Inputs: poi (PoiManager), fire (FireManager),
                building (BuildingManager),
                assigned_agents (set[tuple[int,int]])
        Outputs: list[Candidate]
        Usage: called by coordinate_turn() at the start of every
               assignment recalculation.
        """
        candidates = (
            self.scan_poi_candidates(poi, assigned_agents)
            + self.scan_breach_points(poi, fire, building, assigned_agents)
            + self.scan_chain_breaks(fire, building, assigned_agents)
            + self.scan_general_fire(fire, building, assigned_agents)
            + self.scan_bottleneck_doors(poi, fire, building, assigned_agents)
        )
        candidates = self._apply_density_bonus(candidates, fire)
        return self._deduplicar_candidates(candidates)

    #------------------------------ COST & ASSIGNMENT ---------------------------------

    def build_cost_matrix(self, agents, candidates, building, fire):
        """
        Name: build_cost_matrix
        Description: Computes, for each (agent, candidate) pair, the
                     EFFECTIVE COST of going toward that candidate:
                     the real distance (via Dijkstra, computed once
                     per agent from its position) divided by the
                     candidate's priority. A high priority reduces
                     the effective cost, making the backtracking
                     prefer that candidate even if it is farther than
                     one with lower priority -- this way priority DOES
                     participate in the assignment, not just raw
                     distance.
        Inputs: agents (list[Firefighter]), candidates
                (list[Candidate]), building (BuildingManager),
                fire (FireManager)
        Outputs: dict {(agent, candidato): effective cost (float)}
        Usage: called by coordinate_turn() before running the
               backtracking. Changing Candidate.priority when
               declaring candidates (in scan_poi_candidates,
               scan_breach_points, etc.) directly alters the result
               of this computation, with no need to touch
               backtrack()/explore().
        """
        triage = triage_factor(building, fire)
        matrix = {}
        for agent in agents:
            costs = dijkstra_from(agent.pos, building, fire)
            for candidato in candidates:
                costo = costs[candidato.pos]
                priority = max(candidato.priority, 0.01)
                if candidato.type in FIRE_CANDIDATE_TYPES:
                    priority *= triage
                matrix[(agent, candidato)] = costo / priority
        return matrix

    def explore(self, agents_restantes, remaining_candidates, matrix, mejor, asignation_actual, costo_actual):
        """
        Name: explore
        Description: Recursive backtracking step with pruning. Now
                     its own method (previously nested inside
                     backtrack, capturing matrix by closure) that
                     receives EVERYTHING explicitly as a parameter,
                     including matrix -- this was what was missing
                     when considering pulling it out. Tries each
                     available candidate for the first agent in the
                     list, prunes branches whose accumulated cost
                     already exceeds the best known complete
                     solution, and also explores the option of
                     leaving the agent unassigned when there are more
                     agents left than candidates.
        Inputs: agents_restantes (list[Firefighter]),
                remaining_candidates (list[Candidate]),
                matrix (dict, cost table -- now explicit, not via
                closure), mejor (mutable dict, shared across
                recursive calls to carry the best result found),
                asignation_actual (dict, partial assignment under
                construction), costo_actual (float, accumulated cost
                of that partial assignment)
        Outputs: none (modifies `mejor` in-place)
        Usage: called by backtrack() to start the search, and by
               itself recursively to explore each branch.
        """
        if not agents_restantes or not remaining_candidates:
            if costo_actual < mejor["costo"]:
                mejor["costo"] = costo_actual
                mejor["asignation"] = asignation_actual.copy()
            return

        agent = agents_restantes[0]
        resto_agents = agents_restantes[1:]

        for candidato in remaining_candidates:
            costo_arista = matrix[(agent, candidato)]
            nuevo_costo = costo_actual + costo_arista

            if nuevo_costo >= mejor["costo"]:
                continue   # PRUNE

            asignation_actual[agent] = candidato
            resto_candidates = [c for c in remaining_candidates if c != candidato]
            self.explore(resto_agents, resto_candidates, matrix, mejor, asignation_actual, nuevo_costo)
            del asignation_actual[agent]

        if len(agents_restantes) > len(remaining_candidates):
            self.explore(resto_agents, remaining_candidates, matrix, mejor, asignation_actual, costo_actual)

    def backtrack(self, agents, candidates, matrix):
        """
        Name: backtrack
        Description: Explores assignment combinations agent by
                     agent, candidate by candidate (without repeating
                     a candidate between agents), pruning branches
                     whose accumulated cost already exceeds the best
                     complete combination found so far. Stops when
                     agents or candidates run out, whichever comes
                     first -- remaining agents are left unassigned in
                     this layer. This is a PURE function: it does not
                     modify any agent, it only returns data.
        Inputs: agents (list[Firefighter]), candidates
                (list[Candidate]), matrix (dict, output of
                build_cost_matrix)
        Outputs: dict {Firefighter: Candidate} -> the best assignment
                 found
        Usage: called by coordinate_turn() after building the cost
               matrix.
        """
        mejor = {"costo": float("inf"), "asignation": {}}
        self.explore(agents, candidates, matrix, mejor, {}, 0)
        return mejor["asignation"]

    def apply_assignment(self, asignation):
        """
        Name: apply_assignment
        Description: Writes the resulting assignment onto each agent
                     (objective, objective_type). This is the
                     ONLY point in the whole pipeline that modifies
                     agents directly -- backtrack()/explore() are
                     pure functions that only return data, precisely
                     so branches can be explored and discarded
                     without real side effects.
        Inputs: asignation (dict {Firefighter: Candidate})
        Outputs: none
        Usage: called by coordinate_turn() right after backtrack().
        """
        for agent, candidato in asignation.items():
            agent.objective = candidato.pos
            agent.objective_type = candidato.type
            print(f"[Agent {agent.id}] Asignado a {candidato.pos[0]}, {candidato.pos[1]}. Tarea de type: {agent.objective_type}")

    #------------------------------ COORDINATION ---------------------------------

    def free_up_agents(self, agents):
        """
        Name: free_up_agents
        Description: Clears objective/objective_type for ALL
                    agents that are not carrying a victim and are
                    not knocked down.
        Inputs: agents (list[Firefighter])
        Outputs: none
        Usage: called by coordinate_turn() ONLY on the rising edge of
                triage_factor (False -> True), never while triage
                stays active turn after turn -- releasing every turn
                would cause "thrashing": agents abandoning an almost
                finished task for a barely better one, over and over,
                never finishing anything.
        """
        for agent in agents:
            if agent.knockdown or agent.victim:
                continue
            agent.objective = None
            agent.objective_type = None

    def trigger_candidates_recal(self, candidates, free_agents, active_triage):
        """
        Name: trigger_candidates_recal
        Description: Compares the current set of candidates and of
                    objective-less agents against the last known
                    state. Only if something changed is it worth
                    rerunning the full backtracking -- avoids
                    recalculating every turn unnecessarily.
        Inputs: candidates (list[Candidate]), free_agents
                (list[Firefighter]), active_triage (bool)
        Outputs: bool
        Usage: called by coordinate_turn() before building the cost
            matrix. BEFORE, this function only compared candidate
            positions and free-agent ids -- a change in
            triage_factor (same fire cell, but now with double
            priority) could go completely unnoticed if the set of
            cells on fire was identical to the previous turn,
            leaving the recalculation -- and therefore triage
            itself -- without real effect. Now active_triage is
            part of the compared fingerprint.
        """
        actual_candidates = set(c.pos for c in candidates)
        actual_free = set(a.unique_id for a in free_agents)

        trigger = (actual_candidates != self.prev_candidates or
                actual_free != self.prev_free_agents or
                active_triage != self.prev_triage)

        self.prev_candidates = actual_candidates
        self.prev_free_agents = actual_free
        return trigger


    def fill_remaining(self, agents_not_assigned, remaining_candidates):
        """
        Name: fill_remaining
        Description: Assigns, without rerunning backtracking, the
                     most urgent available candidate to each agent
                     the optimal assignment left without a task.
                     Sorts by priority first (higher priority wins),
                     and distance only breaks ties between candidates
                     of the SAME priority. Uses the same
                     Candidate.priority field as build_cost_matrix,
                     so both mechanisms respond consistently to any
                     priority adjustment.
        Inputs: agents_not_assigned (list[Firefighter]),
                remaining_candidates (list[Candidate])
        Outputs: none
        Usage: called by coordinate_turn() right after
               apply_assignment(), as a low-cost safety net.
        """
        for agent in agents_not_assigned:
            if not remaining_candidates:
                break
            chosen = min(
                remaining_candidates,
                key=lambda c: (-c.priority, manhattan(agent.pos, c.pos))
            )
            agent.objective = chosen.pos
            agent.objective_type = chosen.type
            remaining_candidates.remove(chosen)


    def coordinate_turn(self, agents, poi, fire, building):
        """
        Name: coordinate_turn
        Description: Single entry point of the Coordinator for one
                     turn. Identifies free agents (with no objective
                     or with an already-resolved one), generates
                     candidates, decides whether it is worth
                     recalculating, and if so, runs cost matrix +
                     backtracking + applies the resulting assignment.
        Inputs: agents (list[Firefighter]), poi (PoiManager),
                fire (FireManager), building (BuildingManager)
        Outputs: none
        Usage: called by GameManager on every round, before agents
               execute their act().
        """

        active_triage = triage_factor(building, fire) > 1.0
        actual_damage = building.buildingDam
        rised_since_last_interrupt = actual_damage > self.damage_in_last_interrupt

        if active_triage and (not self.prev_triage or rised_since_last_interrupt):
            # Triggered in two cases:
            #   (a) rising edge -- the board JUST became critical,
            #       first time in this streak.
            #   (b) structural damage grew since the LAST time we
            #       released -- since in this implementation damage
            #       ONLY comes from explosions (see _propagate/
            #       shockwave in FireManager), this is equivalent to
            #       "an explosion happened somewhere since we last
            #       reoptimized". It is a precise signal tied to a
            #       real board event, not a threshold crossed once
            #       and then silent for the rest of the game while
            #       everything keeps getting worse -- which is
            #       exactly what was observed in the earlier log
            #       (a single release on turn 2, none more in 30
            #       turns with near-constant explosions).
            print(f"[Coordinator] Triage (buildingDam={actual_damage}) -> liberando asignationes para reoptimizar")
            self.free_up_agents(agents)
            self.damage_in_last_interrupt = actual_damage

        free_agents = [
            a for a in agents
            if not a.knockdown and not a.victim and a.objective is None
        ]

        if not free_agents:
            self.prev_triage = active_triage
            return

        assigned_agents = set(
            a.objective for a in agents
            if a.objective is not None and a not in free_agents
        )

        candidates = self.generate_candidates(poi, fire, building, assigned_agents)

        if not self.trigger_candidates_recal(candidates, free_agents, active_triage):
            self.prev_triage = active_triage
            return

        self.prev_triage = active_triage

        matrix = self.build_cost_matrix(free_agents, candidates, building, fire)
        asignation = self.backtrack(free_agents, candidates, matrix)
        self.apply_assignment(asignation)

        not_assigned = [a for a in free_agents if a not in asignation]
        remaining_candidates = [c for c in candidates if c not in asignation.values()]
        self.fill_remaining(not_assigned, remaining_candidates)