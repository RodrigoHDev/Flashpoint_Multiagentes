"""
Title: Candidate
Author: Rodrigo Hurtado
Description:

Represents something an agent could go attend to: a POI, a fire
threat near a POI, or general fire/smoke. It is not an action yet,
just an "this exists and is this urgent".

Functions:
CONSTRUCTOR
__init__

REPRESENTATION
__repr__

"""

class Candidate:
    """
    Represents something an agent could go attend to: a POI, a fire
    threat near a POI, or general fire/smoke. It is not an action
    yet, just an "this exists and is this urgent".
    """

    #------------------------------ CONSTRUCTOR ---------------------------------

    def __init__(self, pos, type, priority):
        """
        Name: __init__
        Description: Creates a candidate with its position, type,
                    and numeric priority (higher = more urgent).
        Inputs: pos (tuple[int,int]), type (str), priority (int)
        Outputs: none (constructor)
        Usage: instantiated by the scan_* functions of the
            Coordinator.
        """
        self.pos = pos
        self.type = type
        self.priority = priority

    #------------------------------ REPRESENTATION ---------------------------------

    def __repr__(self):
        """
        Name: __repr__
        Description: Readable representation for debugging/logs.
        Inputs: none
        Outputs: str
        Usage: used automatically by print()/logs when printing a
            list of candidates.
        """
        return f"Candidate(pos={self.pos}, type={self.type}, priority={self.priority})"