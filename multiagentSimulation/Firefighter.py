"""
Title: Firefighter
Author: Rodrigo Hurtado
Description:

Firefighter agent (Mesa Agent). Holds its own state (position via
Mesa, direction, knockdown, whether it carries a victim, action
points) and executes its turn according to the active strategy
("primitive" for now, "optimized" pending).

Functions:
CONSTRUCTOR
__init__

PROPERTIES
x
y
ap
efficiency

SETUP
link

TURN LIFECYCLE
restockAP
getKnockdown
setKnockdown
assignVictim
act

MOVEMENT & BUILDING ACTIONS
move
chop
openDoor

FIRE ACTIONS
_extinguish
turnFireToSmoke
turnFireToNothing
turnSmokeToNothing
_reaccion_fuego_adyacente

ADVANCE
_advance

STRATEGIES
_act_primitive
_act_primitive_astar
_next_direction_towards
_act_optimized

"""

import mesa
from  auxiliars import triage_factor, nearest_target, a_star, greedy_direction, get_next_step_direction


class Firefighter(mesa.Agent):
    """
    Firefighter agent (Mesa Agent). Holds its own state (position
    via Mesa, direction, knockdown, whether it carries a victim,
    action points) and executes its turn according to the active
    strategy ("primitive" for now, "optimized" pending).
    """

    #------------------------------ CONSTRUCTOR ---------------------------------

    def __init__(self, model):
        """
        Name: __init__
        Description: Creates the agent and its initial state. The
                     position is assigned by Mesa via
                     grid.place_agent(), not here. self.id exposes
                     Mesa's unique_id as a plain integer, used in
                     debug prints.
        Inputs: model (GameManager)
        Outputs: none (constructor)
        Usage: called by GameManager._crear_agentes() once per
               firefighter of the game.
        """
        super().__init__(model)
        self.id = self.unique_id
        self.direction = "down"
        self.knockdown = False
        self.victim = False
        self.actionPoints = 0

        #Developed strategies
        # self.strategy = "primitive"
        # self.strategy = "primitive_astar"
        self.strategy = "optimized"

        self.objective = None
        self.tipo_objetivo = None

        self._ruta = None
        self._ruta_destino = None

        self.steps_taken = 0
        self.objectives_completed = 0

        self.building = None
        self.poi = None
        self.fire = None
        self.exits = None

    #------------------------------ PROPERTIES ---------------------------------

    @property
    def x(self):
        """
        Name: x (property)
        Description: Exposes the x coordinate without duplicating
                    state (derived from self.pos, which Mesa
                    manages).
        Inputs: none
        Outputs: int
        Usage: read by GameManager.capture_snapshot/to_dict.
        """
        return self.pos[0]

    @property
    def y(self):
        """
        Name: y (property)
        Description: Exposes the y coordinate without duplicating
                    state.
        Inputs: none
        Outputs: int
        Usage: read by GameManager.capture_snapshot/to_dict.
        """
        return self.pos[1]

    @property
    def ap(self):
        """
        Name: ap (property)
        Description: Alias of self.actionPoints for compatibility
                    with the format expected by GameManager.to_dict.
        Inputs: none
        Outputs: int
        Usage: read by GameManager.to_dict.
        """
        return self.actionPoints

    @property
    def efficiency(self):
        """
        Name: efficiency (property)
        Description: Percentage of objectives completed per real
                    movement step taken. An agent that completes
                    tasks with few movements has high efficiency;
                    one that wanders a lot without completing
                    objectives has low efficiency.
        Inputs: none
        Outputs: float (0.0 if it hasn't moved yet)
        Usage: read by GameManager's DataCollector.
        """
        if self.steps_taken == 0:
            return 0.0

        return round((self.objectives_completed / self.steps_taken)*100,2)

    #------------------------------ SETUP ---------------------------------

    def link(self, buildingManager, poiManager, fireManager, exits):
        """
        Name: link
        Description: Injects the references to the managers and to
                    the list of building exits.
        Inputs: buildingManager, poiManager, fireManager (managers),
                exits (list[tuple[int,int]])
        Outputs: none
        Usage: called by GameManager._crear_agentes() right after
            creating each Firefighter.
        """
        self.building = buildingManager
        self.poi = poiManager
        self.fire = fireManager
        self.exits = exits

    #------------------------------ TURN LIFECYCLE ---------------------------------

    def restockAP(self):
        """
        Name: restockAP
        Description: Restores action points to the maximum (4) at
                    the start of each turn.
        Inputs: none
        Outputs: none
        Usage: called by act() at the beginning of each agent turn.
        """
        self.actionPoints += 4

    def getKnockdown(self):
        """
        Name: getKnockdown
        Description: Queries whether the agent is knocked down.
        Inputs: none
        Outputs: bool
        Usage: available for external logic (future Coordinator,
            reports) that needs to filter active agents.
        """
        return self.knockdown

    def setKnockdown(self, value):
        """
        Name: setKnockdown
        Description: Marks the agent as knocked down. If value=True:
                     if it was carrying a victim, counts it as lost
                     (existing behavior), and respawns IMMEDIATELY at
                     the nearest exit via model.grid.move_agent() (no
                     direct assignment of self.pos), keeping whatever
                     AP it had at that moment -- teleportation is not
                     a played action, it doesn't consume AP.
        Inputs: value (bool)
        Outputs: none
        Usage: called by FireManager.turnToFire() when fire reaches
               the agent's cell.
        """
        if value:
            if self.victim:
                self.poi.destroyVictim()
                self.victim = False

            pos_antes = self.pos
            salida = nearest_target(self.pos, self.exits)
            if salida is not None:
                self.model.grid.move_agent(self, salida)

            self.objective = None
            self.tipo_objetivo = None
            self.model.record_step(self.unique_id, "respawn_knockdown", prev_pos=pos_antes, new_pos=self.pos)

        self.knockdown = False

    def assignVictim(self):
        """
        Name: assignVictim
        Description: Marks that the agent is now carrying a victim.
        Inputs: none
        Outputs: none
        Usage: called by PoiManager.turnOver() when the revealed POI
               turns out to be a real victim.
        """
        self.victim = True
        print(f"[Agente {self.id}] Have victim at {self.pos[0]}, {self.pos[1]}")

    def act(self):
        """
        Name: act
        Description: Entry point of the agent's turn. Restocks AP,
                     and if not knocked down, delegates to the active
                     strategy. This method does NOT change when
                     optimized behavior is added.
        Inputs: none
        Outputs: none
        Usage: called once per agent, on every iteration of
               GameManager.step_agent().
        """
        self.restockAP()
        if self.knockdown:
            return

        if self.strategy == "primitive":
            self._act_primitive()
        elif self.strategy == "primitive_astar":
            self._act_primitive_astar()
        elif self.strategy == "optimized":
            self._act_optimized()

    #------------------------------ MOVEMENT & BUILDING ACTIONS ---------------------------------

    def move(self, dir):
        """
        Name: move
        Description: Moves the agent one cell in the given direction,
                     if it has enough AP according to the cost (1
                     over nothing/smoke, 2 over fire or while
                     carrying a victim; moving with a victim over
                     fire is forbidden). The movement is done via
                     model.grid.move_agent() (no direct assignment of
                     self.pos), so that Mesa keeps its internal
                     MultiGrid structure correctly synced with the
                     real position.
        Inputs: dir (str)
        Outputs: bool -> True if it moved, False if it couldn't
        Usage: called by _advance() when the destination cell is
               free of active fire/smoke requiring prior cleanup.
        """
        next_pos = self.building.getNext(self.pos[0], self.pos[1], dir)
        if next_pos is None:
            return False
        nx, ny = next_pos
        fireState = self.fire.get(nx, ny)

        if self.victim and fireState == 2:
            return False

        cost = 2 if (fireState == 2 or self.victim) else 1
        if self.actionPoints < cost:
            return False

        print(f"[Agente {self.id}] Moving from {self.pos[0]}, {self.pos[1]}")
        self.model.grid.move_agent(self, next_pos)
        self.direction = dir
        self.actionPoints -= cost
        print(f"[Agente {self.id}] Moving to {self.pos[0]}, {self.pos[1]}")
        self.steps_taken += 1
        return True

    def chop(self, dir):
        """
        Name: chop
        Description: Strikes the wall/door in the given direction,
                     costing 2 AP, if BuildingManager.damage confirms
                     there was something damageable there.
        Inputs: dir (str)
        Outputs: bool -> True if damage was applied, False if not
        Usage: called by _advance() when the side in that direction
               is a wall (1 or 2 lives).
        """
        if self.actionPoints < 2:
            return False
        if not self.building.damage(self.pos[0], self.pos[1], dir):
            return False
        self.direction = dir
        self.actionPoints -= 2
        print(f"[Agente {self.id}] Chopped at {self.pos[0]}, {self.pos[1]}")
        return True

    def openDoor(self, dir):
        """
        Name: openDoor
        Description: Toggles the state of a closed/open door in the
                     given direction, costing 1 AP.
        Inputs: dir (str)
        Outputs: bool -> True if there was a door there, False if not
        Usage: called by _advance() when the side in that direction
               is a closed door.
        """
        if self.actionPoints < 1:
            return False
        if not self.building.moveDoor(self.pos[0], self.pos[1], dir):
            return False
        self.direction = dir
        self.actionPoints -= 1
        return True

    #------------------------------ FIRE ACTIONS ---------------------------------

    def _extinguish(self, dir, cost, requiere, accion):
        """
        Name: _extinguish
        Description: Generic helper for the 3 variants of putting out
                     fire/smoke: validates AP, validates that the
                     neighboring cell has the required state, and
                     applies the corresponding FireManager action.
        Inputs: dir (str), cost (int), requiere (int, expected fire
                state), accion (FireManager function)
        Outputs: bool -> True if applied, False if not
        Usage: used internally by turnFireToSmoke, turnFireToNothing,
               and turnSmokeToNothing.
        """
        if self.actionPoints < cost:
            return False
        next_pos = self.building.getNext(self.pos[0], self.pos[1], dir)
        if next_pos is None:
            return False
        nx, ny = next_pos
        if self.fire.get(nx, ny) != requiere:
            return False
        accion(nx, ny)
        self.direction = dir
        self.actionPoints -= cost
        return True

    def turnFireToSmoke(self, dir):
        """
        Name: turnFireToSmoke
        Description: Reduces fire to smoke in the neighboring cell,
                     cost 1 AP.
        Inputs: dir (str)
        Outputs: bool
        Usage: manual action available to the agent (not used in the
               current _advance cycle, which goes straight to
               turnFireToNothing).
        """
        if self._extinguish(dir, 1, 2, self.fire.turnToSmoke):
            print(f"[Agente {self.id}] Turned Fire to Smoke at: {self.pos[0]}, {self.pos[1]}")
            return True
        return False

    def turnFireToNothing(self, dir):
        """
        Name: turnFireToNothing
        Description: Fully puts out fire in the neighboring cell,
                     cost 2 AP.
        Inputs: dir (str)
        Outputs: bool
        Usage: called by _advance() when the destination cell has
               fire.
        """
        if self._extinguish(dir, 2, 2, self.fire.turnOff):
            print(f"[Agente {self.id}] Turned Fire to Nothing at: {self.pos[0]}, {self.pos[1]}")
            return True
        return False

    def turnSmokeToNothing(self, dir):
        """
        Name: turnSmokeToNothing
        Description: Clears smoke in the neighboring cell, cost 1 AP.
        Inputs: dir (str)
        Outputs: bool
        Usage: called by _advance() when the destination cell has
               smoke.
        """
        if self._extinguish(dir, 1, 1, self.fire.turnOff):
            print(f"[Agente {self.id}] Turned Smoke to Nothing at: {self.pos[0]}, {self.pos[1]}")
            return True
        return False

    def _reaccion_fuego_adyacente(self, planned_dir):
        """
        Name: _reaccion_fuego_adyacente
        Description: Checks the 3 NON-planned sides (all except
                    planned_dir) for reachable fire/smoke and, if
                    there is AP to spare, clears it before resolving
                    the planned step. Only considers a neighbor
                    reachable through an open side (0) or an open
                    door (3) -- same criterion used by _advance for
                    the planned direction -- so it never "reaches
                    through" a wall or a closed door the way the
                    previous version accidentally did.
                    Fire is checked first (costs 2 AP, and is the
                    only thing that can explode later), smoke second
                    (costs 1 AP, and left alone it turns into fire on
                    a future dice roll). It only acts ONCE per call
                    (one cell, one action) so as not to drain the
                    whole turn's AP on this instead of advancing
                    toward the assigned objective.
        Inputs: planned_dir (str) -- the direction _advance was
                going to resolve anyway, so as not to check it twice
        Outputs: bool -> True if an adjacent fire or smoke was
                cleared (spent AP), False if there was nothing to do
        Usage: called by _advance() before resolving planned_dir.
        """
        x, y = self.pos
        otras_dirs = [d for d in ("up", "down", "left", "right") if d != planned_dir]

        if self.actionPoints >= 2:
            for otra_dir in otras_dirs:
                element = self.building.getDir(x, y, otra_dir)
                if element not in (0, 3):
                    continue
                neighbor = self.building.getNext(x, y, otra_dir)
                if neighbor is None:
                    continue
                nx, ny = neighbor
                if self.fire.get(nx, ny) == 2:
                    if self.turnFireToNothing(otra_dir):
                        self.model.record_step(self.unique_id, "extinguishFire", otra_dir, prev_pos=(x, y), new_pos=(x, y))
                        return True

        if self.actionPoints >= 1:
            for otra_dir in otras_dirs:
                element = self.building.getDir(x, y, otra_dir)
                if element not in (0, 3):
                    continue
                neighbor = self.building.getNext(x, y, otra_dir)
                if neighbor is None:
                    continue
                nx, ny = neighbor
                if self.fire.get(nx, ny) == 1:
                    if self.turnSmokeToNothing(otra_dir):
                        self.model.record_step(self.unique_id, "extinguishSmoke", otra_dir, prev_pos=(x, y), new_pos=(x, y))
                        return True

        return False

    #------------------------------ ADVANCE ---------------------------------

    def _advance(self, dir):
        """
        Name: _advance
        Description: Resolves ONE obstacle in the given direction:
                    wall -> chop, closed door -> open, fire -> put
                    out, smoke -> clear, free cell -> move. Before
                    resolving `dir`, it reacts to active fire on any
                    of the other 3 sides via
                    Each successful action triggers
                    model.record_step().
        Inputs: dir (str)
        Outputs: bool -> True if some action was executed, False if
                not (no AP, indestructible exterior wall, etc.)
        Usage: called by _act_primitive() at every step of the cycle.
        """
        if self._reaccion_fuego_adyacente(dir):
            return True

        x, y = self.pos
        element = self.building.getDir(x, y, dir)

        if element == 5:
            return False

        if element in (1, 2):
            ok = self.chop(dir)
            if ok:
                self.model.record_step(self.unique_id, "chop", dir, prev_pos=(x, y), new_pos=(x, y))
            return ok

        if element == 4:
            ok = self.openDoor(dir)
            if ok:
                self.model.record_step(self.unique_id, "openDoor", dir, prev_pos=(x, y), new_pos=(x, y))
            return ok

        next_pos = self.building.getNext(x, y, dir)
        if next_pos is None:
            return False
        nx, ny = next_pos
        fireState = self.fire.get(nx, ny)

        if fireState == 2:
            ok = self.turnFireToNothing(dir)
            if ok:
                self.model.record_step(self.unique_id, "extinguishFire", dir, prev_pos=(x, y), new_pos=(x, y))
            return ok

        if fireState == 1:
            ok = self.turnSmokeToNothing(dir)
            if ok:
                self.model.record_step(self.unique_id, "extinguishSmoke", dir, prev_pos=(x, y), new_pos=(x, y))
            return ok

        ok = self.move(dir)
        if ok:
            self.model.record_step(self.unique_id, "move", dir, prev_pos=(x, y), new_pos=self.pos)
        return ok

    #------------------------------ STRATEGIES ---------------------------------

    def _act_primitive(self):
        """
        Name: _act_primitive
        Description: Primitive behavior cycle. Without a victim:
                    chases the nearest unrevealed POI (via
                    poi.pois). With a victim: chases the nearest
                    exit. On arrival, resolves (turnOver/saveVictim)
                    and looks for the next objective with the
                    remaining AP.
        Inputs: none
        Outputs: none
        Usage: called by act() when self.strategy == "primitive".
        """
        while self.actionPoints > 0:
            targets = self.exits if self.victim else self.poi.pois

            if not targets:
                break

            target = nearest_target(self.pos, targets)

            if self.pos == target:
                if self.victim:
                    self.poi.saveVictim()
                    self.victim = False
                    self.model.record_step(self.unique_id, "saveVictim", prev_pos=self.pos, new_pos=self.pos)
                else:
                    self.poi.turnOver(self.pos[0], self.pos[1])
                    self.model.record_step(self.unique_id, "turnOver", prev_pos=self.pos, new_pos=self.pos)
                continue

            dir = greedy_direction(self.pos, target)
            if not self._advance(dir):
                break

    def _act_primitive_astar(self):
            """
            Name: _act_primitive_astar
            Description: Identical to _act_primitive in objective
                        selection (nearest unrevealed POI, then
                        nearest exit), but the direction of each step
                        comes from A* (real lowest-AP-cost route,
                        considering walls and fire), not from
                        greedy_direction (straight line ignoring
                        cost).
            Inputs: none
            Outputs: none
            Usage: called by act() when
                self.strategy == "primitive_astar".
            """
            while self.actionPoints > 0:
                targets = self.exits if self.victim else self.poi.pois

                if not targets:
                    break

                target = nearest_target(self.pos, targets)

                if self.pos == target:
                    if self.victim:
                        self.poi.saveVictim()
                        self.victim = False
                        self.model.record_step(self.unique_id, "saveVictim", prev_pos=self.pos, new_pos=self.pos)
                    else:
                        self.poi.turnOver(self.pos[0], self.pos[1])
                        self.model.record_step(self.unique_id, "turnOver", prev_pos=self.pos, new_pos=self.pos)
                    continue

                path, cost = a_star(self.pos, target, self.building, self.fire)
                dir = get_next_step_direction(self.pos, path)

                if dir is None:
                    break   # no possible route to the current objective

                if not self._advance(dir):
                    break


    def _next_direction_towards(self, destino):
        """
        Name: _next_direction_towards
        Description: Returns the direction of the next step toward
                    `destino`, recalculating A* ONLY when needed
                    (destination changed from the last call, or
                    there is no cached route yet) -- not at every
                    action point of the turn.
        Inputs: destino (tuple[int,int])
        Outputs: str or None -> direction of the next step, or None
                if there is no possible route to destino
        Usage: called by _act_optimized(), both for the exit (when
                carrying a victim) and for objective.
        """
        if destino != self._ruta_destino or not self._ruta:
            self._ruta, _ = a_star(self.pos, destino, self.building, self.fire)
            self._ruta_destino = destino

        if not self._ruta:
            return None

        while len(self._ruta) > 1 and self._ruta[0] != self.pos:
            self._ruta.pop(0)

        return get_next_step_direction(self.pos, self._ruta)

    def _act_optimized(self):
        """
        Name: _act_optimized
        Description: Optimized behavior cycle. While carrying a
                    victim, completely overrides the Coordinator's
                    assignment -- getting the victim out of the
                    building is an absolute, individual priority
                    that needs no coordination. Once the victim is
                    saved, follows objective as assigned by
                    the Coordinator, resolving it on arrival. Falls
                    back to the primitive behavior when the
                    Coordinator has not assigned anything this turn
                    (objective is None).

                    FIX: arrival checks (reaching the exit while
                    carrying a victim, or reaching self.objective)
                    no longer depend on actionPoints being > 0.
                    Previously the whole loop was gated on
                    actionPoints > 0, so if the LAST movement of the
                    turn was the one that landed the agent exactly on
                    the exit/objective and that movement spent the
                    last AP, resolving it (saveVictim/turnOver) was
                    delayed until that same agent's NEXT turn -- the
                    agent was already visually there, but the counter
                    (and therefore to_dict()/the JSON frames) didn't
                    reflect it until a turn later. Resolving an
                    arrival shouldn't cost AP; only the movement
                    itself does -- so the AP gate is now applied only
                    right before the branches that actually act on
                    the board, not before the arrival check.
        Inputs: none
        Outputs: none
        Usage: called by act() when self.strategy == "optimized".
        """
        while True:

            if self.victim:
                # ABSOLUTE PRIORITY
                target = nearest_target(self.pos, self.exits)
                if target is None:
                    break

                if self.pos == target:
                    self.poi.saveVictim()
                    self.victim = False
                    self.model.record_step(self.unique_id, "saveVictim", prev_pos=self.pos, new_pos=self.pos)
                    self.objectives_completed += 1
                    continue

                if self.actionPoints <= 0:
                    break

                dir = self._next_direction_towards(target)
                if dir is None:
                    self._ruta = None
                    break
                if not self._advance(dir):
                    self._ruta = None
                    break
                continue

            if self.objective is None:
                self._act_primitive()
                return

            if self.pos == self.objective:
                if self.tipo_objetivo == "poi_sin_revelar":
                    self.poi.turnOver(self.pos[0], self.pos[1])
                    self.model.record_step(self.unique_id, "turnOver", prev_pos=self.pos, new_pos=self.pos)

                self.objectives_completed += 1
                self.objective = None
                self.tipo_objetivo = None
                continue

            if self.actionPoints <= 0:
                break

            dir = self._next_direction_towards(self.objective)
            if dir is None:
                self._ruta = None
                break
            if not self._advance(dir):
                self._ruta = None
                break