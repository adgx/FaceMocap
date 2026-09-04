# Strumento di ispezione dello stato della scena.
#
# Senza webcam non si vede quasi nulla di cio' che serve per capire i bug del
# rig: quante isole ha davvero la mesh, dove sono finite le ossa dopo il
# posizionamento manuale, quali ossa il bone heat ha lasciato senza peso, e a
# quale osso e' stato legato ogni pezzo rigido (bulbi, denti, lingua).
# Questo operatore fotografa tutto in un colpo solo nella console di sistema,
# cosi' il ciclo di debug non passa dal riavviare la motion capture.
#
# Non modifica NIENTE, nemmeno su disco: legge e stampa soltanto.

import math
import statistics

import bmesh
import bpy
from mathutils import Vector

from ..core import config, solver
from ..core.config import FACE_MAPPING
from ..core.rig import RIG_NAME, find_rig
# Si riusano gli helper del binder e non una copia: il report deve descrivere
# esattamente le stesse isole su cui ragiona bind_by_islands, altrimenti si
# finisce a confrontare due suddivisioni diverse e la diagnosi non vale nulla.
from ..core.weights import RIGID_ISLAND_BONE, _extent, _islands

# Soglia sotto la quale un peso e' rumore del bone heat e non deformazione
# vera. E' la stessa usata da _empty_deform_groups in import_model.py.
PESO_MINIMO = 0.01

# Scarto oltre il quale la posizione verticale di un osso viene segnalata.
# Volutamente largo: FACE_MAPPING descrive un viso IDEALE, e un modello
# stilizzato puo' discostarsene parecchio restando corretto. Serve a dire
# "guarda qui", non a emettere un verdetto.
SCARTO_VERTICALE = 0.04

# Scostamento minimo dal piano sagittale, in frazione della larghezza della
# mesh, perche' un'isola rigida sia presa per un bulbo oculare. I bulbi stanno
# in coppia ai lati; denti, lingua e cavita' orale stanno al centro e non
# devono entrare nella stima della linea degli occhi.
MIN_SCOSTAMENTO_BULBO = 0.05


# --- formattazione -----------------------------------------------------------

def _vec(v, cifre=4):
    """Vettore su una riga sola, con abbastanza cifre da vedere i millimetri."""
    return "(%.*f, %.*f, %.*f)" % (cifre, v.x, cifre, v.y, cifre, v.z)


def _bbox(punti):
    """(minimo, massimo, centro, diagonale) di una nuvola di punti.

    Ritorna None sulla nuvola vuota: capita con isole degeneri o mesh vuote.
    """
    if not punti:
        return None
    minimo = Vector((min(p.x for p in punti),
                     min(p.y for p in punti),
                     min(p.z for p in punti)))
    massimo = Vector((max(p.x for p in punti),
                      max(p.y for p in punti),
                      max(p.z for p in punti)))
    return minimo, massimo, (minimo + massimo) * 0.5, (massimo - minimo).length


# --- raccolta dati -----------------------------------------------------------

def _matrice_verso_armatura(mesh_obj, arm_obj):
    """Trasformazione dalle coordinate locali della mesh allo spazio armatura.

    E' lo spazio in cui vivono gli head_local delle ossa e in cui vale la
    convenzione del rig (Z su, -Y avanti): confrontare bbox e ossa misurati in
    spazi diversi e' l'errore piu' facile da fare qui.
    Senza armatura si ripiega sullo spazio mondo, e il report lo dichiara.
    """
    if arm_obj is None:
        return mesh_obj.matrix_world.copy()
    return arm_obj.matrix_world.inverted() @ mesh_obj.matrix_world


def _pesi_per_vertice(mesh_obj):
    """{indice_vertice: {nome_gruppo: peso}} per la mesh indicata.

    Si passa dai nomi e non dagli indici di gruppo perche' il confronto utile
    e' con i nomi delle ossa, e gli indici cambiano da mesh a mesh.
    """
    nomi = {vg.index: vg.name for vg in mesh_obj.vertex_groups}
    pesi = {}
    for vert in mesh_obj.data.vertices:
        riga = {}
        for g in vert.groups:
            nome = nomi.get(g.group)
            if nome is not None and g.weight > 0.0:
                riga[nome] = g.weight
        if riga:
            pesi[vert.index] = riga
    return pesi


def _isole_mesh(mesh_obj, to_arm):
    """Isole della mesh, ordinate come le ordina il binder.

    L'ordine e' quello di _split_islands (diagonale in spazio LOCALE,
    decrescente): l'isola 0 e' quella che riceve il bone heat, le altre sono
    quelle trattate come rigide.
    """
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)

    gruppi = _islands(bm)
    gruppi.sort(key=_extent, reverse=True)

    isole = []
    for gruppo in gruppi:
        box = _bbox([to_arm @ v.co for v in gruppo])
        isole.append({
            "indici": [v.index for v in gruppo],
            "n_vertici": len(gruppo),
            "centro": box[2] if box else Vector(),
            "diagonale": box[3] if box else 0.0,
        })

    bm.free()
    return isole


def _osso_dominante(isola, pesi, nomi_ossa):
    """(nome_osso, quota) dell'osso che si prende piu' peso sull'isola.

    E' il modo per sapere DAVVERO a chi e' finita l'isola: il binder non lascia
    traccia della scelta. Sui pezzi rigidi il peso e' 1.0 su un osso solo,
    quindi la quota vale 100% e la lettura e' immediata.
    """
    totali = {}
    for indice in isola["indici"]:
        for nome, peso in pesi.get(indice, {}).items():
            if nome in nomi_ossa:
                totali[nome] = totali.get(nome, 0.0) + peso

    if not totali:
        return None, 0.0

    somma = sum(totali.values())
    migliore = max(totali, key=totali.get)
    return migliore, (totali[migliore] / somma if somma > 0.0 else 0.0)


def _modificatori_armatura(mesh_obj):
    """Modificatori Armature della mesh e oggetto a cui puntano."""
    return [(m.name, m.object.name if m.object else "NESSUN OGGETTO")
            for m in mesh_obj.modifiers if m.type == 'ARMATURE']


# --- riferimento verticale del viso ------------------------------------------
#
# Il fondo del bbox NON e' il mento: su un modello con il collo (e a maggior
# ragione con le spalle) sta parecchio piu' in basso, e ogni frazione calcolata
# su z_min..z_max risulta schiacciata verso il basso. Il mento va quindi
# ricavato dalla geometria, non assunto.

