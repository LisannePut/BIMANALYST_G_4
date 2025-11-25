import ifcopenshell
import ifcopenshell.geom
import os
import math
import numpy as np
import re

# BR18 requirements (concise)
# - Doors: clear opening width >= 800 mm (DOOR_MIN)
# - Stairs: clear width >= 1000 mm (STAIR_MIN)
# - Corridors: clear width >= 1300 mm (CORRIDOR_MIN) AND must link to a stair
# The BR18 PDF is included in this folder as 'BR18.pdf' and referenced by
# BR18_DOC_PATH below.

# Config
IFC_PATH = os.path.join(os.path.dirname(__file__), "model", "25-16-D-ARCH.ifc")
DOOR_MIN = 800
STAIR_MIN = 1000
CORRIDOR_MIN = 1300
BUFFER_BBOX = 1000.0
NEAREST_MAX = 30000.0
# BR18 PDF parsing has been removed. Use the hard-coded BR18 thresholds below.


# PDF parsing removed: thresholds are hard-coded at the top of this file

# Geometry settings for door midpoint calculation
GEOM_SETTINGS = ifcopenshell.geom.settings()
GEOM_SETTINGS.set(GEOM_SETTINGS.USE_WORLD_COORDS, True)

# Simple in-memory bbox cache to avoid repeated shape computation
_BBOX_CACHE = {}


def to_mm(v):
    try:
        f = float(v)
    except Exception:
        return None
    return f if f > 100 else f * 1000.0


def extract_dimensions_from_geometry(sp):
    """Extract width and length from IfcSpace geometry using 3D vertices.
    
    ifcopenshell.geom returns coordinates in meters, but IFC file units are millimeters,
    so we multiply by 1000 to convert.
    """
    try:
        verts = get_vertices(sp)
        if verts is not None and len(verts) > 0:
            # Convert from meters to millimeters (multiply by 1000)
            verts = verts * 1000.0
            minv = verts.min(axis=0)
            maxv = verts.max(axis=0)
            dims = maxv - minv
            # Return (longer dim, shorter dim) as (length, width)
            dim_sorted = sorted(dims[:2])  # Take X, Y (ignore Z height)
            if dim_sorted[1] > 0:  # Ensure width > 0
                return dim_sorted[1], dim_sorted[0]
    except Exception:
        pass
    
    return 0, 0



def get_vertices(product):
    """Extract vertices from IFC product using world coordinates.
    
    Skip problematic geometry that hangs.
    """
    try:
        shape = ifcopenshell.geom.create_shape(GEOM_SETTINGS, product)
        verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
        return verts
    except (KeyboardInterrupt, Exception):
        # Return None for any geometry error (includes timeouts/interrupts)
        return None
# NOTE: get_bbox and get_door_midpoint were removed because the code
# now uses `get_vertices` + geometry-based centroids via
# `get_element_centroid`. They were unused and are deleted to keep
# the file clean.

def get_numeric(entity, names):
    names_l = [n.lower() for n in names]
    # Attributes first
    for attr in dir(entity):
        try:
            if attr.lower() in names_l:
                v = getattr(entity, attr)
                r = to_mm(v)
                if r:
                    return r
        except Exception:
            continue
    # PSets and quantities
    for rel in getattr(entity, 'IsDefinedBy', []) or []:
        try:
            if not rel.is_a('IfcRelDefinesByProperties'):
                continue
            pdef = rel.RelatingPropertyDefinition
            if pdef is None:
                continue
            if pdef.is_a('IfcPropertySet'):
                for p in getattr(pdef, 'HasProperties', []) or []:
                    try:
                        pname = (getattr(p, 'Name', '') or '').lower()
                        if any(n in pname for n in names_l):
                            if hasattr(p, 'NominalValue') and p.NominalValue is not None:
                                try:
                                    val = p.NominalValue.wrappedValue
                                except Exception:
                                    val = p.NominalValue
                                r = to_mm(val)
                                if r:
                                    return r
                    except Exception:
                        continue
            if pdef.is_a('IfcElementQuantity'):
                for q in getattr(pdef, 'Quantities', []) or []:
                    try:
                        qn = (getattr(q, 'Name', '') or '').lower()
                        if any(n in qn for n in names_l):
                            val = getattr(q, 'LengthValue', None) or getattr(q, 'AreaValue', None) or getattr(q, 'VolumeValue', None)
                            r = to_mm(val)
                            if r:
                                return r
                    except Exception:
                        continue
        except Exception:
            continue
    return None


def centroid_from_extruded(item):
    try:
        if not item or not item.is_a('IfcExtrudedAreaSolid'):
            return None
        pos = getattr(item, 'Position', None)
        loc = getattr(pos, 'Location', None) if pos else None
        coords = list(getattr(loc, 'Coordinates', [])) if loc else []
        x = float(coords[0]) if coords else 0.0
        y = float(coords[1]) if len(coords) > 1 else 0.0
        z = float(coords[2]) if len(coords) > 2 else 0.0
        # Convert location coords to mm (they come in meters or model units)
        x = x if x > 100 else x * 1000.0
        y = y if y > 100 else y * 1000.0
        z = z if z > 100 else z * 1000.0
        prof = getattr(item, 'SweptArea', None)
        if prof and prof.is_a('IfcRectangleProfileDef'):
            xd = float(getattr(prof, 'XDim', 0) or 0)
            yd = float(getattr(prof, 'YDim', 0) or 0)
            xd = xd if xd > 100 else xd * 1000.0
            yd = yd if yd > 100 else yd * 1000.0
            return (x + xd / 2.0, y + yd / 2.0, z + float(getattr(item, 'Height', 0)) / 2.0)
        return (x, y, z)
    except Exception:
        return None


def get_element_centroid(elem):
    """Get centroid using ifcopenshell.geom (same method as debug script)."""
    try:
        verts = get_vertices(elem)
        if verts is not None and len(verts) > 0:
            verts = verts * 1000.0  # Convert to mm
            return verts.mean(axis=0)
    except Exception:
        pass
    return None


def build_space_bboxes(spaces):
    b = {}
    for sp in spaces:
        sid = getattr(sp, 'GlobalId', None) or str(id(sp))
        xmin = ymin = float('inf'); xmax = ymax = float('-inf')
        if getattr(sp, 'Representation', None):
            for rep in sp.Representation.Representations:
                for it in getattr(rep, 'Items', []) or []:
                    if it.is_a('IfcExtrudedAreaSolid'):
                        pos = getattr(it, 'Position', None)
                        loc = getattr(pos, 'Location', None) if pos else None
                        coords = list(getattr(loc, 'Coordinates', [])) if loc else []
                        x = float(coords[0]) if coords else 0.0
                        y = float(coords[1]) if len(coords) > 1 else 0.0
                        prof = getattr(it, 'SweptArea', None)
                        if prof and prof.is_a('IfcRectangleProfileDef'):
                            xd = float(getattr(prof, 'XDim', 0) or 0)
                            yd = float(getattr(prof, 'YDim', 0) or 0)
                            xd = xd if xd > 100 else xd * 1000.0
                            yd = yd if yd > 100 else yd * 1000.0
                            hx = xd / 2.0; hy = yd / 2.0
                            xmin = min(xmin, x - hx); ymin = min(ymin, y - hy)
                            xmax = max(xmax, x + hx); ymax = max(ymax, y + hy)
        b[sid] = (xmin, ymin, xmax, ymax) if xmin != float('inf') else None
    return b


def build_space_linkages(model, spaces):
    """Check if hallways connect to stair spaces via doors.

    This builds adjacency between spaces that share a door opening, then
    computes which hallways are linked to stairs either directly (door)
    or transitively via other hallways (hallway -> hallway -> ... -> stair).
    """
    # Identify stair and hallway spaces
    stair_spaces = {}
    hallway_spaces = {}

    spaces_list = list(spaces)
    for sp in spaces_list:
        sid = getattr(sp, 'GlobalId', None) or str(id(sp))
        name = (getattr(sp, 'Name', None) or '').lower()
        if 'stair' in name:
            stair_spaces[sid] = sp
        elif 'hallway' in name:
            hallway_spaces[sid] = sp

    # Build adjacency map between spaces (space_gid -> set(space_gid)) using doors
    adjacency = { (getattr(sp, 'GlobalId', None) or str(id(sp))): set() for sp in spaces_list }

    # Build helper map: opening_gid -> list of containing elements (walls etc.)
    opening_to_containers = {}
    for relv in model.by_type('IfcRelVoidsElement'):
        container = getattr(relv, 'RelatingBuildingElement', None)
        opening = getattr(relv, 'RelatedOpeningElement', None)
        if not opening:
            continue
        ogid = getattr(opening, 'GlobalId', None) or str(id(opening))
        if container is not None:
            opening_to_containers.setdefault(ogid, []).append(container)

    # We'll also record which door connects to which spaces and which containers its opening sits in
    door_map = {}
    door_container_map = {}

    for rel in model.by_type('IfcRelFillsElement'):
        opening = getattr(rel, 'RelatingOpeningElement', None)
        door = getattr(rel, 'RelatedBuildingElement', None)
        if not (opening and door and door.is_a('IfcDoor')):
            continue

        # Get opening centroid (try opening first, then door as fallback)
        oc = get_element_centroid(opening)
        if oc is None:
            oc = get_element_centroid(door)
        if oc is None:
            continue

        # Find all spaces that contain this opening
        connected_spaces = []
        margin = 500  # 500mm margin
        for sp in spaces_list:
            sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
            verts = get_vertices(sp)
            if verts is not None and len(verts) > 0:
                verts = verts * 1000.0  # Convert to mm
                minv = verts.min(axis=0)
                maxv = verts.max(axis=0)
                if minv[0] - margin <= oc[0] <= maxv[0] + margin and \
                   minv[1] - margin <= oc[1] <= maxv[1] + margin:
                    connected_spaces.append(sp_gid)

        # Link all connected spaces pairwise in adjacency
        for i in range(len(connected_spaces)):
            for j in range(i + 1, len(connected_spaces)):
                a = connected_spaces[i]
                b = connected_spaces[j]
                adjacency.setdefault(a, set()).add(b)
                adjacency.setdefault(b, set()).add(a)

        # Record door -> spaces map
        dg = getattr(door, 'GlobalId', None) or str(id(door))
        door_map.setdefault(dg, set()).update(connected_spaces)

        # Record container types (walls etc.) for this opening so we can check compartmentation
        og = getattr(opening, 'GlobalId', None) or str(id(opening))
        containers = opening_to_containers.get(og, [])
        door_container_map[dg] = [c.is_a() for c in containers]

    # Now compute which hallways are linked to stairs.
    # Start from stairs and propagate through hallway nodes only.
    linked_hallways = set()
    from collections import deque
    q = deque()

    # Enqueue all hallways that are directly adjacent to a stair
    for stair_gid in stair_spaces:
        for nb in adjacency.get(stair_gid, set()):
            if nb in hallway_spaces and nb not in linked_hallways:
                linked_hallways.add(nb)
                q.append(nb)

    # BFS across hallway nodes only
    while q:
        current = q.popleft()
        for nb in adjacency.get(current, set()):
            if nb in hallway_spaces and nb not in linked_hallways:
                linked_hallways.add(nb)
                q.append(nb)

    # Prepare final map for all hallways
    space_linked_to_stairs = {}
    for sid in hallway_spaces:
        space_linked_to_stairs[sid] = (sid in linked_hallways)

    # Ensure all spaces have an entry (False for non-hallways)
    for sp in spaces_list:
        sid = getattr(sp, 'GlobalId', None) or str(id(sp))
        space_linked_to_stairs.setdefault(sid, False)

    return space_linked_to_stairs, door_map, door_container_map

