import ifcopenshell
import ifcopenshell.geom
import numpy as np
import os

IFC_PATH = os.path.join(os.path.dirname(__file__), "A3", "model", "25-16-D-ARCH.ifc")

def to_mm(v):
    try:
        f = float(v)
    except Exception:
        return None
    return f if f > 100 else f * 1000.0

# Failing corridor GlobalIds from the output
failing_ids = [
    "3Vo8snhKX7fQarsO4DMUkV",
    "3Vo8snhKX7fQarsO4DMUj_",
    "00BLWdUaL9VBG$qrz5yV$D",
    "00BLWdUaL9VBG$qrz5yVaH",
    "2UtUBnYTLAR8Xlpya3fMOt",
    "2UtUBnYTLAR8Xlpya3fMmp",
    "1$EM9uRuLF$xLj0Op5ne1b"
]

model = ifcopenshell.open(IFC_PATH)
GEOM_SETTINGS = ifcopenshell.geom.settings()
GEOM_SETTINGS.set(GEOM_SETTINGS.USE_WORLD_COORDS, True)

def get_vertices(product):
    """Extract vertices from IFC product using world coordinates."""
    try:
        shape = ifcopenshell.geom.create_shape(GEOM_SETTINGS, product)
        verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
        return verts
    except Exception as e:
        return None

print("=" * 100)
print("DEBUGGING FAILING CORRIDORS - DETAILED GEOMETRY INSPECTION")
print("=" * 100)

for gid in failing_ids:
    spaces = model.by_guid(gid)
    if not spaces:
        print(f"\n❌ Could not find space with GlobalId {gid}")
        continue
    
    sp = spaces
    name = getattr(sp, 'Name', 'Unknown')
    print(f"\n{'='*80}")
    print(f"Space: {name} [{gid}]")
    print(f"{'='*80}")
    
    # Try to extract vertices from the entire space object
    print(f"\n  Trying to extract 3D vertices from IfcSpace via ifcopenshell.geom...")
    space_verts = get_vertices(sp)
    if space_verts is not None and len(space_verts) > 0:
        minv = space_verts.min(axis=0)
        maxv = space_verts.max(axis=0)
        dims = maxv - minv
        width = min(dims[0], dims[1])
        length = max(dims[0], dims[1])
        print(f"  ✓ SUCCESS! Extracted {len(space_verts)} vertices")
        print(f"    Bbox: min={minv}, max={maxv}")
        print(f"    Dimensions (X, Y, Z): {dims}")
        print(f"    ✓✓ Width (min of XY): {width:.2f}mm")
        print(f"    ✓✓ Length (max of XY): {length:.2f}mm")
        print(f"    → This is the correct width!")
    else:
        print(f"  ✗ Failed to extract vertices from IfcSpace")
    
    # Check representation
    if not getattr(sp, 'Representation', None):
        print("  ❌ No representation found")
        continue
    
    print(f"\n  Continuing with representation details...")
    
    rep = sp.Representation
    print(f"  Representation has {len(rep.Representations)} representation(s)")
    
    for rep_idx, r in enumerate(rep.Representations):
        print(f"\n  Representation {rep_idx}:")
        print(f"    ContextIdentifier: {getattr(r, 'ContextIdentifier', 'N/A')}")
        print(f"    Items count: {len(getattr(r, 'Items', []) or [])}")
        
        for item_idx, item in enumerate(getattr(r, 'Items', []) or []):
            print(f"\n    Item {item_idx}: {item.is_a()}")
            
            # Try to extract vertices from 3D geometry
            print(f"      Attempting to extract 3D vertices via ifcopenshell.geom...")
            verts = get_vertices(item)
            if verts is not None and len(verts) > 0:
                print(f"      ✓ Got {len(verts)} vertices")
                minv = verts.min(axis=0)
                maxv = verts.max(axis=0)
                dims = maxv - minv
                print(f"      Bbox: min={minv}, max={maxv}")
                print(f"      Dimensions (X, Y, Z): {dims}")
                width = min(dims[0], dims[1])
                length = max(dims[0], dims[1])
                print(f"      ✓ Width (min of XY): {width:.2f}mm")
                print(f"      ✓ Length (max of XY): {length:.2f}mm")
            else:
                print(f"      ✗ Could not extract vertices or got empty")
            
            # If it's an extruded solid, check the profile
            if item.is_a('IfcExtrudedAreaSolid'):
                prof = getattr(item, 'SweptArea', None)
                print(f"      SweptArea type: {prof.is_a() if prof else 'None'}")
                if prof and prof.is_a('IfcRectangleProfileDef'):
                    xd = to_mm(getattr(prof, 'XDim', 0))
                    yd = to_mm(getattr(prof, 'YDim', 0))
                    print(f"      Rectangle XDim: {xd}mm, YDim: {yd}mm")
                elif prof and prof.is_a('IfcArbitraryClosedProfileDef'):
                    print(f"      ArbitraryClosedProfileDef found!")
                    outer_curve = getattr(prof, 'OuterCurve', None)
                    if outer_curve:
                        print(f"        OuterCurve type: {outer_curve.is_a()}")
                        if outer_curve.is_a('IfcPolyline'):
                            points = getattr(outer_curve, 'Points', [])
                            print(f"        Polyline has {len(points)} points")
                            if len(points) > 0:
                                coords = []
                                for pt in points:
                                    x = to_mm(getattr(pt, 'Coordinates', [None, None])[0]) or 0
                                    y = to_mm(getattr(pt, 'Coordinates', [None, None])[1]) or 0
                                    coords.append((x, y))
                                    print(f"          Point: ({x:.2f}, {y:.2f})")
                                if len(coords) > 1:
                                    xs = [c[0] for c in coords]
                                    ys = [c[1] for c in coords]
                                    width = max(xs) - min(xs)
                                    depth = max(ys) - min(ys)
                                    print(f"        Derived dimensions - Width: {width:.2f}mm, Depth: {depth:.2f}mm")
                elif prof:
                    print(f"      Profile attributes: {[attr for attr in dir(prof) if not attr.startswith('_')][:10]}")
            
            # If it's faceted brep, show details
            if item.is_a('IfcFacetedBrep'):
                outer = getattr(item, 'OuterBoundary', None)
                if outer:
                    print(f"      OuterBoundary: {outer.is_a()}")
                    if hasattr(outer, 'CfsFaces'):
                        print(f"      Number of faces: {len(outer.CfsFaces)}")

print("\n" + "=" * 100)