def _stima_mento(arm_obj, dati):
    """Riferimento verticale del viso: mento, cima, metodo usato.

    Ritorna un dizionario con z_mento (None se non stimabile), z_cima, z_base,
    z_occhi, altezza del collo scartata e la descrizione del metodo. Ritorna
    None se nella scena non c'e' proprio niente da misurare.

    Due strade, in ordine di affidabilita':
      1. l'ancora di Jaw, se il rig e' stato riparato: li' il mento non e'
         stimato, e' il punto che l'utente ha posizionato a mano;
      2. la linea degli occhi, presa dal centro dei bulbi (le isole rigide
         fuori asse), piu' la regola anatomica per cui gli occhi cadono a meta'
         fra mento e cima del cranio: chin = 2*z_occhi - z_cima.
    """
    if not dati:
        return None

    # La mesh di riferimento e' la piu' grande: su un modello con i bulbi come
    # oggetti separati, prendere la prima darebbe le misure di un bulbo.
    principale = max(dati, key=lambda i: i["bbox"][3] if i["bbox"] else 0.0)
    box = principale["bbox"]
    if box is None or box[3] < 1e-6:
        return None
    minimo, massimo, centro, _diagonale = box

    esito = {
        "z_base": minimo.z,
        "z_cima": massimo.z,
        "z_mento": None,
        "z_occhi": None,
        "metodo": "",
        "avvisi": [],
    }

    if arm_obj is not None:
        osso = arm_obj.data.bones.get("Jaw")
        ancora = osso.get("fm_anchor") if osso is not None else None
        if ancora is not None and len(ancora) == 3:
            esito["z_mento"] = float(ancora[2])
            esito["metodo"] = ("ancora di Jaw (fm_anchor): misurato sul rig, "
                               "non stimato")
            _controlla_mento(esito)
            return esito

    # Isole rigide fuori asse = i due bulbi. L'isola piu' grande della scena e'
    # la faccia e va esclusa; il resto si filtra sullo scostamento laterale.
    isole = [isola for info in dati for isola in info["isole"]]
    if not isole:
        esito["metodo"] = "non stimabile: nessuna isola nella scena"
        return esito

    faccia = max(isole, key=lambda s: s["diagonale"])
    larghezza = massimo.x - minimo.x
    bulbi = [s for s in isole
             if s is not faccia
             and abs(s["centro"].x - centro.x) > MIN_SCOSTAMENTO_BULBO * larghezza]
    bulbi.sort(key=lambda s: s["diagonale"], reverse=True)

    if len(bulbi) < 2:
        esito["metodo"] = (
            "non stimabile: servono due isole rigide fuori asse (i bulbi "
            "oculari), trovate %d. Senza mento il report ricade sul fondo "
            "della mesh, che con il collo e' falso" % len(bulbi))
        return esito

    esito["z_occhi"] = (bulbi[0]["centro"].z + bulbi[1]["centro"].z) * 0.5
    esito["z_mento"] = 2.0 * esito["z_occhi"] - esito["z_cima"]
    esito["metodo"] = ("linea occhi dai bulbi (2 isole rigide su %d), "
                       "mento = 2*z_occhi - z_cima" % (len(isole) - 1))
    _controlla_mento(esito)
    return esito


def _controlla_mento(esito):
    """Coerenza della stima: il mento deve stare fra il fondo e la cima."""
    z_mento = esito["z_mento"]
    if z_mento is None:
        return
    if z_mento < esito["z_base"]:
        esito["avvisi"].append(
            "il mento stimato (%.4f) cade SOTTO il fondo della mesh (%.4f): "
            "stima inaffidabile, controlla che le isole rigide siano davvero i "
            "bulbi oculari" % (z_mento, esito["z_base"]))
    elif z_mento > esito["z_cima"]:
        esito["avvisi"].append(
            "il mento stimato (%.4f) cade SOPRA la cima della mesh (%.4f): "
            "stima inaffidabile" % (z_mento, esito["z_cima"]))


def _frazione_attesa(nome):
    """Frazione mento..cima che FACE_MAPPING prevede per l'osso, o None.

    FACE_MAPPING normalizza z in [-1, 1] sulle semi-dimensioni della mesh:
    -1 = fondo, +1 = cima, 0 = centro, quindi la frazione e' (z + 1) / 2.
    Il presupposto implicito e' che il bbox sia la sola testa, cioe' che il
    fondo SIA il mento: e' proprio il presupposto che qui viene tolto di mezzo
    misurando il mento sul modello invece di darlo per scontato.
    """
    dati = config.FACE_MAPPING.get(nome)
    if dati is None:
        return None
    return (dati.position[2] + 1.0) * 0.5


def _frazione_reale(osso, esito):
    """Dove sta l'osso fra mento e cima, sul modello vero, o None.

    Si misura sull'ANCORA e non sulla testa: dopo la riparazione del rig, Head
    sta alla base del collo e Jaw sul perno dell'articolazione, e confrontare
    quelle posizioni con un landmark facciale non vorrebbe dire niente.
    """
    if esito is None or esito["z_mento"] is None:
        return None
    altezza = esito["z_cima"] - esito["z_mento"]
    if abs(altezza) < 1e-9:
        return None
    return (solver.bone_anchor(osso).z - esito["z_mento"]) / altezza


def _righe_mento(esito):
    """Righe di intestazione con il riferimento verticale."""
    if esito is None:
        return ["riferimento verticale: nessuna mesh da misurare"]

    righe = ["", "riferimento verticale del viso:",
             "  metodo        : %s" % esito["metodo"],
             "  cima mesh     : z = %.4f" % esito["z_cima"],
             "  fondo mesh    : z = %.4f" % esito["z_base"]]
    if esito["z_occhi"] is not None:
        righe.append("  linea occhi   : z = %.4f" % esito["z_occhi"])

    z_mento = esito["z_mento"]
    if z_mento is None:
        righe.append("  mento         : non stimato")
    else:
        righe.append("  mento         : z = %.4f" % z_mento)
        righe.append("  altezza testa : %.4f  (mento -> cima, e' su questa che "
                     "vanno normalizzate le frazioni)" % (esito["z_cima"] - z_mento))
        # E' la parte di mesh che sta sotto il mento: collo, spalle, busto.
        # Misurarla e' il modo piu' diretto di vedere quanto sbaglierebbe una
        # frazione calcolata sul bbox intero.
        collo = z_mento - esito["z_base"]
        totale = esito["z_cima"] - esito["z_base"]
        quota = (collo / totale * 100.0) if totale > 1e-9 else 0.0
        righe.append("  collo scartato: %.4f  (%.0f%% dell'altezza della mesh)"
                     % (collo, quota))

    for avviso in esito["avvisi"]:
        righe.append("  ATTENZIONE: %s" % avviso)
    return righe


