import random

class Dice:
    """
    Generador de coordenadas aleatorias dentro del interior jugable
    del tablero (x: 1-8, y: 1-6). Usado por FireManager y PoiManager
    para decidir donde cae fuego nuevo o donde aparece un POI nuevo.
    """

    def __init__(self):
        """
        Nombre: __init__
        Descripcion: inicializa el dado sin ningun valor rodado aun.
        Entradas: ninguna
        Salidas: ninguna (constructor)
        Uso: instanciado una vez dentro de FireManager.__init__ y
             una vez dentro de PoiManager.__init__ (cada manager
             tiene su propio dado independiente).
        """
        self.x = 0
        self.y = 0

    def roll(self):
        """
        Nombre: roll
        Descripcion: genera un par de coordenadas aleatorias, x entre
                     1 y 8 inclusive, y entre 1 y 6 inclusive (coincide
                     con el interior jugable del tablero 10x8).
        Entradas: ninguna
        Salidas: tuple[int, int] -> (x, y)
        Uso: llamado por FireManager.putSmoke() para elegir donde cae
             fuego/humo, y por PoiManager.set() para elegir donde
             aparece un nuevo POI.
        """
        self.x = random.randint(1, 8)
        self.y = random.randint(1, 6)
        return self.x, self.y