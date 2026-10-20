# -*- coding: utf-8 -*-
"""EgressTools v1.5 - shared engine.

Data model (unchanged from v1, so v1 markers keep working)
------------------------------------------------------------
Every marker is an arrow from one NODE to another NODE:
    EG_From  -> node the occupants come from (room / pool)
    EG_To    -> node they go to (pool / exit)
A node with no outgoing markers is an EXIT.

At every non-exit node:
    required = own load (EG_Load) + sum(Occupants of markers coming in)
    sum(Occupants of markers going out) must equal required
Balance markers (EG_Balance = Yes) absorb the difference:
    one balance marker  -> gets the remainder
    several             -> remainder split evenly (equal split)
    none                -> nothing changed, only checked
At every exit:
    inflow must not exceed EG_Capacity

Scope: markers in the ACTIVE VIEW only.
"""
import os

from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, BuiltInParameter, FamilyInstance,
    StorageType, Transaction, OverrideGraphicSettings, Color, XYZ, Line,
    CurveElement, TextNote, TextNoteType, ElementTypeGroup, GraphicsStyleType,
    Element, ElementId,
)
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType

# ---------------------------------------------------------------- constants
P_OCC = "Occupants"        # existing family parameter (Number)
P_FROM = "EG_From"
P_TO = "EG_To"
P_BAL = "EG_Balance"
P_LOAD = "EG_Load"
P_CAP = "EG_Capacity"
P_STATUS = "EG_Status"

TXN_NAME = "Egress Rebalance"          # auto-rebalance ignores its own txn

# (name, kind, group, description)
REQUIRED_PARAMS = [
    (P_FROM, "text", "text", "Egress node the occupants come from (room / pool)"),
    (P_TO, "text", "text", "Egress node the occupants go to (pool / exit)"),
    (P_BAL, "yesno", "graphics", "Marker absorbs the difference at its split"),
    (P_LOAD, "int", "text", "Own occupant load of the EG_From node"),
    (P_CAP, "int", "text", "Capacity of the EG_To exit"),
    (P_STATUS, "text", "text", "Written by EgressTools - OK or problem description"),
]

PREFIX_ROOM, PREFIX_POOL, PREFIX_EXIT = "ROOM", "POOL", "EXIT"

# health-check colours (also used to recognise OUR overrides)
COLORS = {
    "red": (220, 0, 0),         # over capacity
    "orange": (255, 128, 0),    # unbalanced (OVER / UNDER)
    "yellow": (215, 175, 0),    # missing data / conflicts
    "purple": (150, 0, 200),    # broken path / cycle
}

GFX_OK = "EG Relationships"
GFX_ISSUE = "EG Relationships - Issue"
GFX_TEXT = "EG Relationships"
GFX_OK_RGB = (0, 110, 220)
GFX_ISSUE_RGB = (220, 0, 0)

AUTO_FLAG = os.path.join(os.getenv("APPDATA") or "", "pyRevit", "EgressTools_auto.txt")


# ---------------------------------------------------------------- helpers
def idval(eid):
    v = getattr(eid, "Value", None)          # Revit 2024+
    return v if v is not None else eid.IntegerValue


def norm(s):
    return " ".join((s or "").strip().upper().split())


def elem_name(e):
    try:
        return e.Name
    except Exception:
        return Element.Name.__get__(e)


def get_text(el, name):
    p = el.LookupParameter(name)
    if p is None:
        return ""
    if p.StorageType == StorageType.String:
        return (p.AsString() or "").strip()
    return (p.AsValueString() or "").strip()


def get_int(el, name):
    p = el.LookupParameter(name)
    if p is None or not p.HasValue:
        return 0
    st = p.StorageType
    if st == StorageType.Integer:
        return p.AsInteger()
    if st == StorageType.Double:
        return int(round(p.AsDouble()))
    if st == StorageType.String:
        try:
            return int(round(float(p.AsString())))
        except Exception:
            return 0
    return 0


def set_value(el, name, value):
    p = el.LookupParameter(name)
    if p is None or p.IsReadOnly:
        return False
    st = p.StorageType
    if st == StorageType.Double:
        return p.Set(float(value))
    if st == StorageType.Integer:
        return p.Set(int(value))
    if st == StorageType.String:
        return p.Set(str(value))
    return False