# --- sezioni del report ------------------------------------------------------

def _sezione_mesh(righe, dati, arm_obj):
    righe.append("")
    righe.append("=" * 78)
    righe.append("1. OGGETTI MESH DELLA SCENA")
    righe.append("=" * 78)

    if not dati:
        righe.append("  nessun oggetto MESH nella scena")
        return

    spazio = "spazio armatura" if arm_obj else "spazio MONDO (armatura assente)"
    nomi_ossa = {b.name for b in arm_obj.data.bones} if arm_obj else set()

    for info in dati:
        mesh_obj = info["oggetto"]
        righe.append("")
        righe.append("[MESH] %s" % mesh_obj.name)
        righe.append("  vertici           : %d" % len(mesh_obj.data.vertices))
        righe.append("  poligoni          : %d" % len(mesh_obj.data.polygons))
        righe.append("  isole collegate   : %d" % len(info["isole"]))

        box = info["bbox"]
        if box:
            minimo, massimo, _centro, diagonale = box
            righe.append("  bbox %s:" % spazio)
            righe.append("    min  %s" % _vec(minimo))
            righe.append("    max  %s" % _vec(massimo))
            righe.append("    dim  %s   diagonale %.4f"
                         % (_vec(massimo - minimo), diagonale))
        else:
            righe.append("  bbox              : mesh vuota")

        mods = _modificatori_armatura(mesh_obj)
        if not mods:
            righe.append("  modif. Armature   : ASSENTE (la mesh non viene deformata)")
        else:
            for nome, bersaglio in mods:
                righe.append("  modif. Armature   : '%s' -> %s" % (nome, bersaglio))
            if len(mods) > 1:
                righe.append("    ATTENZIONE: %d modificatori Armature, la mesh viene "
                             "deformata piu' volte" % len(mods))

        if mesh_obj.parent is None:
            righe.append("  parent            : nessuno")
        else:
            marchio = "  (= %s)" % RIG_NAME if mesh_obj.parent is arm_obj else ""
            righe.append("  parent            : %s [tipo %s]%s"
                         % (mesh_obj.parent.name, mesh_obj.parent_type, marchio))

        if arm_obj is not None:
            corrispondenti = [vg.name for vg in mesh_obj.vertex_groups
                              if vg.name in nomi_ossa]
            righe.append("  vertex group      : %d totali, %d corrispondono a un osso "
                         "del rig" % (len(mesh_obj.vertex_groups), len(corrispondenti)))


def _sezione_ossa(righe, dati, arm_obj, mento=None):
    righe.append("")
    righe.append("=" * 78)
    righe.append("2. OSSA DI %s" % RIG_NAME)
    righe.append("=" * 78)

    if arm_obj is None:
        righe.append("  armatura '%s' non trovata nella scena" % RIG_NAME)
        return

    if mento is not None and mento["z_mento"] is not None:
        righe.append("  frazione vert. = posizione dell'ancora fra mento (0.0) e "
                     "cima del cranio (1.0),")
        righe.append("  confrontata con quella prevista da FACE_MAPPING. Il "
                     "collo NON entra nel conto.")
    else:
        righe.append("  frazione vert. non calcolabile: manca il mento (vedi "
                     "l'intestazione del report)")

    # Le statistiche di peso si raccolgono su TUTTE le mesh: un osso puo'
    # deformare anche solo un bulbo oculare, e cercarlo nella sola faccia lo
    # farebbe sembrare senza peso.
    conteggi = {}   # nome_osso -> [n_vertici, somma_pesi]
    per_mesh = {}   # nome_osso -> [(nome_mesh, n_vertici), ...]
    for info in dati:
        locali = {}
        for pesi in info["pesi"].values():
            for osso, peso in pesi.items():
                if peso <= PESO_MINIMO:
                    continue
                voce = conteggi.setdefault(osso, [0, 0.0])
                voce[0] += 1
                voce[1] += peso
                locali[osso] = locali.get(osso, 0) + 1
        # Il conteggio per mesh serve a distinguere "osso senza peso" da "osso
        # che pesa su una mesh diversa da quella che stavo guardando".
        for osso, n in locali.items():
            per_mesh.setdefault(osso, []).append((info["oggetto"].name, n))

    scarti = []
    for osso in arm_obj.data.bones:
        lunghezza = (osso.tail_local - osso.head_local).length
        n, somma = conteggi.get(osso.name, (0, 0.0))
        righe.append("")
        righe.append("[OSSO] %s" % osso.name)
        righe.append("  parent            : %s" % (osso.parent.name if osso.parent else "-"))
        righe.append("  head_local        : %s" % _vec(osso.head_local))
        righe.append("  tail_local        : %s" % _vec(osso.tail_local))
        # L'ancora e' il punto che il tracking misura: su Head e Jaw non
        # coincide piu' con la testa dopo la riparazione del rig, ed e' quella
        # che il solver usa per calcolare le scale.
        ancora = osso.get("fm_anchor")
        if ancora is not None and len(ancora) == 3:
            distanza = (Vector(ancora) - osso.head_local).length
            righe.append("  fm_anchor         : %s   (a %.4f dalla testa)"
                         % (_vec(Vector(ancora)), distanza))
        else:
            righe.append("  fm_anchor         : assente (il solver usa head_local)")

        # Posizione verticale rispetto al viso, non al bbox: e' un'euristica
        # grossolana (FACE_MAPPING descrive proporzioni ideali), quindi segnala
        # senza sentenziare.
        reale = _frazione_reale(osso, mento)
        attesa = _frazione_attesa(osso.name)
        if reale is None:
            pass
        elif osso.name in config.ROTATION_BONES:
            # Per le ossa a leva la posizione in FACE_MAPPING e' il PERNO,
            # mentre l'ancora e' il landmark (il mento): sono due punti diversi
            # per costruzione e confrontarli segnalerebbe sempre, a torto.
            righe.append("  frazione vert.    : %.3f   (non confrontabile: in "
                         "FACE_MAPPING questa e' la posizione del perno)" % reale)
        elif attesa is not None:
            scarto = reale - attesa
            marchio = ("   <-- da verificare"
                       if abs(scarto) > SCARTO_VERTICALE else "")
            righe.append("  frazione vert.    : %.3f   attesa %.3f   scarto "
                         "%+.3f%s" % (reale, attesa, scarto, marchio))
            scarti.append(scarto)
        else:
            righe.append("  frazione vert.    : %.3f   (osso non in FACE_MAPPING)"
                         % reale)

        righe.append("  lunghezza         : %.4f" % lunghezza)
        righe.append("  use_deform        : %s" % ("si" if osso.use_deform else "NO"))
        if n:
            righe.append("  vertici peso>%.2f  : %d   peso medio %.3f"
                         % (PESO_MINIMO, n, somma / n))
            dettaglio = per_mesh.get(osso.name, [])
            if len(dettaglio) > 1:
                righe.append("    ripartizione    : %s"
                             % ", ".join("%s %d" % (m, k) for m, k in dettaglio))
        else:
            nota = "   <-- osso deformante SENZA PESO" if osso.use_deform else ""
            righe.append("  vertici peso>%.2f  : 0%s" % (PESO_MINIMO, nota))

    _riepilogo_verticale(righe, scarti)


