import ifcopenshell
import os

IFC_PATH = os.path.join(os.path.dirname(__file__), "A3", "model", "25-16-D-ARCH.ifc")
model = ifcopenshell.open(IFC_PATH)

# Check units
for unit in model.by_type("IfcUnitAssignment"):
    for u in unit.Units:
        print(f"Unit: {u}")
        if hasattr(u, 'UnitType'):
            print(f"  Type: {u.UnitType}")
        if hasattr(u, 'Name'):
            print(f"  Name: {u.Name}")
        if hasattr(u, 'Prefix'):
            print(f"  Prefix: {u.Prefix}")

# Check project scale
for proj in model.by_type("IfcProject"):
    print(f"\nProject: {proj.Name}")
    if hasattr(proj, 'RepresentationContexts'):
        for ctx in proj.RepresentationContexts:
            print(f"  Context: {ctx.is_a()}")
            if hasattr(ctx, 'CoordinateSpaceDimension'):
                print(f"    Dimension: {ctx.CoordinateSpaceDimension}")

# Let's also check dimensions of passing corridors using the same geometry method
print("\n" + "="*80)
print("Checking passing corridors for comparison...")
print("="*80)

import ifcopenshell.geom
import numpy as np

GEOM_SETTINGS = ifcopenshell.geom.settings()
GEOM_SETTINGS.set(GEOM_SETTINGS.USE_WORLD_COORDS, True)

def get_vertices(product):
    try:
        shape = ifcopenshell.geom.create_shape(GEOM_SETTINGS, product)
        verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
        return verts
    except Exception:
        return None

# One of the passing corridors
passing_gid = "3Vo8snhKX7fQarsO4DMUkE"  # Hallway:1133161 with width_mm: 1989.99

sp = model.by_guid(passing_gid)
if sp:
    name = getattr(sp, 'Name', 'Unknown')
    print(f"\nPassing corridor: {name}")
    verts = get_vertices(sp)
    if verts is not None:
        minv = verts.min(axis=0)
        maxv = verts.max(axis=0)
        dims = maxv - minv
        print(f"  Bbox: {minv} to {maxv}")
        print(f"  Dimensions (X, Y, Z): {dims}")
        width = min(dims[0], dims[1])
        length = max(dims[0], dims[1])
        print(f"  Width: {width:.2f}mm (should be ~1989.99mm)")
