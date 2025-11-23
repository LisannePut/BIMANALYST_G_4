import ifcopenshell
import os

IFC_PATH = os.path.join(os.path.dirname(__file__), "A3", "model", "25-16-D-ARCH.ifc")
model = ifcopenshell.open(IFC_PATH)

# Get all hallways
hallways = {}
for sp in model.by_type('IfcSpace'):
    name = (getattr(sp, 'Name', None) or '').lower()
    if 'hallway' in name:
        gid = getattr(sp, 'GlobalId', None)
        hallways[gid] = getattr(sp, 'Name', 'Unknown')

# Get all stairs
stairs = {}
for sp in model.by_type('IfcSpace'):
    name = (getattr(sp, 'Name', None) or '').lower()
    if 'stair' in name:
        gid = getattr(sp, 'GlobalId', None)
        stairs[gid] = getattr(sp, 'Name', 'Unknown')

print(f"Hallways found: {len(hallways)}")
print(f"Stairs found: {len(stairs)}")

# Check door relations
print("\n" + "="*80)
print("CHECKING DOOR CONNECTIONS BETWEEN HALLWAYS AND STAIRS")
print("="*80)

hallway_to_stair = {}

for rel in model.by_type('IfcRelFillsElement'):
    opening = getattr(rel, 'RelatingOpeningElement', None)
    door = getattr(rel, 'RelatedBuildingElement', None)
    if not (opening and door and door.is_a('IfcDoor')):
        continue
    
    door_name = getattr(door, 'Name', 'Door')
    
    # Find which spaces contain this opening
    # For simplicity, just check the voids in parent elements
    parent = getattr(opening, 'VoidsElements', None)
    if parent:
        for rel2 in parent:
            elem = getattr(rel2, 'RelatingBuildingElement', None)
            if elem and elem.is_a('IfcSpace'):
                space_gid = getattr(elem, 'GlobalId', None)
                space_name = getattr(elem, 'Name', 'Unknown')
                is_hallway = space_gid in hallways
                is_stair = space_gid in stairs
                
                if is_hallway or is_stair:
                    print(f"\nDoor '{door_name}' in space: {space_name} ({space_gid})")
                    if is_hallway:
                        print(f"  → This is a HALLWAY")
                    if is_stair:
                        print(f"  → This is a STAIR")
                    
                    # Check what other spaces this opening connects to
                    # by finding other doors/openings in the same wall

# Alternative: Check using IfcRelSpaceBoundary
print("\n" + "="*80)
print("CHECKING SPACE BOUNDARIES")
print("="*80)

for hallway_gid in hallways:
    hallway = model.by_guid(hallway_gid)
    boundaries = getattr(hallway, 'BoundedBy', None) or []
    print(f"\nHallway {hallways[hallway_gid]} ({hallway_gid}):")
    print(f"  Boundaries: {len(boundaries)}")
    
    stair_connected = False
    for boundary in boundaries:
        # Each boundary relates to another space
        related = getattr(boundary, 'RelatedBuildingElement', None)
        if related and related.is_a('IfcSpace'):
            related_gid = getattr(related, 'GlobalId', None)
            related_name = getattr(related, 'Name', 'Unknown')
            if related_gid in stairs:
                print(f"    ✓ Connected to STAIR: {related_name}")
                stair_connected = True
            else:
                print(f"    → Connected to: {related_name}")
    
    if not stair_connected:
        print(f"    ✗ NOT connected to any stair")
