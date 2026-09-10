"""
Title: Tile
Author: Rodrigo Hurtado
Description:

Represents a board cell: its 4 walls/doors in the up/down/left/right
directions, encoded according to the BUILD legend: 0=free,
1=1-life wall, 2=2-life wall, 3=open door, 4=closed door, 5=
indestructible exterior wall. Instantiated 80 times inside
BuildingManager.TileGrid.

Functions:
CONSTRUCTOR
__init__

QUERY
getTile
getDir

MODIFICATION
setUp
setDown
setLeft
setRight
setAll

"""

class Tile:
    """
    Represents a board cell: its 4 walls/doors in the
    up/down/left/right directions, encoded according to the BUILD
    legend: 0=free, 1=1-life wall, 2=2-life wall, 3=open door,
    4=closed door, 5=indestructible exterior wall. Instantiated 80
    times inside BuildingManager.TileGrid.
    """

    #------------------------------ CONSTRUCTOR ---------------------------------

    def __init__(self, up, down, left, right):
        """
        Name: __init__
        Description: Creates a Tile with its 4 sides already
                     defined.
        Inputs: up, down, left, right (int, values 0-5)
        Outputs: none (constructor)
        Usage: called by BuildingManager.__init__ once for each of
               the 80 board positions.
        """
        self.up = up
        self.down = down
        self.left = left
        self.right = right

    #------------------------------ QUERY ---------------------------------

    def getTile(self):
        """
        Name: getTile
        Description: Returns the 4 sides of the cell in fixed order.
        Inputs: none
        Outputs: list[int] -> [up, down, left, right]
        Usage: called by BuildingManager.get(x,y) and by
               GameManager._tile_to_dict / capture_snapshot to
               export the wall state.
        """
        return [self.up, self.down, self.left, self.right]

    def getDir(self, dir):
        """
        Name: getDir
        Description: Returns the value of a specific side of the
                     cell.
        Inputs: dir (str) -> "up" | "down" | "left" | "right"
        Outputs: int (0-5), the value of that side
        Usage: called by BuildingManager.getDir(x,y,dir), which in
               turn is used by FireManager (propagation) and
               Firefighter (deciding the action before advancing).
        """
        directions = {
            "up": self.up,
            "down": self.down,
            "left": self.left,
            "right": self.right
        }
        return directions[dir]

    #------------------------------ MODIFICATION ---------------------------------

    def setUp(self, up):
        """
        Name: setUp
        Description: Overwrites the value of the upper side.
        Inputs: up (int, 0-5)
        Outputs: none
        Usage: called by BuildingManager._setDir when dir=="up"
               (wall damage or door state change).
        """
        self.up = up

    def setDown(self, down):
        """
        Name: setDown
        Description: Overwrites the value of the lower side.
        Inputs: down (int, 0-5)
        Outputs: none
        Usage: called by BuildingManager._setDir when dir=="down".
        """
        self.down = down

    def setLeft(self, left):
        """
        Name: setLeft
        Description: Overwrites the value of the left side.
        Inputs: left (int, 0-5)
        Outputs: none
        Usage: called by BuildingManager._setDir when dir=="left".
        """
        self.left = left

    def setRight(self, right):
        """
        Name: setRight
        Description: Overwrites the value of the right side.
        Inputs: right (int, 0-5)
        Outputs: none
        Usage: called by BuildingManager._setDir when dir=="right".
        """
        self.right = right

    def setAll(self, up, down, left, right):
        """
        Name: setAll
        Description: Overwrites all 4 sides of the cell at once.
        Inputs: up, down, left, right (int, 0-5)
        Outputs: none
        Usage: utility for manual board initialization (not used in
               the current automatic flow).
        """
        self.up = up
        self.down = down
        self.left = left
        self.right = right