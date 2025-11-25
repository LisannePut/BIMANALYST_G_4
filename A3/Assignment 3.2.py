import ifcopenshell
import ifcopenshell.geom
import os
import math
import numpy as np
import re

# BR18 requirements (concise)
# - Doors: clear opening width >= 800 mm (DOOR_MIN)
# - Stairs: clear width >= 1000 mm (STAIR_MIN)
# - Corridors: clear width >= 1300 mm (CORRIDOR_MIN) AND must link to a stair
# The BR18 PDF is included in this folder as 'BR18.pdf' and referenced by
# BR18_DOC_PATH below.

# Config
IFC_PATH = os.path.join(os.path.dirname(__file__), "model", "25-16-D-ARCH.ifc")
DOOR_MIN = 800
STAIR_MIN = 1000
CORRIDOR_MIN = 1300
BUFFER_BBOX = 1000.0
NEAREST_MAX = 30000.0
# BR18 PDF parsing has been removed. Use the hard-coded BR18 thresholds below.


# PDF parsing removed: thresholds are hard-coded at the top of this file

# Geometry settings for door midpoint calculation
GEOM_SETTINGS = ifcopenshell.geom.settings()
GEOM_SETTINGS.set(GEOM_SETTINGS.USE_WORLD_COORDS, True)


def to_mm(v):
	try:
		f = float(v)
	except Exception:
		return None
	return f if f > 100 else f * 1000.0


def extract_dimensions_from_geometry(sp):
	"""Extract width and length from IfcSpace geometry using 3D vertices.
    
	ifcopenshell.geom returns coordinates in meters, but IFC file units are millimeters,
	so we multiply by 1000 to convert.
	"""
	try:
		verts = get_vertices(sp)
		if verts is not None and len(verts) > 0:
			# Convert from meters to millimeters (multiply by 1000)
			verts = verts * 1000.0
			minv = verts.min(axis=0)
			maxv = verts.max(axis=0)
			dims = maxv - minv
			# Return (longer dim, shorter dim) as (length, width)
			dim_sorted = sorted(dims[:2])  # Take X, Y (ignore Z height)
			if dim_sorted[1] > 0:  # Ensure width > 0
				return dim_sorted[1], dim_sorted[0]
	except Exception:
		pass
    
	return 0, 0



def get_vertices(product):
	"""Extract vertices from IFC product using world coordinates.
    
	Skip problematic geometry that hangs.
	"""
	try:
		shape = ifcopenshell.geom.create_shape(GEOM_SETTINGS, product)
		verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
		return verts
	except (KeyboardInterrupt, Exception):
		# Return None for any geometry error (includes timeouts/interrupts)
		return None
# NOTE: get_bbox and get_door_midpoint were removed because the code
# now uses `get_vertices` + geometry-based centroids via
# `get_element_centroid`. They were unused and are deleted to keep
# the file clean.

def get_numeric(entity, names):
	names_l = [n.lower() for n in names]
	# Attributes first
	for attr in dir(entity):
		try:
			if attr.lower() in names_l:
				v = getattr(entity, attr)
				r = to_mm(v)
				if r:
					return r
		except Exception:
			continue
	# PSets and quantities
	for rel in getattr(entity, 'IsDefinedBy', []) or []:
		try:
			if not rel.is_a('IfcRelDefinesByProperties'):
				continue
			pdef = rel.RelatingPropertyDefinition
			if pdef is None:
				continue
			if pdef.is_a('IfcPropertySet'):
				for p in getattr(pdef, 'HasProperties', []) or []:
					try:
						pname = (getattr(p, 'Name', '') or '').lower()
						if any(n in pname for n in names_l):
							if hasattr(p, 'NominalValue') and p.NominalValue is not None:
								try:
									val = p.NominalValue.wrappedValue
								except Exception:
									val = p.NominalValue
								r = to_mm(val)
								if r:
									return r
					except Exception:
						continue
			if pdef.is_a('IfcElementQuantity'):
				for q in getattr(pdef, 'Quantities', []) or []:
					try:
						qn = (getattr(q, 'Name', '') or '').lower()
						if any(n in qn for n in names_l):
							val = getattr(q, 'LengthValue', None) or getattr(q, 'AreaValue', None) or getattr(q, 'VolumeValue', None)
							r = to_mm(val)
							if r:
								return r
					except Exception:
						continue
		except Exception:
			continue
	return None


