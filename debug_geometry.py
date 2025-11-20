#!/usr/bin/env python3
import ifcopenshell

model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")

# Check a sample space's geometry
spaces = list(model.by_type("IfcSpace"))[:3]

for sp in spaces:
    print(f"\nSpace: {getattr(sp, 'Name', 'unknown')}")
    if sp.Representation:
        for rep in sp.Representation.Representations:
            print(f"  Representation: {rep.RepresentationType}")
            for i, item in enumerate(getattr(rep, 'Items', [])):
                print(f"    Item {i}: {item.is_a()}")
                # Try to get more info
                if hasattr(item, 'SweptArea'):
                    print(f"      SweptArea: {item.SweptArea}")
                if hasattr(item, 'Position'):
                    print(f"      Position: {item.Position}")
                if hasattr(item, 'Axis'):
                    print(f"      Axis: {item.Axis}")
                if hasattr(item, 'SurfaceStyle'):
                    print(f"      SurfaceStyle: {item.SurfaceStyle}")
                # Check for vertices/points
                if hasattr(item, 'Vertices'):
                    print(f"      Vertices: {len(item.Vertices)} vertices")
                if hasattr(item, 'Points'):
                    print(f"      Points: {len(item.Points)} points")

# Check a sample opening's geometry
print("\n\n--- OPENING GEOMETRY ---")
openings = list(model.by_type("IfcOpeningElement"))[:1]

for op in openings:
    print(f"\nOpening: {getattr(op, 'GlobalId', 'unknown')}")
    if op.Representation:
        for rep in op.Representation.Representations:
            print(f"  Representation: {rep.RepresentationType}")
            for i, item in enumerate(getattr(rep, 'Items', [])):
                print(f"    Item {i}: {item.is_a()}")
                if hasattr(item, 'Position'):
                    pos = item.Position
                    if pos and hasattr(pos, 'Location'):
                        loc = pos.Location
                        if hasattr(loc, 'Coordinates'):
                            print(f"      Location Coords: {loc.Coordinates}")

# Check if spaces might use CSG or other representations
print("\n\n--- Checking all representation types in model ---")
all_rep_types = set()
for sp in list(model.by_type("IfcSpace")):
    if sp.Representation:
        for rep in sp.Representation.Representations:
            for item in getattr(rep, 'Items', []):
                all_rep_types.add(item.is_a())

print(f"Representation item types in spaces: {sorted(all_rep_types)}")