def _riepilogo_verticale(righe, scarti):
    """Legge gli scarti tutti insieme invece che uno per uno.

    Un modello con proporzioni diverse da quelle di FACE_MAPPING sposta TUTTE
    le ossa nella stessa direzione, e riga per riga sembrerebbero diciotto
    problemi distinti. E' l'uniformita' a distinguere "il viso e' fatto cosi'"
    da "questo osso e' fuori posto": la prima non e' un difetto del rig, la
    seconda si'.
    """
    if len(scarti) < 3:
        return

    mediana = statistics.median(scarti)
    minimo, massimo = min(scarti), max(scarti)
    segnalate = sum(1 for s in scarti if abs(s) > SCARTO_VERTICALE)

    righe.append("")
    righe.append("  riepilogo verticale: %d ossa confrontate, %d oltre la soglia "
                 "di %.2f" % (len(scarti), segnalate, SCARTO_VERTICALE))
    righe.append("    scarto mediano %+.3f, da %+.3f a %+.3f" % (mediana, minimo, massimo))

    uniforme = (minimo > 0.0 or massimo < 0.0) and (massimo - minimo) <= 0.10
    if uniforme and abs(mediana) > SCARTO_VERTICALE:
        direzione = "PIU' IN ALTO" if mediana > 0.0 else "PIU' IN BASSO"
        righe.append("    lo scostamento e' uniforme: le ossa stanno tutte %s di "
                     "quanto FACE_MAPPING preveda." % direzione)
        righe.append("    Questo dice che il modello ha proporzioni diverse dal "
                     "viso ideale della tabella,")
        righe.append("    non che le ossa siano fuori posto una per una. Guarda "
                     "semmai chi si scosta dagli altri.")


def _sezione_isole(righe, dati, arm_obj):
    righe.append("")
    righe.append("=" * 78)
    righe.append("3. ISOLE PER MESH (ordine del binder: la #0 riceve il bone heat)")
    righe.append("=" * 78)

    if not dati:
        righe.append("  nessun oggetto MESH nella scena")
        return

    nomi_ossa = {b.name for b in arm_obj.data.bones} if arm_obj else set()

    for info in dati:
        righe.append("")
        righe.append("[ISOLE] %s   (%d isole)"
                     % (info["oggetto"].name, len(info["isole"])))
        if len(info["isole"]) == 1:
            righe.append("  isola unica: qui il binder ricade sul normale ARMATURE_AUTO")

        for i, isola in enumerate(info["isole"]):
            if i == 0:
                ruolo = "principale (bone heat)"
            else:
                ruolo = "rigida -> attesa su %s" % RIGID_ISLAND_BONE
            osso, quota = _osso_dominante(isola, info["pesi"], nomi_ossa)
            if osso is None:
                assegnata = "NESSUN PESO (isola ferma in deformazione)"
            else:
                assegnata = "%s (%.0f%% del peso dell'isola)" % (osso, quota * 100.0)
            righe.append("  #%-2d vertici %-6d centro %s  diagonale %.4f"
                         % (i, isola["n_vertici"], _vec(isola["centro"]),
                            isola["diagonale"]))
            righe.append("      ruolo          : %s" % ruolo)
            righe.append("      osso dominante : %s" % assegnata)


# --- tabella delle scale di conversione --------------------------------------
#
# La stampa il mocap a ogni calibrazione, ma e' un report come gli altri e sta
# con gli altri: dentro l'operatore modale erano cinquanta righe di
# formattazione in mezzo alla pipeline.

# Intervallo entro cui la scala di un osso e' considerata in linea con quella
# globale. Fuori di qui l'osso si muove sensibilmente piu' o meno degli altri:
# non e' per forza un errore (un modello con occhi grandi lo giustifica), ma e'
# il primo posto dove guardare se un'espressione risulta esagerata.
RAPPORTO_ATTESO_MIN = 0.8
RAPPORTO_ATTESO_MAX = 1.25


