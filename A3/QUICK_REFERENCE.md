# Assignment3.3.py - Quick Reference Card

## 🗂️ Script Organization (10 Main Sections)

```
┌─────────────────────────────────────────────────────────────────┐
│  SECTION 1: IMPORTS AND CONFIGURATION (Lines 1-50)              │
│  • Import libraries (ifcopenshell, numpy, etc.)                 │
│  • Set BR18 thresholds (DOOR_MIN, STAIR_MIN, CORRIDOR_MIN)     │
│  • Configure geometry settings                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SECTION 2: UTILITY FUNCTIONS (Lines 51-90)                     │
│  • _BBOX_CACHE = {} ............... Performance cache           │
│  • to_mm(v) ....................... Unit conversion (m→mm)      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SECTION 3: GEOMETRY EXTRACTION (Lines 91-280)                  │
│  • extract_dimensions_from_geometry(sp) ... Get corridor size   │
│  • get_vertices(product) .................. Extract 3D points   │
│  • get_element_centroid(elem) ............. Calculate center    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SECTION 4: PROPERTY EXTRACTION (Lines 281-400)                 │
│  • get_numeric(entity, names) ............ Find width/height    │
│    - Searches: Attributes → Properties → Quantities             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SECTION 5: SPACE CONNECTIVITY (Lines 401-540)                  │
│  • build_space_linkages(model, spaces) ... Corridor→Stair map   │
│  • build_full_door_space_map(model) ...... Door connections     │
│    - Uses BFS to find transitive connections                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SECTION 6: COMPLIANCE CHECKS (Lines 541-640)                   │
│  • analyze_door(door, ...) ............... Width ≥ 800mm?       │
│  • analyze_stair(flight) ................. Width ≥ 1000mm?      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SECTION 7: STAIRCASE GROUPING (Lines 641-850)                  │
│  • analyze_staircase_groups(model) ....... Group by ID          │
│  • analyze_staircase_group_enclosure(model) Proximity check     │
│  • identify_stair_spaces_geometry(model) . Find stair spaces    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SECTION 8: GEOMETRIC HELPERS (Lines 851-890)                   │
│  • _bbox2d_mm(entity) .................... 2D bounding box      │
│  • _bbox_intersect(a, b, margin) ......... Overlap check        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SECTION 9: ENCLOSURE VERIFICATION (Lines 891-1570)             │
│  • analyze_stairflight_4wall_enclosure(model) 4-wall check      │
│  • analyze_stair_flight_enclosure_proximity(model) Alternative  │
│    - Checks if flights surrounded by walls on all sides         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SECTION 10: MAIN ANALYSIS (Lines 1571-1953)                    │
│  • main() ................................. Master controller     │
│    1. Load IFC model                                            │
│    2. Define corridors (filter by name)                         │
│    3. Extract dimensions (geometry)                             │
│    4. Build connectivity (doors→spaces)                         │
│    5. Analyze all elements (doors/stairs/corridors/flights)     │
│    6. Generate timestamped Excel report                         │
│    7. Output clickable file link                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Functions by Purpose

### Finding Dimensions
```python
extract_dimensions_from_geometry(sp)  # Get width/length from space
get_numeric(entity, names)            # Extract properties (width, etc.)
get_vertices(product)                 # Get 3D geometry points
```

### Checking Connectivity
```python
build_space_linkages(model, spaces)   # Which corridors link to stairs?
build_full_door_space_map(model)      # Complete door-space connectivity
```

### Compliance Checks
```python
analyze_door(door, ...)               # Door width ≥ 800mm?
analyze_stair(flight)                 # Stair width ≥ 1000mm?
analyze_stairflight_4wall_enclosure() # Flight enclosed by 4 walls?
```

### Geometric Calculations
```python
_bbox2d_mm(entity)                    # Calculate 2D bounding box (cached)
_bbox_intersect(a, b, margin)         # Check if boxes overlap
get_element_centroid(elem)            # Find center point
```

---

## 📐 BR18 Thresholds

| Element | Requirement | Value |
|---------|-------------|-------|
| Doors | Minimum width | **800 mm** |
| Stairs | Minimum width | **1000 mm** |
| Corridors | Minimum width | **1300 mm** |
| Corridors | Must link to stairs | **Required** |
| Stair Flights | Wall enclosure | **4 sides** |

---

## 🔄 Data Flow Diagram

```
┌──────────────┐
│  IFC Model   │
└──────┬───────┘
       │
       ↓
┌──────────────────────────────────┐
│  Load & Filter Spaces            │
│  • Corridors (by name tokens)    │
│  • Stairs (name contains 'stair')│
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│  Extract Geometry & Dimensions   │
│  • Width/Length from vertices    │
│  • Bounding boxes (cached)       │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│  Build Connectivity Graph        │
│  • Door-Space mapping            │
│  • Corridor-Stair linkage (BFS)  │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│  Analyze All Elements            │
│  ├─ Doors: width check           │
│  ├─ Stairs: width check          │
│  ├─ Corridors: width + linkage   │
│  └─ Flights: 4-wall enclosure    │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│  Generate Excel Report           │
│  • Timestamped filename          │
│  • Requirements + 5-column table │
│  • Vertical lists of failures    │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│  Output Clickable Link           │
│  analysis_summary_YYYYMMDD.xlsx  │
└──────────────────────────────────┘
```

---

## 🚀 Performance Features

1. **_BBOX_CACHE** - Stores calculated bounding boxes to avoid recalculation
2. **Corridor-only analysis** - Only analyzes hallways (not all rooms)
3. **Storey filtering** - Limits wall searches to same building level
4. **Geometry caching** - Reuses vertex calculations

---

## 📂 File Outputs

**Excel File:**
- **Name:** `analysis_summary_YYYYMMDD_HHMMSS.xlsx`
- **Location:** `A3/` folder (same directory as script)
- **Format:** Single sheet "IFC_Compliance_Report"
  - Rows 1-6: Requirements section
  - Row 7: Headers (bold, gray)
  - Rows 8-11: Data (Doors, Corridors, Stairs, Flights)

**Console Output:**
```
Results of the evacuation check: /path/to/file.xlsx
Click: Open Excel (.xlsx)
```
*(Both lines are clickable in VS Code terminal)*

---

## 🔍 Quick Troubleshooting

| Problem | Check | Solution |
|---------|-------|----------|
| No dimensions found | Geometry extraction failed | Verify IFC model geometry |
| Corridor doesn't link to stairs | Door placement | Check door-space relationships |
| Enclosure check fails | Missing walls | Review wall modeling |
| Script runs slow | Large model | Normal (processes all geometry) |

---

## 💡 Tips for Understanding the Code

1. **Start at main()** (Section 10) - Shows overall workflow
2. **Follow the data** - Trace how IFC → Geometry → Analysis → Report
3. **Check section headers** - Jump to relevant code sections quickly
4. **Read docstrings** - Each function explains its purpose
5. **Look for comments** - Key decisions and logic explained inline

---

**Quick Navigation:**
- Import & Config → Line 1
- Utilities → Line 51
- Geometry → Line 91
- Properties → Line 281
- Connectivity → Line 401
- Compliance → Line 541
- Grouping → Line 641
- Helpers → Line 851
- Enclosure → Line 891
- Main → Line 1571

---

**Created:** November 26, 2025  
**For:** BIM Assignment 3.3 - BR18 Compliance Checker
