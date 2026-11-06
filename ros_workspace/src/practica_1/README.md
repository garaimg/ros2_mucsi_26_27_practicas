# Práctica 1: Extracción y análisis de datos cinemáticos del UR3e

Este paquete mueve el robot UR3e simulado con tres trayectorias: **articular (Joint)**, **lineal** y **circular**. Mientras tanto, un nodo suscrito a `/joint_states` registra la **posición, velocidad y aceleración** de las 6 articulaciones con su marca de tiempo. Cada trayectoria se guarda en su propio CSV.

Además incluye los dos retos opcionales:

- **Mensaje personalizado:** `practica_1_interfaces/msg/EstadoCinematico` agrupa en un solo mensaje la posición, la velocidad y la aceleración. Se publica en el topic `/estado_cinematico`.
- **Ingesta inteligente:** solo se guardan datos cuando el robot se mueve, es decir, cuando alguna articulación supera 0,001 rad/s. Los periodos con el robot quieto se ignoran.

## Estructura

```
ros_workspace/
├── datos_practica_1/                     # CSV generados (uno por trayectoria)
└── src/
    ├── practica_1/
    │   ├── launch/practica_1.launch.py   # Lanza simulación + trayectorias
    │   └── practica_1/
    │       ├── control_robot.py          # Movimiento del robot con MoveIt (del ejemplo)
    │       ├── registrador_articulaciones.py  # Suscriptor: calcula, publica y guarda los datos
    │       └── ejecutor_trayectorias.py  # Ejecuta las 3 trayectorias y coordina el registro
    └── practica_1_interfaces/
        └── msg/EstadoCinematico.msg      # Mensaje personalizado
```

## Preparación

Los comandos con `./lab.sh` se ejecutan en una terminal normal desde la raíz del repositorio.

1. Arrancar el entorno. Se abre el escritorio en el navegador; la contraseña es `laboratorio`.
   ```bash
   ./lab.sh iniciar
   ```
2. Compilar. Hace falta la primera vez y después de cada cambio en los paquetes.
   ```bash
   ./lab.sh compilar
   ```

Los comandos `ros2` se ejecutan **dentro del contenedor**. Para abrir una terminal en él y cargar el workspace:

```bash
./lab.sh terminal
```
```bash
source ~/ros_workspace/install/setup.bash
```

El `source` hay que hacerlo en **cada** terminal nueva del contenedor.

## Ejecución

La práctica se puede ejecutar de dos formas.

### Opción A: `ros2 run` (simulación y programa por separado)

1. En una terminal normal, lanzar la simulación y dejarla abierta:
   ```bash
   ./lab.sh sim 203
   ```
2. En otra terminal, dentro del contenedor y con el `source` hecho, ejecutar el programa:
   ```bash
   ros2 run practica_1 ejecutor_trayectorias
   ```
3. Cuando termine, cerrar la simulación con `Ctrl+C` en la terminal del paso 1.

### Opción B: `ros2 launch` (todo con un solo comando)

1. Dentro del contenedor y con el `source` hecho:
   ```bash
   ros2 launch practica_1 practica_1.launch.py
   ```
2. Cuando salgan las tres líneas `Guardadas ...`, cerrar con `Ctrl+C`. La simulación sigue abierta hasta entonces.

Argumentos opcionales:

| Argumento | Por defecto | Para qué sirve |
|---|---|---|
| `robot` | `203` | Puesto a simular: `203`, `204`, `205` o `206` |
| `simulacion` | `true` | Con `false` no se lanza la simulación; se usa la que ya esté abierta |

Ejemplos:

```bash
ros2 launch practica_1 practica_1.launch.py robot:=205
```
```bash
ros2 launch practica_1 practica_1.launch.py simulacion:=false
```

### Diferencias entre `run` y `launch`

