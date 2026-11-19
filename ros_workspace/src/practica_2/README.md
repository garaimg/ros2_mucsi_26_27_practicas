# Práctica 2: Ingesta, calibración y procesamiento de imágenes

Paquete de ROS 2 Jazzy que:

1. **Publica** la imagen de una cámara USB con `usb_cam` y la muestra con `rqt_image_view`.
2. **Ingiere y guarda 10 imágenes** distintas entre sí con un suscriptor propio.
3. **Calibra** la cámara con `camera_calibration` y un tablero de ajedrez.
4. **Aplica la calibración** a la imagen con OpenCV, convirtiendo `Image` ↔ OpenCV con `cv_bridge`.

## Contenido del paquete

```
practica_2/
├── config/
│   └── calibracion_camara.yaml      # Resultado de la calibración (paso 4)
├── launch/
│   ├── camara.launch.py             # usb_cam + rqt_image_view
│   └── practica_2.launch.py         # cámara + visor + corrección de la distorsión
└── practica_2/
    ├── calibracion_camara.py        # Clase que lee el YAML de calibración y corrige la distorsión
    ├── capturador_imagenes.py       # Nodo suscriptor: guarda 10 imágenes distintas
    └── corrector_distorsion.py      # Nodo que aplica la calibración y publica /imagen_corregida
```

| Nodo | Se suscribe a | Publica / guarda |
|---|---|---|
| `usb_cam` (desde `camara.launch.py`) | la cámara (`/dev/video0`) | `/usb_cam/image_raw`, `/usb_cam/camera_info` |
| `capturador_imagenes` | `/usb_cam/image_raw` | PNG en `~/ros_workspace/imagenes_practica_2/` |
| `corrector_distorsion` | `/usb_cam/image_raw` | `/imagen_corregida` |

## Qué hace falta

- Una **cámara USB**.
- Un **tablero de ajedrez impreso** para calibrar, pegado a algo rígido y plano (un cartón o una carpeta). Si está doblado, la calibración sale mal.
- **Docker** y este repositorio. `camera_calibration` no viene en la imagen original del profesor; está añadido a los Dockerfiles (`ros-jazzy-camera-calibration`) y se instala al construir la imagen.

---

## Paso 0: conectar la cámara al contenedor

### 0.1 Pasar la cámara a WSL (solo en Windows)

