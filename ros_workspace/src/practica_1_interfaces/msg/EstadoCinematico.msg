# Estado cinemático de las articulaciones del brazo en un instante.
# Agrupa en un único mensaje la posición (leída de /joint_states) y la velocidad y
# aceleración calculadas a partir de ella, para que quien lo reciba tenga las tres
# magnitudes de la misma muestra sin tener que sincronizar varios topics.

# Marca de tiempo de la lectura de /joint_states de la que salen los datos
std_msgs/Header header

# Nombre de cada articulación. Los tres arrays siguientes van en este mismo orden
string[] nombres

float64[] posicion     # [rad]
float64[] velocidad    # [rad/s]
float64[] aceleracion  # [rad/s^2]
