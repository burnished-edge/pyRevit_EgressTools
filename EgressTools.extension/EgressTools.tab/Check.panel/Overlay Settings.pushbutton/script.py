# -*- coding: utf-8 -*-
"""Options for the Show Relationships overlay."""
from pyrevit import forms, script
import egress_overlay as ov

s = ov.load_settings()
SAVE = "Save"
LW = "Line weight: %d   (change...)" % int(s["line_weight"])
SP = "Arrowhead spacing: %.2f in on paper   (change...)" % float(s["arrow_spacing"])
RL = "Show room labels"
HT = "Halftone the plan while the overlay is on"
res = forms.CommandSwitchWindow.show(
    [SAVE, LW, SP],
    switches={RL: bool(s["room_labels"]), HT: bool(s["halftone"])},
    message="Overlay settings - applied the next time you click Show Relationships")
if not res or not res[0]:
    script.exit()
choice, sw = res
s["room_labels"] = bool(sw.get(RL, s["room_labels"]))
s["halftone"] = bool(sw.get(HT, s["halftone"]))
if choice == LW:
    v = forms.ask_for_string(default=str(s["line_weight"]), title="Overlay line weight",
                             prompt="Revit pen weight for the arcs (1-16, default 8). Arrowheads use 2 less.")
    try:
        s["line_weight"] = max(1, min(16, int(v)))
    except (TypeError, ValueError):
        forms.alert("Line weight must be a whole number from 1 to 16.", exitscript=True)
elif choice == SP:
    v = forms.ask_for_string(default=str(s["arrow_spacing"]), title="Arrowhead spacing",
                             prompt="Distance between small arrowheads, in inches on paper (0.25-3).")
    try:
        s["arrow_spacing"] = max(0.25, min(3.0, float(v)))
    except (TypeError, ValueError):
        forms.alert("Spacing must be a number, e.g. 0.75.", exitscript=True)
ov.save_settings(s)
forms.alert("Saved. Click Show Relationships to apply.", title="EgressTools")
