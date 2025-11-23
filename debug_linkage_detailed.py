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

spaces = list(model.by_type('IfcSpace'))

# Build space geometry map
space_geom_map = {}
for sp in spaces:
    sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
    verts = get_vertices(sp)
    if verts is not None and len(verts) > 0:
        verts = verts * 1000.0
        minv = verts.min(axis=0)
        maxv = verts.max(axis=0)
        space_geom_map[sp_gid] = (minv, maxv, getattr(sp, 'Name', None) or '')

# Identify stair GIDs
stair_gids = set()
for sp_gid in space_geom_map:
    for sp in spaces:
        if (getattr(sp, 'GlobalId', None) or str(id(sp))) == sp_gid:
            name = (getattr(sp, 'Name', None) or '').lower()
            if 'stair' in name:
                stair_gids.add(sp_gid)
            break

print(f"Stair GIDs identified: {len(stair_gids)}")
for gid in stair_gids:
    name = space_geom_map[gid][2]
    print(f"  - {name}")

# For each space, track if it connects to stairs
space_linked_to_stairs = {}
margin = 500

# Trace door connections
door_count = 0
connected_hallways = set()

for rel in model.by_type('IfcRelFillsElement'):
    opening = getattr(rel, 'RelatingOpeningElement', None)
    door = getattr(rel, 'RelatedBuildingElement', None)
    if not (opening and door and door.is_a('IfcDoor')):
        continue
    
    door_count += 1
    oc = get_element_centroid(opening)
    if oc is None:
        continue
    
    # Find all spaces that contain this opening
    spaces_with_opening = []
    for sp_gid, (minv, maxv, name) in space_geom_map.items():
        if minv[0] - margin <= oc[0] <= maxv[0] + margin and \
           minv[1] - margin <= oc[1] <= maxv[1] + margin:
            spaces_with_opening.append((sp_gid, name))
    
    # Check if hallway and stair are both in this door group
    hallway_gids = [sp_gid for sp_gid, name in spaces_with_opening if 'hallway' in name.lower()]
    stair_gids_in_group = [sp_gid for sp_gid, name in spaces_with_opening if sp_gid in stair_gids]
    
    # If both hallway and stair exist in this group, link them
    if hallway_gids and stair_gids_in_group:
        door_name = getattr(door, 'Name', 'Door')
        print(f"\n✓ Door connects:")
        for h_gid in hallway_gids:
            space_linked_to_stairs[h_gid] = True
            connected_hallways.add(h_gid)
            for sp in spaces:
                if (getattr(sp, 'GlobalId', None) or str(id(sp))) == h_gid:
                    print(f"    {getattr(sp, 'Name', 'Unknown')}")
                    break
        for s_gid in stair_gids_in_group:
            for sp in spaces:
                if (getattr(sp, 'GlobalId', None) or str(id(sp))) == s_gid:
                    print(f"    {getattr(sp, 'Name', 'Unknown')}")
                    break

print(f"\nTotal doors processed: {door_count}")
print(f"Hallways connected to stairs: {len(connected_hallways)}")
for h_gid in sorted(connected_hallways):
    name = space_geom_map[h_gid][2]
    print(f"  - {name}")
