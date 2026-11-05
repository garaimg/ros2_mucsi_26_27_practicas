"""Lanza la simulación del UR3e y ejecuta las trayectorias de la práctica 1."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    """Describe el lanzamiento: la simulación (opcional) y el ejecutor de trayectorias.

    Argumentos de lanzamiento:
        robot: puesto del laboratorio a simular (203, 204, 205 o 206).
        simulacion: 'false' si la simulación ya está lanzada aparte.

    Returns:
        Descripción con la simulación y el nodo ejecutor_trayectorias. El nodo espera
        él solo a que MoveIt esté listo, así que se pueden arrancar a la vez.
    """
    robot = LaunchConfiguration('robot')
    simulacion = LaunchConfiguration('simulacion')

    lanzamiento_simulacion = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            FindPackageShare('launcher_robots_lab_robotica'), 'launch',
            ['sim_', robot, '.launch.py']])),
        condition=IfCondition(simulacion))

    return LaunchDescription([
        DeclareLaunchArgument('robot', default_value='203',
                              description='Puesto del laboratorio a simular'),
        DeclareLaunchArgument('simulacion', default_value='true',
                              description="'false' si la simulación ya está lanzada"),
        lanzamiento_simulacion,
        Node(package='practica_1', executable='ejecutor_trayectorias', output='screen'),
    ])
