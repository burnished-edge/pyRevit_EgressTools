# -*- coding: utf-8 -*-
"""Connect markers to a stair / exit and set its capacity."""
__title__ = "Connect\nTo Exit"
from pyrevit import revit, forms, script
from Autodesk.Revit.DB import Transaction
import egress_core as ec

doc, uidoc = revit.doc, revit.uidoc
view = doc.ActiveView

sel = ec.selected_markers(doc, uidoc) or ec.pick_markers(
    doc, uidoc, "Select markers going INTO the stair / exit, then Finish")
if not sel:
    script.exit()

existing = ec.collect_markers(doc, view)
res = ec.solve(existing)
exits = ec.exit_names(existing)
NEW = "+ New exit"
choice = forms.SelectFromList.show([NEW] + exits, title="Connect to which exit?",
                                   multiselect=False) if exits else NEW
if not choice:
    script.exit()

if choice == NEW:
    name = forms.ask_for_string(default=ec.next_name(existing, ec.PREFIX_EXIT),
                                title="New exit",
                                prompt="Exit name (keep the auto name or type e.g. STAIR-W):")
    if not name:
        script.exit()
    cap_default = ""
else:
    name = choice
    row = res.row.get(choice)
    cap_default = str(row.cap) if row and row.cap else ""

cap = forms.ask_for_string(default=cap_default, title="Exit capacity",
                           prompt="Capacity of %s (occupants):" % ec.norm(name))
try:
    cap = int(cap)
except (TypeError, ValueError):
    forms.alert("Capacity must be a whole number.", exitscript=True)

name = ec.norm(name)
sel_ids = set(ec.idval(e.Id) for e in sel)
t = Transaction(doc, "Egress Connect To Exit")
t.Start()
for e in sel:
    ec.set_value(e, ec.P_TO, name)
# keep capacity consistent on every marker into this exit
for m in existing:
    if m.to == name or m.id in sel_ids:
        ec.set_value(m.el, ec.P_CAP, cap)
t.Commit()

ec.run(doc, view)
