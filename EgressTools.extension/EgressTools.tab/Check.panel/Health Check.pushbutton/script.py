# -*- coding: utf-8 -*-
"""One click: rebalance, colour problem markers, select them, report.
Red = over capacity | Orange = unbalanced | Yellow = missing data | Purple = broken path"""
__title__ = "Health\nCheck"
from pyrevit import revit, script
from System.Collections.Generic import List
from Autodesk.Revit.DB import ElementId
import egress_core as ec

doc, uidoc = revit.doc, revit.uidoc
res, changed = ec.run(doc, doc.ActiveView, write_values=True, highlight="on")
bad = [m.el.Id for m in res.markers if m.flags]
uidoc.Selection.SetElementIds(List[ElementId](bad))
out = script.get_output()
ec.report(out, res, changed, "health check")
out.print_md("Colours: **Red** over capacity | **Orange** unbalanced | "
             "**Yellow** missing data | **Purple** broken path. "
             "Problem markers are selected. Run **Clear Highlights** before printing.")
