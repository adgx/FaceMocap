# Calcolo dei pesi di deformazione per il rig facciale.
import bmesh
import bpy

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
    """Pesi automatici calcolati su una copia con i soli vertici indicati perchhé
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
        return note

    pesi = _heat_weights_on_subset(mesh_obj, arm_obj, context, faccia)
    _apply_weights(mesh_obj, pesi)

    if rigide:
        vg = mesh_obj.vertex_groups.get(RIGID_ISLAND_BONE)
        if vg is None:
            vg = mesh_obj.vertex_groups.new(name=RIGID_ISLAND_BONE)
        vg.add(rigide, 1.0, 'REPLACE')

    _parent_to_armature(mesh_obj, arm_obj)
    return note
