#!/usr/bin/env python3
# glb2mod.py
#
# compatible "rigid packet" exporter:
# - Each packet palette size == 1 (indicesCount = 1)
# - Display list PNMTXIDX always selects slot 0
# - Geometry grouped by dominant joint and vertices are DUPLICATED per joint
# - Vertex positions/normals are converted into THAT JOINT'S LOCAL SPACE
#   (because importer uses WEIGHT_TYPE.RELATIVE_TO_BONE)
#   textures may not work yet. I haven't tested.
#
# Rebuilds:
#  - 0x10 positions
#  - 0x11 normals
#  - 0x18 texcoord0 (only if template expects it)
#  - 0x40 VertexMatrix  (values are rigid joint indices)
#  - 0x41 MatrixEnvelope (empty)
#  - 0x50 Mesh (packets + display lists)

import struct
import numpy as np
from pathlib import Path
from collections import defaultdict
from pygltflib import GLTF2

ALIGN = 0x20

def align(n, a=ALIGN):
    return (n + (a - 1)) & ~(a - 1)

class Writer:
    def __init__(self):
        self.buf = bytearray()

    @property
    def pos(self):
        return len(self.buf)

    def pad_to(self, a=ALIGN):
        while (self.pos % a) != 0:
            self.buf += b"\x00"

    def write(self, b: bytes):
        self.buf += b

    def u32(self, v): self.buf += struct.pack(">I", int(v))
    def i32(self, v): self.buf += struct.pack(">i", int(v))
    def u16(self, v): self.buf += struct.pack(">H", int(v))
    def i16(self, v): self.buf += struct.pack(">h", int(v))
    def u8(self, v): self.buf.append(int(v) & 0xFF)
    def f32(self, v): self.buf += struct.pack(">f", float(v))

    def patch_u32(self, off, v):
        self.buf[off:off+4] = struct.pack(">I", int(v))

# ---------------- MOD chunk IO ----------------

def parse_chunks(buf: bytes):
    pos = 0
    chunks = []
    while pos < len(buf):
        if pos % ALIGN != 0:
            raise ValueError(f"unaligned chunk at {pos:#x}")
        cid, length = struct.unpack_from(">II", buf, pos)
        payload = buf[pos+8:pos+8+length]
        chunks.append((cid, payload))
        if cid == 0xFFFF:
            break
        pos = align(pos + 8 + length, ALIGN)
    return chunks

def write_chunk_raw(w: Writer, cid: int, payload: bytes):
    w.pad_to(ALIGN)
    w.u32(cid)
    w.u32(len(payload))
    w.write(payload)
    w.pad_to(ALIGN)

def write_chunk_build(w: Writer, cid: int, build_fn):
    w.pad_to(ALIGN)
    w.u32(cid)
    len_off = w.pos
    w.u32(0)
    payload_start = w.pos
    build_fn(w)
    payload_end = w.pos
    w.patch_u32(len_off, payload_end - payload_start)
    w.pad_to(ALIGN)

# ---------------- GLB accessor reading ----------------

def glb_read_accessor(gltf: GLTF2, acc_index: int) -> np.ndarray:
    acc = gltf.accessors[acc_index]
    bv = gltf.bufferViews[acc.bufferView]
    buf = gltf.buffers[bv.buffer]
    blob = gltf.get_data_from_buffer_uri(buf.uri)

    comp_dtype = {
        5120: np.int8,
        5121: np.uint8,
        5122: np.int16,
        5123: np.uint16,
        5125: np.uint32,
        5126: np.float32,
    }[acc.componentType]

    num_comp = {
        "SCALAR": 1,
        "VEC2": 2,
        "VEC3": 3,
        "VEC4": 4,
        "MAT4": 16,
    }[acc.type]

    base_off = (bv.byteOffset or 0) + (acc.byteOffset or 0)
    stride = bv.byteStride or (np.dtype(comp_dtype).itemsize * num_comp)
    count = acc.count
    packed = np.dtype(comp_dtype).itemsize * num_comp

    if stride == packed:
        raw = blob[base_off:base_off + packed * count]
        return np.frombuffer(raw, dtype=comp_dtype).reshape((count, num_comp)).copy()

    out = np.zeros((count, num_comp), dtype=comp_dtype)
    for i in range(count):
        row = blob[base_off + i * stride: base_off + i * stride + packed]
        out[i, :] = np.frombuffer(row, dtype=comp_dtype, count=num_comp)
    return out

