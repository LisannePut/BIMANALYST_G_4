import ifcopenshell
import os
import math

# Config
IFC_PATH = os.path.join(os.path.dirname(__file__), "model", "25-16-D-ARCH.ifc")
DOOR_MIN = 800
STAIR_MIN = 1000
BUFFER_BBOX = 1000.0
NEAREST_MAX = 30000.0


def to_mm(v):
    try:
        f = float(v)
    except Exception:
        return None
    return f if f > 100 else f * 1000.0


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
    if not getattr(elem, 'Representation', None):
        return None
    for rep in elem.Representation.Representations:
        for it in getattr(rep, 'Items', []) or []:
            c = centroid_from_extruded(it)
            if c:
                return c
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
    bboxes = build_space_bboxes(spaces)
    centroids = { (getattr(s, 'GlobalId', None) or str(id(s))): get_element_centroid(s) for s in spaces }
    door_to_spaces = {}
    door_to_opening = {}
    for rel in model.by_type('IfcRelFillsElement'):
        opening = getattr(rel, 'RelatingOpeningElement', None)
        elem = getattr(rel, 'RelatedBuildingElement', None)
        if not (opening and elem and elem.is_a('IfcDoor')):
            continue
        did = getattr(elem, 'GlobalId', None)
        oc = get_element_centroid(opening) or get_element_centroid(elem)
        if not oc:
            continue
        touching = set()
        for sid, box in bboxes.items():
            if not box:
                continue
            xmin, ymin, xmax, ymax = box
            if xmin - BUFFER_BBOX <= oc[0] <= xmax + BUFFER_BBOX and ymin - BUFFER_BBOX <= oc[1] <= ymax + BUFFER_BBOX:
                touching.add(sid)
        if not touching:
            dists = []
            for sid, c in centroids.items():
                if not c:
                    continue
                dist = math.sqrt((oc[0]-c[0])**2 + (oc[1]-c[1])**2 + (oc[2]-c[2])**2)
                dists.append((dist, sid))
            dists.sort()
            for dist, sid in dists[:2]:
                if dist <= NEAREST_MAX:
                    touching.add(sid)
        if touching:
            door_to_spaces[did] = touching
            door_to_opening[did] = opening
    # adjacency
    space_linked = {}
    for sid_set in door_to_spaces.values():
        lst = list(sid_set)
        for s in lst:
            others = set(lst) - {s}
            if others:
                space_linked.setdefault(s, set()).update(others)
    for s in spaces:
        sid = getattr(s, 'GlobalId', None) or str(id(s))
        space_linked.setdefault(sid, set())
    return space_linked, door_to_spaces, door_to_opening


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
    if analysis.get('is_elongated') and analysis.get('links_multiple_rooms'):
        return True
    return False


def main():
    model = ifcopenshell.open(IFC_PATH)
    spaces = model.by_type('IfcSpace')
    analyses = {}
    for sp in spaces:
        sid = getattr(sp, 'GlobalId', None) or str(id(sp))
        length = width = 0
        if getattr(sp, 'Representation', None):
            for rep in sp.Representation.Representations:
                for it in getattr(rep, 'Items', []) or []:
                    if it.is_a('IfcExtrudedAreaSolid'):
                        prof = getattr(it, 'SweptArea', None)
                        if prof and prof.is_a('IfcRectangleProfileDef'):
                            xd = float(getattr(prof, 'XDim', 0) or 0)
                            yd = float(getattr(prof, 'YDim', 0) or 0)
                            xd = xd if xd > 100 else xd * 1000.0
                            yd = yd if yd > 100 else yd * 1000.0
                            length = max(xd, yd); width = min(xd, yd)
        if width == 0:
            A = get_numeric(sp, ['area'])
            P = get_numeric(sp, ['perimeter'])
            if A and P:
                if A > 1000:
                    A_m2 = A / 1000000.0
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
        analyses[sid] = {'space': sp, 'name': getattr(sp, 'Name', None), 'type': getattr(sp, 'LongName', None), 'width': width, 'length': length}

    space_linked, door_map, open_map = build_space_linkages(model, spaces)
    for sid, a in analyses.items():
        linked = space_linked.get(sid, set())
        a['linked_rooms_count'] = len(linked)
        a['links_multiple_rooms'] = len(linked) >= 2
        a['is_elongated'] = (a['length'] >= 3 * a['width']) if a['width'] > 0 else False

    corridors = [(sid, a) for sid, a in analyses.items() if is_corridor(a['space'], a)]
    doors = [analyze_door(d, door_map, open_map) for d in model.by_type('IfcDoor')]
    failing_doors = [d for d in doors if d['issues']]
    flights = model.by_type('IfcStairFlight')
    stairs = [analyze_stair(f) for f in flights]
    failing_stairs = [s for s in stairs if s['issues']]

    failing_corridors = []
    for sid, a in corridors:
        checks = 0; issues = []
        if a['width'] >= 1300:
            checks += 1
        else:
            issues.append(f"Width is {a['width']:.0f}mm")
        if a['is_elongated']:
            checks += 1
        else:
            ratio = (a['length'] / a['width']) if a['width'] > 0 else 0
            issues.append(f"Length ({a['length']:.0f}mm) is {ratio:.1f}x width")
        if a['links_multiple_rooms']:
            checks += 1
        else:
            issues.append(f"Links to {a.get('linked_rooms_count', 0)} other room(s) via doors/openings")
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
        if w >= 1300:
            checks_passed.append('width')
        if a.get('is_elongated'):
            checks_passed.append('elongation')
        if a.get('links_multiple_rooms'):
            checks_passed.append('links')
        ratio = (a['length'] / a['width']) if a['width'] > 0 else 0
        passing_corridors.append({
            'name': f"{a.get('name')} [{sid}]",
            'width_mm': w,
            'length_mm': a.get('length', 0) or 0,
            'links': a.get('linked_rooms_count', 0),
            'ratio': ratio,
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
    if passing_corridors:
        print("The passing corridors (name [GlobalId]):")
        for p in passing_corridors:
            print(f" - {p}")
    else:
        print("No passing corridors found.")

    print(f"\nAmount of stairs: {len(stairs)}")
    print(f"Amount of stairs that don't fulfill the requirements: {len(failing_stairs)}")
    if failing_stairs:
        print("The names of the stairs and what is not right with them:")
        for s in failing_stairs:
            print(f" - {s['name']}: {', '.join(s['issues'])}")
    else:
        print("No failing stairs.")


if __name__ == '__main__':
    main()
