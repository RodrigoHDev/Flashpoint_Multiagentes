import mesa
from auxiliars import triage_factor, nearest_target, a_star, greedy_direction, get_next_step_direction


class Firefighter(mesa.Agent):
    """
    Agente bombero (Mesa Agent). Guarda su propio estado (posicion
    via Mesa, direccion, knockdown, si carga victima, puntos de
    accion) y ejecuta su turno segun la estrategia activa
    ("primitive" por ahora, "optimized" pendiente).
    """

    def __init__(self, model):
        """
        Nombre: __init__
        Descripcion: crea el agente y su estado inicial. La posicion
                     la asigna Mesa via grid.place_agent(), no aqui.
                     self.id expone el unique_id de Mesa como entero
                     simple, usado en los prints de depuracion.
        Entradas: model (GameManager)
        Salidas: ninguna (constructor)
        Uso: llamado por GameManager._crear_agentes() una vez por
             cada bombero de la partida.
        """
        super().__init__(model)
        self.id = self.unique_id
        self.direction = "down"
        self.knockdown = False
        self.victim = False
        self.actionPoints = 0

        #Estrategias desarrolladas
        # self.strategy = "primitive"
        # self.strategy = "primitive_astar"
        self.strategy = "optimized"

        self.objetivo_actual = None
        self.tipo_objetivo = None

        self._ruta = None
        self._ruta_destino = None

        self.steps_taken = 0
        self.objectives_completed = 0

        self.building = None
        self.poi = None
        self.fire = None
        self.exits = None

    @property
    def x(self):
        """
        Nombre: x (property)
        Descripcion: expone la coordenada x sin duplicar estado
                     (deriva de self.pos, que administra Mesa).
        Entradas: ninguna
        Salidas: int
        Uso: leido por GameManager.capture_snapshot/to_dict.
        """
        return self.pos[0]

    @property
    def y(self):
        """
        Nombre: y (property)
        Descripcion: expone la coordenada y sin duplicar estado.
        Entradas: ninguna
        Salidas: int
        Uso: leido por GameManager.capture_snapshot/to_dict.
        """
        return self.pos[1]

    @property
    def ap(self):
        """
        Nombre: ap (property)
        Descripcion: alias de self.actionPoints para compatibilidad
                     con el formato esperado por GameManager.to_dict.
        Entradas: ninguna
        Salidas: int
        Uso: leido por GameManager.to_dict.
        """
        return self.actionPoints

    @property
    def efficiency(self):
        """
        Nombre: efficiency (property)
        Descripcion: porcentaje de objetivos completados por cada
                     paso de movimiento real dado. Un agente que
                     cumple tareas con pocos movimientos tiene
                     eficiencia alta; uno que deambula mucho sin
                     completar objetivos, baja.
        Entradas: ninguna
        Salidas: float (0.0 si aun no se ha movido)
        Uso: leido por el DataCollector de GameManager.
        """
        if self.steps_taken == 0:
            return 0.0

        return round((self.objectives_completed / self.steps_taken)*100,2)


    def link(self, buildingManager, poiManager, fireManager, exits):
        """
        Nombre: link
        Descripcion: inyecta las referencias a los managers y a la
                     lista de salidas del edificio.
        Entradas: buildingManager, poiManager, fireManager (managers),
                  exits (list[tuple[int,int]])
        Salidas: ninguna
        Uso: llamado por GameManager._crear_agentes() justo despues
             de crear cada Firefighter.
        """
        self.building = buildingManager
        self.poi = poiManager
        self.fire = fireManager
        self.exits = exits

    def restockAP(self):
        """
        Nombre: restockAP
        Descripcion: repone los puntos de accion al maximo (4) al
                     inicio de cada turno.
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado por act() al comienzo de cada turno del agente.
        """
        self.actionPoints = 4

    def getKnockdown(self):
        """
        Nombre: getKnockdown
        Descripcion: consulta si el agente esta derribado.
        Entradas: ninguna
        Salidas: bool
        Uso: disponible para logica externa (Coordinator futuro,
             reportes) que necesite filtrar agentes activos.
        """
        return self.knockdown

    def setKnockdown(self, value):
        """
        Nombre: setKnockdown
        Descripcion: marca al agente como derribado. Si value=True:
                     si cargaba una victima la cuenta como perdida
                     (comportamiento ya existente), y respawnea DE
                     INMEDIATO en la salida mas cercana via
                     model.grid.move_agent() (no asignacion directa
                     de self.pos), conservando los AP que tuviera en
                     ese momento -- la teletransportacion no es una
                     accion jugada, no consume AP. Limpia cualquier
                     objetivo asignado por el Coordinator, ya que la
                     posicion cambio por completo y ese objetivo ya
                     no aplica. El estado se resuelve al instante --
                     no bloquea turnos futuros. MERGE: se captura
                     pos_antes ANTES de la teletransportacion para
                     que record_step reciba prev_pos/new_pos reales
                     (antes solo se registraba el tipo de accion sin
                     posiciones).
        Entradas: value (bool)
        Salidas: ninguna
        Uso: llamado por FireManager.turnToFire() cuando el fuego
             alcanza la celda del agente.
        """
        if value:
            if self.victim:
                self.poi.destroyVictim()
                self.victim = False

            pos_antes = self.pos
            salida = nearest_target(self.pos, self.exits)
            if salida is not None:
                self.model.grid.move_agent(self, salida)

            self.objetivo_actual = None
            self.tipo_objetivo = None
            self.model.record_step(self.unique_id, "respawn_knockdown", prev_pos=pos_antes, new_pos=self.pos)

        self.knockdown = False

    def assignVictim(self):
        """
        Nombre: assignVictim
        Descripcion: marca que el agente ahora carga una victima.
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado por PoiManager.turnOver() cuando el POI revelado
             resulta ser una victima real.
        """
        self.victim = True
        print(f"[Agente {self.id}] Have victim at {self.pos[0]}, {self.pos[1]}")

    def move(self, dir):
        """
        Nombre: move
        Descripcion: mueve al agente una celda en la direccion dada,
                     si tiene AP suficientes segun el costo (1 sobre
                     nada/humo, 2 sobre fuego o cargando victima;
                     prohibido moverse con victima sobre fuego). El
                     movimiento se hace via model.grid.move_agent()
                     (no asignacion directa de self.pos), para que
                     Mesa mantenga correctamente su estructura interna
                     de MultiGrid sincronizada con la posicion real.
        Entradas: dir (str)
        Salidas: bool -> True si se movio, False si no pudo
        Uso: llamado por _advance() cuando la celda destino esta
             libre de fuego/humo activo que requiera limpieza previa.
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
        Nombre: chop
        Descripcion: golpea la pared/puerta en la direccion dada,
                     costando 2 AP, si BuildingManager.damage confirma
                     que habia algo daniable ahi.
        Entradas: dir (str)
        Salidas: bool -> True si se aplico daño, False si no
        Uso: llamado por _advance() cuando el lado en esa direccion
             es una pared (1 o 2 vidas).
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
        Nombre: openDoor
        Descripcion: alterna el estado de una puerta cerrada/abierta
                     en la direccion dada, costando 1 AP.
        Entradas: dir (str)
        Salidas: bool -> True si habia una puerta ahi, False si no
        Uso: llamado por _advance() cuando el lado en esa direccion
             es una puerta cerrada.
        """
        if self.actionPoints < 1:
            return False
        if not self.building.moveDoor(self.pos[0], self.pos[1], dir):
            return False
        self.direction = dir
        self.actionPoints -= 1
        return True

    def _extinguish(self, dir, cost, requiere, accion):
        """
        Nombre: _extinguish
        Descripcion: helper generico para las 3 variantes de apagar
                     fuego/humo: valida AP, valida que la celda
                     vecina tenga el estado requerido, y aplica la
                     accion de FireManager correspondiente.
        Entradas: dir (str), cost (int), requiere (int, estado de
                  fuego esperado), accion (funcion de FireManager)
        Salidas: bool -> True si se aplico, False si no
        Uso: usado internamente por turnFireToSmoke, turnFireToNothing
             y turnSmokeToNothing.
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
        Nombre: turnFireToSmoke
        Descripcion: reduce fuego a humo en la celda vecina, costo 1 AP.
        Entradas: dir (str)
        Salidas: bool
        Uso: accion manual disponible para el agente (no usada en el
             ciclo _advance actual, que va directo a turnFireToNothing).
        """
        if self._extinguish(dir, 1, 2, self.fire.turnToSmoke):
            print(f"[Agente {self.id}] Turned Fire to Smoke at: {self.pos[0]}, {self.pos[1]}")
            return True
        return False

    def turnFireToNothing(self, dir):
        """
        Nombre: turnFireToNothing
        Descripcion: apaga fuego por completo en la celda vecina,
                     costo 2 AP.
        Entradas: dir (str)
        Salidas: bool
        Uso: llamado por _advance() cuando la celda destino tiene fuego.
        """
        if self._extinguish(dir, 2, 2, self.fire.turnOff):
            print(f"[Agente {self.id}] Turned Fire to Nothing at: {self.pos[0]}, {self.pos[1]}")
            return True
        return False

    def turnSmokeToNothing(self, dir):
        """
        Nombre: turnSmokeToNothing
        Descripcion: limpia humo en la celda vecina, costo 1 AP.
        Entradas: dir (str)
        Salidas: bool
        Uso: llamado por _advance() cuando la celda destino tiene humo.
        """
        if self._extinguish(dir, 1, 1, self.fire.turnOff):
            print(f"[Agente {self.id}] Turned Smoke to Nothing at: {self.pos[0]}, {self.pos[1]}")
            return True
        return False

    def _reaccion_fuego_adyacente(self, dir_planeada):
        """
        Nombre: _reaccion_fuego_adyacente
        Descripcion: revisa los 3 lados NO planeados (todos menos
                     dir_planeada) en busca de fuego activo alcanzable
                     y, si hay AP de sobra, lo apaga antes de resolver
                     el paso planeado. _advance() ya apagaba fuego,
                     pero solo el que estaba justo en la direccion de
                     viaje -- un agente podia pasar pegado a fuego que
                     quedaba a un lado sin tocarlo, porque su ruta A*
                     iba para otro lado. Como el dano estructural en
                     este juego solo sale de explosiones, y las
                     explosiones solo pueden salir de fuego que sigue
                     activo, un fuego adyacente ignorado por puro
                     accidente de geometria de ruta es exactamente el
                     tipo de omision que alimenta la siguiente
                     explosion. Se limita a fuego (no humo) porque es
                     lo unico que puede explotar, y solo actua UNA vez
                     por llamada (una celda) para no vaciar el AP del
                     turno completo en esto en vez de avanzar hacia el
                     objetivo asignado. MERGE: la celda donde se apaga
                     el fuego no cambia (el agente no se mueve), asi
                     que prev_pos == new_pos == (x, y) en el delta
                     registrado.
                     ADVERTENCIA para probar despues: si un agente
                     queda "clavado" turno tras turno apagando el
                     mismo vecino que se reenciende sin nunca avanzar
                     hacia su objetivo asignado, hace falta un
                     cooldown (no repetir la misma celda dos turnos
                     seguidos) -- de momento no esta puesto porque no
                     sabemos aun si ocurre en la practica.
        Entradas: dir_planeada (str) -- la direccion que _advance
                  iba a resolver de todas formas, para no revisarla
                  dos veces
        Salidas: bool -> True si se apago un fuego adyacente (gasto
                 una de las AP del turno), False si no habia nada que
                 hacer
        Uso: llamado por _advance() antes de resolver dir_planeada.
        """
        if self.actionPoints < 2:
            return False
        x, y = self.pos
        for otra_dir in ("up", "down", "left", "right"):
            if otra_dir == dir_planeada:
                continue
            vecino = self.building.getNext(x, y, otra_dir)
            if vecino is None:
                continue
            nx, ny = vecino
            if self.fire.get(nx, ny) == 2:
                if self.turnFireToNothing(otra_dir):
                    self.model.record_step(self.unique_id, "extinguishFire", otra_dir, prev_pos=(x, y), new_pos=(x, y))
                    return True
        return False

    def _advance(self, dir):
        """
        Nombre: _advance
        Descripcion: resuelve UN obstaculo en la direccion dada:
                     pared -> chop, puerta cerrada -> abrir, fuego ->
                     apagar, humo -> limpiar, celda libre -> mover.
                     Antes de resolver `dir`, reacciona a fuego activo
                     en cualquiera de los otros 3 lados via
                     _reaccion_fuego_adyacente() -- ver esa funcion
                     para el porque. Cada accion exitosa dispara
                     model.record_step() para que exista un delta por
                     CADA paso, no solo al final del turno completo
                     del agente. MERGE: cada llamada ahora pasa
                     prev_pos/new_pos explicitos -- (x, y) capturado
                     al inicio para las acciones que no mueven al
                     agente (chop, openDoor, apagar fuego/humo), y
                     self.pos (ya actualizado por move()) como
                     new_pos cuando si hay desplazamiento real.
        Entradas: dir (str)
        Salidas: bool -> True si se ejecuto alguna accion, False si
                 no (sin AP, pared exterior indestructible, etc.)
        Uso: llamado por _act_primitive() en cada paso del ciclo.
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

    def act(self):
        """
        Nombre: act
        Descripcion: punto de entrada del turno del agente. Repone
                     AP, y si no esta derribado, delega en la
                     estrategia activa. Este metodo NO cambia cuando
                     se agregue el comportamiento optimizado.
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado una vez por agente, por cada iteracion de
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

    def _act_primitive(self):
        """
        Nombre: _act_primitive
        Descripcion: ciclo de comportamiento primitivo. Sin victima:
                     persigue el POI sin revelar mas cercano (via
                     poi.pois). Con victima: persigue la salida mas
                     cercana. Al llegar, resuelve (turnOver/saveVictim)
                     y busca el siguiente objetivo con el AP restante.
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado por act() cuando self.strategy == "primitive".
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
            Nombre: _act_primitive_astar
            Descripcion: identico a _act_primitive en la seleccion de
                        objetivo (POI sin revelar mas cercano, luego
                        salida mas cercana), pero la direccion de cada
                        paso viene de A* (ruta real de menor costo en
                        AP, considerando paredes y fuego), no de
                        greedy_direction (linea recta ignorando costo).
            Entradas: ninguna
            Salidas: ninguna
            Uso: llamado por act() cuando self.strategy == "primitive_astar".
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
                    break   # sin ruta posible hacia el objetivo actual

                if not self._advance(dir):
                    break


    def _siguiente_direccion_hacia(self, destino):
        """
        Nombre: _siguiente_direccion_hacia
        Descripcion: entrega la direccion del proximo paso hacia
                     `destino`, recalculando A* SOLO cuando hace falta
                     (destino nuevo respecto a la ultima llamada, o
                     todavia no hay ruta cacheada) -- no en cada punto
                     de accion del turno. Antes, _act_optimized llamaba
                     a_star() en cada iteracion del ciclo while; como
                     extinguir fuego/humo cambia de inmediato el costo
                     de esa celda (ver edge_cost en auxiliars.py), un
                     recalculo a mitad de turno a veces encontraba
                     "mejor" retroceder un paso que ya se habia dado
                     -- eso se veia literalmente en el log como
                     Moving to X / Moving to Y-anterior antes de
                     actuar, AP gastados en vaiven sin avance real.
                     Cachear la ruta y solo resincronizarla contra la
                     posicion real (sin recalcular) elimina ese vaiven.
        Entradas: destino (tuple[int,int])
        Salidas: str o None -> direccion del siguiente paso, o None si
                 no hay ruta posible hacia destino
        Uso: llamado por _act_optimized(), tanto para la salida
             (cuando carga victima) como para objetivo_actual.
        """
        if destino != self._ruta_destino or not self._ruta:
            self._ruta, _ = a_star(self.pos, destino, self.building, self.fire)
            self._ruta_destino = destino

        if not self._ruta:
            return None

        # Resincroniza la ruta cacheada contra la posicion real, sin
        # recalcular: si _advance solo corto una pared o abrio una
        # puerta (no hubo movimiento), la cabeza de la ruta sigue
        # siendo self.pos y este while no hace nada; si si hubo
        # movimiento, descarta las celdas ya recorridas.
        while len(self._ruta) > 1 and self._ruta[0] != self.pos:
            self._ruta.pop(0)

        return get_next_step_direction(self.pos, self._ruta)

    def _act_optimized(self):
        """
        (docstring actualizado: se agrega el override de victima -- ignora
        por completo la asignacion del Coordinator mientras carga una
        victima, ya que sacarla del edificio es una prioridad absoluta e
        individual, sin necesidad de coordinacion -- y un respaldo al
        primitivo cuando el Coordinator no le asigno nada este turno.)
        """
        while self.actionPoints > 0:

            if self.victim:
                # PRIORIDAD ABSOLUTA
                target = nearest_target(self.pos, self.exits)
                if target is None:
                    break

                if self.pos == target:
                    self.poi.saveVictim()
                    self.victim = False
                    self.model.record_step(self.unique_id, "saveVictim", prev_pos=self.pos, new_pos=self.pos)
                    self.objectives_completed += 1
                    continue

                dir = self._siguiente_direccion_hacia(target)
                if dir is None:
                    self._ruta = None
                    break
                if not self._advance(dir):
                    self._ruta = None
                    break
                continue

            if self.objetivo_actual is None:
                self._act_primitive()
                return

            if self.pos == self.objetivo_actual:
                if self.tipo_objetivo == "poi_sin_revelar":
                    self.poi.turnOver(self.pos[0], self.pos[1])
                    self.model.record_step(self.unique_id, "turnOver", prev_pos=self.pos, new_pos=self.pos)

                # fuego_amenaza / fuego_general / humo_general: ya se
                # resuelven solos durante el trayecto (_advance apaga
                # fuego/humo automaticamente antes de pisar esa celda),
                # asi que no hace falta accion adicional aqui.

                self.objectives_completed += 1
                self.objetivo_actual = None    # <- limpieza explicita, no inferida
                self.tipo_objetivo = None
                continue

            dir = self._siguiente_direccion_hacia(self.objetivo_actual)
            if dir is None:
                self._ruta = None
                break
            if not self._advance(dir):
                self._ruta = None
                break