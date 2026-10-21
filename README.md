# EgressTools for Revit

**Occupant load markers that add themselves up.**

EgressTools is a pyRevit add-in for egress and occupancy plans. You place occupant markers at doors as usual. The tool keeps the numbers consistent, so that:

- each room's occupants are split across its doors,
- occupants from several rooms are **pooled** in a corridor and split again toward the exits,
- each stair or exit is checked against its capacity, and
- when you change one number, the others at that split update to keep the totals correct.

It can also draw a color-coded **flow overlay** on the plan, like a hand markup, so you can see where everyone goes.

![EgressTools ribbon tab](images/01_ribbon.png)
> 📷 **SCREENSHOT 01:** The full EgressTools ribbon tab showing all five panels.

---

## Contents

1. [Before you start](#1-before-you-start)
2. [Installation](#2-installation)
3. [How the tool thinks](#3-how-the-tool-thinks)
4. [The marker parameters explained](#4-the-marker-parameters-explained)
5. [One-time project setup](#5-one-time-project-setup)
6. [Step-by-step: building an egress plan](#6-step-by-step-building-an-egress-plan)
7. [Changing numbers by hand](#7-changing-numbers-by-hand)
8. [Checking your work](#8-checking-your-work)
9. [Before you print or issue](#9-before-you-print-or-issue)
10. [Button reference](#10-button-reference)
11. [Status messages and how to fix them](#11-status-messages-and-how-to-fix-them)
12. [Advanced: editing parameters directly](#12-advanced-editing-parameters-directly)
13. [Troubleshooting and FAQ](#13-troubleshooting-and-faq)
14. [Known limitations](#14-known-limitations)
15. [Glossary](#15-glossary)

---

## 1. Before you start

**You'll need:**

- Revit with **pyRevit** installed. If you have a **pyRevit** tab on your Revit ribbon, you have it.
- The occupant marker family **Symbol - Occupant Load_Editable**.
- A **Shared Parameters file** (only for the one-time project setup; see [Section 5](#5-one-time-project-setup)).

**New to pyRevit?** pyRevit is a free add-in that lets Revit run small Python tools. EgressTools is one of those tools. Once it's installed, it works like any other Revit tab: click a button, follow the prompts at the bottom-left of the Revit window (the **status bar**), and read the results in a pop-up **output window**.

> 💡 **Two habits that help with every button:**
> - **Watch the status bar** (bottom-left of Revit). When a tool asks you to pick things, the instructions appear there.
> - **"Finish" vs. Esc.** When picking several markers, click **Finish** in the Options Bar (top-left, under the ribbon) when you're done. Pressing **Esc** usually means "cancel" or "skip this step."

---

## 2. Installation

<!-- ===================================================== -->
<!-- TODO: Insert GitHub installation instructions here.   -->
<!-- ===================================================== -->

*Installation instructions coming soon.*

**After installing:** if you previously used Version 1 of EgressTools, delete the old `EgressTools.extension` folder first. Otherwise you'll see two sets of buttons, and Auto Rebalance will run twice. Your existing markers and their values carry over without any changes.

---

## 3. How the tool thinks

You only need four ideas to use this tool.

### Idea 1: Every marker is an arrow from one place to another

Each marker says *"this many people move **from** here **to** there."* The "places" are called **nodes**. There are three kinds:

| Node type | What it is | Example names |
|---|---|---|
| **Room** | Where occupants start. Has its own occupant load. | `MOC`, `PANTRY`, `ROOM-001` |
| **Pool** | A shared space (usually a corridor) where occupants from several rooms come together before splitting toward exits. | `BRIDGE`, `CORR-WEST`, `POOL-001` |
| **Exit** | Where occupants leave: a stair door or exterior exit. Has a capacity. | `STAIR 2`, `EXIT-001` |

You don't have to tell the tool which kind a node is. It works it out:
- A node that only **sends** occupants is a **Room**.
- A node that **receives and sends** occupants is a **Pool**.
- A node that only **receives** occupants is an **Exit**.

### Idea 2: What goes in must come out

At every room and pool:

> **Occupants leaving = the room's own load + everything arriving from upstream**

At every exit:

> **Occupants arriving must not exceed the exit's capacity**

### Idea 3: "Balance" markers fill in automatically

Each marker is either:

- **Balance (automatic):** the tool calculates its number.
- **Manual:** you type the number and the tool never changes it.

At each split:

| Markers leaving the node | What happens |
|---|---|
| All are Balance | The total is **split evenly**. Example: 116 over 3 doors becomes 39 / 39 / 38. |
| Some Manual, some Balance | The Balance markers share **whatever is left** after the Manual numbers. |
| All Manual | Nothing is changed. The tool only **checks** that they add up. |

### Idea 4: The tool works on the current view only

EgressTools only looks at markers **in the view you have open**. Each plan or sketch is calculated on its own, so you can reuse node names like `STAIR 1` on every floor without them interfering.

### A simple example

![Example flow diagram](images/02_flow_example.png)
> 📷 **SCREENSHOT 02:** A small plan (or redline) showing one room with three door markers flowing into a corridor, and two markers from the corridor into two stairs. Label: "MOC (116) → 39 / 39 / 38 → BRIDGE (pool, 148 total with Pantry's 32) → 74 to STAIR 1, 74 to STAIR 2."

```
MOC (load 116)  ──39──┐
                ──39──┤
                ──38──┤
                      ├──►  BRIDGE (pool: 148)  ──74──►  STAIR 1 (cap 220)
PANTRY (load 32) ─32──┘                         ──74──►  STAIR 2 (cap 220)
```

---

## 4. The marker parameters explained

Select any marker and look at the **Properties** palette. EgressTools adds a few parameters that start with `EG_`.

![Marker parameters, annotated](images/03_parameters_annotated.png)
> 📷 **SCREENSHOT 03 (diagram):** The Properties palette for a selected marker, with callouts pointing to each parameter. Use the example values below. **Scroll up in the palette** so `EG_Balance` (in the **Graphics** group, near Top/Bottom/Left/Right) is visible as well.

Using a real marker as the example. This marker carries **148 occupants from the BRIDGE corridor into STAIR 2**, which can take **220**:

| Parameter | Example value | What to enter | When to fill it in | Who fills it in? |
|---|---|---|---|---|
| **Occupants** | `148` | A whole number: the number shown in the bubble. | **Automatic marker:** leave it. **Manual marker:** type the number you want. | You (Manual) or the tool (Automatic) |
| **EG_From** | `BRIDGE` | The name of the room or corridor this door leads **out of**. | Every marker. | Build tools, or you |
| **EG_To** | `STAIR 2` | The name of the corridor, stair or exit this door leads **into**. | Every marker. | Build tools, or you |
| **EG_Load** | `0` | A whole number: the **room's total occupant load** from your occupancy calculation. | On markers leaving a **room** (one door is enough). Leave it **0** on markers leaving a **corridor**; a corridor's total is added up from the rooms feeding it. That's why this example is 0. | Room Split, or you |
| **EG_Capacity** | `220` | A whole number: the **most occupants the exit can take**, from your egress width calculation. | On markers going **into** a stair or exit. Leave it blank (0) otherwise. | Connect To Exit, or you |
| **EG_Balance** | ☑ / ☐ | **Ticked** = the tool calculates Occupants. **Unticked** = you set it. Found in the **Graphics** group. | The Build tools tick it. Typing into Occupants (with Auto Rebalance on) unticks it. | Build tools, or you |
| **EG_Status** | `OK` | **Nothing. Don't edit it.** The tool writes `OK` or a short problem description. | Updated every recalculation. | The tool |

**Parameters EgressTools doesn't touch:**
- **Top / Bottom / Left / Right** control which side of the bubble the chevron sits on. Set them as you always have.
- **Occupants shows decimals** (e.g., `148.000000`) because it's a Number parameter. The tool always writes whole numbers, and the bubble displays them without decimals.

> 💡 **Node names** aren't case-sensitive, and extra spaces are ignored (`stair 2` = `STAIR 2`). Otherwise, they must be spelled **exactly** the same on every marker. `STAIR 2` and `STAIR-2` are two different exits.

---

## 5. One-time project setup

You need to do this **once per Revit project** (or once per family, if you load the updated family into other projects).

### Step 1: Load a Shared Parameters file

1. Go to **Manage tab > Shared Parameters**.
2. Click **Browse** and pick your office or project shared parameters `.txt` file. If you don't have one, click **Create**, save a new one somewhere permanent (e.g., your project folder), and name it something like `EgressTools_SharedParams.txt`.
3. Click **OK**.

![Shared Parameters dialog](images/04_shared_params.png)
> 📷 **SCREENSHOT 04:** The Edit Shared Parameters dialog with a file path filled in.

> **Why is this needed?** Revit only lets tools add certain kinds of parameters to a family if they're recorded in a shared parameters file. EgressTools writes its parameters into a group called **"Egress Markers"** in that file.

### Step 2: Run Setup Parameters

1. Place (or select) one occupant marker in any view.
2. Click **EgressTools > Setup > Setup Parameters**.
3. A message lists the parameters the family is missing. Click **Yes**.
4. Wait a few seconds while the tool opens the family, adds the parameters, and reloads it into your project.
5. You'll see a confirmation message.

![Setup Parameters prompt](images/05_setup_prompt.png)
> 📷 **SCREENSHOT 05:** The "missing parameters... Create them now?" message.

**Good to know:**
- Your existing **Occupants** values and arrow directions are **not** changed.
- Run it again any time. If nothing is missing, it says so and does nothing.
- If you forgot Step 1, the tool stops and tells you to load a shared parameters file first.

---

## 6. Step-by-step: building an egress plan

This is the everyday workflow. You **won't need to type node names into Properties**, because the Build tools fill them in for you.

> ✅ **Before you start:** open the egress plan view and place your occupant markers at the doors, as you normally would. Set their arrow direction (Top/Bottom/Left/Right). Leave Occupants at 0; the tool will fill them in.

> 💡 **Turn on Auto Rebalance first** (Balance panel). With it on, every change you make recalculates the view immediately. Click once to toggle; a message confirms ON or OFF. The setting is remembered after you close and reopen Revit.

### Step 1: Split each room across its doors (Room Split)

Do this for **each room**.

1. Select the door markers for **one room**. You can select them before clicking the button, or click the button first and pick them (then click **Finish**).
2. Click **Build > Room Split**.
3. **Room name:** accept the automatic name (e.g., `ROOM-001`) or type a meaningful one like `MOC`. Meaningful names make the reports and overlay labels much easier to read.
4. **Room occupant load:** type the room's occupant load, e.g., `116`.
5. The markers fill in automatically: **39 / 39 / 38**.

![Room Split before and after](images/06_room_split.png)
> 📷 **SCREENSHOT 06:** Side-by-side: three door markers showing 0 → the same markers showing 39 / 39 / 38.

> 💡 **One-door rooms:** use Room Split too. The single marker will always equal the room load.

> 💡 **Odd numbers:** when a total doesn't divide evenly, the extra occupants go to the markers placed first. 116 ÷ 3 = 39 / 39 / 38.

### Step 2: Pool rooms into a corridor (Create Pool)

Do this for **each corridor** (or corridor segment) where occupants come together.

1. Click **Build > Create Pool**.
2. If pools already exist in this view, choose **New pool** or **Add to existing pool**.
3. **Pool name:** accept the automatic name (e.g., `POOL-001`) or type one like `BRIDGE` or `CORR-WEST`.
4. **Pick the markers flowing INTO the corridor** (the room door markers), then click **Finish**.
5. **Pick the markers flowing OUT of the corridor** (usually the stair door markers), then click **Finish**.
6. The outgoing markers are set to split the pooled total evenly.

![Create Pool picking](images/07_create_pool.png)
> 📷 **SCREENSHOT 07:** Two panels. Left: room door markers selected (blue) as "flowing in." Right: stair door markers selected as "flowing out," with the status-bar prompt visible.

> 💡 **Pick both in and out markers in the same run.** A pool only appears in the "Add to existing pool" list once it has both incoming and outgoing markers.

> 💡 **Uneven or multi-stage corridors:** if a corridor splits, then splits again, make **one pool per segment**. The markers leaving pool A become the markers flowing into pool B. You can chain as many as you need, and branches can split and recombine.

> ⚠️ A marker can't flow **into and out of** the same pool. The tool will stop you if you pick the same marker in both steps.

### Step 3: Connect to the stairs and exits (Connect To Exit)

Do this for **each stair or exit**.

1. Select the marker(s) leading **into** the stair (usually the ones you picked as "flowing out" in Step 2).
2. Click **Build > Connect To Exit**.
3. Choose an existing exit from the list, or **+ New exit** and give it a name (e.g., `STAIR 2`).
4. **Capacity:** type the stair's capacity (e.g., `220`). This is the maximum number of occupants the exit can take, based on your egress width calculations.
5. Every marker going into that exit is set to the same capacity.

![Connect To Exit](images/08_connect_exit.png)
> 📷 **SCREENSHOT 08:** The exit list with "+ New exit" and an existing stair, and the capacity prompt.

> 💡 **Changing a capacity later:** run Connect To Exit again on any marker going into that stair, pick the same exit, and type the new capacity. The tool updates all of its markers.

### Step 4: Check it (Health Check and Show Relationships)

Click **Check > Health Check** to find problems, and **Check > Show Relationships** to see the flow on the plan. See [Section 8](#8-checking-your-work).

---

## 7. Changing numbers by hand

Often the even split isn't what you want. For example, one stair should take more occupants because it's closer to the largest room. You can change any number by hand.

### With Auto Rebalance ON (recommended)

1. Select the marker you want to change.
2. In Properties, type the new number into **Occupants** and click **Apply** (or move the cursor off the palette).
3. The tool:
   - **unticks EG_Balance** on that marker, so your number is kept from now on, and
   - recalculates the **other** markers at the same split to absorb the difference.

**Example:** MOC's three doors were 39 / 39 / 38. You type **45** into the first one. Result: **45** (manual) / **36** / **35**. The total is still 116.

![Manual override example](images/09_manual_override.png)
> 📷 **SCREENSHOT 09:** Before (39/39/38) and after (45/36/35), with Properties showing EG_Balance unticked on the edited marker.

> 💡 If you type into the **last** automatic marker at a split, another marker at that split is switched to automatic so the totals still work.

> 💡 **One-door rooms** can't be overridden this way, because there's no other door to absorb the difference. Change the room's **EG_Load** instead.

### Making a marker automatic again

Tick **EG_Balance** on that marker. With Auto Rebalance on, its number is recalculated immediately. Otherwise, click **Rebalance**.

### With Auto Rebalance OFF

Typing a number does **not** switch the marker to manual. If EG_Balance is still ticked, your number will be overwritten the next time you click Rebalance. **Untick EG_Balance first, then type your number**, then click **Rebalance**.

---

## 8. Checking your work

### Health Check: the one-click check

Click **Check > Health Check**. In one step it:

1. recalculates all automatic markers,
2. **colors** any marker with a problem,
3. **selects** the problem markers so you can find them, and
4. opens a **report** with totals for every room, pool and exit.

| Color | Meaning | Typical fix |
|---|---|---|
| 🔴 **Red** | **Over capacity.** An exit receives more occupants than its capacity. | Shift occupants to another exit, or check the capacity value. |
| 🟠 **Orange** | **Doesn't add up.** Markers leaving a node total more or less than they should. | Adjust a manual number, or tick EG_Balance on one marker at that split. |
| 🟡 **Yellow** | **Missing information.** No room load, no capacity, or two different values entered for the same room or exit. | Fill in the missing value (see [Section 11](#11-status-messages-and-how-to-fix-them)). |
| 🟣 **Purple** | **Broken path.** A marker has no From/To, or paths loop back on themselves. | Use the Build tools (or Set Path) to connect it. |
| (no color) | OK | |

![Health Check colors](images/10_health_check_plan.png)
> 📷 **SCREENSHOT 10:** A plan after Health Check with one red and one orange marker.

![Health Check report](images/11_health_check_report.png)
> 📷 **SCREENSHOT 11:** The output window: the Node totals table and the "Markers needing attention" list.

**Reading the report:**
- **Node totals table:** one row per room, pool and exit.
  - **Own load:** the room's occupant load (rooms only).
  - **Inflow:** occupants arriving from upstream.
  - **Required out:** own load + inflow, which is what must leave.
  - **Actual out:** what the markers leaving that node currently add up to.
  - **Capacity:** exits only.
  - **Status:** OK, or the problem.
- **Markers needing attention:** each line has a **clickable ID**. Click it to zoom to that marker.

> 💡 Once Health Check colors are showing, they **refresh automatically** as you make changes, so fixed markers lose their color.

### Clear Highlights

Click **Check > Clear Highlights** to remove the Health Check colors. Only EgressTools' colors are removed.

### Show Relationships: the flow overlay

Show Relationships draws the egress flow on the plan, like a hand markup:

- **Thick, curved arrows** run from each door marker to a **boxed corridor label**, then from that label to each stair-door marker.
- **Each transfer gets its own color**, in order:

  | Transfer | Color | Line |
  |---|---|---|
  | 1st: room → corridor | Red | Solid |
  | 2nd: corridor → next corridor or stair | Blue | **Dashed** |
  | 3rd: the next split | Green | Solid |
  | 4th | Magenta | **Dashed** |
  | 5th / 6th | Orange / Teal | Solid / Dashed |

  Every second transfer is dashed, so neighboring steps are easy to tell apart.
- **Small arrowheads** repeat along each arrow, with a larger one at the end, so you can read the direction anywhere along it.
- **Arrows curve to avoid each other.** Each one tries about 20 shapes (gentle curves either way, S-curves, wider loops) and keeps the one with the fewest crossings and the least overlap with labels and markers.
- **Bold, boxed labels** show each corridor's totals (e.g., `CORR  565 in -> 339 / 226`) and each stair's load (e.g., `STAIR 2  240 / 240 cap`). A label with a problem turns dark red and shows the status (e.g., `! OVER CAP 14`).
- **The plan is halftoned** so the arrows stand out.

![Show Relationships overlay](images/12_show_relationships.png)
> 📷 **SCREENSHOT 12:** A halftoned plan with the overlay showing: red arrows from room doors into a boxed CORR label, dashed blue arrows from the label to two stair markers, and a stair label.

**Using it:**

| You do | What happens |
|---|---|
| Click it with **nothing selected** | Draws the overlay for the whole view and halftones the plan. |
| **Select one or more markers**, then click it | Draws only their **branch**: everything upstream and downstream. Best for busy plans, and faster. |
| Click it again with **nothing selected** | **Hides** the overlay and puts the view back the way it was (halftone and view template). |

**Moving labels:** drag any label to where you want it, e.g., into the corridor it represents. Its position is **saved with the view** the next time you click Show Relationships, and reused every time after that. New labels are placed automatically so they don't overlap each other or markers.

> 💡 **The overlay doesn't update live.** After changing numbers or connections, click Show Relationships again (nothing selected hides it; click once more to redraw), or select a marker and click it to redraw just that branch.

> ⚠️ **Views with a view template.** If the template controls the view's Display Model, the plan can't be halftoned while the template is applied. EgressTools **turns the template off** while the overlay is showing and **turns it back on** when you hide the overlay. A message tells you when this happens. Don't change view settings while the template is off; they're overwritten when it's reapplied.

### Overlay Settings

Click **Check > Overlay Settings** to change how the overlay looks. Changes apply the next time you click Show Relationships.

| Setting | Default | What it does |
|---|---|---|
| Show room labels | Off | Adds a bold, boxed label for each room with its name and load. |
| Halftone the plan while the overlay is on | On | Halftones the view so the arrows stand out. |
| Line weight | 8 | Revit pen weight for the arrows (1–16). Arrowheads use 2 less. How thick it looks depends on the view scale. |
| Arrowhead spacing | 0.75" | Distance between the small arrowheads, measured on paper. |

Settings are saved for you on your computer, not in the project.

![Overlay Settings](images/13_overlay_settings.png)
> 📷 **SCREENSHOT 13:** The Overlay Settings window with the two switches and the line weight / spacing options.

### Inspector: explain one marker

Select a marker and click **Check > Inspector** (or click Inspector and pick a marker). The output window shows:

- where the marker comes **from** and goes **to**, and whether it's automatic or manual,
- the totals at both ends,
- **which rooms its occupants originally came from**, e.g., "74 into STAIR 2 = 58 from MOC + 16 from PANTRY", and
- for exit markers, everything arriving at that exit, broken down by room.

![Inspector output](images/14_inspector.png)
> 📷 **SCREENSHOT 14:** Inspector output for a stair marker showing the by-room breakdown table.

> 💡 Breakdowns by room are proportional and may show decimals (e.g., 57.6). They're for understanding the flow, not for printing on the plan.

---

## 9. Before you print or issue

EgressTools' checking graphics are **real view graphics**. They print and they sync to central. Run through this checklist before printing:

- [ ] **Show Relationships** with **nothing selected** until the arrows and labels disappear. This also removes the halftone and reapplies any view template that was turned off.
- [ ] **Clear Highlights** (Check panel). Removes the Health Check colors.
- [ ] Final **Health Check** with all statuses OK. Then Clear Highlights again.

> 💡 **Tip:** keep a separate working copy of the egress view (Duplicate View > Duplicate) for checking, and only print the clean one. Because the tool works per view, any markers you place in a duplicated view are calculated independently.

> ⚠️ If you sync or close the model with the overlay showing, the view stays halftoned and without its template. Nothing is lost: the next time you hide the overlay in that view, everything is put back.

---

## 10. Button reference

| Panel | Button | What it does | When to use it |
|---|---|---|---|
| **Setup** | Setup Parameters | Adds the EG_ parameters to the marker family. | Once per project. |
| **Build** | Room Split | Names a room, sets its load, and splits it evenly across its doors. | Once per room. |
| **Build** | Create Pool | Pools markers into a corridor and splits the total across the outgoing markers. | Once per corridor (or segment). |
| **Build** | Connect To Exit | Connects markers to a stair or exit and sets its capacity. | Once per exit, or to change a capacity. |
| **Balance** | Rebalance | Recalculates all automatic markers in the view and shows the report. | After changes when Auto Rebalance is off, or after deleting markers. |
| **Balance** | Auto Rebalance | Toggles automatic recalculation on every edit. | Keep it on while working. |
| **Check** | Health Check | Recalculates, colors problems, selects them, shows the report. | Whenever you want to verify the plan. |
| **Check** | Clear Highlights | Removes Health Check colors. | Before printing. |
| **Check** | Show Relationships | Shows or hides the color-coded flow overlay (selected branch or whole view). | To understand or present the flow. |
| **Check** | Overlay Settings | Room labels, halftone, line weight and arrowhead spacing for the overlay. | When you want to change how the overlay looks. |
| **Check** | Inspector | Explains one marker in detail. | When a number doesn't make sense. |
| **Advanced** | Set Path | Types From/To directly for selected markers. | Power users; see [Section 12](#12-advanced-editing-parameters-directly). |

> 💡 Hover over any button for a short description.

---

## 11. Status messages and how to fix them

These appear in **EG_Status** on each marker, in the report, and on overlay labels.

| Status | Color | What it means | How to fix it |
|---|---|---|---|
| `OK` | none | All good. | |
| `OVER n` | 🟠 | Markers leaving this node total **n more** than required. | Lower a manual number, or tick EG_Balance on one marker at the split. |
| `UNDER n` | 🟠 | Markers leaving this node total **n fewer** than required. | Raise a manual number, or tick EG_Balance on one marker at the split. |
| `OVER CAP n` | 🔴 | The exit receives **n more** than its capacity. | Move occupants to another exit (override a marker upstream), or confirm the capacity. |
| `NO CAP` | 🟡 | The exit has no capacity entered. | Run Connect To Exit on a marker going into it and enter the capacity. |
| `NO LOAD` | 🟡 | A room has no occupant load and nothing flows into it. | Run Room Split on its markers, or type EG_Load on one of its markers. |
| `LOAD CONFLICT a/b` | 🟡 | Markers leaving the same room have **different** EG_Load values. | Make them match, or clear all but one. Re-running Room Split fixes this. |
| `CAP CONFLICT a/b` | 🟡 | Markers going into the same exit have **different** capacities. The **smaller** is used. | Re-run Connect To Exit to set one capacity. |
| `NO PATH` | 🟣 | EG_From or EG_To is blank. | Connect the marker with Room Split, Create Pool or Connect To Exit. |
| `CYCLE` | 🟣 | A path loops back on itself (A → B → A), or From and To are the same. | Check the From/To names on the markers involved. Egress must always flow toward an exit. |

> 💡 A marker can show more than one status, separated by `;`.

---

## 12. Advanced: editing parameters directly

Everything the Build tools do, you can also do by typing in Properties. This was the original (Version 1) workflow, and it's often faster for small edits.

**The rules:**
- **EG_From / EG_To:** type any node name. Markers with the same From belong to the same split.
- **EG_Load:** enter on **one** marker leaving each room. Leave it blank or 0 on corridors.
- **EG_Capacity:** enter on the markers going **into** each exit.
- **EG_Balance:** tick for automatic, untick for manual.
- **Renaming a node:** rename it on **every** marker that uses it. Select them all and type once in Properties, or use **Advanced > Set Path**. Auto names like `POOL-001` can be renamed freely.

**Set Path button:** select markers, click **Set Path**, and type From and To. Leave a field blank to keep its current value. This is handy for redirecting a group of markers to a different corridor or stair.

> 💡 **Mixing workflows is fine.** The Build tools and manual editing write the same parameters.

> 💡 **Renaming a node moves its overlay label back to the automatic spot,** because saved label positions are stored by name. Drag it again after renaming.

---

## 13. Troubleshooting and FAQ

**The numbers didn't update after I changed something.**
- Check that **Auto Rebalance** is ON, or click **Rebalance**.
- Make sure you're in the right view. The tool only calculates the **active view**.
- **Deleting** a marker doesn't trigger Auto Rebalance. Click **Rebalance** afterwards.

**I typed a number and it changed back.**
- Auto Rebalance was off, so the marker was still automatic (EG_Balance ticked). Untick EG_Balance, retype your number, then click Rebalance. See [Section 7](#7-changing-numbers-by-hand).
- Rarely, right after **pyRevit > Reload**, the first edit isn't recognized as manual. Switch to another view and back, then retype.

**A button says "No egress markers found."**
- Run **Setup Parameters** first. Markers without the EG_ parameters are ignored.
- Make sure the markers are visible in the active view and aren't hidden or in a different view.

**I can't select a marker when the tool asks me to pick.**
- The tool only lets you pick egress markers (the occupant family with the EG_ parameters). Other elements are ignored on purpose.

**Setup Parameters says no Shared Parameters file is loaded.**
- See [Section 5, Step 1](#step-1-load-a-shared-parameters-file).

**An overlay label is in an awkward place, or covers something.**
- Drag it where you want it. Its position is saved the next time you click Show Relationships.

**The overlay arrows still cross in a few places.**
- When doors sit on opposite sides of a corridor, some crossings can't be avoided. Try dragging the corridor label to a more central spot, then redraw. Selecting a marker to show only its branch also helps on busy plans.

**The arrows look too thin or too heavy.**
- Change the line weight in **Overlay Settings**. Pen weights look different at different view scales.

**The plan wasn't halftoned.**
- Check that halftone is on in **Overlay Settings**.
- If a message says the Display Model can't be changed, the view's setting is locked by something other than a view template. Halftone the view manually, or turn the setting off.

**My view template is missing after using the overlay.**
- The overlay is probably still showing. Click Show Relationships with nothing selected to hide it; the template is reapplied. If the template was deleted in the meantime, reapply a template in the view's properties.

**Health Check colored my marker's outline but not the number.**
- Depending on how the family's label is set up, the color may only apply to the linework. The **EG_Status** value and the report are always reliable.

**Workshared model: something didn't update.**
- Editing markers and the view requires you to be able to edit them (not borrowed by someone else). Auto Rebalance skips quietly if it can't edit a marker. Click **Rebalance** or **Health Check** to see any errors, and sync to get the latest elements.

**pyRevit shows an error window (IronPython Traceback).**
- Take a screenshot of the whole error and send it to the tool maintainer, along with what you clicked and what was selected.

**Where are the Auto Rebalance and Overlay Settings stored?**
- Per user, on your computer. They persist between Revit sessions. Overlay label positions are different: they're saved in the project, with each view.

---

## 14. Known limitations

- **Checking graphics print.** Health Check colors, the overlay and its halftone are real view changes. Clear them before printing ([Section 9](#9-before-you-print-or-issue)).
- **Arrows avoid each other, labels and markers, but not walls.** On a dense core, some arrows will cross walls, just like on a hand markup.
- **Some crossings are unavoidable** when doors face each other across a corridor.
- **The overlay doesn't update live.** Click Show Relationships again to refresh it.
- **Large floors take longer.** A whole floor with 70+ doors can take around 10 seconds to draw. Showing one branch at a time is much faster.
- **Plan and drafting views only** for the overlay. Sections and elevations aren't supported.
- **Health Check replaces any color override** you had already applied to a problem marker. Clear Highlights then resets that marker to no override.
- **Deleting markers** doesn't trigger Auto Rebalance.
- **Active view only.** Markers on other views or sheets aren't checked together. Each view is its own calculation.

---

## 15. Glossary

| Term | Meaning |
|---|---|
| **Marker** | The occupant load annotation placed at a door, showing how many people pass through it. |
| **Node** | A named place occupants move between: a room, a pool or an exit. |
| **Pool** | A corridor or shared space where occupants from several rooms combine before splitting toward exits. Plan check expects occupants to be pooled and split this way. |
| **Split** | All the markers leaving the same node. Their numbers must add up to that node's total. |
| **Transfer** | One step of occupants moving from one space to the next, e.g., room → corridor. Each transfer gets its own color in the overlay. |
| **Balance / automatic** | A marker whose number the tool calculates (EG_Balance ticked). |
| **Manual** | A marker whose number you set (EG_Balance unticked). |
| **Capacity** | The maximum number of occupants an exit can take. |
| **Overlay** | The color-coded arrows and labels drawn by Show Relationships. |
| **Halftone** | A view setting that grays out the model so annotations stand out. |
| **View template** | A saved set of view settings applied to a view. It can lock settings such as Display Model. |
| **Active view** | The view currently open and in focus in Revit. |
| **Ribbon / tab / panel** | The toolbar at the top of Revit. EgressTools has its own **tab**, divided into **panels** (Setup, Build, Balance, Check, Advanced). |
| **Status bar** | The text line at the bottom-left of the Revit window where tools show instructions. |
| **Options Bar** | The strip under the ribbon. The **Finish** button appears here when picking multiple elements. |
| **Output window** | The pyRevit pop-up where reports appear. Element IDs in it are clickable. |
| **Shared Parameters file** | A text file Revit uses to define parameters that can be shared between families and projects. |
| **pyRevit Reload** | pyRevit tab > Reload. Reloads all pyRevit tools after installing or updating them. |

---
