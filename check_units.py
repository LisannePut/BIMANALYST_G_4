#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/lisanneput/Desktop/2025-2026/Semester 1/BIM/BIMANALYST_G_4/A3')
import ifcopenshell
import math
from Assignment3 import get_element_centroid

model = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")

# Get model units
ifcfile = ifcopenshell.open("A3/model/25-16-D-ARCH.ifc")
project = ifcfile.by_type('IfcProject')[0]
unit_info = project.UnitsInContext
if unit_info:
    for unit in unit_info.Units:
        if hasattr(unit, 'UnitType'):
            print(f"Unit: {unit.UnitType} = {unit.Prefix if hasattr(unit, 'Prefix') else ''}mm")

# Get a hallway and check its geometry directly
spaces = list(model.by_type("IfcSpace"))
hallway = None
for sp in spaces:
    if getattr(sp, 'Name', '') == 'Hallway:1133176':
        hallway = sp
        break

if hallway:
    print(f"\nHallway geometry details:")
    print(f"  Name: {getattr(hallway, 'Name', '?')}")
    
    if hallway.Representation:
        for rep in hallway.Representation.Representations:
            for item in getattr(rep, 'Items', []):
                if item.is_a('IfcExtrudedAreaSolid'):
                    profile = getattr(item, 'SweptArea', None)
                    if profile and profile.is_a('IfcRectangleProfileDef'):
                        x_dim = getattr(profile, 'XDim', 0)
                        y_dim = getattr(profile, 'YDim', 0)
                        height = getattr(item, 'Height', 0)
                        print(f"  Dimensions: {x_dim} x {y_dim} x {height}")
                        
                        # Check if these are in mm or m
                        if x_dim > 1000:
                            print(f"  Units appear to be: MILLIMETERS (x_dim = {x_dim})")
                        else:
                            print(f"  Units appear to be: METERS (x_dim = {x_dim})")

# Find a door near the hallway and check its distance calculation manually
hallway_cent = get_element_centroid(hallway)
print(f"\nHallway centroid: {hallway_cent}")

openings = list(model.by_type("IfcOpeningElement"))[:5]
for op in openings:
    op_cent = get_element_centroid(op)
    if op_cent:
        dist = math.sqrt((op_cent[0] - hallway_cent[0])**2 + 
                        (op_cent[1] - hallway_cent[1])**2 + 
                        (op_cent[2] - hallway_cent[2])**2)
        print(f"Opening {getattr(op, 'GlobalId', '?')[:8]}... -> distance to hallway: {dist:,.0f} units")
