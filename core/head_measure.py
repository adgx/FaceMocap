# Misure anatomiche del modello per "Genera Armatura su Modello".
#
# Le coordinate del template (_TABELLA, BONE_SHAPES) sono normalizzate sul bbox
# del modello di riferimento, che e' quasi solo viso. Su un modello con collo e
# spalle il bbox e' dominato dal busto: normalizzare su quello stira il rig
# verso il basso e lo allarga quanto le spalle. Qui si misurano sulla mesh i
# punti che il template da' per scontati (mento, punta del naso, occhi, cima
# del cranio) e si costruisce una mappatura template -> mondo che li fa
# coincidere.
#
# Tutto e' in coordinate MONDO: mesh_obj.dimensions e' nello spazio locale, e
# su un modello importato ruotato (Y-up) scambia altezza e profondita'.

import bmesh
import numpy as np
from mathutils import Vector

from . import config
from .weights import _extent, _islands

# Punti di riferimento nelle coordinate del template.
T_MENTO_Z = config.BONE_SHAPES["Jaw"][1][2]
T_CIMA_Z = 1.0 - 2.0 * config.GENERATOR_Z_OFFSET
T_NASO_Y = config.FACE_MAPPING["Head"].position[1]
T_OCCHIO_X = config.FACE_MAPPING["Eye.L"].position[0]
T_OCCHIO_Z = config.FACE_MAPPING["Eye.L"].position[2]
# l'ancora di Eye e' il centro dell'iride, cioe' la parte anteriore del bulbo
T_OCCHIO_Y = config.FACE_MAPPING["Eye.L"].position[1]


def _lineare(v, xs, ys):
    """Interpolazione lineare a tratti, estrapolata oltre gli estremi."""
    i = np.clip(np.searchsorted(xs, v) - 1, 0, len(xs) - 2)
    return ys[i] + (v - xs[i]) * (ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i])


def _vettore(a):
    return Vector(tuple(float(c) for c in a))


class Mappa:
    """Template -> mondo: lineare in X, lineare a tratti in Y e Z.

    In Z i nodi sono mento, occhi (se trovati) e cima del cranio; in Y punta
    del naso e parte anteriore dei bulbi. Un viso con la fronte alta, il mento
    corto o gli occhi infossati si adatta per segmenti invece di stirarsi
    tutto insieme: con un solo fattore in Y, su un naso pronunciato palpebre e
    bocca finiscono davanti alla pelle e il bone heat non le pesa.
    """

    def __init__(self, x0, sx, y_template, y_mondo, z_template, z_mondo):
        self.x0, self.sx = float(x0), float(sx)
        self.yt = np.asarray(y_template, dtype=float)
        self.yw = np.asarray(y_mondo, dtype=float)
        self.zt = np.asarray(z_template, dtype=float)
        self.zw = np.asarray(z_mondo, dtype=float)

    def to_world_array(self, a):
        a = np.asarray(a, dtype=float)
        out = np.empty_like(a)
        out[:, 0] = self.x0 + a[:, 0] * self.sx
        out[:, 1] = _lineare(a[:, 1], self.yt, self.yw)
        out[:, 2] = _lineare(a[:, 2], self.zt, self.zw)
        return out

    def from_world_array(self, w):
        w = np.asarray(w, dtype=float)
        out = np.empty_like(w)
        out[:, 0] = (w[:, 0] - self.x0) / self.sx
        out[:, 1] = _lineare(w[:, 1], self.yw, self.yt)
        out[:, 2] = _lineare(w[:, 2], self.zw, self.zt)
        return out

    def to_world(self, p):
        return _vettore(self.to_world_array([tuple(p)])[0])

    def from_world(self, w):
        return _vettore(self.from_world_array([tuple(w)])[0])