def centroid_from_extruded(item):
	try:
		if not item or not item.is_a('IfcExtrudedAreaSolid'):
			return None
		pos = getattr(item, 'Position', None)
		loc = getattr(pos, 'Location', None) if pos else None
		coords = list(getattr(loc, 'Coordinates', [])) if loc else []
		x = float(coords[0]) if coords else 0.0
		y = float(coords[1]) if len(coords) > 1 else 0.0
		z = float(coords[2]) if len(coords) > 2 else 0.0
		# Convert location coords to mm (they come in meters or model units)
		x = x if x > 100 else x * 1000.0
		y = y if y > 100 else y * 1000.0
		z = z if z > 100 else z * 1000.0
		prof = getattr(item, 'SweptArea', None)
		if prof and prof.is_a('IfcRectangleProfileDef'):
			xd = float(getattr(prof, 'XDim', 0) or 0)
			yd = float(getattr(prof, 'YDim', 0) or 0)
			xd = xd if xd > 100 else xd * 1000.0
			yd = yd if yd > 100 else yd * 1000.0
			return (x + xd / 2.0, y + yd / 2.0, z + float(getattr(item, 'Height', 0)) / 2.0)
		return (x, y, z)
	except Exception:
		return None


def get_element_centroid(elem):
	"""Get centroid using ifcopenshell.geom (same method as debug script)."""
	try:
		verts = get_vertices(elem)
		if verts is not None and len(verts) > 0:
			verts = verts * 1000.0  # Convert to mm
			return verts.mean(axis=0)
	except Exception:
		pass
	return None


def build_space_bboxes(spaces):
	b = {}
	for sp in spaces:
		sid = getattr(sp, 'GlobalId', None) or str(id(sp))
		xmin = ymin = float('inf'); xmax = ymax = float('-inf')
		if getattr(sp, 'Representation', None):
			for rep in sp.Representation.Representations:
				for it in getattr(rep, 'Items', []) or []:
					if it.is_a('IfcExtrudedAreaSolid'):
						pos = getattr(it, 'Position', None)
						loc = getattr(pos, 'Location', None) if pos else None
						coords = list(getattr(loc, 'Coordinates', [])) if loc else []
						x = float(coords[0]) if coords else 0.0
						y = float(coords[1]) if len(coords) > 1 else 0.0
						prof = getattr(it, 'SweptArea', None)
						if prof and prof.is_a('IfcRectangleProfileDef'):
							xd = float(getattr(prof, 'XDim', 0) or 0)
							yd = float(getattr(prof, 'YDim', 0) or 0)
							xd = xd if xd > 100 else xd * 1000.0
							yd = yd if yd > 100 else yd * 1000.0
							hx = xd / 2.0; hy = yd / 2.0
							xmin = min(xmin, x - hx); ymin = min(ymin, y - hy)
							xmax = max(xmax, x + hx); ymax = max(ymax, y + hy)
		b[sid] = (xmin, ymin, xmax, ymax) if xmin != float('inf') else None
	return b


