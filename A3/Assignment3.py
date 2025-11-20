import ifcopenshell
import os
import math


def get_property(entity, property_name, property_set_name=None):
    """Get a property value from an IFC entity"""
    try:
        if hasattr(entity, "IsDefinedBy"):
            for definition in entity.IsDefinedBy:
                if definition.is_a("IfcRelDefinesByProperties"):
                    property_set = definition.RelatingPropertyDefinition
                    # IfcPropertySet (IfcPropertySingleValue, etc.)
                    if property_set.is_a("IfcPropertySet"):
                        # compare property set name case-insensitively when provided
                        if property_set_name and getattr(property_set, 'Name', '').lower() != property_set_name.lower():
                            continue
                        for prop in getattr(property_set, 'HasProperties', []) or []:
                            # compare property name case-insensitively
                            try:
                                prop_name = getattr(prop, 'Name', '')
                                prop_name_l = prop_name.lower() if prop_name else ''
                            except Exception:
                                prop_name_l = ''
                            if prop_name_l == (property_name or '').lower():
                                # IfcPropertySingleValue
                                if hasattr(prop, "NominalValue") and prop.NominalValue:
                                    try:
                                        return prop.NominalValue.wrappedValue
                                    except Exception:
                                        return prop.NominalValue
                                # other property types may be added if needed
                    # IfcElementQuantity (holds IfcQuantityLength, IfcQuantityArea, ...)
                    if property_set.is_a('IfcElementQuantity'):
                        if property_set_name and getattr(property_set, 'Name', '').lower() != property_set_name.lower():
                            continue
                        for qty in getattr(property_set, 'Quantities', []) or []:
                            try:
                                qty_name = getattr(qty, 'Name', '')
                                if qty_name and qty_name.lower() == (property_name or '').lower():
                                    # IfcQuantityLength
                                    if qty.is_a('IfcQuantityLength') and hasattr(qty, 'LengthValue'):
                                        return getattr(qty, 'LengthValue')
                                    # IfcQuantityArea
                                    if qty.is_a('IfcQuantityArea') and hasattr(qty, 'AreaValue'):
                                        return getattr(qty, 'AreaValue')
                                    # IfcQuantityVolume
                                    if qty.is_a('IfcQuantityVolume') and hasattr(qty, 'VolumeValue'):
                                        return getattr(qty, 'VolumeValue')
                            except Exception:
                                continue
    except Exception:
        pass
    return None


def get_space_name(space):
    """Get the name of a space"""
    name = get_property(space, "Name")
    if not name:
        name = get_property(space, "LongName")
    if not name and hasattr(space, "Name"):
        name = space.Name
    return name


def get_space_type(space):
    """Get the space type from properties"""
    type_value = get_property(space, "ObjectType")
    if not type_value:
        type_value = get_property(space, "Category")
    return type_value


def get_space_dimensions_from_geometry(space):
    """Extract actual dimensions from the space's geometric representation"""
    try:
        if hasattr(space, 'Representation') and space.Representation:
            for rep in space.Representation.Representations:
                if hasattr(rep, 'Items'):
                    for item in rep.Items:
                        if item.is_a('IfcExtrudedAreaSolid'):
                            if hasattr(item, 'SweptArea') and item.SweptArea:
                                profile = item.SweptArea
                                if profile.is_a('IfcRectangleProfileDef'):
                                    x_dim = float(profile.XDim)
                                    y_dim = float(profile.YDim)
                                    # Detect units: if values are large (>100) assume they are already in mm,
                                    # otherwise assume meters and convert to mm.
                                    if x_dim > 100 or y_dim > 100:
                                        x_mm = x_dim
                                        y_mm = y_dim
                                    else:
                                        x_mm = x_dim * 1000.0
                                        y_mm = y_dim * 1000.0
                                    length = max(x_mm, y_mm)
                                    width = min(x_mm, y_mm)
                                    return (length, width)
    except Exception:
        pass
    return (None, None)


