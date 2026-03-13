import argparse, struct, json, math, base64, io
from pathlib import Path
from collections import defaultdict
import numpy as np

ALIGN = 0x20

# ---- Embedded presets extracted from a known-good vanilla MOD ("snake.mod") ----
_PRESET_22_SNAKE_B64 = "AAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAcAAAEBAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAUAAAACAAAAAAAA"
_PRESET_30_SNAKE_B64 = "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AAAAAD8AAAA/AAAAAAAAAAAAAAAAAAAAAAABAQAAAAL/////AAAAAP////8AAAAAP4AAAAAAAAAAAAAAAAAA0UMH6JAAAAAAAHEABwAAAwMAADAQAAAAADwj1wo8I9cKPCPXCgAAAAEAAQQKAAAAAQAAAAUAAQABAAAEAgAAAP8AAAAAP4AAAD+AAAA/gAAAAAAAAAAAAAAAAAAAPwAAAD8AAAAAAAAAAAAAAAAAAAAAAAEBAAAAA/////8AAAAB/////wAAAAA/gAAAAAAAAAAAAAAAAADTQwfokAAAAAAAcQAHAAADAwAAMBAAAAAAPCPXCjwj1wo8I9cKAAAAAQABBAoAAAABAAAABgABAAEAAAQCAAAA/wAAAAA/gAAAP4AAAD+AAAAAAAAAAAAAAAAAAAA/AAAAPwAAAAAAAAAAAAAAAAAAAAAAAQEAAAAE/////wAAAAD/////AAAAAD+AAAAAAAAAAAAAAAAAANFDB+iQAAAAAABxAAcAAAMDAAAwEAAAAAA8I9cKPCPXCjwj1woAAAABAAEECgAAAAEAAAABAAEAAQAABAIAAAD/AAAAAD+AAAA/gAAAP4AAAAAAAAAAAAAAAAAAAD8AAAA/AAAAAAAAAAAAAAAAAAAAAAABAQAAAAX/////AAAAAf////8AAAAAP4AAAAAAAAAAAAAAAAAA00MH6JAAAAAAAHEABwAAAwMAADAQAAAAADwj1wo8I9cKPCPXCgAAAAEAAQQKAAAAAQAAAAcAAgABAAAEAgAAAP8AAAAAP4AAAD+AAAA/gAAAAAAAAAAAAAAAAAAAPwAAAD8AAAAAAAAAAAAAAAAAAAAAAAIBAAAABv////8AAAAA/////wAAAAA/gAAAAAAAAAAAAAAAAADRQwfokAAAAAAAcQAHAAADAQAANUEAAAAAPCPXCjwj1wo8I9cKAAAAAQABBAoAAAABAAAAAAABAAEAAAQCAAAA/wAAAAA/gAAAP4AAAD+AAAAAAAAAAAAAAAAAAAA/AAAAPwAAAAAAAAAAAAAAAAAAAAAAAgEAAAAH/////wAAAAD/////AAAAAD+AAAAAAAAAAAAAAAAAANFDB+iQAAAAAABxAAcAAAMBAAA1QQAAAAA8I9cKPCPXCjwj1woAAAABAAEECgAAAAEAAAAAAAEAAQAABAIAAAD/AAAAAD+AAAA/gAAAP4AAAAAAAAAAAAAAAAAAAD8AAAA/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

def _b64(b64s: str) -> bytes:
    return base64.b64decode(b64s.encode("ascii"))

def align(n, a=ALIGN):
    return (n + (a - 1)) & ~(a - 1)

class Writer:
    def __init__(self):
        self.buf = bytearray()
    @property
    def pos(self):
        return len(self.buf)
    def pad_to(self, a=ALIGN):
        while self.pos % a:
            self.buf += b"\x00"
    def write(self, b: bytes):
        self.buf += b
    def u32(self, v): self.buf += struct.pack(">I", int(v) & 0xFFFFFFFF)
    def i32(self, v): self.buf += struct.pack(">i", int(v))
    def i16(self, v): self.buf += struct.pack(">h", int(v))
    def u16(self, v): self.buf += struct.pack(">H", int(v) & 0xFFFF)
    def u8(self, v):  self.buf.append(int(v) & 0xFF)
    def f32(self, v): self.buf += struct.pack(">f", float(v))
    def patch_u32(self, off, v):
        self.buf[off:off+4] = struct.pack(">I", int(v) & 0xFFFFFFFF)

