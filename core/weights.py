# Calcolo dei pesi di deformazione per il rig facciale.
import bmesh
import bpy

from . import config

RIGID_ISLAND_BONE = "Head"


def clean_loose_geometry(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)

    sciolti = [v for v in bm.verts if not v.link_faces]
    n = len(sciolti)
    if n:
        bmesh.ops.delete(bm, geom=sciolti, context='VERTS')
        bm.to_mesh(mesh_obj.data)
        mesh_obj.data.update()
    bm.free()
    return n


def _islands(bm):
    bm.verts.ensure_lookup_table()
    visti = set()
    isole = []
    for v in bm.verts:
        if v.index in visti:
            continue
        pila = [v]
        visti.add(v.index)
        gruppo = []
        while pila:
            cur = pila.pop()
            gruppo.append(cur)
            for e in cur.link_edges:
                alt = e.other_vert(cur)
                if alt.index not in visti:
                    visti.add(alt.index)
                    pila.append(alt)
        isole.append(gruppo)
    return isole


def _extent(gruppo):
    """Diagonale del bounding box della faccia"""
    xs = [v.co.x for v in gruppo]
    ys = [v.co.y for v in gruppo]
    zs = [v.co.z for v in gruppo]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dz = max(zs) - min(zs)
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _split_islands(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)

    isole = _islands(bm)
    if len(isole) <= 1:
        bm.free()
        return None, [], []

    isole.sort(key=_extent, reverse=True)
    faccia = [v.index for v in isole[0]]
    rigide = [v.index for gruppo in isole[1:] for v in gruppo]
    note = ["isola principale %d vertici, %d isole rigide su %s (%d vertici)"
            % (len(faccia), len(isole) - 1, RIGID_ISLAND_BONE, len(rigide))]

    bm.free()
    return faccia, rigide, note


def _heat_weights_on_subset(mesh_obj, arm_obj, context, indici):
    """Pesi automatici calcolati su una copia con i soli vertici indicati perché
    parent_set lavora sull'oggetto intero, quindi la sola via per escludere le
    isole rigide dal bone heat e' skinnare una copia temporanea."""

    tenere = set(indici)

    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()

    layer = bm.verts.layers.int.new("facemocap_orig")
    for v in bm.verts:
        v[layer] = v.index

    scarti = [v for v in bm.verts if v.index not in tenere]
    if scarti:
        bmesh.ops.delete(bm, geom=scarti, context='VERTS')

    temp_data = bpy.data.meshes.new(mesh_obj.data.name + "_fm_tmp")
    bm.to_mesh(temp_data)
    bm.free()

    temp_obj = bpy.data.objects.new(mesh_obj.name + "_fm_tmp", temp_data)
    temp_obj.matrix_world = mesh_obj.matrix_world.copy()
    context.collection.objects.link(temp_obj)

    try:
        bpy.ops.object.select_all(action='DESELECT')
        temp_obj.select_set(True)
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')

        attr = temp_data.attributes.get("facemocap_orig")
        if attr is None:
            return {}

        nomi = {vg.index: vg.name for vg in temp_obj.vertex_groups}
        pesi = {}
        for v in temp_data.vertices:
            originale = attr.data[v.index].value
            for g in v.groups:
                if g.weight <= 0.0:
                    continue
                nome = nomi.get(g.group)
                if nome is not None:
                    pesi.setdefault(nome, []).append((originale, g.weight))
        return pesi
    finally:
        bpy.data.objects.remove(temp_obj, do_unlink=True)
        bpy.data.meshes.remove(temp_data, do_unlink=True)


def _apply_weights(mesh_obj, pesi):
    for nome, coppie in pesi.items():
        vg = mesh_obj.vertex_groups.get(nome)
        if vg is None:
            vg = mesh_obj.vertex_groups.new(name=nome)
        for indice, peso in coppie:
            vg.add([indice], peso, 'REPLACE')


def _parent_to_armature(mesh_obj, arm_obj):
    mondo = mesh_obj.matrix_world.copy()
    mesh_obj.parent = arm_obj
    mesh_obj.parent_type = 'ARMATURE'
    mesh_obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()
    mesh_obj.matrix_world = mondo

    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE':
            mod.object = arm_obj
            return
    mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = arm_obj


def bind_by_islands(mesh_obj, arm_obj, context):
    faccia, rigide, note = _split_islands(mesh_obj)

    if faccia is None:
        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        return note + spread_eyelid_weights(mesh_obj, arm_obj)

    pesi = _heat_weights_on_subset(mesh_obj, arm_obj, context, faccia)
    _apply_weights(mesh_obj, pesi)

    if rigide:
        vg = mesh_obj.vertex_groups.get(RIGID_ISLAND_BONE)
        if vg is None:
            vg = mesh_obj.vertex_groups.new(name=RIGID_ISLAND_BONE)
        vg.add(rigide, 1.0, 'REPLACE')

    note += spread_eyelid_weights(mesh_obj, arm_obj, faccia)

    _parent_to_armature(mesh_obj, arm_obj)
    return note