def analyze_space(space):
    """Analyze a space and return its characteristics"""
    name = get_space_name(space)
    space_type = get_space_type(space)
    
    # Try to get actual dimensions from geometry
    length, width = get_space_dimensions_from_geometry(space)
    
    # If we couldn't get dimensions from geometry, try from properties
    if length is None or width is None:
        area = get_property(space, "Area", "Dimensions")
        perimeter = get_property(space, "Perimeter", "Dimensions")
        
        if not area:
            return None
        
        # Convert area to square meters if needed
        area = float(area)
        if area > 1000:
            area = area / 1000000
        
        # Use perimeter to get a better estimate of dimensions
        if perimeter:
            perimeter = float(perimeter)
            P = perimeter / 2
            A = area
            discriminant = P * P - 4 * A
            if discriminant > 0:
                width = (P - math.sqrt(discriminant)) / 2
                length = area / width
            else:
                width = math.sqrt(area / 3)
                length = area / width
        else:
            width = math.sqrt(area / 3)
            length = area / width
        
        # Convert to millimeters for checking requirements
        width *= 1000
        length *= 1000
    else:
        # Dimensions are already in millimeters from geometry
        area = (length * width) / 1000000
    
    # Check if this might be a corridor based on name or type
    keywords = ["hallway", "corridor", "circulation", "passage"]
    is_named_corridor = any(keyword in (name or "").lower() for keyword in keywords)
    is_typed_corridor = any(keyword in (space_type or "").lower() for keyword in keywords)
    
    # Avoid division by zero
    if width == 0 or length == 0:
        return None
    
    return {
        "name": name,
        "type": space_type,
        "area": area,
        "width": width,
        "length": length,
        "is_elongated": length >= 3 * width,
        "is_named_corridor": is_named_corridor,
        "is_typed_corridor": is_typed_corridor,
        # placeholders to be filled later when adjacency info is available
        "linked_rooms_count": 0,
        "links_multiple_rooms": False,
        "is_inferred_corridor": False
    }


def check_requirements(analysis):
    """Check all requirements and return results"""
    MIN_WIDTH = 1300  # minimum width in mm
    MIN_LENGTH_WIDTH_RATIO = 3  # minimum ratio of length to width for corridors
    
    checks = {
        "width": {
            "value": analysis["width"],
            "requirement": f">= {MIN_WIDTH}mm",
            "pass": analysis["width"] >= MIN_WIDTH,
            "message": f"Width is {analysis['width']:.0f}mm"
        },
        "elongation": {
            "value": analysis["length"] / analysis["width"] if analysis["width"] > 0 else 0,
            "requirement": f">= {MIN_LENGTH_WIDTH_RATIO}x width",
            "pass": analysis["is_elongated"],
            "message": f"Length ({analysis['length']:.0f}mm) is {analysis['length']/analysis['width']:.1f}x width" if analysis["width"] > 0 else "Cannot calculate ratio"
        },
        "links_rooms": {
            "value": analysis.get("linked_rooms_count", 0),
            "requirement": ">= 2 linked rooms to be considered a corridor (inferred)",
            "pass": analysis.get("links_multiple_rooms", False),
            "message": f"Links to {analysis.get('linked_rooms_count', 0)} other room(s) via doors/openings"
        },
        "area": {
            "value": analysis["area"],
            "requirement": "informational",
            "pass": True,
            "message": f"Area is {analysis['area']:.1f}m²"
        },
        "identification": {
            "value": analysis["is_named_corridor"] or analysis["is_typed_corridor"],
            "requirement": "informational",
            "pass": True,
            "message": f"Space {'is' if analysis['is_named_corridor'] or analysis['is_typed_corridor'] else 'is not'} identified as corridor in the model"
        }
    }
    
    return checks


def build_opening_to_spaces_map(model):
    """Build a mapping from opening/building element to the set of spaces that border it.

    Uses IfcRelSpaceBoundary relations where possible. Keys are element instances (opening, wall, etc.).
    Returns a dict: element -> set(spaces)
    """
    # Map by element.GlobalId (string) -> set of space GlobalIds
    opening_to_spaces = {}
    try:
        # Primary: IfcRelSpaceBoundary directly relates spaces to elements (openings/walls)
        for rel in model.by_type("IfcRelSpaceBoundary"):
            try:
                space = rel.RelatingSpace
                related = rel.RelatedBuildingElement
                if space and related:
                    key = getattr(related, 'GlobalId', None) or str(id(related))
                    opening_to_spaces.setdefault(key, set()).add(getattr(space, 'GlobalId', None) or str(id(space)))
            except Exception:
                continue

        # Secondary: IfcRelContainedInSpatialStructure links elements to spaces (containment)
        for rel in model.by_type("IfcRelContainedInSpatialStructure"):
            try:
                space = rel.RelatingStructure
                for elem in rel.RelatedElements:
                    if space and elem:
                        key = getattr(elem, 'GlobalId', None) or str(id(elem))
                        opening_to_spaces.setdefault(key, set()).add(getattr(space, 'GlobalId', None) or str(id(space)))
            except Exception:
                continue
    except Exception:
        pass
    return opening_to_spaces


