#!/usr/bin/env python3
"""Check this gathering's output structure and bytes offline, not visual quality."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from make_preview import decode_png

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://api.imd.fun/artifacts/'
BARE = '1694079b8c096876644b7db6f84112f2550b53ad024540401ad702809cb35941'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def jpeg_size(data):
    assert data[:2] == b'\xff\xd8' and data[-2:] == b'\xff\xd9'
    pos = 2
    while pos < len(data):
        assert data[pos] == 255
        code = data[pos+1]
        length = struct.unpack_from('>H', data, pos+2)[0]
        if code == 0xc0:
            depth, h, w, channels = struct.unpack_from('>BHHB', data, pos+4)
            assert depth == 8 and channels == 3
            return w, h
        assert code != 0xda, 'missing baseline JPEG frame'
        pos += length + 2
    raise AssertionError('missing JPEG size')


def traits(record):
    assert set(record) == {'name', 'image', 'attributes'}
    result = {a['trait_type']: a['value'] for a in record['attributes']}
    assert len(result) == len(record['attributes'])
    return result


def main():
    png = ROOT / 'artifacts/gathering/wall-v3.png'
    raw = png.read_bytes()
    assert decode_png(png)[:2] == (1254, 1254)
    alias = ROOT / 'artifacts/gathering/wall.png'
    # The PNG is delivered by the named-output uploader. Keep the current-wall
    # path as a relative alias, rather than bundling its 3 MB bytes a second time.
    assert alias.is_symlink(), 'current wall must not duplicate the declared output'
    assert alias.readlink() == Path('wall-v3.png')
    assert alias.resolve() == png.resolve() and alias.read_bytes() == raw
    assert png.is_file() and not png.is_symlink(), 'declared upload needs actual PNG bytes'
    uploaded_source = subprocess.run(['git', 'ls-files', '--', str(png.relative_to(ROOT))],
                                     cwd=ROOT, check=True, capture_output=True).stdout
    assert not uploaded_source, 'declared PNG must stay outside the source bundle'
    digest = hashlib.sha256(raw).hexdigest()
    record = read(ROOT / 'dist/gathering/03.json')
    attributes = traits(record)
    assert record['image'] == URL + digest
    assert set(attributes) == {'Cave', 'Wall', 'Number', 'Left behind', 'Meaning', 'One thing'}
    assert attributes['Cave'] == 'Roots' and attributes['Wall'] == 'Gathering'
    assert type(attributes['Number']) is int and attributes['Number'] == 3
    assert attributes['One thing'] == 'Gathering'
    jpg = ROOT / 'dist/gathering/03.jpg'
    assert jpeg_size(jpg.read_bytes()) == (512, 512)
    assert jpg.stat().st_size < 100_000
    placeholder = {'name': 'Not painted yet', 'image': URL + BARE,
                   'attributes': [{'trait_type': 'Cave', 'value': 'Roots'}]}
    index = (ROOT / 'dist/index.html').read_text(encoding='utf-8')
    future, painted, numbered = 0, 0, 0
    for wall in ['line-1', 'line-2', 'line-3', 'line-4', 'gathering']:
        folder = ROOT / 'dist' / wall
        assert all((folder / f'{n:02d}.json').is_file() for n in range(1, 22))
        paths = sorted(folder.glob('[0-9][0-9].json'), reverse=True)
        ordering = []
        for path in paths:
            numbered += 1
            assert f'{wall}/{path.name}' in index
            item = read(path)
            if item['name'] == 'Not painted yet':
                assert item == placeholder
                assert not path.with_suffix('.jpg').exists()
                future += 1
            else:
                values = traits(item)
                expected_wall = 'Gathering' if wall == 'gathering' else 'Line ' + wall[-1]
                assert values['Cave'] == 'Roots' and values['Wall'] == expected_wall
                assert type(values['Number']) is int and values['Number'] == int(path.stem)
                assert set(values) == {'Cave', 'Wall', 'Number', 'Left behind', 'Meaning', 'One thing'}
                assert len(item['image']) == len(URL) + 64 and item['image'].startswith(URL)
                int(item['image'][len(URL):], 16)
                assert jpeg_size(path.with_suffix('.jpg').read_bytes()) == (512, 512)
                ordering.append(index.index(f'id="{wall}-{path.stem}"'))
                painted += 1
        assert ordering == sorted(ordering), 'painted records must be newest first'
    assert (numbered, painted, future) == (112, 14, 98)
    goals = read(ROOT / 'dist/goals.json')
    assert goals == [{'line': n, 'goal': (ROOT / f'line-{n}/GOAL.md').read_text().strip()}
                     for n in range(1, 5)]
    one = read(ROOT / 'dist/one.json')
    assert one['name'] == 'One' and one['image'] == URL + digest
    assert traits(one) == {'Cave': 'Roots', 'Wall': 'One', 'Number': 736, 'Meaning': attributes['Meaning']}
    # All line work, line records, and the prior gathering record/preview stay exact.
    tracked = subprocess.run(['git', 'ls-files', '-z', 'line-1', 'line-2', 'line-3', 'line-4',
                              'dist/line-1', 'dist/line-2', 'dist/line-3', 'dist/line-4',
                              'dist/gathering/01.json', 'dist/gathering/01.jpg',
                              'dist/gathering/02.json', 'dist/gathering/02.jpg'],
                             cwd=ROOT, check=True, capture_output=True).stdout.split(b'\0')
    unchanged = 0
    for item in filter(None, tracked):
        name = item.decode()
        original = subprocess.run(['git', 'show', f'HEAD:{name}'], cwd=ROOT,
                                  check=True, capture_output=True).stdout
        assert (ROOT / name).read_bytes() == original, f'changed ancestor: {name}'
        unchanged += 1
    for folder in ('gathering', 'shared', 'dist'):
        for path in (ROOT / folder).rglob('*'):
            if path.is_file():
                assert path.stat().st_size <= 100_000, f'oversize: {path}'
    for row in read(ROOT / 'shared/replay-review/provenance.json'):
        snapshot = (ROOT / row['snapshot']).read_bytes()
        assert snapshot == (ROOT / row['source']).read_bytes()
        assert hashlib.sha256(snapshot).hexdigest() == row['sha256']
    # The existing shared tool keeps its explicitly documented earlier snapshots.
    for path in (ROOT / 'shared/reviewed-timeline/vendor').glob('*.py'):
        relative = str(path.relative_to(ROOT))
        original = subprocess.run(['git', 'show', f'HEAD:{relative}'], cwd=ROOT,
                                  check=True, capture_output=True).stdout
        assert path.read_bytes() == original
    checks = read(ROOT / 'gathering/check-results.json')
    assert checks['checks_passed'] and checks['line_files_unchanged'] and checks['test_count'] == 169
    demos = read(ROOT / 'gathering/demo-results.json')
    assert demos['checks_passed'] and len(demos['examples']) == 16
    assert all(x['passed'] for x in demos['examples'])
    for prefix in ('line-1', 'line-2', 'line-3', 'line-4',
                   'dist/line-1', 'dist/line-2', 'dist/line-3', 'dist/line-4'):
        assert not subprocess.run(['git', 'diff', 'HEAD', '--', prefix], cwd=ROOT,
                                  check=True, capture_output=True).stdout
    review = read(ROOT / 'gathering/wall-review.json')
    assert review['wall_sha256'] == digest
    assert review['unmet_visual_requirements'] == []
    result = {'structural_checks': 'passed', 'unchanged_tracked_ancestor_files': unchanged,
              'future_records': future, 'painted_records': painted, 'numbered_records': numbered, 'goals': 4,
              'wall': {'path': 'artifacts/gathering/wall-v3.png', 'alias': 'artifacts/gathering/wall.png',
                       'format': 'PNG RGB8', 'width': 1254, 'height': 1254, 'bytes': len(raw), 'sha256': digest},
              'preview': {'path': 'dist/gathering/03.jpg', 'format': 'JPEG', 'width': 512,
                          'height': 512, 'bytes': jpg.stat().st_size},
              'source_packaging': {'current_wall_alias': str(alias.readlink()),
                                   'alias_entry_bytes': alias.lstat().st_size,
                                   'duplicate_png_bytes_removed': len(raw) - alias.lstat().st_size,
                                   'declared_output_tracked': False},
              'visual_review': review['observations'], 'visual_limits': review['limits'],
              'unmet_visual_requirements': review['unmet_visual_requirements'],
              'tests': {'line_passed': 122, 'shared_passed': 35, 'additional_line_passed': 12,
                        'expected_failures': 0}, 'cli_examples': 16}
    (ROOT / 'gathering/validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
