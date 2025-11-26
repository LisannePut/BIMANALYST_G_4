# Assignment3.3.py - Script Structure Guide

## Overview
This script performs BR18 building code compliance checking for evacuation routes in IFC building models.

---

## 📋 SECTION 1: IMPORTS AND CONFIGURATION (Lines 1-40)

**Purpose:** Load required libraries and set up configuration constants

**Contents:**
- Import statements (ifcopenshell, numpy, etc.)
- File paths and model location
- BR18 compliance thresholds:
  - `DOOR_MIN = 800` mm
  - `STAIR_MIN = 1000` mm
  - `CORRIDOR_MIN = 1300` mm
- Geometry settings for IFC shape extraction

---

## 🔧 SECTION 2: UTILITY FUNCTIONS - CACHING AND UNIT CONVERSION (Lines 41-70)

**Purpose:** Provide helper functions for performance and unit handling

**Key Functions:**
- `_BBOX_CACHE = {}` - Cache dictionary for bounding boxes (performance optimization)
- `to_mm(v)` - Convert values to millimeters (handles meters/mm auto-detection)

**Why Important:**
- Avoids recalculating geometry for same elements
- Ensures consistent units across all calculations

---

## 📐 SECTION 3: GEOMETRY EXTRACTION FUNCTIONS (Lines 71-180)

**Purpose:** Extract 3D geometry and dimensions from IFC elements

**Key Functions:**
- `extract_dimensions_from_geometry(sp)` - Get corridor width/length from space vertices
- `get_vertices(product)` - Extract 3D vertex coordinates from any IFC element
- `centroid_from_extruded(item)` - Calculate center point from extruded solid geometry
- `get_element_centroid(elem)` - Get centroid using vertex averaging

**What It Does:**
- Converts IFC geometry to usable measurements
- Calculates bounding boxes for spatial analysis
- Extracts center points for proximity checks

---

## 🔍 SECTION 4: PROPERTY EXTRACTION FUNCTIONS (Lines 181-280)

**Purpose:** Search and extract property values from IFC entities

**Key Functions:**
- `get_numeric(entity, names)` - Extract numeric properties (width, height, etc.)
  - Searches: Direct attributes → Property sets → Quantity sets
  - Case-insensitive with partial matching

**Use Cases:**
- Finding door widths from properties
- Extracting stair dimensions
- Getting corridor measurements

---

## 🔗 SECTION 5: SPACE CONNECTIVITY AND LINKAGE ANALYSIS (Lines 281-530)

**Purpose:** Build connectivity graphs showing how spaces connect via doors

**Key Functions:**
- `build_space_bboxes(spaces)` - Calculate bounding boxes for all spaces
- `build_space_linkages(model, spaces)` - Create adjacency map of spaces via doors
  - Identifies hallways vs. stair spaces
  - Uses breadth-first search for transitive connections
  - Returns: which hallways link to stairs (directly or via other hallways)
- `build_full_door_space_map(model)` - Complete door-to-space connectivity map

**Why Important:**
BR18 requires corridors to connect to stairs (evacuation route requirement)

---

## ✅ SECTION 6: COMPLIANCE ANALYSIS FUNCTIONS - DOORS, STAIRS, CORRIDORS (Lines 531-633)

**Purpose:** Check individual elements against BR18 requirements

**Key Functions:**
- `analyze_door(door, door_map, opening_map)` 
  - Checks: width ≥ 800mm
  - Returns: pass/fail status + connected spaces
  
- `analyze_stair(flight)`
  - Checks: width ≥ 1000mm
  - Returns: pass/fail status + measurements

**BR18 Rules Applied:**
- ✓ Door minimum clear width: 800mm
- ✓ Stair minimum clear width: 1000mm

---

## 🏢 SECTION 7: STAIRCASE GROUPING AND ENCLOSURE ANALYSIS (Lines 634-842)

**Purpose:** Group stair flights and check if they're properly enclosed

**Key Functions:**
- `analyze_staircase_groups(model)` - Group flights by staircase ID
  - Parses names like "Assembled Stair:Stair:1282665 Run 1"
  - Groups all runs (1, 2, 3) belonging to same staircase
  
- `analyze_staircase_group_enclosure(model)` - Check if staircase group is enclosed
  - Uses proximity detection with wall bounding boxes
  - Checks 3 vertical sides (left, right, top)
  
- `identify_stair_spaces_geometry(model)` - Find stair spaces using geometry
  - Associates flights with containing spaces by centroid location

**Why Important:**
BR18 requires stair shafts to be enclosed (fire safety + structural)

---

## 📦 SECTION 8: BOUNDING BOX AND GEOMETRIC HELPER FUNCTIONS (Lines 843-882)

**Purpose:** Provide geometric calculation utilities

**Key Functions:**
- `_bbox2d_mm(entity)` - Calculate 2D bounding box in millimeters
  - Cached for performance
  - Used extensively for proximity checks
  
- `_bbox_intersect(a, b, margin)` - Check if two bounding boxes overlap
  - With optional margin for tolerance

**Use Cases:**
- Checking if door is inside space
- Detecting wall adjacency
- Computing enclosure coverage

---

