"""Lanza la cámara y la corrección de la distorsión con la calibración obtenida."""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    """Describe el lanzamiento completo de la práctica (requiere la cámara calibrada).

    Acepta los mismos argumentos que camara.launch.py (dispositivo, formato_pixel,
    ancho, alto, fps y visor), que se pasan a la cámara.

    Returns:
        Descripción con usb_cam, el visor y corrector_distorsion.
    """
    camara = IncludeLaunchDescription(PythonLaunchDescriptionSource(PathJoinSubstitution([
        FindPackageShare('practica_2'), 'launch', 'camara.launch.py'])))

    corrector = Node(package='practica_2', executable='corrector_distorsion', output='screen')

    return LaunchDescription([camara, corrector])
