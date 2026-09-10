"""
Title: GameManager
Author: Rodrigo Hurtado
Description:

Central orchestrator of the game (Mesa Model). Instantiates and
connects the three managers (fire, POI, building), creates the
firefighters, runs the turn cycle, and evaluates win/lose
conditions. Also exposes the full game state for external
consumption (console, animation, or eventually Unity).

Functions:
CONSTRUCTOR
__init__

AGENT SETUP
_create_agents
_entry_position

TURN CYCLE
step_agent
step

WIN/LOSE CONDITIONS
win
lose
get_lose_reason

SIMULATION RUNNER
run_limited
_print_turn_summary
_debug_print

STEP RECORDING
record_step

SNAPSHOTS & SERIALIZATION
capture_snapshot
_tile_to_dict
to_dict

FOCUS CONTROL
set_focus
clear_focus

"""

import  FireManager as FireManager
import  PoiManager as PoiManager
import mesa
import  BuildingManager as BuildingManager
import  Coordinator as Coordinator
import  Firefighter as Firefighter

WIDTH, HEIGHT = 10, 8

class GameManager(mesa.Model):
    """
    Central orchestrator of the game (Mesa Model). Instantiates and
    connects the three managers (fire, POI, building), creates the
    firefighters, runs the turn cycle, and evaluates win/lose
    conditions. Also exposes the full game state for external
    consumption (console, animation, or eventually Unity).
    """

    #------------------------------ CONSTRUCTOR ---------------------------------

    def __init__(self, num_firefighters=6, seed=None, strategy="optimized"):
        """
        Name: __init__
        Description: Creates the three managers, the Mesa grid, the
                     agent list, and the building entrances, and
                     links the cross-references between managers.
                     Does not create the agents automatically
                     (requires calling _create_agents separately).
        Inputs: num_firefighters (int, default 6), seed (int or
                None, Mesa's random generator seed)
        Outputs: none (constructor)
        Usage: entry point to start a new game, e.g.
               `model = GameManager(num_firefighters=6, seed=42)`.
        """
        super().__init__(seed=seed)
        self.turn = 0
        self.atomic_step_counter = 0 # Initialize a counter for atomic steps
        self.focus = -1
        # MERGE: list of deltas ("movements") accumulated since the
        # last to_dict(). Replaces the previous record_step() scheme,
        # which stored a FULL snapshot of the state on every atomic
        # step -- expensive to generate and to transmit when the
        # external consumer (e.g. Unity) only needs to know what
        # changed, not the whole board again.
        self.movements = []

        self.buildingManager = BuildingManager.BuildingManager()
        self.fireManager = FireManager.FireManager()
        self.poiManager = PoiManager.PoiManager()
        self.coordinator = Coordinator.Coordinator()

        self.grid = mesa.space.MultiGrid(WIDTH, HEIGHT, torus=False)

        self.agentsList = []
        self.entradas = [(6,0), (0,3), (3,7), (9,4)]

        self.buildingManager.link(self.fireManager, self.poiManager)
        self.poiManager.link(self.buildingManager, self.fireManager, self.agentsList)
        self.fireManager.link(self.buildingManager, self.poiManager, self.agentsList)

        self.running = True
        self.datacollector = mesa.DataCollector(
           model_reporters={
                "turn": lambda m: m.turn,
                "buildingDam": lambda m: m.buildingManager.buildingDam,
                "savedVictims": lambda m: m.poiManager.getVictimsSaved(),
                "lostVictims": lambda m: m.poiManager.getVictimsLost(),
                "fuegoActivo": lambda m: int((m.fireManager.fireGrid == 2).sum()),
                "humoActivo": lambda m: int((m.fireManager.fireGrid == 1).sum()),
                "loseReason": lambda m: m.get_lose_reason(),
            },
            agent_reporters={
                "pos": "pos",
                "actionPoints": "actionPoints",
                "knockdown": "knockdown",
                "victim": "victim",
                "tipo_objetivo": "tipo_objetivo",
                "efficiency": "efficiency",
            },
        )

        self._create_agents(num_firefighters, strategy)

    #------------------------------ AGENT SETUP ---------------------------------

    def _create_agents(self, num_firefighters, strategy="optimized"):
        """
        Name: _create_agents
        Description: Creates num_firefighters firefighters, places
                     them on the grid according to
                     _entry_position(), injects their references
                     via link(), and adds them to agentsList.
        Inputs: num_firefighters (int)
        Outputs: none
        Usage: must be called manually after __init__ to populate
               the game (not called automatically).
        """
        for _ in range(num_firefighters):
            x, y = self._entry_position()
            agente = Firefighter.Firefighter(self)
            agente.strategy = strategy
            self.grid.place_agent(agente, (x, y))
            agente.link(self.buildingManager, self.poiManager, self.fireManager, self.entradas)
            self.agentsList.append(agente)

    def _entry_position(self):
        """
        Name: _entry_position
        Description: Decides which of the 4 building entrances to
                     place the next firefighter at, following a
                     fixed distribution for 6 firefighters (2/2/1/1),
                     with cyclic distribution as a fallback if the
                     number differs from 6.
        Inputs: none (uses len(self.agentsList) as index)
        Outputs: tuple[int,int] -> chosen entrance coordinate
        Usage: called by _create_agents() once per firefighter.
        """
        index = len(self.agentsList)
        distribucion = [0, 0, 1, 1, 2, 3]

        if index < len(distribucion):
            return self.entradas[distribucion[index]]

        return self.entradas[index % len(self.entradas)]

    #------------------------------ TURN CYCLE ---------------------------------

    def step_agent(self, agent) -> bool:
        """
        Name: step_agent
        Description: Executes an agent's full turn (act()), followed
                     by fire advancement (putSmoke()) and POI
                     replenishment (set()). Checks win/lose before
                     acting.
        Inputs: agent (Firefighter)
        Outputs: bool -> True if the game has already ended (win or
                 lose), False if it should continue
        Usage: called by step() and run_limited() once per agent, on
               every round of turns.
        """
        

        self.coordinator.coordinate_turn(  
          self.agentsList, self.poiManager, self.fireManager, self.buildingManager
        )

        agent.act()
        self.fireManager.putSmoke()
        self.poiManager.set()

        if self.lose():
            return True
        if self.win():
            return True

        return False

    def step(self):
        """
        Name: step
        Description: Advances the simulation EXACTLY one individual
                     turn (a single agent, not a full round), taking
                     turns round-robin through agentsList. This is
                     the convention mesa.batch_run() needs: it calls
                     model.step() repeatedly, once per "step". That's
                     why this method must always (a) increment
                     self.steps -- Mesa's NATIVE counter (distinct
                     from self.turn), which batch_run uses for the
                     max_steps limit -- and (b) call
                     self.datacollector.collect(self) at the end,
                     without exception -- otherwise batch_run has no
                     row to report, which is exactly the problem that
                     was detected.
        Inputs: none
        Outputs: none
        Usage: called automatically by mesa.batch_run() once per step
               (max_steps in batch_run = individual turns, same as in
               run_limited). Can also be called manually:
               `while model.running: model.step()`.
        """
        if not self.running:
            return

        self.steps += 1

        agent = self.agentsList[self.turn % len(self.agentsList)]
        self.turn += 1

        self.step_agent(agent)
        self.datacollector.collect(self)

    #------------------------------ WIN/LOSE CONDITIONS ---------------------------------

    def win(self) -> bool:
        """
        Name: win
        Description: Evaluates whether the win condition was met (7
                     or more victims saved).
        Inputs: none
        Outputs: bool
        Usage: called by step_agent(), step(), and run_limited()
               before every action, to stop the game in time.
        """
        if self.poiManager.getVictimsSaved() >= 7:
            self.running = False
            return True
        return False

    def lose(self) -> bool:
        """
        Name: lose
        Description: Evaluates whether any lose condition was met (4
                     or more victims lost, or 24 or more accumulated
                     structural damage points).
        Inputs: none
        Outputs: bool
        Usage: called by step_agent(), step(), and run_limited()
               before every action, to stop the game in time.
        """
        if self.poiManager.getVictimsLost() >= 4:
            self.running = False
            return True
        elif self.buildingManager.buildingDam >= 24:
            self.running = False
            return True
        return False


    def get_lose_reason(self):
        """
        Name: get_lose_reason
        Description: Determines the cause of the loss based on the
                     current state, without side effects (unlike
                     lose(), it does not touch self.running). If both
                     conditions are met at once, reports "victims"
                     first, matching lose()'s check order.
        Inputs: none
        Outputs: str or None -> "victims", "structural", or None if
                 the game hasn't been lost yet
        Usage: called by the DataCollector (model_reporters) on every
               row, so that afterward, via batch_run, one can analyze
               why each game ended.
        """
        if self.poiManager.getVictimsLost() >= 4:
            return "victims"
        elif self.buildingManager.buildingDam >= 24:
            return "structural"
        return None

    #------------------------------ SIMULATION RUNNER ---------------------------------

    def run_limited(self, max_turns=500, verbose=True, debug=False):
        """
        Name: run_limited
        Description: Runs the simulation in the console for a
                     limited number of turns, saving one snapshot per
                     turn (including the initial one) so it can be
                     animated afterward with matplotlib, without
                     depending on Unity.
        Inputs: max_turns (int, default 20), verbose (bool, prints a
                summary per turn), debug (bool, prints a trace for
                each agent)
        Outputs: list[dict] -> self.history, one snapshot per turn
        Usage: recommended way to run console tests:
               `model.run_limited(max_turns=40, verbose=True)`.
        """
        self.history = []
        self._debug_print(0, "estado inicial", debug)
        self.history.append(self.capture_snapshot())

        turnos_transcurridos = 0

        while turnos_transcurridos < max_turns:
            if self.win() or self.lose():
                if verbose:
                    print(f"[Turno {turnos_transcurridos}] Juego terminado -> win={self.win()}, lose={self.lose()}")
                break

            for agent in self.agentsList:
                self.turn += 1
                self.steps += 1
                turnos_transcurridos += 1

                terminado = self.step_agent(agent)
                self._debug_print(self.turn, f"agent {agent.unique_id} pos={agent.pos}", debug)

                self.history.append(self.capture_snapshot())
                self.datacollector.collect(self)

                if verbose:
                    print(f"\n--- Turno {self.turn} (agente {agent.unique_id}) ---")
                    self._print_turn_summary(self.turn)

                if terminado or turnos_transcurridos >= max_turns:
                    break
        else:
            if verbose:
                print(f"\nSe alcanzo el limite de {max_turns} turnos sin terminar el juego.")

        return self.history

    def _print_turn_summary(self, turn):
        """
        Name: _print_turn_summary
        Description: Prints a summary of the global state to the
                     console after a turn (damage, victims,
                     active fire/smoke, active POIs).
        Inputs: turn (int)
        Outputs: none (prints to console)
        Usage: called by run_limited() at the end of every turn,
               only if verbose=True.
        """
        fuego = int((self.fireManager.fireGrid == 2).sum())
        humo = int((self.fireManager.fireGrid == 1).sum())
        print(f"  buildingDam={self.buildingManager.buildingDam}, "
              f"savedVictims={self.poiManager.getVictimsSaved()}, "
              f"lostVictims={self.poiManager.getVictimsLost()}, "
              f"fuegoActivo={fuego}, humoActivo={humo}, "
              f"poisActivos={self.poiManager.quantity}")

    def _debug_print(self, turn, message, debug):
        """
        Name: _debug_print
        Description: Prints a debug message with a consistent
                     format, only if debug is active.
        Inputs: turn (int), message (str), debug (bool)
        Outputs: none (prints to console)
        Usage: called by run_limited() for every agent on every
               turn; enable with debug=True to see the detailed
               trace.
        """
        if debug:
            print(f"    [DEBUG turno {turn}] {message}")

    #------------------------------ STEP RECORDING ---------------------------------

    def record_step(self, agent_id, action_type, dir=None, prev_pos=None, new_pos=None):
        """
        Name: record_step
        Description: Records ONE atomic step (a single agent action:
                     move, chop, open door, put out fire/smoke,
                     reveal POI, save victim) -- not a full turn.
                     MERGE: unlike the previous version (which built
                     a full self.to_dict() -- all 80 board cells --
                     on EVERY atomic step), it now builds only a
                     lightweight DELTA {step, agentId, type, dir,
                     prevX, prevY, newX, newY} and appends it to
                     self.movements. The external consumer can still
                     reconstruct the full state via to_dict(), which
                     now includes "movements" and by default clears
                     the list after reading it (see flush_movements).
        Inputs: agent_id (int), action_type (str), dir (str or
                None), prev_pos (tuple[int,int] or None, position
                before the action), new_pos (tuple[int,int] or None,
                position after the action)
        Outputs: dict -> the recorded delta
        Usage: called by Firefighter._advance(), _act_primitive(),
               _act_primitive_astar(), _act_optimized(), and
               setKnockdown() after every successful action.
        """
        self.atomic_step_counter += 1
        movement = {
            "step": self.atomic_step_counter,
            "agentId": agent_id,
            "type": action_type,
            "dir": dir,
            "prevX": prev_pos[0] if prev_pos else None,
            "prevY": prev_pos[1] if prev_pos else None,
            "newX": new_pos[0] if new_pos else None,
            "newY": new_pos[1] if new_pos else None,
        }
        self.movements.append(movement)
        return movement

    #------------------------------ SNAPSHOTS & SERIALIZATION ---------------------------------

    def capture_snapshot(self):
        """
        Name: capture_snapshot
        Description: Copies the current state (fireGrid, POIGrid,
                     walls, damage, victims, agents) into an
                     independent dict, so the simulation can be
                     reconstructed/animated afterward without
                     depending on GameManager staying alive or being
                     mutated.
        Inputs: none
        Outputs: dict -> {fireGrid, poiGrid, walls, buildingDam,
                 savedVictims, lostVictims, agents}
        Usage: called by run_limited() once per turn; the result
               feeds animate_history().
        """
        walls_snapshot = [
            [self.buildingManager.get(x, y) for y in range(HEIGHT)]
            for x in range(WIDTH)
        ]

        return {
            "fireGrid": self.fireManager.fireGrid.copy(),
            "poiGrid": self.poiManager.POIGrid.copy(),
            "walls": walls_snapshot,
            "buildingDam": self.buildingManager.buildingDam,
            "savedVictims": self.poiManager.getVictimsSaved(),
            "lostVictims": self.poiManager.getVictimsLost(),
            "agents": [
                {"id": a.unique_id, "x": a.x, "y": a.y, "knockdown": a.knockdown}
                for a in self.agentsList
            ],
        }

    def _tile_to_dict(self, x, y):
        """
        Name: _tile_to_dict
        Description: Serializes a board cell (walls, fire, poi,
                     agents present) into a flat dictionary.
        Inputs: x, y (int)
        Outputs: dict -> {x, y, walls, fire, poi, agentIds}
        Usage: called by to_dict() once for each of the 80 board
               cells.
        """
        walls = self.buildingManager.get(x, y)
        agent_ids = [a.unique_id for a in self.agentsList if a.x == x and a.y == y]
        return {
            "x": x,
            "y": y,
            "walls": {
                "up": walls[0], "down": walls[1],
                "left": walls[2], "right": walls[3],
            },
            "fire": int(self.fireManager.get(x, y)),
            "poi": int(self.poiManager.get(x, y)),
            "agentIds": agent_ids,
        }

    def to_dict(self, flush_movements=True):
        """
        Name: to_dict
        Description: Serializes the full game state (turn,
                     dimensions, damage, victims, focus, all cells,
                     all agents) into a flat dictionary, ready to
                     export as JSON. MERGE: now includes "movements"
                     (the deltas accumulated by record_step() since
                     the last call to to_dict()). By default
                     (flush_movements=True) the list is cleared after
                     being read, so the external consumer receives
                     each delta exactly once; pass
                     flush_movements=False to inspect without
                     consuming the buffer (e.g. debugging).
        Inputs: flush_movements (bool, default True)
        Outputs: dict -> full game state, including "movements"
        Usage: intended as the export point toward an external
               consumer (e.g. Unity via JSON), or for manual
               inspection of the current state in the console.
        """
        tiles = [self._tile_to_dict(x, y) for x in range(WIDTH) for y in range(HEIGHT)]
        result = {
            "turn": self.turn,
            "width": WIDTH,
            "height": HEIGHT,
            "buildingDamage": self.buildingManager.buildingDam,
            "saved": self.poiManager.getVictimsSaved(),
            "lost": self.poiManager.getVictimsLost(),
            "focus": self.focus,
            "tiles": tiles,
            "agents": [
                {
                    "id": a.unique_id,
                    "knockdown": a.knockdown,
                    "victim": a.victim,
                    "x": a.x,
                    "y": a.y,
                    "ap": a.ap,
                }
                for a in self.agentsList
            ],
            "movements": self.movements,
        }
        if flush_movements:
            self.movements = []
        return result

    #------------------------------ FOCUS CONTROL ---------------------------------

    def set_focus(self, agent_id):
        """
        Name: set_focus
        Description: Marks an agent as "focused" (for external UI,
                     e.g. highlighting it in Unity).
        Inputs: agent_id (int)
        Outputs: none
        Usage: called externally (Unity/console) when the user
               selects a specific agent.
        """
        self.focus = agent_id

    def clear_focus(self):
        """
        Name: clear_focus
        Description: Removes the current focus (back to -1, "none").
        Inputs: none
        Outputs: none
        Usage: called externally when the focused agent is
               deselected.
        """
        self.focus = -1