def is_marker(el):
    if not isinstance(el, FamilyInstance) or el.Category is None:
        return False
    if idval(el.Category.Id) != int(BuiltInCategory.OST_GenericAnnotation):
        return False
    return el.LookupParameter(P_OCC) is not None and el.LookupParameter(P_FROM) is not None


def marker_elements(doc, view):
    col = (FilteredElementCollector(doc, view.Id)
           .OfCategory(BuiltInCategory.OST_GenericAnnotation)
           .WhereElementIsNotElementType())
    return [e for e in col if is_marker(e)]


def collect_markers(doc, view):
    return [Marker(e) for e in marker_elements(doc, view)]


def auto_enabled():
    return os.path.exists(AUTO_FLAG)


def set_auto(on):
    folder = os.path.dirname(AUTO_FLAG)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    if on:
        open(AUTO_FLAG, "w").close()
    elif os.path.exists(AUTO_FLAG):
        os.remove(AUTO_FLAG)


# ---------------------------------------------------------------- picking
class MarkerFilter(ISelectionFilter):
    def AllowElement(self, el):
        return is_marker(el)

    def AllowReference(self, ref, pt):
        return False


def selected_markers(doc, uidoc):
    els = [doc.GetElement(i) for i in uidoc.Selection.GetElementIds()]
    return [e for e in els if is_marker(e)]


def pick_markers(doc, uidoc, prompt):
    """Window/click select markers, Finish to accept. Returns [] on Esc."""
    try:
        refs = uidoc.Selection.PickObjects(ObjectType.Element, MarkerFilter(), prompt)
        return [doc.GetElement(r) for r in refs]
    except Exception:
        return []


def pick_marker(doc, uidoc, prompt):
    try:
        return doc.GetElement(uidoc.Selection.PickObject(ObjectType.Element, MarkerFilter(), prompt))
    except Exception:
        return None


# ---------------------------------------------------------------- model
class Marker(object):
    def __init__(self, el):
        self.el = el
        self.id = idval(el.Id)
        self.frm = norm(get_text(el, P_FROM))
        self.to = norm(get_text(el, P_TO))
        self.bal = get_int(el, P_BAL) == 1
        self.bal_orig = self.bal
        self.load = get_int(el, P_LOAD)
        self.cap = get_int(el, P_CAP)
        self.occ = get_int(el, P_OCC)
        self.new_occ = self.occ
        self.flags = []
        self.comp = {}           # source node -> occupants carried

    @property
    def status(self):
        return "; ".join(self.flags) if self.flags else "OK"

    def point(self):
        loc = self.el.Location
        return getattr(loc, "Point", None)


class NodeRow(object):
    def __init__(self, name, kind, own, inflow, required, outflow, cap, status):
        self.name, self.kind, self.own, self.inflow = name, kind, own, inflow
        self.required, self.outflow, self.cap, self.status = required, outflow, cap, status


class Result(object):
    def __init__(self, markers):
        self.markers = markers
        self.rows = []
        self.row = {}            # node -> NodeRow
        self.out = {}            # node -> [markers leaving]
        self.inn = {}            # node -> [markers arriving]
        self.comp = {}           # node -> {source node: occupants}
        self.locked = []         # markers switched from balance to manual


def _distribute(outs, required):
    bal = [m for m in outs if m.bal]
    fixed = [m for m in outs if not m.bal]
    if bal:
        rem = required - sum(m.new_occ for m in fixed)
        if rem < 0:
            for m in bal:
                m.new_occ = 0
            return "OVER %d" % (-rem)
        q, r = divmod(rem, len(bal))
        for i, m in enumerate(bal):
            m.new_occ = q + (1 if i < r else 0)
        return None
    diff = sum(m.new_occ for m in outs) - required
    if diff > 0:
        return "OVER %d" % diff
    if diff < 0:
        return "UNDER %d" % (-diff)
    return None


def _apply_locks(res, lock_ids):
    """A user typed into a balance marker: make it manual, keep the split balanced."""
    for m in res.markers:
        if m.id not in lock_ids or not m.bal:
            continue
        sibs = [s for s in res.out.get(m.frm, []) if s is not m]
        if not sibs:
            continue                      # single door: nothing else can absorb
        m.bal = False
        res.locked.append(m)
        if not any(s.bal for s in sibs):
            # m was the last balance marker: hand the job to the first sibling
            s = sorted(sibs, key=lambda x: x.id)[0]
            s.bal = True


