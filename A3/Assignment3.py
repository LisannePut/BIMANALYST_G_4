import ifcopenshell
import numpy as np
import os

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

def is_elongated_space(space):
    """
    Check if a space is elongated (potential corridor)
    Returns True if the space's length is significantly greater than its width
    """
    # Get the space's bounding box
    bbox = space.get_bbox()
    if not bbox:
        return False
        
    length = max(
        abs(bbox[3] - bbox[0]),  # X dimension
        abs(bbox[4] - bbox[1])   # Y dimension
    )
    width = min(
        abs(bbox[3] - bbox[0]),  # X dimension
        abs(bbox[4] - bbox[1])   # Y dimension
    )
    
    # Consider it elongated if length is at least 3 times the width
    return length >= 3 * width

def is_connected_to_stairs(space, stairs):
    """
    Check if a space is connected to stairs
    """
    # Get the space's boundaries
    space_bounds = space.BoundedBy
    if not space_bounds:
        return False
        
    # Check each boundary
    for boundary in space_bounds:
        relating_element = boundary.RelatedBuildingElement
        if relating_element and relating_element.is_a("IfcStair"):
            return True
            
    return False

def get_space_connections(space):
    """
    Get all spaces connected to this space through doors
    """
    connected_spaces = []
    
    # Get all doors connected to this space
    space_bounds = space.BoundedBy
    if not space_bounds:
        return connected_spaces
        
    for boundary in space_bounds:
        if boundary.RelatedBuildingElement and boundary.RelatedBuildingElement.is_a("IfcDoor"):
            # Find spaces on the other side of the door
            door = boundary.RelatedBuildingElement
            for rel in door.ContainedInStructure:
                if rel.RelatingStructure and rel.RelatingStructure != space:
                    connected_spaces.append(rel.RelatingStructure)
                    
    return connected_spaces

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
    """
    Get the name of an IFC space
    """
    for prop in space.IsDefinedBy:
        if prop.is_a("IfcRelDefinesByProperties"):
            pset = prop.RelatingPropertyDefinition
            if pset.is_a("IfcPropertySet"):
                for property in pset.HasProperties:
                    if property.Name in ["Name", "LongName"]:
                        return property.NominalValue.wrappedValue
    return None

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

def main():
    # Path to your IFC file
    ifc_file_path = os.path.join("model", "25-16-D-ARCH.ifc")
    
    try:
        # Load the IFC file
        model = load_ifc_file(ifc_file_path)
        
        # Identify and analyze corridors
        corridors = identify_corridors(model)
        
        print("=== Corridor Analysis Report ===")
        print(f"\nAnalyzing {len(corridors)} spaces (named 'Hallway' or meeting corridor criteria)")
        print("\nSpaces with requirement violations:")
        
        # Track if any violations were found
        violations_found = False
        
        # Check each space against requirements
        for corridor in corridors:
            issues = check_corridor_requirements(corridor)
            
            if issues:
                violations_found = True
                print(f"\nSpace: {corridor['name'] or 'Unnamed Space'}")
                print(f"Properties:")
                print(f"- Width: {corridor['width']}mm")
                print(f"- Is elongated: {'Yes' if corridor['is_elongated'] else 'No'}")
                print(f"- Connected spaces: {corridor['num_connected_spaces']}")
                print(f"- Connected to stairs: {'Yes' if corridor['connected_to_stairs'] else 'No'}")
                print("Violations:")
                for issue in issues:
                    print(f"  {issue}")
        
        if not violations_found:
            print("\nAll analyzed spaces meet corridor requirements.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
