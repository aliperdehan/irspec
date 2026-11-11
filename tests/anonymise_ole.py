"""Anonymise a Shimadzu OLE2 file (.vqud/.vspd), every stream keeping its size: how the UV-Vis
test files in tests/data/ were made from the author's instrument files (tests/data/README.md).

    python3 tests/anonymise_ole.py IN OUT --spec SPEC.json

Needs olefile. The SPEC files used are not published (they name what was blanked).

SPEC: {"tables": {"Sample Table": {"keep": ["2"], "rename": {"2": "Unknown 1"}}, ...},
       "reading_columns": ["WL", "Result", "Conc"],   # prefixes of numeric columns to star
       "keep_columns": {"Standard Table": ["Conc"]},   # numeric columns kept as they are
       "replace": [["<serial number>", "<as many zeros>"], ...]}  # same length, every stream

A row whose group is not kept: its readings (and Sample Name) become stars of the same length
and the doubles the "no value" sentinel. The Column Data caches of the starred columns are
starred whole. Then every free sector and free mini sector, and the slack after each stream's
end in its last sector, is zeroed, so no stale bytes remain.
"""
import json
import shutil
import struct
import sys

import olefile

MARKER = b'\x01\x00\x00\x00\x03\x00\x00\x00'
SENTINEL = struct.pack('<d', 1.7976931348623157e+308)
FREE = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE


def records(data):
    idx = 0
    while True:
        pos = data.find(MARKER, idx)
        if pos == -1:
            return
        p = pos + 8
        l1 = data[p]
        p += 1
        rid = data[p:p + l1].decode('latin1')
        p += l1
        l2 = data[p]
        yield rid, p + 1, l2
        idx = p + 1 + l2


def group(rid):
    return rid[:-4] if rid.endswith('-Avg') else rid.split('-')[0]


def star_cache(data):
    """[u16 id][u16 FFFF][u16 count] then count x ([len][ascii]) -> every value starred."""
    out = bytearray(data)
    count = struct.unpack_from('<H', data, 4)[0]
    p = 6
    for _ in range(count):
        n = out[p]
        out[p + 1:p + 1 + n] = b'*' * n
        p += 1 + n
    return bytes(out)


def scrub_streams(ole, spec):
    changed = {}
    star_cols = tuple(spec.get('reading_columns', []))
    for table, rule in spec.get('tables', {}).items():
        keep = set(rule['keep'])
        rename = rule.get('rename', {})
        kept_cols = set(spec.get('keep_columns', {}).get(table, []))
        for st in ole.listdir(streams=True, storages=False):
            if st[:2] != [table, 'Column Configuration'] or st[2] == '#ColNodes#':
                continue
            col = st[2]
            numeric = col.startswith(star_cols) and col not in kept_cols
            if not (numeric or col == 'Sample Name'):
                continue
            data = bytearray(ole.openstream(st).read())
            for rid, vpos, n in list(records(bytes(data))):
                g = group(rid)
                if col == 'Sample Name':
                    if g in rename:
                        new = rename[g].encode('latin1')
                        assert len(new) == n, (rename[g], n)
                        data[vpos:vpos + n] = new
                    elif g not in keep and n:
                        data[vpos:vpos + n] = b'*' * n
                elif g not in keep and n and bytes(data[vpos:vpos + n]) != b'*' * n:
                    data[vpos:vpos + n] = b'*' * n
                    data[vpos + n:vpos + n + 8] = SENTINEL
                    data[vpos + n + 8:vpos + n + 16] = SENTINEL
            changed[tuple(st)] = bytes(data)
        for st in ole.listdir(streams=True, storages=False):
            if st[:2] == [table, 'Column Data'] and st[2].startswith(star_cols) \
                    and st[2] not in kept_cols:
                changed[tuple(st)] = star_cache(ole.openstream(st).read())
    for st in ole.listdir(streams=True, storages=False):
        data = changed.get(tuple(st)) or ole.openstream(st).read()
        new = data
        for a, b in spec.get('replace', []):
            a, b = a.encode('latin1'), b.encode('latin1')
            assert len(a) == len(b), (a, b)
            new = new.replace(a, b)
        if new != data or tuple(st) in changed:
            changed[tuple(st)] = new
    for st, data in changed.items():
        ole.write_stream(list(st), data)
    return sorted('/'.join(s) for s in changed)


def chain(fat, start):
    out = []
    while start not in (ENDOFCHAIN, FREE) and start < len(fat):
        out.append(start)
        start = fat[start]
    return out


def zero_slack(path):
    """Zero free sectors, free mini sectors and the slack after every stream's end."""
    ole = olefile.OleFileIO(path)
    ss, mss = ole.sectorsize, ole.minisectorsize
    fat = list(ole.fat)
    zeros = []                                     # (file offset, length)
    for i, nxt in enumerate(fat):
        if nxt == FREE and (i + 1) * ss < ole._filesize:
            zeros.append(((i + 1) * ss, ss))
    root = ole.root
    mini_chain = chain(fat, root.isectStart)

    def mini_offset(j):
        off = j * mss
        return (mini_chain[off // ss] + 1) * ss + off % ss

    ole.loadminifat()
    minifat = list(ole.minifat)
    nmini = root.size // mss
    for j in range(min(nmini, len(minifat))):
        if minifat[j] == FREE:
            zeros.append((mini_offset(j), mss))
    for e in ole.direntries:
        if e is None or e.entry_type != olefile.STGTY_STREAM or e.size == 0:
            continue
        if e.size < ole.minisectorcutoff:
            mc = chain(minifat, e.isectStart)
            used = e.size - (len(mc) - 1) * mss
            if mc and used < mss:
                zeros.append((mini_offset(mc[-1]) + used, mss - used))
        else:
            c = chain(fat, e.isectStart)
            used = e.size - (len(c) - 1) * ss
            if c and used < ss:
                zeros.append(((c[-1] + 1) * ss + used, ss - used))
    # the mini stream's own last sector, after its end
    used = root.size - (len(mini_chain) - 1) * ss
    if mini_chain and used < ss:
        zeros.append(((mini_chain[-1] + 1) * ss + used, ss - used))
    ole.close()
    with open(path, 'r+b') as f:
        for off, n in zeros:
            f.seek(off)
            f.write(b'\0' * n)
    return len(zeros)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    spec = json.load(open(sys.argv[sys.argv.index('--spec') + 1]))
    shutil.copyfile(src, dst)
    ole = olefile.OleFileIO(dst, write_mode=True)
    for s in scrub_streams(ole, spec):
        print('changed:', s)
    ole.close()
    print('zeroed regions:', zero_slack(dst))


if __name__ == '__main__':
    main()
