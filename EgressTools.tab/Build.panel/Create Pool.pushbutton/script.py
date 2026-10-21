# -*- coding: utf-8 -*-
"""Pool occupants in a corridor: pick markers flowing IN, then markers flowing OUT.
Outgoing markers are set to equal split."""
__title__ = "Create\nPool"
from pyrevit import revit, forms, script
from Autodesk.Revit.DB import Transaction
import egress_core as ec

doc, uidoc = revit.doc, revit.uidoc
view = doc.ActiveView
existing = ec.collect_markers(doc, view)
pools = ec.pool_names(existing)

NEW = "New pool"
ADD = "Add to existing pool"
choice = forms.CommandSwitchWindow.show([NEW, ADD] if pools else [NEW],
                                        message="Create Pool") if pools else NEW
if not choice:
    script.exit()

if choice == ADD:
    name = forms.SelectFromList.show(pools, title="Pick pool", multiselect=False)
    if not name:
        script.exit()
else:
    name = forms.ask_for_string(default=ec.next_name(existing, ec.PREFIX_POOL),
                                title="Create Pool",
                                prompt="Pool name (keep the auto name or type e.g. CORR-WEST):")
    if not name:
        script.exit()
name = ec.norm(name)

ins = ec.pick_markers(doc, uidoc, "%s: select markers flowing INTO the pool, then Finish "
                      "(Esc = none)" % name)
outs = ec.pick_markers(doc, uidoc, "%s: select markers flowing OUT of the pool, then Finish "
                       "(Esc = none)" % name)
if not ins and not outs:
    script.exit()
both = set(ec.idval(e.Id) for e in ins) & set(ec.idval(e.Id) for e in outs)
if both:
    forms.alert("A marker can't flow both into and out of the same pool.", exitscript=True)

t = Transaction(doc, "Egress Create Pool")
t.Start()
for e in ins:
    ec.set_value(e, ec.P_TO, name)
for e in outs:
    ec.set_value(e, ec.P_FROM, name)
    ec.set_value(e, ec.P_BAL, 1)
    ec.set_value(e, ec.P_LOAD, 0)     # pools have no own load
t.Commit()

ec.run(doc, view)
