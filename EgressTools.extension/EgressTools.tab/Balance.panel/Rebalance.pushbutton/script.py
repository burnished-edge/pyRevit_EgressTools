# -*- coding: utf-8 -*-
"""Fill balance markers in the active view and show node totals."""
__title__ = "Rebalance"
from pyrevit import revit, script
import egress_core as ec

doc = revit.doc
res, changed = ec.run(doc, doc.ActiveView, write_values=True, highlight="auto")
ec.report(script.get_output(), res, changed, "rebalanced")