WSL no ve las cámaras USB por defecto. Se le pasan con [usbipd-win](https://github.com/dorssel/usbipd-win).

**Solo la primera vez**, en PowerShell **como administrador**:

```powershell
winget install --exact --id dorssel.usbipd-win
```

Cierra esa terminal y abre otra como administrador:

```powershell
usbipd list
```

Busca la línea de la cámara (por ejemplo, `2-1  32e4:0577  HD USB Camera`) y comparte su BUSID:

```powershell
usbipd bind --busid 2-1
```

**Cada vez** que se conecte la cámara o se reinicie el ordenador (no hace falta ser administrador):

```powershell
usbipd attach --wsl --busid 2-1
```

Comprueba en WSL que aparece:

```bash
ls /dev/video*
```

Debe salir `/dev/video0`; la misma cámara suele crear también `/dev/video1`, que es de metadatos y no se usa. Mientras la cámara está en WSL, Windows no puede usarla. Para devolvérsela: `usbipd detach --busid 2-1`.

En Linux nativo este paso no hace falta: la cámara ya está en `/dev/video0`.

### 0.2 Arrancar el contenedor con acceso a la cámara

Un contenedor solo ve los dispositivos que se le pasan **al crearlo**. El fichero `docker-compose.camara.yml` añade `/dev/video0` al contenedor `desktop`. Desde la raíz del repositorio:

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.camara.yml ./lab.sh iniciar
```

Es el mismo `./lab.sh iniciar` del README del repositorio base: `lab.sh` llama a `docker compose` sin indicar fichero, así que respeta `COMPOSE_FILE`.

La primera vez construye la imagen, que tarda un rato. Luego abre el escritorio en el navegador (`http://localhost:6081`, contraseña `laboratorio`).

- Si la cámara es otro dispositivo: `CAMARA=/dev/video2 COMPOSE_FILE=docker-compose.yml:docker-compose.camara.yml ./lab.sh iniciar`.
- Si después se usa `./lab.sh iniciar` sin `COMPOSE_FILE`, el contenedor se recrea **sin** la cámara.
- En los PCs del laboratorio (`./lab.sh iniciar --lab` o `--lab-gpu`) el contenedor es privilegiado y ya ve la cámara, así que no hace falta el fichero extra.

### 0.3 Compilar y abrir terminales

```bash
./lab.sh compilar
```

Los comandos `ros2` de los pasos siguientes se ejecutan **dentro del contenedor**. Cada terminal se abre así:

```bash
./lab.sh terminal
```

---

## Paso 1: publicar y ver la imagen de la cámara

```bash
ros2 launch practica_2 camara.launch.py
```

En el escritorio del navegador se abre `rqt_image_view` con `/usb_cam/image_raw`. Deja esta terminal abierta durante los pasos 2 a 4.

Argumentos opcionales:

| Argumento | Por defecto | Para qué |
|---|---|---|
| `dispositivo` | `/dev/video0` | Dispositivo de la cámara |
| `formato_pixel` | `mjpeg2rgb` | Formato de la cámara (`mjpeg2rgb` o `yuyv`; por usbipd solo funciona bien MJPEG) |
| `ancho`, `alto` | `640`, `480` | Resolución [px] |
| `fps` | `30.0` | Imágenes por segundo |
| `visor` | `true` | `false` para no abrir `rqt_image_view` |

Mientras no se haya calibrado, sale el aviso `Unable to open camera calibration file`. Es normal.

## Paso 2: capturar 10 imágenes distintas

Con la cámara en marcha, en otra terminal:

```bash
ros2 run practica_2 capturador_imagenes
```

**Mueve la cámara o lo que tiene delante** hasta que se guarden las 10. El nodo termina solo.

Cómo funciona: cada imagen se convierte a OpenCV con `cv_bridge` y se compara con **todas** las ya guardadas. Para la comparación se reducen, se pasan a gris y se suavizan, de modo que el ruido del sensor no cuente como cambio. Si la diferencia media de los píxeles con alguna guardada no supera `umbral_diferencia` (5,0 sobre 255), se descarta por repetida. Así las 10 son distintas entre sí. El umbral está medido con la cámara: con la escena quieta, el ruido y el ajuste automático de exposición al encenderla no llegan a 3, y al mover la cámara o el tablero se supera de sobra.

Se guardan en `ros_workspace/imagenes_practica_2/imagen_00.png` … `imagen_09.png`, que también se ven desde fuera del contenedor. Parámetros: `numero_imagenes`, `umbral_diferencia`, `directorio` y `topic_imagen`. Por ejemplo:

```bash
ros2 run practica_2 capturador_imagenes --ros-args -p umbral_diferencia:=10.0
```

## Paso 3: calibrar la cámara con el tablero de ajedrez

### 3.1 Preparar el tablero

- Imprime el tablero **al 100 %**, sin "ajustar a la página". Por ejemplo, uno de 7×9 cuadros de 25 mm en un A4.
- **Cuenta las esquinas interiores**, las que tocan 4 cuadros, no los cuadros. Un tablero de 7×9 cuadros tiene 6×8 esquinas interiores, y se pasa como `--size 8x6`. El orden da igual.
- **Mide con una regla** el lado de un cuadro. La impresora puede cambiar un poco el tamaño, y la medida se pasa **en metros**: 25 mm son `--square 0.025`.
- Pégalo a algo **rígido y plano**.

### 3.2 Lanzar el calibrador

Con la cámara del paso 1 en marcha, en otra terminal (cambia `8x6` y `0.025` por los de tu tablero):

```bash
ros2 run camera_calibration cameracalibrator --size 8x6 --square 0.025 --no-service-check --ros-args -r image:=/usb_cam/image_raw
```

`--no-service-check` evita que el calibrador exija el servicio `camera/set_camera_info`. Ese servicio solo lo usa el botón **COMMIT**, y aquí no hace falta: la calibración se guarda con **SAVE** y se copia al paquete (paso 3.5). Sin esa opción, el calibrador se cierra con `RuntimeError: no camera service available`.

En el escritorio se abre la ventana del calibrador con la imagen de la cámara. Cuando detecta el tablero, dibuja sus esquinas en colores.

### 3.3 Capturar vistas del tablero

A la derecha hay cuatro barras que se van llenando y se ponen en verde a medida que el tablero se ve en vistas variadas:

| Barra | Qué pide | Cómo conseguirla |
|---|---|---|
| **X** | posiciones de izquierda a derecha | Lleva el tablero a los bordes izquierdo y derecho |
| **Y** | posiciones de arriba a abajo | Llévalo arriba y abajo, **incluidas las esquinas** |
| **Size** | distintas distancias | Acércalo hasta que ocupe casi toda la imagen y aléjalo |
| **Skew** | inclinaciones | Inclínalo hacia los lados y hacia arriba y abajo, unos 30–45° |

Consejos:

- Mueve el tablero **despacio** y para un momento en cada posición. Con la imagen movida no detecta las esquinas.
- El tablero tiene que verse **entero**.
- Las **esquinas de la imagen** son lo más importante: es donde más distorsiona la lente y donde peor queda la corrección si faltan datos.
- Con buena luz y sin reflejos va mucho mejor. Si el papel brilla, inclínalo un poco.

### 3.4 Calibrar y guardar

1. Cuando se active el botón **CALIBRATE** (normalmente con unas 40 vistas o más), púlsalo. La ventana se queda congelada unos segundos o hasta un minuto mientras calcula.
2. Mueve el tablero y comprueba en la ventana que las líneas rectas, como los bordes del tablero, salen rectas también cerca de los bordes de la imagen. En la terminal aparece el resultado (`camera matrix`, `distortion`...).
3. Pulsa **SAVE**. Se guarda en `/tmp/calibrationdata.tar.gz`, con las imágenes usadas y el fichero `ost.yaml`.
4. Cierra el calibrador con `Ctrl+C` en su terminal.

No pulses **COMMIT**: la calibración se guarda en el paquete en el paso siguiente.

### 3.5 Copiar la calibración al paquete

```bash
mkdir -p /tmp/calibracion && tar -xzf /tmp/calibrationdata.tar.gz -C /tmp/calibracion
```
```bash
cp /tmp/calibracion/ost.yaml ~/ros_workspace/src/practica_2/config/calibracion_camara.yaml
```
```bash
cd ~/ros_workspace && colcon build --symlink-install --packages-select practica_2
```

Hay que recompilar la primera vez para que el fichero se instale con el paquete. Después, **reinicia la cámara del paso 1** (`Ctrl+C` y vuelve a lanzarla): ya no sale el aviso, y `usb_cam` publica los parámetros en `/usb_cam/camera_info`. Para comprobarlo:

```bash
ros2 topic echo /usb_cam/camera_info --once
```

La calibración vale para **esa cámara y esa resolución**. Con otra cámara o con otro `ancho`/`alto` hay que repetirla.

## Paso 4: aplicar la calibración con OpenCV

Con la cámara en marcha:

```bash
ros2 run practica_2 corrector_distorsion
```

En `rqt_image_view`, elige en el desplegable `/imagen_corregida` y compárala con `/usb_cam/image_raw`. Las líneas rectas que salían curvadas cerca de los bordes ahora salen rectas.

Cómo funciona, por cada imagen:

1. `cv_bridge` convierte el `Image` de ROS en una imagen de OpenCV.
2. `CalibracionCamara.corregir` quita la distorsión. Al arrancar se calculan una sola vez los mapas de corrección con `cv2.getOptimalNewCameraMatrix` y `cv2.initUndistortRectifyMap`; después, a cada imagen solo se le aplica `cv2.remap`, que es mucho más rápido.
3. `cv_bridge` la vuelve a convertir a `Image`, con la misma cabecera que la original, y se publica en `/imagen_corregida`.

Parámetros:

- `ruta_calibracion`: por defecto, la del paquete.
- `alpha`: con `0.0` se recortan los bordes negros que deja la corrección; con `1.0` se conserva toda la imagen original.

```bash
ros2 run practica_2 corrector_distorsion --ros-args -p alpha:=1.0
```

### Todo junto

Con la cámara ya calibrada, este launch abre la cámara, el visor y la corrección a la vez. Acepta los mismos argumentos que `camara.launch.py`:

```bash
ros2 launch practica_2 practica_2.launch.py
```

## Comprobaciones útiles

```bash
ros2 topic hz /usb_cam/image_raw
```
Muestra a cuántas imágenes por segundo llega la cámara.

```bash
ros2 run rqt_graph rqt_graph
```
Muestra el grafo: `usb_cam` → `/usb_cam/image_raw` → `capturador_imagenes` / `corrector_distorsion`.

## Al terminar

`Ctrl+C` en cada terminal y, desde la raíz del repositorio:

```bash
./lab.sh parar
```

Para devolver la cámara a Windows, en PowerShell: `usbipd detach --busid 2-1`.

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `ls /dev/video*` no muestra nada en WSL | Falta `usbipd attach --wsl --busid ...` (paso 0.1), que hay que repetir tras cada reinicio |
| `directory iterator cannot open directory ... /sys/class/video4linux` | El contenedor no ve la cámara: créalo con `COMPOSE_FILE=...` (paso 0.2) **después** de que exista `/dev/video0` |
| La imagen llega verde en su mayor parte, o no llega | Con `yuyv` por usbipd, las imágenes sin comprimir no caben en el ancho de banda y llegan incompletas. Usa `formato_pixel:=mjpeg2rgb`, que es el valor por defecto. Con la HD USB Camera, MJPEG a 640×480 da unas 22 fps completas |
| `Unable to open camera calibration file` | Todavía no se ha calibrado (paso 3). Es solo un aviso |
| `FileNotFoundError ... calibracion_camara.yaml` en `corrector_distorsion` | Falta el paso 3.5, o no se recompiló después de copiar el YAML |
| `ValueError: La imagen es de ... y la calibración de ...` | La cámara está a otra resolución que la usada al calibrar: lánzala con el mismo `ancho`/`alto` o vuelve a calibrar |
| El capturador no guarda imágenes | La escena no cambia: mueve la cámara o el objeto, o baja `umbral_diferencia` |
| El calibrador no detecta el tablero | Revisa `--size` (esquinas interiores, no cuadros), que el tablero se vea entero, la luz y que no esté doblado |
| `RuntimeError: no camera service available` al lanzar el calibrador | Falta `--no-service-check` en el comando (paso 3.2) |
| `cameracalibrator` no existe | Falta `camera_calibration`: reconstruye la imagen (paso 0.2) o instálalo con `sudo apt-get install -y ros-jazzy-camera-calibration` |
