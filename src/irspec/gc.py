"""The GC session kind; gc_tool remains the reader, analysis and output oracle.

An entry yields a full figure followed by its optional cropped figure. Requests in a
crop's removed ranges are omitted before analysis, including the solvent request.
"""
import io
import os
import tempfile

import numpy as np

from . import gc_tool as tool
from . import kinds, spa_tool


def validate(entry):
    if 'peaks' in entry:
        raise ValueError('name GC peaks in `compounds`, not `peaks`')
    if not entry.get('full', True) and not entry.get('crop'):
        raise ValueError('full: false requires crop')


def figure_settings(entry, cropped=False):
    """The figure's analysis settings, with crop requests restricted to retained time."""
    e = dict(entry)
    if cropped:
        c = e['crop']
        ranges = [tuple(float(v) for v in r.strip().split('-'))
                  for r in c.get('exclude', '').split(',') if r.strip()]
        for key in ('compounds', 'solvent'):
            e[key] = ','.join(item.strip() for item in e.get(key, '').split(',')
                              if item.strip() and retained(float(item.partition('=')[0]), c, ranges))
        if c.get('correct'):
            e['baseline'] = 'none'
    return e


def retained(t, crop, ranges):
    return ((crop.get('xmin') is None or t >= crop['xmin'])
            and (crop.get('xmax') is None or t <= crop['xmax'])
            and not any(a <= t <= b for a, b in ranges))


def analyse(source, settings, no_requests=False):
    try:
        res = tool.analyse(str(source), settings.get('compounds', ''), settings.get('solvent', ''),
                           settings.get('min_prominence', 20.0), settings.get('window', 0.08),
                           settings.get('ymax'), settings.get('xmin'), settings.get('xmax'),
                           settings.get('baseline', 'auto'), tool.LANDSCAPE_PLOT_CM)
    except SystemExit as err:  # the tool's complaint about an unresolved requested peak
        raise ValueError(str(err.code)) from err
    if no_requests:  # all explicit requests were removed; do not switch to automatic picking
        res['peaks'] = []
        res['labels'] = []
        t, y = res['t'], res['y']
        visible = np.isfinite(y)
        if settings.get('xmin') is not None:
            visible &= t >= settings['xmin']
        if settings.get('xmax') is not None:
            visible &= t <= settings['xmax']
        y = y[visible]
        _, suggested = tool.assign_labels([], (0, 1), (float(y.min()), res['ydata_max']),
                                           settings.get('ymax'), tool.LANDSCAPE_PLOT_CM)
        res['ymax'] = tool.nice_ceil(suggested) if settings.get('ymax') is None else settings['ymax']
    return res


def process(folder, e, csv_dir, plain_dir):
    from .session import SessionError
    try:
        validate(e)
        source = os.path.join(folder, e['file'])
        stem = e.get('name') or spa_tool.clean_stem(e['file'])
        raw = tool.read_raw(source)
        archival = tool.write_xcalibur_csv(raw['time'], raw['signal'],
                                          os.path.join(csv_dir, stem + '.csv'), os.path.basename(source))
        plain = tool.write_plain_csv(raw['time'], raw['signal'],
                                    os.path.join(plain_dir, stem + '_plain.csv'))
        plots = []
        if e.get('full', True):
            plots.append((plain, False))
        if e.get('crop'):
            c = e['crop']
            cropped = tool.crop(source, os.path.join(plain_dir, stem + '_crop.csv'),
                                c.get('xmin'), c.get('xmax'), c.get('correct', False),
                                e.get('baseline', 'auto'), c.get('exclude', ''))
            plots.append((cropped, True))
        results = []
        for path, cropped in plots:
            settings = figure_settings(e, cropped)
            removed_all = bool(e.get('compounds') or e.get('solvent')) and not (
                settings.get('compounds') or settings.get('solvent'))
            res = analyse(path, settings, removed_all)
            table = write_tables(folder, path, stem, settings, res, cropped)
            res['meta']['detector'] = raw['meta'].get('detector')
            title = e.get('title') or stem
            if cropped:
                title = e['crop'].get('title') or title + ' (cropped)'
            corrected = bool(cropped and e['crop'].get('correct'))
            # macro_opts owns the detector's label, just as it does in batch.
            opts = tool.macro_opts(res, corrected=corrected)
            axis = e.get('axis') or (opts.split('ylabel={', 1)[1][:-1] if 'ylabel={' in opts
                                     else kinds.GC.y_label)
            results.append(dict(title=title, stem=stem, axis_label=axis, axis_md=axis,
                                peaks=[[p['tR'], ly] for p, ly, _ in res['labels']],
                                apex=[a for _, _, a in res['labels']],
                                names=[p['name'] for p, _, _ in res['labels']],
                                restrict_y=res['ydata_max'] > res['ymax'],
                                ymin=e.get('ymin'), ymax=res['ymax'], xmin=e.get('xmin'), xmax=e.get('xmax'),
                                n_peaks=len(res['labels']), archival_path=archival, plain_path=path,
                                integrate_path=table))
        return results
    except (ValueError, OSError, tool.RawFormatError) as err:
        raise SessionError(f"{e['file']}: {err}") from err


