"""
Title: Dice
Author: Rodrigo Hurtado
Description:

Random coordinate generator within the playable interior of the
board (x: 1-8, y: 1-6). Used by FireManager and PoiManager to decide
where new fire falls or where a new POI appears.

Functions:
CONSTRUCTOR
__init__

RANDOM GENERATION
roll

"""

import random

class Dice:
    """
    Random coordinate generator within the playable interior of the
    board (x: 1-8, y: 1-6). Used by FireManager and PoiManager to
    decide where new fire falls or where a new POI appears.
    """

    #------------------------------ CONSTRUCTOR ---------------------------------

    def __init__(self):
        """
        Name: __init__
        Description: Initializes the dice with no value rolled yet.
        Inputs: none
        Outputs: none (constructor)
        Usage: instantiated once inside FireManager.__init__ and once
               inside PoiManager.__init__ (each manager has its own
               independent dice).
        """
        self.x = 0
        self.y = 0

    #------------------------------ RANDOM GENERATION ---------------------------------

    def roll(self):
        """
        Name: roll
        Description: Generates a pair of random coordinates, x
                     between 1 and 8 inclusive, y between 1 and 6
                     inclusive (matches the playable interior of the
                     10x8 board).
        Inputs: none
        Outputs: tuple[int, int] -> (x, y)
        Usage: called by FireManager.putSmoke() to choose where
               fire/smoke falls, and by PoiManager.set() to choose
               where a new POI appears.
        """
        self.x = random.randint(1, 8)
        self.y = random.randint(1, 6)
        return self.x, self.y