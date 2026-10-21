# -*- coding: utf-8 -*-
"""Show / hide the egress flow overlay (markup style).
- Markers selected: redraw showing only their branch.
- Nothing selected: show the whole view, or hide it if it's showing.
Label positions are saved with the view. Hiding restores halftone and any
view template that was turned off. Hide before printing."""
from pyrevit import revit, forms
from Autodesk.Revit.DB import Transaction
import egress_core as ec
import egress_overlay as ov

doc, uidoc = revit.doc, revit.uidoc
view = doc.ActiveView
if not ov.supported_view(view):
    forms.alert("Show Relationships works in plan and drafting views only.", exitscript=True)

settings = ov.load_settings()
sel_ids = set(ec.idval(e.Id) for e in ec.selected_markers(doc, uidoc))
markers = ec.collect_markers(doc, view)
res = ec.solve(markers)
existing, labels = ov.overlay_elements(doc, view)

drawn, msgs = 0, []
t = Transaction(doc, "Egress Show Relationships")
t.Start()
try:
    state = ov.read_state(view)
    if existing:
        ov.save_positions(labels, state)
        ov.delete(doc, existing)
    if sel_ids or not existing:
        seeds = [m for m in markers if m.id in sel_ids]
        scope = ec.branch(res, seeds) if seeds else markers
        drawn, msgs = ov.draw(doc, view, res, scope, settings, state)
        if drawn and settings.get("halftone"):
            msgs += ov.apply_halftone(doc, view, state)
        else:
            msgs += ov.restore_view(doc, view, state)
    else:
        msgs += ov.restore_view(doc, view, state)
    ov.write_state(view, state)
    t.Commit()
except Exception:
    t.RollBack()
    raise

if not drawn and not existing:
    msgs.append("No connected egress markers found in this view. Use the Build tools first.")
if msgs:
    forms.alert("\n\n".join(msgs), title="EgressTools")
