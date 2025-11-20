#!/usr/bin/env python3
import ifcopenshell

model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")

# Check IfcRelConnectsElements
rel_connects = list(model.by_type("IfcRelConnectsElements"))
print(f"Total IfcRelConnectsElements: {len(rel_connects)}\n")

# Categorize what they connect
space_connections = 0
door_connections = 0
wall_connections = 0
element_types = {}

for rel in rel_connects:
    elem1 = getattr(rel, 'RelatedElement', None)
    elem2 = getattr(rel, 'RelatingElement', None)
    
    if elem1:
        t1 = elem1.is_a()
        element_types[t1] = element_types.get(t1, 0) + 1
        
        if elem1.is_a('IfcSpace') and elem2 and elem2.is_a('IfcSpace'):
            space_connections += 1
        elif (elem1.is_a('IfcDoor') or elem1.is_a('IfcSpace')) and (elem2 and (elem2.is_a('IfcDoor') or elem2.is_a('IfcSpace'))):
            door_connections += 1
        elif elem1.is_a('IfcWall'):
            wall_connections += 1

print(f"Space-to-Space connections: {space_connections}")
print(f"Door/Space connections: {door_connections}")
print(f"Wall connections: {wall_connections}")

print(f"\nElement types in relations:")
for etype, count in sorted(element_types.items()):
    print(f"  {etype}: {count}")

# Check specific space-to-space or space-to-door connections
print("\n--- Sample connections ---")
for i, rel in enumerate(rel_connects[:10]):
    elem1 = getattr(rel, 'RelatedElement', None)
    elem2 = getattr(rel, 'RelatingElement', None)
    
    if not elem1 or not elem2:
        continue
    
    e1_type = elem1.is_a()
    e2_type = elem2.is_a()
    e1_name = getattr(elem1, 'Name', '?')
    e2_name = getattr(elem2, 'Name', '?')
    
    print(f"  {i+1}. {e1_type}({e1_name}) <-> {e2_type}({e2_name})")