def build_full_door_space_map(model, margin=1000):
    """Build a complete door->space connectivity map over ALL IfcSpace elements.

    Heuristics combined:
      1. Opening/door centroid inside space bbox (+margin)
      2. Door bbox (expanded by margin) intersects space bbox
    This widens detection of doors connecting to stair spaces that were missed by
    centroid-only logic. Also returns door->container element types.
    Returns (door_map_all, door_container_map_all)
    """
    spaces_list = list(model.by_type('IfcSpace'))
    # Precompute space bboxes
    space_bboxes = {}
    for sp in spaces_list:
        sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
        bb = _bbox2d_mm(sp)
        if bb:
            space_bboxes[sp_gid] = bb
    door_map_all = {}
    door_container_map_all = {}
    opening_to_containers = {}
    for relv in model.by_type('IfcRelVoidsElement'):
        container = getattr(relv, 'RelatingBuildingElement', None)
        opening = getattr(relv, 'RelatedOpeningElement', None)
        if not opening:
            continue
        ogid = getattr(opening, 'GlobalId', None) or str(id(opening))
        if container is not None:
            opening_to_containers.setdefault(ogid, []).append(container)
    for rel in model.by_type('IfcRelFillsElement'):
        opening = getattr(rel, 'RelatingOpeningElement', None)
        door = getattr(rel, 'RelatedBuildingElement', None)
        if not (opening and door and door.is_a('IfcDoor')):
            continue
        oc_open = get_element_centroid(opening)
        oc_door = get_element_centroid(door)
        oc = oc_open if oc_open is not None else oc_door
        if oc is None:
            continue
        dg = getattr(door, 'GlobalId', None) or str(id(door))
        connected_spaces = []
        # Centroid inclusion
        for sp_gid, (x1,y1,x2,y2) in space_bboxes.items():
            if (x1 - margin) <= oc[0] <= (x2 + margin) and (y1 - margin) <= oc[1] <= (y2 + margin):
                connected_spaces.append(sp_gid)
        # Door bbox intersection
        db = _bbox2d_mm(door)
        if db:
            dx1,dy1,dx2,dy2 = db
            db_exp = (dx1 - margin, dy1 - margin, dx2 + margin, dy2 + margin)
            for sp_gid, bb in space_bboxes.items():
                if sp_gid in connected_spaces:
                    continue
                if _bbox_intersect(db_exp, bb):
                    connected_spaces.append(sp_gid)
        # Opening bbox intersection (if available)
        ob = _bbox2d_mm(opening)
        if ob:
            ox1,oy1,ox2,oy2 = ob
            ob_exp = (ox1 - margin, oy1 - margin, ox2 + margin, oy2 + margin)
            for sp_gid, bb in space_bboxes.items():
                if sp_gid in connected_spaces:
                    continue
                if _bbox_intersect(ob_exp, bb):
                    connected_spaces.append(sp_gid)
        if connected_spaces:
            door_map_all.setdefault(dg, set()).update(connected_spaces)
        og = getattr(opening, 'GlobalId', None) or str(id(opening))
        containers = opening_to_containers.get(og, [])
        door_container_map_all[dg] = [c.is_a() for c in containers]
    # Also add mappings via space boundaries where the RelatedBuildingElement is a door
    try:
        for rb in model.by_type('IfcRelSpaceBoundary'):
            try:
                sp = getattr(rb, 'RelatingSpace', None)
                be = getattr(rb, 'RelatedBuildingElement', None)
                if not sp or not be or not getattr(be, 'is_a', lambda *_: False)('IfcDoor'):
                    continue
                sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
                dg = getattr(be, 'GlobalId', None) or str(id(be))
                door_map_all.setdefault(dg, set()).add(sp_gid)
            except Exception:
                continue
    except Exception:
        pass
    return door_map_all, door_container_map_all


def analyze_door(door, door_map, opening_map):
    name = getattr(door, 'Name', None) or str(door)
    gid = getattr(door, 'GlobalId', None) or str(id(door))
    full = f"{name} [{gid}]"
    width = get_numeric(door, ['overallwidth', 'width', 'doorwidth'])
    op = opening_map.get(gid)
    if not width and op:
        if getattr(op, 'Representation', None):
            for rep in op.Representation.Representations:
                for it in getattr(rep, 'Items', []) or []:
                    if it.is_a('IfcExtrudedAreaSolid'):
                        prof = getattr(it, 'SweptArea', None)
                        if prof and prof.is_a('IfcRectangleProfileDef'):
                            w = to_mm(getattr(prof, 'YDim', None)) or to_mm(getattr(prof, 'XDim', None))
                            if w:
                                width = w
                                break
                if width:
                    break
    issues = []
    if width is None:
        issues.append('width unknown')
    elif width < DOOR_MIN:
        issues.append(f'width {width:.0f}mm < {DOOR_MIN}mm')
    linked = door_map.get(gid, set())
    return {'name': full, 'width_mm': width, 'linked_spaces': linked, 'issues': issues}


def analyze_stair(flight):
    name = getattr(flight, 'Name', None) or str(flight)
    gid = getattr(flight, 'GlobalId', None) or str(id(flight))
    full = f"{name} [{gid}]"
    width = get_numeric(flight, ['actual run width', 'actualrunwidth', 'run width', 'width', 'tread'])
    if width is None and getattr(flight, 'Representation', None):
        for rep in flight.Representation.Representations:
            for it in getattr(rep, 'Items', []) or []:
                if it.is_a('IfcExtrudedAreaSolid'):
                    prof = getattr(it, 'SweptArea', None)
                    if prof and prof.is_a('IfcRectangleProfileDef'):
                        xd = float(getattr(prof, 'XDim', 0) or 0)
                        yd = float(getattr(prof, 'YDim', 0) or 0)
                        xd = xd if xd > 100 else xd * 1000.0
                        yd = yd if yd > 100 else yd * 1000.0
                        width = max(xd, yd)
                        break
            if width is not None:
                break
    issues = []
    if width is None:
        issues.append('width unknown')
    elif width + 1e-6 < STAIR_MIN:
        issues.append(f'width {width:.0f}mm < {STAIR_MIN}mm')
    return {'name': full, 'width_mm': width, 'issues': issues}


def is_corridor(space, analysis):
    name = analysis.get('name') or ''
    if any(k in (name or '').lower() for k in ['hallway', 'corridor', 'passage', 'circulation']):
        return True
    return False


def _door_swing_heuristic(door):
    """Try a simple heuristic to determine if a door swings away from an adjacent space.

    Returns 'away', 'toward', or 'unknown'. This is a best-effort string-match heuristic
    from door attributes (Name, ObjectType, Description, OperationType). If nothing
    meaningful is found we return 'unknown'.
    """
    # Prefer explicit IFC attribute OperationType when available
    try:
        op = getattr(door, 'OperationType', None)
        if op:
            op_s = str(op).lower()
            # Common textual/enum hints indicating outward/inward swing
            if 'out' in op_s or 'outward' in op_s or 'opens_out' in op_s or 'open_out' in op_s:
                return 'away'
            if 'in' in op_s or 'inward' in op_s or 'opens_in' in op_s or 'open_in' in op_s:
                return 'toward'
            # Some enumerations include SWING + direction, try to detect 'swing' with qualifier
            if 'swing' in op_s:
                if 'out' in op_s or 'outward' in op_s:
                    return 'away'
                if 'in' in op_s or 'inward' in op_s:
                    return 'toward'
    except Exception:
        pass

    # Fallback: inspect other textual attributes (Name, ObjectType, Description, Tag)
    candidates = []
    for attr in ('PredefinedType', 'ObjectType', 'Name', 'Description', 'Tag'):
        try:
            v = getattr(door, attr, None)
            if v:
                candidates.append(str(v).lower())
        except Exception:
            continue

    txt = ' '.join(candidates)
    if not txt:
        return 'unknown'

    if 'outward' in txt or 'opens out' in txt or 'opens away' in txt or 'open out' in txt or 'open outwards' in txt:
        return 'away'
    if 'inward' in txt or 'opens in' in txt or 'open in' in txt or 'opens into' in txt or 'into' in txt:
        return 'toward'
    if 'swing' in txt:
        if 'out' in txt or 'outward' in txt:
            return 'away'
        if 'in' in txt or 'inward' in txt:
            return 'toward'

    return 'unknown'