# ---------------- Transforms (global axis/rot fixes for vertices) ----------------

def apply_axis_fix(V: np.ndarray, N: np.ndarray, mode: str):
    if mode == "none":
        return V, N
    if mode == "x_neg_90":     # (x, y, z) -> (x, z, -y)
        V2 = V[:, [0, 2, 1]].copy(); V2[:, 2] *= -1
        N2 = N[:, [0, 2, 1]].copy(); N2[:, 2] *= -1
        return V2, N2
    if mode == "x_pos_90":     # (x, y, z) -> (x, -z, y)
        V2 = V[:, [0, 2, 1]].copy(); V2[:, 1] *= -1
        N2 = N[:, [0, 2, 1]].copy(); N2[:, 1] *= -1
        return V2, N2
    if mode == "y_pos_90":     # (x, y, z) -> (z, y, -x)
        V2 = V[:, [2, 1, 0]].copy(); V2[:, 2] *= -1
        N2 = N[:, [2, 1, 0]].copy(); N2[:, 2] *= -1
        return V2, N2
    if mode == "y_neg_90":     # (x, y, z) -> (-z, y, x)
        V2 = V[:, [2, 1, 0]].copy(); V2[:, 0] *= -1
        N2 = N[:, [2, 1, 0]].copy(); N2[:, 0] *= -1
        return V2, N2
    if mode == "flip_z":       # (x, y, z) -> (x, y, -z)
        V2 = V.copy(); V2[:, 2] *= -1
        N2 = N.copy(); N2[:, 2] *= -1
        return V2, N2
    raise ValueError(f"unknown axis mode: {mode}")

def rot_matrix_xyz(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    rx = np.deg2rad(rx_deg); ry = np.deg2rad(ry_deg); rz = np.deg2rad(rz_deg)
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    Rx = np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]], dtype=np.float32)
    Ry = np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]], dtype=np.float32)
    Rz = np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]], dtype=np.float32)
    return (Rz @ Ry @ Rx).astype(np.float32)

def apply_extra_rotation(V: np.ndarray, N: np.ndarray, rx: float, ry: float, rz: float):
    if (rx, ry, rz) == (0.0, 0.0, 0.0):
        return V, N
    R = rot_matrix_xyz(rx, ry, rz)
    V2 = (V @ R.T).astype(np.float32)
    N2 = (N @ R.T).astype(np.float32)
    ln = np.linalg.norm(N2, axis=1)
    ln = np.where(ln == 0, 1.0, ln).astype(np.float32)
    N2 = (N2 / ln[:, None]).astype(np.float32)
    return V2, N2

# ---------------- Chunk builders 0x10/0x11/0x18 ----------------

def build_vec3_chunk(w: Writer, A: np.ndarray):
    w.u32(A.shape[0])
    w.write(b"\x00" * 0x14)  # pad payload header to 0x18
    for x, y, z in A:
        w.f32(x); w.f32(y); w.f32(z)
    w.pad_to(ALIGN)

def build_uv_chunk(w: Writer, UV: np.ndarray):
    w.u32(UV.shape[0])
    w.write(b"\x00" * 0x14)
    for u, v in UV:
        w.f32(u); w.f32(v)
    w.pad_to(ALIGN)

def build_chunk_41_empty(w: Writer):
    w.u32(0)
    w.write(b"\x00" * 0x14)
    w.pad_to(ALIGN)

def build_chunk_40(w: Writer, vtx_matrix_values):
    w.u32(len(vtx_matrix_values))
    w.write(b"\x00" * 0x14)
    for s in vtx_matrix_values:
        w.i16(int(s))
    w.pad_to(ALIGN)

# ---------------- VertexDescriptor decode ----------------

def parse_vdesc_bits(vdesc: int):
    has_posmtx = (vdesc & 1) != 0
    has_tex1mtx = (vdesc & 2) != 0
    tmp = vdesc >> 2
    has_color0 = (tmp & 1) != 0
    tmp >>= 1
    texcoord_mask = tmp & 0xFF
    has_tex0 = (texcoord_mask & 1) != 0
    return has_posmtx, has_tex1mtx, has_color0, has_tex0

# ---------------- 0x50 parser (template settings) ----------------

