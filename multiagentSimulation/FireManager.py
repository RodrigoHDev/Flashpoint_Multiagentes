"""
Title: FireManager
Author: Rodrigo Hurtado
Description:

Manages the fire/smoke state of the board (fireGrid). Cell values:
0=empty, 1=smoke, 2=fire. Depends on BuildingManager (walls/doors)
and PoiManager (to know whether a POI must be destroyed when its
cell catches fire), plus the list of agents (to apply knockdown).

Functions:
SETUP
__init__
link

QUERY
get
getNeighborhoodFire

STATE TRANSITIONS
turnToFire
turnToSmoke
turnOff

TURN CYCLE
putSmoke

EXPLOSION PROPAGATION
_propagate
explotion
shockwave

"""

import numpy as np
import  Dice as Dice

WIDTH, HEIGHT = 10, 8

class FireManager:
    """
    Manages the fire/smoke state of the board (fireGrid). Cell
    values: 0=empty, 1=smoke, 2=fire. Depends on BuildingManager
    (walls/doors) and PoiManager (to know whether a POI must be
    destroyed when its cell catches fire), plus the list of agents
    (to apply knockdown).
    """

    #------------------------------ SETUP ---------------------------------

    def __init__(self):
        """
        Name: __init__
        Description: Creates the fire grid at zero and places the
                     game's initial fire at the fixed positions
                     agreed upon for this map.
        Inputs: none
        Outputs: none (constructor)
        Usage: instantiated once inside GameManager.__init__.
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
        Name: link
        Description: Injects the necessary cross-references to
                     operate (two-phase pattern, avoids a circular
                     dependency in the constructor).
        Inputs: buildingManager (BuildingManager), poiManager
                (PoiManager), agents (list[Firefighter])
        Outputs: none
        Usage: called once from GameManager.__init__, right after
               instantiating the three managers.
        """
        self.building = buildingManager
        self.poi = poiManager
        self.agents = agents

    #------------------------------ QUERY ---------------------------------

    def get(self, x, y):
        """
        Name: get
        Description: Queries what is in a cell of the fire grid.
        Inputs: x, y (int)
        Outputs: int -> 0 (empty), 1 (smoke), 2 (fire)
        Usage: called extensively by Firefighter (to decide an
               action), PoiManager.set() (to check whether to clear
               fire when inserting a POI), and by this same manager
               in its internal logic.
        """
        return self.fireGrid[x, y]

    def getNeighborhoodFire(self, x, y):
        """
        Name: getNeighborhoodFire
        Description: Checks the 4 directions around a cell and
                     returns the neighboring positions that have
                     fire, respecting walls/closed doors in between.
        Inputs: x, y (int)
        Outputs: list[tuple[int,int]] -> neighboring positions with
                 fire
        Usage: called by putSmoke() to decide whether an empty cell
               should turn into fire (if there is adjacent fire) or
               into smoke (if there isn't).
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

    #------------------------------ STATE TRANSITIONS ---------------------------------

    def turnToFire(self, x, y):
        """
        Name: turnToFire
        Description: Turns a cell into fire. Applies knockdown to
                     any agent standing there, and destroys any POI
                     present in that cell.
        Inputs: x, y (int)
        Outputs: none
        Usage: called by putSmoke(), _propagate(), and shockwave()
               as a consequence of fire propagation.
        """
        for agent in self.agents:
            if agent.pos[0] == x and agent.pos[1] == y:
                agent.setKnockdown(True)

        if self.poi.get(x, y) > 0:
            self.poi.destroy(x, y)

        self.fireGrid[x, y] = 2

    def turnToSmoke(self, x, y):
        """
        Name: turnToSmoke
        Description: Marks a cell as smoke.
        Inputs: x, y (int)
        Outputs: none
        Usage: called by putSmoke() when an empty cell has no
               adjacent fire; and by Firefighter.turnFireToSmoke()
               as the effect of the firefighter's action.
        """
        self.fireGrid[x, y] = 1

    def turnOff(self, x, y):
        """
        Name: turnOff
        Description: Clears a cell (fire or smoke), leaving it
                     empty.
        Inputs: x, y (int)
        Outputs: none
        Usage: called by PoiManager.set() when inserting a POI on
               top of fire, and by Firefighter.turnFireToNothing() /
               turnSmokeToNothing() as the effect of the
               firefighter's action.
        """
        self.fireGrid[x, y] = 0

    #------------------------------ TURN CYCLE ---------------------------------

    def putSmoke(self):
        """
        Name: putSmoke
        Description: Rolls its own dice and applies the fire
                     advancement rule to the resulting cell:
                     empty+adjacent fire->fire, empty with no fire
                     nearby->smoke, smoke->fire, fire->explosion.
        Inputs: none
        Outputs: none
        Usage: called once per complete agent turn, from
               GameManager.step_agent().
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

    #------------------------------ EXPLOSION PROPAGATION ---------------------------------

    def _propagate(self, x, y, dir):
        """
        Name: _propagate
        Description: Applies the effect of an explosion/shockwave in
                     ONE direction: if the path is clear and the next
                     cell has no fire, it ignites it (or triggers a
                     shockwave if it already had fire); if there is a
                     wall/door in the way, damages it.
        Inputs: x, y (int), dir (str)
        Outputs: none
        Usage: called by explotion() (once for each of the 4
               directions) and by shockwave() (upon reaching the end
               of the fire chain).
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
        Name: explotion
        Description: Applies a full explosion (all 4 directions) on
                     a cell that already had fire.
        Inputs: x, y (int)
        Outputs: none
        Usage: called by putSmoke() when the dice lands on a cell
               that was already on fire.
        """
        directions = ["right", "left", "up", "down"]
        for dir in directions:
            self._propagate(x, y, dir)

    def shockwave(self, x, y, dir):
        """
        Name: shockwave
        Description: Advances in a direction while the path is
                     clear/an open door and the next cell has fire,
                     until reaching the last burning cell of that
                     chain, and applies _propagate there.
        Inputs: x, y (int), dir (str)
        Outputs: none
        Usage: called by _propagate() when an explosion hits a cell
               that already had fire (domino effect).
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