def build_space_linkages_via_doors(model, spaces):
    """Build mapping from each space to the set of other spaces it's linked to via doors/openings.

    Since this model lacks IfcRelSpaceBoundary relations, use GEOMETRY to infer connectivity:
      - For each door/opening, find the 2 nearest spaces by centroid distance
      - Link those two spaces as adjacent
    
    Returns: dict space -> set(other_spaces)
    """
    # Build a map of openings -> spaces using explicit IFC relations where available
    opening_to_spaces_rel = build_opening_to_spaces_map(model)

    # Build space centroids and bboxes for geometric analysis
    space_bboxes = build_space_bboxes(spaces)
    space_centroids = {}
    for sp in spaces:
        sp_id = getattr(sp, 'GlobalId', None) or str(id(sp))
        cent = get_element_centroid(sp)
        if cent:
            space_centroids[sp_id] = cent

    # door_id (GlobalId) -> set(space GlobalId)
    door_to_spaces = {}
    # door_id -> opening element (object) if known
    door_to_opening = {}

    # Create a map of door GlobalId -> door object for lookup
    door_by_id = {}
    for door in model.by_type("IfcDoor"):
        door_id = getattr(door, 'GlobalId', None)
        if door_id:
            door_by_id[door_id] = door

    # Collect all doors and their openings via IfcRelFillsElement
    # Strategy: For each opening, find which spaces' bboxes contain it, and check nearby spaces
    try:
        for rel in model.by_type("IfcRelFillsElement"):
            try:
                opening = rel.RelatingOpeningElement
                element = rel.RelatedBuildingElement
                # Only consider actual doors
                if not (opening and element and element.is_a('IfcDoor')):
                    continue

                door_global_id = getattr(element, 'GlobalId', None)
                if not door_global_id:
                    continue

                spaces_touching = set()

                # First: try explicit IFC relations map (IfcRelSpaceBoundary / IfcRelContainedInSpatialStructure)
                opening_key = getattr(opening, 'GlobalId', None) or str(id(opening))
                related_spaces = opening_to_spaces_rel.get(opening_key)
                if related_spaces:
                    spaces_touching.update(related_spaces)

                # If relation-based mapping didn't yield anything, fall back to geometry
                if not spaces_touching:
                    # Get opening centroid; if not available, try the door element centroid as a fallback
                    opening_cent = get_element_centroid(opening)
                    if not opening_cent:
                        opening_cent = get_element_centroid(element)
                    if not opening_cent:
                        continue

                    # Strategy 1: Buffered bbox containment (expand bbox by a buffer)
                    # Use a larger buffer to account for unit inconsistencies in some exports
                    BUFFER = 1000.0
                    for sp_id, bbox in space_bboxes.items():
                        if bbox and len(bbox) >= 4:
                            xmin, ymin, xmax, ymax = bbox[0] - BUFFER, bbox[1] - BUFFER, bbox[2] + BUFFER, bbox[3] + BUFFER
                            if xmin <= opening_cent[0] <= xmax and ymin <= opening_cent[1] <= ymax:
                                spaces_touching.add(sp_id)

                    # Strategy 2: If still none, find nearest spaces by 3D centroid distance with a relaxed threshold
                    if not spaces_touching:
                        distances = []
                        for sp_id, cent in space_centroids.items():
                            try:
                                dist = math.sqrt((opening_cent[0] - cent[0])**2 + 
                                               (opening_cent[1] - cent[1])**2 + 
                                               (opening_cent[2] - cent[2])**2)
                            except Exception:
                                # fallback to 2D distance
                                dist = math.sqrt((opening_cent[0] - cent[0])**2 + (opening_cent[1] - cent[1])**2)
                            distances.append((dist, sp_id))
                        distances.sort()
                        # Allow a larger max distance in case coordinates are in mm (e.g., 30000 mm = 30 m)
                        for dist, sp_id in distances:
                            if dist <= 30000 and len(spaces_touching) < 2:
                                spaces_touching.add(sp_id)

                if spaces_touching:
                    door_to_spaces[door_global_id] = spaces_touching
                    door_to_opening[door_global_id] = opening
            except Exception:
                continue
    except Exception:
        pass

    # Build space adjacency from door connections
    space_linked = {}
    for door_id, sset in door_to_spaces.items():
        s_list = list(sset)
        for s in s_list:
            others = set(s_list) - {s}
            if others:
                space_linked.setdefault(s, set()).update(others)

    # Ensure every provided space has an entry (even if empty)
    for sp in spaces:
        sp_id = getattr(sp, 'GlobalId', None) or str(id(sp))
        space_linked.setdefault(sp_id, set())

    return space_linked, door_to_spaces, door_to_opening


