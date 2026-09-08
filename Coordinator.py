import Candidate
import numpy as np
from auxiliars import triage_factor, a_star, manhattan, FIRE_CANDIDATE_TYPES, dijkstra_from

WIDTH, HEIGHT = 10, 8

class Coordinator:
    """
    Orquesta la estrategia optimizada: genera candidatos a partir
    del estado del tablero, construye la matriz de costo via A*,
    resuelve la asignacion optima con backtracking y poda, y la
    aplica a los agentes. Guarda el ultimo estado conocido de
    candidatos/agentes libres para saber cuando vale la pena
    recalcular.
    """

    def __init__(self):
        """
        Nombre: __init__
        Descripcion: inicializa el coordinador sin ninguna
                     asignacion previa registrada.
        Entradas: ninguna
        Salidas: ninguna (constructor)
        Uso: instanciado una vez dentro de GameManager.__init__,
             igual que los demas managers.
        """
        self._ultimo_candidatos = set()
        self._ultimo_libres = set()
        self._triage_previo = False
        self._dam_en_ultimo_interrupt = 0

    def scan_poi_candidates(self, poi, ya_asignados):
        """
        Nombre: scan_poi_candidates
        Descripcion: genera un candidato por cada POI sin revelar
                     que no tenga ya un agente asignado.
        Entradas: poi (PoiManager), ya_asignados (set[tuple[int,int]])
        Salidas: list[Candidate]
        Uso: llamado por generate_candidates().
        """
        candidatos = []
        for pos in poi.pois:
            if pos not in ya_asignados:
                candidatos.append(Candidate.Candidate(pos, "poi_sin_revelar", 10))
        return candidatos


    def _chain_run(self, building, fire, x, y, dir):
        """
        Nombre: _chain_run
        Descripcion: cuenta cuantas celdas consecutivas de fuego hay
                     empezando justo despues de (x,y) en la direccion
                     dada, caminando solo por lados abiertos (mismo
                     criterio que shockwave: element in (0,3)). No
                     cuenta la celda de origen.
        Entradas: building (BuildingManager), fire (FireManager),
                  x, y (int), dir (str)
        Salidas: int -> longitud de la racha de fuego en esa direccion
        Uso: llamado por scan_chain_breaks() dos veces por eje
             (una vez por cada sentido) para medir cuanto fuego
             contiguo hay a cada lado de una celda candidata.
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

    def scan_chain_breaks(self, fire, building, ya_asignados):
        """
        Nombre: scan_chain_breaks
        Descripcion: para cada celda de fuego activa, mide (por cada
                     eje vertical y horizontal) cuanto fuego contiguo
                     hay a cada lado usando _chain_run, y calcula un
                     "puntaje de ruptura" = min(racha_a, racha_b) + 1.
                     Ese puntaje es maximo cerca del centro de una
                     cadena larga y minimo (1) en los extremos, asi
                     que prioriza el "eslabon debil" que divide una
                     cadena larga en dos cortas, no solo el borde del
                     cluster. Solo genera candidato si al menos un eje
                     tiene una cadena de 3+ celdas y el puntaje es >=2
                     (evita marcar fuego aislado o en el borde).
        Entradas: fire (FireManager), building (BuildingManager),
                  ya_asignados (set[tuple[int,int]])
        Salidas: list[Candidate] -> tipo "romper_cadena"
        Uso: llamado por generate_candidates().
        """
        candidatos = []
        ejes = [("up", "down"), ("left", "right")]

        for x in range(WIDTH):
            for y in range(HEIGHT):
                if (x, y) in ya_asignados:
                    continue
                if fire.get(x, y) != 2:
                    continue

                mejor_score = 0
                for dir_a, dir_b in ejes:
                    run_a = self._chain_run(building, fire, x, y, dir_a)
                    run_b = self._chain_run(building, fire, x, y, dir_b)
                    if run_a + run_b + 1 < 3:
                        continue
                    score = min(run_a, run_b) + 1
                    mejor_score = max(mejor_score, score)

                if mejor_score >= 2:
                    prioridad = 8 + mejor_score * 3
                    candidatos.append(Candidate.Candidate((x, y), "romper_cadena", prioridad))

        return candidatos

    def scan_breach_points(self, poi, fire, building, ya_asignados):
        """
        Nombre: scan_breach_points
        Descripcion: para cada POI sin revelar o victima (poi.get en
                     (1,3)), hace BFS saliendo de esa celda solo por
                     lados abiertos (mismo criterio que
                     getNeighborhoodFire: element in (0,3)) hasta
                     encontrar la celda de fuego activa mas cercana
                     por ese camino sin paredes/puertas cerradas de
                     por medio. Esa celda de fuego es el "punto de
                     brecha": el unico camino por el que el fuego
                     podria llegar a ese POI sin necesitar una
                     explosion con suerte. Si varios POIs llegan a la
                     misma celda de fuego, se queda con la distancia
                     minima encontrada. Prioridad mas alta cuanto mas
                     cerca esta el punto de brecha del POI (a
                     distancia 1 es el mismo caso que antes cubria
                     scan_fire_threats, pero con prioridad mayor y
                     tambien detecta amenazas a 2+ pasos de distancia
                     que scan_fire_threats no veia). Esta funcion
                     generaliza y reemplaza a scan_fire_threats.
        Entradas: poi (PoiManager), fire (FireManager),
                  building (BuildingManager),
                  ya_asignados (set[tuple[int,int]])
        Salidas: list[Candidate] -> tipo "punto_de_brecha"
        Uso: llamado por generate_candidates().
        """
        candidatos = []
        directions = ["up", "down", "left", "right"]
        mejor_por_fuego = {}

        objetivos = [
            (x, y)
            for x in range(WIDTH)
            for y in range(HEIGHT)
            if poi.get(x, y) in (1, 3)
        ]

        for origen in objetivos:
            visitado = {origen}
            frontera = [origen]
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
            if fire_pos in ya_asignados:
                continue
            anterior = mejor_por_fuego.get(fire_pos)
            if anterior is None or distancia < anterior:
                mejor_por_fuego[fire_pos] = distancia

        for fire_pos, distancia in mejor_por_fuego.items():
            prioridad = max(20 - 3 * (distancia - 1), 6)
            candidatos.append(Candidate.Candidate(fire_pos, "punto_de_brecha", prioridad))

        return candidatos

    def scan_general_fire(self, fire, building, ya_asignados):
        """
        Nombre: scan_general_fire
        Descripcion: genera un candidato por cada celda con fuego o
                     humo activo, sin importar si amenaza un POI.
                     Prioridad baja: sirve para ocupar agentes que
                     el backtracking no asigno a algo mas urgente,
                     evitando que el edificio se dañe sin control.
        Entradas: fire (FireManager), ya_asignados (set[tuple[int,int]])
        Salidas: list[Candidate]
        Uso: llamado por generate_candidates().
        """
        candidatos = []
        directions = ["up", "down", "left", "right"]
        for x in range(WIDTH):
            for y in range(HEIGHT):
                if (x, y) in ya_asignados:
                    continue
                estado = fire.get(x, y)
                buildDamage = 0
                if estado == 2:
                  for dir in directions:
                    element = building.getDir(x, y, dir)
                    if element in (1, 2, 4): buildDamage += 1
                    candidatos.append(Candidate.Candidate((x, y), "fuego_general", 5 + buildDamage))
                elif estado == 1:
                    candidatos.append(Candidate.Candidate((x, y), "humo_general", 1))

        return candidatos


    def _densidad_fuego(self, fire, x, y, radio=2):
        """
        Nombre: _densidad_fuego
        Descripcion: cuenta cuantas celdas en fuego activo (estado==2)
                     hay dentro de un radio Manhattan `radio` alrededor
                     de (x,y), sin contar la propia celda (x,y). No
                     revisa paredes/puertas -- es una medida de cuanto
                     fuego hay "cerca" en el tablero, no de cuanto es
                     alcanzable, a proposito: lo que nos interesa es
                     detectar zonas ya densas de fuego para reforzarlas
                     con mas agentes, sin importar si el camino directo
                     esta bloqueado.
        Entradas: fire (FireManager), x, y (int), radio (int, default 2)
        Salidas: int -> numero de celdas vecinas en fuego
        Uso: llamado por _apply_density_bonus() una vez por candidato
             de tipo fuego.
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
 
    def _apply_density_bonus(self, candidatos, fire, radio=2, peso=3):
        """
        Nombre: _apply_density_bonus
        Descripcion: sube la prioridad de cada candidato de tipo
                     fuego (FIRE_CANDIDATE_TYPES) segun que tan denso
                     de fuego este su vecindario (_densidad_fuego).
                     Se aplica UNA vez sobre la lista ya combinada de
                     generate_candidates, no dentro de cada scan por
                     separado -- as� "punto_de_brecha" y
                     "romper_cadena" en una zona con cascada de
                     explosiones reciben el mismo refuerzo que
                     "fuego_general" ahi, en vez de competir cada uno
                     solo con su propio merito local. La idea es que
                     al ganar varios candidatos de la misma zona
                     prioridad simultaneamente, el backtracking (que
                     hace matching 1 a 1 candidato-agente) tenga razon
                     para mandar mas de un agente a esa zona en vez de
                     repartirlos parejo por el tablero.
        Entradas: candidatos (list[Candidate]), fire (FireManager),
                  radio (int, default 2), peso (float, default 3)
        Salidas: list[Candidate] -> los mismos objetos, prioridad
                 modificada in-place
        Uso: llamado por generate_candidates() justo antes de
             regresar la lista combinada.
        """
        for c in candidatos:
            if c.tipo in FIRE_CANDIDATE_TYPES:
                densidad = self._densidad_fuego(fire, c.pos[0], c.pos[1], radio)
                c.prioridad += densidad * peso
        return candidatos


    def _deduplicar_candidatos(self, candidatos):
        """
        Nombre: _deduplicar_candidatos
        Descripcion: cuando dos o mas scan_* generan un candidato en
                     la MISMA celda (una celda de fuego facilmente
                     califica a la vez como "fuego_general",
                     "romper_cadena" y "frontera_contencion"), se
                     queda solo con el de mayor prioridad y descarta
                     los demas. Una celda fisica sigue siendo una
                     sola celda sin importar cuantos scans distintos
                     la detecten -- dejarla duplicada en la lista solo
                     infla C (numero de candidatos) sin agregar
                     informacion real, encareciendo build_cost_matrix
                     (que corre pathfinding por cada candidato) y el
                     arbol de busqueda de backtrack() de forma
                     innecesaria. Es puramente una reduccion de
                     trabajo repetido: no cambia ninguna prioridad, no
                     descarta ninguna celda real, solo colapsa
                     duplicados exactos de posicion.
        Entradas: candidatos (list[Candidate])
        Salidas: list[Candidate] -> como maximo un candidato por
                 posicion (el de mayor prioridad de los que competian
                 ahi)
        Uso: llamado por generate_candidates() como ultimo paso,
             despues de _apply_density_bonus() (el orden no importa
             para la correctitud: candidatos en la misma posicion
             reciben el mismo bono de densidad, asi que el orden
             relativo entre ellos no cambia).
        """
        mejor_por_pos = {}
        for c in candidatos:
            actual = mejor_por_pos.get(c.pos)
            if actual is None or c.prioridad > actual.prioridad:
                mejor_por_pos[c.pos] = c
        return list(mejor_por_pos.values())

    def generate_candidates(self, poi, fire, building, ya_asignados):
        """
        Nombre: generate_candidates
        Descripcion: combina las tres fuentes de candidatos (POI,
                     amenaza de fuego, fuego/humo general) en una
                     sola lista, excluyendo posiciones ya asignadas,
                     aplica el bono de densidad, y colapsa duplicados
                     de posicion a uno solo (el de mayor prioridad)
                     via _deduplicar_candidatos().
        Entradas: poi (PoiManager), fire (FireManager),
                  building (BuildingManager),
                  ya_asignados (set[tuple[int,int]])
        Salidas: list[Candidate]
        Uso: llamado por coordinate_turn() al inicio de cada
             recalculo de asignacion.
        """
        candidatos = (
            self.scan_poi_candidates(poi, ya_asignados)
            + self.scan_breach_points(poi, fire, building, ya_asignados)
            + self.scan_chain_breaks(fire, building, ya_asignados)
            + self.scan_general_fire(fire, building, ya_asignados)
        )
        candidatos = self._apply_density_bonus(candidatos, fire)
        return self._deduplicar_candidatos(candidatos)


    def build_cost_matrix(self, agentes, candidatos, building, fire):
        """
        Nombre: build_cost_matrix
        Descripcion: calcula, para cada par (agente, candidato), el
                     COSTO EFECTIVO de ir hacia ese candidato: la
                     distancia real (via A*) dividida entre la
                     prioridad del candidato. Una prioridad alta
                     reduce el costo efectivo, haciendo que el
                     backtracking prefiera ese candidato aunque este
                     mas lejos que uno de menor prioridad -- asi la
                     prioridad SI participa en la asignacion, no solo
                     la distancia cruda. Si no existe ruta posible,
                     el costo queda como infinito (la poda lo
                     descarta automaticamente, sin importar la
                     prioridad).
        Entradas: agentes (list[Firefighter]), candidatos
                  (list[Candidate]), building (BuildingManager),
                  fire (FireManager)
        Salidas: dict {(agente, candidato): costo efectivo (float)}
        Uso: llamado por coordinate_turn() antes de correr el
             backtracking. Cambiar Candidate.prioridad al declarar
             candidatos (en scan_poi_candidates, scan_fire_threats,
             etc.) altera directamente el resultado de este calculo,
             sin necesidad de tocar backtrack()/_explorar().
        """
        triage = triage_factor(building, fire)
        matriz = {}
        for agente in agentes:
            costs = dijkstra_from(agente.pos, building, fire)
            for candidato in candidatos:
                costo = costs[candidato.pos]
                prioridad = max(candidato.prioridad, 0.01) 
                if candidato.tipo in FIRE_CANDIDATE_TYPES:
                    prioridad *= triage
                matriz[(agente, candidato)] = costo / prioridad
        return matriz

    def _explorar(self, agentes_restantes, candidatos_restantes, matriz, mejor, asignacion_actual, costo_actual):
        """
        Nombre: _explorar
        Descripcion: paso recursivo del backtracking con poda. Ahora
                     es un metodo propio (antes vivia anidado dentro
                     de backtrack, tomando matriz por closure) que
                     recibe TODO explicitamente como parametro,
                     incluyendo matriz -- esto es lo que estaba
                     faltando al considerar sacarla fuera. Prueba
                     cada candidato disponible para el primer agente
                     de la lista, poda ramas cuyo costo acumulado ya
                     supera la mejor solucion completa conocida, y
                     tambien explora la opcion de dejar al agente
                     sin asignar cuando sobran mas agentes que
                     candidatos.
        Entradas: agentes_restantes (list[Firefighter]),
                  candidatos_restantes (list[Candidate]),
                  matriz (dict, tabla de costos -- ahora explicita,
                  no por closure), mejor (dict mutable, compartido
                  entre llamadas recursivas para llevar el mejor
                  resultado encontrado), asignacion_actual (dict,
                  asignacion parcial en construccion), costo_actual
                  (float, costo acumulado de esa asignacion parcial)
        Salidas: ninguna (modifica `mejor` in-place)
        Uso: llamado por backtrack() para iniciar la busqueda, y por
             si misma recursivamente para explorar cada rama.
        """
        if not agentes_restantes or not candidatos_restantes:
            if costo_actual < mejor["costo"]:
                mejor["costo"] = costo_actual
                mejor["asignacion"] = asignacion_actual.copy()
            return

        agente = agentes_restantes[0]
        resto_agentes = agentes_restantes[1:]

        for candidato in candidatos_restantes:
            costo_arista = matriz[(agente, candidato)]
            nuevo_costo = costo_actual + costo_arista

            if nuevo_costo >= mejor["costo"]:
                continue   # PODA

            asignacion_actual[agente] = candidato
            resto_candidatos = [c for c in candidatos_restantes if c != candidato]
            self._explorar(resto_agentes, resto_candidatos, matriz, mejor, asignacion_actual, nuevo_costo)
            del asignacion_actual[agente]

        if len(agentes_restantes) > len(candidatos_restantes):
            self._explorar(resto_agentes, candidatos_restantes, matriz, mejor, asignacion_actual, costo_actual)

    def backtrack(self, agentes, candidatos, matriz):
        """
        Nombre: backtrack
        Descripcion: explora combinaciones de asignacion agente por
                     agente, candidato por candidato (sin repetir
                     candidato entre agentes), podando ramas cuyo
                     costo acumulado ya supera la mejor combinacion
                     completa encontrada hasta el momento. Se detiene
                     al agotar agentes o candidatos, lo que ocurra
                     primero -- los agentes sobrantes quedan sin
                     asignacion de esta capa. Es una funcion PURA:
                     no modifica a ningun agente, solo regresa datos.
        Entradas: agentes (list[Firefighter]), candidatos
                  (list[Candidate]), matriz (dict, salida de
                  build_cost_matrix)
        Salidas: dict {Firefighter: Candidate} -> la mejor asignacion
                 encontrada
        Uso: llamado por coordinate_turn() despues de construir la
             matriz de costo.
        """
        mejor = {"costo": float("inf"), "asignacion": {}}
        self._explorar(agentes, candidatos, matriz, mejor, {}, 0)
        return mejor["asignacion"]

    def apply_assignment(self, asignacion):
        """
        Nombre: apply_assignment
        Descripcion: escribe la asignacion resultante en cada agente
                     (objetivo_actual, tipo_objetivo). Es el UNICO
                     punto de todo el pipeline que modifica a los
                     agentes directamente -- backtrack()/_explorar()
                     son funciones puras que solo devuelven datos,
                     precisamente para poder explorar y descartar
                     ramas sin efectos secundarios reales.
        Entradas: asignacion (dict {Firefighter: Candidate})
        Salidas: ninguna
        Uso: llamado por coordinate_turn() justo despues de backtrack().
        """
        for agente, candidato in asignacion.items():
            agente.objetivo_actual = candidato.pos
            agente.tipo_objetivo = candidato.tipo
            print(f"[Agente {agente.id}] Asignado a {candidato.pos[0]}, {candidato.pos[1]}. Tarea de tipo: {agente.tipo_objetivo}")


    def _liberar_comprometidos(self, agentes):
        """
        Nombre: _liberar_comprometidos
        Descripcion: borra objetivo_actual/tipo_objetivo de TODOS los
                     agentes que no llevan victima y no estan
                     derribados, sin importar que tan avanzados
                     esten en su ruta actual. Esto los regresa al
                     pool de agentes_libres en la MISMA llamada a
                     coordinate_turn, para que el backtracking los
                     considere junto con los que ya estaban libres --
                     una reoptimizacion global, no solo de los pocos
                     agentes sueltos. No toca a quien carga victima
                     (esa es prioridad absoluta e individual, ver
                     Firefighter._act_optimized) ni a quien esta
                     derribado (su objetivo ya se limpio en
                     setKnockdown y se resuelve por separado).
        Entradas: agentes (list[Firefighter])
        Salidas: ninguna
        Uso: llamado por coordinate_turn() SOLO en el flanco de
             subida de triage_factor (False -> True), nunca mientras
             triage se mantiene activo turno tras turno -- liberar en
             cada turno causaria "thrashing": agentes que abandonan
             una tarea casi terminada por otra apenas mejor, una y
             otra vez, sin terminar nunca nada.
        """
        for agente in agentes:
            if agente.knockdown or agente.victim:
                continue
            agente.objetivo_actual = None
            agente.tipo_objetivo = None

    def necesita_recalcular(self, candidatos, agentes_libres, triage_activo):
        """
        Nombre: necesita_recalcular
        Descripcion: compara el conjunto actual de candidatos y de
                     agentes sin objetivo contra el ultimo estado
                     conocido. Solo si alguno cambio vale la pena
                     volver a correr el backtracking completo --
                     evita recalcular cada turno sin necesidad.
        Entradas: candidatos (list[Candidate]), agentes_libres
                  (list[Firefighter]), triage_activo (bool)
        Salidas: bool
        Uso: llamado por coordinate_turn() antes de construir la
             matriz de costo. ANTES esta funcion solo comparaba
             posiciones de candidatos e ids de agentes libres -- un
             cambio de triage_factor (misma celda de fuego, pero
             ahora con el doble de prioridad) podia pasar
             completamente inadvertido si el conjunto de celdas en
             fuego era identico al del turno anterior, dejando el
             recalculo -- y por lo tanto el propio triage -- sin
             efecto real. Ahora triage_activo forma parte de la
             huella comparada.
        """
        actual_candidatos = set(c.pos for c in candidatos)
        actual_libres = set(a.unique_id for a in agentes_libres)

        cambio = (actual_candidatos != self._ultimo_candidatos or
                  actual_libres != self._ultimo_libres or
                  triage_activo != self._triage_previo)

        self._ultimo_candidatos = actual_candidatos
        self._ultimo_libres = actual_libres
        return cambio


    def fill_remaining(self, agentes_sin_asignar, candidatos_restantes):
        """
        Nombre: fill_remaining
        Descripcion: asigna, sin volver a correr backtracking, el
                     candidato mas urgente disponible a cada agente
                     que la asignacion optima dejo sin tarea. Ordena
                     por prioridad primero (mayor prioridad gana), y
                     la distancia solo desempata entre candidatos de
                     la MISMA prioridad. Usa el mismo campo
                     Candidate.prioridad que build_cost_matrix, para
                     que ambos mecanismos respondan de forma
                     consistente a cualquier ajuste de prioridades.
        Entradas: agentes_sin_asignar (list[Firefighter]),
                  candidatos_restantes (list[Candidate])
        Salidas: ninguna
        Uso: llamado por coordinate_turn() justo despues de
             apply_assignment(), como red de seguridad de bajo costo.
        """
        for agente in agentes_sin_asignar:
            if not candidatos_restantes:
                break
            elegido = min(
                candidatos_restantes,
                key=lambda c: (-c.prioridad, manhattan(agente.pos, c.pos))
            )
            agente.objetivo_actual = elegido.pos
            agente.tipo_objetivo = elegido.tipo
            candidatos_restantes.remove(elegido)


    def coordinate_turn(self, agentes, poi, fire, building):
        """
        Nombre: coordinate_turn
        Descripcion: punto de entrada unico del Coordinator para un
                     turno. Identifica agentes libres (sin objetivo o
                     con objetivo ya resuelto), genera candidatos,
                     decide si vale la pena recalcular, y si es asi,
                     corre matriz de costo + backtracking + aplica la
                     asignacion resultante.
        Entradas: agentes (list[Firefighter]), poi (PoiManager),
                  fire (FireManager), building (BuildingManager)
        Salidas: ninguna
        Uso: llamado por GameManager en cada ronda, antes de que los
             agentes ejecuten su act().
        """

        triage_activo = triage_factor(building, fire) > 1.0
        dam_actual = building.buildingDam
        escalo_desde_ultimo_interrupt = dam_actual > self._dam_en_ultimo_interrupt

        if triage_activo and (not self._triage_previo or escalo_desde_ultimo_interrupt):
            # Disparamos en dos casos, no solo el primero:
            #   (a) flanco de subida -- el tablero ACABA de volverse
            #       critico, primera vez en esta racha.
            #   (b) el dano estructural crecio desde la ULTIMA vez que
            #       liberamos -- como en esta implementacion el dano
            #       SOLO ocurre por explosiones (ver _propagate/
            #       shockwave en FireManager), esto equivale a "hubo
            #       una explosion en algun lado desde que reoptimizamos
            #       por ultima vez". Es una senal precisa ligada a un
            #       evento real del tablero, no un umbral que se cruza
            #       una sola vez y despues queda mudo por el resto de
            #       la partida mientras todo sigue empeorando -- que
            #       es exactamente lo que se observo en el log anterior
            #       (una sola liberacion en el turno 2, ninguna mas en
            #       30 turnos con explosiones casi constantes).
            print(f"[Coordinator] Triage/escalada (buildingDam={dam_actual}) -> liberando asignaciones para reoptimizar")
            self._liberar_comprometidos(agentes)
            self._dam_en_ultimo_interrupt = dam_actual

        agentes_libres = [
            a for a in agentes
            if not a.knockdown and not a.victim and a.objetivo_actual is None
        ]

        if not agentes_libres:
            self._triage_previo = triage_activo
            return

        ya_asignados = set(
            a.objetivo_actual for a in agentes
            if a.objetivo_actual is not None and a not in agentes_libres
        )

        candidatos = self.generate_candidates(poi, fire, building, ya_asignados)

        if not self.necesita_recalcular(candidatos, agentes_libres, triage_activo):
            self._triage_previo = triage_activo
            return

        self._triage_previo = triage_activo

        matriz = self.build_cost_matrix(agentes_libres, candidatos, building, fire)
        asignacion = self.backtrack(agentes_libres, candidatos, matriz)
        self.apply_assignment(asignacion)

        sin_asignar = [a for a in agentes_libres if a not in asignacion]
        candidatos_restantes = [c for c in candidatos if c not in asignacion.values()]
        self.fill_remaining(sin_asignar, candidatos_restantes)

    # def coordinate_turn(self, agentes, poi, fire, building):

    #     agentes_disponibles = [
    #         a for a in agentes
    #         if not a.knockdown and not a.victim
    #     ]

    #     if not agentes_disponibles:
    #         return

    #     # Forget every previous assignment
    #     for agente in agentes_disponibles:
    #         agente.objetivo_actual = None
    #         agente.tipo_objetivo = None

    #     candidatos = self.generate_candidates(
    #         poi,
    #         fire,
    #         building,
    #         set()
    #     )

    #     matriz = self.build_cost_matrix(
    #         agentes_disponibles,
    #         candidatos,
    #         building,
    #         fire
    #     )

    #     asignacion = self.backtrack(
    #         agentes_disponibles,
    #         candidatos,
    #         matriz
    #     )

    #     self.apply_assignment(asignacion)

    #     sin_asignar = [
    #         a for a in agentes_disponibles
    #         if a not in asignacion
    #     ]

    #     candidatos_restantes = [
    #         c for c in candidatos
    #         if c not in asignacion.values()
    #     ]

    #     self.fill_remaining(
    #         sin_asignar,
    #         candidatos_restantes
    #     )