def stampa_tabella_scale(unit_scale, dett_unit, dett_scale):
    """Tabella delle scale di conversione, sulla console di sistema.

    La scala per-feature e' il posto piu' probabile in cui nasce un'ampiezza
    sbagliata, ed e' invisibile: si vede solo l'effetto sulle ossa.
    """
    righe = [
        "=" * 78,
        "FACEMOCAP - CALIBRAZIONE: scale di conversione",
        "=" * 78,
        "unit_scale     : %.6f unita' Blender per larghezza viso" % unit_scale,
        "coppie usate   : %d (fra %d ossa) per la mediana di unit_scale"
        % (dett_unit.get("coppie", 0), dett_unit.get("ossa", 0)),
        "limiti feature : da %.2f a %.2f volte unit_scale (MIN/MAX_FEATURE_SCALE)"
        % (config.MIN_FEATURE_SCALE, config.MAX_FEATURE_SCALE),
        "",
        "%-16s %-31s %9s %9s %10s %8s" % ("osso", "riferimento", "mp_dist",
                                          "rig_dist", "scala", "su unit"),
        "-" * 88,
    ]

    for nome in FACE_MAPPING:
        info = dett_scale.get(nome)
        if info is None:
            continue

        ref = info["ref"]
        riferimento = "%s / %s" % ref if ref else "globale (larghezza viso)"
        mp = "%9.5f" % info["mp_dist"] if info["mp_dist"] is not None else "%9s" % "-"
        rig = "%9.5f" % info["rig_dist"] if info["rig_dist"] is not None else "%9s" % "-"

        scala = info["scala"]
        rapporto = scala / unit_scale if unit_scale else 0.0
        note = []
        if rapporto < RAPPORTO_ATTESO_MIN or rapporto > RAPPORTO_ATTESO_MAX:
            note.append("<-- fuori da %.2f-%.2f"
                        % (RAPPORTO_ATTESO_MIN, RAPPORTO_ATTESO_MAX))
        if info["taglio"]:
            note.append("TAGLIATA da %s" % info["taglio"])

        righe.append("%-16s %-31s %s %s %10.6f %8.3f  %s"
                     % (nome, riferimento, mp, rig, scala, rapporto,
                        "  ".join(note)))

    righe.append("")
    righe.append("mp_dist  = distanza fra i due landmark in posa neutra "
                 "(1.0 = una larghezza di viso)")
    righe.append("rig_dist = distanza fra le ancore delle stesse due ossa, in "
                 "unita' Blender")
    righe.append("scala    = rig_dist / mp_dist, cioe' quanto vale sul rig un "
                 "movimento del tracking")
    print("\n".join(righe), flush=True)


# --- operatore ---------------------------------------------------------------

class FACEMOCAP_OT_diagnose_scene(bpy.types.Operator):
    """Stampa nella console di sistema lo stato di mesh, ossa e pesi"""
    bl_idname = "facemocap.diagnose_scene"
    bl_label = "Diagnostica Scena"

    def execute(self, context):
        arm_obj = find_rig()

        mesh_objs = [o for o in context.scene.objects if o.type == 'MESH']

        # Isole e pesi sono la parte costosa: si calcolano UNA volta sola e le
        # tre sezioni si servono dello stesso risultato.
        dati = []
        for mesh_obj in mesh_objs:
            to_arm = _matrice_verso_armatura(mesh_obj, arm_obj)
            dati.append({
                "oggetto": mesh_obj,
                "isole": _isole_mesh(mesh_obj, to_arm),
                "pesi": _pesi_per_vertice(mesh_obj),
                "bbox": _bbox([to_arm @ v.co for v in mesh_obj.data.vertices]),
            })

        righe = [
            "=" * 78,
            "FACEMOCAP - REPORT DI DIAGNOSTICA",
            "=" * 78,
            "file .blend  : %s" % (bpy.data.filepath or "(mai salvato)"),
            "scena        : %s" % context.scene.name,
            "armatura     : %s" % (arm_obj.name if arm_obj else "NON TROVATA"),
        ]
        if arm_obj is not None:
            righe.append("  posizione mondo : %s" % _vec(arm_obj.location))
            righe.append("  scala oggetto   : %s" % _vec(arm_obj.scale))
            righe.append("  numero di ossa  : %d" % len(arm_obj.data.bones))

        mento = _stima_mento(arm_obj, dati)
        righe += _righe_mento(mento)

        _sezione_mesh(righe, dati, arm_obj)
        _sezione_ossa(righe, dati, arm_obj, mento)
        _sezione_isole(righe, dati, arm_obj)
        righe.append("")
        righe.append("fine report")

        print("\n".join(righe), flush=True)

        self.report({'INFO'}, "Report stampato nella console di sistema.")
        return {'FINISHED'}


# --- riparazione del rig -----------------------------------------------------
#
# Il rig ha due mestieri in conflitto:
#   - deformare bene: conta il SEGMENTO testa-coda, perche' e' quello che il
#     bone heat pesa, e conta il perno, perche' e' attorno a quello che ruota;
#   - corrispondere al tracking: conta il PUNTO in cui sta il landmark.
# Finche' i due mestieri stanno sullo stesso punto (la testa dell'osso) non se
# ne puo' sistemare uno senza rompere l'altro. L'ancora li separa: la geometria
# si puo' spostare dove serve, il landmark resta registrato dov'era.
#
# Questo operatore lavora su un rig GIA' posizionato a mano e non tocca le
# teste delle ossa facciali: quello e' lavoro dell'utente.

# Lunghezza delle ossa facciali, in frazione della diagonale del bbox della
# mesh. La coda va corta e diretta DENTRO il volume, lungo la normale entrante:
# con la coda lunga verso l'alto il segmento di Lip_Lower attraversa il labbro
# superiore e arriva al naso, e il bone heat gli regala meta' del labbro
# sbagliato; con la coda in avanti meta' dell'osso esce dalla mesh, e il bone
# heat, che misura la visibilita' dall'interno, non vede il segmento e produce
# pesi deboli.
FRAZIONE_CODA_FACCIALE = 0.02

# Perno della temporo-mandibolare: sta all'altezza del condotto uditivo, cioe'
# circa al 70% della salita dagli angoli della bocca agli occhi, e circa all'8%
# della profondita' dietro il centro della testa.
SALITA_PERNO_JAW = 0.70
PROFONDITA_PERNO_JAW = 0.08

# Asse del cranio: dalla base del collo alla cima, arretrato rispetto al centro
# del bbox perche' il viso sporge in avanti e il centro geometrico no.
PROFONDITA_ASSE_CRANIO = 0.10
ALTEZZA_BASE_COLLO = 0.05
ALTEZZA_CIMA_CRANIO = 0.15

# Se la base della mesh dista dagli occhi piu' di questo multiplo della
# distanza occhi-bocca, la mesh non e' solo testa e collo.
MAX_RAPPORTO_COLLO = 4.0


