import numpy as np
import Dice

WIDTH, HEIGHT = 10, 8

class FireManager:
    """
    Administra el estado de fuego/humo del tablero (fireGrid).
    Valores por celda: 0=vacio, 1=humo, 2=fuego.
    Depende de BuildingManager (paredes/puertas) y PoiManager
    (para saber si un POI debe destruirse al incendiarse su celda),
    ademas de la lista de agentes (para aplicar knockdown).
    """

    def __init__(self):
        """
        Nombre: __init__
        Descripcion: crea el grid de fuego en ceros y coloca el fuego
                     inicial de la partida en las posiciones fijas
                     acordadas para este mapa.
        Entradas: ninguna
        Salidas: ninguna (constructor)
        Uso: instanciado una vez dentro de GameManager.__init__.
        """
        self.fireGrid = np.zeros((WIDTH, HEIGHT), dtype=np.int8)
        fire_positions = [
            (2,2), (3,2), (2,3), (3,3), (4,3),
            (5,3), (4,4), (6,5), (7,5), (6,6)
        ]
        for x, y in fire_positions:
            self.fireGrid[x, y] = 2

        self.dice = Dice.Dice()
        self.building = None
        self.poi = None
        self.agents = None

    def link(self, buildingManager, poiManager, agents):
        """
        Nombre: link
        Descripcion: inyecta las referencias cruzadas necesarias para
                     operar (patron de dos fases, evita dependencia
                     circular en el constructor).
        Entradas: buildingManager (BuildingManager), poiManager
                  (PoiManager), agents (list[Firefighter])
        Salidas: ninguna
        Uso: llamado una vez desde GameManager.__init__, justo
             despues de instanciar los tres managers.
        """
        self.building = buildingManager
        self.poi = poiManager
        self.agents = agents

    def get(self, x, y):
        """
        Nombre: get
        Descripcion: consulta que hay en una celda del grid de fuego.
        Entradas: x, y (int)
        Salidas: int -> 0 (vacio), 1 (humo), 2 (fuego)
        Uso: llamado extensamente por Firefighter (decidir accion),
             PoiManager.set() (verificar si limpiar fuego al insertar
             POI), y por este mismo manager en su logica interna.
        """
        return self.fireGrid[x, y]

    def putSmoke(self):
        """
        Nombre: putSmoke
        Descripcion: rolea el dado propio y aplica la regla de
                     avance de fuego sobre la celda resultante:
                     vacia+fuego adyacente->fuego, vacia sin fuego
                     cerca->humo, humo->fuego, fuego->explosion.
        Entradas: ninguna
        Salidas: ninguna
        Uso: llamado una vez por cada turno completo de agente,
             desde GameManager.step_agent().
        """
        x_, y_ = self.dice.roll()
        print(f"Put smoke at {x_}, {y_}")
        fire = self.get(x_, y_)

        if fire == 0:
            tuplas = self.getNeighborhoodFire(x_, y_)
            if tuplas:
                self.turnToFire(x_, y_)
                print(f"Turned to fire at {x_}, {y_}")
            else:
                self.turnToSmoke(x_, y_)

        elif fire == 1:
            self.turnToFire(x_, y_)
            print(f"Turned to fire at {x_}, {y_}")
        elif fire == 2:
            self.explotion(x_, y_)
            print(f"Explotion erupted at {x_}, {y_}")

    def turnToFire(self, x, y):
        """
        Nombre: turnToFire
        Descripcion: convierte una celda en fuego. Aplica knockdown a
                     cualquier agente parado ahi, y destruye cualquier
                     POI presente en esa celda.
        Entradas: x, y (int)
        Salidas: ninguna
        Uso: llamado por putSmoke(), _propagate() y shockwave() como
             consecuencia de propagacion de fuego.
        """
        for agent in self.agents:
            if agent.pos[0] == x and agent.pos[1] == y:
                agent.setKnockdown(True)

        if self.poi.get(x, y) > 0:
            self.poi.destroy(x, y)

        self.fireGrid[x, y] = 2

    def turnToSmoke(self, x, y):
        """
        Nombre: turnToSmoke
        Descripcion: marca una celda como humo.
        Entradas: x, y (int)
        Salidas: ninguna
        Uso: llamado por putSmoke() cuando una celda vacia no tiene
             fuego adyacente; y por Firefighter.turnFireToSmoke()
             como efecto de la accion del bombero.
        """
        self.fireGrid[x, y] = 1

    def turnOff(self, x, y):
        """
        Nombre: turnOff
        Descripcion: limpia una celda (fuego o humo) dejandola vacia.
        Entradas: x, y (int)
        Salidas: ninguna
        Uso: llamado por PoiManager.set() al insertar un POI sobre
             fuego, y por Firefighter.turnFireToNothing() /
             turnSmokeToNothing() como efecto de la accion del bombero.
        """
        self.fireGrid[x, y] = 0

    def getNeighborhoodFire(self, x, y):
        """
        Nombre: getNeighborhoodFire
        Descripcion: revisa las 4 direcciones alrededor de una celda
                     y regresa las posiciones vecinas que tienen fuego,
                     respetando paredes/puertas cerradas de por medio.
        Entradas: x, y (int)
        Salidas: list[tuple[int,int]] -> posiciones vecinas con fuego
        Uso: llamado por putSmoke() para decidir si una celda vacia
             debe convertirse en fuego (si hay fuego adyacente) o
             en humo (si no lo hay).
        """
        directions = ["up", "down", "left", "right"]
        tuplas = []

        for dir in directions:
            element = self.building.getDir(x, y, dir)
            if element == 0 or element == 3:
                next_pos = self.building.getNext(x, y, dir)
                if next_pos is not None:
                    x_, y_ = next_pos
                    fire = self.get(x_, y_)
                    if fire == 2:
                        tuplas.append((x_, y_))

        return tuplas

    def _propagate(self, x, y, dir):
        """
        Nombre: _propagate
        Descripcion: aplica el efecto de una explosion/onda de choque
                     en UNA direccion: si el camino esta libre y la
                     celda siguiente no tiene fuego, la incendia (o
                     dispara una shockwave si ya tenia fuego); si hay
                     pared/puerta en el camino, la daña.
        Entradas: x, y (int), dir (str)
        Salidas: ninguna
        Uso: llamado por explotion() (una vez por cada una de las 4
             direcciones) y por shockwave() (al llegar al final de
             la cadena de fuego).
        """
        element = self.building.getDir(x, y, dir)

        if element in (0, 3):
            next_pos = self.building.getNext(x, y, dir)
            if next_pos is not None:
                new_x, new_y = next_pos
                fire = self.get(new_x, new_y)
                if fire == 0 or fire == 1:
                    self.turnToFire(new_x, new_y)
                    print(f"Turn to fire at {new_x}, {new_y}")
                elif fire == 2:
                    self.shockwave(new_x, new_y, dir)
                    print(f"Started shockwave at {new_x}, {new_y} in direction {dir}")

        if element in (1, 2, 3, 4):
            self.building.damage(x, y, dir)
            print(f"Damage at {x}, {y} by fire")

    def explotion(self, x, y):
        """
        Nombre: explotion
        Descripcion: aplica una explosion completa (las 4 direcciones)
                     sobre una celda que ya tenia fuego.
        Entradas: x, y (int)
        Salidas: ninguna
        Uso: llamado por putSmoke() cuando el dado cae sobre una
             celda que ya estaba en fuego.
        """
        directions = ["right", "left", "up", "down"]
        for dir in directions:
            self._propagate(x, y, dir)

    def shockwave(self, x, y, dir):
        """
        Nombre: shockwave
        Descripcion: avanza en una direccion mientras el camino este
                     libre/puerta abierta y la siguiente celda tenga
                     fuego, hasta llegar a la ultima celda en llamas
                     de esa cadena, y ahi aplica _propagate.
        Entradas: x, y (int), dir (str)
        Salidas: ninguna
        Uso: llamado por _propagate() cuando una explosion choca con
             una celda que ya tenia fuego (efecto domino).
        """
        while True:
            next_pos = self.building.getNext(x, y, dir)
            if next_pos is None:
                break

            element = self.building.getDir(x, y, dir)
            if element not in (0, 3):
                break

            x_, y_ = next_pos
            if self.get(x_, y_) != 2:
                break

            x, y = x_, y_

        self._propagate(x, y, dir)