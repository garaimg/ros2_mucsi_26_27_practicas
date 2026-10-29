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
    """Ejecuta las tres trayectorias de la práctica y coordina su registro.

    No es un nodo de ROS: contiene los dos nodos del programa, ControlRobot (que
    mueve el robot con MoveIt) y RegistradorArticulaciones (que guarda los datos),
    y decide en qué orden se hace cada cosa.

    Attributes:
        control: nodo que manda los movimientos a MoveIt.
        registrador: nodo suscriptor que registra los datos de cada trayectoria.
    """

    def __init__(self) -> None:
        """Crea los dos nodos y conecta el registrador al ejecutor de ROS.

        ControlRobot ya tiene un ejecutor atendiendo callbacks en un hilo aparte; al
        añadirle el registrador, este recibe /joint_states mientras el hilo principal
        espera a que terminen los movimientos. Se bloquea hasta que MoveIt está listo.
        """
        self.control = ControlRobot()
        self.registrador = RegistradorArticulaciones(DIRECTORIO_DATOS)
        # ControlRobot ya tiene un ejecutor atendiendo callbacks en otro hilo; así el
        # suscriptor recibe /joint_states en tiempo real mientras el robot se mueve
        self.control.ejecutor.add_node(self.registrador)

    def ejecutar(self) -> None:
        """Ejecuta, en orden, la trayectoria articular, la lineal y la circular.

        Antes de cada una lleva el robot a ARTICULACIONES_INICIO (ese posicionamiento
        no se registra). Cada trayectoria se guarda en su propio CSV. Se bloquea hasta
        que el robot termina la última.
        """
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
        """Para el ejecutor de ROS y destruye los dos nodos.

        Hay que llamarlo al terminar, antes de rclpy.try_shutdown().
        """
        self.control.ejecutor.shutdown()
        self.registrador.destroy_node()
        self.control.destroy_node()

    def _registrar(self, nombre: str, movimiento: Callable[[], bool]) -> None:
        """Ejecuta un movimiento registrando sus datos como una trayectoria.

        Args:
            nombre: nombre de la trayectoria, que será también el nombre del CSV.
            movimiento: función sin argumentos que mueve el robot y devuelve True si
                el movimiento se ha completado bien. Por ejemplo, _trayectoria_lineal.
        """
        self.registrador.iniciar_trayectoria(nombre)
        exito = movimiento()
        self.registrador.finalizar_trayectoria()
        if not exito:
            self.control.get_logger().error(f"La trayectoria '{nombre}' ha fallado")

    def _trayectoria_articular(self) -> bool:
        """Movimiento Joint: lleva el robot a ARTICULACIONES_DESTINO.

        Solo se fijan los ángulos finales; MoveIt elige el camino en el espacio
        articular, así que la pinza no sigue una línea recta.

        Returns:
            True si MoveIt ha planificado y ejecutado el movimiento; False si no.
        """
        return self.control.mover_articulaciones(ARTICULACIONES_DESTINO)

    def _trayectoria_lineal(self) -> bool:
        """Movimiento lineal: dos tramos rectos de la pinza desde la pose actual.

        Primero baja DESCENSO_LINEAL metros en Z y después avanza AVANCE_LINEAL metros
        en Y, sin cambiar la orientación de la pinza.

        Returns:
            True si se ha podido hacer el camino recto completo; False si MoveIt no lo
            encuentra (en ese caso el robot no se mueve) o falla al ejecutarlo.
        """
        pose = self.control.pose_actual()
        poses: List[Pose] = []

        pose.position.z -= DESCENSO_LINEAL
        poses.append(copy.deepcopy(pose))
        pose.position.y += AVANCE_LINEAL
        poses.append(copy.deepcopy(pose))

        return self.control.mover_trayectoria(poses)

    def _trayectoria_circular(self) -> bool:
        """Movimiento circular: una vuelta completa en un plano horizontal.

        MoveIt no tiene un movimiento circular como tal, así que se aproxima con
        PUNTOS_CIRCULO poses sobre una circunferencia de radio RADIO_CIRCULO unidas por
        tramos rectos. La pose actual es el primer punto de la circunferencia y el
        último coincide con ella, así que el robot acaba donde empezó.

        Returns:
            True si se ha completado la circunferencia; False si MoveIt no encuentra el
            camino (en ese caso el robot no se mueve) o falla al ejecutarlo.
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
    """Punto de entrada de `ros2 run practica_1 ejecutor_trayectorias`.

    Inicializa ROS, ejecuta las tres trayectorias y cierra todo al acabar o al
    pulsar Ctrl+C.
    """
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
