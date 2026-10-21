# -*- coding: utf-8 -*-
"""Advanced: type EG_From / EG_To for selected markers (v1 workflow).
All parameters can also still be edited directly in Properties."""
__title__ = "Set\nPath"
from pyrevit import revit, forms, script
from Autodesk.Revit.DB import Transaction
import egress_core as ec

doc, uidoc = revit.doc, revit.uidoc
sel = ec.selected_markers(doc, uidoc) or ec.pick_markers(
    doc, uidoc, "Select egress markers, then Finish")
if not sel:
    script.exit()

frm = forms.ask_for_string(default=ec.get_text(sel[0], ec.P_FROM), title="Set Path",
                           prompt="EG_From (blank = keep existing):")
if frm is None:
    script.exit()
to = forms.ask_for_string(default=ec.get_text(sel[0], ec.P_TO), title="Set Path",
                          prompt="EG_To (blank = keep existing):")
if to is None:
    script.exit()

t = Transaction(doc, "Egress Set Path")
t.Start()
for e in sel:
    if frm.strip():
        ec.set_value(e, ec.P_FROM, ec.norm(frm))
    if to.strip():
        ec.set_value(e, ec.P_TO, ec.norm(to))
t.Commit()