class Misura:
    """Esito della misura: la mappatura e i punti anatomici che l'hanno decisa."""

    def __init__(self, modo, mappa, altezza):
        self.modo = modo            # "testa" oppure "bbox"
        self.mappa = mappa
        self.altezza = altezza      # altezza della mesh, per le code di ripiego
        self.note = []
        self.naso = None
        self.mento_z = None
        self.cima_z = None
        self.occhi = None           # (scostamento x dal centro, z, y anteriore) o None
        self.collo_base = None      # punto mondo, None se il collo non c'e'
        self.collo_y = None
        self.torace_base = None     # punto mondo, None se sotto il collo non c'e' busto

    def righe(self):
        """Resoconto leggibile, in coordinate mondo."""
        def v(p):
            return "(%.4f, %.4f, %.4f)" % tuple(p)

        if self.modo == "testa":
            righe = ["modo          : testa (collo riconosciuto, normalizzazione sul viso)"]
        else:
            righe = ["modo          : bbox (generatore classico, normalizzazione sulla mesh intera)"]
        if self.cima_z is not None:
            righe.append("cima cranio z : %.4f" % self.cima_z)
        if self.mento_z is not None:
            righe.append("mento z       : %.4f   altezza testa %.4f"
                         % (self.mento_z, self.cima_z - self.mento_z))
        if self.naso is not None:
            righe.append("punta naso    : %s" % v(self.naso))
        if self.modo == "testa":
            if self.occhi is not None:
                righe.append("occhi (bulbi) : +-%.4f dal centro, z %.4f, fronte y %.4f"
                             % self.occhi)
            else:
                righe.append("occhi (bulbi) : non trovati")
        if self.collo_base is not None:
            righe.append("base collo    : %s" % v(self.collo_base))
        if self.torace_base is not None:
            righe.append("base torace   : %s" % v(self.torace_base))
        m = self.mappa
        righe.append("mappa         : x = %.4f + %.4f*t" % (m.x0, m.sx))
        righe.append("               y a tratti, template %s -> mondo %s"
                     % (np.round(m.yt, 3).tolist(), np.round(m.yw, 4).tolist()))
        righe.append("               z a tratti, template %s -> mondo %s"
                     % (np.round(m.zt, 3).tolist(), np.round(m.zw, 4).tolist()))
        righe += ["nota          : %s" % n for n in self.note]
        return righe


# --- lettura della mesh -------------------------------------------------------