def write_chunk(w: Writer, cid: int, build_fn):
    # Chunk length must include padding up to next 0x20 boundary.
    w.pad_to(ALIGN)
    w.u32(cid)
    len_off = w.pos
    w.u32(0)
    payload_start = w.pos
    build_fn(w)
    w.pad_to(ALIGN)
    w.patch_u32(len_off, w.pos - payload_start)

# ---------------- GLB parsing (manual, JSON+BIN) ----------------
COMP_DTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NUM_COMP   = {"SCALAR":1, "VEC2":2, "VEC3":3, "VEC4":4, "MAT4":16}

def load_glb(path: Path):
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("File too small to be a .glb")
    magic, ver, _ = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or ver != 2:
        raise ValueError("Not a glTF 2.0 .glb")
    off = 12
    json_chunk = None
    bin_chunk = None
    while off + 8 <= len(data):
        clen, ctype = struct.unpack_from("<I4s", data, off)
        off += 8
        chunk = data[off:off+clen]
        off += clen
        if ctype == b"JSON":
            json_chunk = chunk
        elif ctype == b"BIN\x00":
            bin_chunk = chunk
        if off % 4:
            off = (off + 3) & ~3
    if json_chunk is None or bin_chunk is None:
        raise ValueError("Missing JSON or BIN chunk (export as .glb, not .gltf)")
    return json.loads(json_chunk.decode("utf-8")), bin_chunk

def read_accessor(j, bin_blob: bytes, acc_index: int) -> np.ndarray:
    acc = j["accessors"][acc_index]
    bv  = j["bufferViews"][acc["bufferView"]]
    comp = COMP_DTYPE[acc["componentType"]]
    ncomp = NUM_COMP[acc["type"]]
    count = acc["count"]
    base_off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", np.dtype(comp).itemsize * ncomp)
    packed = np.dtype(comp).itemsize * ncomp
    if stride == packed:
        raw = bin_blob[base_off: base_off + packed * count]
        return np.frombuffer(raw, dtype=comp).reshape((count, ncomp)).copy()
    out = np.zeros((count, ncomp), dtype=comp)
    for i in range(count):
        row = bin_blob[base_off + i*stride : base_off + i*stride + packed]
        out[i, :] = np.frombuffer(row, dtype=comp, count=ncomp)
    return out

# ---------------- math helpers ----------------
def quat_to_euler_xyz(q):
    x, y, z, w = q
    t0 = 2*(w*x + y*z); t1 = 1 - 2*(x*x + y*y)
    rx = math.atan2(t0, t1)
    t2 = 2*(w*y - z*x)
    t2 = 1 if t2 > 1 else (-1 if t2 < -1 else t2)
    ry = math.asin(t2)
    t3 = 2*(w*z + x*y); t4 = 1 - 2*(y*y + z*z)
    rz = math.atan2(t3, t4)
    return (rx, ry, rz)

def mat4_identity(): return np.eye(4, dtype=np.float32)
def mat4_translate(t):
    m = mat4_identity(); m[:3, 3] = t; return m
def mat4_scale(s):
    m = mat4_identity(); m[0,0], m[1,1], m[2,2] = s; return m
def mat4_rot_xyz(rx, ry, rz):
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = np.array([[1,0,0,0],[0,cx,-sx,0],[0,sx,cx,0],[0,0,0,1]], np.float32)
    Ry = np.array([[cy,0,sy,0],[0,1,0,0],[-sy,0,cy,0],[0,0,0,1]], np.float32)
    Rz = np.array([[cz,-sz,0,0],[sz,cz,0,0],[0,0,1,0],[0,0,0,1]], np.float32)
    return (Rz @ Ry @ Rx).astype(np.float32)

def build_world_mats(parents, scales, eulers, poss):
    local = [(mat4_translate(p) @ mat4_rot_xyz(*r) @ mat4_scale(s)).astype(np.float32)
             for s, r, p in zip(scales, eulers, poss)]
    world = [mat4_identity() for _ in local]
    for i in range(len(local)):
        p = parents[i]
        world[i] = local[i] if p == -1 else (world[p] @ local[i]).astype(np.float32)
    inv = [np.linalg.inv(w).astype(np.float32) for w in world]
    return world, inv

def apply_axis_fix(V, N, mode):
    if mode == "none":
        return V, N
    if mode == "x_neg_90":
        V2 = V[:, [0,2,1]].copy(); V2[:, 2] *= -1
        N2 = N[:, [0,2,1]].copy(); N2[:, 2] *= -1
        return V2, N2
    raise ValueError("Unknown axis mode: " + mode)

