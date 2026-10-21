# -*- coding: utf-8 -*-
"""Explain the selected marker(s): where the occupants come from and where they go."""
__title__ = "Inspector"
from pyrevit import revit, forms, script
import egress_core as ec

doc, uidoc = revit.doc, revit.uidoc
view = doc.ActiveView
sel_ids = set(ec.idval(e.Id) for e in ec.selected_markers(doc, uidoc))
if not sel_ids:
    m = ec.pick_marker(doc, uidoc, "Pick a marker to inspect")
    if m is None:
        script.exit()
    sel_ids = {ec.idval(m.Id)}

res = ec.solve(ec.collect_markers(doc, view))
out = script.get_output()


def fmt_comp(comp):
    items = sorted(comp.items(), key=lambda kv: -kv[1])
    return [[k, "%.1f" % v] for k, v in items if v > 0.05]


def node_block(node, label):
    r = res.row.get(node)
    if r is None:
        out.print_md("**%s: %s** - not found" % (label, node or "(blank)"))
        return
    out.print_md("**%s: %s** (%s) - %s" % (label, node, r.kind, r.status))
    ins = res.inn.get(node, [])
    outs = res.out.get(node, [])
    if r.kind != "Exit":
        out.print_md("Own load %d + inflow %d = **%d** required, %d assigned out"
                     % (r.own, r.inflow, r.required, r.outflow))
    else:
        out.print_md("Inflow **%d** / capacity %s" % (r.inflow, r.cap if r.cap else "?"))
    if ins:
        out.print_md("In: " + ", ".join("%s %s=%d" % (output_link(m), m.frm, m.new_occ) for m in ins))
    if outs:
        out.print_md("Out: " + ", ".join("%s %s%s=%d" % (output_link(m), "[bal] " if m.bal else "",
                                                          m.to, m.new_occ) for m in outs))


def output_link(m):
    return out.linkify(m.el.Id)


for m in [x for x in res.markers if x.id in sel_ids]:
    out.print_md("---\n## Marker %s = %d  (%s)" % (output_link(m), m.new_occ, m.status))
    out.print_md("%s -> %s | %s" % (m.frm or "?", m.to or "?",
                                    "balance (auto)" if m.bal else "manual"))
    node_block(m.frm, "From")
    node_block(m.to, "To")
    if m.comp:
        out.print_table(table_data=fmt_comp(m.comp), title="Occupants in this marker by origin",
                        columns=["Room / node", "Occupants"])
    if m.to in res.row and res.row[m.to].kind == "Exit":
        out.print_table(table_data=fmt_comp(res.comp.get(m.to, {})),
                        title="Everything arriving at %s by origin" % m.to,
                        columns=["Room / node", "Occupants"])
