# -*- coding: utf-8 -*-
"""EgressTools Auto Rebalance.
- Editing a marker rebalances the active view (when Auto Rebalance is ON).
- Typing a number into a balance marker switches that marker to manual,
  so the other markers at that split absorb the change.
- Health Check colours refresh automatically if they're showing."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from System import AppDomain, EventHandler
from Autodesk.Revit.DB.Events import DocumentChangedEventArgs, UndoOperation
from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent
from Autodesk.Revit.UI.Events import ViewActivatedEventArgs
from pyrevit import HOST_APP
import egress_core as ec

_cache = {}     # (doc key, element id) -> last known Occupants
_locks = set()  # marker ids the user typed into


def _key(doc):
    return doc.PathName or doc.Title


def _remember(doc, els):
    k = _key(doc)
    for el in els:
        _cache[(k, ec.idval(el.Id))] = ec.get_int(el, ec.P_OCC)


class _Handler(IExternalEventHandler):
    def Execute(self, uiapp):
        try:
            uidoc = uiapp.ActiveUIDocument
            if uidoc is None or uidoc.Document.IsFamilyDocument:
                return
            locks = set(_locks)
            _locks.clear()
            ec.run(uidoc.Document, uidoc.ActiveView, write_values=True,
                   highlight="auto", lock_ids=locks)
        except Exception:
            pass

    def GetName(self):
        return "EgressTools Auto Rebalance"


_event = ExternalEvent.Create(_Handler())


def _on_changed(sender, args):
    try:
        doc = args.GetDocument()
        if doc.IsFamilyDocument:
            return
        ids = list(args.GetModifiedElementIds()) + list(args.GetAddedElementIds())
        els = [doc.GetElement(i) for i in ids]
        els = [e for e in els if e is not None and ec.is_marker(e)]
        if not els:
            return
        if args.Operation != UndoOperation.TransactionCommitted:
            _remember(doc, els)                     # undo / redo: just resync
            return
        ours = ec.TXN_NAME in list(args.GetTransactionNames())
        if not ours:
            k = _key(doc)
            for e in els:
                prev = _cache.get((k, ec.idval(e.Id)))
                if (prev is not None and ec.get_int(e, ec.P_OCC) != prev
                        and ec.get_int(e, ec.P_BAL) == 1):
                    _locks.add(ec.idval(e.Id))
        _remember(doc, els)
        if not ours and ec.auto_enabled():
            _event.Raise()
    except Exception:
        pass


def _on_view(sender, args):
    try:
        doc, view = args.Document, args.CurrentActiveView
        if doc is not None and view is not None and not doc.IsFamilyDocument:
            _remember(doc, ec.marker_elements(doc, view))
    except Exception:
        pass


# remove handlers from a previous pyRevit reload, then register
_dom = AppDomain.CurrentDomain
_old = _dom.GetData("EgressTools.handlers")
if _old is not None:
    try:
        HOST_APP.app.DocumentChanged -= _old[0]
        HOST_APP.uiapp.ViewActivated -= _old[1]
    except Exception:
        pass
_h1 = EventHandler[DocumentChangedEventArgs](_on_changed)
_h2 = EventHandler[ViewActivatedEventArgs](_on_view)
HOST_APP.app.DocumentChanged += _h1
HOST_APP.uiapp.ViewActivated += _h2
_dom.SetData("EgressTools.handlers", (_h1, _h2))
