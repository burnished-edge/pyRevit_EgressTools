EGRESSTOOLS v1.5 - pyRevit extension

INSTALL / UPGRADE
1. Delete the old EgressTools.extension folder (v1 buttons are replaced).
2. Unzip this one to the same place, e.g. %APPDATA%\pyRevit\Extensions\
3. pyRevit tab > Reload.
Existing markers and parameters from v1 keep working - no migration.

SETUP (once per project)
- Manage > Shared Parameters: load a shared parameter file.
- Select a marker > Setup Parameters.

BASIC WORKFLOW (no typing of node names)
1. Room Split     - select a room's door markers, enter room load -> equal split.
2. Create Pool    - pick markers flowing INTO the corridor (Finish), then markers
                    flowing OUT (Finish). Outgoing = equal split.
                    Use "Add to existing pool" to extend one. Pools can feed pools.
3. Connect To Exit- select markers going into a stair, pick/create the exit, enter capacity.
4. Health Check   - rebalances, colours problems, selects them, prints totals.

ADJUSTING NUMBERS
- With Auto Rebalance ON, type a number into any marker: that marker becomes manual
  (EG_Balance unticked) and the other markers at the same split absorb the change.
- To return a marker to automatic, tick EG_Balance again.

CHECK TOOLS
- Health Check: Red over capacity | Orange unbalanced | Yellow missing data | Purple broken path
- Clear Highlights: removes only EgressTools colours.
- Show Relationships: select markers = show that branch; nothing selected = whole view.
  Click again with nothing selected to hide. Blue OK, red problem.
- Inspector: what feeds a marker, where it goes, and occupants by room of origin.

ADVANCED
- Set Path, or edit EG_From / EG_To / EG_Load / EG_Capacity / EG_Balance in Properties
  exactly as in v1. Auto names (ROOM-001, POOL-001, EXIT-001) can be renamed freely
  as long as every marker using that node is renamed the same.

BEFORE PRINTING / ISSUING
- Clear Highlights and hide Show Relationships - both are real view graphics.