def solve(markers, lock_ids=None):
    res = Result(markers)
    valid = []
    for m in markers:
        if not m.frm or not m.to:
            m.flags.append("NO PATH")
        elif m.frm == m.to:
            m.flags.append("CYCLE")
        else:
            valid.append(m)

    nodes = set()
    for m in valid:
        res.out.setdefault(m.frm, []).append(m)
        res.inn.setdefault(m.to, []).append(m)
        nodes.add(m.frm)
        nodes.add(m.to)

    if lock_ids:
        _apply_locks(res, lock_ids)

    # topological order
    edges = dict((n, set()) for n in nodes)
    indeg = dict((n, 0) for n in nodes)
    for m in valid:
        if m.to not in edges[m.frm]:
            edges[m.frm].add(m.to)
            indeg[m.to] += 1
    queue = sorted(n for n in nodes if indeg[n] == 0)
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for t in sorted(edges[n]):
            indeg[t] -= 1
            if indeg[t] == 0:
                queue.append(t)

    for n in sorted(nodes - set(order)):
        for m in res.out.get(n, []):
            m.flags.append("CYCLE")
        row = NodeRow(n, "Loop", 0, 0, 0, 0, None, "CYCLE - paths loop back")
        res.rows.append(row)
        res.row[n] = row

    for n in order:
        outs = sorted(res.out.get(n, []), key=lambda x: x.id)
        ins = res.inn.get(n, [])
        inflow = sum(m.new_occ for m in ins)
        comp = {}
        for m in ins:
            for k, v in m.comp.items():
                comp[k] = comp.get(k, 0.0) + v

        if outs:
            loads = set(m.load for m in outs if m.load > 0)
            own = max(loads) if loads else 0
            if own:
                comp[n] = comp.get(n, 0.0) + own
            required = own + inflow
            problems = []
            if len(loads) > 1:
                problems.append("LOAD CONFLICT %s" % "/".join(str(x) for x in sorted(loads)))
            if required == 0:
                problems.append("NO LOAD")
            p = _distribute(outs, required)
            if p:
                problems.append(p)
            for m in outs:
                m.flags.extend(problems)
                f = (float(m.new_occ) / required) if required else 0.0
                m.comp = dict((k, v * f) for k, v in comp.items())
            row = NodeRow(n, "Pool" if ins else "Room", own, inflow, required,
                          sum(m.new_occ for m in outs), None, "; ".join(problems) or "OK")
        else:
            caps = set(m.cap for m in ins if m.cap > 0)
            cap = min(caps) if caps else None
            problems = []
            if cap is None:
                problems.append("NO CAP")
            elif inflow > cap:
                problems.append("OVER CAP %d" % (inflow - cap))
            if len(caps) > 1:
                problems.append("CAP CONFLICT %s" % "/".join(str(x) for x in sorted(caps)))
            for m in ins:
                m.flags.extend(problems)
            row = NodeRow(n, "Exit", 0, inflow, None, None, cap, "; ".join(problems) or "OK")
        res.comp[n] = comp
        res.rows.append(row)
        res.row[n] = row
    return res


# ---------------------------------------------------------------- highlights
def _rgb(c):
    return (c.Red, c.Green, c.Blue)


def severity(status):
    s = status.upper()
    if s == "OK":
        return None
    if "CYCLE" in s or "NO PATH" in s:
        return "purple"
    if "OVER CAP" in s:
        return "red"
    if "OVER" in s or "UNDER" in s:
        return "orange"
    return "yellow"


def is_our_override(view, eid):
    c = view.GetElementOverrides(eid).ProjectionLineColor
    return c.IsValid and _rgb(c) in COLORS.values()


def highlights_active(view, markers):
    return any(is_our_override(view, m.el.Id) for m in markers)


def apply_highlights(view, markers):
    for m in markers:
        sev = severity(m.status)
        if sev:
            ogs = OverrideGraphicSettings()
            ogs.SetProjectionLineColor(Color(*COLORS[sev]))
            view.SetElementOverrides(m.el.Id, ogs)
        elif is_our_override(view, m.el.Id):
            view.SetElementOverrides(m.el.Id, OverrideGraphicSettings())


