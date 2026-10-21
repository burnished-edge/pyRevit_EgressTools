# -*- coding: utf-8 -*-
"""Select the door markers of ONE room, enter the room load -> equal split."""
__title__ = "Room\nSplit"
from pyrevit import revit, forms, script
from Autodesk.Revit.DB import Transaction
import egress_core as ec

doc, uidoc = revit.doc, revit.uidoc
view = doc.ActiveView

sel = ec.selected_markers(doc, uidoc) or ec.pick_markers(
    doc, uidoc, "Select the door markers of ONE room, then Finish")
if not sel:
    script.exit()

existing = ec.collect_markers(doc, view)
froms = set(ec.norm(ec.get_text(e, ec.P_FROM)) for e in sel) - {""}
default_name = froms.pop() if len(froms) == 1 else ec.next_name(existing, ec.PREFIX_ROOM)
default_load = max([ec.get_int(e, ec.P_LOAD) for e in sel] + [0])

name = forms.ask_for_string(default=default_name, title="Room Split - %d door(s)" % len(sel),
                            prompt="Room name (keep the auto name or type e.g. MOC):")
if not name:
    script.exit()
load = forms.ask_for_string(default=str(default_load or ""), title="Room Split",
                            prompt="Room occupant load:")
try:
    load = int(load)
except (TypeError, ValueError):
    forms.alert("Occupant load must be a whole number.", exitscript=True)

t = Transaction(doc, "Egress Room Split")
t.Start()
for e in sel:
    ec.set_value(e, ec.P_FROM, ec.norm(name))
    ec.set_value(e, ec.P_LOAD, load)
    ec.set_value(e, ec.P_BAL, 1)
t.Commit()

ec.run(doc, view)