def build_space_linkages(model, spaces):
	"""Check if hallways connect to stair spaces via doors.

	This builds adjacency between spaces that share a door opening, then
	computes which hallways are linked to stairs either directly (door)
	or transitively via other hallways (hallway -> hallway -> ... -> stair).
	"""
	# Identify stair and hallway spaces
	stair_spaces = {}
	hallway_spaces = {}

	spaces_list = list(spaces)
	for sp in spaces_list:
		sid = getattr(sp, 'GlobalId', None) or str(id(sp))
		name = (getattr(sp, 'Name', None) or '').lower()
		if 'stair' in name:
			stair_spaces[sid] = sp
		elif 'hallway' in name:
			hallway_spaces[sid] = sp

	# Build adjacency map between spaces (space_gid -> set(space_gid)) using doors
	adjacency = { (getattr(sp, 'GlobalId', None) or str(id(sp))): set() for sp in spaces_list }

	# Build helper map: opening_gid -> list of containing elements (walls etc.)
	opening_to_containers = {}
	for relv in model.by_type('IfcRelVoidsElement'):
		container = getattr(relv, 'RelatingBuildingElement', None)
		opening = getattr(relv, 'RelatedOpeningElement', None)
		if not opening:
			continue
		ogid = getattr(opening, 'GlobalId', None) or str(id(opening))
		if container is not None:
			opening_to_containers.setdefault(ogid, []).append(container)

	# We'll also record which door connects to which spaces and which containers its opening sits in
	door_map = {}
	door_container_map = {}

	for rel in model.by_type('IfcRelFillsElement'):
		opening = getattr(rel, 'RelatingOpeningElement', None)
		door = getattr(rel, 'RelatedBuildingElement', None)
		if not (opening and door and door.is_a('IfcDoor')):
			continue

		# Get opening centroid (try opening first, then door as fallback)
		oc = get_element_centroid(opening)
		if oc is None:
			oc = get_element_centroid(door)
		if oc is None:
			continue

		# Find all spaces that contain this opening
		connected_spaces = []
		margin = 500  # 500mm margin
		for sp in spaces_list:
			sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
			verts = get_vertices(sp)
			if verts is not None and len(verts) > 0:
				verts = verts * 1000.0  # Convert to mm
				minv = verts.min(axis=0)
				maxv = verts.max(axis=0)
				if minv[0] - margin <= oc[0] <= maxv[0] + margin and \
				   minv[1] - margin <= oc[1] <= maxv[1] + margin:
					connected_spaces.append(sp_gid)

		# Link all connected spaces pairwise in adjacency
		for i in range(len(connected_spaces)):
			for j in range(i + 1, len(connected_spaces)):
				a = connected_spaces[i]
				b = connected_spaces[j]
				adjacency.setdefault(a, set()).add(b)
				adjacency.setdefault(b, set()).add(a)

		# Record door -> spaces map
		dg = getattr(door, 'GlobalId', None) or str(id(door))
		door_map.setdefault(dg, set()).update(connected_spaces)

		# Record container types (walls etc.) for this opening so we can check compartmentation
		og = getattr(opening, 'GlobalId', None) or str(id(opening))
		containers = opening_to_containers.get(og, [])
		door_container_map[dg] = [c.is_a() for c in containers]

	# Now compute which hallways are linked to stairs.
	# Start from stairs and propagate through hallway nodes only.
	linked_hallways = set()
	from collections import deque
	q = deque()

	# Enqueue all hallways that are directly adjacent to a stair
	for stair_gid in stair_spaces:
		for nb in adjacency.get(stair_gid, set()):
			if nb in hallway_spaces and nb not in linked_hallways:
				linked_hallways.add(nb)
				q.append(nb)

	# BFS across hallway nodes only
	while q:
		current = q.popleft()
		for nb in adjacency.get(current, set()):
			if nb in hallway_spaces and nb not in linked_hallways:
				linked_hallways.add(nb)
				q.append(nb)

	# Prepare final map for all hallways
	space_linked_to_stairs = {}
	for sid in hallway_spaces:
		space_linked_to_stairs[sid] = (sid in linked_hallways)

	# Ensure all spaces have an entry (False for non-hallways)
	for sp in spaces_list:
		sid = getattr(sp, 'GlobalId', None) or str(id(sp))
		space_linked_to_stairs.setdefault(sid, False)

	return space_linked_to_stairs, door_map, door_container_map


