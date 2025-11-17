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

    Strategy:
      - Use IfcRelSpaceBoundary to map openings -> spaces
      - Use IfcRelFillsElement to map openings <-> doors (door fills opening)
      - For each door, collect spaces touching the opening and connect them to each other
    Returns: dict space -> set(other_spaces)
    """
    opening_to_spaces = build_opening_to_spaces_map(model)
    # door_id (GlobalId) -> set(space GlobalId)
    door_to_spaces = {}
    # door_id -> opening element (object) if known
    door_to_opening = {}

    # Relates openings to doors/windows (the filling element)
    try:
        for rel in model.by_type("IfcRelFillsElement"):
            try:
                opening = rel.RelatingOpeningElement
                element = rel.RelatedBuildingElement
                if opening and element:
                    opening_key = getattr(opening, 'GlobalId', None) or str(id(opening))
                    # try direct mapping first
                    spaces_touching = set(opening_to_spaces.get(opening_key, set()))
                    # fallback: find space boundaries that reference a parent wall/element that contains this opening
                    if not spaces_touching:
                        try:
                            for relb in model.by_type('IfcRelSpaceBoundary'):
                                try:
                                    related = relb.RelatedBuildingElement
                                    if not related:
                                        continue
                                    # direct match
                                    if getattr(related, 'GlobalId', None) == getattr(opening, 'GlobalId', None):
                                        spaces_touching.add(getattr(relb.RelatingSpace, 'GlobalId', None) or str(id(relb.RelatingSpace)))
                                        continue
                                    # check if related element has openings that reference our opening
                                    for ro in getattr(related, 'HasOpenings', []) or []:
                                        for o in getattr(ro, 'RelatedOpeningElements', []) or []:
                                            if getattr(o, 'GlobalId', None) == getattr(opening, 'GlobalId', None):
                                                spaces_touching.add(getattr(relb.RelatingSpace, 'GlobalId', None) or str(id(relb.RelatingSpace)))
                                                break
                                except Exception:
                                    continue
                        except Exception:
                            pass
                    if spaces_touching:
                        door_id = getattr(element, 'GlobalId', None) or str(id(element))
                        door_to_spaces.setdefault(door_id, set()).update(spaces_touching)
                        door_to_opening[door_id] = opening
            except Exception:
                continue
    except Exception:
        pass

    # Also handle cases where the door itself is directly referenced in a space boundary
    try:
        for rel in model.by_type("IfcRelSpaceBoundary"):
            try:
                related = rel.RelatedBuildingElement
                space = rel.RelatingSpace
                if related and space and related.is_a("IfcDoor"):
                    door_id = getattr(related, 'GlobalId', None) or str(id(related))
                    door_to_spaces.setdefault(door_id, set()).add(getattr(space, 'GlobalId', None) or str(id(space)))
            except Exception:
                continue
    except Exception:
        pass

    # Additional mapping: use containment relations to find spaces a door belongs to
    try:
        for rel in model.by_type("IfcRelContainedInSpatialStructure"):
            try:
                space = rel.RelatingStructure
                for elem in rel.RelatedElements:
                    if elem and elem.is_a("IfcDoor"):
                        door_id = getattr(elem, 'GlobalId', None) or str(id(elem))
                        door_to_spaces.setdefault(door_id, set()).add(getattr(space, 'GlobalId', None) or str(id(space)))
            except Exception:
                continue
    except Exception:
        pass

    # Now build space adjacency via doors
    # Build adjacency keyed by space GlobalId
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

    # Common property set names to try explicitly (your model uses 'Dimensions')
    psets = ["Dimensions", "Pset_DoorCommon", "PSet_DoorCommon", "Pset_StairCommon", "Dimensions "]
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


def analyze_door(door, door_to_spaces=None, opening_for_door=None):
    """Analyze a door: try to get width and report linking spaces.

    Returns dict with name, width_mm, pass (bool), issues list.
    """
    name = get_property(door, "Name") or getattr(door, "Name", None) or str(door)
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
        "name": name,
        "width_mm": width,
        "linked_spaces": linked_spaces,
        "issues": issues
    }


def analyze_stair(stair):
    """Analyze a stair element for simple requirements (width check).

    Returns dict with name, width_mm, pass bool, issues list.
    """
    name = get_property(stair, "Name") or getattr(stair, "Name", None) or str(stair)
    width = _get_numeric_property(stair, ["OverallWidth", "Width", "NominalWidth", "StairWidth"])

    issues = []
    STAIR_MIN_WIDTH = 1000  # default mm, adjust to BR18 if needed
    if width is None:
        issues.append("width unknown")
    else:
        if width < STAIR_MIN_WIDTH:
            issues.append(f"width {width:.0f}mm < {STAIR_MIN_WIDTH}mm")

    return {
        "name": name,
        "width_mm": width,
        "issues": issues
    }


def main():
    # Path to your IFC file
    ifc_file_path = os.path.join(os.path.dirname(__file__), "model", "25-16-D-ARCH.ifc")
    
    try:
        print("=== Corridor Analysis Report ===\n")
        
        # Load the IFC file
        model = ifcopenshell.open(ifc_file_path)
        
        # Get all spaces
        spaces = model.by_type("IfcSpace")
        print(f"Analyzing {len(spaces)} spaces...\n")

        # Track spaces analyzed
        spaces_analyzed = 0
        potential_corridors = []

        # Build adjacency information (doors -> spaces -> space linkages)
        space_linked, door_to_spaces, door_to_opening = build_space_linkages_via_doors(model, spaces)

        # Diagnostic: how many doors map to spaces via relations?
        mapped_doors_count = sum(1 for k, v in door_to_spaces.items() if v)
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
            elif analysis["width"] >= 1300 and analysis["links_multiple_rooms"]:
                analysis["is_inferred_corridor"] = True
                inferred_reason = "wide and links multiple rooms"
            else:
                analysis["is_inferred_corridor"] = False
                inferred_reason = None

            # Check if this might be a corridor by any criteria
            if analysis["is_inferred_corridor"]:
                potential_corridors.append((space, analysis, inferred_reason))

        # After checking all spaces, report potential corridors
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

        # Analyze stairs in the model
        stairs = model.by_type("IfcStair") + model.by_type("IfcStairFlight")
        analyzed_stairs = [analyze_stair(s) for s in stairs]

        # Build summary outputs requested
        failing_doors = [d for d in analyzed_doors if d["issues"]]
        failing_corridors = []
        for space, analysis, reason in potential_corridors:
            # determine corridor-specific issues
            checks = check_requirements(analysis)
            issues = []
            if not checks["width"]["pass"]:
                issues.append(checks["width"]["message"])
            if not checks["elongation"]["pass"]:
                issues.append(checks["elongation"]["message"])
            if not checks["links_rooms"]["pass"]:
                issues.append(checks["links_rooms"]["message"])
            if issues:
                failing_corridors.append({
                    "name": analysis.get("name"),
                    "issues": issues
                })

        failing_stairs = [s for s in analyzed_stairs if s["issues"]]

        # Print final summary as requested
        print("\n" + "="*70)
        print("Final Summary:")
        print("="*70)
        # Doors
        print(f"Total doors in model: {len(analyzed_doors)}")
        print(f"Doors failing requirements: {len(failing_doors)}")
        if failing_doors:
            print("Failing doors and issues:")
            for d in failing_doors:
                print(f" - {d['name']}: {', '.join(d['issues'])}")

        # Corridors
        print(f"\nTotal corridors identified: {len(potential_corridors)}")
        print(f"Corridors failing requirements: {len(failing_corridors)}")
        if failing_corridors:
            print("Failing corridors and issues:")
            for c in failing_corridors:
                print(f" - {c['name']}: {', '.join(c['issues'])}")

        # Stairs
        print(f"\nTotal stairs in model: {len(analyzed_stairs)}")
        print(f"Stairs failing requirements: {len(failing_stairs)}")
        if failing_stairs:
            print("Failing stairs and issues:")
            for s in failing_stairs:
                print(f" - {s['name']}: {', '.join(s['issues'])}")
        
        print(f"\n{'='*70}")
        print(f"Analysis Summary:")
        print(f"{'='*70}")
        print(f"Total spaces in model: {len(spaces)}")
        print(f"Potential corridors analyzed: {spaces_analyzed}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
