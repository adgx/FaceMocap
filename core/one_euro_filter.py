import math
import time
from mathutils import Vector, Quaternion

def smoothing_factor(dt, cutoff):
    """Calcola il fattore di smoothing (alpha) basato sul tempo e la frequenza di taglio."""
    r = 2.0 * math.pi * cutoff * dt
    return r / (r + 1.0)

class OneEuroFilter:
    """1Euro filter per Vector.

    velocity_scale: quante unita' del segnale corrispondono a una larghezza di
    viso. La velocita' usata per il cutoff dinamico viene divisa per questo
    valore, cosi' beta ha lo stesso effetto su qualunque rig e con qualunque gain.
    """
    def __init__(self, min_cutoff=1.0, beta=0.3, d_cutoff=1.0, velocity_scale=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.velocity_scale = velocity_scale
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

    def filter(self, x: Vector, t: float = None) -> Vector:
        if t is None:
            t = time.perf_counter()

        # Inizializzazione al primo frame (nessun filtraggio per evitare scatti)
        if self.t_prev is None:
            self.x_prev = x.copy()
            self.dx_prev = Vector((0.0, 0.0, 0.0))
            self.t_prev = t
            return x.copy()

        dt = t - self.t_prev
        if dt <= 0.0:
            return self.x_prev.copy()

        # stima della velocità
        dx = (x - self.x_prev) / dt
        alpha_d = smoothing_factor(dt, self.d_cutoff)
        dx_hat = self.dx_prev.lerp(dx, alpha_d)

        #calcolo della frequenza di taglio dinamica basata sulla velocità (normalizzata)
        speed = dx_hat.length / max(abs(self.velocity_scale), 1e-9)
        cutoff = self.min_cutoff + self.beta * speed

        # filtraggio finale
        alpha = smoothing_factor(dt, cutoff)
        x_hat = self.x_prev.lerp(x, alpha)

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t

        return x_hat.copy()


class OneEuroFilterQuaternion:
    def __init__(self, min_cutoff=1.0, beta=0.3, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.q_prev = None
        self.dq_prev = Vector((0.0, 0.0, 0.0))
        self.t_prev = None

    def filter(self, q: Quaternion, t: float = None) -> Quaternion:
        if t is None:
            t = time.perf_counter()

        if self.t_prev is None:
            self.q_prev = q.copy()
            self.dq_prev = Vector((0.0, 0.0, 0.0))
            self.t_prev = t
            return q.copy()

        dt = t - self.t_prev
        if dt <= 0.0:
            return self.q_prev.copy()

        # Assicura il percorso di rotazione più breve (gestione della doppia copertura)
        q_target = q.copy()
        if self.q_prev.dot(q_target) < 0.0:
            q_target.negate()

        # stima della velocità angolare come vettore (asse * rad/s): a differenza
        # del solo modulo, il rumore in direzioni opposte si compensa nella media
        diff = self.q_prev.rotation_difference(q_target)
        axis, angle = diff.to_axis_angle()
        if angle > math.pi:
            angle -= 2.0 * math.pi
        ang_vel = axis * (angle / dt)

        alpha_d = smoothing_factor(dt, self.d_cutoff)
        dq_hat = self.dq_prev.lerp(ang_vel, alpha_d)

        cutoff = self.min_cutoff + self.beta * dq_hat.length

        # filtraggio finale
        alpha = smoothing_factor(dt, cutoff)
        q_hat = self.q_prev.slerp(q_target, alpha)

        self.q_prev = q_hat
        self.dq_prev = dq_hat
        self.t_prev = t

        return q_hat.copy()
