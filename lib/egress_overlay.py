# -*- coding: utf-8 -*-
"""EgressTools v1.7 - Show Relationships overlay (markup style).

Drawing rules
-------------
- Room -> pool:  arc from the door marker to the pool's label box
- Pool -> exit:  arc from the pool's label box to the stair-door marker
- Pool -> pool:  arc box -> marker -> box (two arcs, same style)
- Each transfer TIER gets its own colour; every second tier is dashed.
    tier 1 = room -> corridor, tier 2 = corridor -> next node, ...
- Arcs are cubic curves. Each arc tries ~20 shapes (single bow / S-curve,
  either side, several sizes) and keeps the one with the fewest crossings,
  close passes, and overlaps with labels and markers.
- Small arrowheads repeat along each arc; a larger one at the end.
- Labels are bold, boxed text. New labels are placed so they don't overlap
  each other or markers. Drag them anywhere: positions are saved with the
  view when the overlay is hidden or redrawn.
- Optional: room labels, halftone plan (view's Display Model -> Halftone).
  If a view template locks Display Model, the template is removed while the
  overlay is on and reapplied when it's hidden.
"""
import os
import json
import math

# ======================================================================
# Pure-python geometry (no Revit) - unit-testable outside Revit
# ======================================================================
AMPS = (0.12, 0.25, 0.4, 0.6, 0.85)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _mul(a, k):
    return (a[0] * k, a[1] * k)


def _len(a):
    return math.hypot(a[0], a[1])


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def bez_pt(c, t):
    u = 1 - t
    return (u ** 3 * c[0][0] + 3 * u * u * t * c[1][0] + 3 * u * t * t * c[2][0] + t ** 3 * c[3][0],
            u ** 3 * c[0][1] + 3 * u * u * t * c[1][1] + 3 * u * t * t * c[2][1] + t ** 3 * c[3][1])


def bez_tan(c, t):
    u = 1 - t
    return (3 * u * u * (c[1][0] - c[0][0]) + 6 * u * t * (c[2][0] - c[1][0]) + 3 * t * t * (c[3][0] - c[2][0]),
            3 * u * u * (c[1][1] - c[0][1]) + 6 * u * t * (c[2][1] - c[1][1]) + 3 * t * t * (c[3][1] - c[2][1]))


def bez_samples(c, n):
    return [bez_pt(c, i / float(n)) for i in range(n + 1)]