def _get_numeric_property(entity, names):
    """Try multiple property names and return a float value in mm if found.

    Accepts area/width stored in meters — converted to mm if appropriate.
    """
    # First try entity attributes (some exporters put dimensions as attributes)
    for n in names:
        try:
            # direct attribute (case-sensitive)
            if hasattr(entity, n):
                val = getattr(entity, n)
                if val is not None:
                    try:
                        num = float(val)
                        if num <= 100:
                            return num * 1000.0
                        return num
                    except Exception:
                        pass
            # case-insensitive attribute check
            for attr in dir(entity):
                try:
                    if attr.lower() == n.lower():
                        val = getattr(entity, attr)
                        if val is not None:
                            num = float(val)
                            if num <= 100:
                                return num * 1000.0
                            return num
                except Exception:
                    continue
        except Exception:
            continue

    # Try common property set names explicitly first (your model uses 'Dimensions')
    psets = ["Dimensions", "Pset_DoorCommon", "PSet_DoorCommon", "Pset_StairCommon", "Pset_StairFlightCommon"]
    for pset in psets:
        for n in names:
            val = get_property(entity, n, pset)
            if val is None:
                continue
            try:
                num = float(val)
            except Exception:
                continue
            if num <= 100:
                return num * 1000.0
            return num

    # Try without specifying a property set (search all PSets)
    for n in names:
        val = get_property(entity, n)
        if val is not None:
            try:
                num = float(val)
            except Exception:
                continue
            if num <= 100:
                return num * 1000.0
            return num

    return None


def _find_numeric_by_substring(entity, substrings=None):
    """Scan all property-sets and quantities for property names containing any of the substrings.

    Returns first numeric value found (converted to mm if appropriate), else None.
    """
    if substrings is None:
        substrings = ["width"]
    subs = [s.lower() for s in substrings]

    # Search IfcPropertySet entries
    for definition in getattr(entity, 'IsDefinedBy', []) or []:
        try:
            if not definition.is_a('IfcRelDefinesByProperties'):
                continue
            pdef = definition.RelatingPropertyDefinition
            if pdef is None:
                continue
            # Property sets
            if pdef.is_a('IfcPropertySet'):
                for prop in getattr(pdef, 'HasProperties', []) or []:
                    pname = getattr(prop, 'Name', '')
                    if not pname:
                        continue
                    pname_l = pname.lower()
                    for sub in subs:
                        if sub in pname_l:
                            # try to extract numeric value
                            try:
                                if hasattr(prop, 'NominalValue') and prop.NominalValue is not None:
                                    val = prop.NominalValue.wrappedValue
                                else:
                                    # skip non single-value properties
                                    continue
                                num = float(val)
                                if num <= 100:
                                    return num * 1000.0
                                return num
                            except Exception:
                                continue
            # Quantities
            if pdef.is_a('IfcElementQuantity'):
                for qty in getattr(pdef, 'Quantities', []) or []:
                    qname = getattr(qty, 'Name', '')
                    if not qname:
                        continue
                    qname_l = qname.lower()
                    for sub in subs:
                        if sub in qname_l:
                            try:
                                val = getattr(qty, 'LengthValue', None) or getattr(qty, 'AreaValue', None) or getattr(qty, 'VolumeValue', None)
                                if val is None:
                                    continue
                                num = float(val)
                                if num <= 100:
                                    return num * 1000.0
                                return num
                            except Exception:
                                continue
        except Exception:
            continue
    return None


def get_opening_dimensions_from_geometry(opening):
    """Try to extract opening dimensions (length, width) from opening geometry.

    Returns tuple (length_mm, width_mm) or (None, None).
    """
    try:
        if not hasattr(opening, 'Representation') or not opening.Representation:
            return (None, None)
        for rep in opening.Representation.Representations:
            if hasattr(rep, 'Items'):
                for item in rep.Items:
                    if item.is_a('IfcExtrudedAreaSolid'):
                        profile = getattr(item, 'SweptArea', None)
                        if profile and profile.is_a('IfcRectangleProfileDef'):
                            x = float(profile.XDim)
                            y = float(profile.YDim)
                            if x > 100 or y > 100:
                                x_mm = x
                                y_mm = y
                            else:
                                x_mm = x * 1000.0
                                y_mm = y * 1000.0
                            length = max(x_mm, y_mm)
                            width = min(x_mm, y_mm)
                            return (length, width)
    except Exception:
        pass
    return (None, None)


def _to_meters(val):
    try:
        v = float(val)
    except Exception:
        return None
    # If value looks like mm (>100) convert to meters
    if v > 100:
        return v / 1000.0
    return v


