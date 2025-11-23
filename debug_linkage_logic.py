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

def get_element_centroid(elem):
    try:
        verts = get_vertices(elem)
        if verts is not None and len(verts) > 0:
            verts = verts * 1000.0
            return verts.mean(axis=0)
    except Exception:
        pass
    return None

spaces = model.by_type('IfcSpace')

# Identify stair and hallway spaces
stair_spaces = set()
hallway_spaces = set()
for sp in spaces:
    name = (getattr(sp, 'Name', None) or '').lower()
    gid = getattr(sp, 'GlobalId', None) or str(id(sp))
    if 'stair' in name:
        stair_spaces.add(gid)
    if 'hallway' in name:
        hallway_spaces.add(gid)

print(f"Stair spaces: {len(stair_spaces)}")
print(f"Hallway spaces: {len(hallway_spaces)}")

# Test the door logic
for rel in model.by_type('IfcRelFillsElement'):
    opening = getattr(rel, 'RelatingOpeningElement', None)
    door = getattr(rel, 'RelatedBuildingElement', None)
    if not (opening and door and door.is_a('IfcDoor')):
        continue
    
    oc = get_element_centroid(opening)
    if oc is None:
        continue
    
    # Find spaces
    spaces_with_opening_info = []
    margin = 500
    
    for sp in spaces:
        sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
        sp_name = getattr(sp, 'Name', None) or ''
        verts = get_vertices(sp)
        if verts is not None and len(verts) > 0:
            verts = verts * 1000.0
            minv = verts.min(axis=0)
            maxv = verts.max(axis=0)
            
            if minv[0] - margin <= oc[0] <= maxv[0] + margin and \
               minv[1] - margin <= oc[1] <= maxv[1] + margin:
                spaces_with_opening_info.append((sp_gid, sp_name))
    
    hallway_gids = [sp_gid for sp_gid, sp_name in spaces_with_opening_info if 'hallway' in sp_name.lower()]
    stair_gids = [sp_gid for sp_gid, sp_name in spaces_with_opening_info if sp_gid in stair_spaces]
    
    if hallway_gids and stair_gids:
        door_name = getattr(door, 'Name', 'Door')
        print(f"\n✓ Door {door_name} connects:")
        for h in hallway_gids:
            for sp in spaces:
                if (getattr(sp, 'GlobalId', None) or str(id(sp))) == h:
                    print(f"    Hallway: {getattr(sp, 'Name', 'Unknown')}")
        for s in stair_gids:
            for sp in spaces:
                if (getattr(sp, 'GlobalId', None) or str(id(sp))) == s:
                    print(f"    Stair: {getattr(sp, 'Name', 'Unknown')}")
