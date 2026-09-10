"""
Title: BuildingManager
Author: Rodrigo Hurtado
Description:

Manages the physical structure of the board: the Tile grid
(walls, doors), the accumulated structural damage level, and the
query/modification functions for walls used by the rest of the
system.

Functions:
SETUP
__init__
link

QUERY
get
_is_exterior
getNext
getDir
getCost

MODIFICATION
_setDir
_sync_neighbor
damage
moveDoor

"""

import Tile as Tile

WIDTH, HEIGHT = 10, 8

class BuildingManager:
    """
    Manages the physical structure of the board: the Tile grid
    (walls, doors), the accumulated damage level, and the
    query/modification functions for walls used by the rest of the
    system.
    """

    _OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}

    #------------------------------ SETUP ---------------------------------

    def __init__(self):
        """
        Name: __init__
        Description: Builds the 80 cells of the board (10x8) with
                    their fixed walls/doors, previously validated
                    for coherence between neighbors.
        Inputs: none
        Outputs: none (constructor)
        Usage: instantiated once inside GameManager.__init__.
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
        Name: link
        Description: Injects the necessary cross-references.
        Inputs: fireManager (FireManager), poiManager (PoiManager)
        Outputs: none
        Usage: called once from GameManager.__init__.
        """
        self.fire = fireManager
        self.poi = poiManager

    #------------------------------ QUERY ---------------------------------

    def get(self, x, y):
        """
        Name: get
        Description: Returns the 4 sides of the cell at (x, y).
        Inputs: x, y (int)
        Outputs: list[int] -> [up, down, left, right]
        Usage: called by GameManager.capture_snapshot/_tile_to_dict
            to export the wall state.
        """
        return self.TileGrid[x][y].getTile()

    def _is_exterior(self, x, y):
        """
        Name: _is_exterior
        Description: Checks whether a cell lies on the outer ring of
                    the board (the impassable exterior corridor).
        Inputs: x, y (int)
        Outputs: bool
        Usage: helper used internally by getNext() to block movement
            through the exterior corridor.
        """
        return x == 0 or x == WIDTH - 1 or y == 0 or y == HEIGHT - 1

    def getNext(self, x, y, dir):
        """
        Name: getNext
        Description: Computes the resulting coordinate of moving one
                    cell in the given direction. Returns None if it
                    falls outside the board.
        Inputs: x, y (int), dir (str)
        Outputs: tuple[int,int] or None
        Usage: called extensively by FireManager, Firefighter, and
            any movement/propagation logic.
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
            return None   # cannot walk through the exterior corridor

        return nx, ny

    def getDir(self, x, y, dir):
        """
        Name: getDir
        Description: Queries the value of a specific side of the
                    cell (what lies between this cell and its
                    neighbor).
        Inputs: x, y (int), dir (str)
        Outputs: int (0-5)
        Usage: called extensively by FireManager (propagation) and
            Firefighter (deciding the action before moving).
        """
        return self.TileGrid[x][y].getDir(dir)

    def getCost(self, x, y, dir):
        """
        Name: getCost
        Description: Returns the movement/pathfinding cost of
                    crossing the given side of the cell: 1 for
                    open/door, 2 for closed door, 15 for a 1-life
                    wall, 40 for a 2-life wall, and infinite for an
                    indestructible exterior wall.
        Inputs: x, y (int), dir (str)
        Outputs: int or float("inf")
        Usage: called by auxiliars.edge_cost() as the base cost used
            by A*/Dijkstra.
        """
        element = self.getDir(x, y, dir)
        if element in (0, 3):
            return 1
        elif element == 4:
            return 2
        elif element == 1:
            return 40
        elif element == 2:
            return 80
        else:   # element == 5, indestructible exterior
            return float("inf")

    #------------------------------ MODIFICATION ---------------------------------

    def _setDir(self, x, y, dir, value):
        """
        Name: _setDir
        Description: Overwrites the value of a specific side of the
                    cell, delegating to the correct Tile setter.
        Inputs: x, y (int), dir (str), value (int, 0-5)
        Outputs: none
        Usage: internal helper for damage() and moveDoor().
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
        Name: _sync_neighbor
        Description: Replicates the value of a side onto the
                    corresponding neighbor cell (opposite side),
                    keeping adjacent cells coherent.
        Inputs: x, y (int), dir (str)
        Outputs: none
        Usage: internal helper for damage() and moveDoor(), called
                    after modifying a side.
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
        Name: damage
        Description: Applies one point of damage in the given
                    direction. A 2-life wall becomes 1-life; a
                    1-life wall or a closed door is destroyed (0).
                    Syncs the change with the neighboring cell and
                    accumulates buildingDam.
        Inputs: x, y (int), dir (str)
        Outputs: bool -> True if damage was applied, False if the
                side was not damageable (empty, open door, or
                exterior)
        Usage: called by Firefighter.chop() and by
            FireManager._propagate() during explosions.
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
        Name: moveDoor
        Description: Toggles a door's state between open (3) and
                    closed (4). Syncs the change with the
                    neighboring cell.
        Inputs: x, y (int), dir (str)
        Outputs: bool -> True if there was a door there, False if not
        Usage: called by Firefighter.openDoor().
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