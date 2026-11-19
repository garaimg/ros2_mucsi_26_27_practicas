"""Carga la calibración generada por camera_calibration y corrige la distorsión."""

from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
import yaml

# Con alpha = 0 la imagen corregida se recorta para que todos sus píxeles sean válidos
# (sin bordes negros); con alpha = 1 se conservan todos los píxeles de la original
ALPHA_SIN_BORDES = 0.0


class CalibracionCamara:
    """Parámetros intrínsecos de una cámara y corrección de su distorsión.

    Lee el fichero YAML que guarda camera_calibration (ost.yaml), el mismo formato que
    usa camera_info_manager, y prepara los mapas de OpenCV para quitar la distorsión
    de las imágenes de esa cámara.

    Attributes:
        tamano_imagen: (ancho, alto) en píxeles de las imágenes calibradas.
        matriz_camara: matriz intrínseca K (3x3) de la imagen original.
        coeficientes_distorsion: coeficientes de distorsión (k1, k2, p1, p2, k3).
        matriz_corregida: matriz intrínseca de la imagen ya corregida. Es la que hay
            que usar para cualquier cálculo geométrico sobre la imagen corregida,
            que ya no tiene distorsión.
    """

    def __init__(self, tamano_imagen: Tuple[int, int], matriz_camara: np.ndarray,
                 coeficientes_distorsion: np.ndarray,
                 alpha: float = ALPHA_SIN_BORDES) -> None:
        """Calcula la matriz corregida y los mapas de corrección.

        Args:
            tamano_imagen: (ancho, alto) en píxeles de las imágenes de la cámara.
            matriz_camara: matriz intrínseca K (3x3).
            coeficientes_distorsion: coeficientes de distorsión de OpenCV.
            alpha: entre 0 (recorta los bordes negros) y 1 (conserva toda la imagen).
        """
        self.tamano_imagen = tamano_imagen
        self.matriz_camara = matriz_camara
        self.coeficientes_distorsion = coeficientes_distorsion
        self.matriz_corregida, _ = cv2.getOptimalNewCameraMatrix(
            matriz_camara, coeficientes_distorsion, tamano_imagen, alpha, tamano_imagen)
        # Los mapas dicen, para cada píxel de la imagen corregida, de qué punto de la
        # original sale. Se calculan una vez aquí porque cv2.undistort los recalcularía
        # en cada imagen, y con remap la corrección es mucho más rápida
        self._mapa_x, self._mapa_y = cv2.initUndistortRectifyMap(
            matriz_camara, coeficientes_distorsion, None, self.matriz_corregida,
            tamano_imagen, cv2.CV_32FC1)

    @classmethod
    def desde_yaml(cls, ruta: Path, alpha: float = ALPHA_SIN_BORDES) -> 'CalibracionCamara':
        """Crea la calibración a partir del YAML guardado por camera_calibration.

        Args:
            ruta: fichero YAML con image_width, image_height, camera_matrix y
                distortion_coefficients.
            alpha: entre 0 (recorta los bordes negros) y 1 (conserva toda la imagen).

        Returns:
            La calibración lista para corregir imágenes.

        Raises:
            FileNotFoundError: si el fichero no existe (falta calibrar la cámara).
        """
        with open(ruta) as fichero:
            datos = yaml.safe_load(fichero)
        tamano_imagen = (int(datos['image_width']), int(datos['image_height']))
        matriz_camara = cls._leer_matriz(datos['camera_matrix'])
        coeficientes_distorsion = cls._leer_matriz(datos['distortion_coefficients'])
        return cls(tamano_imagen, matriz_camara, coeficientes_distorsion, alpha)

    def corregir(self, imagen: np.ndarray) -> np.ndarray:
        """Quita la distorsión de una imagen de la cámara.

        Args:
            imagen: imagen original de OpenCV, del tamaño con el que se calibró.

        Returns:
            Imagen corregida, del mismo tamaño. Su matriz intrínseca es
            `matriz_corregida` y ya no tiene distorsión.

        Raises:
            ValueError: si la imagen no tiene el tamaño de la calibración. Los
                parámetros dependen de la resolución, así que no se pueden aplicar
                a otra distinta.
        """
        alto, ancho = imagen.shape[:2]
        if (ancho, alto) != self.tamano_imagen:
            raise ValueError(
                f'La imagen es de {ancho}x{alto} y la calibración de '
                f'{self.tamano_imagen[0]}x{self.tamano_imagen[1]}')
        return cv2.remap(imagen, self._mapa_x, self._mapa_y, cv2.INTER_LINEAR)

    @staticmethod
    def _leer_matriz(datos_matriz: dict) -> np.ndarray:
        """Convierte una matriz del YAML (rows, cols, data) en un array de numpy.

        Args:
            datos_matriz: diccionario con 'rows', 'cols' y 'data' (lista plana).

        Returns:
            Array de tamaño rows x cols con los datos en float64.
        """
        return np.array(datos_matriz['data'], dtype=np.float64).reshape(
            datos_matriz['rows'], datos_matriz['cols'])
