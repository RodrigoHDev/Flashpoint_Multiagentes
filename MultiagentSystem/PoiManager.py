"""
Title: PoiManager
Author: Rodrigo Hurtado
Description:

Manages the board's points of interest (POI): its grid (POIGrid,
values 0=nothing, 1=unrevealed, 2=false alarm, 3=victim), the
saved/lost victim counters, and the public list of unrevealed POIs
(self.pois) that agent behavior queries directly.

Functions:
SETUP
__init__
link

QUERY
get
getVictimsSaved
getVictimsLost

POI INSERTION
initialInsert
insert
set

POI RESOLUTION
turnOver
destroy
destroyVictim
saveVictim

"""

import numpy as np
import  Dice as Dice

WIDTH, HEIGHT = 10, 8

from types import NoneType
class PoiManager:
    """
    Manages the board's points of interest (POI): its grid
    (POIGrid, values 0=nothing, 1=unrevealed, 2=false alarm,
    3=victim), the saved/lost victim counters, and the public list
    of unrevealed POIs (self.pois) that agent behavior queries
    directly.
    """

    #------------------------------ SETUP ---------------------------------

    def __init__(self):
        """
        Name: __init__
        Description: Creates the POI grid at zero and inserts the 3
                     initial POIs of the game at their fixed
                     positions.
        Inputs: none
        Outputs: none (constructor)
        Usage: instantiated once inside GameManager.__init__.
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
        Name: link
        Description: Injects the necessary cross-references.
        Inputs: buildManager (BuildingManager), fireManager
                (FireManager), agents (list[Firefighter])
        Outputs: none
        Usage: called once from GameManager.__init__.
        """
        self.building = buildManager
        self.fire = fireManager
        self.agents = agents

    #------------------------------ QUERY ---------------------------------

    def get(self, x, y):
        """
        Name: get
        Description: Queries the POI state in a cell.
        Inputs: x, y (int)
        Outputs: int -> 0 (nothing), 1 (unrevealed), 2 (transient
                 false alarm), 3 (transient victim)
        Usage: called by FireManager.turnToFire (to check whether
               there is something to destroy) and by
               Firefighter/GameManager to query the board.
        """
        return self.POIGrid[x, y]

    def getVictimsSaved(self):
        """
        Name: getVictimsSaved
        Description: Queries the saved-victims counter.
        Inputs: none
        Outputs: int
        Usage: called by GameManager.win() and by reports/snapshots.
        """
        return self.savedVictims

    def getVictimsLost(self):
        """
        Name: getVictimsLost
        Description: Queries the lost-victims counter.
        Inputs: none
        Outputs: int
        Usage: called by GameManager.lose() and by reports/snapshots.
        """
        return self.lostVictims

    #------------------------------ POI INSERTION ---------------------------------

    def initialInsert(self, x, y):
        """
        Name: initialInsert
        Description: Places an unrevealed POI on an empty cell and
                     adds it to the public list self.pois.
        Inputs: x, y (int)
        Outputs: none
        Usage: called by __init__ (initial POIs) and by set()
               (replenishment during the game).
        """
        print(f"POI inserted at {x}, {y}")
        self.POIGrid[x, y] = 1
        self.quantity += 1
        self.pois.append((x, y))

    def insert(self, x, y):
        """
        Name: insert
        Description: Places an unrevealed POI on an empty cell and
                     adds it to the public list self.pois.
                     Afterward, walks the list of available agents to
                     check whether any of them should trigger a
                     turnOver.
        Inputs: x, y (int)
        Outputs: none
        Usage: called by __init__ (initial POIs) and by set()
               (replenishment during the game).
        """
        self.initialInsert(x,y)
        for agent in self.agents:
                if agent.pos[0] == x and agent.pos[1] == y:
                    self.turnOver(x, y)
                    break

    def set(self):
        """
        Name: set
        Description: Replenishes POIs up to 3 active, rolling for
                     empty positions. If the new POI lands on fire,
                     puts it out; if it lands on an agent, reveals
                     the POI immediately.
        Inputs: none
        Outputs: none
        Usage: called once per complete agent turn, from
               GameManager.step_agent().
        """
        while self.quantity < 3:
            x, y = self.dice.roll()
            while self.get(x, y) != 0:
                x, y = self.dice.roll()

            self.insert(x, y)

            if self.fire.get(x, y) == 2:
                self.fire.turnOff(x, y)

    #------------------------------ POI RESOLUTION ---------------------------------

    def turnOver(self, x, y):
        """
        Name: turnOver
        Description: Reveals an unrevealed POI: rolls whether it is
                     a false alarm or a victim. If there is an agent
                     on that cell, resolves it immediately (assigns
                     the victim to the agent, or destroys the false
                     alarm).
        Inputs: x, y (int)
        Outputs: none
        Usage: called by set() (a new POI lands on an agent) and by
               Firefighter._act_primitive() upon reaching an
               unrevealed POI.
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

    def destroy(self, x, y):
        """
        Name: destroy
        Description: Removes a POI from the cell due to fire. If it
                     was already a confirmed victim, counts it as a
                     lost victim.
        Inputs: x, y (int)
        Outputs: none
        Usage: called by FireManager.turnToFire when fire reaches a
               cell that had a POI.
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
        Name: destroyVictim
        Description: Counts as lost a victim that a firefighter was
                     already carrying, when the firefighter falls
                     (knockdown).
        Inputs: none
        Outputs: none
        Usage: called by Firefighter.setKnockdown() when the agent
               falls while carrying a victim.
        """
        self.quantity -= 1
        self.lostVictims += 1

    def saveVictim(self):
        """
        Name: saveVictim
        Description: Registers that a victim was saved successfully
                     (a firefighter reached an exit with it).
        Inputs: none
        Outputs: none
        Usage: called by Firefighter._act_primitive() upon reaching
               an exit while carrying a victim.
        """
        print(f"Saved victim")
        self.savedVictims += 1
        self.quantity -= 1