def parse_mesh_chunk_payload(payload_50: bytes):
    off = 0
    meshCount = struct.unpack_from(">I", payload_50, off)[0]
    off = 0x18

    meshes = []
    for _ in range(meshCount):
        boneIndex, vdesc, packetCount = struct.unpack_from(">III", payload_50, off)
        off += 12
        packets = []
        for _pk in range(packetCount):
            idxCount = struct.unpack_from(">I", payload_50, off)[0]
            off += 4
            indices = list(struct.unpack_from(f">{idxCount}h", payload_50, off)) if idxCount else []
            off += idxCount * 2

            dlistCount = struct.unpack_from(">I", payload_50, off)[0]
            off += 4
            dlists = []
            for _dl in range(dlistCount):
                flags = bytes(payload_50[off:off+3])
                cull = payload_50[off+3]
                off += 4
                cmdCount = struct.unpack_from(">I", payload_50, off)[0]
                off += 4
                dlen = struct.unpack_from(">i", payload_50, off)[0]
                off += 4

                file_mod = (8 + off) % ALIGN
                if file_mod != 0:
                    off += (ALIGN - file_mod)

                data = bytes(payload_50[off:off+dlen])
                off += dlen
                dlists.append({"flags": flags, "cull": cull, "cmdCount": cmdCount, "dlistData": data})
            packets.append({"indices": indices, "displaylists": dlists})
        meshes.append({"boneIndex": boneIndex, "vtxDescriptor": vdesc, "packets": packets})

    return {"meshCount": meshCount, "meshes": meshes}

# ---------------- Joint chunk (0x60) parsing + bind matrices ----------------

def parse_joint60_full(payload_60: bytes):
    count = struct.unpack_from(">I", payload_60, 0)[0]
    off = 0x18
    parents = []
    scales = []
    rots = []
    poss = []

    for _ in range(count):
        parent = struct.unpack_from(">I", payload_60, off)[0]; off += 4
        _flags = struct.unpack_from(">I", payload_60, off)[0]; off += 4
        off += 12 + 12 + 4  # boundsMax, boundsMin, radius
        sx, sy, sz = struct.unpack_from(">fff", payload_60, off); off += 12
        rx, ry, rz = struct.unpack_from(">fff", payload_60, off); off += 12
        px, py, pz = struct.unpack_from(">fff", payload_60, off); off += 12
        matcnt = struct.unpack_from(">I", payload_60, off)[0]; off += 4 + matcnt * 4

        parents.append(-1 if parent == 0xFFFFFFFF else int(parent))
        scales.append((float(sx), float(sy), float(sz)))
        rots.append((float(rx), float(ry), float(rz)))
        poss.append((float(px), float(py), float(pz)))

    return count, parents, scales, rots, poss

def mat4_identity():
    return np.eye(4, dtype=np.float32)

def mat4_translate(t):
    x,y,z = t
    m = mat4_identity()
    m[0,3]=x; m[1,3]=y; m[2,3]=z
    return m

def mat4_scale(s):
    x,y,z = s
    m = mat4_identity()
    m[0,0]=x; m[1,1]=y; m[2,2]=z
    return m

def mat4_rot_xyz_radians(rx, ry, rz):
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)

    Rx = np.array([[1,0,0,0],
                   [0,cx,-sx,0],
                   [0,sx,cx,0],
                   [0,0,0,1]], dtype=np.float32)

    Ry = np.array([[cy,0,sy,0],
                   [0,1,0,0],
                   [-sy,0,cy,0],
                   [0,0,0,1]], dtype=np.float32)

    Rz = np.array([[cz,-sz,0,0],
                   [sz,cz,0,0],
                   [0,0,1,0],
                   [0,0,0,1]], dtype=np.float32)

    return (Rz @ Ry @ Rx).astype(np.float32)

def build_bind_world_mats(count, parents, scales, rots, poss):
    local = []
    for i in range(count):
        S = mat4_scale(scales[i])
        R = mat4_rot_xyz_radians(*rots[i])
        T = mat4_translate(poss[i])
        local.append((T @ R @ S).astype(np.float32))

    world = [mat4_identity() for _ in range(count)]
    for i in range(count):
        p = parents[i]
        world[i] = local[i] if p == -1 else (world[p] @ local[i]).astype(np.float32)

    inv_world = [np.linalg.inv(world[i]).astype(np.float32) for i in range(count)]
    return world, inv_world

# ---------------- Stripify ----------------

