class Candidate:
    """
    Representa algo que un agente podria ir a atender: un POI, una
    amenaza de fuego cerca de un POI, o fuego/humo general. No es
    una accion todavia, solo un "esto existe y asi de urgente es".
    """

    def __init__(self, pos, tipo, prioridad):
        """
        Nombre: __init__
        Descripcion: crea un candidato con su posicion, tipo y
                     prioridad numerica (mayor = mas urgente).
        Entradas: pos (tuple[int,int]), tipo (str), prioridad (int)
        Salidas: ninguna (constructor)
        Uso: instanciado por las funciones scan_* del Coordinator.
        """
        self.pos = pos
        self.tipo = tipo
        self.prioridad = prioridad

    def __repr__(self):
        """
        Nombre: __repr__
        Descripcion: representacion legible para depuracion/logs.
        Entradas: ninguna
        Salidas: str
        Uso: usado automaticamente por print()/logs cuando se
             imprime una lista de candidatos.
        """
        return f"Candidate(pos={self.pos}, tipo={self.tipo}, prioridad={self.prioridad})"