def get_element_centroid(element):
    """Try to get a 3D point (x,y,z) from an element's representation.

    For IfcExtrudedAreaSolid, compute centroid from base position + profile center + height/2.
    Returns coordinates in model units (usually meters) or None.
    """
    try:
        if not hasattr(element, 'Representation') or not element.Representation:
            return None
        for rep in element.Representation.Representations:
            for item in getattr(rep, 'Items', []) or []:
                # IfcExtrudedAreaSolid: compute centroid from profile + extrusion
                if item.is_a('IfcExtrudedAreaSolid'):
                    try:
                        pos = getattr(item, 'Position', None)
                        if not pos:
                            continue
                        
                        loc = getattr(pos, 'Location', None)
                        if not loc or not getattr(loc, 'Coordinates', None):
                            continue
                        
                        base_coords = list(loc.Coordinates)
                        base_x = float(base_coords[0])
                        base_y = float(base_coords[1])
                        base_z = float(base_coords[2]) if len(base_coords) > 2 else 0.0
                        
                        # Get extrusion height
                        height = float(getattr(item, 'Height', 0)) if hasattr(item, 'Height') else 0
                        
                        # Get profile centroid if available (RectangleProfileDef)
                        profile = getattr(item, 'SweptArea', None)
                        if profile and profile.is_a('IfcRectangleProfileDef'):
                            # Centroid relative to profile's position
                            profile_pos = getattr(profile, 'Position', None)
                            x_dim = float(getattr(profile, 'XDim', 0))
                            y_dim = float(getattr(profile, 'YDim', 0))
                            # Profile center is at (x_dim/2, y_dim/2) relative to profile position
                            if profile_pos and getattr(profile_pos, 'Location', None):
                                p_coords = list(profile_pos.Location.Coordinates)
                                profile_x = float(p_coords[0]) if len(p_coords) > 0 else 0
                                profile_y = float(p_coords[1]) if len(p_coords) > 1 else 0
                            else:
                                profile_x = 0
                                profile_y = 0
                            
                            cent_x = base_x + profile_x + x_dim / 2.0
                            cent_y = base_y + profile_y + y_dim / 2.0
                            cent_z = base_z + height / 2.0
                            return (cent_x, cent_y, cent_z)
                        else:
                            # No profile info: use base location + height/2
                            return (base_x, base_y, base_z + height / 2.0)
                    except Exception:
                        pass
                
                # IfcFacetedBrep: try to extract vertices and compute centroid
                if item.is_a('IfcFacetedBrep'):
                    try:
                        outer_shell = getattr(item, 'OuterBoundary', None)
                        if outer_shell:
                            vertices = []
                            for bound in getattr(outer_shell, 'CfaceBounds', []):
                                if hasattr(bound, 'Bound'):
                                    loop = bound.Bound
                                    for pt in getattr(loop, 'PolygonalBoundary', []):
                                        if hasattr(pt, 'Coordinates'):
                                            coords = list(pt.Coordinates)
                                            vertices.append((float(coords[0]), float(coords[1]), float(coords[2]) if len(coords) > 2 else 0))
                            if vertices:
                                x_avg = sum(v[0] for v in vertices) / len(vertices)
                                y_avg = sum(v[1] for v in vertices) / len(vertices)
                                z_avg = sum(v[2] for v in vertices) / len(vertices)
                                return (x_avg, y_avg, z_avg)
                    except Exception:
                        pass
        
        return None
    except Exception:
        return None


def build_space_bboxes(spaces):
    """Build simple 2D axis-aligned bounding boxes (xmin,ymin,xmax,ymax) for each space from geometry.

    Uses IfcExtrudedAreaSolid positions and rectangle profile dims when available. Returns dict space_id->bbox (meters).
    """
    bboxes = {}
    for sp in spaces:
        sp_id = getattr(sp, 'GlobalId', None) or str(id(sp))
        xmin = ymin = float('inf')
        xmax = ymax = float('-inf')
        found = False
        try:
            if hasattr(sp, 'Representation') and sp.Representation:
                for rep in sp.Representation.Representations:
                    for item in getattr(rep, 'Items', []) or []:
                        if item.is_a('IfcExtrudedAreaSolid'):
                            pos = getattr(item, 'Position', None)
                            if not pos or not getattr(pos, 'Location', None) or not getattr(pos.Location, 'Coordinates', None):
                                continue
                            coords = list(pos.Location.Coordinates)
                            x = float(coords[0])
                            y = float(coords[1])
                            profile = getattr(item, 'SweptArea', None)
                            if profile and profile.is_a('IfcRectangleProfileDef'):
                                # Convert profile dims to model units (this IFC uses millimeters here)
                                try:
                                    px = getattr(profile, 'XDim', None)
                                    py = getattr(profile, 'YDim', None)
                                    if px is None or py is None:
                                        continue
                                    # If values look like meters (<100) convert to mm, otherwise assume already mm
                                    xdim_mm = float(px) * 1000.0 if float(px) <= 100 else float(px)
                                    ydim_mm = float(py) * 1000.0 if float(py) <= 100 else float(py)
                                except Exception:
                                    continue
                                hx = xdim_mm / 2.0
                                hy = ydim_mm / 2.0
                                # Ensure position coordinates are in the same unit (model uses mm)
                                xmin = min(xmin, x - hx)
                                ymin = min(ymin, y - hy)
                                xmax = max(xmax, x + hx)
                                ymax = max(ymax, y + hy)
                                found = True
                            else:
                                # fallback: treat the position point as footprint
                                xmin = min(xmin, x)
                                ymin = min(ymin, y)
                                xmax = max(xmax, x)
                                ymax = max(ymax, y)
                                found = True
        except Exception:
            pass
        if found:
            bboxes[sp_id] = (xmin, ymin, xmax, ymax)
        else:
            bboxes[sp_id] = None
    return bboxes


