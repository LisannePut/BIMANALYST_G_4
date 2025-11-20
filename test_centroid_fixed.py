#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/lisanneput/Desktop/2025-2026/Semester 1/BIM/BIMANALYST_G_4/A3')
from Assignment3 import get_element_centroid
import ifcopenshell
import math

# Load model
model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")

# Check spaces and their centroids
spaces = list(model.by_type("IfcSpace"))
print(f"Total spaces: {len(spaces)}")

space_centroids = {}
no_centroid = 0
for sp in spaces[:5]:
    cent = get_element_centroid(sp)
    sp_id = getattr(sp, 'GlobalId', None) or str(id(sp))
    sp_name = getattr(sp, 'Name', 'unknown')
    if cent:
        space_centroids[sp_id] = cent
        print(f"Space: {sp_name} [{sp_id[:8]}...] - Centroid: {cent}")
    else:
        no_centroid += 1
        print(f"Space: {sp_name} [{sp_id[:8]}...] - NO CENTROID")

print(f"\nSpaces with centroid (first 5): {len(space_centroids)}")

# Check opening centroids
print("\n--- Checking openings ---")
openings = list(model.by_type("IfcOpeningElement"))
print(f"Total openings: {len(openings)}")

opening_centroids = 0
for i, opening in enumerate(openings[:3]):
    cent = get_element_centroid(opening)
    op_id = getattr(opening, 'GlobalId', None)
    if cent:
        opening_centroids += 1
        print(f"Opening {i+1} [{op_id[:8]}...]: {cent}")
    else:
        print(f"Opening {i+1} [{op_id[:8]}...]: NO CENTROID")

print(f"\nOpening centroids available: {opening_centroids} (of first 3 checked)")

# Check a door-opening connection
print("\n--- Checking a door-opening connection ---")
for rel in list(model.by_type("IfcRelFillsElement"))[:1]:
    opening = rel.RelatingOpeningElement
    door = rel.RelatedBuildingElement
    
    door_name = getattr(door, 'Name', 'unknown')
    door_id = getattr(door, 'GlobalId', None)
    
    opening_cent = get_element_centroid(opening)
    
    print(f"Door: {door_name[:40]}... [{door_id[:8]}...]")
    print(f"Opening centroid: {opening_cent}")
    
    if opening_cent and space_centroids:
        # Find nearest spaces
        distances = []
        for sp_id, cent in space_centroids.items():
            dist = math.sqrt((opening_cent[0] - cent[0])**2 + 
                           (opening_cent[1] - cent[1])**2 + 
                           (opening_cent[2] - cent[2])**2)
            distances.append((dist, sp_id))
        
        distances.sort()
        print(f"Nearest 3 spaces:")
        for i, (dist, sp_id) in enumerate(distances[:3]):
            sp = next((s for s in spaces if (getattr(s, 'GlobalId', None) or str(id(s))) == sp_id), None)
            sp_name = getattr(sp, 'Name', 'unknown') if sp else 'unknown'
            print(f"  {i+1}. Distance {dist:.1f}mm - {sp_name} [{sp_id[:8]}...]")