def _mesh_del_rig(context, rig):
    """La mesh piu' grande legata al rig, o None.

    Se il modello ha bulbi o denti come oggetti separati, la testa e' quella
    con il bbox piu' grande: prendere la prima che capita darebbe misure di un
    bulbo oculare e l'intero rig verrebbe dimensionato su quello.
    """
    migliore = None
    migliore_diag = 0.0
    for obj in context.scene.objects:
        if obj.type != 'MESH':
            continue
        legata = obj.parent is rig or any(
            m.type == 'ARMATURE' and m.object is rig for m in obj.modifiers)
        if not legata:
            continue
        box = _bbox_in_armatura(obj, rig)
        if box is not None and box[3] > migliore_diag:
            migliore, migliore_diag = obj, box[3]
    return migliore


def _bbox_in_armatura(mesh_obj, rig):
    """(min, max, centro, diagonale) del bbox della mesh in spazio armatura.

    Bastano gli 8 angoli di bound_box: il risultato e' lo stesso che iterando
    tutti i vertici, ma non costa nulla su una mesh da centinaia di migliaia.
    """
    to_arm = rig.matrix_world.inverted() @ mesh_obj.matrix_world
    return _bbox([to_arm @ Vector(angolo) for angolo in mesh_obj.bound_box])


def _sonda_superficie(mesh_obj, rig):
    """Costruisce la funzione che interroga la superficie della mesh.

    Ritorna `sonda(punto_armatura)` -> (normale_uscente, dentro, distanza),
    oppure None se la mesh non sa rispondere (nessun poligono, matrici
    degeneri). Le matrici si calcolano una volta sola e restano nella chiusura:
    la riparazione interroga la superficie una volta per osso per la normale e
    tre per il controllo dentro/fuori.
    """
    to_mesh = mesh_obj.matrix_world.inverted() @ rig.matrix_world
    to_arm = rig.matrix_world.inverted() @ mesh_obj.matrix_world
    # Le normali non si trasformano con la matrice ma con la sua inversa
    # trasposta: con una scala non uniforme la direzione ruoterebbe di traverso
    # e la coda entrerebbe nel volume storta.
    matrice_normali = to_arm.to_3x3().inverted_safe().transposed()

    def sonda(punto_armatura):
        trovato, posizione, normale, _indice = mesh_obj.closest_point_on_mesh(
            to_mesh @ punto_armatura)
        if not trovato:
            return None

        uscente = matrice_normali @ normale
        if uscente.length < 1e-9:
            return None
        uscente.normalize()

        superficie = to_arm @ posizione
        scostamento = punto_armatura - superficie
        # La normale esce dal volume: se il punto sta oltre la superficie lungo
        # la normale, e' fuori. Vale su una superficie chiusa; su una piega
        # stretta (le labbra a contatto) puo' sbagliare, ed e' il motivo per cui
        # questo finisce in un report e non in una decisione automatica.
        return uscente, scostamento.dot(uscente) <= 0.0, scostamento.length

    return sonda


def _ossa_da_spostare():
    """Ossa di cui questo operatore muove la TESTA, non solo la coda."""
    return {"Head"} | set(config.ROTATION_BONES)


def _leggi_ancore(rig):
    """{nome_osso: ancora}, cioe' dove sta il landmark di ogni osso.

    Per le ossa di cui NON spostiamo la testa l'ancora si rilegge sempre da
    head_local: se l'utente le ha riposizionate in Edit Mode, quella e' la
    verita' aggiornata.

    Per Head e Jaw invece un'ancora gia' presente si conserva. Dopo una prima
    riparazione la loro testa non e' piu' sul landmark (e' sul perno e sulla
    base del collo): rileggerla da head_local a ogni esecuzione sposterebbe il
    mento sul perno e al secondo click il rig sarebbe rotto.
    """
    da_spostare = _ossa_da_spostare()
    ancore = {}
    for osso in rig.data.bones:
        esistente = osso.get("fm_anchor")
        if osso.name in da_spostare and esistente is not None and len(esistente) == 3:
            ancore[osso.name] = Vector(esistente)
        elif osso.name in config.ROTATION_BONES:
            ancore[osso.name] = _ancora_leva(osso)
        else:
            ancore[osso.name] = osso.head_local.copy()
    return ancore


def _ancora_leva(osso):
    """Dove sta il mento su un osso a leva che non ha ancora un'ancora.

    Le due convenzioni in circolazione mettono il mento su estremi diversi: un
    osso costruito come leva ce l'ha sulla CODA (la testa sta sul perno), uno
    vecchio in traslazione ce l'ha sulla TESTA, dov'era il landmark 152.
    Si distinguono dalla direzione: se la coda scende gia' quanto basta al
    solver, l'osso e' una leva e il mento e' la sua coda.

    Senza questa distinzione, ri-riparare un rig gia' a posto sposterebbe il
    mento sul perno e il secondo click romperebbe cio' che il primo ha
    sistemato.
    """
    if solver.is_valid_lever(osso.tail_local - osso.head_local):
        return osso.tail_local.copy()
    return osso.head_local.copy()


