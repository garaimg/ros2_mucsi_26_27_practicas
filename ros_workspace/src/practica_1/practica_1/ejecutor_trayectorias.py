"""Ejecuta una trayectoria articular, una lineal y una circular registrando cada una por separado."""

import copy
from math import cos, pi, sin
from pathlib import Path
from typing import Callable, List

import rclpy
from geometry_msgs.msg import Pose

from practica_1.control_robot import ControlRobot
from practica_1.registrador_articulaciones import RegistradorArticulaciones

DIRECTORIO_DATOS = Path("~/ros_workspace/datos_practica_1").expanduser()

PI_MEDIOS = pi / 2
# Configuración articular desde la que empiezan todas las trayectorias (la del ejemplo)
ARTICULACIONES_INICIO = [0.0, -PI_MEDIOS, -PI_MEDIOS, -PI_MEDIOS, PI_MEDIOS, 0.0]
# Destino de la trayectoria articular: gira la base 45º e inclina el brazo hacia delante
# manteniendo la herramienta apuntando hacia abajo
ARTICULACIONES_DESTINO = [pi / 4, -pi / 3, -2 * pi / 3, -PI_MEDIOS, PI_MEDIOS, pi / 4]

DESCENSO_LINEAL = 0.1  # [m] bajada vertical del primer tramo lineal
AVANCE_LINEAL = 0.1  # [m] desplazamiento en Y del segundo tramo lineal

RADIO_CIRCULO = 0.05  # [m]
PUNTOS_CIRCULO = 36  # Nº de poses con las que se aproxima la circunferencia


class EjecutorTrayectorias:
    """Mueve el robot por las tres trayectorias mientras el registrador guarda sus datos."""

    def __init__(self) -> None:
        """Conecta con MoveIt y añade el registrador al ejecutor de ROS de ControlRobot."""
        self.control = ControlRobot()
        self.registrador = RegistradorArticulaciones(DIRECTORIO_DATOS)
        # ControlRobot ya tiene un ejecutor atendiendo callbacks en otro hilo; así el
        # suscriptor recibe /joint_states en tiempo real mientras el robot se mueve
        self.control.ejecutor.add_node(self.registrador)

    def ejecutar(self) -> None:
        """Ejecuta las trayectorias, volviendo a la posición de inicio antes de cada una."""
        trayectorias = {
            "articular": self._trayectoria_articular,
            "lineal": self._trayectoria_lineal,
            "circular": self._trayectoria_circular,
        }
        for nombre, movimiento in trayectorias.items():
            # El posicionamiento previo no se registra
            self.control.mover_articulaciones(ARTICULACIONES_INICIO)
            self._registrar(nombre, movimiento)

    def cerrar(self) -> None:
        """Detiene el ejecutor de ROS y destruye los nodos."""
        self.control.ejecutor.shutdown()
        self.registrador.destroy_node()
        self.control.destroy_node()

    def _registrar(self, nombre: str, movimiento: Callable[[], bool]) -> None:
        """Ejecuta `movimiento` guardando sus datos como la trayectoria `nombre`."""
        self.registrador.iniciar_trayectoria(nombre)
        exito = movimiento()
        self.registrador.finalizar_trayectoria()
        if not exito:
            self.control.get_logger().error(f"La trayectoria '{nombre}' ha fallado")

    def _trayectoria_articular(self) -> bool:
        """Movimiento Joint: MoveIt elige libremente el camino en el espacio articular."""
        return self.control.mover_articulaciones(ARTICULACIONES_DESTINO)

    def _trayectoria_lineal(self) -> bool:
        """Movimiento lineal: dos tramos rectos del efector final (bajada en Z y avance en Y)."""
        pose = self.control.pose_actual()
        poses: List[Pose] = []

        pose.position.z -= DESCENSO_LINEAL
        poses.append(copy.deepcopy(pose))
        pose.position.y += AVANCE_LINEAL
        poses.append(copy.deepcopy(pose))

        return self.control.mover_trayectoria(poses)

    def _trayectoria_circular(self) -> bool:
        """Movimiento circular: circunferencia horizontal que pasa por la pose actual.

        MoveIt no tiene un movimiento circular como tal, así que se aproxima con
        PUNTOS_CIRCULO poses sobre la circunferencia unidas por tramos rectos.
        """
        inicio = self.control.pose_actual()
        # El centro se coloca a RADIO_CIRCULO en -X para que la pose actual (ángulo 0)
        # sea un punto de la circunferencia y el movimiento empiece sin saltos
        centro_x = inicio.position.x - RADIO_CIRCULO
        centro_y = inicio.position.y

        poses: List[Pose] = []
        for i in range(1, PUNTOS_CIRCULO + 1):
            angulo = 2 * pi * i / PUNTOS_CIRCULO
            pose = copy.deepcopy(inicio)
            pose.position.x = centro_x + RADIO_CIRCULO * cos(angulo)
            pose.position.y = centro_y + RADIO_CIRCULO * sin(angulo)
            poses.append(pose)

        return self.control.mover_trayectoria(poses)


def main() -> None:
    """Punto de entrada de `ros2 run practica_1 ejecutor_trayectorias`."""
    rclpy.init()
    ejecutor = EjecutorTrayectorias()
    try:
        ejecutor.ejecutar()
    except KeyboardInterrupt:
        pass
    ejecutor.cerrar()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