def clear_highlights(view, markers):
    n = 0
    for m in markers:
        if is_our_override(view, m.el.Id):
            view.SetElementOverrides(m.el.Id, OverrideGraphicSettings())
            n += 1
    return n


# ---------------------------------------------------------------- run
def apply(doc, view, res, write_values, highlight):
    """highlight: 'on' | 'off' | 'auto' (refresh only if already showing)."""
    changed = 0
    t = Transaction(doc, TXN_NAME)
    t.Start()
    try:
        for m in res.markers:
            if write_values and m.new_occ != m.occ:
                if set_value(m.el, P_OCC, m.new_occ):
                    changed += 1
            if write_values and m.bal != m.bal_orig:
                set_value(m.el, P_BAL, 1 if m.bal else 0)
            if get_text(m.el, P_STATUS) != m.status:
                set_value(m.el, P_STATUS, m.status)
        if highlight == "on" or (highlight == "auto" and highlights_active(view, res.markers)):
            apply_highlights(view, res.markers)
        elif highlight == "off":
            clear_highlights(view, res.markers)
        t.Commit()
    except Exception:
        t.RollBack()
        raise
    return changed


def run(doc, view, write_values=True, highlight="auto", lock_ids=None):
    markers = collect_markers(doc, view)
    res = solve(markers, lock_ids)
    changed = apply(doc, view, res, write_values, highlight) if markers else 0
    return res, changed


# ---------------------------------------------------------------- naming
def next_name(markers, prefix):
    used = set()
    for m in markers:
        for n in (m.frm, m.to):
            if n.startswith(prefix + "-"):
                try:
                    used.add(int(n.split("-", 1)[1]))
                except ValueError:
                    pass
    i = 1
    while i in used:
        i += 1
    return "%s-%03d" % (prefix, i)


def exit_names(markers):
    froms = set(m.frm for m in markers if m.frm)
    return sorted(set(m.to for m in markers if m.to and m.to not in froms))


def pool_names(markers):
    """Nodes that both receive and send occupants."""
    froms = set(m.frm for m in markers if m.frm)
    tos = set(m.to for m in markers if m.to)
    return sorted(froms & tos)


# ---------------------------------------------------------------- relationship graphics
def _int_color(rgb):
    return rgb[0] + rgb[1] * 256 + rgb[2] * 65536


def _line_style(doc, name, rgb):
    cats = doc.Settings.Categories
    lines = cats.get_Item(BuiltInCategory.OST_Lines)
    subs = lines.SubCategories
    if subs.Contains(name):
        sub = subs.get_Item(name)
    else:
        sub = cats.NewSubcategory(lines, name)
        sub.LineColor = Color(*rgb)
        sub.SetLineWeight(3, GraphicsStyleType.Projection)
    return sub.GetGraphicsStyle(GraphicsStyleType.Projection)


def _text_type(doc):
    for t in FilteredElementCollector(doc).OfClass(TextNoteType):
        if elem_name(t) == GFX_TEXT:
            return t
    base = doc.GetElement(doc.GetDefaultElementTypeId(ElementTypeGroup.TextNoteType))
    t = base.Duplicate(GFX_TEXT)
    p = t.get_Parameter(BuiltInParameter.LINE_COLOR)
    if p:
        p.Set(_int_color(GFX_ISSUE_RGB))
    return t


def graphics_elements(doc, view):
    ids = []
    for c in FilteredElementCollector(doc, view.Id).OfClass(CurveElement):
        ls = c.LineStyle
        if ls is not None and elem_name(ls) in (GFX_OK, GFX_ISSUE):
            ids.append(c.Id)
    tt = [t.Id for t in FilteredElementCollector(doc).OfClass(TextNoteType)
          if elem_name(t) == GFX_TEXT]
    if tt:
        for n in FilteredElementCollector(doc, view.Id).OfClass(TextNote):
            if n.GetTypeId() == tt[0]:
                ids.append(n.Id)
    return ids


def clear_graphics(doc, view):
    """Must be called inside a transaction."""
    ids = graphics_elements(doc, view)
    for i in ids:
        try:
            doc.Delete(i)
        except Exception:
            pass
    return len(ids)