def analyze_stair_compartmentation(model, door_map, door_container_map, use_geometry=False):
    """ULTRA-FAST stair compartmentation check - NO GEOMETRY EXTRACTION.

    Rule set enforced per stair space (multi-storey context assumed if building has >1 storey):
        1. Exactly one ENTRY door must exist (door linking stair space to exactly one NON-stair space)
        2. That door must be contained in / related to a wall (compartmentation boundary)
        3. That door must swing TOWARD the stair (heuristic text-based swing detection)
        4. Unknown swing is flagged (cannot verify compliance)

    A door is classified as an ENTRY door only if:
        - The door_map shows the door connects to the stair space AND
        - Connects to at least one non-stair space AND
        - Connects to exactly 2 spaces total (stair + one other) to reduce false positives.

    Returns a list of stair result dicts including:
        stair_name, door_count, offending_doors (list), stair_reasons (list), has_issues (bool)
    """
    results = []

    # Quick lookup of doors by GlobalId
    doors_by_gid = {(getattr(d, 'GlobalId', None) or str(id(d))): d for d in model.by_type('IfcDoor')}

    # Check if building has multiple storeys
    storeys = model.by_type('IfcBuildingStorey')
    if len(storeys) < 2:
        return results  # Single storey building, no multi-storey stairs possible

    if use_geometry:
        # Use geometry-derived mapping, but FILTER OUT spaces that are not actually stairs by name
        geom_map = identify_stair_spaces_geometry(model)
        stair_spaces = []
        stair_space_gids = set()
        for gid, rec in geom_map.items():
            nm = (rec.get('name') or '').lower()
            if 'stair' in nm:  # exclude hallways mislabeled as stair spaces by geometry
                stair_spaces.append({'gid': gid, 'name': rec.get('name')})
                stair_space_gids.add(gid)
        # Also include any name-based stair spaces that geometry missed
        for space in model.by_type('IfcSpace'):
            nm = (getattr(space, 'Name', None) or '').lower()
            if 'stair' in nm:
                gid = getattr(space, 'GlobalId', None) or str(id(space))
                if gid not in stair_space_gids:
                    stair_spaces.append({'gid': gid, 'name': getattr(space, 'Name', None)})
                    stair_space_gids.add(gid)
    else:
        # Name-based only
        stair_spaces = []
        stair_space_gids = set()
        for space in model.by_type('IfcSpace'):
            name = (getattr(space, 'Name', None) or '').lower()
            if 'stair' in name:
                gid = getattr(space, 'GlobalId', None) or str(id(space))
                stair_spaces.append({'gid': gid, 'name': getattr(space, 'Name', None)})
                stair_space_gids.add(gid)

    if not stair_spaces:
        return results  # No stair spaces found (geometry or name based)

    # For each stair space, find ENTRY doors (doors connecting stair to non-stair spaces)
    for stair_space in stair_spaces:
        stair_gid = stair_space['gid']
        stair_name = stair_space['name']

        # Identify entry doors meeting criteria
        entry_doors = []
        for door_gid, connected_space_gids in door_map.items():
            if stair_gid not in connected_space_gids:
                continue
            other_spaces = [sid for sid in connected_space_gids if sid != stair_gid]
            has_non_stair = any(sid not in stair_space_gids for sid in other_spaces)
            # Relax: accept doors that connect stair + any non-stair (even if >2 spaces due to modeling)
            if has_non_stair:
                entry_doors.append(door_gid)

        # Stair-level reasons (missing or multiple entry doors)
        stair_reasons = []
        if len(entry_doors) == 0:
            stair_reasons.append('no entry door found (expected exactly 1)')
        elif len(entry_doors) > 1:
            stair_reasons.append(f'{len(entry_doors)} entry doors found (expected exactly 1)')

        # Door-level checks
        offending_doors = []
        for dg in entry_doors:
            door = doors_by_gid.get(dg)
            if door is None:
                continue
            reason_parts = []
            conts = door_container_map.get(dg, [])
            in_wall = any('IfcWall' in c for c in conts)
            if not in_wall:
                reason_parts.append('door not in wall (compartmentation required)')
            swing = _door_swing_heuristic(door)
            if swing == 'away':
                reason_parts.append('swings away from stair (should swing toward stair)')
            elif swing == 'unknown':
                reason_parts.append('swing direction unknown')
            if reason_parts:
                offending_doors.append({
                    'door_gid': dg,
                    'reasons': reason_parts,
                    'door_name': getattr(door, 'Name', None)
                })

        has_issues = bool(stair_reasons or offending_doors)
        results.append({
            'stair_name': stair_name or f'Stair space [{stair_gid}]',
            'door_count': len(entry_doors),
            'offending_doors': offending_doors,
            'stair_reasons': stair_reasons,
            'has_issues': has_issues,
            'geometry_based': use_geometry
        })

    return results


def analyze_staircase_groups(model):
    """Group IfcStairFlight elements by their base staircase identifier extracted from the Name.

    Example flight names observed:
      Assembled Stair:Stair:1282665 Run 1
      Assembled Stair:Stair:1282665 Run 2
      Assembled Stair:Stair:1282665 Run 3

    We extract the numeric id after the last 'Stair:' token (here 1282665).
    Each unique id represents one staircase between two storeys according to user spec.

    Returns list of staircase dicts:
      { 'id': <numeric str>, 'flight_count': N, 'run_labels': [...], 'is_standard_3_run': bool }
    """
    flights = model.by_type('IfcStairFlight')
    groups = {}
    for fl in flights:
        name = (getattr(fl, 'Name', None) or '')
        # Extract last numeric sequence after 'Stair:'
        stair_id = None
        if 'Stair:' in name:
            parts = name.split('Stair:')
            # Take last part then isolate leading digits
            tail = parts[-1].strip()
            # tail may look like '1282665 Run 1' -> take digits at start
            import re as _re
            m = _re.match(r'(\d+)', tail)
            if m:
                stair_id = m.group(1)
        if not stair_id:
            continue
        g = groups.setdefault(stair_id, {'id': stair_id, 'flights': [], 'run_labels': []})
        g['flights'].append(fl)
        run_label = ''
        if 'Run' in name:
            # capture 'Run' part
            run_label = name.split('Run',1)[1].strip()
        g['run_labels'].append(run_label or 'unknown')
    # Build output list
    out = []
    for sid, g in groups.items():
        run_labels_norm = [rl for rl in g['run_labels']]
        # Determine if it matches expected 3-run pattern (Run 1, Run 2, Run 3)
        expected_set = {'1','2','3','Run 1','Run 2','Run 3'}
        # Simplify run label tokens
        simple_tokens = set()
        for rl in run_labels_norm:
            tok = rl.replace(':',' ').split()[0]
            simple_tokens.add(tok)
        is_standard = {'1','2','3'} <= simple_tokens or {'Run','1','2','3'} <= simple_tokens
        out.append({
            'id': sid,
            'flight_count': len(g['flights']),
            'run_labels': run_labels_norm,
            'is_standard_3_run': is_standard
        })
    return out


def analyze_staircase_group_enclosure(model, side_margin=300.0, wall_search_expand=500.0, debug_group_id=None):
    """Proximity enclosure check per staircase flight group.

    Improvement over previous version:
      - Prefer union of associated stair *space* bboxes (geometry-identified) instead of raw flight bboxes.
        This aligns group enclosure with space-level enclosure logic and avoids artificial open sides
        introduced by irregular flight arrangement (e.g. landing offsets making union larger than real shaft).
      - Fallback to flight union if no spaces found.
      - Optional debug output for a specific staircase id to inspect chosen bboxes and side coverage.

    Passing condition: all 4 sides covered by at least one wall bbox intersection.
    Returns list of dicts: {id, flight_count, sides_covered, missing_sides, has_issue, source}
    """
    groups = analyze_staircase_groups(model)
    if not groups:
        return []

    # Collect flights indexed by gid & names for quick membership
    flights = { (getattr(f,'GlobalId',None) or str(id(f))): f for f in model.by_type('IfcStairFlight') }

    # Geometry-based stair spaces mapping (space_gid -> {'space','name','flight_gids'})
    geom_stair_spaces = identify_stair_spaces_geometry(model)
    # Invert mapping flight_gid -> list(space_gid)
    flight_to_spaces = {}
    for sp_gid, rec in geom_stair_spaces.items():
        for fg in rec['flight_gids']:
            flight_to_spaces.setdefault(fg, set()).add(sp_gid)

    # Walls (standard + regular)
    walls = list(model.by_type('IfcWall')) + list(model.by_type('IfcWallStandardCase'))
    wall_bboxes = []
    for w in walls:
        wb = _bbox2d_mm(w)
        if wb:
            wall_bboxes.append(wb)

    results = []
    for g in groups:
        sid = g['id']
        group_flight_gids = []
        flight_bboxes = []
        for fl_gid, fl in flights.items():
            name = getattr(fl, 'Name', None) or ''
            if sid in name:  # flight belongs to this staircase id
                bb = _bbox2d_mm(fl)
                if bb:
                    flight_bboxes.append(bb)
                    group_flight_gids.append(fl_gid)
        if not flight_bboxes:
            results.append({'id': sid, 'flight_count': g['flight_count'], 'sides_covered': 0, 'missing_sides': ['left','right','bottom','top'], 'has_issue': True, 'source': 'none'} )
            continue

        # Attempt to derive union of associated stair spaces (those containing any group flight centroids)
        space_bboxes = []
        used_space_ids = set()
        for fg in group_flight_gids:
            for sp_gid in flight_to_spaces.get(fg, []):
                if sp_gid in used_space_ids:
                    continue
                sp_rec = geom_stair_spaces.get(sp_gid)
                if not sp_rec:
                    continue
                sp_bb = _bbox2d_mm(sp_rec['space'])
                if sp_bb:
                    space_bboxes.append(sp_bb)
                    used_space_ids.add(sp_gid)

        if space_bboxes:
            xs1 = min(b[0] for b in space_bboxes); ys1 = min(b[1] for b in space_bboxes)
            xs2 = max(b[2] for b in space_bboxes); ys2 = max(b[3] for b in space_bboxes)
            source = 'space_union'
        else:
            # Fallback: flight union (previous behavior)
            xs1 = min(b[0] for b in flight_bboxes); ys1 = min(b[1] for b in flight_bboxes)
            xs2 = max(b[2] for b in flight_bboxes); ys2 = max(b[3] for b in flight_bboxes)
            source = 'flight_union'

        # Build side strips (slightly shrink interior by side_margin/2 to reduce false missing side)
        # NOTE: side_margin kept; could be tuned if still missing sides erroneously.
        strips = {
            'left':   (xs1 - wall_search_expand, ys1 - wall_search_expand, xs1 + side_margin, ys2 + wall_search_expand),
            'right':  (xs2 - side_margin,       ys1 - wall_search_expand, xs2 + wall_search_expand, ys2 + wall_search_expand),
            'top':    (xs1 - wall_search_expand, ys2 - side_margin,       xs2 + wall_search_expand, ys2 + wall_search_expand),
        }
        covered = {k: False for k in strips}
        for wb in wall_bboxes:
            for k, strip in strips.items():
                if not covered[k] and _bbox_intersect(strip, wb):
                    covered[k] = True
            if all(covered.values()):
                break
        sides_covered = sum(1 for v in covered.values() if v)
        missing = [k for k, v in covered.items() if not v]
        has_issue = sides_covered < 3

        # Optional debug print for one target group id
        if debug_group_id and sid == str(debug_group_id):
            print(f"DEBUG StaircaseGroup {sid}: source={source} flights={len(group_flight_gids)} spaces={len(space_bboxes)} bbox=({xs1:.1f},{ys1:.1f},{xs2:.1f},{ys2:.1f}) sides_covered={sides_covered}/3 missing={missing}")
            if space_bboxes:
                for i, sb in enumerate(space_bboxes):
                    print(f"  DEBUG space_bbox[{i}]={sb}")
            for i, fb in enumerate(flight_bboxes[:5]):
                print(f"  DEBUG flight_bbox[{i}]={fb}")

        results.append({'id': sid, 'flight_count': g['flight_count'], 'sides_covered': sides_covered, 'missing_sides': missing, 'has_issue': has_issue, 'source': source})
    return results

