from glob import glob

from setuptools import find_packages, setup

package_name = 'practica_2'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Garaimtzg',
    maintainer_email='garaimg12@gmail.com',
    description='Práctica 2: ingesta, calibración y procesamiento de imágenes',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'capturador_imagenes = practica_2.capturador_imagenes:main',
            'corrector_distorsion = practica_2.corrector_distorsion:main',
        ],
    },
)
