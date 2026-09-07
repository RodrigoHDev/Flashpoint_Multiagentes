import FireManager
import PoiManager
import mesa
import BuildingManager
import Coordinator
import Firefighter

WIDTH, HEIGHT = 10, 8

class GameManager(mesa.Model):
    """
    Orquestador central de la partida (Mesa Model). Instancia y
    conecta los tres managers (fuego, POI, edificio), crea a los
    bomberos, corre el ciclo de turnos, y evalua las condiciones de
    victoria/derrota. Tambien expone el estado completo del juego
    para consumo externo (consola, animacion, o eventualmente Unity).
    """

    def __init__(self, num_firefighters=6, seed=None, strategy="optimized"):
        """
        Nombre: __init__
        Descripcion: crea los tres managers, el grid de Mesa, la
                     lista de agentes y las entradas del edificio, y
                     conecta (link) las referencias cruzadas entre
                     managers. No crea los agentes automaticamente
                     (requiere llamar _crear_agentes por separado).
        Entradas: num_firefighters (int, default 6), seed (int o None,
                  semilla del generador aleatorio de Mesa)
        Salidas: ninguna (constructor)
        Uso: punto de entrada para iniciar una partida nueva, p.ej.
             `model = GameManager(num_firefighters=6, seed=42)`.
        """
        super().__init__(seed=seed)
        self.turn = 0
        self.atomic_step_counter = 0 # Initialize a counter for atomic steps
        self.focus = -1

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

        self._crear_agentes(num_firefighters, strategy)

    def _crear_agentes(self, num_firefighters, strategy="optimized"):
        """
        Nombre: _crear_agentes
        Descripcion: crea num_firefighters bomberos, los coloca en el
                     grid segun _posicion_entrada(), les inyecta las
                     referencias via link(), y los agrega a agentsList.
        Entradas: num_firefighters (int)
        Salidas: ninguna
        Uso: debe llamarse manualmente despues de __init__ para
             poblar la partida (no se llama automaticamente).
        """
        for _ in range(num_firefighters):
            x, y = self._posicion_entrada()
            agente = Firefighter.Firefighter(self)
            agente.strategy = strategy
            self.grid.place_agent(agente, (x, y))
            agente.link(self.buildingManager, self.poiManager, self.fireManager, self.entradas)
            self.agentsList.append(agente)

    def _posicion_entrada(self):
        """
        Nombre: _posicion_entrada
        Descripcion: decide en cual de las 4 entradas del edificio
                     colocar al proximo bombero, siguiendo una
                     distribucion fija para 6 bomberos (2/2/1/1), con
                     reparto ciclico como respaldo si el numero
                     difiere de 6.
        Entradas: ninguna (usa len(self.agentsList) como indice)
        Salidas: tuple[int,int] -> coordenada de entrada elegida
        Uso: llamado por _crear_agentes() una vez por cada bombero.
        """
        index = len(self.agentsList)
        distribucion = [0, 0, 1, 1, 2, 3]

        if index < len(distribucion):
            return self.entradas[distribucion[index]]

        return self.entradas[index % len(self.entradas)]

    def step_agent(self, agent) -> bool:
        """
        Nombre: step_agent
        Descripcion: ejecuta el turno completo de un agente (act()),
                     seguido del avance de fuego (putSmoke()) y la
                     reposicion de POIs (set()). Verifica win/lose
                     antes de actuar.
        Entradas: agent (Firefighter)
        Salidas: bool -> True si el juego ya termino (win o lose),
                 False si debe continuar
        Uso: llamado por step() y run_limited() una vez por agente,
             por cada ronda de turnos.
        """
        if self.lose():
            return True
        if self.win():
            return True

        self.coordinator.coordinate_turn(     # <- NUEVO, antes de que actue
          self.agentsList, self.poiManager, self.fireManager, self.buildingManager
        )

        agent.act()
        self.fireManager.putSmoke()
        self.poiManager.set()
        return False

    def step(self):
        """
        Nombre: step
        Descripcion: avanza la simulacion EXACTAMENTE un turno
                     individual (un solo agente, no una ronda
                     completa), turnando round-robin por agentsList.
                     Esta es la convencion que mesa.batch_run()
                     necesita: llama a model.step() repetidamente,
                     una vez por "paso". Por eso este metodo debe
                     siempre (a) incrementar self.steps -- el
                     contador NATIVO de Mesa (distinto de self.turn),
                     que batch_run usa para el limite max_steps -- y
                     (b) llamar self.datacollector.collect(self) al
                     final, sin excepcion -- de lo contrario
                     batch_run no tiene ninguna fila que reportar,
                     que es exactamente el problema detectado.
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado automaticamente por mesa.batch_run() una vez por
             paso (max_steps en batch_run = turnos individuales,
             igual que en run_limited). Tambien se puede llamar
             manualmente: `while model.running: model.step()`.
        """
        if not self.running:
            return

        self.steps += 1

        agent = self.agentsList[self.turn % len(self.agentsList)]
        self.turn += 1

        self.step_agent(agent)

        self.datacollector.collect(self)

    def win(self) -> bool:
        """
        Nombre: win
        Descripcion: evalua si se cumplio la condicion de victoria
                     (7 o mas victimas salvadas).
        Entradas: ninguna
        Salidas: bool
        Uso: llamado por step_agent(), step() y run_limited() antes
             de cada accion, para detener la partida a tiempo.
        """
        if self.poiManager.getVictimsSaved() >= 7:
            self.running = False
            return True
        return False

    def lose(self) -> bool:
        """
        Nombre: lose
        Descripcion: evalua si se cumplio alguna condicion de derrota
                     (4 o mas victimas perdidas, o 24 o mas puntos de
                     daño estructural acumulado).
        Entradas: ninguna
        Salidas: bool
        Uso: llamado por step_agent(), step() y run_limited() antes
             de cada accion, para detener la partida a tiempo.
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
        Nombre: get_lose_reason
        Descripcion: determina la causa de derrota segun el estado
                     actual, sin efectos secundarios (a diferencia de
                     lose(), no toca self.running). Si ambas
                     condiciones se cumplen a la vez, reporta
                     "victims" primero, igual que el orden de
                     verificacion de lose().
        Entradas: ninguna
        Salidas: str o None -> "victims", "structural", o None si
                 aun no ha perdido
        Uso: llamado por el DataCollector (model_reporters) en cada
             fila, para poder analizar despues, via batch_run, por
             que causa termino cada partida.
        """
        if self.poiManager.getVictimsLost() >= 4:
            return "victims"
        elif self.buildingManager.buildingDam >= 24:
            return "structural"
        return None

    def run_limited(self, max_turns=500, verbose=True, debug=False):
        """
        Nombre: run_limited
        Descripcion: corre la simulacion en consola durante un numero
                     limitado de turnos, guardando un snapshot por
                     turno (incluyendo el inicial) para poder animarla
                     despues con matplotlib, sin depender de Unity.
        Entradas: max_turns (int, default 20), verbose (bool, imprime
                  resumen por turno), debug (bool, imprime traza de
                  cada agente)
        Salidas: list[dict] -> self.history, un snapshot por turno
        Uso: forma recomendada de correr pruebas en consola:
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

    def record_step(self, agent_id, action_type, dir=None):
        """
        Nombre: record_step
        Descripcion: registra UN paso atomico (una sola accion de un
                     agente: mover, cortar, abrir puerta, apagar
                     fuego/humo, revelar POI, salvar victima) -- no
                     un turno completo. Guarda el estado en
                     self.step_history y, si self.export_folder esta
                     configurado, tambien escribe un JSON por paso.
        Entradas: agent_id (int), action_type (str), dir (str o None)
        Salidas: dict -> el estado guardado
        Uso: llamado por Firefighter._advance() y _act_primitive()
             despues de cada accion exitosa.
        """
        self.atomic_step_counter += 1 # Use the new atomic step counter
        state = self.to_dict()
        state["step"] = self.atomic_step_counter
        state["lastAction"] = {"agentId": agent_id, "type": action_type, "dir": dir}

        # if self.export_folder:
        #     os.makedirs(self.export_folder, exist_ok=True)
        #     path = os.path.join(self.export_folder, f"step_{self.step:05d}.json")
        #     with open(path, "w") as f:
        #         json.dump(state, f)

        return state

    def _print_turn_summary(self, turn):
        """
        Nombre: _print_turn_summary
        Descripcion: imprime en consola un resumen del estado global
                     tras un turno (daño, victimas, fuego/humo activo,
                     POIs activos).
        Entradas: turn (int)
        Salidas: ninguna (imprime a consola)
        Uso: llamado por run_limited() al final de cada turno, solo
             si verbose=True.
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
        Nombre: _debug_print
        Descripcion: imprime un mensaje de depuracion con formato
                     consistente, solo si debug esta activo.
        Entradas: turn (int), message (str), debug (bool)
        Salidas: ninguna (imprime a consola)
        Uso: llamado por run_limited() por cada agente en cada turno;
             activar con debug=True para ver la traza detallada.
        """
        if debug:
            print(f"    [DEBUG turno {turn}] {message}")

    def capture_snapshot(self):
        """
        Nombre: capture_snapshot
        Descripcion: copia el estado actual (fireGrid, POIGrid,
                     paredes, daño, victimas, agentes) en un dict
                     independiente, para poder reconstruir/animar la
                     simulacion despues sin depender de que el
                     GameManager siga vivo o sin mutar.
        Entradas: ninguna
        Salidas: dict -> {fireGrid, poiGrid, walls, buildingDam,
                 savedVictims, lostVictims, agents}
        Uso: llamado por run_limited() una vez por turno; el
             resultado alimenta animate_history().
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
        Nombre: _tile_to_dict
        Descripcion: serializa una celda del tablero (paredes, fuego,
                     poi, agentes presentes) a un diccionario plano.
        Entradas: x, y (int)
        Salidas: dict -> {x, y, walls, fire, poi, agentIds}
        Uso: llamado por to_dict() una vez por cada una de las 80
             celdas del tablero.
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

    def set_focus(self, agent_id):
        """
        Nombre: set_focus
        Descripcion: marca un agente como "enfocado" (para UI externa,
                     p.ej. resaltarlo en Unity).
        Entradas: agent_id (int)
        Salidas: ninguna
        Uso: llamado externamente (Unity/consola) cuando el usuario
             selecciona un agente especifico.
        """
        self.focus = agent_id

    def clear_focus(self):
        """
        Nombre: clear_focus
        Descripcion: quita el enfoque actual (vuelve a -1, "ninguno").
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado externamente cuando se deselecciona el agente
             enfocado.
        """
        self.focus = -1

    def to_dict(self):
        """
        Nombre: to_dict
        Descripcion: serializa el estado completo de la partida
                     (turno, dimensiones, daño, victimas, foco, todas
                     las celdas, todos los agentes) a un diccionario
                     plano, listo para exportar como JSON.
        Entradas: ninguna
        Salidas: dict -> estado completo de la partida
        Uso: pensado como el punto de exportacion hacia un consumidor
             externo (p.ej. Unity via JSON), o para inspeccion manual
             del estado actual en consola.
        """
        tiles = [self._tile_to_dict(x, y) for x in range(WIDTH) for y in range(HEIGHT)]
        return {
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
        }