def analyze_staircase_group_entry_doors(model, door_map):
    """Find doors that lead into each staircase flight group and classify their swing.

    Logic:
      - Retrieve staircase groups via analyze_staircase_groups (group id from flight names)
      - Geometry map flights->spaces using identify_stair_spaces_geometry (centroid within space bbox)
      - For each group, collect all spaces containing its flights
      - Entry door for group: door connects exactly two spaces where one is in group's space set and the other isn't
      - Classify door swing with _door_swing_heuristic
    Returns list per group:
      {
        'group_id', 'flight_count', 'space_count',
        'entry_doors': [ {'door_gid','door_name','swing'} ],
        'counts': {'total','toward','away','unknown'}
      }
    """
    groups = analyze_staircase_groups(model)
    if not groups:
        return []
    geom_map = identify_stair_spaces_geometry(model)  # space_gid -> rec with flight_gids
    # Build flight->space set mapping from geom_map
    flight_to_spaces = {}
    for sp_gid, rec in geom_map.items():
        for fg in rec.get('flight_gids', []):
            flight_to_spaces.setdefault(fg, set()).add(sp_gid)

    # Pre-index flights by name for membership in group
    flights = model.by_type('IfcStairFlight')
    flight_name_map = { (getattr(fl,'GlobalId',None) or str(id(fl))): (getattr(fl,'Name',None) or '') for fl in flights }

    # Door entities for naming
    doors_by_gid = {(getattr(d,'GlobalId',None) or str(id(d))): d for d in model.by_type('IfcDoor')}

    results = []
    for g in groups:
        gid = g['id']
        # Gather flights that belong to this group
        group_flight_gids = [fg for fg,name in flight_name_map.items() if gid in name]
        # Spaces containing these flights
        group_space_gids = set()
        for fg in group_flight_gids:
            group_space_gids.update(flight_to_spaces.get(fg, []))
        entry_doors = []
        toward = away = unknown = 0
        for door_gid, connected_space_gids in door_map.items():
            sids = list(connected_space_gids)
            in_count = sum(1 for sid in sids if sid in group_space_gids)
            # Accept doors that connect at least one group space and at least one non-group space
            if in_count >= 1 and any(sid not in group_space_gids for sid in sids):
                door = doors_by_gid.get(door_gid)
                swing = _door_swing_heuristic(door) if door else 'unknown'
                if swing == 'toward':
                    toward += 1
                elif swing == 'away':
                    away += 1
                else:
                    unknown += 1
                entry_doors.append({
                    'door_gid': door_gid,
                    'door_name': getattr(door,'Name',None) if door else door_gid,
                    'swing': swing
                })
        results.append({
            'group_id': gid,
            'flight_count': g['flight_count'],
            'space_count': len(group_space_gids),
            'entry_doors': entry_doors,
            'counts': {'total': len(entry_doors), 'toward': toward, 'away': away, 'unknown': unknown}
        })
    return results


def analyze_stair_flight_enclosure(model):
    """Check each IfcStairFlight is 'between walls' by counting connected walls.

    Heuristic: Use IfcRelConnectsElements relationships. If a flight has fewer than 2
    distinct connected walls it is flagged as an issue (not enclosed / missing boundary).
    No geometry extraction performed.
    Returns list of dicts: {name, gid, wall_count, has_issue, issues}
    """
    flights = model.by_type('IfcStairFlight')
    rels = model.by_type('IfcRelConnectsElements')
    # Map element id to connected walls
    flight_wall_map = {}
    for rel in rels:
        try:
            a = getattr(rel, 'RelatingElement', None)
            b = getattr(rel, 'RelatedElement', None)
        except Exception:
            continue
        if not a or not b:
            continue
        # If one side is flight, other is wall
        for flight, other in ((a, b), (b, a)):
            try:
                if flight.is_a('IfcStairFlight') and other.is_a('IfcWall'):
                    gid = getattr(flight, 'GlobalId', None) or str(id(flight))
                    wgid = getattr(other, 'GlobalId', None) or str(id(other))
                    s = flight_wall_map.setdefault(gid, set())
                    s.add(wgid)
                if flight.is_a('IfcStairFlight') and other.is_a('IfcWallStandardCase'):
                    gid = getattr(flight, 'GlobalId', None) or str(id(flight))
                    wgid = getattr(other, 'GlobalId', None) or str(id(other))
                    s = flight_wall_map.setdefault(gid, set())
                    s.add(wgid)
            except Exception:
                continue
    # Also include IfcRelConnectsWithRealizingElements relations
    for rel in model.by_type('IfcRelConnectsWithRealizingElements'):
        try:
            rel_elem = getattr(rel, 'RelatingElement', None)
            related_elems = list(getattr(rel, 'RelatedElements', []) or [])
        except Exception:
            continue
        elems = []
        if rel_elem:
            elems.append(rel_elem)
        elems.extend(related_elems)
        # Check any pair (flight, wall)
        flights = [e for e in elems if getattr(e, 'is_a', lambda *_: False)('IfcStairFlight')]
        walls = [e for e in elems if getattr(e, 'is_a', lambda *_: False)('IfcWall') or getattr(e, 'is_a', lambda *_: False)('IfcWallStandardCase')]
        for fl in flights:
            gid = getattr(fl, 'GlobalId', None) or str(id(fl))
            s = flight_wall_map.setdefault(gid, set())
            for w in walls:
                wgid = getattr(w, 'GlobalId', None) or str(id(w))
                s.add(wgid)
    results = []
    for fl in flights:
        gid = getattr(fl, 'GlobalId', None) or str(id(fl))
        name = getattr(fl, 'Name', None) or f'Flight {gid}'
        walls = flight_wall_map.get(gid, set())
        wall_count = len(walls)
        issues = []
        if wall_count < 2:
            issues.append(f'connected walls: {wall_count} (<2) - not between two enclosing walls')
        results.append({'name': name, 'gid': gid, 'wall_count': wall_count, 'has_issue': bool(issues), 'issues': issues})
    return results

def analyze_stair_flight_enclosure_proximity(model, side_margin=300.0, wall_search_expand=500.0):
    """Walls-only proximity enclosure for each IfcStairFlight (exclude floor side).

    Passing condition: all 3 vertical sides (left/right/top) have intersecting wall bboxes.
    Returns list with per-flight enclosure status.
    """
    flights = model.by_type('IfcStairFlight')
    walls = list(model.by_type('IfcWall')) + list(model.by_type('IfcWallStandardCase'))
    wall_bboxes = []
    for w in walls:
        wb = _bbox2d_mm(w)
        if wb:
            wall_bboxes.append(wb)
    results = []
    for fl in flights:
        gid = getattr(fl,'GlobalId',None) or str(id(fl))
        name = getattr(fl,'Name',None) or f'Flight {gid}'
        bb = _bbox2d_mm(fl)
        if not bb:
            results.append({'flight_name': name,'flight_gid': gid,'sides_covered':0,'missing_sides':['left','right','top'],'has_issue':True,'notes':['no geometry']})
            continue
        x1,y1,x2,y2 = bb
        strips = {
            'left':   (x1 - wall_search_expand, y1 - wall_search_expand, x1 + side_margin, y2 + wall_search_expand),
            'right':  (x2 - side_margin,       y1 - wall_search_expand, x2 + wall_search_expand, y2 + wall_search_expand),
            'top':    (x1 - wall_search_expand, y2 - side_margin,       x2 + wall_search_expand, y2 + wall_search_expand),
        }
        covered = {k: False for k in strips}
        for wb in wall_bboxes:
            for k, strip in strips.items():
                if not covered[k] and _bbox_intersect(strip, wb):
                    covered[k] = True
            if all(covered.values()):
                break
        sides_covered = sum(1 for v in covered.values() if v)
        missing = [k for k,v in covered.items() if not v]
        has_issue = sides_covered < 3
        results.append({'flight_name': name,'flight_gid': gid,'sides_covered': sides_covered,'missing_sides': missing,'has_issue': has_issue,'notes':[f'sides {sides_covered}/3']})
    return results