def analyze_door(door, door_to_spaces=None, opening_for_door=None):
    """Analyze a door: try to get width and report linking spaces.

    Returns dict with name, width_mm, pass (bool), issues list.
    """
    name = get_property(door, "Name") or getattr(door, "Name", None) or str(door)
    door_id = getattr(door, 'GlobalId', None) or str(id(door))
    full_name = f"{name} [{door_id}]" if door_id else name
    # try common property names
    width = _get_numeric_property(door, ["OverallWidth", "Width", "NominalWidth", "DoorWidth"])

    # fallback: try openings filled by this door (IfcRelFillsElement)
    if width is None:
        try:
            for rel in door.Model.by_type("IfcRelFillsElement"):
                try:
                    if getattr(rel, 'RelatedBuildingElement', None) is door:
                        opening = rel.RelatingOpeningElement
                        if opening:
                            ol, ow = get_opening_dimensions_from_geometry(opening)
                            if ow:
                                width = ow
                                break
                except Exception:
                    continue
        except Exception:
            pass

    # If still None, scan property-sets for any property containing 'width'
    if width is None:
        try:
            found = _find_numeric_by_substring(door, ['width'])
            if found:
                width = found
        except Exception:
            pass

    linked_spaces = set()
    door_id = getattr(door, 'GlobalId', None) or str(id(door))
    if door_to_spaces:
        linked_spaces = door_to_spaces.get(door_id, set())
    # If opening_for_door provided, try extract geometry width
    if width is None and opening_for_door is not None:
        ol, ow = get_opening_dimensions_from_geometry(opening_for_door)
        if ow:
            width = ow

    issues = []
    DOOR_MIN_WIDTH = 800  # default mm, adjust to BR18 if needed
    if width is None:
        issues.append("width unknown")
    else:
        if width < DOOR_MIN_WIDTH:
            issues.append(f"width {width:.0f}mm < {DOOR_MIN_WIDTH}mm")

    return {
        "name": full_name,
        "width_mm": width,
        "linked_spaces": linked_spaces,
        "issues": issues
    }


