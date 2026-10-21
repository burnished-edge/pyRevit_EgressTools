# -*- coding: utf-8 -*-
"""Remove Health Check colours from the active view (your own overrides are kept)."""
__title__ = "Clear\nHighlights"
from pyrevit import revit, forms
from Autodesk.Revit.DB import Transaction
import egress_core as ec

doc = revit.doc
view = doc.ActiveView
t = Transaction(doc, "Egress Clear Highlights")
t.Start()
n = ec.clear_highlights(view, ec.collect_markers(doc, view))
t.Commit()
forms.alert("Cleared %d highlighted marker(s)." % n, title="EgressTools")
