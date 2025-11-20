#!/usr/bin/env python3
import ifcopenshell

model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")

# Check if there are any IfcRelSpaceBoundary relations
rel_space_boundary = list(model.by_type("IfcRelSpaceBoundary"))
print(f"IfcRelSpaceBoundary relations: {len(rel_space_boundary)}")

# Check if there are IfcRelConnectsPathElements or other connectivity relations
rel_connects_path = list(model.by_type("IfcRelConnectsPathElements"))
print(f"IfcRelConnectsPathElements: {len(rel_connects_path)}")

rel_connects_elements = list(model.by_type("IfcRelConnectsElements"))
print(f"IfcRelConnectsElements: {len(rel_connects_elements)}")

# Maybe the way to check adjacency is by looking at walls/doors that separate rooms
# Let's check if we can use IfcWall to find adjacent spaces
walls = list(model.by_type("IfcWall"))
print(f"\nIfcWalls: {len(walls)}")

# Check if walls have space boundary info
if walls:
    wall = walls[0]
    print(f"  Sample wall: {getattr(wall, 'Name', 'unknown')}")
    if hasattr(wall, 'BoundedBy'):
        print(f"    Has BoundedBy: {wall.BoundedBy}")

# Check if spaces have any boundary information
spaces = list(model.by_type("IfcSpace"))
print(f"\nSpaces: {len(spaces)}")
if spaces:
    sp = spaces[0]
    print(f"  Sample space: {getattr(sp, 'Name', 'unknown')}")
    if hasattr(sp, 'BoundedBy'):
        print(f"    BoundedBy: {sp.BoundedBy}")
    if hasattr(sp, 'HasOpenings'):
        print(f"    HasOpenings: {sp.HasOpenings}")

# Check if doors relate spaces directly
print("\n--- Door-space relationships ---")
doors = list(model.by_type("IfcDoor"))[:2]
for door in doors:
    door_name = getattr(door, 'Name', 'unknown')
    print(f"Door: {door_name}")
    
    # Check if door has any relations
    if hasattr(door, 'HasOpenings'):
        openings = door.HasOpenings
        print(f"  Openings related: {len(openings) if openings else 0}")
    
    # Check via IfcRelConnectsPortToElement
    rel_connects_port = list(model.by_type("IfcRelConnectsPortToElement"))
    for rel in rel_connects_port[:1]:
        print(f"  RelConnectsPortToElement found")

# Look for space-to-space adjacency via different mechanism
print("\n--- Looking for space containers ---")
for sp in spaces[:3]:
    sp_name = getattr(sp, 'Name', 'unknown')
    sp_id = getattr(sp, 'GlobalId', 'unknown')
    
    # Check parent/container
    if hasattr(sp, 'ContainedInStructure'):
        container = sp.ContainedInStructure
        if container:
            print(f"Space {sp_name} contained in: {container}")
    
    # Check if there's any group or zone
    if hasattr(sp, 'Decomposes'):
        decomp = sp.Decomposes
        if decomp:
            print(f"Space {sp_name} decomposes: {decomp}")