def analyze_stair(stair, model=None):
    """Analyze a stair element for simple requirements (width check).

    If `stair` is an IfcStairFlight we prefer the Actual Run Width property.
    If `stair` is an IfcStair, we will search related IfcStairFlight children
    (by IfcRelAggregates or by name pattern matching) for the Actual Run Width.
    Fallback: use TreadLength from parent IfcStair Dimensions PSet (proxy for run width).

    Returns dict with name, width_mm, pass bool, issues list.
    """
    name = get_property(stair, "Name") or getattr(stair, "Name", None) or str(stair)
    stair_id = getattr(stair, 'GlobalId', None) or str(id(stair))
    full_name = f"{name} [{stair_id}]" if stair_id else name
    # Prefer ActualRunWidth for IfcStairFlight (found under Dimensions -> Actual Run Width)
    if stair.is_a('IfcStairFlight'):
        # try explicit stair flight property names first — "Actual Run Width" is the key property in Dimensions PSet
        width = _get_numeric_property(stair, ["Actual Run Width", "ActualRunWidth", "Actual_Run_Width", "Run Width", "RunWidth"])
        if width is None:
            # fallback to common width names
            width = _get_numeric_property(stair, ["OverallWidth", "Width", "NominalWidth", "StairWidth"])
        # (use properties directly on the IfcStairFlight; parent lookup removed per model content)
    else:
        # For IfcStair (assembled), try direct properties first
        width = _get_numeric_property(stair, ["OverallWidth", "Width", "NominalWidth", "StairWidth"])
        # If still None and model provided, search child IfcStairFlight entities
        if width is None and model is not None:
            try:
                stair_name = name or ""
                # Try IfcRelAggregates first
                for rel in model.by_type('IfcRelAggregates'):
                    try:
                        if getattr(rel, 'RelatingObject', None) is stair:
                            for child in getattr(rel, 'RelatedObjects', []) or []:
                                try:
                                    if child.is_a('IfcStairFlight'):
                                        w = _get_numeric_property(child, ["Actual Run Width", "ActualRunWidth", "Actual_Run_Width"])
                                        if w is None:
                                            w = _find_numeric_by_substring(child, ['width'])
                                        if w:
                                            width = w
                                            break
                                except Exception:
                                    continue
                            if width is not None:
                                break
                    except Exception:
                        continue
                # Fallback: match IfcStairFlight children by name pattern (e.g., "Assembled Stair:Stair:1282665" -> "Assembled Stair:Stair:1282665 Run X")
                if width is None and stair_name:
                    try:
                        for sf in model.by_type('IfcStairFlight'):
                            sf_name = getattr(sf, 'Name', '') or ""
                            if stair_name in sf_name and ' Run ' in sf_name:
                                w = _get_numeric_property(sf, ["Actual Run Width", "ActualRunWidth", "Actual_Run_Width"])
                                if w is None:
                                    w = _find_numeric_by_substring(sf, ['width'])
                                if w:
                                    width = w
                                    break
                    except Exception:
                        pass
            except Exception:
                pass
        # Final fallback: use TreadLength from Pset_StairCommon or Dimensions if width still unknown
        if width is None:
            width = _get_numeric_property(stair, ["TreadLength", "Tread Length", "Tread_Length"])
        # Final fallback: if still no width, try TreadLength from Dimensions PSet (proxy for run width on parent IfcStair)
        if width is None:
            width = _get_numeric_property(stair, ["TreadLength", "Tread Length", "Tread_Length"])

    issues = []
    STAIR_MIN_WIDTH = 1000  # default mm, adjust to BR18 if needed
    # Use a small tolerance to account for minor numeric precision differences
    TOL = 1e-6
    if width is None:
        issues.append("width unknown")
    else:
        # Accept widths that are effectively >= STAIR_MIN_WIDTH within tolerance
        if width + TOL < STAIR_MIN_WIDTH:
            issues.append(f"width {width:.0f}mm < {STAIR_MIN_WIDTH}mm")

    # If width still unknown, try substring search for 'width' in PSets/quantities
    if width is None:
        try:
            found = _find_numeric_by_substring(stair, ['width'])
            if found:
                width = found
                # re-evaluate issues with same tolerance
                issues = []
                if width + TOL < STAIR_MIN_WIDTH:
                    issues.append(f"width {width:.0f}mm < {STAIR_MIN_WIDTH}mm")
        except Exception:
            pass

    return {
        "name": full_name,
        "width_mm": width,
        "issues": issues
    }


