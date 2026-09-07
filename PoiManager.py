import numpy as np
import Dice

WIDTH, HEIGHT = 10, 8

from types import NoneType
class PoiManager:
    """
    Administra los puntos de interes (POI) del tablero: su grid
    (POIGrid, valores 0=nada, 1=sin revelar, 2=falsa alarma,
    3=victima), los contadores de victimas salvadas/perdidas, y la
    lista publica de POIs sin revelar (self.pois) que el
    comportamiento de los agentes consulta directamente.
    """

    def __init__(self):
        """
        Nombre: __init__
        Descripcion: crea el grid de POIs en ceros e inserta los 3
                     POIs iniciales de la partida en sus posiciones
                     fijas.
        Entradas: ninguna
        Salidas: ninguna (constructor)
        Uso: instanciado una vez dentro de GameManager.__init__.
        """
        self.POIGrid = np.zeros((WIDTH, HEIGHT), dtype=np.int8)
        self.dice = Dice.Dice()
        self.savedVictims = 0
        self.lostVictims = 0
        self.quantity = 0
        self.building = None
        self.fire = None
        self.agents = None
        self.pois = []

        poi_positions = [(1,5), (4,2), (8,5)]
        for x, y in poi_positions:
            self.initialInsert(x, y)

    def link(self, buildManager, fireManager, agents):
        """
        Nombre: link
        Descripcion: inyecta las referencias cruzadas necesarias.
        Entradas: buildManager (BuildingManager), fireManager
                  (FireManager), agents (list[Firefighter])
        Salidas: ninguna
        Uso: llamado una vez desde GameManager.__init__.
        """
        self.building = buildManager
        self.fire = fireManager
        self.agents = agents

    def get(self, x, y):
        """
        Nombre: get
        Descripcion: consulta el estado de POI en una celda.
        Entradas: x, y (int)
        Salidas: int -> 0 (nada), 1 (sin revelar), 2 (falsa alarma
                 transitoria), 3 (victima transitoria)
        Uso: llamado por FireManager.turnToFire (verificar si hay
             algo que destruir) y por Firefighter/GameManager para
             consultar el tablero.
        """
        return self.POIGrid[x, y]

    def destroy(self, x, y):
        """
        Nombre: destroy
        Descripcion: elimina un POI de la celda por causa de fuego.
                     Si ya era una victima confirmada, cuenta como
                     victima perdida.
        Entradas: x, y (int)
        Salidas: ninguna
        Uso: llamado por FireManager.turnToFire cuando el fuego
             alcanza una celda que tenia un POI.
        """
        if self.get(x, y) == 3:
            print(f"Victim was lost at {x}, {y}")
            self.lostVictims += 1
        else:
            print(f"POI at {x}, {y} was destroyed")
        self.POIGrid[x, y] = 0
        self.quantity -= 1
        if (x, y) in self.pois:
            self.pois.remove((x, y))

    def destroyVictim(self):
        """
        Nombre: destroyVictim
        Descripcion: cuenta como perdida una victima que un bombero
                     ya cargaba, al caer el bombero (knockdown).
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado por Firefighter.setKnockdown() cuando el agente
             cae mientras cargaba una victima.
        """
        self.quantity -= 1
        self.lostVictims += 1

    def set(self):
        """
        Nombre: set
        Descripcion: repone POIs hasta llegar a 3 activos, roleando
                     posiciones vacias. Si el POI nuevo cae sobre
                     fuego, lo apaga; si cae sobre un agente, revela
                     el POI de inmediato.
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado una vez por cada turno completo de agente,
             desde GameManager.step_agent().
        """
        while self.quantity < 3:
            x, y = self.dice.roll()
            while self.get(x, y) != 0:
                x, y = self.dice.roll()

            self.insert(x, y)

            if self.fire.get(x, y) == 2:
                self.fire.turnOff(x, y)

            for agent in self.agents:
                if agent.pos[0] == x and agent.pos[1] == y:
                    self.turnOver(x, y)
                    break

    def initialInsert(self, x, y):
        """
        Nombre: initialInsert
        Descripcion: coloca un POI sin revelar en una celda vacia y
                     lo agrega a la lista publica self.pois.
        Entradas: x, y (int)
        Salidas: ninguna
        Uso: llamado por __init__ (POIs iniciales) y por set()
             (reposicion durante la partida).
        """
        print(f"POI inserted at {x}, {y}")
        self.POIGrid[x, y] = 1
        self.quantity += 1
        self.pois.append((x, y))

    def insert(self, x, y):
        """
        Nombre: insert
        Descripcion: coloca un POI sin revelar en una celda vacia y
                     lo agrega a la lista publica self.pois.Posteriormente,
                     recorre la lista de agentes disponibles para comprobar
                     si debe hacer turnOver de alguno.
        Entradas: x, y (int)
        Salidas: ninguna
        Uso: llamado por __init__ (POIs iniciales) y por set()
             (reposicion durante la partida).
        """
        print(f"POI inserted at {x}, {y}")
        self.POIGrid[x, y] = 1
        self.quantity += 1
        self.pois.append((x, y))

        for agent in self.agents:
                if agent.pos[0] == x and agent.pos[1] == y:
                    self.turnOver(x, y)
                    break


    def turnOver(self, x, y):
        """
        Nombre: turnOver
        Descripcion: revela un POI sin revelar: rolea si es falsa
                     alarma o victima. Si hay un agente en esa celda,
                     resuelve de inmediato (asigna la victima al
                     agente, o destruye la falsa alarma).
        Entradas: x, y (int)
        Salidas: ninguna
        Uso: llamado por set() (POI nuevo cae sobre un agente) y por
             Firefighter._act_primitive() al llegar a un POI sin
             revelar.
        """
        print("POI Turned Over")
        rand = np.random.randint(2, 4)
        self.POIGrid[x, y] = rand

        for agent in self.agents:
            if agent.pos[0] == x and agent.pos[1] == y:
                if rand == 3:
                    print(f"POI at {agent.pos[0]}, {agent.pos[1]} is Victim")
                    agent.assignVictim()
                    print(f"Victim at {agent.pos[0]}, {agent.pos[1]} assigned")
                    self.POIGrid[x, y] = 0
                    if (x, y) in self.pois:
                        self.pois.remove((x, y))
                else:
                    print(f"POI at {agent.pos[0]}, {agent.pos[1]} is Alarm")
                    self.POIGrid[x, y] = 0
                    self.quantity -= 1
                    if (x, y) in self.pois:
                        self.pois.remove((x, y))
                return

    def getVictimsSaved(self):
        """
        Nombre: getVictimsSaved
        Descripcion: consulta el contador de victimas salvadas.
        Entradas: ninguna
        Salidas: int
        Uso: llamado por GameManager.win() y por reportes/snapshots.
        """
        return self.savedVictims

    def getVictimsLost(self):
        """
        Nombre: getVictimsLost
        Descripcion: consulta el contador de victimas perdidas.
        Entradas: ninguna
        Salidas: int
        Uso: llamado por GameManager.lose() y por reportes/snapshots.
        """
        return self.lostVictims

    def saveVictim(self):
        """
        Nombre: saveVictim
        Descripcion: registra que una victima fue salvada exitosamente
                     (bombero llego con ella a una salida).
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado por Firefighter._act_primitive() al llegar a
             una salida cargando una victima.
        """
        print(f"Saved victim")
        self.savedVictims += 1
        self.quantity -= 1