def analyze_door(door, door_map, opening_map):
	name = getattr(door, 'Name', None) or str(door)
	gid = getattr(door, 'GlobalId', None) or str(id(door))
	full = f"{name} [{gid}]"
	width = get_numeric(door, ['overallwidth', 'width', 'doorwidth'])
	op = opening_map.get(gid)
	if not width and op:
		if getattr(op, 'Representation', None):
			for rep in op.Representation.Representations:
				for it in getattr(rep, 'Items', []) or []:
					if it.is_a('IfcExtrudedAreaSolid'):
						prof = getattr(it, 'SweptArea', None)
						if prof and prof.is_a('IfcRectangleProfileDef'):
							w = to_mm(getattr(prof, 'YDim', None)) or to_mm(getattr(prof, 'XDim', None))
							if w:
								width = w
								break
				if width:
					break
	issues = []
	if width is None:
		issues.append('width unknown')
	elif width < DOOR_MIN:
		issues.append(f'width {width:.0f}mm < {DOOR_MIN}mm')
	linked = door_map.get(gid, set())
	return {'name': full, 'width_mm': width, 'linked_spaces': linked, 'issues': issues}


def analyze_stair(flight):
	name = getattr(flight, 'Name', None) or str(flight)
	gid = getattr(flight, 'GlobalId', None) or str(id(flight))
	full = f"{name} [{gid}]"
	width = get_numeric(flight, ['actual run width', 'actualrunwidth', 'run width', 'width', 'tread'])
	if width is None and getattr(flight, 'Representation', None):
		for rep in flight.Representation.Representations:
			for it in getattr(rep, 'Items', []) or []:
				if it.is_a('IfcExtrudedAreaSolid'):
					prof = getattr(it, 'SweptArea', None)
					if prof and prof.is_a('IfcRectangleProfileDef'):
						xd = float(getattr(prof, 'XDim', 0) or 0)
						yd = float(getattr(prof, 'YDim', 0) or 0)
						xd = xd if xd > 100 else xd * 1000.0
						yd = yd if yd > 100 else yd * 1000.0
						width = max(xd, yd)
						break
			if width is not None:
				break
	issues = []
	if width is None:
		issues.append('width unknown')
	elif width + 1e-6 < STAIR_MIN:
		issues.append(f'width {width:.0f}mm < {STAIR_MIN}mm')
	return {'name': full, 'width_mm': width, 'issues': issues}


def _door_swing_heuristic(door):
	"""Try a simple heuristic to determine if a door swings away from an adjacent space.

	Returns 'away', 'toward', or 'unknown'. This is a best-effort string-match heuristic
	from door attributes (Name, ObjectType, Description, OperationType). If nothing
	meaningful is found we return 'unknown'.
	"""
	# Prefer explicit IFC attribute OperationType when available
	try:
		op = getattr(door, 'OperationType', None)
		if op:
			op_s = str(op).lower()
			# Common textual/enum hints indicating outward/inward swing
			if 'out' in op_s or 'outward' in op_s or 'opens_out' in op_s or 'open_out' in op_s:
				return 'away'
			if 'in' in op_s or 'inward' in op_s or 'opens_in' in op_s or 'open_in' in op_s:
				return 'toward'
			# Some enumerations include SWING + direction, try to detect 'swing' with qualifier
			if 'swing' in op_s:
				if 'out' in op_s or 'outward' in op_s:
					return 'away'
				if 'in' in op_s or 'inward' in op_s:
					return 'toward'
	except Exception:
		pass

	# Fallback: inspect other textual attributes (Name, ObjectType, Description, Tag)
	candidates = []
	for attr in ('PredefinedType', 'ObjectType', 'Name', 'Description', 'Tag'):
		try:
			v = getattr(door, attr, None)
			if v:
				candidates.append(str(v).lower())
		except Exception:
			continue

	txt = ' '.join(candidates)
	if not txt:
		return 'unknown'

	if 'outward' in txt or 'opens out' in txt or 'opens away' in txt or 'open out' in txt or 'open outwards' in txt:
		return 'away'
	if 'inward' in txt or 'opens in' in txt or 'open in' in txt or 'opens into' in txt or 'into' in txt:
		return 'toward'
	if 'swing' in txt:
		if 'out' in txt or 'outward' in txt:
			return 'away'
		if 'in' in txt or 'inward' in txt:
			return 'toward'

	return 'unknown'