def write_tables(folder, plain, stem, settings, res, cropped):
    """Exactly the integrate command's text, with its source relative to the session folder.

    Use the figure's analysis before adding the RAW detector metadata: `gc integrate`
    reads the plain CSV, which carries no detector, so its options have no ylabel.
    """
    buf = io.StringIO()
    source = os.path.relpath(plain, folder)
    mode = 'manual' if (settings.get('compounds') or settings.get('solvent')) else 'auto'
    baseline = settings.get('baseline', 'auto')
    print(f"# {source}  mode={mode}  baseline={baseline}  "
          f"noise sigma={res['sigma']:.0f}  n_peaks={len(res['peaks'])}", file=buf)
    for line in tool.review_table(res['peaks']):
        print('  ', line, file=buf)
    tri, trap = tool.markdown_tables(res['peaks'], tool.parse_known(settings.get('known', '')))
    print('\ntriangulation table:\n', file=buf)
    print('\n'.join(tri), file=buf)
    print('\nintegration table:\n', file=buf)
    print('\n'.join(trap), file=buf)
    print('\n\\chromatogram options:', tool.macro_opts(res, settings.get('xmin'), settings.get('xmax')), file=buf)
    print('\\chromatogram peaks:  ', tool.format_peaklist(res['labels']), file=buf)
    directory = os.path.join(folder, 'integrate')
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, stem + ('_crop' if cropped else '') + '.txt')
    with open(path, 'w', encoding='utf-8') as out:
        out.write(buf.getvalue())
    return path


def peaklist(fig):
    return tool.format_peaklist([({'tR': x, 'name': name}, ly, apex)
                                 for (x, ly), apex, name in zip(fig.peaks, fig.apex, fig.names or [])])


def tex_block(fig):
    """Use batch's formatting and escaping, also after figures.json has been reloaded."""
    res = dict(ymax=fig.ymax, ydata_max=fig.ymax + 1 if fig.restrict_y else fig.ymax, meta={})
    opts = tool.macro_opts(res, fig.xmin, fig.xmax)
    if fig.ymin is not None:
        opts = f'ymin={fig.ymin:g},' + opts
    # The default kind label is implicit in the macro, as in batch without a detector.
    if fig.axis != kinds.GC.y_label:
        opts += ',ylabel={' + tool.latex_escape(fig.axis) + '}'
    block = tool.CHROMATOGRAM_TEMPLATE.format(opts=opts, csv_rel=fig.csv,
                                              peaklist=peaklist(fig), title=tool.latex_escape(fig.title))
    block = block.replace(r'width=\linewidth,height=6.8in', f'width={fig.width},height={fig.height}', 1)
    if '%' in fig.csv:
        block = '\\begingroup\\catcode`\\%=12\n' + block + '\\endgroup\n'
    return block


def load(path, entry):
    e = entry or {}
    validate(e)
    raw = tool.read_raw(path)
    axis = (entry or {}).get('axis') or (raw['meta']['detector'] + ' signal / counts'
                                       if raw['meta'].get('detector') else kinds.GC.y_label)
    x, y = raw['time'], raw['signal']
    if not e.get('full', True):
        c = e['crop']
        with tempfile.TemporaryDirectory() as tmp:
            cropped = tool.crop(str(path), os.path.join(tmp, 'crop.csv'), c.get('xmin'), c.get('xmax'),
                                c.get('correct', False), e.get('baseline', 'auto'), c.get('exclude', ''))
            x, y, _ = tool.read_any(cropped)
        if c.get('correct') and not e.get('axis') and raw['meta'].get('detector'):
            axis = 'Baseline-corrected ' + axis
    return x, y, axis, True, 'raw', None


def pick(entry, x, y, axis, absorbance, path=None):
    e = entry or {}
    validate(e)
    # Session analyses its six-decimal plain CSV. Use the same input without modifying the session.
    with tempfile.TemporaryDirectory() as tmp:
        plain = tool.write_plain_csv(x, y, os.path.join(tmp, 'preview.csv'))
        settings = figure_settings(e, not e.get('full', True))
        removed_all = bool(e.get('compounds') or e.get('solvent')) and not (
            settings.get('compounds') or settings.get('solvent'))
        res = analyse(plain, settings, removed_all)
    return dict(peaks=[[p['tR'], ly] for p, ly, _ in res['labels']],
                ymin=e.get('ymin'), ymax=res['ymax'])


def preview_plain(entry, stem):
    return stem + ('_plain.csv' if entry.get('full', True) else '_crop.csv')


def load_saved(folder, entry):
    from .edit import EditError
    stem = entry.get('name') or spa_tool.clean_stem(entry['file'])
    filename = preview_plain(entry, stem)
    plain = os.path.join(folder, 'plain', filename)
    if not os.path.exists(plain):
        raise EditError(f'no chromatogram at plain/{filename} (run `irspec session` first)')
    x, y, _ = tool.read_any(plain)
    return x, y, entry.get('axis') or kinds.GC.y_label, True
