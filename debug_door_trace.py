import ifcopenshell
import ifcopenshell.geom
import numpy as np
import os
import math

IFC_PATH = os.path.join(os.path.dirname(__file__), "A3", "model", "25-16-D-ARCH.ifc")
model = ifcopenshell.open(IFC_PATH)

GEOM_SETTINGS = ifcopenshell.geom.settings()
GEOM_SETTINGS.set(GEOM_SETTINGS.USE_WORLD_COORDS, True)

def to_mm(v):
    try:
        f = float(v)
    except Exception:
        return None
    return f if f > 100 else f * 1000.0

def get_vertices(product):
    """Extract vertices from IFC product using world coordinates."""
    try:
        shape = ifcopenshell.geom.create_shape(GEOM_SETTINGS, product)
        verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
        return verts
    except Exception:
        return None

def get_element_centroid(elem):
    """Get centroid from element's geometry."""
    try:
        verts = get_vertices(elem)
        if verts is not None and len(verts) > 0:
            verts = verts * 1000.0  # Convert to mm
            return verts.mean(axis=0)
    except Exception:
        pass
    return None

# Get hallways and stairs
hallways = {}
for sp in model.by_type('IfcSpace'):
    name = (getattr(sp, 'Name', None) or '').lower()
    if 'hallway' in name:
        gid = getattr(sp, 'GlobalId', None)
        hallways[gid] = getattr(sp, 'Name', 'Unknown')

stairs = {}
for sp in model.by_type('IfcSpace'):
    name = (getattr(sp, 'Name', None) or '').lower()
    if 'stair' in name:
        gid = getattr(sp, 'GlobalId', None)
        stairs[gid] = getattr(sp, 'Name', 'Unknown')

print(f"Hallways: {len(hallways)}")
print(f"Stair spaces: {len(stairs)}")

# Now manually trace door relations
print("\n" + "="*80)
print("TRACING DOOR-TO-SPACE CONNECTIONS")
print("="*80)

hallway_stair_connections = {}

for rel in model.by_type('IfcRelFillsElement'):
    opening = getattr(rel, 'RelatingOpeningElement', None)
    door = getattr(rel, 'RelatedBuildingElement', None)
    if not (opening and door and door.is_a('IfcDoor')):
        continue
    
    door_name = getattr(door, 'Name', 'Door')
    door_gid = getattr(door, 'GlobalId', None)
    
    # Get opening centroid
    oc = get_element_centroid(opening)
    if oc is None:
        continue
    
    print(f"\nDoor: {door_name} ({door_gid})")
    print(f"  Opening centroid: ({oc[0]:.1f}, {oc[1]:.1f}, {oc[2]:.1f}) mm")
    
    # Find which spaces this opening is in
    spaces_with_opening = []
    for sp in model.by_type('IfcSpace'):
        sp_gid = getattr(sp, 'GlobalId', None)
        sp_name = getattr(sp, 'Name', 'Unknown')
        
        # Get space bbox
        verts = get_vertices(sp)
        if verts is not None and len(verts) > 0:
            verts = verts * 1000.0
            minv = verts.min(axis=0)
            maxv = verts.max(axis=0)
            
            # Check if opening is in space (with margin)
            margin = 500
            if minv[0] - margin <= oc[0] <= maxv[0] + margin and \
               minv[1] - margin <= oc[1] <= maxv[1] + margin:
                spaces_with_opening.append((sp_gid, sp_name, 'hallway' if sp_gid in hallways else ('stair' if sp_gid in stairs else 'other')))
                print(f"    In space: {sp_name} ({sp_gid}) - TYPE: {'hallway' if sp_gid in hallways else ('stair' if sp_gid in stairs else 'other')}")
    
    if len(spaces_with_opening) >= 2:
        # Check if one is hallway and other is stair
        types = [t[2] for t in spaces_with_opening]
        if 'hallway' in types and 'stair' in types:
            for gid, name, typ in spaces_with_opening:
                if typ == 'hallway':
                    hallway_stair_connections[gid] = True
                    print(f"  ✓ HALLWAY {name} CONNECTED TO STAIR!")

print("\n" + "="*80)
print("SUMMARY: Hallways connected to stairs")
print("="*80)
for h_gid, h_name in hallways.items():
    if h_gid in hallway_stair_connections:
        print(f"✓ {h_name} ({h_gid})")
    else:
        print(f"✗ {h_name} ({h_gid})")

print(f"\nTotal hallways linked to stairs: {len(hallway_stair_connections)}/{len(hallways)}")