def main():
    # Path to your IFC file
    ifc_file_path = os.path.join(os.path.dirname(__file__), "model", "25-16-D-ARCH.ifc")
    
    try:
        # Set VERBOSE to False for normal summary output.
        VERBOSE = False
        # Top-level heading (only printed in verbose mode)
        if VERBOSE:
            print("=== Corridor Analysis Report ===\n")
        
        # Load the IFC file
        model = ifcopenshell.open(ifc_file_path)
        
        # Get all spaces
        spaces = model.by_type("IfcSpace")
        if VERBOSE:
            print(f"Analyzing {len(spaces)} spaces...\n")

        # Track spaces analyzed
        spaces_analyzed = 0
        potential_corridors = []

        # Build adjacency information (doors -> spaces -> space linkages)
        space_linked, door_to_spaces, door_to_opening = build_space_linkages_via_doors(model, spaces)

        # Diagnostic: how many doors map to spaces via relations?
        mapped_doors_count = sum(1 for k, v in door_to_spaces.items() if v)
        if VERBOSE:
            print(f"Door->space relations found for {mapped_doors_count} doors (of {len(model.by_type('IfcDoor'))})")

        # First pass: collect information about all spaces and identify corridors
        for space in spaces:
            analysis = analyze_space(space)
            if not analysis:
                continue

            # augment with adjacency info
            space_id = getattr(space, 'GlobalId', None) or str(id(space))
            linked = space_linked.get(space_id, set())
            analysis["linked_rooms_count"] = len(linked)
            analysis["links_multiple_rooms"] = len(linked) >= 2

            # Determine if this space should be considered an inferred corridor
            # Flowchart logic (interpreted): if named/typed as corridor -> corridor
            # else if elongated AND links multiple rooms -> inferred corridor
            # else if width >= MIN_WIDTH and links multiple rooms -> inferred corridor
            if analysis["is_named_corridor"] or analysis["is_typed_corridor"]:
                analysis["is_inferred_corridor"] = True
                inferred_reason = "declared in model"
            elif analysis["is_elongated"] and analysis["links_multiple_rooms"]:
                analysis["is_inferred_corridor"] = True
                inferred_reason = "elongated and links multiple rooms"
            else:
                analysis["is_inferred_corridor"] = False
                inferred_reason = None

            # Check if this might be a corridor by any criteria
            if analysis["is_inferred_corridor"]:
                potential_corridors.append((space, analysis, inferred_reason))

        # After checking all spaces, report potential corridors
        if VERBOSE:
            if potential_corridors:
                print(f"Found {len(potential_corridors)} potential corridors/hallways\n")
                print("Detailed Analysis:")
                print("="*70)

                for space, analysis, reason in potential_corridors:
                    spaces_analyzed += 1
                    checks = check_requirements(analysis)

                    print(f"\nSpace #{spaces_analyzed}: {analysis['name']}")
                    if analysis["type"]:
                        print(f"Type: {analysis['type']}")
                    if reason:
                        print(f"Identified as corridor because: {reason}")
                    print("-"*70)

                    # Print all checks with their results
                    print("Requirements Check:")
                    for check_name, check in checks.items():
                        if check_name in ("area", "identification"):
                            # informational only
                            print(f"\n  {check_name.title()}: {check['message']}")
                        else:
                            status = "✓ PASS" if check["pass"] else "✗ FAIL"
                            print(f"\n  {check_name.title()}: {status}")
                            print(f"    {check['message']}")
                            print(f"    Requirement: {check['requirement']}")
            else:
                print("No corridors or hallways identified in the model.")

        # Analyze doors in the model
        doors = model.by_type("IfcDoor")
        analyzed_doors = []
        for door in doors:
            door_id = getattr(door, 'GlobalId', None) or str(id(door))
            opening = door_to_opening.get(door_id)
            dres = analyze_door(door, door_to_spaces, opening_for_door=opening)
            analyzed_doors.append(dres)

        # Analyze stairs in the model (prefer IfcStairFlight entries)
        # The model's stairs of interest are represented as IfcStairFlight (Assembled Stair: ... Run X)
        # Use the IfcStairFlight instances directly to match the expected 25 entries.
        flights = model.by_type("IfcStairFlight")
        analyzed_stairs = [analyze_stair(s, model=model) for s in flights]

        # Build summary outputs requested
        failing_doors = [d for d in analyzed_doors if d["issues"]]
        failing_corridors = []
        for space, analysis, reason in potential_corridors:
            # determine corridor-specific issues
            checks = check_requirements(analysis)
            # Corridor requirement: 2 out of 3 must pass (width, elongation, links)
            # Count how many pass
            passing = 0
            issues = []
            
            if checks["width"]["pass"]:
                passing += 1
            else:
                issues.append(checks["width"]["message"])
            
            if checks["elongation"]["pass"]:
                passing += 1
            else:
                issues.append(checks["elongation"]["message"])
            
            if checks["links_rooms"]["pass"]:
                passing += 1
            else:
                issues.append(checks["links_rooms"]["message"])
            
            # Corridor fails only if fewer than 2 checks pass
            if passing < 2:
                space_id = getattr(space, 'GlobalId', '')
                failing_corridors.append({
                    "name": f"{analysis.get('name')} [{space_id}]",
                    "issues": issues
                })

        failing_stairs = [s for s in analyzed_stairs if s["issues"]]

        # (replaced by minimal final summary block below)
        
        # Final summary: print only the outputs requested by the user
        # Doors
        print(f"Amount of doors in model: {len(analyzed_doors)}")
        print(f"Amount of doors that don't fulfill the requirements: {len(failing_doors)}")
        if failing_doors:
            print("The names of the doors and what is not right with them:")
            for d in failing_doors:
                issues = d.get('issues') or []
                print(f" - {d.get('name')}: {', '.join(issues)}")
        else:
            print("No failing doors.")

        # Corridors
        print(f"\nAmount of corridors: {len(potential_corridors)}")
        print(f"Amount of corridors that don't fulfill the requirements: {len(failing_corridors)}")
        if failing_corridors:
            print("The names of the corridors and what is not right with them:")
            for c in failing_corridors:
                print(f" - {c['name']}: {', '.join(c['issues'])}")
        else:
            print("No failing corridors.")

        # Stairs
        print(f"\nAmount of stairs: {len(analyzed_stairs)}")
        print(f"Amount of stairs that don't fulfill the requirements: {len(failing_stairs)}")
        if failing_stairs:
            print("The names of the stairs and what is not right with them:")
            for s in failing_stairs:
                print(f" - {s['name']}: {', '.join(s['issues'])}")
        else:
            print("No failing stairs.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
