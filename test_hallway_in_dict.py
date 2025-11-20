#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/lisanneput/Desktop/2025-2026/Semester 1/BIM/BIMANALYST_G_4/A3')
import ifcopenshell
import math
from Assignment3 import get_element_centroid

model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")
spaces = list(model.by_type("IfcSpace"))

# Build space centroids (copy from Assignment3.py)
space_centroids = {}
hallway_found = False
for sp in spaces:
    sp_id = getattr(sp, 'GlobalId', None) or str(id(sp))
    sp_name = getattr(sp, 'Name', '')
    cent = get_element_centroid(sp)
    if cent:
        space_centroids[sp_id] = cent
    
    # Track hallway
    if sp_name == 'Hallway:1133176':
        hallway_found = True
        hallway_id = sp_id
        if cent:
            print(f"Found Hallway in space_centroids: {sp_id}")
        else:
            print(f"Hallway found but NO CENTROID: {sp_id}")

print(f"\nTotal spaces with centroids: {len(space_centroids)} / {len(spaces)}")
print(f"Hallway in space_centroids: {'3Vo8snhKX7fQarsO4DMUkV' in space_centroids}")

# Now test a specific door's nearest 2 spaces
# Get the first door that should be near the hallway
for rel in list(model.by_type("IfcRelFillsElement"))[:50]:
    door = rel.RelatedBuildingElement
    opening = rel.RelatingOpeningElement
    
    if door and opening and door.is_a('IfcDoor'):
        door_id = getattr(door, 'GlobalId', None)
        opening_cent = get_element_centroid(opening)
        
        if opening_cent:
            # Find 2 nearest spaces
            distances = []
            for sp_id, cent in space_centroids.items():
                dist = math.sqrt((opening_cent[0] - cent[0])**2 + 
                               (opening_cent[1] - cent[1])**2 + 
                               (opening_cent[2] - cent[2])**2)
                distances.append((dist, sp_id))
            
            distances.sort()
            
            # Check if hallway is in top 5
            hallway_rank = None
            for rank, (dist, sp_id) in enumerate(distances):
                if sp_id == '3Vo8snhKX7fQarsO4DMUkV':
                    hallway_rank = rank
                    break
            
            if hallway_rank is not None and hallway_rank < 10:
                print(f"\nDoor {door_id[:16]}... opening at {opening_cent}")
                print(f"  Nearest 5 spaces:")
                for i, (dist, sp_id) in enumerate(distances[:5]):
                    sp = next((s for s in spaces if (getattr(s, 'GlobalId', None) or str(id(s))) == sp_id), None)
                    sp_name = getattr(sp, 'Name', '?')
                    marker = " <-- HALLWAY" if sp_id == '3Vo8snhKX7fQarsO4DMUkV' else ""
                    print(f"    {i+1}. {dist:,.0f}mm - {sp_name}{marker}")
                break
