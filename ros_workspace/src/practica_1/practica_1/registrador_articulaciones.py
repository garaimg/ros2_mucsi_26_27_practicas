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
    """Nodo suscriptor que registra el estado cinemático de las articulaciones del brazo.

    Se suscribe a /joint_states y, con cada mensaje, calcula la velocidad y la
    aceleración de las 6 articulaciones. Mientras hay una trayectoria activa (entre
    iniciar_trayectoria y finalizar_trayectoria) y el robot se está moviendo, guarda
    una fila por mensaje. Al finalizar la trayectoria escribe esas filas en un CSV.
    """

    def __init__(self, directorio_salida: Path) -> None:
        """Crea el nodo y la suscripción a /joint_states.

        Args:
            directorio_salida: carpeta donde se guardarán los CSV. Se crea si no existe
                cuando se escribe el primer fichero.
        """
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
        """Empieza a registrar una trayectoria nueva.

        Borra las filas que hubiera de la trayectoria anterior; a partir de aquí cada
        mensaje de /joint_states con el robot en movimiento se guarda como parte de ella.

        Args:
            nombre: nombre de la trayectoria. Se usa como nombre del CSV (<nombre>.csv).
        """
        self._filas = []
        self._trayectoria_actual = nombre

    def finalizar_trayectoria(self) -> None:
        """Deja de registrar y escribe la trayectoria en curso en su CSV.

        El fichero se guarda en <directorio_salida>/<nombre>.csv con una cabecera y una
        fila por muestra: tiempo, 6 posiciones, 6 velocidades y 6 aceleraciones.
        Si el fichero ya existía se sobrescribe.
        """
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
        """Procesa un mensaje de /joint_states (callback de la suscripción).

        Saca las posiciones del brazo en el orden de ARTICULACIONES, calcula la
        velocidad y la aceleración y, si hay una trayectoria activa y el robot se está
        moviendo, añade la fila a las muestras. Los mensajes que no traen las
        articulaciones del brazo (los de la pinza) o que llegan repetidos se ignoran.

        Args:
            mensaje: estado de las articulaciones publicado por el robot (nombres,
                posiciones en rad y marca de tiempo en la cabecera).
        """
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
        """Comprueba si el robot se está moviendo.

        Args:
            velocidad: velocidad de cada articulación [rad/s].

        Returns:
            True si al menos una articulación supera UMBRAL_VELOCIDAD (en valor
            absoluto); False si todas están por debajo, es decir, el robot está parado.
        """
        return any(abs(v) > UMBRAL_VELOCIDAD for v in velocidad)

    @staticmethod
    def _derivar(historial: Deque[Muestra], tiempo: float, valores: List[float]) -> List[float]:
        """Calcula la derivada respecto al tiempo de una magnitud de las articulaciones.

        Añade la muestra nueva a `historial` y quita las que tienen más de
        VENTANA_DERIVADA segundos de antigüedad. La derivada es una diferencia finita
        hacia atrás entre la muestra nueva y la más antigua que queda en el historial.
        Ojo: modifica `historial`.

        Args:
            historial: muestras anteriores de la magnitud (tiempo y valores).
            tiempo: instante de la muestra nueva [s].
            valores: valor de la magnitud en cada articulación en ese instante.

        Returns:
            Lista con la derivada de cada articulación (por ejemplo, si `valores` son
            posiciones en rad, devuelve velocidades en rad/s). En la primera muestra,
            cuando aún no hay con qué comparar, devuelve todo ceros.
        """
        historial.append((tiempo, valores))
        while len(historial) > 2 and tiempo - historial[1][0] >= VENTANA_DERIVADA:
            historial.popleft()

        tiempo_antiguo, valores_antiguos = historial[0]
        intervalo = tiempo - tiempo_antiguo
        if intervalo == 0.0:
            return [0.0] * len(valores)  # Primera lectura: todavía no hay con qué derivar
        return [(v - v_antiguo) / intervalo for v, v_antiguo in zip(valores, valores_antiguos)]
