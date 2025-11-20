#!/usr/bin/env python3
import ifcopenshell

model = ifcopenshell.open('A3/model/25-16-D-ARCH.ifc')
space_id = '3Vo8snhKX7fQarsO4DMUkV'
spaces = list(model.by_type('IfcSpace'))
sp = next((s for s in spaces if getattr(s,'GlobalId',None)==space_id), None)
if not sp:
    print('space not found')
else:
    print('Space:', getattr(sp,'Name',None), space_id)
    if sp.Representation:
        for rep in sp.Representation.Representations:
            print(' Rep type:', rep.RepresentationType)
            for item in getattr(rep,'Items',[]) or []:
                print('  Item type:', item.is_a())
                if item.is_a('IfcExtrudedAreaSolid'):
                    pos = getattr(item,'Position',None)
                    print('   Position:', pos)
                    if pos and getattr(pos,'Location',None) and getattr(pos.Location,'Coordinates',None):
                        print('   Location coords:', list(pos.Location.Coordinates))
                    print('   Height:', getattr(item,'Depth',None) or getattr(item,'Height',None))
                    profile = getattr(item,'SweptArea',None)
                    print('   Profile:', profile)
                    if profile and profile.is_a('IfcRectangleProfileDef'):
                        print('    XDim, YDim:', getattr(profile,'XDim',None), getattr(profile,'YDim',None))
    else:
        print(' No representation')
