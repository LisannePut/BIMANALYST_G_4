#!/usr/bin/env python3
import ifcopenshell
import math

def get_element_centroid(element):
    """Get 3D centroid of an element from its geometry."""
    try:
        if not element.Representation:
            return None
        
        for rep in element.Representation.Representations:
            if rep.RepresentationType in ["Body", "Tessellation"]:
                for item in rep.Items:
                    if item.is_a("IfcPolyhedralBoundedSurface"):
                        vertices = []
                        for face in item.OuterBoundary.CfaceBounds:
                            if hasattr(face, 'Bound'):
                                try:
                                    pts = face.Bound.Points if hasattr(face.Bound, 'Points') else []
                                    vertices.extend(pts)
                                except:
                                    pass
                        if vertices:
                            xs = [v[0] for v in vertices]
                            ys = [v[1] for v in vertices]
                            zs = [v[2] for v in vertices]
                            return (sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs))
                    
                    elif item.is_a("IfcShapeRepresentation"):
                        try:
                            pts = item.Items if hasattr(item, 'Items') else []
                            if pts:
                                vertices = []
                                for pt in pts:
                                    if hasattr(pt, 'Coordinates'):
                                        vertices.append(pt.Coordinates)
                                if vertices:
                                    xs = [v[0] for v in vertices]
                                    ys = [v[1] for v in vertices]
                                    zs = [v[2] for v in vertices]
                                    return (sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs))
                        except:
                            pass
    except:
        pass
    
    return None

# Load model
model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")

# Check spaces and their centroids
spaces = list(model.by_type("IfcSpace"))
print(f"Total spaces: {len(spaces)}")

space_centroids = {}
no_centroid = 0
for sp in spaces:
    cent = get_element_centroid(sp)
    sp_id = getattr(sp, 'GlobalId', None) or str(id(sp))
    sp_name = getattr(sp, 'Name', 'unknown')
    if cent:
        space_centroids[sp_id] = cent
    else:
        no_centroid += 1
    
    if len(space_centroids) <= 3:
        print(f"Space: {sp_name} [{sp_id}] - Centroid: {cent}")

print(f"\nSpaces with centroid: {len(space_centroids)}")
print(f"Spaces without centroid: {no_centroid}")

# Check opening centroids
print("\n--- Checking openings ---")
openings = list(model.by_type("IfcOpeningElement"))
print(f"Total openings: {len(openings)}")

opening_centroids = 0
for i, opening in enumerate(openings):
    if i >= 3:
        break
    cent = get_element_centroid(opening)
    op_id = getattr(opening, 'GlobalId', None)
    if cent:
        opening_centroids += 1
        print(f"Opening {i+1} [{op_id}]: {cent}")
    else:
        print(f"Opening {i+1} [{op_id}]: NO CENTROID")

print(f"\nOpening centroids available: {opening_centroids} (of first 3 checked)")

# Check a door-opening connection
print("\n--- Checking a door-opening connection ---")
for rel in list(model.by_type("IfcRelFillsElement"))[:1]:
    opening = rel.RelatingOpeningElement
    door = rel.RelatedBuildingElement
    
    door_name = getattr(door, 'Name', 'unknown')
    door_id = getattr(door, 'GlobalId', None)
    
    opening_cent = get_element_centroid(opening)
    
    print(f"Door: {door_name} [{door_id}]")
    print(f"Opening centroid: {opening_cent}")
    
    if opening_cent and space_centroids:
        # Find nearest spaces
        distances = []
        for sp_id, cent in space_centroids.items():
            dist = math.sqrt((opening_cent[0] - cent[0])**2 + 
                           (opening_cent[1] - cent[1])**2 + 
                           (opening_cent[2] - cent[2])**2)
            distances.append((dist, sp_id))
        
        distances.sort()
        print(f"Nearest 3 spaces:")
        for i, (dist, sp_id) in enumerate(distances[:3]):
            sp = next((s for s in spaces if (getattr(s, 'GlobalId', None) or str(id(s))) == sp_id), None)
            sp_name = getattr(sp, 'Name', 'unknown') if sp else 'unknown'
            print(f"  {i+1}. Distance {dist:.1f}mm - {sp_name} [{sp_id}]")
