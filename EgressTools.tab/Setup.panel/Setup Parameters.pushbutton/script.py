# -*- coding: utf-8 -*-
"""Check the marker family for the EgressTools shared parameters and add any
that are missing (written to the loaded Shared Parameters file)."""
__title__ = "Setup\nParameters"
import os
from pyrevit import revit, forms, script
from Autodesk.Revit.DB import (
    BuiltInCategory, FamilyInstance, Transaction, IFamilyLoadOptions,
    FamilySource, ExternalDefinitionCreationOptions, SpecTypeId, GroupTypeId,
)
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
import egress_core as ec

doc, uidoc, app = revit.doc, revit.uidoc, revit.doc.Application

SPEC = {"text": SpecTypeId.String.Text,
        "yesno": SpecTypeId.Boolean.YesNo,
        "int": SpecTypeId.Int.Integer}
GROUP = {"text": GroupTypeId.Text, "graphics": GroupTypeId.Graphics}
SP_GROUP_NAME = "Egress Markers"


class OccFilter(ISelectionFilter):
    def AllowElement(self, el):
        return (isinstance(el, FamilyInstance) and el.Category is not None
                and ec.idval(el.Category.Id) == int(BuiltInCategory.OST_GenericAnnotation)
                and el.LookupParameter(ec.P_OCC) is not None)

    def AllowReference(self, ref, pt):
        return False


class LoadOpts(IFamilyLoadOptions):
    def OnFamilyFound(self, familyInUse, overwriteParameterValues):
        overwriteParameterValues.Value = False
        return True

    def OnSharedFamilyFound(self, sharedFamily, familyInUse, source, overwriteParameterValues):
        source.Value = FamilySource.Family
        overwriteParameterValues.Value = False
        return True


flt = OccFilter()
picked = [doc.GetElement(i) for i in uidoc.Selection.GetElementIds()]
picked = [e for e in picked if flt.AllowElement(e)]
if not picked:
    try:
        picked = [doc.GetElement(uidoc.Selection.PickObject(
            ObjectType.Element, flt, "Pick one egress occupant marker"))]
    except Exception:
        script.exit()

family = picked[0].Symbol.Family
fam_name = family.Name          # cache: reloading invalidates the reference

famdoc = doc.EditFamily(family)
fm = famdoc.FamilyManager
existing = set(p.Definition.Name for p in fm.Parameters)
missing = [r for r in ec.REQUIRED_PARAMS if r[0] not in existing]

if not missing:
    famdoc.Close(False)
    forms.alert("'%s' already has all EgressTools parameters." % fam_name, title="EgressTools")
    script.exit()

names = "\n".join("  - %s (%s)" % (r[0], r[1]) for r in missing)
if not forms.alert("'%s' is missing these parameters:\n\n%s\n\nCreate them now?"
                   % (fam_name, names), title="EgressTools", yes=True, no=True):
    famdoc.Close(False)
    script.exit()

sp_path = app.SharedParametersFilename
if not sp_path or not os.path.exists(sp_path):
    famdoc.Close(False)
    forms.alert("No Shared Parameters file is loaded.\n\n"
                "Go to Manage > Shared Parameters, browse to (or create) a shared "
                "parameter file, click OK, then run Setup Parameters again so the "
                "tool can write the required parameters to it.",
                title="EgressTools - Shared Parameters file required")
    script.exit()

def_file = app.OpenSharedParameterFile()
if def_file is None:
    famdoc.Close(False)
    forms.alert("The Shared Parameters file could not be opened:\n%s" % sp_path,
                title="EgressTools")
    script.exit()


def find_def(name):
    for g in def_file.Groups:
        d = g.Definitions.get_Item(name)
        if d is not None:
            return d
    return None


sp_group = def_file.Groups.get_Item(SP_GROUP_NAME) or def_file.Groups.Create(SP_GROUP_NAME)

defs = []
for name, kind, grp, desc in missing:
    d = find_def(name)
    if d is None:
        opts = ExternalDefinitionCreationOptions(name, SPEC[kind])
        opts.Description = desc
        opts.Visible = True
        d = sp_group.Definitions.Create(opts)
    defs.append((d, grp))

t = Transaction(famdoc, "Add EgressTools parameters")
t.Start()
for d, grp in defs:
    fm.AddParameter(d, GROUP[grp], True)
t.Commit()

famdoc.LoadFamily(doc, LoadOpts())
famdoc.Close(False)

forms.alert("Added %d parameter(s) to '%s' and reloaded it.\n\nShared parameter file: %s"
            % (len(defs), fam_name, sp_path), title="EgressTools")
