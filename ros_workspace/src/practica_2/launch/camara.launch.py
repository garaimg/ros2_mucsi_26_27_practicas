"""Publica las imágenes de la cámara con usb_cam y las muestra con rqt_image_view."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# Con el espacio de nombres usb_cam los topics quedan /usb_cam/image_raw y
# /usb_cam/camera_info (usb_cam los publica relativos a su espacio de nombres)
ESPACIO_NOMBRES_CAMARA = 'usb_cam'
RUTA_CALIBRACION = (Path(get_package_share_directory('practica_2'))
                    / 'config' / 'calibracion_camara.yaml')


def generate_launch_description() -> LaunchDescription:
    """Describe el lanzamiento de la cámara y del visor.

    Argumentos de lanzamiento:
        dispositivo: dispositivo de vídeo de la cámara (por ejemplo /dev/video0).
        formato_pixel: formato que entrega la cámara (yuyv, mjpeg2rgb...).
        ancho, alto: resolución de la imagen [píxeles].
        fps: imágenes por segundo.
        visor: 'false' para no abrir rqt_image_view.

    Returns:
        Descripción con el nodo usb_cam y, opcionalmente, el visor. Si existe el
        fichero de calibración, usb_cam lo publica en /usb_cam/camera_info.
    """
    argumentos = [
        DeclareLaunchArgument('dispositivo', default_value='/dev/video0',
                              description='Dispositivo de vídeo de la cámara'),
        # MJPEG llega comprimido: con la cámara pasada a WSL por usbipd, yuyv (sin
        # comprimir) no cabe en el ancho de banda y las imágenes llegan incompletas
        DeclareLaunchArgument('formato_pixel', default_value='mjpeg2rgb',
                              description='Formato de la cámara: mjpeg2rgb, yuyv...'),
        DeclareLaunchArgument('ancho', default_value='640', description='Ancho [px]'),
        DeclareLaunchArgument('alto', default_value='480', description='Alto [px]'),
        DeclareLaunchArgument('fps', default_value='30.0', description='Imágenes por segundo'),
        DeclareLaunchArgument('visor', default_value='true',
                              description="'false' para no abrir rqt_image_view"),
    ]

    camara = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam',
        namespace=ESPACIO_NOMBRES_CAMARA,
        output='screen',
        parameters=[{
            'video_device': LaunchConfiguration('dispositivo'),
            'pixel_format': LaunchConfiguration('formato_pixel'),
            'image_width': LaunchConfiguration('ancho'),
            'image_height': LaunchConfiguration('alto'),
            'framerate': LaunchConfiguration('fps'),
            'io_method': 'mmap',
            'camera_frame_id': 'camara',
            'camera_info_url': f'file://{RUTA_CALIBRACION}',
        }],
    )

    visor = Node(
        package='rqt_image_view',
        executable='rqt_image_view',
        name='visor_imagen',
        output='screen',
        arguments=[f'/{ESPACIO_NOMBRES_CAMARA}/image_raw'],
        condition=IfCondition(LaunchConfiguration('visor')),
    )

    return LaunchDescription(argumentos + [camara, visor])