def stripify(tris: np.ndarray):
    tris = [tuple(map(int, t)) for t in tris]
    edge_to_tri = defaultdict(list)
    for ti, (a, b, c) in enumerate(tris):
        edge_to_tri[(a, b)].append((ti, c))
        edge_to_tri[(b, c)].append((ti, a))
        edge_to_tri[(c, a)].append((ti, b))

    used = [False] * len(tris)
    strips = []
    for ti, (a, b, c) in enumerate(tris):
        if used[ti]:
            continue
        strip = [a, b, c]
        used[ti] = True

        while len(strip) >= 2:
            x, y = strip[-2], strip[-1]
            cand = edge_to_tri.get((y, x), [])
            nxt = None
            for tindex, z in cand:
                if not used[tindex]:
                    nxt = (tindex, z)
                    break
            if nxt is None:
                break
            tindex, z = nxt
            strip.append(z)
            used[tindex] = True

        strips.append(strip)
    return strips

# ---------------- Rigid grouping ----------------

def dominant_joint(joints4: np.ndarray, weights4: np.ndarray):
    idx = np.argmax(weights4, axis=1)
    return joints4[np.arange(joints4.shape[0]), idx].astype(np.int32)

def group_faces_by_joint(F: np.ndarray, v_joint: np.ndarray):
    groups = defaultdict(list)
    for (a, b, c) in F:
        ja, jb, jc = int(v_joint[a]), int(v_joint[b]), int(v_joint[c])
        if ja == jb or ja == jc:
            jt = ja
        elif jb == jc:
            jt = jb
        else:
            jt = ja
        groups[jt].append((int(a), int(b), int(c)))
    return groups

# ---------------- Display list bytes (rigid) ----------------

def build_packet_dlist(strips, record_size: int):
    out = bytearray()
    total_vertices = 0
    strip_count = 0

    for strip in strips:
        if len(strip) < 3:
            continue
        strip_count += 1
        out.append(0x98)               # GX_TRIANGLESTRIP
        out += struct.pack(">H", len(strip))
        for vi in strip:
            out.append(0)              # PNMTXIDX slot 0
            out += struct.pack(">H", int(vi))  # pos
            out += struct.pack(">H", int(vi))  # nrm
            if record_size == 7:
                out += struct.pack(">H", int(vi))  # uv
            total_vertices += 1

    return bytes(out), total_vertices, strip_count

# ---------------- Build 0x50 rigid packets ----------------

def build_chunk_50_rigid_packets(w: Writer, bone_index: int, vdesc: int, packets_built, flags: bytes, cull: int):
    w.u32(1)        # meshCount
    w.pad_to(ALIGN)

    w.u32(bone_index)
    w.u32(vdesc)
    w.u32(len(packets_built))

    for pkt in packets_built:
        w.u32(1)                          # indicesCount == 1 (yel rigid)
        w.i16(int(pkt["palette_entry"]))  # INDEX into 0x40 list

        w.u32(1)        # displayListCount
        w.write(flags)
        w.u8(cull & 0xFF)
        w.u32(int(pkt["cmdCount"]))

        dlist = pkt["dlistData"]
        w.i32(len(dlist))
        w.pad_to(ALIGN)
        w.write(dlist)

# ---------------- Main convert ----------------