def rot_matrix_xyz_deg(rx, ry, rz):
    rx, ry, rz = map(math.radians, [rx, ry, rz])
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]], np.float32)
    Ry = np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]], np.float32)
    Rz = np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]], np.float32)
    return (Rz @ Ry @ Rx).astype(np.float32)

def apply_extra_rot(V, N, rx, ry, rz):
    if (rx, ry, rz) == (0,0,0):
        return V, N
    R = rot_matrix_xyz_deg(rx, ry, rz)
    V2 = (V @ R.T).astype(np.float32)
    N2 = (N @ R.T).astype(np.float32)
    ln = np.linalg.norm(N2, axis=1); ln = np.where(ln == 0, 1, ln)
    return V2, (N2 / ln[:, None]).astype(np.float32)

# ---------------- rigid packet building ----------------
def stripify(tris):
    tris = [tuple(map(int, t)) for t in tris]
    edge_to_tri = defaultdict(list)
    for ti, (a,b,c) in enumerate(tris):
        edge_to_tri[(a,b)].append((ti,c))
        edge_to_tri[(b,c)].append((ti,a))
        edge_to_tri[(c,a)].append((ti,b))
    used = [False] * len(tris)
    strips = []
    for ti, (a,b,c) in enumerate(tris):
        if used[ti]:
            continue
        strip = [a,b,c]; used[ti] = True
        while True:
            x, y = strip[-2], strip[-1]
            cand = edge_to_tri.get((y,x), [])
            nxt = None
            for tindex, z in cand:
                if not used[tindex]:
                    nxt = (tindex, z); break
            if nxt is None:
                break
            tindex, z = nxt
            strip.append(z); used[tindex] = True
        strips.append(strip)
    return strips

def build_packet_dlist(strips, has_uv=True):
    out = bytearray()
    strip_count = 0
    for strip in strips:
        if len(strip) < 3:
            continue
        strip_count += 1
        out.append(0x98)                       # GX_Begin (triangle strip)
        out += struct.pack(">H", len(strip))
        for vi in strip:
            out.append(0)                      # PNMTXIDX slot 0
            out += struct.pack(">H", int(vi))  # pos idx
            out += struct.pack(">H", int(vi))  # nrm idx
            if has_uv:
                out += struct.pack(">H", int(vi))  # uv idx
    return bytes(out), strip_count

def dominant_joint(joints4, weights4):
    idx = np.argmax(weights4, axis=1)
    return joints4[np.arange(joints4.shape[0]), idx].astype(np.int32)

def group_faces_by_joint(F, v_joint):
    groups = defaultdict(list)
    for a,b,c in F:
        ja, jb, jc = int(v_joint[a]), int(v_joint[b]), int(v_joint[c])
        if ja == jb or ja == jc: jt = ja
        elif jb == jc: jt = jb
        else: jt = ja
        groups[jt].append((int(a), int(b), int(c)))
    return groups

# ---------------- chunk builders ----------------
def build_header_chunk(w: Writer):
    # 0x38 bytes, only timestamp is currently meaningful to us.
    b = bytearray(b"\x00" * 0x38)
    struct.pack_into(">I", b, 0x18, 0x07E60226)  # 2026-02-26
    w.write(b)

def build_chunk_vec3(w: Writer, A: np.ndarray):
    w.u32(A.shape[0]); w.write(b"\x00"*0x14)
    for x,y,z in A:
        w.f32(x); w.f32(y); w.f32(z)

def build_chunk_uv(w: Writer, UV: np.ndarray):
    w.u32(UV.shape[0]); w.write(b"\x00"*0x14)
    for u,v in UV:
        w.f32(float(u)); w.f32(float(v))

def build_chunk_22_snake(w: Writer):
    w.write(_b64(_PRESET_22_SNAKE_B64))

def build_chunk_30_snake(w: Writer):
    w.write(_b64(_PRESET_30_SNAKE_B64))

def build_chunk_40(w: Writer, vals):
    w.u32(len(vals)); w.write(b"\x00"*0x14)
    for v in vals:
        w.i16(int(v))

def build_chunk_41_rigid(w: Writer, env_vtx_indices):
    w.u32(len(env_vtx_indices))
    w.write(b"\x00" * 0x14)
    for vtx_idx in env_vtx_indices:
        w.u16(1)
        w.u16(int(vtx_idx))
        w.f32(1.0)