def _piano_riparazione(rig, box, ancore, sonda):
    """Calcola le nuove coppie head/tail SENZA applicarle.

    Si calcola tutto prima e si applica dopo, cosi' se la leva della mandibola
    non passa il criterio del solver si esce senza aver toccato niente: meglio
    non partire che lasciare a meta' un rig su cui l'utente ha lavorato a mano.

    Ritorna (piano, avvisi, errore): con errore non None il piano non vale.
    """
    minimo, massimo, centro, diagonale = box
    dim = massimo - minimo
    avvisi = []

    mancanti = [n for n in ("Eye_L", "Eye_R", "Mouth_Corner_L", "Mouth_Corner_R")
                if n not in ancore]
    if mancanti:
        return None, avvisi, ("ossa di riferimento assenti nel rig: %s"
                              % ", ".join(mancanti))

    z_occhi = (ancore["Eye_L"].z + ancore["Eye_R"].z) * 0.5
    y_occhi = (ancore["Eye_L"].y + ancore["Eye_R"].y) * 0.5
    z_angoli = (ancore["Mouth_Corner_L"].z + ancore["Mouth_Corner_R"].z) * 0.5

    piano = {}

    # 1. Ossa facciali: la testa resta dove l'ha messa l'utente, cambia solo la
    #    coda. La direzione della coda non entra nella matematica del solver
    #    (to_bone_space assorbe il cambio di base) ma decide i pesi, e va presa
    #    verso l'INTERNO del volume: il bone heat misura la visibilita' dei
    #    vertici dal segmento dell'osso, e un segmento che sta fuori dalla mesh
    #    non e' visto da nessuno.
    lunghezza = FRAZIONE_CODA_FACCIALE * diagonale
    da_spostare = _ossa_da_spostare()
    fuori_volume = []
    senza_normale = []
    for osso in rig.data.bones:
        if osso.name in da_spostare:
            continue
        testa = osso.head_local.copy()

        esito = sonda(testa)
        if esito is None:
            # Nessuna risposta dalla superficie: si ripiega sulla vecchia
            # direzione in avanti, che almeno non punta verso l'alto.
            direzione = Vector((0.0, -1.0, 0.0))
            senza_normale.append(osso.name)
        else:
            uscente, dentro, _distanza = esito
            direzione = -uscente
            if not dentro:
                # Si segnala e basta: dove sta la testa e' una decisione
                # dell'utente, non di questo operatore.
                fuori_volume.append(osso.name)

        piano[osso.name] = (testa, testa + direzione * lunghezza)

    if fuori_volume:
        avvisi.append("teste FUORI dal volume della mesh (lasciate dove sono): "
                      "%s" % ", ".join(fuori_volume))
    if senza_normale:
        avvisi.append("nessuna normale di superficie per %s: coda messa in "
                      "avanti (-Y) come ripiego" % ", ".join(senza_normale))

    # 2. Head: diventa l'osso del cranio. La testa alla base del collo perche'
    #    e' li' il perno naturale attorno a cui la testa annuisce e ruota.
    if "Head" in ancore:
        y_asse = centro.y + PROFONDITA_ASSE_CRANIO * dim.y
        piano["Head"] = (
            Vector((0.0, y_asse, minimo.z + ALTEZZA_BASE_COLLO * dim.z)),
            Vector((0.0, y_asse, massimo.z - ALTEZZA_CIMA_CRANIO * dim.z)),
        )

        # La base del collo si ricava da min_z, quindi vale solo se la mesh
        # finisce col collo. Su un corpo intero min_z sarebbe ai piedi e l'osso
        # Head nascerebbe all'altezza delle caviglie.
        riferimento = abs(z_occhi - z_angoli)
        if riferimento > 1e-6 and abs(minimo.z - z_occhi) > MAX_RAPPORTO_COLLO * riferimento:
            avvisi.append(
                "la base della mesh dista %.4f dagli occhi, piu' di %.0f volte la "
                "distanza occhi-bocca (%.4f): la mesh sembra contenere piu' di "
                "testa e collo, quindi la testa di Head e' finita troppo in basso"
                % (abs(minimo.z - z_occhi), MAX_RAPPORTO_COLLO, riferimento))

    # 3. Jaw: da osso in traslazione a leva vera. La coda torna sul mento, cioe'
    #    sull'ancora: la testa dov'e' oggi non c'entra piu' niente.
    for nome in config.ROTATION_BONES:
        if nome not in ancore:
            continue
        perno = Vector((0.0,
                        centro.y + PROFONDITA_PERNO_JAW * dim.y,
                        z_angoli + SALITA_PERNO_JAW * (z_occhi - z_angoli)))
        mento = ancore[nome].copy()
        leva = mento - perno

        if leva.length < 1e-6:
            return None, avvisi, (
                "'%s': perno calcolato e ancora coincidono %s, leva di lunghezza "
                "zero. L'ancora non e' sul mento: in Edit Mode porta la TESTA di "
                "%s sulla punta del mento (la coda dove capita, la sistemo io) e "
                "ripremi. Rig lasciato invariato" % (nome, _vec(perno), nome))

        # Stesso criterio del solver, chiamato e non ricopiato: se non passa
        # qui, non passerebbe nemmeno a regime, e il rig resterebbe muto senza
        # dire perche'.
        if not solver.is_valid_lever(leva):
            seno = max(-1.0, min(1.0, -leva.z / leva.length))
            return None, avvisi, (
                "'%s': la leva calcolata non passa il criterio del solver. "
                "Perno %s, mento (ancora) %s, leva %s inclinata %.1f gradi sotto "
                "l'orizzonte, ne servono almeno %.1f. L'ancora e' troppo in alto "
                "o troppo arretrata per essere il mento: in Edit Mode porta la "
                "TESTA di questo osso sulla punta del mento e ripremi. Rig "
                "lasciato invariato"
                % (nome, _vec(perno), _vec(mento), _vec(leva),
                   math.degrees(math.asin(seno)),
                   math.degrees(math.asin(config.MIN_LEVER_DOWN))))

        piano[nome] = (perno, mento)

    # Misure di contesto: servono a rileggere il piano senza rifare i conti.
    avvisi.append("misure: diagonale %.4f, occhi z %.4f y %.4f, angoli bocca z "
                  "%.4f, coda facciale %.4f"
                  % (diagonale, z_occhi, y_occhi, z_angoli, lunghezza))
    return piano, avvisi, None


def _applica_piano(context, rig, piano, ancore):
    """Scrive ancore e geometria. Ritorna le righe del resoconto."""
    precedente = context.view_layer.objects.active

    # Le ancore vanno scritte PRIMA di toccare la geometria: dopo, head_local
    # di Head e Jaw non e' piu' il landmark e il dato originale sarebbe perso.
    for nome, ancora in ancore.items():
        rig.data.bones[nome]["fm_anchor"] = list(ancora)

    vecchi = {osso.name: (osso.head_local.copy(), osso.tail_local.copy())
              for osso in rig.data.bones}

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')

    scollegati = []
    try:
        edit_bones = rig.data.edit_bones
        for nome, (testa, coda) in piano.items():
            eb = edit_bones.get(nome)
            if eb is None:
                continue
            # Un osso connesso al genitore si tira dietro la testa quando il
            # genitore muove la coda: violerebbe la promessa di non spostare le
            # teste posizionate a mano.
            for figlio in eb.children:
                if figlio.use_connect:
                    figlio.use_connect = False
                    scollegati.append(figlio.name)
            if eb.use_connect:
                eb.use_connect = False
                scollegati.append(nome)
            eb.head = testa
            eb.tail = coda
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
        if precedente is not None:
            context.view_layer.objects.active = precedente

    # Rispristino difensivo: le custom property sopravvivono al giro in Edit
    # Mode, ma qui costa tre righe assicurarsene invece di scoprire il
    # contrario a rig gia' riparato.
    for nome, ancora in ancore.items():
        rig.data.bones[nome]["fm_anchor"] = list(ancora)

    # Eye_L/Eye_R sono pilotate in TRASLAZIONE dall'iride: se deformano la
    # pelle, muovere lo sguardo trascina l'occhio intero. I bulbi restano
    # legati a Head (vedi RIGID_ISLAND_BONE in core/weights.py).
    spente = []
    for nome in ("Eye_L", "Eye_R"):
        osso = rig.data.bones.get(nome)
        if osso is not None and osso.use_deform:
            osso.use_deform = False
            spente.append(nome)

    righe = []
    for nome in sorted(piano):
        if nome not in vecchi:
            continue
        osso = rig.data.bones.get(nome)
        if osso is None:
            continue
        vecchia_testa, vecchia_coda = vecchi[nome]
        righe.append("%-16s head %s -> %s" % (nome, _vec(vecchia_testa),
                                              _vec(osso.head_local)))
        righe.append("%-16s tail %s -> %s" % ("", _vec(vecchia_coda),
                                              _vec(osso.tail_local)))
    if scollegati:
        righe.append("scollegate dal genitore (use_connect): %s"
                     % ", ".join(sorted(set(scollegati))))
    if spente:
        righe.append("use_deform disattivato su: %s" % ", ".join(spente))
    return righe