## 🛡️ SECTION 9: STAIR FLIGHT ENCLOSURE CHECKS (4-WALL VERIFICATION) (Lines 883-1560)

**Purpose:** Verify each stair flight is surrounded by walls on all 4 sides

**Key Functions:**
- `analyze_stairflight_4wall_enclosure(model)` - Main 4-wall check
  - Builds side strips around each flight bbox
  - Checks for wall intersections on all sides
  - Returns: fully_enclosed status + missing sides
  
- `analyze_stair_flight_enclosure_proximity(model)` - Alternative proximity method
- `analyze_stair_space_enclosure(model)` - Space boundary-based check
- Additional helper functions for different enclosure strategies

**BR18 Rule:**
Stair flights must be enclosed by walls (prevents falls, fire containment)

---

## 🎯 SECTION 10: MAIN ANALYSIS FUNCTION (Lines 1561-1950)

**Purpose:** Orchestrate the entire compliance check workflow

**Main Process:**

### 10.1 Initialize and Load Model
```python
model = ifcopenshell.open(IFC_PATH)
all_spaces = model.by_type('IfcSpace')
```

### 10.2 Define Corridor Spaces
- Filter spaces by name tokens: 'hallway', 'corridor', 'passage', 'circulation'
- Extract dimensions using geometry
- Store in `analyses` dictionary

### 10.3 Build Space Connectivity
- Create door-space linkage map
- Determine which corridors connect to stairs
- Check corridor shape (elongated vs. compact)

### 10.4 Analyze All Elements
- Doors: width compliance
- Stairs: width compliance  
- Corridors: width + linkage compliance
- Stair flights: 4-wall enclosure

### 10.5 Generate Excel Report
**Structure:**
- Sheet: "IFC_Compliance_Report"
- Rows 1-6: Requirements section
- Row 7: Table header (bold, gray)
- Rows 8-11: Data (Doors, Corridors, Stairs width, Stair flight enclosure)

**Columns:**
- A: Category name
- B: Passing count
- C: Failing count
- D: Failing element IDs (vertical list)
- E: Reasons for failure (vertical list)

### 10.6 Output Results
- Creates timestamped Excel file: `analysis_summary_YYYYMMDD_HHMMSS.xlsx`
- Prints clickable terminal link (OSC 8 hyperlink protocol)

---

## 📊 Data Flow

```
IFC Model
    ↓
Load all spaces
    ↓
Filter corridors & stairs
    ↓
Extract geometry → Calculate dimensions
    ↓
Build door-space connectivity map
    ↓
Analyze compliance:
  • Doors (width ≥ 800mm)
  • Stairs (width ≥ 1000mm)  
  • Corridors (width ≥ 1300mm + links to stairs)
  • Stair flights (4-wall enclosure)
    ↓
Generate Excel report with timestamp
    ↓
Output clickable file link
```

---

## 🔑 Key BR18 Requirements

| Category | Requirement | Threshold | Section |
|----------|-------------|-----------|---------|
| **Doors** | Clear opening width | ≥ 800mm | Section 6 |
| **Stairs** | Clear flight width | ≥ 1000mm | Section 6 |
| **Corridors** | Clear width | ≥ 1300mm | Section 6 |
| **Corridors** | Links to stairs | Must connect | Section 5 |
| **Stair Flights** | Wall enclosure | 4 sides minimum | Section 9 |

---

## 🚀 Performance Optimizations

1. **Bounding Box Cache** (`_BBOX_CACHE`)
   - Avoids recalculating geometry
   - Speeds up repeated proximity checks

2. **Corridor-Only Analysis**
   - Only analyzes corridor spaces (not all rooms)
   - Reduces runtime significantly

3. **Geometry-Based Detection**
   - Uses vertex calculations instead of name parsing where possible
   - More reliable and faster

4. **Storey-Based Wall Filtering**
   - Limits wall searches to same building storey
   - Reduces unnecessary comparisons

---

## 📝 Output Format

### Console Output:
```
Results of the evacuation check: /path/to/analysis_summary_20251126_140020.xlsx
Click: Open Excel (.xlsx)
```
(Both lines are clickable hyperlinks in VS Code terminal)

### Excel Output:
- **File naming:** `analysis_summary_YYYYMMDD_HHMMSS.xlsx`
- **Location:** A3 folder (same as script)
- **Format:** Single sheet with Requirements + 5-column table
- **Features:** Text wrapping, vertical lists, proper formatting

---

## 🛠️ Troubleshooting

**If geometry extraction fails:**
- Function returns `None` or `(0, 0)` to avoid crashes
- Fallback to property-based measurements

**If spaces don't link to stairs:**
- Check door placement in IFC model
- Verify space naming conventions
- Review door-space connectivity in output

**If enclosure checks fail:**
- Adjust `side_margin` and `wall_search_expand` parameters
- Check wall modeling (gaps, missing walls)
- Review bounding box calculations

---

## 📚 Dependencies

- `ifcopenshell` - IFC file parsing
- `numpy` - Numerical calculations
- `openpyxl` - Excel file generation
- Python 3.7+ required

---

**Last Updated:** November 26, 2025  
**Script Version:** Assignment3.3.py (Optimized corridor analysis with comments)
