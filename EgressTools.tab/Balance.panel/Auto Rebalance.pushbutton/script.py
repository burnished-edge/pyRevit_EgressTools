# -*- coding: utf-8 -*-
"""Toggle automatic rebalancing when a marker is edited."""
__title__ = "Auto\nRebalance"
from pyrevit import forms
import egress_core as ec

ec.set_auto(not ec.auto_enabled())
forms.alert("Auto Rebalance is now %s." % ("ON" if ec.auto_enabled() else "OFF"),
            title="EgressTools")