def world_vertices(mesh_obj):
    """Array (n, 3) dei vertici in coordinate mondo."""
    n = len(mesh_obj.data.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    mesh_obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    m = np.array(mesh_obj.matrix_world, dtype=np.float64)
    return co @ m[:3, :3].T + m[:3, 3]


def rigid_islands(mesh_obj):
    """[(centro_mondo, diagonale, y_anteriore)] dei pezzi staccati, la parte
    principale esclusa.

    Stesso ordinamento del binder (_split_islands): i pezzi rigidi sono quelli
    che non ricevono il bone heat, e fra questi stanno i bulbi oculari.
    """
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    try:
        gruppi = _islands(bm)
        if len(gruppi) < 2:
            return []
        gruppi.sort(key=_extent, reverse=True)
        m = np.array(mesh_obj.matrix_world, dtype=np.float64)
        isole = []
        for gruppo in gruppi[1:]:
            co = np.array([v.co[:] for v in gruppo]) @ m[:3, :3].T + m[:3, 3]
            lo, hi = co.min(0), co.max(0)
            isole.append(((lo + hi) * 0.5, float(np.linalg.norm(hi - lo)), float(lo[1])))
        return isole
    finally:
        bm.free()


def nearby_parts(mesh_obj, objects):
    """[(centro_mondo, diagonale, y_anteriore)] delle altre mesh piccole dentro il modello.

    Molti modelli hanno bulbi, denti e lingua come oggetti a parte invece che
    come pezzi staccati della stessa mesh: per la ricerca degli occhi contano
    allo stesso modo. Basta il bbox di ogni oggetto.
    """
    def angoli(obj):
        m = np.array(obj.matrix_world, dtype=np.float64)
        return np.array([tuple(c) for c in obj.bound_box]) @ m[:3, :3].T + m[:3, 3]

    box = angoli(mesh_obj)
    lo, hi = box.min(0), box.max(0)
    diag = float(np.linalg.norm(hi - lo))
    parti = []
    for obj in objects:
        if obj is mesh_obj or obj.type != 'MESH' or not len(obj.data.vertices):
            continue
        c = angoli(obj)
        c_lo, c_hi = c.min(0), c.max(0)
        centro = (c_lo + c_hi) * 0.5
        d = float(np.linalg.norm(c_hi - c_lo))
        if d < 0.5 * diag and np.all(centro > lo) and np.all(centro < hi):
            parti.append((centro, d, float(c_lo[1])))
    return parti


def misura_modello(mesh_obj, objects=()):
    """objects: le altre mesh della scena, fra cui cercare occhi separati."""
    return misura(world_vertices(mesh_obj),
                  rigid_islands(mesh_obj) + nearby_parts(mesh_obj, objects))


# --- misura ------------------------------------------------------------------

def misura(verts, isole=()):
    """Misura una nuvola di vertici in coordinate mondo.

    Se trova mento e collo normalizza sulla testa; altrimenti ricade sul
    generatore classico (bbox intero), che e' quello con cui e' stato tarato
    il template ed e' giusto per un modello che e' solo viso.
    """
    lo, hi = verts.min(0), verts.max(0)
    esito, motivo = _misura_testa(verts, isole, lo, hi)
    if esito is not None:
        return esito
    classica = _misura_bbox(lo, hi)
    classica.note.append(motivo)
    return classica


def _misura_bbox(lo, hi):
    """La mappatura storica: centro del bbox alzato di GENERATOR_Z_OFFSET."""
    dims = hi - lo
    semi = np.where(dims > 1e-9, dims * 0.5, 1.0)
    centro = (lo + hi) * 0.5
    centro[2] += dims[2] * config.GENERATOR_Z_OFFSET
    mappa = Mappa(centro[0], semi[0],
                  (-1.0, 1.0), (centro[1] - semi[1], centro[1] + semi[1]),
                  (-1.0, 1.0), (centro[2] - semi[2], centro[2] + semi[2]))
    return Misura("bbox", mappa, float(dims[2]))


def _misura_testa(verts, isole, lo, hi):
    """(Misura, None) se il modello ha un collo, altrimenti (None, motivo)."""
    x, y, z = verts[:, 0], verts[:, 1], verts[:, 2]
    altezza = hi[2] - lo[2]
    if altezza < 1e-9:
        return None, "mesh piatta in altezza"

    # Punta del naso: il punto piu' avanzato vicino alla linea mediana.
    cx0 = (lo[0] + hi[0]) * 0.5
    mediana = np.abs(x - cx0) < 0.05 * (hi[0] - lo[0])
    candidati = verts[mediana] if mediana.any() else verts
    naso = candidati[np.argmin(candidati[:, 1])]

    larghezza_su = np.ptp(x[z >= naso[2]])
    if larghezza_su < 1e-9:
        return None, "nessun volume sopra il naso"

    # Mento: scendendo dal naso, la prima quota in cui il bordo anteriore
    # arretra oltre la soglia, per due fasce di fila (una sola puo' essere una
    # fascia con pochi vertici, tutti sulla nuca).
    soglia_y = naso[1] + config.GENERATOR_CHIN_RECESS * larghezza_su
    passo = altezza * config.GENERATOR_BAND
    gola = None
    inizio = None
    arretrate = 0
    k = 0
    while naso[2] - k * passo > lo[2]:
        alto = naso[2] - k * passo
        k += 1
        sel = (z <= alto) & (z > alto - passo)
        if not sel.any():
            continue
        if y[sel].min() > soglia_y:
            arretrate += 1
            if arretrate == 1:
                inizio = alto
            if arretrate == 2:
                gola = inizio
                break
        else:
            arretrate = 0
    if gola is None:
        return None, ("sotto il naso il profilo non arretra: nessun collo, "
                      "uso il bbox intero")

    faccia = (z < naso[2]) & (z > gola) & (y < soglia_y)
    mento_z = float(z[faccia].min()) if faccia.any() else float(gola)
    cima_z = float(hi[2])
    altezza_testa = cima_z - mento_z
    quota_collo = (mento_z - lo[2]) / altezza_testa
    if quota_collo < config.GENERATOR_MIN_NECK:
        return None, ("sotto il mento c'e' il %.0f%% dell'altezza della testa, "
                      "meno del %.0f%%: lo tratto come un modello senza collo"
                      % (quota_collo * 100, config.GENERATOR_MIN_NECK * 100))

    testa = verts[z > mento_z]
    cx = (testa[:, 0].min() + testa[:, 0].max()) * 0.5
    semi_testa = np.ptp(testa[:, 0]) * 0.5

    note = []
    occhi = _occhi(isole, cx, semi_testa, mento_z, cima_z)
    if occhi is not None:
        sx = occhi[0] / T_OCCHIO_X
        zt = (T_MENTO_Z, T_OCCHIO_Z, T_CIMA_Z)
        zw = (mento_z, occhi[1], cima_z)
    else:
        sx = semi_testa
        zt = (T_MENTO_Z, T_CIMA_Z)
        zw = (mento_z, cima_z)
        note.append("bulbi oculari non trovati (ne' pezzi staccati ne' oggetti "
                    "separati): larghezza presa dal cranio, orecchie comprese. "
                    "Controlla gli occhi")
    # In Y la punta del naso del template cade su quella misurata. Con gli
    # occhi anche la parte anteriore dei bulbi cade su quella misurata, e oltre
    # si prosegue con la stessa pendenza: e' la profondita' di palpebre, angoli
    # della bocca e mandibola, che un solo fattore dal naso sbaglia di molto.
    if occhi is not None and occhi[2] > naso[1]:
        pendenza = (occhi[2] - naso[1]) / (T_OCCHIO_Y - T_NASO_Y)
        yt = (T_NASO_Y, T_OCCHIO_Y, T_OCCHIO_Y + 1.0)
        yw = (naso[1], occhi[2], occhi[2] + pendenza)
    else:
        sy = sx * config.GENERATOR_REF_ASPECT_YX
        yt = (T_NASO_Y, T_NASO_Y + 1.0)
        yw = (naso[1], naso[1] + sy)

    esito = Misura("testa", Mappa(cx, sx, yt, yw, zt, zw), float(altezza))
    esito.note = note
    esito.naso = naso
    esito.mento_z = mento_z
    esito.cima_z = cima_z
    esito.occhi = occhi
    _misura_collo(esito, verts, cx, lo, passo, altezza_testa)
    return esito, None


def _occhi(isole, cx, semi, z_min, z_max):
    """(scostamento x, z, y anteriore) della coppia di bulbi oculari, o None.

    Due pezzi staccati simili, ai due lati del centro, alla stessa altezza e
    dentro la testa: denti e lingua stanno al centro, e un orecchino da solo
    non fa coppia.
    """
    cand = [(c, d, fy) for c, d, fy in isole
            if abs(c[0] - cx) > 0.1 * semi and z_min < c[2] < z_max]
    cand.sort(key=lambda t: t[1], reverse=True)
    if len(cand) < 2:
        return None
    (a, da, fa), (b, db, fb) = cand[:2]
    if (a[0] - cx) * (b[0] - cx) >= 0.0:
        return None
    if abs(a[2] - b[2]) > 0.1 * (z_max - z_min) or min(da, db) < 0.5 * max(da, db):
        return None
    return ((abs(a[0] - cx) + abs(b[0] - cx)) * 0.5, (a[2] + b[2]) * 0.5,
            (fa + fb) * 0.5)


def _misura_collo(esito, verts, cx, lo, passo, altezza_testa):
    """Strozzatura e base del collo, base del torace."""
    x, y, z = verts[:, 0], verts[:, 1], verts[:, 2]
    fondo = max(lo[2], esito.mento_z - 0.5 * altezza_testa)

    fasce = []      # (alto, basso, larghezza, y_centro)
    alto = esito.mento_z
    while alto > fondo:
        sel = (z <= alto) & (z > alto - passo)
        if np.count_nonzero(sel) >= 3:
            fasce.append((alto, alto - passo, float(np.ptp(x[sel])),
                          float((y[sel].min() + y[sel].max()) * 0.5)))
        alto -= passo
    if not fasce:
        esito.note.append("nessuna fascia misurabile sotto il mento: niente collo")
        return

    i_stretta = min(range(len(fasce)), key=lambda i: fasce[i][2])
    stretta = fasce[i_stretta]
    base_z = fasce[-1][1]
    for fascia in fasce[i_stretta + 1:]:
        if fascia[2] > config.GENERATOR_NECK_FLARE * stretta[2]:
            base_z = fascia[0]
            break

    esito.collo_y = stretta[3]
    esito.collo_base = np.array((cx, stretta[3], base_z))
    if base_z - lo[2] > 0.05 * altezza_testa:
        esito.torace_base = np.array((cx, stretta[3], lo[2]))
