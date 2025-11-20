#!/usr/bin/env python3
import ifcopenshell
import math

# Load model
model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")

# Count IfcRelFillsElement relations
rel_count = len(list(model.by_type("IfcRelFillsElement")))
print(f"Total IfcRelFillsElement relations: {rel_count}")

# Count IfcDoor elements
door_count = len(list(model.by_type("IfcDoor")))
print(f"Total IfcDoor elements: {door_count}")

# Check how many IfcRelFillsElement relations actually have a door
matched = 0
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
        
        if not element:
            not_door += 1
            continue
            
        if not element.is_a('IfcDoor'):
            not_door += 1
            continue
        
        door_global_id = getattr(element, 'GlobalId', None)
        if not door_global_id:
            no_global_id += 1
            continue
        
        matched += 1
    except Exception as e:
        print(f"Exception: {e}")
        continue

print(f"\nMatched door IfcRelFillsElement relations: {matched}")
print(f"Missing opening: {no_opening}")
print(f"Not a door (or missing): {not_door}")
print(f"No GlobalId: {no_global_id}")

# Check if any door is connected to an opening at all
doors_with_opening = set()
for rel in model.by_type("IfcRelFillsElement"):
    try:
        if rel.RelatedBuildingElement and rel.RelatedBuildingElement.is_a('IfcDoor'):
            doors_with_opening.add(rel.RelatedBuildingElement.GlobalId)
    except:
        pass

print(f"\nDoors connected to openings: {len(doors_with_opening)}")

# Sample a few doors and check if they're in IfcRelFillsElement
print("\n--- Sampling first 5 doors ---")
for i, door in enumerate(model.by_type("IfcDoor")):
    if i >= 5:
        break
    door_id = getattr(door, 'GlobalId', None)
    door_name = getattr(door, 'Name', 'unknown')
    is_in_rel = door_id in doors_with_opening
    print(f"Door {i+1}: {door_name} [{door_id}] - In IfcRelFillsElement: {is_in_rel}")