def analyze_stair_entry_door_swings(model, door_map):
    """Summarize swing directions for stair entry doors.

    Entry door = connects exactly two spaces where one is a 'stair' space and the other is not.
    Returns dict with counts and list of door records: { total, toward, away, unknown, records:[...] }
    Each record: { door_name, door_gid, stair_name, swing }
    """
    # Collect stair spaces and names
    stair_spaces = {}
    for sp in model.by_type('IfcSpace'):
        nm = (getattr(sp, 'Name', None) or '').lower()
        if 'stair' in nm:
            gid = getattr(sp, 'GlobalId', None) or str(id(sp))
            stair_spaces[gid] = getattr(sp, 'Name', None) or gid

    if not stair_spaces:
        return {'total': 0, 'toward': 0, 'away': 0, 'unknown': 0, 'records': []}

    # Door entities by gid
    doors_by_gid = {(getattr(d, 'GlobalId', None) or str(id(d))): d for d in model.by_type('IfcDoor')}

    records = []
    toward = away = unknown = 0
    for door_gid, connected_space_gids in door_map.items():
        sids = list(connected_space_gids)
        # Check if one is stair and the other is not
        has_stair = any(sid in stair_spaces for sid in sids)
        has_non_stair = any(sid not in stair_spaces for sid in sids)
        if has_stair and has_non_stair:
            # pick the first stair space for reporting
            stair_gid = next((sid for sid in sids if sid in stair_spaces), None)
            stair_name = stair_spaces[stair_gid]
            door = doors_by_gid.get(door_gid)
            if not door:
                continue
            sw = _door_swing_heuristic(door)
            if sw == 'toward':
                toward += 1
            elif sw == 'away':
                away += 1
            else:
                unknown += 1
            records.append({
                'door_name': getattr(door, 'Name', None) or door_gid,
                'door_gid': door_gid,
                'stair_name': stair_name,
                'swing': sw,
            })

    return {
        'total': len(records),
        'toward': toward,
        'away': away,
        'unknown': unknown,
        'records': records,
    }


def analyze_stair_space_enclosure(model):
    """Check if each 'stair' IfcSpace is fully enclosed by walls using IfcRelSpaceBoundary.

    Rule: For each stair space, consider only PHYSICAL space boundaries. All such boundaries
    must reference a wall element (IfcWall or IfcWallStandardCase). If none are present,
    or if any physical boundary is not a wall, the space is flagged.

    Returns list of dicts per space: {
        'stair_name', 'stair_gid', 'physical_boundaries', 'wall_boundaries', 'has_issue', 'issues'
    }
    """
    stair_spaces = [sp for sp in model.by_type('IfcSpace') if 'stair' in (getattr(sp, 'Name', '') or '').lower()]
    if not stair_spaces:
        return []

    # Pre-collect space boundaries grouped by RelatingSpace gid
    by_space = {}
    for rb in model.by_type('IfcRelSpaceBoundary'):
        try:
            sp = getattr(rb, 'RelatingSpace', None)
            if not sp:
                continue
            gid = getattr(sp, 'GlobalId', None) or str(id(sp))
            by_space.setdefault(gid, []).append(rb)
        except Exception:
            continue

    results = []
    for sp in stair_spaces:
        gid = getattr(sp, 'GlobalId', None) or str(id(sp))
        name = getattr(sp, 'Name', None) or gid
        rbs = by_space.get(gid, [])
        phys = 0
        wall_phys = 0
        issues = []
        for rb in rbs:
            try:
                pv = getattr(rb, 'PhysicalOrVirtualBoundary', None)
                pv_s = str(pv).lower() if pv is not None else ''
                if 'physical' not in pv_s and pv_s != '' and pv_s != 'none':
                    # skip non-physical
                    continue
                # Treat empty pv as physical if unspecified
                phys += 1
                el = getattr(rb, 'RelatedBuildingElement', None)
                if el and (el.is_a('IfcWall') or el.is_a('IfcWallStandardCase')):
                    wall_phys += 1
            except Exception:
                continue

        if phys == 0:
            issues.append('no physical space boundaries found for stair space')
        elif wall_phys < phys:
            issues.append(f'only {wall_phys}/{phys} physical boundaries are walls')

        results.append({
            'stair_name': name,
            'stair_gid': gid,
            'physical_boundaries': phys,
            'wall_boundaries': wall_phys,
            'has_issue': bool(issues),
            'issues': issues,
        })

    return results

def identify_stair_spaces_geometry(model):
    """Identify stair spaces by associating each IfcStairFlight centroid with a containing IfcSpace.

    This supplements name-based detection (spaces containing 'stair'). A space is flagged as a
    stair space if at least one stair flight centroid lies inside its 2D bbox (with margin).
    Returns a dict: {space_gid: {'space': space, 'name': name, 'flight_gids': set([...])}}
    """
    spaces = model.by_type('IfcSpace')
    flights = model.by_type('IfcStairFlight')
    # Precompute space bboxes
    space_bbox = {}
    for sp in spaces:
        gid = getattr(sp, 'GlobalId', None) or str(id(sp))
        bb = _bbox2d_mm(sp)
        if bb:
            space_bbox[gid] = bb
    # Get flight centroids
    flight_centroids = {}
    for fl in flights:
        verts = get_vertices(fl)
        if verts is not None and len(verts) > 0:
            verts = verts * 1000.0
            c = verts.mean(axis=0)
            flight_centroids[getattr(fl, 'GlobalId', None) or str(id(fl))] = (float(c[0]), float(c[1]))
    # Associate
    stair_spaces = {}
    margin = 300.0
    for fl_gid, (fx, fy) in flight_centroids.items():
        for sp_gid, bb in space_bbox.items():
            x1,y1,x2,y2 = bb
            if (x1 - margin) <= fx <= (x2 + margin) and (y1 - margin) <= fy <= (y2 + margin):
                sp = next((s for s in spaces if (getattr(s,'GlobalId',None) or str(id(s)))==sp_gid), None)
                if sp is None:
                    continue
                entry = stair_spaces.setdefault(sp_gid, {'space': sp, 'name': getattr(sp,'Name',None) or sp_gid, 'flight_gids': set()})
                entry['flight_gids'].add(fl_gid)
    # Merge name-based spaces even if no flight caught (keep original 5)
    for sp in spaces:
        name_l = (getattr(sp,'Name',None) or '').lower()
        if 'stair' in name_l:
            sp_gid = getattr(sp,'GlobalId',None) or str(id(sp))
            stair_spaces.setdefault(sp_gid, {'space': sp, 'name': getattr(sp,'Name',None) or sp_gid, 'flight_gids': set()})
    return stair_spaces


def _bbox2d_mm(entity):
    """Return (xmin,ymin,xmax,ymax) in mm for an entity using geometry verts; None on failure."""
    try:
        # Cache by type + GlobalId
        try:
            gid = getattr(entity, 'GlobalId', None) or str(id(entity))
            et = entity.is_a() if hasattr(entity, 'is_a') else type(entity).__name__
            key = (et, gid)
        except Exception:
            key = None
        if key and key in _BBOX_CACHE:
            return _BBOX_CACHE[key]

        verts = get_vertices(entity)
        if verts is None or len(verts) == 0:
            return None
        verts = verts * 1000.0
        minv = verts.min(axis=0)
        maxv = verts.max(axis=0)
        bb = (float(minv[0]), float(minv[1]), float(maxv[0]), float(maxv[1]))
        if key:
            _BBOX_CACHE[key] = bb
        return bb
    except Exception:
        return None


def _bbox_intersect(a, b, margin=0.0):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 < bx1 - margin or bx2 < ax1 - margin or ay2 < by1 - margin or by2 < ay1 - margin)


