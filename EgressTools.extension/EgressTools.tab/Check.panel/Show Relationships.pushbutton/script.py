# -*- coding: utf-8 -*-
"""Toggle relationship lines.
- Markers selected: show only their branch (upstream + downstream).
- Nothing selected: show the whole view; click again to hide.
Blue = OK, red = problem. Lines are real detail lines - hide before printing."""
__title__ = "Show\nRelationships"
from pyrevit import revit, forms, script
from Autodesk.Revit.DB import Transaction
import egress_core as ec

doc, uidoc = revit.doc, revit.uidoc
view = doc.ActiveView
sel_ids = set(ec.idval(e.Id) for e in ec.selected_markers(doc, uidoc))

markers = ec.collect_markers(doc, view)
res = ec.solve(markers)

t = Transaction(doc, "Egress Show Relationships")
t.Start()
had = ec.clear_graphics(doc, view)
drawn = 0
if sel_ids or not had:
    seeds = [m for m in markers if m.id in sel_ids]
    scope = ec.branch(res, seeds) if seeds else markers
    drawn = ec.draw_relationships(doc, view, res, scope)
t.Commit()

if not drawn and not had:
    forms.alert("No egress markers with paths found in this view.", title="EgressTools")