def limit_body_weights(mesh_obj, arm_obj):
    """Toglie Neck e Chest dal viso: zero sopra il mento, pieni piu' in basso.

    Il bone heat assegna ogni vertice alle ossa piu' vicine, e su un collo
    corto Neck passa dietro bocca e mento: labbra e mento prendono parte del
    peso da un osso che non segue la mandibola, e si muovono smorzati.
    Il peso tolto va alle altre ossa del vertice (il modificatore Armature
    normalizza la somma); se non ne ha, va a Head, che e' l'osso del cranio.
    """
    bones = arm_obj.data.bones
    jaw = bones.get("Jaw")
    if "Neck" not in bones or jaw is None:
        return []

    anchor = jaw.get("fm_anchor")
    chin_z = anchor[2] if anchor is not None and len(anchor) == 3 else jaw.tail_local.z

    to_arm = arm_obj.matrix_world.inverted() @ mesh_obj.matrix_world
    verts = mesh_obj.data.vertices
    zs = [(to_arm @ v.co).z for v in verts]
    fade = config.BODY_WEIGHT_FADE * (max(zs) - chin_z)
    if fade <= 1e-9:
        return []

    body = {vg.index for vg in mesh_obj.vertex_groups if vg.name in config.BODY_BONES}
    face = {vg.index for vg in mesh_obj.vertex_groups
            if vg.name in bones and vg.name not in config.BODY_BONES}
    if not body:
        return []
    head_vg = mesh_obj.vertex_groups.get("Head")
    if head_vg is None:
        head_vg = mesh_obj.vertex_groups.new(name="Head")

    toccati = 0
    for v in verts:
        quota = min(max((chin_z - zs[v.index]) / fade, 0.0), 1.0)
        if quota >= 1.0:
            continue
        tolto = 0.0
        altri = 0.0
        # copia prima di modificare: remove() invalida gli elementi di v.groups
        for gruppo, peso in [(g.group, g.weight) for g in v.groups]:
            if gruppo in body:
                tolto += peso * (1.0 - quota)
                nuovo = peso * quota
                vg = mesh_obj.vertex_groups[gruppo]
                if nuovo > 1e-3:
                    vg.add([v.index], nuovo, 'REPLACE')
                else:
                    vg.remove([v.index])
            elif gruppo in face:
                altri += peso
        if tolto > 0.0:
            toccati += 1
            if altri <= 1e-3:
                head_vg.add([v.index], tolto, 'ADD')

    return ["Neck/Chest tolti dal viso su %d vertici (sopra il mento)" % toccati] if toccati else []


EYELID_BONES = ("Eyelid_Up.L", "Eyelid_Low.L", "Eyelid_Up.R", "Eyelid_Low.R")


def _taper(t):
    """Frazione del peso che resta a distanza t (1 = angolo dell'occhio)."""
    drop = config.EYELID_CORNER_DROP
    if t <= 1.0:
        return 1.0 - drop * t * t
    if t < 1.3:
        return (1.0 - drop) * (1.3 - t) / 0.3
    return 0.0


def _verticale(a):
    """Frazione del peso a distanza verticale a (1 = bordo della fascia).

    Piena vicino all'osso, cosi' il bordo della palpebra segue l'osso per
    intero, poi scende a zero verso il bordo della fascia.
    """
    if a <= 0.5:
        return 1.0
    if a >= 1.0:
        return 0.0
    t = (a - 0.5) / 0.5
    return 1.0 - t * t