def build_chunk_50(w: Writer, bone_index, vdesc, packets, flags=b"\x01\x00\x00", cull=2):
    # 0x01 in the high byte is the stable vanilla display-list mode.
    # Texturing itself is still controlled by material/TEV state (chunks 0x22/0x30).
    w.u32(1); w.write(b"\x00"*0x14)
    w.u32(bone_index); w.u32(vdesc); w.u32(len(packets))
    for pkt in packets:
        w.u32(1)
        w.i16(int(pkt["envelope_index"]))
        w.u32(1)
        w.write(flags); w.u8(cull)
        w.u32(int(pkt["cmdCount"]))
        d = pkt["dlistData"]
        w.i32(len(d))
        w.pad_to(ALIGN)
        w.write(d)

def build_chunk_60(w: Writer, parents, scales, eulers, poss):
    n = len(parents)
    w.u32(n); w.write(b"\x00"*0x14)
    for i in range(n):
        w.u32(0xFFFFFFFF if parents[i] == -1 else parents[i])
        w.u32(0)
        w.f32(32768.0); w.f32(32768.0); w.f32(32768.0)
        w.f32(-32768.0); w.f32(-32768.0); w.f32(-32768.0)
        w.f32(0.0)
        sx,sy,sz = scales[i]; w.f32(sx); w.f32(sy); w.f32(sz)
        rx,ry,rz = eulers[i]; w.f32(rx); w.f32(ry); w.f32(rz)
        px,py,pz = poss[i];   w.f32(px); w.f32(py); w.f32(pz)
        if i == 0:
            w.u32(1); w.u16(0); w.u16(0)
        else:
            w.u32(0)

# ---------- Texture extraction + GX encode (RGB565) ----------
def _pad_image_rgba(img_rgba: bytes, w: int, h: int, pw: int, ph: int) -> bytes:
    out = bytearray(pw * ph * 4)
    for y in range(ph):
        sy = min(y, h-1)
        for x in range(pw):
            sx = min(x, w-1)
            si = (sy*w + sx) * 4
            di = (y*pw + x) * 4
            out[di:di+4] = img_rgba[si:si+4]
    return bytes(out)

def _rgba_to_gx_rgb565_tiled(img_rgba: bytes, w: int, h: int):
    def next_pow2(n: int) -> int:
        if n <= 1: return 1
        return 1 << (n - 1).bit_length()
    pw = next_pow2(w)
    ph = next_pow2(h)
    pw = (pw + 3) & ~3
    ph = (ph + 3) & ~3
    if pw != w or ph != h:
        img_rgba = _pad_image_rgba(img_rgba, w, h, pw, ph)

    out = bytearray(pw * ph * 2)

    def pack565(r,g,b):
        return ((r>>3)<<11) | ((g>>2)<<5) | (b>>3)

    o = 0
    for ty in range(0, ph, 4):
        for tx in range(0, pw, 4):
            for y in range(4):
                for x in range(4):
                    i = ((ty+y)*pw + (tx+x))*4
                    r,g,b,a = img_rgba[i:i+4]
                    v = pack565(r,g,b)
                    out[o:o+2] = struct.pack(">H", v)
                    o += 2
    return bytes(out), pw, ph

def _extract_basecolor_image_rgba(glb_path: Path):
    from pygltflib import GLTF2
    from PIL import Image
    gltf = GLTF2().load(str(glb_path))

    tex_index = None
    if gltf.materials:
        m0 = gltf.materials[0]
        pbr = getattr(m0, "pbrMetallicRoughness", None)
        bct = getattr(pbr, "baseColorTexture", None) if pbr else None
        if bct and getattr(bct, "index", None) is not None:
            tex_index = bct.index
    if tex_index is None and gltf.textures:
        tex_index = 0
    if tex_index is None:
        return None

    tex = gltf.textures[tex_index]
    img_index = getattr(tex, "source", None)
    if img_index is None or not gltf.images or img_index >= len(gltf.images):
        return None
    img = gltf.images[img_index]

    raw = None
    if img.uri:
        if img.uri.startswith("data:"):
            b64 = img.uri.split(",",1)[1]
            raw = base64.b64decode(b64)
        else:
            p = (glb_path.parent / img.uri)
            if p.exists():
                raw = p.read_bytes()
    elif img.bufferView is not None:
        blob = gltf.binary_blob()
        view = gltf.bufferViews[img.bufferView]
        start = view.byteOffset or 0
        raw = blob[start:start + view.byteLength]

    if raw is None:
        return None

    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    w,h = im.size
    return im.tobytes(), w, h

def _downscale_rgba_max(img_rgba: bytes, w: int, h: int, max_size: int):
    max_size = int(max_size)
    if max_size <= 0 or max(w, h) <= max_size:
        return img_rgba, w, h
    from PIL import Image
    im = Image.frombytes("RGBA", (int(w), int(h)), img_rgba)
    scale = float(max_size) / float(max(w, h))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    lanczos = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    im = im.resize((nw, nh), lanczos)
    return im.tobytes(), nw, nh

