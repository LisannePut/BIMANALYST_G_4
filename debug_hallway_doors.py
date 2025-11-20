#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/lisanneput/Desktop/2025-2026/Semester 1/BIM/BIMANALYST_G_4/A3')
import ifcopenshell
import math
from Assignment3 import get_element_centroid

model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")
spaces = list(model.by_type("IfcSpace"))

# Find a failing hallway
failing_hallway = None
for sp in spaces:
    sp_name = getattr(sp, 'Name', '')
    if sp_name == 'Hallway:1133176':  # One of the failing ones
        failing_hallway = sp
        break

if failing_hallway:
    sp_id = getattr(failing_hallway, 'GlobalId', 'unknown')
    cent = get_element_centroid(failing_hallway)
    
    print(f"Hallway: {getattr(failing_hallway, 'Name', 'unknown')} [{sp_id[:16]}...]")
    print(f"Centroid: {cent}")
    
    # Find all doors and their distances to this hallway
    doors = list(model.by_type("IfcDoor"))
    openings = list(model.by_type("IfcOpeningElement"))
    
    distances_to_doors = []
    for door in doors:
        door_id = getattr(door, 'GlobalId', 'unknown')
        door_name = getattr(door, 'Name', 'unknown')[:40]
        
        # Find opening for this door
        for rel in model.by_type("IfcRelFillsElement"):
            if rel.RelatedBuildingElement == door:
                opening = rel.RelatingOpeningElement
                op_cent = get_element_centroid(opening)
                if op_cent and cent:
                    dist = math.sqrt((op_cent[0] - cent[0])**2 + 
                                   (op_cent[1] - cent[1])**2 + 
                                   (op_cent[2] - cent[2])**2)
                    distances_to_doors.append((dist, door_name, door_id[:16]))
                break
    
    # Sort by distance
    distances_to_doors.sort()
    
    print(f"\nNearest doors/openings:")
    for i, (dist, door_name, door_id) in enumerate(distances_to_doors[:10]):
        print(f"  {i+1}. {dist:,.0f}mm - {door_name}... [{door_id}...]")

else:
    print("Hallway not found")
