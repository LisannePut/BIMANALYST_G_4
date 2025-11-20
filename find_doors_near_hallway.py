#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/lisanneput/Desktop/2025-2026/Semester 1/BIM/BIMANALYST_G_4/A3')
import ifcopenshell
import math
from Assignment3 import get_element_centroid

model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")
spaces = list(model.by_type("IfcSpace"))

# Build space centroids
space_centroids = {}
for sp in spaces:
    sp_id = getattr(sp, 'GlobalId', None) or str(id(sp))
    cent = get_element_centroid(sp)
    if cent:
        space_centroids[sp_id] = cent

print(f"Total spaces with centroids: {len(space_centroids)} / {len(spaces)}")

# Scan ALL doors and check which ones have hallway in top 5 nearest
hallway_id = '3Vo8snhKX7fQarsO4DMUkV'
doors_with_hallway_nearby = 0

for rel in model.by_type("IfcRelFillsElement"):
    door = rel.RelatedBuildingElement
    opening = rel.RelatingOpeningElement
    
    if not (door and opening and door.is_a('IfcDoor')):
        continue
    
    opening_cent = get_element_centroid(opening)
    if not opening_cent:
        continue
    
    # Find nearest spaces
    distances = []
    for sp_id, cent in space_centroids.items():
        dist = math.sqrt((opening_cent[0] - cent[0])**2 + 
                       (opening_cent[1] - cent[1])**2 + 
                       (opening_cent[2] - cent[2])**2)
        distances.append((dist, sp_id))
    
    distances.sort()
    
    # Check if hallway is in top 5
    for rank, (dist, sp_id) in enumerate(distances[:5]):
        if sp_id == hallway_id:
            doors_with_hallway_nearby += 1
            if doors_with_hallway_nearby <= 3:
                print(f"\nDoor with hallway nearby:")
                for i, (d, sid) in enumerate(distances[:5]):
                    sp = next((s for s in spaces if (getattr(s, 'GlobalId', None) or str(id(s))) == sid), None)
                    sp_name = getattr(sp, 'Name', '?')[:30]
                    marker = " <-- HALLWAY" if sid == hallway_id else ""
                    print(f"  {i+1}. {d:,.0f}mm - {sp_name}{marker}")
            break

print(f"\nDoors with hallway in top 5 nearest spaces: {doors_with_hallway_nearby}")