def _write_texture_item(w: Writer, tex_gx: bytes, width: int, height: int, fmt_u32: int = 0, mipmaps_u32: int = 1):
    # Matches MeltyTool schema Texture.cs exactly.
    w.u16(width); w.u16(height)
    w.u32(fmt_u32)
    w.u32(mipmaps_u32)
    w.u32(0); w.u32(0); w.u32(0); w.u32(0)   # unknowns[4]
    w.u32(len(tex_gx))
    w.write(tex_gx)

def build_chunk_20_textures_multi(w: Writer, textures, fmt_u32: int, transp_u32: int, tex_count: int = 8):
    """Write a 0x20 textures chunk matching MeltyTool's schema.

    Layout:
      u32 count
      align 0x20 (absolute)
      repeat count times:
        u16 width, u16 height
        u32 format
        u32 mipmapCount
        u32 unknown0..unknown3 (4 u32s)
        u32 dataSize
        data bytes
        align 0x20 (absolute)  # so next header starts aligned

    'textures' is a list of tuples: (gx_bytes, width, height). Entry 0 should be the real texture.
    Remaining slots are filled with a small dummy texture so materials referencing texture IDs > 0 won't crash.
    """
    tex_count = max(1, int(tex_count))
    # Ensure we have enough entries
    textures = list(textures) if textures is not None else []
    if not textures:
        # fallback: 1x1 white in RGB565 tiled (encoder will pad to 4x4)
        rgba = bytes([255, 255, 255, 255])
        dummy_gx, dw, dh = _rgba_to_gx_rgb565_tiled(rgba, 1, 1)
        textures = [(dummy_gx, dw, dh)]
    # pad/fill
    if len(textures) < tex_count:
                # fill remaining slots by repeating slot0 so whatever texID the material uses will still show the real texture
        textures = textures + [textures[0]] * (tex_count - len(textures))
    else:
        textures = textures[:tex_count]

    w.u32(tex_count)
    w.pad_to(ALIGN)  # aligns absolute stream to 0x20 like the reader expects

    for gx_bytes, width, height in textures:
        w.pad_to(ALIGN)
        w.u16(int(width) & 0xFFFF)
        w.u16(int(height) & 0xFFFF)
        w.u32(int(fmt_u32) & 0xFFFFFFFF)
        w.u32(1)  # mipmapCount
        w.u32(0); w.u32(0); w.u32(0); w.u32(0)  # unknowns
        w.u32(len(gx_bytes))
        w.write(gx_bytes)
        w.pad_to(ALIGN)
def build_chunk_20_textures_multi8(w, tex_gx, tw, th, fmt_u32=0, verbose=False, tex_count=8):
    # Use the stable texture chunk writer (from PRESET30 branch) and replicate the same
    # GLB texture into all slots so snake material stages never sample an uninitialized slot.
    items = [(tex_gx, tw, th)] * int(tex_count)
    return build_chunk_20_textures_multi(w, items, fmt_u32=fmt_u32, transp_u32=1, tex_count=int(tex_count))

def planar_uv_from_pos(V: np.ndarray):
    # Project XZ into [0,1], stable for debug.
    xz = V[:, [0,2]]
    mn, mx = xz.min(0), xz.max(0)
    span = np.where((mx - mn) == 0, 1, (mx - mn))
    return ((xz - mn) / span).astype(np.float32)


def _next_pow2(x: int) -> int:
    p = 1
    while p < x:
        p <<= 1
    return p

def _get_basecolor_factor(j, mat_index):
    try:
        mat = j.get("materials", [])[mat_index]
        pbr = mat.get("pbrMetallicRoughness", {})
        f = pbr.get("baseColorFactor", [1,1,1,1])
        return [max(0,min(255,int(round(float(c)*255.0)))) for c in f]
    except Exception:
        return [255,255,255,255]

def _solid_tile_rgba(tile_size: int, rgba):
    r,g,b,a = rgba
    return bytes([r,g,b,a]) * (tile_size*tile_size)

def _decode_to_rgba(image_bytes: bytes, tile_size: int):
    # returns RGBA8 bytes for a square tile_size x tile_size tile (padded)
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    im.thumbnail((tile_size, tile_size))
    tile = Image.new("RGBA", (tile_size, tile_size), (0,0,0,0))
    ox = (tile_size - im.size[0])//2
    oy = (tile_size - im.size[1])//2
    tile.paste(im, (ox, oy))
    return tile.tobytes()