def branch(res, seeds):
    """Markers upstream + downstream of the seed markers (plus seed siblings)."""
    keep, seen_up, seen_dn = set(), set(), set()

    def up(node):
        if node in seen_up:
            return
        seen_up.add(node)
        for m in res.inn.get(node, []):
            keep.add(m)
            up(m.frm)

    def down(node):
        if node in seen_dn:
            return
        seen_dn.add(node)
        for m in res.out.get(node, []):
            keep.add(m)
            down(m.to)

    for s in seeds:
        keep.add(s)
        for sib in res.out.get(s.frm, []):
            keep.add(sib)
        up(s.frm)
        down(s.to)
    return keep


def _label(res, node):
    r = res.row.get(node)
    if r is None:
        return node
    if r.kind == "Exit":
        txt = "%s  %d / %s cap" % (node, r.inflow, "?" if r.cap is None else r.cap)
    elif r.kind == "Pool":
        outs = res.out.get(node, [])
        txt = "%s  %d in -> %s" % (node, r.required, " / ".join(str(m.new_occ) for m in outs))
    else:
        txt = "%s  %d" % (node, r.required)
    if r.status != "OK":
        txt += "\n" + r.status
    return txt


def draw_relationships(doc, view, res, markers):
    """Must be called inside a transaction. Returns number of elements drawn."""
    pts = {}
    for m in markers:
        p = m.point()
        if p is not None:
            pts[m] = p
    if not pts:
        return 0
    z = list(pts.values())[0].Z

    # hub = centroid of the drawn markers attached to each node
    acc = {}
    for m, p in pts.items():
        for n in (m.frm, m.to):
            if n:
                acc.setdefault(n, []).append(p)
    hubs = {}
    for n, ps in acc.items():
        hubs[n] = XYZ(sum(p.X for p in ps) / len(ps), sum(p.Y for p in ps) / len(ps), z)

    ok_style = _line_style(doc, GFX_OK, GFX_OK_RGB)
    bad_style = _line_style(doc, GFX_ISSUE, GFX_ISSUE_RGB)
    tol = doc.Application.ShortCurveTolerance * 2
    count = 0

    def seg(a, b, bad):
        a, b = XYZ(a.X, a.Y, z), XYZ(b.X, b.Y, z)
        if a.DistanceTo(b) < tol:
            return 0
        dc = doc.Create.NewDetailCurve(view, Line.CreateBound(a, b))
        dc.LineStyle = bad_style if bad else ok_style
        return 1

    for m, p in pts.items():
        bad = m.status != "OK"
        if m.frm in hubs:
            count += seg(hubs[m.frm], p, bad)
        if m.to in hubs:
            count += seg(p, hubs[m.to], bad)

    tt = _text_type(doc)
    off = (3.0 / 16.0) / 12.0 * max(view.Scale, 1)      # 3/16" on paper
    for n, h in hubs.items():
        TextNote.Create(doc, view.Id, XYZ(h.X + off, h.Y + off, z), _label(res, n), tt.Id)
        count += 1
    return count


# ---------------------------------------------------------------- report
def report(output, res, changed, title):
    output.print_md("## Egress - %s" % title)
    if not res.markers:
        output.print_md("No egress markers found in the active view. "
                        "Run **Setup Parameters**, then use the Build tools.")
        return
    output.print_md("Markers updated: **%d**" % changed)
    if res.locked:
        output.print_md("Switched to manual (you typed a value): %s" %
                        ", ".join(output.linkify(m.el.Id) for m in res.locked))

    def s(v):
        return "-" if v is None else str(v)

    data = [[r.name, r.kind, s(r.own), s(r.inflow), s(r.required),
             s(r.outflow), s(r.cap), r.status] for r in res.rows]
    output.print_table(table_data=data, title="Node totals",
                       columns=["Node", "Type", "Own load", "Inflow",
                                "Required out", "Actual out", "Capacity", "Status"])

    bad = [m for m in res.markers if m.flags]
    if bad:
        output.print_md("### Markers needing attention (%d)" % len(bad))
        for m in sorted(bad, key=lambda x: (x.frm, x.to)):
            output.print_md("- %s  %s -> %s  =  %d  |  %s" % (
                output.linkify(m.el.Id), m.frm or "?", m.to or "?", m.new_occ, m.status))
    else:
        output.print_md("**All nodes balanced and all exits within capacity.**")