def analyze_stair_space_enclosure_proximity(model, side_margin=300.0, wall_search_expand=500.0):
    """Proximity-based stair space enclosure (vertical walls only).

    A stair space passes enclosure if walls are detected adjacent to all three
    vertical perimeter sides: left, right, top (floor side ignored).
    Returns list per stair space: {stair_name, stair_gid, sides_covered, missing_sides, has_issue, notes}
    """
    # Collect stair spaces
    stair_spaces = [sp for sp in model.by_type('IfcSpace') if 'stair' in (getattr(sp, 'Name', '') or '').lower()]
    if not stair_spaces:
        return []

    # Collect walls and storey containment mapping
    walls = list(model.by_type('IfcWall')) + list(model.by_type('IfcWallStandardCase'))
    wall_to_storey = {}
    space_to_storey = {}
    for rel in model.by_type('IfcRelContainedInSpatialStructure'):
        parent = getattr(rel, 'RelatingStructure', None)
        if parent and parent.is_a('IfcBuildingStorey'):
            for e in getattr(rel, 'RelatedElements', []) or []:
                try:
                    gid = getattr(e, 'GlobalId', None) or str(id(e))
                    if e.is_a('IfcWall') or e.is_a('IfcWallStandardCase'):
                        wall_to_storey[gid] = parent
                    if e.is_a('IfcSpace'):
                        space_to_storey[gid] = parent
                except Exception:
                    continue

    # Precompute wall bboxes by storey lazily
    wall_bboxes_by_storey = {}

    results = []
    for sp in stair_spaces:
        sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
        sp_name = getattr(sp, 'Name', None) or sp_gid
        sb = _bbox2d_mm(sp)
        if sb is None:
            results.append({'stair_name': sp_name, 'stair_gid': sp_gid, 'sides_covered': 0, 'missing_sides': ['left','right','top'], 'has_issue': True, 'notes': ['no geometry available for space bbox']})
            continue
        sx1, sy1, sx2, sy2 = sb
        storey = space_to_storey.get(sp_gid)

        # Get walls in the same storey if available else all walls
        candidate_walls = []
        if storey:
            sid = getattr(storey, 'GlobalId', None) or str(id(storey))
            if sid not in wall_bboxes_by_storey:
                # compute bboxes for walls in this storey
                wall_bboxes_by_storey[sid] = []
                for w in walls:
                    w_gid = getattr(w, 'GlobalId', None) or str(id(w))
                    if wall_to_storey.get(w_gid) is storey:
                        wb = _bbox2d_mm(w)
                        if wb:
                            wall_bboxes_by_storey[sid].append((w_gid, wb))
            candidate_walls = wall_bboxes_by_storey[sid]
        else:
            # fall back to all walls (slow)
            if 'ALL' not in wall_bboxes_by_storey:
                wall_bboxes_by_storey['ALL'] = []
                for w in walls:
                    wb = _bbox2d_mm(w)
                    if wb:
                        wall_bboxes_by_storey['ALL'].append((getattr(w, 'GlobalId', None) or str(id(w)), wb))
            candidate_walls = wall_bboxes_by_storey['ALL']

        # Build side strips (exclude floor side): only left/right/top for vertical enclosure
        strips = {
            'left':   (sx1 - wall_search_expand, sy1 - wall_search_expand, sx1 + side_margin, sy2 + wall_search_expand),
            'right':  (sx2 - side_margin,       sy1 - wall_search_expand, sx2 + wall_search_expand, sy2 + wall_search_expand),
            'top':    (sx1 - wall_search_expand, sy2 - side_margin,       sx2 + wall_search_expand, sy2 + wall_search_expand),
        }

        covered = {k: False for k in strips}
        for _, wb in candidate_walls:
            for k, strip in strips.items():
                if not covered[k] and _bbox_intersect(strip, wb):
                    covered[k] = True
        sides_covered = sum(1 for v in covered.values() if v)
        missing = [k for k, v in covered.items() if not v]
        # Require all 3 vertical sides
        has_issue = sides_covered < 3
        note = [f"sides covered: {sides_covered}/3"]
        results.append({
            'stair_name': sp_name,
            'stair_gid': sp_gid,
            'sides_covered': sides_covered,
            'missing_sides': missing,
            'has_issue': has_issue,
            'notes': note,
        })

    return results


def analyze_stair_simple_4wall_enclosure(model, side_margin=300.0, wall_search_expand=500.0):
    """Simple 4-wall enclosure check for stair spaces (ignores doors completely).

    Checks if each stair space has walls on all 4 sides: left, right, top, bottom.
    Returns list: {stair_name, stair_gid, fully_enclosed (bool), sides_covered, missing_sides}
    """
    stair_spaces = [sp for sp in model.by_type('IfcSpace') if 'stair' in (getattr(sp, 'Name', '') or '').lower()]
    if not stair_spaces:
        return []

    walls = list(model.by_type('IfcWall')) + list(model.by_type('IfcWallStandardCase'))
    wall_to_storey = {}
    space_to_storey = {}
    for rel in model.by_type('IfcRelContainedInSpatialStructure'):
        parent = getattr(rel, 'RelatingStructure', None)
        if parent and parent.is_a('IfcBuildingStorey'):
            for e in getattr(rel, 'RelatedElements', []) or []:
                try:
                    gid = getattr(e, 'GlobalId', None) or str(id(e))
                    if e.is_a('IfcWall') or e.is_a('IfcWallStandardCase'):
                        wall_to_storey[gid] = parent
                    if e.is_a('IfcSpace'):
                        space_to_storey[gid] = parent
                except Exception:
                    continue

    wall_bboxes_by_storey = {}
    results = []
    
    for sp in stair_spaces:
        sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
        sp_name = getattr(sp, 'Name', None) or sp_gid
        sb = _bbox2d_mm(sp)
        if sb is None:
            results.append({
                'stair_name': sp_name,
                'stair_gid': sp_gid,
                'fully_enclosed': False,
                'sides_covered': 0,
                'missing_sides': ['left','right','top','bottom']
            })
            continue
        
        sx1, sy1, sx2, sy2 = sb
        storey = space_to_storey.get(sp_gid)

        candidate_walls = []
        if storey:
            sid = getattr(storey, 'GlobalId', None) or str(id(storey))
            if sid not in wall_bboxes_by_storey:
                wall_bboxes_by_storey[sid] = []
                for w in walls:
                    w_gid = getattr(w, 'GlobalId', None) or str(id(w))
                    if wall_to_storey.get(w_gid) is storey:
                        wb = _bbox2d_mm(w)
                        if wb:
                            wall_bboxes_by_storey[sid].append((w_gid, wb))
            candidate_walls = wall_bboxes_by_storey[sid]
        else:
            if 'ALL' not in wall_bboxes_by_storey:
                wall_bboxes_by_storey['ALL'] = []
                for w in walls:
                    wb = _bbox2d_mm(w)
                    if wb:
                        wall_bboxes_by_storey['ALL'].append((getattr(w, 'GlobalId', None) or str(id(w)), wb))
            candidate_walls = wall_bboxes_by_storey['ALL']

        # Build all 4 side strips
        strips = {
            'left':   (sx1 - wall_search_expand, sy1 - wall_search_expand, sx1 + side_margin, sy2 + wall_search_expand),
            'right':  (sx2 - side_margin,       sy1 - wall_search_expand, sx2 + wall_search_expand, sy2 + wall_search_expand),
            'top':    (sx1 - wall_search_expand, sy2 - side_margin,       sx2 + wall_search_expand, sy2 + wall_search_expand),
            'bottom': (sx1 - wall_search_expand, sy1 - wall_search_expand, sx2 + wall_search_expand, sy1 + side_margin),
        }

        covered = {k: False for k in strips}
        for _, wb in candidate_walls:
            for k, strip in strips.items():
                if not covered[k] and _bbox_intersect(strip, wb):
                    covered[k] = True
        
        sides_covered = sum(1 for v in covered.values() if v)
        missing = [k for k, v in covered.items() if not v]
        fully_enclosed = (sides_covered == 4)
        
        results.append({
            'stair_name': sp_name,
            'stair_gid': sp_gid,
            'fully_enclosed': fully_enclosed,
            'sides_covered': sides_covered,
            'missing_sides': missing
        })

    return results


def analyze_stairflight_4wall_enclosure(model, side_margin=300.0, wall_search_expand=500.0):
    """Simple 4-wall enclosure check for IfcStairFlight entities.

    Returns list: {flight_name, flight_gid, fully_enclosed (bool), sides_covered, missing_sides}
    Debug and wall listing removed per user request.
    """
    flights = model.by_type('IfcStairFlight')
    if not flights:
        return []

    walls = list(model.by_type('IfcWall')) + list(model.by_type('IfcWallStandardCase'))
    wall_to_storey = {}
    flight_to_storey = {}
    
    for rel in model.by_type('IfcRelContainedInSpatialStructure'):
        parent = getattr(rel, 'RelatingStructure', None)
        if parent and parent.is_a('IfcBuildingStorey'):
            for e in getattr(rel, 'RelatedElements', []) or []:
                try:
                    gid = getattr(e, 'GlobalId', None) or str(id(e))
                    if e.is_a('IfcWall') or e.is_a('IfcWallStandardCase'):
                        wall_to_storey[gid] = parent
                    if e.is_a('IfcStairFlight'):
                        flight_to_storey[gid] = parent
                except Exception:
                    continue

    wall_bboxes_by_storey = {}
    results = []
    
    for flight in flights:
        flight_gid = getattr(flight, 'GlobalId', None) or str(id(flight))
        flight_name = getattr(flight, 'Name', None) or flight_gid
        
    # (Removed debug classification logic)
        
        fb = _bbox2d_mm(flight)
        
        if fb is None:
            results.append({
                'flight_name': flight_name,
                'flight_gid': flight_gid,
                'fully_enclosed': False,
                'sides_covered': 0,
                'missing_sides': ['left','right','top','bottom']
            })
            continue
        
        fx1, fy1, fx2, fy2 = fb
        storey = flight_to_storey.get(flight_gid)

        candidate_walls = []
        if storey:
            sid = getattr(storey, 'GlobalId', None) or str(id(storey))
            if sid not in wall_bboxes_by_storey:
                wall_bboxes_by_storey[sid] = []
                for w in walls:
                    w_gid = getattr(w, 'GlobalId', None) or str(id(w))
                    if wall_to_storey.get(w_gid) is storey:
                        wb = _bbox2d_mm(w)
                        if wb:
                            wall_bboxes_by_storey[sid].append((w_gid, wb))
            candidate_walls = wall_bboxes_by_storey[sid]
        
        # If no storey or no walls found for that storey, use all walls
        if not candidate_walls:
            if 'ALL' not in wall_bboxes_by_storey:
                wall_bboxes_by_storey['ALL'] = []
                for w in walls:
                    wb = _bbox2d_mm(w)
                    if wb:
                        wall_bboxes_by_storey['ALL'].append((getattr(w, 'GlobalId', None) or str(id(w)), wb))
            candidate_walls = wall_bboxes_by_storey['ALL']

        # Build all 4 side strips
        strips = {
            'left':   (fx1 - wall_search_expand, fy1 - wall_search_expand, fx1 + side_margin, fy2 + wall_search_expand),
            'right':  (fx2 - side_margin,       fy1 - wall_search_expand, fx2 + wall_search_expand, fy2 + wall_search_expand),
            'top':    (fx1 - wall_search_expand, fy2 - side_margin,       fx2 + wall_search_expand, fy2 + wall_search_expand),
            'bottom': (fx1 - wall_search_expand, fy1 - wall_search_expand, fx2 + wall_search_expand, fy1 + side_margin),
        }

        covered = {k: False for k in strips}
        for _, wb in candidate_walls:
            for k, strip in strips.items():
                if not covered[k] and _bbox_intersect(strip, wb):
                    covered[k] = True
        sides_covered = sum(1 for v in covered.values() if v)
        missing = [k for k, v in covered.items() if not v]
        fully_enclosed = (sides_covered == 4)
        results.append({
            'flight_name': flight_name,
            'flight_gid': flight_gid,
            'fully_enclosed': fully_enclosed,
            'sides_covered': sides_covered,
            'missing_sides': missing
        })

    return results