def _material_tile_rgba(j, bin_blob, glb_path: Path, mat_index: int, tile_size: int):
    # If material has baseColorTexture, decode it; else use baseColorFactor as solid tile.
    try:
        mats = j.get("materials", [])
        if not mats or mat_index is None or mat_index >= len(mats):
            return _solid_tile_rgba(tile_size, _get_basecolor_factor(j, 0))
        mat = mats[mat_index]
        pbr = mat.get("pbrMetallicRoughness", {})
        bct = pbr.get("baseColorTexture")
        if not bct:
            return _solid_tile_rgba(tile_size, _get_basecolor_factor(j, mat_index))
        tex_index = int(bct.get("index", 0))
        tex = j.get("textures", [])[tex_index]
        src_idx = int(tex.get("source", 0))
        img = j.get("images", [])[src_idx]

        data = None
        if "bufferView" in img:
            bv = j["bufferViews"][int(img["bufferView"])]
            off = int(bv.get("byteOffset", 0))
            ln = int(bv["byteLength"])
            data = bin_blob[off:off+ln]
        elif "uri" in img:
            uri = img["uri"]
            if uri.startswith("data:"):
                import base64
                data = base64.b64decode(uri.split(",")[1])
            else:
                data = (glb_path.parent / uri).read_bytes()
        if data is None:
            return _solid_tile_rgba(tile_size, _get_basecolor_factor(j, mat_index))
        return _decode_to_rgba(data, tile_size)
    except Exception:
        return _solid_tile_rgba(tile_size, _get_basecolor_factor(j, mat_index))