def spread_eyelid_weights(mesh_obj, arm_obj, indici=None):
    """Disegna i pesi delle palpebre sulla geometria, senza il bone heat.

    Il bone heat sulle palpebre non e' affidabile: su un modello il centro
    della palpebra prende un buon peso, su un altro lo prendono quasi tutto
    Head e le sopracciglia e la palpebra resta ferma mentre l'osso si muove.
    Qui il peso di ogni vertice della fascia attorno all'osso e'

        riduzione verso gli angoli (EYELID_SPREAD_RADIUS, EYELID_CORNER_DROP)
        x riduzione in verticale (EYELID_SPREAD_HEIGHT)

    pieno al centro, zero fuori dalla fascia. Le altre ossa del vertice
    vengono scalate perche' sommino al piu' 1 - peso: il modificatore Armature
    fa la media pesata, e senza questo una palpebra con peso 1 ma con Head a 1
    si muoverebbe solo a meta'.
    I vertici si guardano di fronte (x, z): gli angoli dell'occhio stanno piu'
    indietro del centro. In profondita' si escludono solo quelli molto dietro
    la palpebra (orbita, interno della testa).
    """
    bones = arm_obj.data.bones
    eye_l, eye_r = bones.get("Eye.L"), bones.get("Eye.R")
    if eye_l is None or eye_r is None:
        return []
    distanza_occhi = (eye_l.head_local - eye_r.head_local).length
    raggio = distanza_occhi * config.EYELID_SPREAD_RADIUS
    altezza = distanza_occhi * config.EYELID_SPREAD_HEIGHT
    if raggio < 1e-6 or altezza < 1e-6:
        return []

    to_arm = arm_obj.matrix_world.inverted() @ mesh_obj.matrix_world
    verts = mesh_obj.data.vertices
    sorgente = range(len(verts)) if indici is None else indici
    pos = {i: to_arm @ verts[i].co for i in sorgente}

    # Linea a meta' fra le due palpebre di ogni occhio. Su un occhio piccolo
    # le due fasce, alte 2 * altezza, si sovrappongono: la palpebra inferiore,
    # pesata dopo, si prenderebbe il bordo della superiore e l'occhio non si
    # chiuderebbe. Sopra la linea pesa solo la superiore, sotto solo
    # l'inferiore, ciascuna piena dalla linea fino al proprio osso.
    meta = {}
    for lato in (".L", ".R"):
        su, giu = bones.get("Eyelid_Up" + lato), bones.get("Eyelid_Low" + lato)
        if su is not None and giu is not None:
            meta[lato] = (su.head_local.z + giu.head_local.z) * 0.5

    note = []
    for nome in EYELID_BONES:
        bone = bones.get(nome)
        if bone is None:
            continue
        linea = meta.get(nome[-2:])
        superiore = nome.startswith("Eyelid_Up")
        vg = mesh_obj.vertex_groups.get(nome)
        if vg is None:
            vg = mesh_obj.vertex_groups.new(name=nome)
        # gruppi delle altre ossa del rig, da ridurre dove pesa la palpebra
        altri = {g.index for g in mesh_obj.vertex_groups
                 if g.name in bones and g.index != vg.index}
        c = bone.head_local

        pesati = 0
        for i, p in pos.items():
            dx = abs(p.x - c.x) / raggio
            if linea is None:
                dz = abs(p.z - c.z) / altezza
                dal_lato_giusto = True
            elif superiore:
                # pieno fra la linea e l'osso, poi sfuma verso il sopracciglio
                dz = max(0.0, p.z - c.z) / altezza
                dal_lato_giusto = p.z >= linea
            else:
                dz = max(0.0, c.z - p.z) / altezza
                dal_lato_giusto = p.z < linea
            peso = 0.0
            if dal_lato_giusto and dx < 1.3 and dz < 1.0 and p.y < c.y + altezza:
                peso = _taper(dx) * _verticale(dz)

            # copia prima di modificare: add/remove invalidano v.groups
            gruppi = [(g.group, g.weight) for g in verts[i].groups]
            if peso <= 1e-3:
                if any(gr == vg.index for gr, _w in gruppi):
                    vg.remove([i])
                continue

            vg.add([i], peso, 'REPLACE')
            pesati += 1
            somma = sum(w for gr, w in gruppi if gr in altri)
            if somma > 1.0 - peso:
                fattore = (1.0 - peso) / somma
                for gr, w in gruppi:
                    if gr not in altri:
                        continue
                    nuovo = w * fattore
                    if nuovo > 1e-3:
                        mesh_obj.vertex_groups[gr].add([i], nuovo, 'REPLACE')
                    else:
                        mesh_obj.vertex_groups[gr].remove([i])
        note.append("%s: %d vertici pesati" % (nome, pesati))

    note += _limit_brows(mesh_obj, bones, pos)
    return note


def _limit_brows(mesh_obj, bones, pos):
    """Toglie il sopracciglio dalla cavita' dell'occhio.

    Il bone heat da' a Brow tutta la zona attorno, cavita' dell'occhio
    compresa: alzando le sopracciglia si deforma l'orbita, e all'angolo
    esterno, dove la palpebra pesa poco, il sopracciglio tiene l'occhio aperto
    anche a palpebra chiusa. Il peso di Brow resta pieno dalla sua altezza in
    su e scende a zero all'altezza dell'osso della palpebra superiore; quello
    tolto va a Head, cosi' l'orbita resta ferma.
    """
    verts = mesh_obj.data.vertices
    head_vg = mesh_obj.vertex_groups.get("Head")
    if head_vg is None:
        head_vg = mesh_obj.vertex_groups.new(name="Head")

    note = []
    for lato in (".L", ".R"):
        brow, su = bones.get("Brow" + lato), bones.get("Eyelid_Up" + lato)
        vg = mesh_obj.vertex_groups.get("Brow" + lato)
        if brow is None or su is None or vg is None:
            continue
        alto, basso = brow.head_local.z, su.head_local.z
        if alto - basso < 1e-6:
            continue

        ridotti = 0
        for i, p in pos.items():
            if p.z >= alto:
                continue
            peso = next((g.weight for g in verts[i].groups if g.group == vg.index), 0.0)
            if peso <= 0.0:
                continue
            quota = min(max((p.z - basso) / (alto - basso), 0.0), 1.0)
            nuovo = peso * quota
            if nuovo > 1e-3:
                vg.add([i], nuovo, 'REPLACE')
            else:
                vg.remove([i])
            head_vg.add([i], peso - nuovo, 'ADD')
            ridotti += 1
        note.append("Brow%s: peso ridotto su %d vertici attorno all'occhio" % (lato, ridotti))
    return note