def analyze_stair_compartmentation(model, analyses, door_map, door_container_map, spaces_list):
	"""Check compartmentation for actual IfcStairFlight elements only.

	Heuristics implemented:
	- The stair flight must span (intersect) at least two building storey elevations.
	- The stair flight should have at least one door connecting its containing space(s).
	- Doors leading to the stair should be installed in walls (checked via IfcRelVoidsElement container)
	  and ideally swing away from the stair (heuristic based on textual door attributes).

	Returns a list of failing stair records with reasons and offending doors.
	"""
	failing = []

	# Quick lookup of doors by GlobalId
	doors_by_gid = { (getattr(d, 'GlobalId', None) or str(id(d))): d for d in model.by_type('IfcDoor') }

	# Collect building storey elevations (mm)
	storeys = []
	for bs in model.by_type('IfcBuildingStorey'):
		elev = getattr(bs, 'Elevation', None)
		if elev is None:
			continue
		try:
			ev = float(elev)
			ev_mm = ev if ev > 100 else ev * 1000.0
			storeys.append(ev_mm)
		except Exception:
			continue
	storeys = sorted(storeys)

	# Helper: find spaces that contain a product (via IfcRelContainedInSpatialStructure or spatial centroid fallback)
	rels = model.by_type('IfcRelContainedInSpatialStructure')
	def _find_containing_spaces(product):
		gids = set()
		for r in rels:
			for el in getattr(r, 'RelatedElements', []) or []:
				if el == product:
					cont = getattr(r, 'RelatingStructure', None)
					if cont is not None and cont.is_a('IfcSpace'):
						gids.add(getattr(cont, 'GlobalId', None) or str(id(cont)))
		# fallback: centroid-in-space test
		if not gids:
			pc = get_element_centroid(product)
			if pc is not None:
				margin = 500
				for sp in spaces_list:
					sp_gid = getattr(sp, 'GlobalId', None) or str(id(sp))
					verts = get_vertices(sp)
					if verts is not None and len(verts) > 0:
						verts = verts * 1000.0
						minv = verts.min(axis=0); maxv = verts.max(axis=0)
						if minv[0] - margin <= pc[0] <= maxv[0] + margin and minv[1] - margin <= pc[1] <= maxv[1] + margin:
							gids.add(sp_gid)
		return gids

	# Iterate through true stair flights
	for flight in model.by_type('IfcStairFlight'):
		fid = getattr(flight, 'GlobalId', None) or str(id(flight))
		fname = getattr(flight, 'Name', None) or str(flight)
		verts = get_vertices(flight)
		if verts is None or len(verts) == 0:
			# fallback: treat as unknown geometry -> mark for manual check
			failing.append({'stair_name': f"{fname} [{fid}]", 'space_issues': ['no geometry found for stair flight'], 'offending_doors': []})
			continue
		verts = verts * 1000.0
		minz = float(verts[:, 2].min())
		maxz = float(verts[:, 2].max())

		# Check storey intersection: count distinct storeys whose elevation lies within flight z-range
		tol = 500.0
		intersecting = [ev for ev in storeys if (ev >= minz - tol and ev <= maxz + tol)]
		issues = []
		if len(intersecting) < 2:
			issues.append('stair flight does not span multiple building storey elevations')

		# Find containing spaces for this flight
		containing_space_gids = _find_containing_spaces(flight)

		# Gather adjacent doors by checking door_map entries that reference any containing space
		adjacent_doors = []
		for dg, sids in door_map.items():
			if any(sg in sids for sg in containing_space_gids):
				adjacent_doors.append(dg)

		# Filter candidates by centroid proximity (tighten margins to reduce false positives)
		def _filter_by_centroid(candidates):
			out = []
			if not candidates:
				return out
			minxy = verts[:, :2].min(axis=0); maxxy = verts[:, :2].max(axis=0)
			margin_xy = 500.0
			for dg in candidates:
				door = doors_by_gid.get(dg)
				if door is None:
					continue
				c = get_element_centroid(door)
				if c is None:
					continue
				cx, cy, cz = c
				if (cx >= minxy[0] - margin_xy and cx <= maxxy[0] + margin_xy and
					cy >= minxy[1] - margin_xy and cy <= maxxy[1] + margin_xy and
					cz >= minz - tol and cz <= maxz + tol):
					out.append(dg)
			return out

		adjacent_doors = _filter_by_centroid(adjacent_doors)

		if not adjacent_doors:
			# If no doors found via containing spaces, try spatial proximity between all doors and flight
			minxy = verts[:, :2].min(axis=0); maxxy = verts[:, :2].max(axis=0)
			margin_xy = 500.0
			for dg in door_map.keys():
				door = doors_by_gid.get(dg)
				if door is None:
					continue
				c = get_element_centroid(door)
				if c is None:
					continue
				cx, cy, cz = c
				if (cx >= minxy[0] - margin_xy and cx <= maxxy[0] + margin_xy and
					cy >= minxy[1] - margin_xy and cy <= maxxy[1] + margin_xy and
					cz >= minz - tol and cz <= maxz + tol):
					adjacent_doors.append(dg)

		offending_doors = []
		# Check each adjacent door for container (wall) and swing direction
		for dg in adjacent_doors:
			door = doors_by_gid.get(dg)
			reason_parts = []
			conts = door_container_map.get(dg, [])
			in_wall = any('IfcWall' in c for c in conts) or any(c == 'IfcWall' or c == 'IfcWallStandardCase' for c in conts)
			if not in_wall:
				reason_parts.append('door not installed in wall')

			swing = _door_swing_heuristic(door) if door is not None else 'unknown'
			if swing == 'toward':
				reason_parts.append('door swings toward stair')
			elif swing == 'unknown':
				# mark unknown as a warning; include as failing so user can inspect
				reason_parts.append('door swing unknown')

			if reason_parts:
				offending_doors.append({'door_gid': dg, 'reasons': reason_parts, 'door_name': getattr(door, 'Name', None)})

		if issues or offending_doors:
			failing.append({'stair_name': f"{fname} [{fid}]", 'space_issues': issues, 'offending_doors': offending_doors})

	return failing


