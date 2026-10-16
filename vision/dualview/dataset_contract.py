"""Validate explicit real paired-image partitions before any model work (stdlib only)."""
import csv
from pathlib import Path

DEFAULT_SHAPES = ['cube', 'cylinder', 'cone', 'prism']
REQUIRED = {'pair_id', 'physical_object_id', 'session_id', 'split', 'top',
            'side', 'color', 'shape', 'source_kind', 'top_parent_id', 'side_parent_id'}

def validate_shapes(shapes):
    if not isinstance(shapes, list) or len(shapes) < 2:
        raise ValueError('shapes must contain at least two unique class identifiers')
    if any(not isinstance(s, str) or not s or not s.isascii() or
           any(not (c.isalnum() or c == '_') for c in s) for s in shapes):
        raise ValueError('shape identifiers must be nonempty ASCII letters/numbers/underscores')
    if len(set(shapes)) != len(shapes):
        raise ValueError('shapes must contain unique class identifiers')
    return list(shapes)

def load_pairs(csv_path, shapes=None):
    shapes = validate_shapes(DEFAULT_SHAPES if shapes is None else shapes)
    path = Path(csv_path).resolve()
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError('Missing CSV fields: ' + ', '.join(sorted(REQUIRED - set(reader.fieldnames or []))))
        rows = list(reader)
    if not rows:
        raise ValueError('Empty paired-image dataset')
    seen_ids = set(); seen_pairs = set(); partitions = {}; truths = {}
    for number, raw in enumerate(rows, 2):
        row = {key: value.strip() if isinstance(value, str) else value for key, value in raw.items()}
        if any(not row.get(key) for key in REQUIRED):
            raise ValueError(f'Row {number}: required field is empty')
        if row['split'] not in {'train', 'val', 'test'}:
            raise ValueError(f'Row {number}: split must be train/val/test')
        if row['color'] not in {'red', 'blue'} or row['shape'] not in shapes:
            raise ValueError(f'Row {number}: unsupported color/shape')
        if row['source_kind'] not in {'real', 'derived', 'synthetic'}:
            raise ValueError(f'Row {number}: source_kind must be real/derived/synthetic')
        if row['split'] != 'train' and row['source_kind'] != 'real':
            raise ValueError(f'Row {number}: validation/test must be real captures')
        if row['pair_id'] in seen_ids:
            raise ValueError(f'Row {number}: duplicate pair_id')
        seen_ids.add(row['pair_id'])
        for view in ['top', 'side']:
            image = (path.parent / row[view]).resolve()
            if not image.is_file():
                raise ValueError(f'Row {number}: missing {view} image: {image}')
            row[view] = str(image)
        if row['top'] == row['side']:
            raise ValueError(f'Row {number}: top and side cannot be the same image')
        pair_key = (row['top'], row['side'])
        if pair_key in seen_pairs:
            raise ValueError(f'Row {number}: duplicate image pair')
        seen_pairs.add(pair_key)
        # Each axis is checked separately, never just (object,session) tuples.
        keys = [('object', row['physical_object_id']), ('session', row['session_id']),
                ('parent', row['top_parent_id']), ('parent', row['side_parent_id']),
                ('image', row['top']), ('image', row['side'])]
        for key in keys:
            previous = partitions.setdefault(key, row['split'])
            if previous != row['split']:
                raise ValueError(f'Row {number}: cross-split leakage for {key[0]} {key[1]}')
            if key[0] in {'object','parent','image'}:
                truth=(row['color'],row['shape'])
                if truths.setdefault(key,truth)!=truth:
                    raise ValueError(f'Row {number}: inconsistent truth for {key[0]} {key[1]}')
        raw.clear(); raw.update(row)
    for split in ['train', 'val']:
        if not any(row['split'] == split for row in rows):
            raise ValueError(f'Missing {split} partition')
    if {row['shape'] for row in rows if row['split'] == 'train'} != set(shapes):
        raise ValueError('Training partition must cover all configured shapes')
    return rows
