"""Nodo que aplica la calibración a la imagen de la cámara y publica la imagen corregida."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from practica_2.calibracion_camara import ALPHA_SIN_BORDES, CalibracionCamara
import rclpy
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Image

TOPIC_IMAGEN = '/usb_cam/image_raw'
TOPIC_IMAGEN_CORREGIDA = '/imagen_corregida'
PROFUNDIDAD_COLA = 10
# Fichero que se obtiene al calibrar con camera_calibration (ver README)
FICHERO_CALIBRACION = 'calibracion_camara.yaml'


def ruta_calibracion_por_defecto() -> str:
    """Devuelve la ruta del YAML de calibración instalado con el paquete.

    Returns:
        <share de practica_2>/config/calibracion_camara.yaml
    """
    return str(Path(get_package_share_directory('practica_2')) / 'config' / FICHERO_CALIBRACION)


class CorrectorDistorsion(Node):
    """Suscriptor que corrige la distorsión de la cámara y republica la imagen.

    Convierte cada Image de ROS a OpenCV con cv_bridge, le aplica los parámetros
    de calibración con `CalibracionCamara` y la vuelve a convertir para publicarla.
    """

    def __init__(self) -> None:
        """Declara los parámetros, carga la calibración y crea la suscripción y el publicador."""
        super().__init__('corrector_distorsion')
        ruta_calibracion = Path(self.declare_parameter(
            'ruta_calibracion', ruta_calibracion_por_defecto()).value)
        alpha: float = self.declare_parameter('alpha', ALPHA_SIN_BORDES).value
        topic_entrada: str = self.declare_parameter('topic_imagen', TOPIC_IMAGEN).value
        topic_salida: str = self.declare_parameter(
            'topic_imagen_corregida', TOPIC_IMAGEN_CORREGIDA).value

        self._calibracion = CalibracionCamara.desde_yaml(ruta_calibracion, alpha)
        self._puente = CvBridge()
        self._publicador = self.create_publisher(Image, topic_salida, PROFUNDIDAD_COLA)
        self.create_subscription(Image, topic_entrada, self._cb_imagen, PROFUNDIDAD_COLA)
        self.get_logger().info(
            f'Calibración cargada de {ruta_calibracion}. Corrigiendo {topic_entrada} '
            f'y publicando en {topic_salida}')

    def _cb_imagen(self, mensaje: Image) -> None:
        """Corrige una imagen recibida y la publica (callback de la suscripción).

        Args:
            mensaje: imagen original publicada por usb_cam.
        """
        imagen = self._puente.imgmsg_to_cv2(mensaje, desired_encoding='bgr8')
        corregida = self._calibracion.corregir(imagen)
        mensaje_corregido = self._puente.cv2_to_imgmsg(corregida, encoding='bgr8')
        # Misma marca de tiempo y frame que la original: es la misma captura
        mensaje_corregido.header = mensaje.header
        self._publicador.publish(mensaje_corregido)


def main() -> None:
    """Punto de entrada de `ros2 run practica_2 corrector_distorsion`."""
    # Sin el gestor de señales de rclpy, Ctrl+C llega como KeyboardInterrupt y corta el
    # spin con ROS aún activo. Con él, ROS se cerraría en mitad de un callback y
    # publicar o destruir el nodo fallaría con un error
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    nodo = CorrectorDistorsion()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    nodo.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
