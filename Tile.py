class Tile:
    """
    Representa una celda del tablero: sus 4 paredes/puertas en las
    direcciones up/down/left/right, codificadas segun la leyenda BUILD:
    0=libre, 1=pared 1 vida, 2=pared 2 vidas, 3=puerta abierta,
    4=puerta cerrada, 5=pared exterior indestructible.
    Instanciada 80 veces dentro de BuildingManager.TileGrid.
    """

    def __init__(self, up, down, left, right):
        """
        Nombre: __init__
        Descripcion: crea un Tile con sus 4 lados ya definidos.
        Entradas: up, down, left, right (int, valores 0-5)
        Salidas: ninguna (constructor)
        Uso: llamado por BuildingManager.__init__ una vez por cada
             una de las 80 posiciones del tablero.
        """
        self.up = up
        self.down = down
        self.left = left
        self.right = right

    def getTile(self):
        """
        Nombre: getTile
        Descripcion: regresa los 4 lados de la celda en orden fijo.
        Entradas: ninguna
        Salidas: list[int] -> [up, down, left, right]
        Uso: llamado por BuildingManager.get(x,y) y por
             GameManager._tile_to_dict / capture_snapshot para
             exportar el estado de paredes.
        """
        return [self.up, self.down, self.left, self.right]

    def getDir(self, dir):
        """
        Nombre: getDir
        Descripcion: regresa el valor de un lado especifico de la celda.
        Entradas: dir (str) -> "up" | "down" | "left" | "right"
        Salidas: int (0-5), el valor de ese lado
        Uso: llamado por BuildingManager.getDir(x,y,dir), que a su vez
             es usado por FireManager (propagacion) y Firefighter
             (decidir la accion antes de avanzar).
        """
        directions = {
            "up": self.up,
            "down": self.down,
            "left": self.left,
            "right": self.right
        }
        return directions[dir]

    def setUp(self, up):
        """
        Nombre: setUp
        Descripcion: sobreescribe el valor del lado superior.
        Entradas: up (int, 0-5)
        Salidas: ninguna
        Uso: llamado por BuildingManager._setDir cuando dir=="up"
             (danio de pared o cambio de estado de puerta).
        """
        self.up = up

    def setDown(self, down):
        """
        Nombre: setDown
        Descripcion: sobreescribe el valor del lado inferior.
        Entradas: down (int, 0-5)
        Salidas: ninguna
        Uso: llamado por BuildingManager._setDir cuando dir=="down".
        """
        self.down = down

    def setLeft(self, left):
        """
        Nombre: setLeft
        Descripcion: sobreescribe el valor del lado izquierdo.
        Entradas: left (int, 0-5)
        Salidas: ninguna
        Uso: llamado por BuildingManager._setDir cuando dir=="left".
        """
        self.left = left

    def setRight(self, right):
        """
        Nombre: setRight
        Descripcion: sobreescribe el valor del lado derecho.
        Entradas: right (int, 0-5)
        Salidas: ninguna
        Uso: llamado por BuildingManager._setDir cuando dir=="right".
        """
        self.right = right

    def setAll(self, up, down, left, right):
        """
        Nombre: setAll
        Descripcion: sobreescribe los 4 lados de la celda a la vez.
        Entradas: up, down, left, right (int, 0-5)
        Salidas: ninguna
        Uso: utilitario para inicializacion manual de tableros
             (no usado en el flujo automatico actual).
        """
        self.up = up
        self.down = down
        self.left = left
        self.right = right