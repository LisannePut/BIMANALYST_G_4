import ifcopenshell
import os
import math

def get_property(entity, property_name, property_set_name=None):
    """Get a property value from an IFC entity"""
    try:
        # Try to get direct attributes first
        if hasattr(entity, property_name):
            return getattr(entity, property_name)
        
        # Try to get from property sets
        if hasattr(entity, "IsDefinedBy"):
            for definition in entity.IsDefinedBy:
                if definition.is_a("IfcRelDefinesByProperties"):
                    property_set = definition.RelatingPropertyDefinition
                    if property_set.is_a("IfcPropertySet"):
                        if property_set_name and property_set.Name != property_set_name:
                            continue
                        for prop in property_set.HasProperties:
                            if prop.Name == property_name and hasattr(prop, "NominalValue"):
                                return prop.NominalValue.wrappedValue
                            elif prop.Name == property_name:
                                # For cases where the property might be stored differently
                                if hasattr(prop, "wrappedValue"):
                                    return prop.wrappedValue
                                elif hasattr(prop, "LengthValue"):
                                    return prop.LengthValue
                                elif hasattr(prop, "AreaValue"):
                                    return prop.AreaValue
                                elif hasattr(prop, "VolumeValue"):
                                    return prop.VolumeValue
    except Exception as e:
        print(f"Error getting property {property_name} from {entity.is_a()}: {e}")
    return None

