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

print(f"Spaces with centroids: {len(space_centroids)} / {len(spaces)}")

# Create a map of door GlobalId -> door object for lookup
door_by_id = {}
for door in model.by_type("IfcDoor"):
    door_id = getattr(door, 'GlobalId', None)
    if door_id:
        door_by_id[door_id] = door

print(f"Doors by ID map: {len(door_by_id)}")

# Collect all doors and their openings via IfcRelFillsElement
door_to_spaces = {}
matched_rels = 0
no_opening = 0
not_door = 0
no_global_id = 0

for rel in model.by_type("IfcRelFillsElement"):
    try:
        opening = rel.RelatingOpeningElement
        element = rel.RelatedBuildingElement
        
        if not opening:
            no_opening += 1
            continue
        
        if not element or not element.is_a('IfcDoor'):
            not_door += 1
            continue
        
        door_global_id = getattr(element, 'GlobalId', None)
        if not door_global_id:
            no_global_id += 1
            continue

        # Get opening centroid
        opening_cent = get_element_centroid(opening)
        if not opening_cent:
            print(f"  No centroid for opening")
            continue

        # Find 2 nearest spaces to this opening
        distances = []
        for sp_id, cent in space_centroids.items():
            dist = math.sqrt((opening_cent[0] - cent[0])**2 + 
                           (opening_cent[1] - cent[1])**2 + 
                           (opening_cent[2] - cent[2])**2)
            distances.append((dist, sp_id))

        distances.sort()
        spaces_touching = set()
        # Take the 2 closest spaces (typical door connects 2 rooms)
        for dist, sp_id in distances[:2]:
            spaces_touching.add(sp_id)

        if spaces_touching:
            door_to_spaces[door_global_id] = spaces_touching
            matched_rels += 1
            if matched_rels <= 3:
                print(f"Matched door relation {matched_rels}: {door_global_id[:8]}... -> {len(spaces_touching)} spaces")
    except Exception as e:
        print(f"Exception: {e}")
        continue

print(f"\nMatched door relations: {matched_rels}")
print(f"No opening: {no_opening}")
print(f"Not a door: {not_door}")
print(f"No GlobalId: {no_global_id}")
print(f"Total door_to_spaces entries: {len(door_to_spaces)}")

# Build space adjacency from door connections
space_linked = {}
for door_id, sset in door_to_spaces.items():
    s_list = list(sset)
    for s in s_list:
        others = set(s_list) - {s}
        if others:
            space_linked.setdefault(s, set()).update(others)

print(f"\nSpaces with links: {len(space_linked)}")
for sp_id, linked_sps in list(space_linked.items())[:3]:
    sp = next((s for s in spaces if (getattr(s, 'GlobalId', None) or str(id(s))) == sp_id), None)
    sp_name = getattr(sp, 'Name', 'unknown') if sp else 'unknown'
    print(f"  {sp_name} [{sp_id[:8]}...] -> {len(linked_sps)} other rooms")