def convert(template_mod: str, glb_path: str, out_path: str,
            axis_mode: str = "x_neg_90",
            rot_xyz=(0.0, 0.0, 0.0),
            scale: float = 1.0):

    tmpl = Path(template_mod).read_bytes()
    chunks = parse_chunks(tmpl)
    chunk_map = {cid: payload for cid, payload in chunks}

    if 0x60 not in chunk_map:
        raise ValueError("Template has no 0x60 joint chunk; required for RELATIVE_TO_BONE conversion.")

    joint_count, parents, scales, rots, poss = parse_joint60_full(chunk_map[0x60])
    _, inv_bind_world = build_bind_world_mats(joint_count, parents, scales, rots, poss)

    if 0x50 not in chunk_map:
        raise ValueError("Template has no 0x50 chunk.")

    tmpl50 = parse_mesh_chunk_payload(chunk_map[0x50])
    mesh0 = tmpl50["meshes"][0]
    bone_index = int(mesh0["boneIndex"])
    vdesc = int(mesh0["vtxDescriptor"])

    # FIND A TEMPLATE DISPLAY LIST (defines found_dl)
    found_dl = None
    for m in tmpl50["meshes"]:
        for p in m["packets"]:
            if p["displaylists"]:
                found_dl = p["displaylists"][0]
                break
        if found_dl:
            break
    if not found_dl:
        raise ValueError("Template has no display list.")

    flags = found_dl["flags"]
    cull = int(found_dl["cull"])
    tmpl_cmdCount = int(found_dl["cmdCount"])
    tmpl_dlistData = found_dl["dlistData"]

    has_posmtx, _, _, has_tex0 = parse_vdesc_bits(vdesc)
    if not has_posmtx:
        raise ValueError(f"Template vdesc={vdesc} does NOT include PosMatIdx. Cannot use yel rigid packets.")

    record_size = 7 if has_tex0 else 5
    print(f"[TEMPLATE] boneIndex={bone_index} vdesc={vdesc} record={record_size} flags={flags.hex()} cull={cull}")
    print(f"[JOINTS] jointCount={joint_count}")

    # Determine cmd_mode
    off = 0
    strips = 0
    verts = 0
    while off < len(tmpl_dlistData):
        cmd = tmpl_dlistData[off]
        if cmd != 0x98:
            break
        if off + 3 > len(tmpl_dlistData):
            break
        n = struct.unpack_from(">H", tmpl_dlistData, off + 1)[0]
        off += 3
        strips += 1
        verts += n
        off += n * record_size

    if tmpl_cmdCount == strips:
        cmd_mode = "strips"
    elif tmpl_cmdCount == verts:
        cmd_mode = "verts"
    else:
        # safest default to avoid overread in many engines
        cmd_mode = "strips"
    print(f"[TEMPLATE] cmdCount={tmpl_cmdCount} strips={strips} verts={verts} -> cmd_mode={cmd_mode}")

    # ---- Load GLB ----
    gltf = GLTF2().load(glb_path)
    prim = gltf.meshes[0].primitives[0]
    attrs = prim.attributes

    V = glb_read_accessor(gltf, attrs.POSITION).astype(np.float32)
    N = glb_read_accessor(gltf, attrs.NORMAL).astype(np.float32)

    if getattr(attrs, "JOINTS_0", None) is None or getattr(attrs, "WEIGHTS_0", None) is None:
        raise ValueError("GLB must have JOINTS_0 and WEIGHTS_0 for rigid packet build.")
    joints4 = glb_read_accessor(gltf, attrs.JOINTS_0).astype(np.int32)
    weights4 = glb_read_accessor(gltf, attrs.WEIGHTS_0).astype(np.float32)

    if prim.indices is None:
        raise ValueError("GLB primitive has no indices.")
    I = glb_read_accessor(gltf, prim.indices).reshape((-1,)).astype(np.int32)
    if I.size % 3 != 0:
        raise ValueError("indices not divisible by 3")
    F = I.reshape((-1, 3))

    if has_tex0 and getattr(attrs, "TEXCOORD_0", None) is not None:
        UV = glb_read_accessor(gltf, attrs.TEXCOORD_0).astype(np.float32)
        if UV.shape[1] > 2:
            UV = UV[:, :2].copy()
    else:
        xz = V[:, [0, 2]]
        mn = xz.min(axis=0); mx = xz.max(axis=0)
        span = np.where((mx - mn) == 0, 1, (mx - mn))
        UV = ((xz - mn) / span).astype(np.float32)

    # global transforms to game space
    if scale != 1.0:
        V = (V * float(scale)).astype(np.float32)
    V, N = apply_axis_fix(V, N, axis_mode)
    V, N = apply_extra_rotation(V, N, *rot_xyz)

    # ---- RIGIDIZE ----
    v_joint = dominant_joint(joints4, weights4)
    v_joint = np.clip(v_joint, 0, joint_count - 1).astype(np.int32)

    face_groups = group_faces_by_joint(F, v_joint)
    joints_used = sorted(face_groups.keys())
    print(f"[RIGID] jointsUsed={len(joints_used)} packets={len(joints_used)}")

    # 0x40 contains VALUES (joint ids), but meshPacket.indices stores INDEX into this array.
    vtxMatrix_vals = [int(j) for j in joints_used]
    joint_to_vtx40_index = {j: i for i, j in enumerate(joints_used)}
    print(f"[0x40] count={len(vtxMatrix_vals)}")

    # ---- Build new global vertex arrays by duplicating per (joint, oldVertex) ----
    newV = []
    newN = []
    newUV = []
    remap_v = {}  # (joint, oldIndex) -> newIndex

    def to_joint_local(joint_id: int, p_world: np.ndarray, n_world: np.ndarray):
        invM = inv_bind_world[joint_id]
        p4 = np.array([p_world[0], p_world[1], p_world[2], 1.0], dtype=np.float32)
        pl = (invM @ p4)[:3]
        inv3 = invM[:3, :3]
        nl = (inv3 @ n_world).astype(np.float32)
        ln = float(np.linalg.norm(nl))
        if ln > 1e-8:
            nl /= ln
        return pl.astype(np.float32), nl.astype(np.float32)

    packets_built = []

    for j in joints_used:
        tris = np.array(face_groups[j], dtype=np.int32)

        tris_new = np.zeros_like(tris)
        for ti in range(tris.shape[0]):
            for k in range(3):
                old_idx = int(tris[ti, k])
                key = (int(j), old_idx)
                if key in remap_v:
                    tris_new[ti, k] = remap_v[key]
                else:
                    p_local, n_local = to_joint_local(int(j), V[old_idx], N[old_idx])
                    new_idx = len(newV)
                    newV.append(p_local)
                    newN.append(n_local)
                    newUV.append(UV[old_idx])
                    remap_v[key] = new_idx
                    tris_new[ti, k] = new_idx

        strips_list = stripify(tris_new)
        dlist_bytes, total_verts, strip_count = build_packet_dlist(strips_list, record_size=record_size)
        cmdCount = int(strip_count if cmd_mode == "strips" else total_verts)

        packets_built.append({
            "palette_entry": joint_to_vtx40_index[int(j)],  # INDEX into 0x40 list
            "dlistData": dlist_bytes,
            "cmdCount": cmdCount
        })

    newV = np.asarray(newV, dtype=np.float32)
    newN = np.asarray(newN, dtype=np.float32)
    newUV = np.asarray(newUV, dtype=np.float32)

    print(f"[VERTS] old={V.shape[0]} new={newV.shape[0]} (duplicated per-joint)")
    print(f"[PACKETS] count={len(packets_built)} (paletteSize=1 each)")

    # ---- Write output MOD ----
    w = Writer()
    for cid, payload in chunks:
        if cid == 0x10:
            write_chunk_build(w, cid, lambda ww: build_vec3_chunk(ww, newV))
        elif cid == 0x11:
            write_chunk_build(w, cid, lambda ww: build_vec3_chunk(ww, newN))
        elif cid == 0x18:
            if has_tex0:
                write_chunk_build(w, cid, lambda ww: build_uv_chunk(ww, newUV))
            else:
                write_chunk_raw(w, cid, payload)
        elif cid == 0x40:
            write_chunk_build(w, cid, lambda ww: build_chunk_40(ww, vtxMatrix_vals))
        elif cid == 0x41:
            write_chunk_build(w, cid, lambda ww: build_chunk_41_empty(ww))
        elif cid == 0x50:
            write_chunk_build(w, cid, lambda ww: build_chunk_50_rigid_packets(
                ww,
                bone_index=bone_index,
                vdesc=vdesc,
                packets_built=packets_built,
                flags=flags,
                cull=cull
            ))
        else:
            write_chunk_raw(w, cid, payload)

    Path(out_path).write_bytes(w.buf)
    print(f"[OK] wrote {out_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GLB -> MOD (yelModel rigid packet skinning, bone-local verts).")
    parser.add_argument("-t", "--template", required=True, help="Template .mod (use yelModel.mod).")
    parser.add_argument("-g", "--glb", required=True, help="Input .glb")
    parser.add_argument("-o", "--out", default=None, help="Output .mod")
    parser.add_argument("--axis", default="x_neg_90",
                        choices=["x_neg_90", "x_pos_90", "y_pos_90", "y_neg_90", "flip_z", "none"])
    parser.add_argument("--rot", default="0,0,0", help="extra rotation degrees rx,ry,rz")
    parser.add_argument("--scale", type=float, default=1.0)

    args = parser.parse_args()
    rx, ry, rz = [float(x.strip()) for x in args.rot.split(",")]

    out = args.out
    if out is None:
        out = str(Path(args.glb).with_name(Path(args.glb).stem + "_yel_rigid_FIXED.mod"))

    convert(args.template, args.glb, out,
            axis_mode=args.axis,
            rot_xyz=(rx, ry, rz),
            scale=args.scale)