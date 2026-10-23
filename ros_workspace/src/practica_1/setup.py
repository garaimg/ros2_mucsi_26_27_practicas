from setuptools import find_packages, setup

package_name = 'practica_1'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Garaimtzg',
    maintainer_email='garaimg12@gmail.com',
    description='Práctica 1: extracción de posición, velocidad y aceleración del UR3e',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'ejecutor_trayectorias = practica_1.ejecutor_trayectorias:main',
        ],
    },
)