def load_ifc_file(file_path):
    """
    Load an IFC file and return the model
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"IFC file not found at {file_path}")
    return ifcopenshell.open(file_path)

def get_spaces(model):
    """
    Get all IfcSpaces from the model
    """
    return model.by_type("IfcSpace")

def get_stairs(model):
    """
    Get all IfcStairs from the model
    """
    return model.by_type("IfcStair")

def get_walls(model):
    """
    Get all IfcWalls from the model
    """
    return model.by_type("IfcWall")

def get_doors(model):
    """
    Get all IfcDoors from the model
    """
    return model.by_type("IfcDoor")

def get_space_type(space):
    """Get the space type from properties"""
    type_value = get_property(space, "ObjectType") or get_property(space, "LongName")
    return type_value

def analyze_space(space):
    """Analyze a space and return its characteristics"""
    name = get_space_name(space)
    space_type = get_space_type(space)
    
    # Get dimensions from the Dimensions property set
    area = get_property(space, "Area", "Dimensions")
    perimeter = get_property(space, "Perimeter", "Dimensions")
    
    if not area:
        print(f"Warning: Could not get area for space {name}")
        return None
        
    # Convert area to square meters if needed
    area = float(area)
    if area > 1000:  # If area is in square millimeters
        area = area / 1000000
        
    # Use perimeter to get a better estimate of dimensions
    if perimeter:
        perimeter = float(perimeter)
        # Using perimeter and area to estimate width and length
        # For a rectangle: area = length * width, perimeter = 2(length + width)
        # Solve quadratic equation: w^2 - (P/2)w + A = 0
        P = perimeter / 2
        A = area
        # width = (P - sqrt(P^2 - 4A))/2  # smaller dimension
        discriminant = P*P - 4*A
        if discriminant > 0:
            estimated_width = (P - math.sqrt(discriminant))/2
            estimated_length = area/estimated_width
        else:
            # Fallback to simpler estimation if the space isn't rectangular
            estimated_width = math.sqrt(area / 3)  # Assuming length is roughly 3 times width
            estimated_length = area / estimated_width
    else:
        # Fallback to simple estimation
        estimated_width = math.sqrt(area / 3)
        estimated_length = area / estimated_width
    
    # Convert to millimeters for checking requirements
    estimated_width_mm = estimated_width * 1000
    estimated_length_mm = estimated_length * 1000
    
    # Check if this might be a corridor based on name or type
    keywords = ["hallway", "corridor", "circulation", "passage"]
    is_named_corridor = any(keyword in (name or "").lower() for keyword in keywords)
    is_typed_corridor = any(keyword in (space_type or "").lower() for keyword in keywords)
    
    return {
        "name": name,
        "type": space_type,
        "area": area,
        "width": estimated_width_mm,
        "length": estimated_length_mm,
        "is_elongated": estimated_length_mm >= 3 * estimated_width_mm,
        "area": area,
        "estimated_width": estimated_width,
        "estimated_length": estimated_length,
        "is_elongated": estimated_length >= 3 * estimated_width,
        "is_named_corridor": is_named_corridor,
        "is_typed_corridor": is_typed_corridor
    }



def is_connected_to_stairs(space, stairs):
    """
    Check if a space is connected to stairs
    """
    try:
        # Try to find connections through space boundaries
        for rel in space.BoundedBy:
            if hasattr(rel, 'RelatedBuildingElement'):
                element = rel.RelatedBuildingElement
                if element and element.is_a("IfcStair"):
                    return True
                    
        # Also check for nearby stairs
        for stair in stairs:
            if hasattr(stair, 'ObjectPlacement') and hasattr(space, 'ObjectPlacement'):
                # If they have placements, they might be connected
                return True
                
    except Exception as e:
        print(f"Error checking stair connection: {e}")
        
    return False

def get_space_connections(space):
    """
    Get all spaces connected to this space through doors
    """
    connected_spaces = set()
    
    try:
        # Check all relationships for this space
        for rel in space.ContainsElements:
            if hasattr(rel, 'RelatedElements'):
                for element in rel.RelatedElements:
                    if element.is_a("IfcDoor"):
                        # Found a door, look for connected spaces
                        for ref in element.ReferencedBy:
                            if hasattr(ref, 'RelatingSpace'):
                                connected_space = ref.RelatingSpace
                                if connected_space != space:
                                    connected_spaces.add(connected_space)
                                    
    except Exception as e:
        print(f"Error getting space connections: {e}")
        
    return list(connected_spaces)

def get_corridor_width(space):
    """
    Calculate the minimum width of a space (potential corridor)
    """
    bbox = space.get_bbox()
    if not bbox:
        return 0
        
    # Return the minimum dimension as the width
    return min(
        abs(bbox[3] - bbox[0]),  # X dimension
        abs(bbox[4] - bbox[1])   # Y dimension
    )

def get_space_name(space):
    """Get the name of a space"""
    name = get_property(space, "Name")
    if not name:
        name = get_property(space, "LongName")
    return name

def identify_corridors(model):
    """
    Identify corridors in the model based on the following criteria:
    1. Named as 'Hallway' in the model
    2. Meets corridor definition:
        - Elongated space (length >= 3x width)
        - Connected to at least 2 other spaces OR connected to stairs
        - Minimum width requirements (1300mm)
    """
    corridors = []
    spaces = get_spaces(model)
    stairs = get_stairs(model)
    
    for space in spaces:
        space_name = get_space_name(space)
        is_hallway = space_name and "Hallway" in space_name
        
        # Get space properties
        connected_spaces = get_space_connections(space)
        width = get_corridor_width(space)
        is_elongated = is_elongated_space(space)
        connects_to_stairs = is_connected_to_stairs(space, stairs)
        
        # Create a corridor info dictionary
        corridor_info = {
            'space': space,
            'name': space_name,
            'width': width,
            'is_elongated': is_elongated,
            'connected_to_stairs': connects_to_stairs,
            'num_connected_spaces': len(connected_spaces),
            'is_named_hallway': is_hallway
        }
        
        # Include if it's named Hallway or meets corridor criteria
        if is_hallway or (is_elongated and (len(connected_spaces) >= 2 or connects_to_stairs)):
            corridors.append(corridor_info)
    
    return corridors

def check_corridor_requirements(corridor_info):
    """
    Check if a space meets the requirements to function as a corridor according to BR 18:
    1. Minimum width of 1.3m (1300mm)
    2. Must connect to at least 2 spaces OR connect to stairs (escape route)
    3. Must be elongated (length >= 3x width) if named as Hallway
    """
    issues = []
    MIN_WIDTH = 1300  # 1.3 meters in millimeters
    
    # Always check width requirement
    if corridor_info['width'] < MIN_WIDTH:
        issues.append(f"FAIL: Width is {corridor_info['width']}mm (minimum required: {MIN_WIDTH}mm)")
    
    # Check connectivity requirements
    if corridor_info['num_connected_spaces'] < 2 and not corridor_info['connected_to_stairs']:
        issues.append("FAIL: Space does not connect multiple rooms or stairs")
    
    # If it's named as a Hallway, check if it meets corridor criteria
    if corridor_info['is_named_hallway'] and not corridor_info['is_elongated']:
        issues.append("FAIL: Space is named Hallway but does not meet elongated space criteria (length >= 3x width)")
    
    return issues

def check_requirements(analysis):
    """Check all requirements and return results"""
    MIN_WIDTH = 1300  # minimum width in mm
    MIN_LENGTH_WIDTH_RATIO = 3  # minimum ratio of length to width for corridors
    
    checks = {
        "width": {
            "value": analysis["estimated_width"],
            "requirement": f">= {MIN_WIDTH}mm",
            "pass": analysis["estimated_width"] >= MIN_WIDTH,
            "message": f"Width is {analysis['estimated_width']:.0f}mm"
        },
        "elongation": {
            "value": analysis["estimated_length"] / analysis["estimated_width"],
            "requirement": f">= {MIN_LENGTH_WIDTH_RATIO}x width",
            "pass": analysis["is_elongated"],
            "message": f"Length ({analysis['estimated_length']:.0f}mm) is {analysis['estimated_length']/analysis['estimated_width']:.1f}x width"
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

def main():
    # Path to your IFC file
    ifc_file_path = os.path.join(os.path.dirname(__file__), "model", "25-16-D-ARCH.ifc")
    
    try:
        print("=== Corridor Analysis Report ===")
        
        # Load the IFC file
        model = ifcopenshell.open(ifc_file_path)
        
        # Get all spaces
        spaces = model.by_type("IfcSpace")
        print(f"\nAnalyzing {len(spaces)} spaces...")
        
        # Track spaces analyzed
        spaces_analyzed = 0
        potential_corridors = []
        all_spaces_info = []
        
        # First pass: collect information about all spaces
        for space in spaces:
            analysis = analyze_space(space)
            if not analysis:
                continue
                
            name = analysis["name"] or "Unnamed Space"
            all_spaces_info.append((name, analysis["type"]))
            
            # Check if this might be a corridor
            if (analysis["is_named_corridor"] or 
                analysis["is_typed_corridor"] or 
                analysis["is_elongated"] or 
                analysis["estimated_width"] >= 1300):
                potential_corridors.append((space, analysis))
        
        # Print overview of all spaces
        print("\nAll Spaces in Model:")
        print("="*50)
        for name, type_info in sorted(all_spaces_info):
            print(f"- {name} (Type: {type_info if type_info else 'Not specified'})")
        
        # Analyze potential corridors
        if potential_corridors:
            print("\nDetailed Analysis of Potential Corridors:")
            print("="*50)
            
            for space, analysis in potential_corridors:
                spaces_analyzed += 1
                checks = check_requirements(analysis)
                
                print(f"\n{'='*50}")
                print(f"Space: {analysis['name']}")
                if analysis["type"]:
                    print(f"Type: {analysis['type']}")
                print(f"{'='*50}")
                
                # Print all checks with their results
                print("Requirements Check:")
                for check_name, check in checks.items():
                    status = "PASS" if check["pass"] else "FAIL"
                    if check["requirement"] == "informational":
                        print(f"- {check_name.title()}: {check['message']}")
                    else:
                        print(f"- {check_name.title()}: {status}")
                        print(f"  Value: {check['message']}")
                        print(f"  Requirement: {check['requirement']}")
        
        print(f"\n{'='*50}")
        print(f"Analysis Summary:")
        print(f"{'='*50}")
        print(f"Total spaces in model: {len(spaces)}")
        print(f"Potential corridors analyzed: {spaces_analyzed}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
