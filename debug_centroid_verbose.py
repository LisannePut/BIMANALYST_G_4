#!/usr/bin/env python3
import ifcopenshell

def get_element_centroid_debug(element):
    """Try to get a 3D point (x,y,z) from an element's representation.

    For IfcExtrudedAreaSolid, compute centroid from base position + profile center + height/2.
    Returns coordinates in model units (usually meters) or None.
    """
    try:
        if not hasattr(element, 'Representation') or not element.Representation:
            print(f"  No Representation")
            return None
        
        for rep in element.Representation.Representations:
            print(f"  Rep type: {rep.RepresentationType}")
            for i, item in enumerate(getattr(rep, 'Items', []) or []):
                print(f"    Item {i}: {item.is_a()}")
                
                # IfcExtrudedAreaSolid: compute centroid from profile + extrusion
                if item.is_a('IfcExtrudedAreaSolid'):
                    print(f"      Processing IfcExtrudedAreaSolid")
                    try:
                        pos = getattr(item, 'Position', None)
                        print(f"        Position: {pos}")
                        if not pos:
                            print(f"        No Position")
                            continue
                        
                        loc = getattr(pos, 'Location', None)
                        print(f"        Location: {loc}")
                        if not loc or not getattr(loc, 'Coordinates', None):
                            print(f"        No Location or Coordinates")
                            continue
                        
                        base_coords = list(loc.Coordinates)
                        print(f"        Base coords: {base_coords}")
                        base_x = float(base_coords[0])
                        base_y = float(base_coords[1])
                        base_z = float(base_coords[2]) if len(base_coords) > 2 else 0.0
                        print(f"        Base XYZ: ({base_x}, {base_y}, {base_z})")
                        
                        # Get extrusion height
                        height = float(getattr(item, 'Height', 0)) if hasattr(item, 'Height') else 0
                        print(f"        Height: {height}")
                        
                        # Get profile centroid if available (RectangleProfileDef)
                        profile = getattr(item, 'SweptArea', None)
                        print(f"        Profile: {profile}")
                        if profile and profile.is_a('IfcRectangleProfileDef'):
                            print(f"          Is rectangle profile")
                            # Centroid relative to profile's position
                            profile_pos = getattr(profile, 'Position', None)
                            x_dim = float(getattr(profile, 'XDim', 0))
                            y_dim = float(getattr(profile, 'YDim', 0))
                            print(f"          Dims: {x_dim} x {y_dim}")
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
                            print(f"          FOUND CENTROID: ({cent_x}, {cent_y}, {cent_z})")
                            return (cent_x, cent_y, cent_z)
                        else:
                            # No profile info: use base location + height/2
                            result = (base_x, base_y, base_z + height / 2.0)
                            print(f"        FOUND CENTROID (no profile): {result}")
                            return result
                    except Exception as e:
                        print(f"      Exception: {e}")
                        import traceback
                        traceback.print_exc()
                        pass
        
        print(f"  No centroid found")
        return None
    except Exception as e:
        print(f"Exception in get_element_centroid_debug: {e}")
        import traceback
        traceback.print_exc()
        return None

# Load model
model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")

# Check first space
spaces = list(model.by_type("IfcSpace"))
sp = spaces[0]
sp_name = getattr(sp, 'Name', 'unknown')

print(f"Testing space: {sp_name}")
cent = get_element_centroid_debug(sp)
print(f"Result: {cent}\n")

# Check first opening
openings = list(model.by_type("IfcOpeningElement"))
op = openings[0]
op_id = getattr(op, 'GlobalId', 'unknown')

print(f"Testing opening: {op_id}")
cent = get_element_centroid_debug(op)
print(f"Result: {cent}")