def _build_material_atlas(j, bin_blob, glb_path: Path, mat_indices, tile_size: int):
    # returns (atlas_rgba_bytes, atlas_w, atlas_h, mat_to_uv_xform)
    from PIL import Image
    import math
    mats = list(mat_indices)
    n = max(1, len(mats))
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    atlas_w = _next_pow2(cols * tile_size)
    atlas_h = _next_pow2(rows * tile_size)
    atlas = Image.new("RGBA", (atlas_w, atlas_h), (0,0,0,0))
    mat_to = {}
    for i, mi in enumerate(mats):
        tile_rgba = _material_tile_rgba(j, bin_blob, glb_path, mi, tile_size)
        tile = Image.frombytes("RGBA", (tile_size, tile_size), tile_rgba)
        cx = i % cols
        cy = i // cols
        x0 = cx * tile_size
        y0 = cy * tile_size
        atlas.paste(tile, (x0, y0))
        su = tile_size / atlas_w
        sv = tile_size / atlas_h
        ou = x0 / atlas_w
        ov = y0 / atlas_h
        mat_to[mi] = (su, sv, ou, ov)
    return (atlas.tobytes(), atlas_w, atlas_h, mat_to)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-g","--glb", required=True, help="Input .glb")
    ap.add_argument("-o","--out", required=True, help="Output .mod")
    ap.add_argument("--axis", default="x_neg_90", choices=["x_neg_90","none"])
    ap.add_argument("--rot", default="90,0,0", help="Extra rotation degrees as RX,RY,RZ")
    ap.add_argument("--scale", default=1.0, type=float)
    ap.add_argument("--uv", default="gltf", choices=["gltf","planar"], help="UV source: gltf uses TEXCOORD_0, planar uses XZ projection (debug)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--tex-count", type=int, default=8, help="How many texture slots to emit (fill all with the same image).")
    ap.add_argument("--max-tex-size", type=int, default=256, help="Clamp source texture to this max dimension before encoding (0 disables clamp).")
    ap.add_argument("--atlas", action="store_true", help="Bake multiple GLB materials into one texture atlas so a single MOD can represent them.")
    ap.add_argument("--atlas-tile", type=int, default=512, help="Atlas tile size (pixels) when --atlas is enabled.")
    args = ap.parse_args()
    if getattr(args, "tex_count", 8) < 8:
        if args.verbose:
            print("[tex] forcing --tex-count to 8 because presets reference multiple slots")
        args.tex_count = 8

    glb_path = Path(args.glb)
    rx,ry,rz = [float(x) for x in args.rot.split(",")]

    j, bin_blob = load_glb(glb_path)

    mesh = j["meshes"][0]
    prims = mesh.get("primitives", [])
    if not prims:
        raise SystemExit("GLB has no primitives to export.")

    # Determine if we need atlas baking
    used_mats = []
    for pr in prims:
        mi = pr.get("material", 0)
        if mi not in used_mats:
            used_mats.append(mi)

    atlas_rgba = None
    atlas_w = atlas_h = None
    uv_xform = {mi: (1.0, 1.0, 0.0, 0.0) for mi in used_mats}

    if len(used_mats) > 1:
        args.atlas = True
        if args.verbose:
            print(f"[atlas] baking {len(used_mats)} materials into one atlas (tile={args.atlas_tile})")
        atlas_rgba, atlas_w, atlas_h, uv_xform = _build_material_atlas(
            j, bin_blob, glb_path, used_mats, int(args.atlas_tile)
        )

    # Merge all primitives into one indexed mesh stream.
    V_list = []
    N_list = []
    UV_list = []
    joints_list = []
    weights_list = []
    F_list = []
    base_index = 0

    for pr in prims:
        attrs = pr["attributes"]

        Vp = read_accessor(j, bin_blob, attrs["POSITION"]).astype(np.float32) * float(args.scale)
        Np = read_accessor(j, bin_blob, attrs["NORMAL"]).astype(np.float32)

        if "JOINTS_0" in attrs and "WEIGHTS_0" in attrs:
            jp = read_accessor(j, bin_blob, attrs["JOINTS_0"]).astype(np.int32)
            wp = read_accessor(j, bin_blob, attrs["WEIGHTS_0"]).astype(np.float32)
        else:
            jp = np.zeros((len(Vp), 4), dtype=np.int32)
            wp = np.zeros((len(Vp), 4), dtype=np.float32)
            wp[:, 0] = 1.0

        # indices
        if "indices" in pr:
            Ip = read_accessor(j, bin_blob, pr["indices"]).reshape((-1,)).astype(np.int32)
        else:
            Ip = np.arange(len(Vp), dtype=np.int32)
        Fp = Ip.reshape((-1, 3))

        # UVs
        UVp = None
        if args.uv == "gltf" and "TEXCOORD_0" in attrs:
            UVp = read_accessor(j, bin_blob, attrs["TEXCOORD_0"]).astype(np.float32)[:, :2]
            if args.verbose:
                print("[uv] using glTF TEXCOORD_0")
        if UVp is None:
            UVp = planar_uv_from_pos(Vp)
            if args.verbose:
                print("[uv] using planar XZ projection")

        # Apply atlas remap if enabled
        if atlas_rgba is not None:
            mi = pr.get("material", 0)
            su, sv, ou, ov = uv_xform.get(mi, (1.0, 1.0, 0.0, 0.0))
            UVp = UVp.copy()
            UVp[:, 0] = UVp[:, 0] * su + ou
            UVp[:, 1] = UVp[:, 1] * sv + ov

        V_list.append(Vp); N_list.append(Np); UV_list.append(UVp)
        joints_list.append(jp); weights_list.append(wp)
        F_list.append(Fp + base_index)
        base_index += len(Vp)

    V = np.vstack(V_list).astype(np.float32)
    N = np.vstack(N_list).astype(np.float32)
    UV = np.vstack(UV_list).astype(np.float32)
    joints = np.vstack(joints_list).astype(np.int32)
    weights = np.vstack(weights_list).astype(np.float32)
    F = np.vstack(F_list).astype(np.int32)

    # skeleton
    # skeleton
    if j.get("skins"):
        joint_nodes = j["skins"][0]["joints"]
    else:
        joint_nodes = []
    if not joint_nodes:
        parents = [-1]; scales = [(1,1,1)]; eulers = [(0,0,0)]; poss = [(0,0,0)]
    else:
        node_to_joint = {node:i for i,node in enumerate(joint_nodes)}
        parent_of = {}
        for ni, node in enumerate(j["nodes"]):
            for ch in node.get("children", []):
                parent_of[ch] = ni
        parents, scales, eulers, poss = [], [], [], []
        for node_idx in joint_nodes:
            pnode = parent_of.get(node_idx, None)
            parents.append(node_to_joint[pnode] if (pnode in node_to_joint) else -1)
            node = j["nodes"][node_idx]
            poss.append(tuple(map(float, node.get("translation", [0,0,0]))))
            scales.append(tuple(map(float, node.get("scale", [1,1,1]))))
            eulers.append(tuple(map(float, quat_to_euler_xyz(node.get("rotation", [0,0,0,1])))))

    _, inv_world = build_world_mats(parents, scales, eulers, poss)

    V, N = apply_axis_fix(V, N, args.axis)
    V, N = apply_extra_rot(V, N, rx, ry, rz)

    v_joint = dominant_joint(joints, weights)
    v_joint = np.clip(v_joint, 0, len(parents)-1).astype(np.int32) if len(parents) > 0 else np.zeros((V.shape[0],), np.int32)

    face_groups = group_faces_by_joint(F, v_joint)
    joints_used = sorted(face_groups.keys()) if face_groups else [0]

    vtx_vals = [int(jt) for jt in joints_used]
    jt_to_env = {jt:i for i,jt in enumerate(joints_used)}
    env_vtx_indices = list(range(len(joints_used)))  # 1:1 mapping

    newV, newN, newUV = [], [], []
    remap = {}
    packets = []

    for jt in joints_used:
        tris = np.array(face_groups[jt], dtype=np.int32)
        tris_new = np.zeros_like(tris)
        invM = inv_world[jt] if inv_world else np.eye(4, np.float32)
        inv3 = invM[:3, :3]

        for ti in range(tris.shape[0]):
            for k in range(3):
                old = int(tris[ti, k])
                key = (jt, old)
                if key in remap:
                    tris_new[ti, k] = remap[key]
                else:
                    p4 = np.array([V[old,0], V[old,1], V[old,2], 1.0], np.float32)
                    pl = (invM @ p4)[:3]
                    nl = (inv3 @ N[old]).astype(np.float32)
                    ln = np.linalg.norm(nl)
                    if ln > 1e-8:
                        nl /= ln
                    ni = len(newV)
                    newV.append(pl); newN.append(nl); newUV.append(UV[old])
                    remap[key] = ni
                    tris_new[ti, k] = ni

        strips = stripify(tris_new)
        dlist, strip_count = build_packet_dlist(strips, has_uv=True)
        packets.append({
            "envelope_index": jt_to_env[jt],
            "dlistData": dlist,
            "cmdCount": int(strip_count),
        })

    newV = np.asarray(newV, np.float32)
    newN = np.asarray(newN, np.float32)
    newUV = np.asarray(newUV, np.float32)

    # vdesc: position + normal + uv0
    vdesc = 1 | (1 << 3)

    # texture
    tex_rgba = None
    try:
        tex_rgba = (atlas_rgba, atlas_w, atlas_h) if (atlas_rgba is not None) else _extract_basecolor_image_rgba(glb_path)
    except Exception as e:
        if args.verbose:
            print("[tex] extraction failed:", e)

    if tex_rgba is None:
        rgba = bytes([255,255,255,255])
        sw, sh = 1, 1
        if args.verbose:
            print("[tex] no image found; using 1x1 white")
    else:
        rgba, sw, sh = tex_rgba
        if args.verbose:
            print(f"[tex] source image: {sw}x{sh}")

    orig_sw, orig_sh = sw, sh
    rgba, sw, sh = _downscale_rgba_max(rgba, sw, sh, args.max_tex_size)
    if args.verbose and (sw != orig_sw or sh != orig_sh):
        print(f"[tex] downscaled to {sw}x{sh} (max={args.max_tex_size})")

    tex_gx, tw, th = _rgba_to_gx_rgb565_tiled(rgba, sw, sh)
    if args.verbose:
        print(f"[tex] encoded RGB565 tiled: {tw}x{th}, bytes={len(tex_gx)} fmt=0")

    w = Writer()
    write_chunk(w, 0x00, build_header_chunk)
    write_chunk(w, 0x10, lambda ww: build_chunk_vec3(ww, newV))
    write_chunk(w, 0x11, lambda ww: build_chunk_vec3(ww, newN))
    write_chunk(w, 0x18, lambda ww: build_chunk_uv(ww, newUV))
    write_chunk(w, 0x20, lambda ww: build_chunk_20_textures_multi8(ww, tex_gx, tw, th, fmt_u32=0, verbose=args.verbose, tex_count=args.tex_count))
    write_chunk(w, 0x22, build_chunk_22_snake)
    write_chunk(w, 0x30, build_chunk_30_snake)
    write_chunk(w, 0x40, lambda ww: build_chunk_40(ww, vtx_vals))
    write_chunk(w, 0x41, lambda ww: build_chunk_41_rigid(ww, env_vtx_indices))
    write_chunk(w, 0x50, lambda ww: build_chunk_50(ww, bone_index=0, vdesc=vdesc, packets=packets))  # TEX flags
    write_chunk(w, 0x60, lambda ww: build_chunk_60(ww, parents, scales, eulers, poss))
    write_chunk(w, 0xFFFF, lambda ww: ww.write(b""))  # EMPTY terminator

    Path(args.out).write_bytes(w.buf)
    print("Wrote", args.out)

if __name__ == "__main__":
    main()
