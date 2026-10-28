"""Suscriptor de /joint_states que registra posición, velocidad y aceleración articulares."""

import csv
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional, Tuple

from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import JointState

from practica_1.control_robot import ARTICULACIONES

# /joint_states llega cada ~2 ms y sus marcas de tiempo tienen jitter (la simulación no
# es de tiempo real). Derivar entre dos muestras seguidas convierte ese jitter en picos
# de velocidad absurdos, así que se deriva respecto a la muestra de hace ~VENTANA_DERIVADA
VENTANA_DERIVADA = 0.05  # [s]

# Si ninguna articulación supera esta velocidad se considera que el robot está parado.
# En la simulación la posición de un robot quieto no cambia nada, así que con un valor
# pequeño basta para distinguirlo
UMBRAL_VELOCIDAD = 0.001  # [rad/s]

# (tiempo [s], un valor por articulación)
Muestra = Tuple[float, List[float]]


class RegistradorArticulaciones(Node):
    """Lee /joint_states en tiempo real y guarda un CSV por cada trayectoria registrada."""

    def __init__(self, directorio_salida: Path) -> None:
        """Crea la suscripción; los CSV se escribirán en `directorio_salida`."""
        super().__init__("registrador_articulaciones")
        self._directorio_salida = directorio_salida
        # None mientras no se está registrando ninguna trayectoria
        self._trayectoria_actual: Optional[str] = None
        # Filas del CSV de la trayectoria en curso: tiempo, posiciones, velocidades, aceleraciones
        self._filas: List[List[float]] = []

        # Lecturas recientes, necesarias para derivar
        self._historial_posicion: Deque[Muestra] = deque()
        self._historial_velocidad: Deque[Muestra] = deque()

        self.create_subscription(JointState, "/joint_states", self._cb_joint_states, 10)

    def iniciar_trayectoria(self, nombre: str) -> None:
        """Empieza a guardar las muestras que lleguen como parte de la trayectoria `nombre`."""
        self._filas = []
        self._trayectoria_actual = nombre

    def finalizar_trayectoria(self) -> None:
        """Deja de registrar y escribe las muestras en <directorio_salida>/<nombre>.csv."""
        nombre, filas = self._trayectoria_actual, self._filas
        # Se desactiva antes de escribir para que el callback no añada filas mientras tanto
        self._trayectoria_actual = None

        self._directorio_salida.mkdir(parents=True, exist_ok=True)
        ruta = self._directorio_salida / f"{nombre}.csv"
        with open(ruta, "w", newline="") as fichero:
            escritor = csv.writer(fichero)
            escritor.writerow(
                ["tiempo"]
                + [f"posicion_{j}" for j in ARTICULACIONES]
                + [f"velocidad_{j}" for j in ARTICULACIONES]
                + [f"aceleracion_{j}" for j in ARTICULACIONES])
            escritor.writerows(filas)
        self.get_logger().info(f"Guardadas {len(filas)} muestras en {ruta}")

    def _cb_joint_states(self, mensaje: JointState) -> None:
        """Deriva la nueva lectura de posición y la guarda si el robot se está moviendo."""
        # El mensaje no trae las articulaciones en un orden fijo y la pinza puede
        # publicar mensajes propios sin las del brazo: se reordenan o se descartan
        try:
            posicion = [mensaje.position[mensaje.name.index(j)] for j in ARTICULACIONES]
        except ValueError:
            return
        tiempo = Time.from_msg(mensaje.header.stamp).nanoseconds / 1e9
        if self._historial_posicion and tiempo <= self._historial_posicion[-1][0]:
            return  # Lectura repetida o desordenada: no se puede derivar

        # Se deriva también fuera de las trayectorias para que el historial esté
        # completo cuando empiece a registrarse una
        velocidad = self._derivar(self._historial_posicion, tiempo, posicion)
        aceleracion = self._derivar(self._historial_velocidad, tiempo, velocidad)

        if self._trayectoria_actual is None:
            return
        # Ingesta inteligente: los ratos en los que el robot está quieto (justo antes de
        # arrancar y después de frenar) no se guardan
        if not self._robot_en_movimiento(velocidad):
            return
        self._filas.append([tiempo] + posicion + velocidad + aceleracion)

    @staticmethod
    def _robot_en_movimiento(velocidad: List[float]) -> bool:
        """Indica si alguna articulación se mueve más rápido que UMBRAL_VELOCIDAD."""
        return any(abs(v) > UMBRAL_VELOCIDAD for v in velocidad)

    @staticmethod
    def _derivar(historial: Deque[Muestra], tiempo: float, valores: List[float]) -> List[float]:
        """Añade (tiempo, valores) a `historial` y devuelve su derivada respecto al tiempo.

        Es una diferencia finita hacia atrás entre la muestra nueva y la más antigua
        del historial, que se recorta para que tenga una antigüedad de ~VENTANA_DERIVADA.
        """
        historial.append((tiempo, valores))
        while len(historial) > 2 and tiempo - historial[1][0] >= VENTANA_DERIVADA:
            historial.popleft()

        tiempo_antiguo, valores_antiguos = historial[0]
        intervalo = tiempo - tiempo_antiguo
        if intervalo == 0.0:
            return [0.0] * len(valores)  # Primera lectura: todavía no hay con qué derivar
        return [(v - v_antiguo) / intervalo for v, v_antiguo in zip(valores, valores_antiguos)]