def _righe_dentro_fuori(rig, piano, sonda):
    """Verifica che testa, meta' e coda di ogni osso stiano nel volume.

    Si legge la geometria VERA dopo l'applicazione, non il piano: e' il modo di
    controllare il risultato senza dover rilanciare la diagnostica.
    """
    righe = ["", "controllo dentro/fuori (D = dentro il volume, F = fuori, "
                 "? = superficie muta):"]
    for nome in sorted(piano):
        osso = rig.data.bones.get(nome)
        if osso is None:
            continue
        testa = osso.head_local
        coda = osso.tail_local
        stati = []
        for punto in (testa, (testa + coda) * 0.5, coda):
            esito = sonda(punto)
            stati.append("?" if esito is None else ("D" if esito[1] else "F"))

        nota = ""
        if stati[0] == "F":
            nota = "   <-- testa fuori: non spostata, e' posizione dell'utente"
        elif "F" in stati:
            nota = "   <-- il segmento esce dal volume: pesi deboli attesi"
        righe.append("  %-16s testa %s   meta' %s   coda %s%s"
                     % (nome, stati[0], stati[1], stati[2], nota))
    return righe


class FACEMOCAP_OT_fix_rig(bpy.types.Operator):
    """Riorienta le ossa del rig senza spostare le teste posizionate a mano"""
    bl_idname = "facemocap.fix_rig"
    bl_label = "Ripara Armatura"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig = find_rig()
        if rig is None:
            self.report({'ERROR'}, "Armatura '%s' non trovata." % RIG_NAME)
            return {'CANCELLED'}
        if not rig.visible_get():
            self.report({'ERROR'}, "L'armatura e' nascosta: rendila visibile "
                                   "per poter entrare in Edit Mode.")
            return {'CANCELLED'}

        mesh_obj = _mesh_del_rig(context, rig)
        if mesh_obj is None:
            self.report({'ERROR'}, "Nessuna mesh legata al rig: collega prima "
                                   "il modello con 'Collega Manualmente'.")
            return {'CANCELLED'}

        # In Edit Mode bound_box e closest_point_on_mesh rispondono sulla mesh
        # com'era PRIMA delle modifiche in corso: si esce subito, prima di
        # misurare qualsiasi cosa.
        if context.mode != 'OBJECT' and context.object is not None:
            bpy.ops.object.mode_set(mode='OBJECT')

        box = _bbox_in_armatura(mesh_obj, rig)
        if box is None or box[3] < 1e-6:
            self.report({'ERROR'}, "La mesh '%s' ha un bbox degenere." % mesh_obj.name)
            return {'CANCELLED'}

        sonda = _sonda_superficie(mesh_obj, rig)
        ancore = _leggi_ancore(rig)
        piano, avvisi, errore = _piano_riparazione(rig, box, ancore, sonda)
        if errore is not None:
            print("FaceMocap - riparazione ANNULLATA: %s" % errore, flush=True)
            self.report({'ERROR'}, errore)
            return {'CANCELLED'}

        righe = _applica_piano(context, rig, piano, ancore)
        righe += _righe_dentro_fuori(rig, piano, sonda)

        testo = "\n".join(
            ["FaceMocap - riparazione del rig (mesh di riferimento: %s)" % mesh_obj.name]
            + ["  " + r for r in avvisi]
            + [""]
            + righe
            + ["", "Ricorda: i pesi sono stati calcolati sulle ossa VECCHIE. "
               "Ripremi 'Collega Manualmente' per ricalcolarli."])
        print(testo, flush=True)

        vere = [a for a in avvisi if not a.startswith("misure:")]
        if vere:
            self.report({'WARNING'}, "Rig riparato con avvisi: %s | dettagli in "
                        "console" % " | ".join(vere))
        else:
            self.report({'INFO'}, "Rig riparato: %d ossa aggiornate. Dettagli in "
                        "console. Ora ricollega il modello per rifare i pesi."
                        % len(piano))
        return {'FINISHED'}


# --- pannello di servizio ----------------------------------------------------

class FACEMOCAP_PT_debug_panel(bpy.types.Panel):
    """Sottopannello di servizio: non serve al flusso di lavoro normale.

    E' un sottopannello di FACEMOCAP_PT_main_panel invece di una voce dentro
    gui.py cosi' l'aggiunta resta tutta in questo file: auto_load registra il
    genitore prima del figlio guardando bl_parent_id.
    """
    bl_label = "Debug"
    bl_idname = "FACEMOCAP_PT_debug_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'FaceMocap'
    bl_parent_id = "FACEMOCAP_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        box_report = layout.box()
        box_report.operator("facemocap.diagnose_scene",
                            text="Diagnostica Scena", icon='CONSOLE')
        col = box_report.column(align=True)
        col.scale_y = 0.8
        col.label(text="Report nella console di sistema")

        box_fix = layout.box()
        box_fix.operator("facemocap.fix_rig", text="Ripara Armatura", icon='TOOL_SETTINGS')
        col = box_fix.column(align=True)
        col.scale_y = 0.8
        col.label(text="Riorienta code, Head e Jaw")
        col.label(text="Poi ricollega per rifare i pesi")
