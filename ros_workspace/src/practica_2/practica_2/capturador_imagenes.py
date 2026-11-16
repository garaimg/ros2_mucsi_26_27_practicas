"""Nodo que guarda un número fijo de imágenes de la cámara, todas distintas entre sí."""

from pathlib import Path
from typing import List

import cv2
from cv_bridge import CvBridge
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Image

TOPIC_IMAGEN = '/usb_cam/image_raw'
PROFUNDIDAD_COLA = 10
NUMERO_IMAGENES = 10
DIRECTORIO_IMAGENES = '~/ros_workspace/imagenes_practica_2'

# Dos imágenes se consideran iguales si la diferencia media entre sus píxeles (escala
# de grises, 0-255) no supera este valor. Medido con la HD USB Camera y la escena
# quieta: el ruido entre imágenes seguidas es ~0,2, pero el ajuste automático de
# exposición al encenderla y la deriva lenta de la imagen llegan a ~2,6. Mover la
# cámara o el tablero da diferencias mucho mayores, así que 5 separa bien ambos casos
UMBRAL_DIFERENCIA = 5.0
# Las imágenes se comparan reducidas y suavizadas: es más rápido y el ruido de píxeles
# sueltos influye menos que los cambios reales de la escena
TAMANO_COMPARACION = (160, 120)  # (ancho, alto) [píxeles]
NUCLEO_SUAVIZADO = (5, 5)
PERIODO_AVISO_DESCARTE = 2.0  # [s] como mucho un aviso por descarte cada este tiempo


class CapturadorImagenes(Node):
    """Suscriptor que ingiere imágenes de la cámara y guarda las primeras N distintas.

    Cada imagen que llega se convierte a OpenCV con cv_bridge y se compara con todas
    las ya guardadas. Si se parece demasiado a alguna, se descarta; si no, se guarda
    como PNG. Al llegar a N imágenes el nodo marca `terminado`.

    Attributes:
        terminado: True cuando ya se han guardado todas las imágenes.
    """

    def __init__(self) -> None:
        """Declara los parámetros, crea la carpeta de salida y la suscripción."""
        super().__init__('capturador_imagenes')
        self._numero_imagenes: int = self.declare_parameter(
            'numero_imagenes', NUMERO_IMAGENES).value
        self._umbral_diferencia: float = self.declare_parameter(
            'umbral_diferencia', UMBRAL_DIFERENCIA).value
        self._directorio = Path(self.declare_parameter(
            'directorio', DIRECTORIO_IMAGENES).value).expanduser()
        topic_imagen: str = self.declare_parameter('topic_imagen', TOPIC_IMAGEN).value

        self._directorio.mkdir(parents=True, exist_ok=True)
        self._puente = CvBridge()
        # Versión reducida de cada imagen guardada, para compararla con las nuevas
        self._miniaturas_guardadas: List[np.ndarray] = []
        self._imagenes_descartadas = 0
        self.terminado = False

        self.create_subscription(Image, topic_imagen, self._cb_imagen, PROFUNDIDAD_COLA)
        self.get_logger().info(
            f'Esperando imágenes en {topic_imagen}. Se guardarán '
            f'{self._numero_imagenes} distintas en {self._directorio}')

    def _cb_imagen(self, mensaje: Image) -> None:
        """Procesa una imagen recibida (callback de la suscripción).

        Args:
            mensaje: imagen de ROS publicada por usb_cam.
        """
        if self.terminado:
            return
        imagen = self._puente.imgmsg_to_cv2(mensaje, desired_encoding='bgr8')
        miniatura = self._miniatura(imagen)
        if not self._es_distinta(miniatura):
            self._imagenes_descartadas += 1
            self.get_logger().info(
                'Imagen descartada por parecerse a una ya guardada: mueve la cámara o '
                'lo que tiene delante', throttle_duration_sec=PERIODO_AVISO_DESCARTE)
            return

        indice = len(self._miniaturas_guardadas)
        ruta = self._directorio / f'imagen_{indice:02d}.png'
        cv2.imwrite(str(ruta), imagen)
        self._miniaturas_guardadas.append(miniatura)
        self.get_logger().info(
            f'Guardada {ruta.name} ({indice + 1}/{self._numero_imagenes}, '
            f'{self._imagenes_descartadas} descartadas por repetidas hasta ahora)')

        if len(self._miniaturas_guardadas) == self._numero_imagenes:
            self.terminado = True
            self.get_logger().info('Captura terminada')

    def _es_distinta(self, miniatura: np.ndarray) -> bool:
        """Comprueba si una imagen es distinta de todas las ya guardadas.

        Args:
            miniatura: imagen nueva ya reducida con `_miniatura`.

        Returns:
            True si su diferencia media con cada imagen guardada supera el umbral.
            Se compara con todas, y no solo con la última, para que las N imágenes
            sean distintas entre sí y no únicamente de su anterior.
        """
        return all(
            float(np.mean(cv2.absdiff(miniatura, guardada))) > self._umbral_diferencia
            for guardada in self._miniaturas_guardadas)

    @staticmethod
    def _miniatura(imagen: np.ndarray) -> np.ndarray:
        """Reduce una imagen a una versión pequeña, gris y suavizada para compararla.

        Args:
            imagen: imagen BGR de OpenCV.

        Returns:
            Imagen en escala de grises de tamaño TAMANO_COMPARACION.
        """
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        reducida = cv2.resize(gris, TAMANO_COMPARACION, interpolation=cv2.INTER_AREA)
        return cv2.GaussianBlur(reducida, NUCLEO_SUAVIZADO, 0)


def main() -> None:
    """Punto de entrada de `ros2 run practica_2 capturador_imagenes`.

    Atiende la suscripción hasta guardar todas las imágenes o pulsar Ctrl+C.
    """
    # Sin el gestor de señales de rclpy, Ctrl+C llega como KeyboardInterrupt y corta el
    # spin con ROS aún activo. Con él, ROS se cerraría en mitad de un callback y
    # publicar o destruir el nodo fallaría con un error
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    nodo = CapturadorImagenes()
    try:
        while rclpy.ok() and not nodo.terminado:
            rclpy.spin_once(nodo)
    except KeyboardInterrupt:
        pass
    nodo.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