def end_center(e):
    if e[0] == "rect":
        r = e[1]
        return ((r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0)
    return e[1]


def clip_end(e, toward):
    """Point on the end's boundary in the direction of `toward`."""
    c = end_center(e)
    d = _sub(toward, c)
    L = _len(d)
    if L < 1e-9:
        return c
    if e[0] == "circle":
        return _add(c, _mul(d, e[2] / L))
    r = e[1]
    hw, hh = (r[2] - r[0]) / 2.0, (r[3] - r[1]) / 2.0
    sx = hw / abs(d[0]) if abs(d[0]) > 1e-12 else 1e18
    sy = hh / abs(d[1]) if abs(d[1]) > 1e-12 else 1e18
    s = min(sx, sy)
    return _add(c, _mul(d, s))


def candidates(a_end, b_end):
    """Yield (ctrl_points, shape_penalty)."""
    A, B = end_center(a_end), end_center(b_end)
    d = _sub(B, A)
    L = _len(d)
    if L < 1e-9:
        return
    n = (-d[1] / L, d[0] / L)
    forms = [((0.0, 0.0), 3.0)]                              # straight: least preferred
    for i, a in enumerate(AMPS):
        for s in (1, -1):
            forms.append(((a * s, a * s), 1.5 * i))          # single bow (gentle bow preferred)
            forms.append(((a * s, -a * s), 4.0 + 1.5 * i))   # S-curve, only if needed
    for (k1, k2), pen in forms:
        p1 = _add(_add(A, _mul(d, 1 / 3.0)), _mul(n, k1 * L))
        p2 = _add(_add(A, _mul(d, 2 / 3.0)), _mul(n, k2 * L))
        a0 = clip_end(a_end, p1)
        b0 = clip_end(b_end, p2)
        yield ((a0, p1, p2, b0), pen)


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def seg_intersect(a, b, c, d):
    d1, d2 = _orient(c, d, a), _orient(c, d, b)
    d3, d4 = _orient(a, b, c), _orient(a, b, d)
    return (d1 * d2 < 0) and (d3 * d4 < 0)


def _pt_seg(p, a, b):
    ab = _sub(b, a)
    L2 = ab[0] * ab[0] + ab[1] * ab[1]
    if L2 < 1e-18:
        return dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
    return dist(p, (a[0] + ab[0] * t, a[1] + ab[1] * t))


def seg_dist(a, b, c, d):
    if seg_intersect(a, b, c, d):
        return 0.0
    return min(_pt_seg(a, c, d), _pt_seg(b, c, d), _pt_seg(c, a, b), _pt_seg(d, a, b))


class Grid(object):
    def __init__(self, cell):
        self.c = cell
        self.cells = {}
        self.by_pid = {}

    def _keys(self, a, b, grow=0):
        c = self.c
        x0, x1 = int(math.floor(min(a[0], b[0]) / c)) - grow, int(math.floor(max(a[0], b[0]) / c)) + grow
        y0, y1 = int(math.floor(min(a[1], b[1]) / c)) - grow, int(math.floor(max(a[1], b[1]) / c)) + grow
        for i in range(x0, x1 + 1):
            for j in range(y0, y1 + 1):
                yield (i, j)

    def add(self, pid, pts):
        keys = []
        for i in range(len(pts) - 1):
            seg = (pts[i], pts[i + 1], pid)
            for k in self._keys(pts[i], pts[i + 1]):
                self.cells.setdefault(k, []).append(seg)
                keys.append(k)
        self.by_pid[pid] = keys

    def remove(self, pid):
        for k in self.by_pid.pop(pid, []):
            lst = self.cells.get(k)
            if lst:
                self.cells[k] = [s for s in lst if s[2] != pid]

    def near(self, a, b):
        seen = set()
        for k in self._keys(a, b, 1):
            for s in self.cells.get(k, ()):
                sid = id(s)
                if sid not in seen:
                    seen.add(sid)
                    yield s


def _in_rect(p, r, m):
    return r[0] - m <= p[0] <= r[2] + m and r[1] - m <= p[1] <= r[3] + m


def score(pts, pid, grid, rects, circles, gap, clear, chord):
    cross = close = hits = 0
    p0, pn = pts[0], pts[-1]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        m = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if dist(m, p0) < clear or dist(m, pn) < clear:
            continue
        for (c, d, opid) in grid.near(a, b):
            if opid == pid:
                continue
            if seg_intersect(a, b, c, d):
                cross += 1
            elif seg_dist(a, b, c, d) < gap:
                close += 1
        for r in rects:
            if _in_rect(m, r, gap * 0.5):
                hits += 1
        for (cc, rr) in circles:
            if dist(m, cc) < rr + gap * 0.5:
                hits += 1
    length = sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    return cross * 1000 + hits * 150 + close * 6 + 10.0 * length / max(chord, 1e-9)


def route(paths, gap, clear, n=20, passes=2):
    """paths: list of dicts {pid, a, b, rects, circles} (obstacles exclude own ends).
    Returns {pid: ctrl}."""
    if not paths:
        return {}
    cell = max(gap * 2.0, 1e-6)
    grid = Grid(cell)
    chosen = {}
    order = sorted(paths, key=lambda p: -dist(end_center(p["a"]), end_center(p["b"])))

    def pick(p):
        best = None
        chord = dist(end_center(p["a"]), end_center(p["b"]))
        for ctrl, pen in candidates(p["a"], p["b"]):
            pts = bez_samples(ctrl, n)
            s = score(pts, p["pid"], grid, p["rects"], p["circles"], gap, clear, chord) + pen
            if best is None or s < best[0]:
                best = (s, ctrl, pts)
        return best

    for _ in range(passes):
        for p in order:
            grid.remove(p["pid"])
            best = pick(p)
            if best is None:
                continue
            chosen[p["pid"]] = best[1]
            grid.add(p["pid"], best[2])
    return chosen


def arrow_marks(ctrl, spacing, h_mid, h_end, spread=0.5, n=120):
    """Return list of (p, q) segments forming chevrons along the curve."""
    pts = bez_samples(ctrl, n)
    cum = [0.0]
    for i in range(n):
        cum.append(cum[-1] + dist(pts[i], pts[i + 1]))
    L = cum[-1]
    if L < 1e-9:
        return []
    stations = []
    s = spacing
    while s < L - spacing * 0.5:
        stations.append((s, h_mid))
        s += spacing
    stations.append((L, h_end))
    segs = []
    j = 0
    for st, h in stations:
        while j < n - 1 and cum[j + 1] < st:
            j += 1
        seg_len = cum[j + 1] - cum[j]
        f = (st - cum[j]) / seg_len if seg_len > 1e-12 else 0.0
        tip = (pts[j][0] + (pts[j + 1][0] - pts[j][0]) * f, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * f)
        tg = bez_tan(ctrl, min(1.0, max(0.0, (j + f) / float(n))))
        tl = _len(tg)
        if tl < 1e-12:
            continue
        ang = math.atan2(tg[1], tg[0])
        for sgn in (1, -1):
            a = ang + math.pi + sgn * spread
            segs.append((tip, (tip[0] + h * math.cos(a), tip[1] + h * math.sin(a))))
    return segs


def tiers(res):
    """Depth per node: rooms = 1, each downstream node = 1 + deepest feeder."""
    depth = {}
    for r in res.rows:
        ins = res.inn.get(r.name, [])
        depth[r.name] = 1 if not ins else 1 + max(depth.get(m.frm, 1) for m in ins)
    return depth


# ---------------------------------------------------------------- label placement
def _overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 0 and min(a[3], b[3]) - max(a[1], b[1]) > 0


def _overlap_area(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def place_labels(items, fixed, gap, step, rings=10, dirs=12):
    """Place label boxes so they don't overlap each other or `fixed` boxes.
    items: list of (key, width, height, (ax, ay)) in priority order.
    fixed: list of (x0, y0, x1, y1) that must be avoided.
    Returns {key: (cx, cy)}. Tries the anchor first, then rings of positions
    around it; falls back to the least-overlapping spot."""
    taken = list(fixed)
    out = {}
    for key, w, h, (ax, ay) in items:
        best = None
        for ring in range(rings + 1):
            r = ring * step
            n = 1 if ring == 0 else dirs
            found = None
            for k in range(n):
                ang = 2 * math.pi * k / n + (math.pi / dirs if ring % 2 else 0.0)
                cx, cy = ax + r * math.cos(ang), ay + r * math.sin(ang)
                box = (cx - w / 2 - gap, cy - h / 2 - gap, cx + w / 2 + gap, cy + h / 2 + gap)
                area = sum(_overlap_area(box, t) for t in taken)
                if area <= 0:
                    found = (cx, cy)
                    break
                if best is None or area < best[0]:
                    best = (area, (cx, cy))
            if found:
                best = (0.0, found)
                break
        cx, cy = best[1]
        out[key] = (cx, cy)
        taken.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return out


# ======================================================================
# Settings
# ======================================================================
SETTINGS_PATH = os.path.join(os.getenv("APPDATA") or "", "pyRevit", "EgressTools_overlay.json")
SETTINGS_VERSION = 2
DEFAULTS = {"room_labels": False, "halftone": True, "line_weight": 8, "arrow_spacing": 0.75,
            "v": SETTINGS_VERSION}


def load_settings():
    s = dict(DEFAULTS)
    saved = {}
    try:
        with open(SETTINGS_PATH) as f:
            saved = json.load(f)
    except Exception:
        pass
    s.update(saved)
    # v1.6 files stored the old default weight 6; move them to the new default
    if saved and saved.get("v", 1) < 2 and int(saved.get("line_weight", 6)) == 6:
        s["line_weight"] = DEFAULTS["line_weight"]
    s["v"] = SETTINGS_VERSION
    return s


def save_settings(s):
    folder = os.path.dirname(SETTINGS_PATH)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    s = dict(s)
    s["v"] = SETTINGS_VERSION
    with open(SETTINGS_PATH, "w") as f:
        json.dump(s, f, indent=1)


# ======================================================================
# Revit side
# ======================================================================
PREFIX = "EG Overlay"
LEGACY = ("EG Relationships",)
DASH_NAME = "EG Overlay Dash"
LABEL_TYPE = "EG Overlay Label"
LABEL_ISSUE_TYPE = "EG Overlay Label - Issue"
TIER_COLORS = [(230, 30, 30), (0, 95, 230), (0, 150, 60), (200, 0, 170), (240, 130, 0), (0, 160, 170)]
TIER_NAMES = ["Red", "Blue", "Green", "Magenta", "Orange", "Teal"]
SCHEMA_GUID_STR = "6f1c2a8e-3b4d-4e9a-9c51-0e7d2b8a4f13"

# paper sizes (inches)
MARKER_R_IN = 0.14
LABEL_TEXT_IN = 3 / 32.0
BORDER_OFFSET_IN = 5 / 64.0
GAP_IN = 0.09
CLEAR_IN = 0.30
H_MID_IN = 0.06
H_END_IN = 0.11
LABEL_GAP_IN = 0.06
LABEL_STEP_IN = 0.18

try:
    from System import String, Guid, Int64
    from System.Collections.Generic import List
    from Autodesk.Revit.DB import (
        FilteredElementCollector, BuiltInCategory, BuiltInParameter, XYZ, Line, NurbSpline,
        CurveElement, TextNote, TextNoteType, ElementTypeGroup, GraphicsStyleType, Color,
        LinePatternElement, LinePattern, LinePatternSegment, LinePatternSegmentType,
        ElementTransformUtils, ViewType, ElementId,
    )
    from Autodesk.Revit.DB.ExtensibleStorage import SchemaBuilder, Schema, Entity, AccessLevel
    import egress_core as ec
    _REVIT = True
except Exception:
    _REVIT = False


def paper(view, inches):
    return inches / 12.0 * max(view.Scale, 1)


def supported_view(view):
    if view.ViewType == ViewType.DraftingView:
        return True
    try:
        return view.ViewDirection.IsAlmostEqualTo(XYZ.BasisZ)
    except Exception:
        return False


def _make_id(v):
    try:
        return ElementId(Int64(v))
    except Exception:
        return ElementId(int(v))


# ---------------------------------------------------------------- storage
def _plain(v):
    """Convert .NET numbers (Int64, Int32, Double) to plain Python int/float.
    IronPython's json can't serialise a boxed System.Int64."""
    if isinstance(v, bool):
        return v
    s = str(v).rstrip("Ll")
    try:
        return int(s)
    except ValueError:
        return float(s)


def _clean(o):
    if isinstance(o, dict):
        return dict((str(k), _clean(v)) for k, v in o.items())
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if o is None or isinstance(o, (bool, str)):
        return o
    try:
        if isinstance(o, unicode):  # noqa: F821  (IronPython 2)
            return o
    except NameError:
        pass
    try:
        return _plain(o)
    except Exception:
        return str(o)


def _schema():
    g = Guid(SCHEMA_GUID_STR)
    s = Schema.Lookup(g)
    if s is not None:
        return s
    b = SchemaBuilder(g)
    b.SetReadAccessLevel(AccessLevel.Public)
    b.SetWriteAccessLevel(AccessLevel.Public)
    b.SetSchemaName("EgressToolsOverlay")
    b.AddSimpleField("Data", String)
    return b.Finish()


def read_state(view):
    s = Schema.Lookup(Guid(SCHEMA_GUID_STR))
    if s is None:
        return {}
    e = view.GetEntity(s)
    if e is None or not e.IsValid():
        return {}
    try:
        return json.loads(e.Get[String]("Data") or "{}")
    except Exception:
        return {}


def write_state(view, data):
    """Must be inside a transaction."""
    s = _schema()
    e = Entity(s)
    e.Set[String]("Data", json.dumps(_clean(data)))
    view.SetEntity(e)


# ---------------------------------------------------------------- halftone / template
def _display_param(view):
    p = None
    try:
        p = view.get_Parameter(BuiltInParameter.VIEW_MODEL_DISPLAY_MODE)
    except Exception:
        p = None
    if p is None:
        p = view.LookupParameter("Display Model")
    return p


def _set_halftone(p, state):
    if "display_model" not in state:
        state["display_model"] = _plain(p.AsInteger())
    if "half" in (p.AsValueString() or "").lower():
        return True
    for v in (1, 2, 0, 3):
        try:
            p.Set(v)
        except Exception:
            continue
        if "half" in (p.AsValueString() or "").lower():
            return True
    p.Set(int(state.pop("display_model")))
    return False


def apply_halftone(doc, view, state):
    """Halftone the view. If a view template locks Display Model, remove the
    template temporarily (remembered in `state`). Returns a list of messages."""
    msgs = []
    p = _display_param(view)
    if p is None:
        return ["Halftone skipped: this view has no Display Model setting."]
    if p.IsReadOnly and "template_id" not in state:
        tid = view.ViewTemplateId
        if tid is not None and tid != ElementId.InvalidElementId:
            tmpl = doc.GetElement(tid)
            state["template_id"] = _plain(ec.idval(tid))
            state["template_name"] = ec.elem_name(tmpl) if tmpl is not None else ""
            view.ViewTemplateId = ElementId.InvalidElementId
            doc.Regenerate()
            p = _display_param(view)
            msgs.append("View template '%s' is turned off while the overlay is showing, so the "
                        "plan can be halftoned. It's reapplied when you hide the overlay."
                        % state["template_name"])
    if p is None or p.IsReadOnly:
        _restore_template(doc, view, state)
        return msgs + ["Halftone skipped: Display Model can't be changed in this view."]
    if not _set_halftone(p, state):
        msgs.append("Halftone skipped: no Halftone option found for Display Model.")
    return msgs


def _restore_template(doc, view, state):
    if "template_id" not in state:
        return None
    tid = _make_id(_plain(state.pop("template_id")))
    name = state.pop("template_name", "")
    if doc.GetElement(tid) is None:
        return "View template '%s' no longer exists, so it wasn't reapplied." % name
    try:
        view.ViewTemplateId = tid
    except Exception:
        return "Couldn't reapply view template '%s'. Reapply it in the view's properties." % name
    return None


def restore_view(doc, view, state):
    """Undo halftone and reapply any template. Returns a list of messages."""
    msgs = []
    if "display_model" in state:
        p = _display_param(view)
        if p is not None and not p.IsReadOnly:
            try:
                p.Set(int(state["display_model"]))
            except Exception:
                pass
        state.pop("display_model", None)
    m = _restore_template(doc, view, state)
    if m:
        msgs.append(m)
    return msgs


# ---------------------------------------------------------------- find / clear
def _ours(name):
    return name.startswith(PREFIX) or name.startswith(LEGACY)


def overlay_elements(doc, view):
    """(ids_to_delete, label_notes)"""
    ids, labels = [], []
    for c in FilteredElementCollector(doc, view.Id).OfClass(CurveElement):
        try:
            ls = c.LineStyle
        except Exception:
            continue
        if ls is not None and _ours(ec.elem_name(ls)):
            ids.append(c.Id)
    tt = {}
    for t in FilteredElementCollector(doc).OfClass(TextNoteType):
        nm = ec.elem_name(t)
        if _ours(nm):
            tt[ec.idval(t.Id)] = nm.startswith(PREFIX)
    for n in FilteredElementCollector(doc, view.Id).OfClass(TextNote):
        k = ec.idval(n.GetTypeId())
        if k in tt:
            ids.append(n.Id)
            if tt[k]:                      # only v1.6+ labels carry a saved position
                labels.append(n)
    return ids, labels


def _label_key(note):
    t = (note.Text or "").replace("\r", "\n").split("\n")[0]
    return t.strip()


def save_positions(labels, state):
    pos = state.setdefault("labels", {})
    for n in labels:
        k = _label_key(n)
        if k:
            c = n.Coord
            pos[k] = [_plain(c.X), _plain(c.Y)]


def delete(doc, ids):
    for i in ids:
        try:
            doc.Delete(i)
        except Exception:
            pass


# ---------------------------------------------------------------- styles
def _dash(doc):
    for lp in FilteredElementCollector(doc).OfClass(LinePatternElement):
        if ec.elem_name(lp) == DASH_NAME:
            return lp.Id
    pat = LinePattern(DASH_NAME)
    segs = List[LinePatternSegment]()
    segs.Add(LinePatternSegment(LinePatternSegmentType.Dash, 0.125 / 12.0))
    segs.Add(LinePatternSegment(LinePatternSegmentType.Space, 0.0625 / 12.0))
    pat.SetSegments(segs)
    return LinePatternElement.Create(doc, pat).Id


def _style(doc, name, rgb, weight, pattern_id):
    cats = doc.Settings.Categories
    lines = cats.get_Item(BuiltInCategory.OST_Lines)
    subs = lines.SubCategories
    sub = subs.get_Item(name) if subs.Contains(name) else cats.NewSubcategory(lines, name)
    sub.LineColor = Color(*rgb)
    sub.SetLineWeight(int(weight), GraphicsStyleType.Projection)
    sub.SetLinePatternId(pattern_id, GraphicsStyleType.Projection)
    return sub.GetGraphicsStyle(GraphicsStyleType.Projection)


class Styles(object):
    def __init__(self, doc, weight):
        self.doc, self.weight = doc, weight
        self.cache = {}
        self.solid = LinePatternElement.GetSolidPatternId()
        self.dash = None

    def tier(self, t, arrow=False):
        k = (t, arrow)
        if k not in self.cache:
            i = (t - 1) % len(TIER_COLORS)
            dashed = (t % 2 == 0) and not arrow
            if dashed and self.dash is None:
                self.dash = _dash(self.doc)
            name = "%s T%d %s%s" % (PREFIX, t, TIER_NAMES[i], " Arrow" if arrow else "")
            w = max(1, int(self.weight) - (2 if arrow else 0))
            self.cache[k] = _style(self.doc, name, TIER_COLORS[i], w,
                                   self.dash if dashed else self.solid)
        return self.cache[k]


def _text_type(doc, name, rgb):
    """Get or create the label text type, and (re)apply its settings every run
    so older projects pick up changes: bold, boxed, opaque, 5/64" border offset."""
    t = None
    for x in FilteredElementCollector(doc).OfClass(TextNoteType):
        if ec.elem_name(x) == name:
            t = x
            break
    if t is None:
        base = doc.GetElement(doc.GetDefaultElementTypeId(ElementTypeGroup.TextNoteType))
        t = base.Duplicate(name)

    def sp(bip, val):
        try:
            p = t.get_Parameter(bip)
            if p is not None and not p.IsReadOnly:
                cur = p.AsInteger() if isinstance(val, int) else p.AsDouble()
                if cur != val:
                    p.Set(val)
        except Exception:
            pass
    sp(BuiltInParameter.LINE_COLOR, rgb[0] + rgb[1] * 256 + rgb[2] * 65536)
    sp(BuiltInParameter.TEXT_BOX_VISIBILITY, 1)                        # border on
    sp(BuiltInParameter.TEXT_BACKGROUND, 0)                            # opaque
    sp(BuiltInParameter.TEXT_STYLE_BOLD, 1)                            # bold
    sp(BuiltInParameter.TEXT_SIZE, LABEL_TEXT_IN / 12.0)
    sp(BuiltInParameter.LEADER_OFFSET_SHEET, BORDER_OFFSET_IN / 12.0)  # Leader/Border Offset
    return t


# ---------------------------------------------------------------- draw
def _label_text(res, node, kind):
    r = res.row.get(node)
    if r is None:
        return node, False
    if kind == "Exit":
        txt = "%s\n%d / %s cap" % (node, r.inflow, "?" if r.cap is None else r.cap)
    elif kind == "Room":
        txt = "%s\n%d" % (node, r.required)
    else:
        outs = sorted(res.out.get(node, []), key=lambda m: m.id)
        txt = "%s\n%d in -> %s" % (node, r.required, " / ".join(str(m.new_occ) for m in outs))
    bad = r.status != "OK"
    if bad:
        txt += "\n! " + r.status
    return txt, bad


def _bbox2(note, view):
    bb = note.get_BoundingBox(view)
    return (bb.Min.X, bb.Min.Y, bb.Max.X, bb.Max.Y)


def _draw_curve(doc, view, ctrl, z, style, tol):
    if dist(ctrl[0], ctrl[3]) < tol:
        return 0
    p = [XYZ(x, y, z) for x, y in ctrl]
    straight = abs(_orient(ctrl[0], ctrl[3], ctrl[1])) < 1e-9 and abs(_orient(ctrl[0], ctrl[3], ctrl[2])) < 1e-9
    try:
        if straight:
            crv = Line.CreateBound(p[0], p[3])
        else:
            crv = NurbSpline.CreateCurve(3, List[float]([0, 0, 0, 0, 1, 1, 1, 1]),
                                         List[XYZ](p), List[float]([1, 1, 1, 1]))
        dc = doc.Create.NewDetailCurve(view, crv)
        dc.LineStyle = style
        return 1
    except Exception:
        pts = bez_samples(ctrl, 24)
        k = 0
        for i in range(len(pts) - 1):
            if dist(pts[i], pts[i + 1]) < tol:
                continue
            dc = doc.Create.NewDetailCurve(view, Line.CreateBound(XYZ(pts[i][0], pts[i][1], z),
                                                                  XYZ(pts[i + 1][0], pts[i + 1][1], z)))
            dc.LineStyle = style
            k += 1
        return k


def draw(doc, view, res, scope, settings, state):
    """Must be inside a transaction. Returns (elements_drawn, messages)."""
    msgs = []
    pts = {}
    for m in scope:
        p = m.point()
        if p is not None and m.frm and m.to and m.frm != m.to:
            pts[m] = p
    if not pts:
        return 0, msgs
    z = list(pts.values())[0].Z
    depth = tiers(res)
    kind = dict((r.name, r.kind) for r in res.rows)
    saved = state.get("labels", {})
    tol = doc.Application.ShortCurveTolerance * 2
    R = paper(view, MARKER_R_IN)

    # ---- which nodes get labels
    want = {}
    for m in pts:
        for n in (m.frm, m.to):
            k = kind.get(n)
            if k in ("Pool", "Loop"):
                want[n] = "Pool"
            elif k == "Exit":
                want[n] = "Exit"
            elif k == "Room" and settings.get("room_labels"):
                want[n] = "Room"

    def anchor(n, k):
        if k == "Exit":
            ps = [p for m, p in pts.items() if m.to == n]
        elif k == "Room":
            ps = [p for m, p in pts.items() if m.frm == n]
        else:
            ps = [p for m, p in pts.items() if n in (m.frm, m.to)]
        return (sum(p.X for p in ps) / len(ps), sum(p.Y for p in ps) / len(ps))

    t_ok = _text_type(doc, LABEL_TYPE, (30, 30, 30))
    t_bad = _text_type(doc, LABEL_ISSUE_TYPE, (150, 0, 0))
    notes, fresh = {}, []
    for n, k in want.items():
        txt, bad = _label_text(res, n, k)
        if n in saved:
            x, y = saved[n]
        else:
            x, y = anchor(n, k)
            fresh.append(n)
        notes[n] = TextNote.Create(doc, view.Id, XYZ(x, y, z), txt, (t_bad if bad else t_ok).Id)
    doc.Regenerate()

    # ---- place new labels clear of saved labels, other new labels and markers
    if fresh:
        fixed = [_bbox2(notes[n], view) for n in notes if n not in fresh]
        fixed += [(p.X - R, p.Y - R, p.X + R, p.Y + R) for p in pts.values()]
        prio = {"Pool": 0, "Exit": 1, "Room": 2}
        items = []
        for n in sorted(fresh, key=lambda n: prio.get(want[n], 3)):
            b = _bbox2(notes[n], view)
            items.append((n, b[2] - b[0], b[3] - b[1], anchor(n, want[n])))
        spots = place_labels(items, fixed, paper(view, LABEL_GAP_IN), paper(view, LABEL_STEP_IN))
        for n, (cx, cy) in spots.items():
            b = _bbox2(notes[n], view)
            ElementTransformUtils.MoveElement(doc, notes[n].Id,
                                              XYZ(cx - (b[0] + b[2]) / 2.0, cy - (b[1] + b[3]) / 2.0, 0))
        doc.Regenerate()
    pad = paper(view, 0.03)
    rect = {}
    for n, note in notes.items():
        b = _bbox2(note, view)
        rect[n] = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)

    # ---- build paths (room labels are display only; arcs still start at the doors)
    circ = dict((m, ("circle", (p.X, p.Y), R)) for m, p in pts.items())
    paths, meta = [], {}
    pid = 0
    for m, p in pts.items():
        fk, tk = kind.get(m.frm), kind.get(m.to)
        segs = []
        if fk == "Room" and m.to in rect:
            segs.append((circ[m], ("rect", rect[m.to]), (None, m.to)))
        elif m.frm in rect and tk == "Exit":
            segs.append((("rect", rect[m.frm]), circ[m], (m.frm, None)))
        elif m.frm in rect and m.to in rect:
            segs.append((("rect", rect[m.frm]), circ[m], (m.frm, None)))
            segs.append((circ[m], ("rect", rect[m.to]), (None, m.to)))
        for a, b, (ra, rb) in segs:
            pid += 1
            own = set(x for x in (ra, rb) if x)
            paths.append({"pid": pid, "a": a, "b": b,
                          "rects": [r for nn, r in rect.items() if nn not in own],
                          "circles": [(c[1], c[2]) for mm, c in circ.items() if mm is not m]})
            meta[pid] = depth.get(m.frm, 1)

    ctrl = route(paths, paper(view, GAP_IN), paper(view, CLEAR_IN))

    # ---- draw
    st = Styles(doc, settings.get("line_weight", DEFAULTS["line_weight"]))
    spacing = paper(view, float(settings.get("arrow_spacing", 0.75)))
    h_mid, h_end = paper(view, H_MID_IN), paper(view, H_END_IN)
    count = len(notes)
    for p in paths:
        c = ctrl.get(p["pid"])
        if c is None:
            continue
        t = meta[p["pid"]]
        count += _draw_curve(doc, view, c, z, st.tier(t), tol)
        astyle = st.tier(t, arrow=True)
        for a, b in arrow_marks(c, spacing, h_mid, h_end):
            if dist(a, b) < tol:
                continue
            dc = doc.Create.NewDetailCurve(view, Line.CreateBound(XYZ(a[0], a[1], z), XYZ(b[0], b[1], z)))
            dc.LineStyle = astyle
            count += 1
    return count, msgs
