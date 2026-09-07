import Tile

WIDTH, HEIGHT = 10, 8

class BuildingManager:
    """
    Administra la estructura fisica del tablero: el grid de Tiles
    (paredes, puertas), el nivel de daño acumulado, y las funciones
    de consulta/modificacion de paredes usadas por el resto del
    sistema.
    """

    _OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}

    def __init__(self):
        """
        Nombre: __init__
        Descripcion: construye las 80 celdas del tablero (10x8) con
                     sus paredes/puertas fijas, validadas previamente
                     por coherencia entre vecinos.
        Entradas: ninguna
        Salidas: ninguna (constructor)
        Uso: instanciado una vez dentro de GameManager.__init__.
        """
        self.TileGrid = [[None for _ in range(HEIGHT)] for _ in range(WIDTH)]

        self.TileGrid[0][0] = Tile.Tile(up=5, down=0, left=5, right=0)
        self.TileGrid[0][1] = Tile.Tile(up=0, down=0, left=5, right=2)
        self.TileGrid[0][2] = Tile.Tile(up=0, down=0, left=5, right=2)
        self.TileGrid[0][3] = Tile.Tile(up=0, down=0, left=5, right=3)
        self.TileGrid[0][4] = Tile.Tile(up=0, down=0, left=5, right=2)
        self.TileGrid[0][5] = Tile.Tile(up=0, down=0, left=5, right=2)
        self.TileGrid[0][6] = Tile.Tile(up=0, down=0, left=5, right=2)
        self.TileGrid[0][7] = Tile.Tile(up=0, down=5, left=5, right=0)
        self.TileGrid[1][0] = Tile.Tile(up=5, down=2, left=0, right=0)
        self.TileGrid[1][1] = Tile.Tile(up=2, down=0, left=2, right=0)
        self.TileGrid[1][2] = Tile.Tile(up=0, down=0, left=2, right=0)
        self.TileGrid[1][3] = Tile.Tile(up=0, down=0, left=3, right=0)
        self.TileGrid[1][4] = Tile.Tile(up=0, down=2, left=2, right=0)
        self.TileGrid[1][5] = Tile.Tile(up=2, down=0, left=2, right=0)
        self.TileGrid[1][6] = Tile.Tile(up=0, down=2, left=2, right=0)
        self.TileGrid[1][7] = Tile.Tile(up=2, down=5, left=0, right=0)
        self.TileGrid[2][0] = Tile.Tile(up=5, down=2, left=0, right=0)
        self.TileGrid[2][1] = Tile.Tile(up=2, down=0, left=0, right=0)
        self.TileGrid[2][2] = Tile.Tile(up=0, down=0, left=0, right=0)
        self.TileGrid[2][3] = Tile.Tile(up=0, down=0, left=0, right=4)
        self.TileGrid[2][4] = Tile.Tile(up=0, down=2, left=0, right=2)
        self.TileGrid[2][5] = Tile.Tile(up=2, down=0, left=0, right=0)
        self.TileGrid[2][6] = Tile.Tile(up=0, down=2, left=0, right=0)
        self.TileGrid[2][7] = Tile.Tile(up=2, down=5, left=0, right=0)
        self.TileGrid[3][0] = Tile.Tile(up=5, down=2, left=0, right=0)
        self.TileGrid[3][1] = Tile.Tile(up=2, down=0, left=0, right=4)
        self.TileGrid[3][2] = Tile.Tile(up=0, down=2, left=0, right=2)
        self.TileGrid[3][3] = Tile.Tile(up=2, down=0, left=4, right=0)
        self.TileGrid[3][4] = Tile.Tile(up=0, down=2, left=2, right=0)
        self.TileGrid[3][5] = Tile.Tile(up=2, down=0, left=0, right=0)
        self.TileGrid[3][6] = Tile.Tile(up=0, down=3, left=0, right=0)
        self.TileGrid[3][7] = Tile.Tile(up=3, down=5, left=0, right=0)
        self.TileGrid[4][0] = Tile.Tile(up=5, down=2, left=0, right=0)
        self.TileGrid[4][1] = Tile.Tile(up=2, down=0, left=4, right=0)
        self.TileGrid[4][2] = Tile.Tile(up=0, down=2, left=2, right=0)
        self.TileGrid[4][3] = Tile.Tile(up=2, down=0, left=0, right=0)
        self.TileGrid[4][4] = Tile.Tile(up=0, down=4, left=0, right=0)
        self.TileGrid[4][5] = Tile.Tile(up=4, down=0, left=0, right=0)
        self.TileGrid[4][6] = Tile.Tile(up=0, down=2, left=0, right=0)
        self.TileGrid[4][7] = Tile.Tile(up=2, down=5, left=0, right=0)
        self.TileGrid[5][0] = Tile.Tile(up=5, down=2, left=0, right=0)
        self.TileGrid[5][1] = Tile.Tile(up=2, down=0, left=0, right=2)
        self.TileGrid[5][2] = Tile.Tile(up=0, down=2, left=0, right=4)
        self.TileGrid[5][3] = Tile.Tile(up=2, down=0, left=0, right=0)
        self.TileGrid[5][4] = Tile.Tile(up=0, down=2, left=0, right=0)
        self.TileGrid[5][5] = Tile.Tile(up=2, down=0, left=0, right=2)
        self.TileGrid[5][6] = Tile.Tile(up=0, down=2, left=0, right=4)
        self.TileGrid[5][7] = Tile.Tile(up=2, down=5, left=0, right=0)
        self.TileGrid[6][0] = Tile.Tile(up=5, down=3, left=0, right=0)
        self.TileGrid[6][1] = Tile.Tile(up=3, down=0, left=2, right=0)
        self.TileGrid[6][2] = Tile.Tile(up=0, down=2, left=4, right=0)
        self.TileGrid[6][3] = Tile.Tile(up=2, down=0, left=0, right=2)
        self.TileGrid[6][4] = Tile.Tile(up=0, down=2, left=0, right=4)
        self.TileGrid[6][5] = Tile.Tile(up=2, down=0, left=2, right=0)
        self.TileGrid[6][6] = Tile.Tile(up=0, down=2, left=4, right=0)
        self.TileGrid[6][7] = Tile.Tile(up=2, down=5, left=0, right=0)
        self.TileGrid[7][0] = Tile.Tile(up=5, down=2, left=0, right=0)
        self.TileGrid[7][1] = Tile.Tile(up=2, down=0, left=0, right=0)
        self.TileGrid[7][2] = Tile.Tile(up=0, down=2, left=0, right=0)
        self.TileGrid[7][3] = Tile.Tile(up=2, down=0, left=2, right=0)
        self.TileGrid[7][4] = Tile.Tile(up=0, down=2, left=4, right=0)
        self.TileGrid[7][5] = Tile.Tile(up=2, down=0, left=0, right=2)
        self.TileGrid[7][6] = Tile.Tile(up=0, down=2, left=0, right=4)
        self.TileGrid[7][7] = Tile.Tile(up=2, down=5, left=0, right=0)
        self.TileGrid[8][0] = Tile.Tile(up=5, down=2, left=0, right=0)
        self.TileGrid[8][1] = Tile.Tile(up=2, down=0, left=0, right=2)
        self.TileGrid[8][2] = Tile.Tile(up=0, down=4, left=0, right=2)
        self.TileGrid[8][3] = Tile.Tile(up=4, down=0, left=0, right=2)
        self.TileGrid[8][4] = Tile.Tile(up=0, down=2, left=0, right=3)
        self.TileGrid[8][5] = Tile.Tile(up=2, down=0, left=2, right=2)
        self.TileGrid[8][6] = Tile.Tile(up=0, down=2, left=4, right=2)
        self.TileGrid[8][7] = Tile.Tile(up=2, down=5, left=0, right=0)
        self.TileGrid[9][0] = Tile.Tile(up=5, down=0, left=0, right=5)
        self.TileGrid[9][1] = Tile.Tile(up=0, down=0, left=2, right=5)
        self.TileGrid[9][2] = Tile.Tile(up=0, down=0, left=2, right=5)
        self.TileGrid[9][3] = Tile.Tile(up=0, down=0, left=2, right=5)
        self.TileGrid[9][4] = Tile.Tile(up=0, down=0, left=3, right=5)
        self.TileGrid[9][5] = Tile.Tile(up=0, down=0, left=2, right=5)
        self.TileGrid[9][6] = Tile.Tile(up=0, down=0, left=2, right=5)
        self.TileGrid[9][7] = Tile.Tile(up=0, down=5, left=0, right=5)

        self.buildingDam = 0
        self.fire = None
        self.poi = None
    def link(self, fireManager, poiManager):
        """
        Nombre: link
        Descripcion: inyecta las referencias cruzadas necesarias.
        Entradas: fireManager (FireManager), poiManager (PoiManager)
        Salidas: ninguna
        Uso: llamado una vez desde GameManager.__init__.
        """
        self.fire = fireManager
        self.poi = poiManager

    def get(self, x, y):
        """
        Nombre: get
        Descripcion: regresa los 4 lados de la celda en (x,y).
        Entradas: x, y (int)
        Salidas: list[int] -> [up, down, left, right]
        Uso: llamado por GameManager.capture_snapshot/_tile_to_dict
             para exportar el estado de paredes.
        """
        return self.TileGrid[x][y].getTile()

    def _is_exterior(self, x, y):
        return x == 0 or x == WIDTH - 1 or y == 0 or y == HEIGHT - 1

    def getNext(self, x, y, dir):
        """
        Nombre: getNext
        Descripcion: calcula la coordenada resultante de moverse una
                     celda en la direccion dada. Regresa None si cae
                     fuera del tablero.
        Entradas: x, y (int), dir (str)
        Salidas: tuple[int,int] o None
        Uso: llamado extensamente por FireManager, Firefighter y
             cualquier logica de movimiento/propagacion.
        """
        if dir == "up":
            nx, ny = x, y - 1
        elif dir == "down":
            nx, ny = x, y + 1
        elif dir == "left":
            nx, ny = x - 1, y
        elif dir == "right":
            nx, ny = x + 1, y

        if not (0 <= nx < WIDTH and 0 <= ny < HEIGHT):
            return None

        if self._is_exterior(x, y) and self._is_exterior(nx, ny):
            return None   # no se puede caminar por el pasillo exterior

        return nx, ny

    def getDir(self, x, y, dir):
        """
        Nombre: getDir
        Descripcion: consulta el valor de un lado especifico de la
                     celda (que hay entre esta celda y su vecina).
        Entradas: x, y (int), dir (str)
        Salidas: int (0-5)
        Uso: llamado extensamente por FireManager (propagacion) y
             Firefighter (decidir la accion antes de moverse).
        """
        return self.TileGrid[x][y].getDir(dir)

    def _setDir(self, x, y, dir, value):
        """
        Nombre: _setDir
        Descripcion: sobreescribe el valor de un lado especifico de
                     la celda, delegando al setter correcto de Tile.
        Entradas: x, y (int), dir (str), value (int, 0-5)
        Salidas: ninguna
        Uso: helper interno de damage() y moveDoor().
        """
        tile = self.TileGrid[x][y]
        if dir == "up":
            tile.setUp(value)
        elif dir == "down":
            tile.setDown(value)
        elif dir == "left":
            tile.setLeft(value)
        elif dir == "right":
            tile.setRight(value)

    def _sync_neighbor(self, x, y, dir):
        """
        Nombre: _sync_neighbor
        Descripcion: replica el valor de un lado en la celda vecina
                     correspondiente (lado opuesto), manteniendo la
                     coherencia entre celdas adyacentes.
        Entradas: x, y (int), dir (str)
        Salidas: ninguna
        Uso: helper interno de damage() y moveDoor(), llamado despues
             de modificar un lado.
        """
        next_pos = self.getNext(x, y, dir)
        if next_pos is None:
            return
        nx, ny = next_pos
        opp = self._OPPOSITE[dir]
        value = self.getDir(x, y, dir)
        self._setDir(nx, ny, opp, value)

    def damage(self, x, y, dir) -> bool:
        """
        Nombre: damage
        Descripcion: aplica un punto de daño en la direccion dada.
                     Pared de 2 vidas -> 1 vida; pared de 1 vida o
                     puerta cerrada -> destruida (0). Sincroniza el
                     cambio con la celda vecina y acumula buildingDam.
        Entradas: x, y (int), dir (str)
        Salidas: bool -> True si se aplico daño, False si el lado no
                 era daniable (vacio, puerta abierta, o exterior)
        Uso: llamado por Firefighter.chop() y por
             FireManager._propagate() durante explosiones.
        """
        element = self.getDir(x, y, dir)

        if element == 2:
            self._setDir(x, y, dir, 1)
        elif element == 1:
            self._setDir(x, y, dir, 0)
        elif element == 4:
            self._setDir(x, y, dir, 0)
        else:
            return False

        self.buildingDam += 1
        self._sync_neighbor(x, y, dir)
        return True

    def moveDoor(self, x, y, dir) -> bool:
        """
        Nombre: moveDoor
        Descripcion: alterna el estado de una puerta entre abierta
                     (3) y cerrada (4). Sincroniza el cambio con la
                     celda vecina.
        Entradas: x, y (int), dir (str)
        Salidas: bool -> True si habia una puerta ahi, False si no
        Uso: llamado por Firefighter.openDoor().
        """
        element = self.getDir(x, y, dir)
        if element == 3:
            self._setDir(x, y, dir, 4)
        elif element == 4:
            self._setDir(x, y, dir, 3)
        else:
            return False
        self._sync_neighbor(x, y, dir)
        return True

    def getCost(self, x, y, dir):
        element = self.getDir(x, y, dir)
        if element in (0, 3):
            return 1
        elif element == 4:
            return 2
        elif element == 1:
            return 15
        elif element == 2:
            return 40
        else:   # element == 5, exterior indestructible
            return float("inf")