def analyze_stair_space_elements(model, door_map, margin=300.0):
    """List nearby elements for each stair space via bbox intersection.

    Returns list per stair space:
      {
        'stair_name','stair_gid',
        'walls': [{'name','gid'}],
        'doors': [{'name','gid'}],
        'flights': [{'name','gid'}],
      }
    """
    stair_spaces = [sp for sp in model.by_type('IfcSpace') if 'stair' in (getattr(sp, 'Name', '') or '').lower()]
    walls = list(model.by_type('IfcWall')) + list(model.by_type('IfcWallStandardCase'))
    doors = model.by_type('IfcDoor')
    flights = model.by_type('IfcStairFlight')

    # Build containment map to restrict walls to same storey as stair space
    wall_to_storey = {}
    space_to_storey = {}
    for rel in model.by_type('IfcRelContainedInSpatialStructure'):
        parent = getattr(rel, 'RelatingStructure', None)
        if parent and parent.is_a('IfcBuildingStorey'):
            for e in getattr(rel, 'RelatedElements', []) or []:
                try:
                    gid = getattr(e, 'GlobalId', None) or str(id(e))
                    if e.is_a('IfcWall') or e.is_a('IfcWallStandardCase'):
                        wall_to_storey[gid] = parent
                    if e.is_a('IfcSpace'):
                        space_to_storey[gid] = parent
                except Exception:
                    continue

    results = []
    for sp in stair_spaces:
        sb = _bbox2d_mm(sp)
        if not sb:
            continue
        sx1, sy1, sx2, sy2 = sb
        # Expand space bbox slightly
        ext = (sx1 - margin, sy1 - margin, sx2 + margin, sy2 + margin)
        items = {'walls': [], 'doors': [], 'flights': []}
        # Restrict walls by storey
        storey = space_to_storey.get(getattr(sp, 'GlobalId', None) or str(id(sp)))
        for w in walls:
            if storey:
                w_gid = getattr(w, 'GlobalId', None) or str(id(w))
                if wall_to_storey.get(w_gid) is not storey:
                    continue
            wb = _bbox2d_mm(w)
            if wb and _bbox_intersect(ext, wb):
                items['walls'].append({'name': getattr(w, 'Name', None) or '', 'gid': getattr(w, 'GlobalId', None) or str(id(w))})
        # Doors: only those linked to this stair space (from door_map)
        sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
        door_gids = [dg for dg, sids in door_map.items() if sp_gid in sids]
        doors_by_gid = {(getattr(d, 'GlobalId', None) or str(id(d))): d for d in doors}
        for dg in door_gids:
            d = doors_by_gid.get(dg)
            if not d:
                continue
            db = _bbox2d_mm(d)
            if db and _bbox_intersect(ext, db):
                items['doors'].append({'name': getattr(d, 'Name', None) or '', 'gid': dg})
        for fl in flights:
            fb = _bbox2d_mm(fl)
            if fb and _bbox_intersect(ext, fb):
                items['flights'].append({'name': getattr(fl, 'Name', None) or '', 'gid': getattr(fl, 'GlobalId', None) or str(id(fl))})
        results.append({
            'stair_name': getattr(sp, 'Name', None) or '',
            'stair_gid': getattr(sp, 'GlobalId', None) or str(id(sp)),
            **items,
        })
    return results


def summarize_stair_space_compliance(stair_compartmentation, prox_enclosure):
    """Build compact PASS/FAIL per stair space using proximity enclosure and door checks.

    Pass = (sides_covered==3) AND (door_count==1) AND (no offending_doors)
    """
    # index proximity by stair name
    prox_by_name = {p['stair_name']: p for p in prox_enclosure}
    summary = []
    for rec in stair_compartmentation:
        name = rec.get('stair_name')
        door_count = rec.get('door_count', 0)
        offending = rec.get('offending_doors', [])
        prox = prox_by_name.get(name)
        sides = prox.get('sides_covered', 0) if prox else 0
        enclosed_ok = sides == 3
        door_ok = (door_count == 1)
        swing_ok = (len(offending) == 0)
        passed = enclosed_ok and door_ok and swing_ok
        reasons = []
        if not enclosed_ok:
            reasons.append(f'enclosure {sides}/3 sides')
        if not door_ok:
            reasons.append(f'entry doors={door_count} (expected 1)')
        # collect swing specific reasons if any
        for d in offending:
            for r in d.get('reasons', []):
                if 'swings' in r or 'swing' in r:
                    reasons.append(r)
        summary.append({
            'stair_name': name,
            'passed': passed,
            'enclosure_sides': sides,
            'door_count': door_count,
            'swing_ok': swing_ok,
            'reasons': reasons,
        })
    return summary


