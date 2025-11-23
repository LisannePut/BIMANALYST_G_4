import ifcopenshell
import ifcopenshell.geom
import numpy as np
import os

IFC_PATH = os.path.join(os.path.dirname(__file__), "A3", "model", "25-16-D-ARCH.ifc")
model = ifcopenshell.open(IFC_PATH)

GEOM_SETTINGS = ifcopenshell.geom.settings()
GEOM_SETTINGS.set(GEOM_SETTINGS.USE_WORLD_COORDS, True)

def get_vertices(product):
    try:
        shape = ifcopenshell.geom.create_shape(GEOM_SETTINGS, product)
        verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
        return verts
    except Exception:
        return None

spaces = list(model.by_type('IfcSpace'))
print(f"Total spaces: {len(spaces)}")

# Check which spaces extract geometry
space_geom_map = {}
for sp in spaces:
    sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
    sp_name = getattr(sp, 'Name', None) or ''
    verts = get_vertices(sp)
    if verts is not None and len(verts) > 0:
        space_geom_map[sp_gid] = sp_name
    else:
        print(f"❌ {sp_name} ({sp_gid}): NO GEOMETRY")

print(f"\nSpaces with geometry: {len(space_geom_map)}")

# Check stair spaces
stair_count = 0
for sp_gid, name in space_geom_map.items():
    if 'stair' in name.lower():
        stair_count += 1
        print(f"✓ Stair in map: {name}")

print(f"\nStairs in geometry map: {stair_count}")

# Count hallways
hallway_count = 0
for sp_gid, name in space_geom_map.items():
    if 'hallway' in name.lower():
        hallway_count += 1

print(f"Hallways in geometry map: {hallway_count}")