| | `ros2 run` | `ros2 launch` |
|---|---|---|
| Qué arranca | Solo el programa `ejecutor_trayectorias` | La simulación (RViz + MoveIt) **y** el programa |
| Simulación | Hay que lanzarla antes con `./lab.sh sim 203` | La lanza él (salvo con `simulacion:=false`) |
| Terminales | Dos: una para la simulación y otra para el programa | Una |
| Robot simulado | El que se lance con `./lab.sh sim` | Se elige con `robot:=` |
| Al terminar | El programa se cierra y la simulación sigue en su terminal | El programa se cierra y la simulación sigue hasta `Ctrl+C` |
| Cuándo usarlo | Para repetir las trayectorias varias veces sin reiniciar la simulación | Para probarlo todo de una vez |

En los dos casos el programa espera solo a que MoveIt esté listo, así que no hay que esperar a mano antes de arrancarlo.

## Qué hace el programa

Antes de cada trayectoria, el robot vuelve a una posición inicial común. Esa colocación **no se guarda**. Después ejecuta, en orden:

1. **Articular:** gira la base 45° e inclina el brazo. MoveIt elige el camino en el espacio de articulaciones. Se guarda en `articular.csv`.
2. **Lineal:** la pinza baja 10 cm en Z y luego avanza 10 cm en Y, en línea recta. Se guarda en `lineal.csv`.
3. **Circular:** la pinza da una vuelta completa de 5 cm de radio en un plano horizontal, aproximada con 36 puntos. Se guarda en `circular.csv`.

Salida esperada:

```
[registrador_articulaciones]: Guardadas ... muestras en /home/laboratorio/ros_workspace/datos_practica_1/articular.csv
[registrador_articulaciones]: Guardadas ... muestras en /home/laboratorio/ros_workspace/datos_practica_1/lineal.csv
[registrador_articulaciones]: Guardadas ... muestras en /home/laboratorio/ros_workspace/datos_practica_1/circular.csv
```

## Datos generados

Los CSV se guardan en `ros_workspace/datos_practica_1/`. Como la carpeta está montada en el contenedor, también se ven desde fuera. Cada ejecución **sobrescribe** los ficheros anteriores.

Columnas, con una fila por mensaje de `/joint_states` mientras el robot se mueve:

| Columna | Unidad |
|---|---|
| `tiempo` | s (marca de tiempo del mensaje) |
| `posicion_<articulación>` ×6 | rad |
| `velocidad_<articulación>` ×6 | rad/s |
| `aceleracion_<articulación>` ×6 | rad/s² |

La velocidad y la aceleración se calculan por diferencias finitas con una ventana de 0,05 s. Así se evitan los picos que provoca el ruido de las marcas de tiempo de la simulación.

## Comprobaciones opcionales

Todos estos comandos van dentro del contenedor, con el `source` hecho.

- **Ver el mensaje personalizado en directo.** Lánzalo antes que el programa; se queda esperando hasta que empiecen a llegar datos:
  ```bash
  ros2 topic echo /estado_cinematico practica_1_interfaces/msg/EstadoCinematico
  ```
  El topic publica siempre, también durante las colocaciones entre trayectorias. Por eso ahí se ven velocidades que no aparecen en los CSV.
- **Ver la definición del mensaje:**
  ```bash
  ros2 interface show practica_1_interfaces/msg/EstadoCinematico
  ```
- **Ver el grafo de nodos** mientras el robot se mueve:
  ```bash
  ros2 run rqt_graph rqt_graph
  ```

## Problemas que hemos tenido

- **`topic [/estado_cinematico] does not appear to be published yet`:** el programa no está en marcha. Indica el tipo del mensaje, como en las comprobaciones, para que el `echo` espere.
- **`./lab.sh compilar` falla en `practica_1_interfaces` con `failed to create symbolic link`:** quedan restos de una compilación anterior. Dentro del contenedor, ejecuta lo siguiente y vuelve a compilar:
  ```bash
  rm -rf ~/ros_workspace/build/practica_1_interfaces ~/ros_workspace/install/practica_1_interfaces
  ```
- **No lances la simulación dos veces:** con `./lab.sh sim` abierto, usa `run` o `launch` con `simulacion:=false`.