def is_corridor(space, analysis):
	name = analysis.get('name') or ''
	if any(k in (name or '').lower() for k in ['hallway', 'corridor', 'passage', 'circulation']):
		return True
	return False


def main():
	# (thresholds are hard-coded in constants at the top of this file)

	model = ifcopenshell.open(IFC_PATH)
	spaces = model.by_type('IfcSpace')
	analyses = {}
	for sp in spaces:
		sid = getattr(sp, 'GlobalId', None) or str(id(sp))
		length, width = extract_dimensions_from_geometry(sp)
        
		if width == 0:
			A = get_numeric(sp, ['area'])
			P = get_numeric(sp, ['perimeter'])
			if A and P:
				if A > 1000:
					A_m2 = A / 1000000.0
				else:
					A_m2 = A
				P_m = P if P > 100 else P * 1000.0
				try:
					s = P_m / 2.0
					w = (s - math.sqrt(max(0, s * s - 4 * A_m2))) / 2.0
					length = (A_m2 / w) * 1000.0
					width = w * 1000.0
				except Exception:
					pass
		analyses[sid] = {'space': sp, 'name': getattr(sp, 'Name', None), 'type': getattr(sp, 'LongName', None), 'width': width, 'length': length}

	space_linked, door_map, door_container_map = build_space_linkages(model, spaces)
    
	for sid, a in analyses.items():
		linked_to_stairs = space_linked.get(sid, False)
		a['links_to_stairs'] = linked_to_stairs
		a['is_elongated'] = (a['length'] >= 3 * a['width']) if a['width'] > 0 else False

	corridors = [(sid, a) for sid, a in analyses.items() if is_corridor(a['space'], a)]
	doors = [analyze_door(d, door_map, door_container_map) for d in model.by_type('IfcDoor')]
	failing_doors = [d for d in doors if d['issues']]
	flights = model.by_type('IfcStairFlight')
	stairs = [analyze_stair(f) for f in flights]
	failing_stairs = [s for s in stairs if s['issues']]

	# Run compartmentation checks for stairs (doors in walls, doors swing away)
	stair_comp_failures = analyze_stair_compartmentation(model, analyses, door_map, door_container_map, spaces)

	failing_corridors = []
	for sid, a in corridors:
		checks = 0; issues = []
		if a['width'] >= CORRIDOR_MIN:
			checks += 1
		else:
			issues.append(f"Width is {a['width']:.0f}mm")
		if a['links_to_stairs']:
			checks += 1
		else:
			issues.append(f"Does not link to stairs via doors/openings")
		if checks < 2:
			failing_corridors.append({'name': f"{a.get('name')} [{sid}]", 'issues': issues})

	# determine passing corridors (those in corridors but not in failing_corridors)
	failing_sids = set()
	for fc in failing_corridors:
		n = fc.get('name','')
		if '[' in n and n.endswith(']'):
			sid_parsed = n.split('[')[-1][:-1]
			failing_sids.add(sid_parsed)

	passing_corridors = []
	for sid, a in corridors:
		if sid in failing_sids:
			continue
		checks_passed = []
		w = a.get('width', 0) or 0
		if w >= CORRIDOR_MIN:
			checks_passed.append('width')
		if a.get('links_to_stairs'):
			checks_passed.append('stairs')
		ratio = (a['length'] / a['width']) if a['width'] > 0 else 0
		passing_corridors.append({
			'name': f"{a.get('name')} [{sid}]",
			'width_mm': float(w),
			'length_mm': float(a.get('length', 0) or 0),
			'links_stairs': a.get('links_to_stairs', False),
			'ratio': float(ratio),
			'passed': checks_passed,
		})

	print(f"Amount of doors in model: {len(doors)}")
	print(f"Amount of doors that don't fulfill the requirements: {len(failing_doors)}")
	if failing_doors:
		print("The names of the doors and what is not right with them:")
		for d in failing_doors:  # FIXED: was "fanailing_doors"
			print(f" - {d['name']}: {', '.join(d['issues'])}")
	else:
		print("No failing doors.")

	print(f"\nAmount of corridors: {len(corridors)}")
	print(f"Amount of corridors that don't fulfill the requirements: {len(failing_corridors)}")
	if failing_corridors:
		print("The names of the corridors and what is not right with them:")
		for c in failing_corridors:
			print(f" - {c['name']}: {', '.join(c['issues'])}")
	else:
		print("No failing corridors.")

	# Print passing (right) corridors
	print(f"\nAmount of corridors that fulfill the requirements (passing): {len(passing_corridors)}")

	print(f"\nAmount of stairs: {len(stairs)}")
	print(f"Amount of stairs that don't fulfill the requirements: {len(failing_stairs)}")
	if failing_stairs:
		print("The names of the stairs and what is not right with them:")
		for s in failing_stairs:
			print(f" - {s['name']}: {', '.join(s['issues'])}")
	else:
		print("No failing stairs.")

	# Report compartmentation failures (doors/walls/swing)
	if stair_comp_failures:
		print('\nStair compartmentation failures:')
		for f in stair_comp_failures:
			print(f" - {f['stair_name']}")
			for it in f.get('space_issues', []):
				print(f"    * {it}")
			for d in f.get('offending_doors', []):
				dn = d.get('door_name') or d.get('door_gid')
				rs = ', '.join(d.get('reasons', []))
				print(f"    - Door {dn}: {rs}")
	else:
		print('\nNo stair compartmentation failures detected.')


if __name__ == '__main__':
	main()