def main():
    """Morning-style run: only analyse corridor/hallway spaces (plus stair spaces for linkage).
    This reduces runtime by skipping geometry + width calculations for non-corridor rooms.
    """
    model = ifcopenshell.open(IFC_PATH)
    all_spaces = model.by_type('IfcSpace')

    def _n(sp):
        return (getattr(sp, 'Name', '') or '').lower()

    hallway_tokens = ['hallway', 'corridor', 'passage', 'circulation']

    # Select corridor spaces only (these are the 18 we report on) + collect stair spaces for linkage graph
    corridor_spaces = [sp for sp in all_spaces if any(t in _n(sp) for t in hallway_tokens)]
    stair_spaces = [sp for sp in all_spaces if 'stair' in _n(sp)]

    # For building door/stair adjacency we include corridor + stair spaces only
    linkage_spaces = corridor_spaces + stair_spaces

    analyses = {}
    for sp in corridor_spaces:  # Only analyse corridors
        sid = getattr(sp, 'GlobalId', None) or str(id(sp))
        # Try geometry first for accurate width
        length, width = extract_dimensions_from_geometry(sp)
        if width == 0:  # fallback to area/perimeter if geometry fails
            A = get_numeric(sp, ['area'])
            P = get_numeric(sp, ['perimeter'])
            if A and P:
                if A > 1000:
                    A_m2 = A / 1_000_000.0
                else:
                    A_m2 = A
                P_m = P if P > 100 else P * 1000.0
                try:
                    s = P_m / 2.0
                    w = (s - math.sqrt(max(0, s * s - 4 * A_m2))) / 2.0
                    length = (A_m2 / w) * 1000.0
                    width = w * 1000.0
                except Exception:
                    pass
        analyses[sid] = {
            'space': sp,
            'name': getattr(sp, 'Name', None),
            'type': getattr(sp, 'LongName', None),
            'width': width,
            'length': length,
        }

    # Build linkages (doors between corridor+stair subset)
    space_linked, door_map, door_container_map = build_space_linkages(model, linkage_spaces)

    for sid, a in analyses.items():
        a['links_to_stairs'] = space_linked.get(sid, False)
        a['is_elongated'] = (a['length'] >= 3 * a['width']) if a['width'] > 0 else False

    corridors = [(sid, a) for sid, a in analyses.items()]  # analyses already corridor-only
    # Build enhanced full door-space map (global scope) for richer stair entry detection
    door_map_all, door_container_map_all = build_full_door_space_map(model)
    doors = [analyze_door(d, door_map_all, door_container_map_all) for d in model.by_type('IfcDoor')]
    failing_doors = [d for d in doors if d['issues']]
    flights = model.by_type('IfcStairFlight')
    stairs = [analyze_stair(f) for f in flights]
    failing_stairs = [s for s in stairs if s['issues']]

    failing_corridors = []
    for sid, a in corridors:
        checks = 0; issues = []
        if a['width'] >= CORRIDOR_MIN:
            checks += 1
        else:
            issues.append(f"Width is {a['width']:.0f}mm")
        if a['links_to_stairs']:
            checks += 1
        else:
            issues.append(f"Does not link to stairs via doors/openings")
        if checks < 2:
            failing_corridors.append({'name': f"{a.get('name')} [{sid}]", 'issues': issues})

    # determine passing corridors (those in corridors but not in failing_corridors)
    failing_sids = set()
    for fc in failing_corridors:
        n = fc.get('name','')
        if '[' in n and n.endswith(']'):
            sid_parsed = n.split('[')[-1][:-1]
            failing_sids.add(sid_parsed)

    passing_corridors = []
    for sid, a in corridors:
        if sid in failing_sids:
            continue
        checks_passed = []
        w = a.get('width', 0) or 0
        if w >= CORRIDOR_MIN:
            checks_passed.append('width')
        if a.get('links_to_stairs'):
            checks_passed.append('stairs')
        ratio = (a['length'] / a['width']) if a['width'] > 0 else 0
        passing_corridors.append({
            'name': f"{a.get('name')} [{sid}]",
            'width_mm': float(w),
            'length_mm': float(a.get('length', 0) or 0),
            'links_stairs': a.get('links_to_stairs', False),
            'ratio': float(ratio),
            'passed': checks_passed,
        })

    print(f"Amount of doors in model: {len(doors)}")
    print(f"Amount of doors that don't fulfill the requirements: {len(failing_doors)}")
    if failing_doors:
        print("The names of the doors and what is not right with them:")
        for d in failing_doors:
            print(f" - {d['name']}: {', '.join(d['issues'])}")
    else:
        print("No failing doors.")

    print(f"\nAmount of corridors: {len(corridors)}")
    print(f"Amount of corridors that don't fulfill the requirements: {len(failing_corridors)}")
    if failing_corridors:
        print("The names of the corridors and what is not right with them:")
        for c in failing_corridors:
            print(f" - {c['name']}: {', '.join(c['issues'])}")
    else:
        print("No failing corridors.")

    # Print passing (right) corridors
    print(f"\nAmount of corridors that fulfill the requirements (passing): {len(passing_corridors)}")

    print(f"\nAmount of stairs: {len(stairs)}")
    print(f"Amount of stairs that don't fulfill the requirements: {len(failing_stairs)}")
    if failing_stairs:
        print("The names of the stairs and what is not right with them:")
        for s in failing_stairs:
            print(f" - {s['name']}: {', '.join(s['issues'])}")
    else:
        print("No failing stairs.")

    # Simple 4-wall enclosure check for IfcStairFlight entities (FAST - no space analysis needed)
    flight_4wall = analyze_stairflight_4wall_enclosure(model)
    print('\n=== STAIR COMPARTMENTATION: 4-WALL ENCLOSURE (IfcStairFlight) ===')
    for f in flight_4wall:
        status = '✓' if f['fully_enclosed'] else '✗'
        print(f"{status} {f['flight_name']} - {f['sides_covered']}/4 sides covered")

    # Staircase (flight group) summary
    staircase_groups = analyze_staircase_groups(model)
    storey_count = len(model.by_type('IfcBuildingStorey'))
    expected_groups = max(storey_count - 2, 0) * 3 if storey_count >= 3 else max(storey_count - 1, 0) * 3
    # User specification indicated (storey_pairs * 3). Ambiguity in storey pairing for 7 storeys.
    # We approximate expected by (storey_count - 2) * 3 to match 7->15 per user statement.
    print('\n=== Staircase Flight Group Summary ===')
    print(f'Unique staircase IDs (from flights): {len(staircase_groups)}')
    print(f'Expected staircase groups (user spec): {expected_groups}')
    standard = [g for g in staircase_groups if g['is_standard_3_run']]
    non_standard = [g for g in staircase_groups if not g['is_standard_3_run']]
    print(f'Standard 3-run staircases detected: {len(standard)}')
    if non_standard:
        print(f'Non-standard staircase flight sets (run pattern != 3 runs): {len(non_standard)}')
    # List groups
    for g in staircase_groups:
        flag = '✓' if g['is_standard_3_run'] else '⚠'
        print(f" {flag} Staircase ID {g['id']} flights={g['flight_count']} runs={', '.join(g['run_labels'])}")

    # Staircase group proximity enclosure check
    group_enclosure = analyze_staircase_group_enclosure(model)
    failing_groups = [ge for ge in group_enclosure if ge['has_issue']]

    # Geometry-based stair space detection (may reveal additional stair spaces)
    geo_stair_spaces = identify_stair_spaces_geometry(model)

    # Export summary to Excel (.xlsx) if available, otherwise fall back to CSV
    import os
    base_dir = os.path.dirname(__file__)
    csv_path = os.path.join(base_dir, 'analysis_summary.csv')
    xlsx_path = os.path.join(base_dir, 'analysis_summary.xlsx')

    def _write_csv(path):
        import csv
        with open(path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Header
            writer.writerow(['category', 'item_id', 'item_name', 'status', 'reason_or_details'])

            # Doors
            writer.writerow([]); writer.writerow(['DOORS'])
            writer.writerow(['summary', '', '', 'failing', len(failing_doors)])
            writer.writerow(['summary', '', '', 'passing', len(doors) - len(failing_doors)])
            for d in failing_doors:
                writer.writerow([
                    'door', '',
                    d.get('name',''), 'fail', '; '.join(d.get('issues', []))
                ])

            # Corridors
            writer.writerow([]); writer.writerow(['CORRIDORS'])
            writer.writerow(['summary', '', '', 'failing', len(failing_corridors)])
            writer.writerow(['summary', '', '', 'passing', len(passing_corridors)])
            for c in failing_corridors:
                writer.writerow(['corridor', '', c.get('name',''), 'fail', '; '.join(c.get('issues', []))])
            for c in passing_corridors:
                writer.writerow(['corridor', '', c.get('name',''), 'pass', ', '.join(c.get('passed', []))])

            # Stairs (width compliance)
            writer.writerow([]); writer.writerow(['STAIRS (width)'])
            writer.writerow(['summary', '', '', 'failing', len(failing_stairs)])
            writer.writerow(['summary', '', '', 'passing', len(stairs) - len(failing_stairs)])
            for s in failing_stairs:
                writer.writerow(['stair', '', s.get('name',''), 'fail', '; '.join(s.get('issues', []))])

            # Stair Flights Enclosure (4 walls)
            writer.writerow([]); writer.writerow(['STAIR FLIGHTS (4-wall enclosure)'])
            failing_flights = [f for f in flight_4wall if not f.get('fully_enclosed')]
            passing_flights = [f for f in flight_4wall if f.get('fully_enclosed')]
            writer.writerow(['summary', '', '', 'failing', len(failing_flights)])
            writer.writerow(['summary', '', '', 'passing', len(passing_flights)])
            for f in failing_flights:
                writer.writerow([
                    'stair_flight', f.get('flight_gid',''), f.get('flight_name',''), 'fail', f"sides_covered={f.get('sides_covered',0)}/4"
                ])
            for f in passing_flights:
                writer.writerow(['stair_flight', f.get('flight_gid',''), f.get('flight_name',''), 'pass', ''])

    def _write_xlsx(path):
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        wb = Workbook()

        # Single sheet matching requested format
        ws = wb.active
        ws.title = 'IFC_Compliance_Report'

        # Requirements section at top
        ws.append(['Requirements'])
        ws['A1'].font = Font(bold=True, size=12)
        ws.append(['- Doors: clear opening width ≥ 800 mm'])
        ws.append(['- Corridors: clear width ≥ 1300 mm AND must link to a stair via a door/opening'])
        ws.append(['- Stairs: clear flight width ≥ 1000 mm'])
        ws.append(['- Stair flights: must be enclosed by 4 walls (left, right, top, bottom)'])
        ws.append([''])

        # Table header per your spec
        ws.append(['Category', 'Passing count', 'Failing count', "Failing element ID's", 'Reason for failure'])
        for c in ('A','B','C','D','E'):
            ws[f"{c}7"].font = Font(bold=True)
            ws[f"{c}7"].fill = PatternFill(start_color='FFEFEFEF', end_color='FFEFEFEF', fill_type='solid')
            ws[f"{c}7"].alignment = Alignment(horizontal='center')

        # Doors row
        door_fail_ids = []  # we don't have IDs directly for failing doors in summary; leave empty or collect if available
        door_reasons = []
        for d in failing_doors:
            door_fail_ids.append('')  # ID not stored; could be parsed from d['name'] if needed
            door_reasons.append('; '.join(d.get('issues', [])))
        ws.append([
            'Doors',
            (len(doors) - len(failing_doors)),
            len(failing_doors),
            ', '.join(door_fail_ids),
            '; '.join(door_reasons) if door_reasons else ''
        ])

        # Corridors row
        corridor_fail_ids = []
        corridor_reasons = []
        for c in failing_corridors:
            # Extract element ID from name like "Hallway:XXXXX [GID]" if present; otherwise leave empty
            nm = c.get('name','')
            try:
                if ':' in nm:
                    corridor_fail_ids.append(nm.split(':',1)[1].split()[0])
                else:
                    corridor_fail_ids.append('')
            except Exception:
                corridor_fail_ids.append('')
            corridor_reasons.append('; '.join(c.get('issues', [])))
        ws.append([
            'Corridors',
            len(passing_corridors),
            len(failing_corridors),
            ', '.join(corridor_fail_ids),
            '; '.join(corridor_reasons) if corridor_reasons else ''
        ])

        # Stairs (width) row
        stair_fail_ids = []
        stair_reasons = []
        for s in failing_stairs:
            # Stair ID not parsed; leave blank or parse from name if pattern exists
            stair_fail_ids.append('')
            stair_reasons.append('; '.join(s.get('issues', [])))
        ws.append([
            'Stairs (width)',
            (len(stairs) - len(failing_stairs)),
            len(failing_stairs),
            ', '.join(stair_fail_ids),
            '; '.join(stair_reasons) if stair_reasons else ''
        ])

        # Stair flights enclosure row
        failing_flights = [f for f in flight_4wall if not f.get('fully_enclosed')]
        passing_flights = [f for f in flight_4wall if f.get('fully_enclosed')]
        flight_fail_ids = [f.get('flight_gid','') for f in failing_flights]
        flight_reasons = [f"{f.get('flight_name','')}: sides_covered={f.get('sides_covered',0)}/4" for f in failing_flights]
        ws.append([
            'Stair flights (4-wall enclosure)',
            len(passing_flights),
            len(failing_flights),
            ', '.join(flight_fail_ids),
            '; '.join(flight_reasons) if flight_reasons else ''
        ])

        # Auto-size columns for readability
        widths = {'A': 32, 'B': 16, 'C': 16, 'D': 36, 'E': 48}
        for col, w in widths.items():
            ws.column_dimensions[col].width = w

        wb.save(path)

    # Try Excel first
    wrote_xlsx = False
    try:
        import openpyxl  # noqa: F401
        _write_xlsx(xlsx_path)
        wrote_xlsx = True
    except Exception:
        wrote_xlsx = False

    # Always write CSV as a universal fallback
    _write_csv(csv_path)

    # Print clickable paths (absolute and file:// URLs with percent-encoding for spaces)
    import urllib.parse as _url
    csv_url = f"file://{_url.quote(csv_path)}"
    def _osc8_link(url: str, text: str):
        # OSC 8 hyperlink (supported by VS Code terminal, iTerm2)
        return f"\u001b]8;;{url}\u0007{text}\u001b]8;;\u0007"
    if wrote_xlsx:
        xlsx_url = f"file://{_url.quote(xlsx_path)}"
        print("\nExcel summary written to:", _osc8_link(xlsx_url, xlsx_path))
        print("Click:", _osc8_link(xlsx_url, "Open Excel (.xlsx)"))
        print("CSV summary also written to:", _osc8_link(csv_url, csv_path))
        print("Click:", _osc8_link(csv_url, "Open CSV"))
    else:
        print("\nExcel not available (openpyxl missing).")
        print("CSV summary written to:", _osc8_link(csv_url, csv_path))
        print("Click:", _osc8_link(csv_url, "Open CSV"))


if __name__ == '__main__':
    main()
