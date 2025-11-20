#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/lisanneput/Desktop/2025-2026/Semester 1/BIM/BIMANALYST_G_4/A3')
import ifcopenshell
from Assignment3 import build_space_bboxes, get_element_centroid

model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")
spaces = list(model.by_type("IfcSpace"))

# Build space bboxes
bboxes = build_space_bboxes(spaces)
print(f"Spaces with bboxes: {len(bboxes)} / {len(spaces)}")

# Check if hallway has a bbox
hallway_id = '3Vo8snhKX7fQarsO4DMUkV'
if hallway_id in bboxes:
    bbox = bboxes[hallway_id]
    print(f"\nHallway bbox: {bbox}")
    if bbox and len(bbox) >= 4:
        print(f"  X: {bbox[0]:.0f} to {bbox[2]:.0f}")
        print(f"  Y: {bbox[1]:.0f} to {bbox[3]:.0f}")
else:
    print(f"\nHallway NOT in bboxes dict")

# Get hallway centroid for comparison
hallway = next((s for s in spaces if getattr(s, 'GlobalId', None) == hallway_id), None)
if hallway:
    cent = get_element_centroid(hallway)
    print(f"Hallway centroid: {cent}")
    
    # Check if centroid is within its own bbox
    if hallway_id in bboxes and bboxes[hallway_id] and len(bboxes[hallway_id]) >= 4:
        bbox = bboxes[hallway_id]
        inside = (bbox[0] <= cent[0] <= bbox[2] and bbox[1] <= cent[1] <= bbox[3])
        print(f"Centroid inside hallway bbox: {inside}")

# Check sample opening - is it in any space's bbox?
openings = list(model.by_type("IfcOpeningElement"))[:3]
for op in openings:
    op_cent = get_element_centroid(op)
    if op_cent:
        print(f"\nOpening {getattr(op, 'GlobalId', '?')[:8]}... at {op_cent}")
        
        # Find which spaces contain this opening
        spaces_containing = []
        for sp_id, bbox in bboxes.items():
            if bbox and len(bbox) >= 4:
                xmin, ymin, xmax, ymax = bbox[0], bbox[1], bbox[2], bbox[3]
                if xmin <= op_cent[0] <= xmax and ymin <= op_cent[1] <= ymax:
                    sp = next((s for s in spaces if (getattr(s, 'GlobalId', None) or str(id(s))) == sp_id), None)
                    sp_name = getattr(sp, 'Name', '?') if sp else '?'
                    spaces_containing.append(sp_name)
        
        if spaces_containing:
            print(f"  Inside spaces: {spaces_containing}")
        else:
            print(f"  Inside spaces: NONE")
