"""The GC session kind, compared through the CLI with the unchanged GC tool."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from irspec import kinds, layout, session, texout
from irspec.figure import read_figures

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tests' / 'data'
RAW = 'gc_lab4.RAW'
COMPOUNDS = '2.84=Methanol,3.02=Ethanol,3.65=1-Propanol,5.31=1-Butanol,9.05=1-Pentanol'
LR4 = dict(title='Group 1', compounds=COMPOUNDS, solvent='3.30=Acetone',
           baseline='2.5,4.5,6.6,8.0,8.5,8.97,9.6',
           crop=dict(xmin=2.6, xmax=9.6, correct=True, exclude='3.24-3.46',
                     title='Group 1 (trimmed, baseline-corrected, acetone removed)'))


class GcCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'),
                    'PYTHONDONTWRITEBYTECODE': '1', 'MPLCONFIGDIR': str(self.folder / 'mpl'),
                    'XDG_CACHE_HOME': str(self.folder / 'cache')}
        shutil.copyfile(DATA / RAW, self.folder / RAW)

    def cli(self, *args, ok=True):
        r = subprocess.run([sys.executable, '-m', 'irspec', *map(str, args)],
                           cwd=self.folder, env=self.env, capture_output=True,
                           text=True, encoding='utf-8')
        if ok:
            self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def entry(self, **kw):
        (self.folder / 'gc').mkdir(exist_ok=True)
        if (self.folder / RAW).exists():
            (self.folder / RAW).rename(self.folder / 'gc' / RAW)
        e = dict(file='gc/' + RAW, **kw)
        (self.folder / 'manifest.json').write_text(json.dumps([e]), encoding='utf-8')
        return e

    def run_session(self):
        return json.loads(self.cli('session', '.', '--build', 'none', '--json').stdout)

    def figures(self):
        return read_figures(self.folder / 'figures.json')[0]

    def test_report_is_named_after_the_kind(self):
        # gc_<folder>, not ir_<folder> (a folder name without a date keeps the whole name)
        self.entry()
        self.assertEqual(self.run_session()['outputs']['markdown'], f'gc_{self.folder.name}.md')
        self.assertEqual(sorted(p.name for p in self.folder.glob('*.md')), [f'gc_{self.folder.name}.md'])

    def batch_block(self, e, crop=False):
        oracle = self.folder / 'oracle'
        oracle.mkdir(exist_ok=True)
        entry = {k: v for k, v in e.items() if k not in ('file', 'kind', 'compounds', 'full')}
        entry['raw'] = '../gc/' + RAW
        entry['peaks'] = e.get('compounds', '')
        if crop:
            entry['title'] = e['crop'].get('title') or e.get('title', 'gc_lab4') + ' (cropped)'
            entry.pop('solvent', None)  # LR4 removes acetone; batch_crop requests five alcohols
        else:
            entry.pop('crop', None)
        (oracle / 'batch.json').write_text(json.dumps([entry]), encoding='utf-8')
        r = subprocess.run([sys.executable, '-m', 'irspec', 'gc', 'batch', '--manifest', 'batch.json',
                            '--out-dir', '.', '--md', 'batch.md'], cwd=oracle, env=self.env,
                           capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        md = (oracle / 'batch.md').read_text(encoding='utf-8')
        return re.search(r'\\chromatogram\n.*?\\clearpage\n', md, re.S).group()

class Session(GcCase):
    def test_loose_raw_default_and_csv_oracle(self):
        obj = self.run_session()
        self.assertEqual(obj['kind'], 'gc')
        self.assertTrue((self.folder / 'gc' / RAW).exists())
        e = json.loads((self.folder / 'manifest.json').read_text(encoding='utf-8'))[0]
        self.assertEqual(set(e), {'file', 'title', 'kind'})
        fig = self.figures()[0]
        self.assertEqual(texout._block(fig), self.batch_block(e))
        for rel in ('csv/gc_lab4.csv', 'plain/gc_lab4_plain.csv'):
            self.assertEqual((self.folder / rel).read_bytes(), (self.folder / 'oracle' / rel).read_bytes())

    def test_lr4_two_blocks_and_rerun(self):
        self.entry(**LR4)
        obj = self.run_session()
        self.assertEqual(len(obj['spectra']), 2)
        figs = self.figures()
        e = dict(file='gc/' + RAW, **LR4)
        for fig, cropped in zip(figs, (False, True)):
            self.assertEqual(texout._block(fig), self.batch_block(e, cropped))
            a = np.genfromtxt(self.folder / fig.csv, delimiter=',', skip_header=1)
            frame = layout.frame(a[:, 0], a[:, 1], kinds.GC, fig.xmin, fig.xmax, fig.ymin, fig.ymax)
            self.assertTrue(np.isfinite(frame[1]).all())
            session.check_frame(fig, self.folder / fig.csv)
        self.assertEqual(len(figs[0].names), 6)
        self.assertEqual(len(figs[1].names), 5)
        self.assertNotIn('Acetone', figs[1].names)
        self.assertEqual((self.folder / figs[1].csv).read_bytes(),
                         (self.folder / 'oracle' / figs[1].csv).read_bytes())
        self.run_session()
        stored = json.loads((self.folder / 'manifest.json').read_text(encoding='utf-8'))[0]
        self.assertEqual(stored, dict(e, kind='gc'))

    def test_full_false_and_invalid_entries(self):
        self.entry(**dict(LR4, full=False))
        self.run_session()
        self.assertEqual([f.csv for f in self.figures()], ['plain/gc_lab4_crop.csv'])
        for kw, message in ((dict(full=False), 'crop'), (dict(peaks=[]), 'compounds')):
            self.entry(**kw)
            r = self.cli('session', '.', '--build', 'none', ok=False)
            self.assertEqual(r.returncode, 1)
            self.assertIn(message, r.stderr)

    def test_clamp_custom_labels_titles_and_sizes(self):
        for title in ('Group 1', 'Run_1 & 50%'):
            self.entry(title=title, compounds=COMPOUNDS, solvent='3.30=Acetone', ymax=900000,
                       xmin=2.6, xmax=9.6)
            self.run_session()
            fig = self.figures()[0]
            self.assertEqual(texout._block(fig), self.batch_block(dict(file='gc/' + RAW,
                             title=title, compounds=COMPOUNDS, solvent='3.30=Acetone',
                             ymax=900000, xmin=2.6, xmax=9.6)))
            self.assertTrue(fig.restrict_y)
            self.assertLessEqual(max(fig.apex), fig.ymax)
        self.entry(title='Run', compounds=COMPOUNDS, axis='Custom & counts', ymin=-100)
        self.run_session()
        fig = self.figures()[0]
        fig.width, fig.height = '20cm', '10cm'
        block = texout._block(fig)
        self.assertIn('width=20cm,height=10cm,ymin=-100,ymax=', block)
        self.assertIn(r'ylabel={Custom \& counts}', block)

    def test_crop_filters_outside_and_excluded_requests(self):
        e = self.entry(title='Run', compounds=COMPOUNDS + ',11=Outside', solvent='3.30=Acetone',
                       crop=dict(xmin=2.6, xmax=9.6, exclude='3.24-3.46'), full=False)
        self.run_session()
        fig = self.figures()[0]
        self.assertEqual(fig.title, 'Run (cropped)')
        self.assertEqual(set(fig.names), {'Methanol', 'Ethanol', '1-Propanol', '1-Butanol', '1-Pentanol'})
        # Correct=false retains the original detector label.
        self.assertEqual(fig.axis, 'FID signal / counts')
        self.assertEqual(e['compounds'].split(',')[-1], '11=Outside')

    def test_preview_edit_mixed_and_plot_refusals(self):
        obj = json.loads(self.cli('preview', RAW, '--json').stdout)
        self.assertEqual((obj['kind'], obj['format'], obj['points']), ('gc', 'raw', 7197))
        self.assertIn('against time (min)', self.cli('preview', RAW, '--ascii').stdout)
        plan = json.loads(self.cli('session', '.', '--preview', '--json').stdout)
        self.assertEqual(plan['spectra'][0]['plain'], 'plain/gc_lab4_plain.csv')
        self.assertEqual(plan['spectra'][0]['peaks'], obj['peaks'])
        self.run_session()
        self.assertEqual(self.figures()[0].peaks, [tuple(p) for p in obj['peaks']])
        self.cli('edit', '.', 'gc_lab4', 'set', 'ymax=900000')
        self.run_session()
        self.assertEqual(self.figures()[0].ymax, 900000)
        self.cli('edit', '.', 'gc_lab4', 'unset', 'ymax')
        r = self.cli('edit', '.', 'gc_lab4', 'peak', 'add', '3')
        self.assertIn('peak:', r.stdout)
        for backend in ('r',):  # matplotlib draws GC (0.3.10, test_plot_kinds)
            r = self.cli('plot', 'figures.json', '--backend', backend, ok=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('gc', r.stderr)
        shutil.copyfile(DATA / 'PHENACETIN_CRUDE_LR1-2.SPA', self.folder / 'sample.SPA')
        self.assertEqual(self.run_session()['kind'], 'mixed')

    def test_crop_preview_with_gaps_and_all_requests_removed(self):
        self.entry(**dict(LR4, full=False))
        self.run_session()
        fig = self.figures()[0]
        preview = json.loads(self.cli('preview', 'gc/' + RAW, '--json').stdout)
        self.assertEqual(preview['peaks'], [list(p) for p in fig.peaks])
        self.assertEqual(preview['axis'], fig.axis)
        plan = json.loads(self.cli('session', '.', '--preview', '--json').stdout)
        self.assertEqual(plan['spectra'][0]['plain'], fig.csv)
        self.cli('preview', 'gc/' + RAW, '--ascii')
        from irspec import gc
        x, y, _, _ = gc.load_saved(str(self.folder), dict(file='gc/' + RAW, full=False))
        self.assertTrue(np.isnan(y).any())
        layout.frame(x, y, kinds.GC)
        self.cli('edit', '.', 'gc_lab4', 'set', 'ymax=900000')
        self.run_session()
        self.entry(compounds='3.30=Acetone', crop=dict(xmin=2.6, xmax=9.6, exclude='3.24-3.46'),
                   full=False)
        self.run_session()
        self.assertEqual(self.figures()[0].peaks, [])

    def test_kind(self):
        k = kinds.GC
        self.assertEqual((k.x_column, k.y_column, k.x_label, k.x_unit, k.y_label),
                         ('time', 'signal', 'Retention time / min', 'min', 'Signal / counts'))
        self.assertEqual((k.xlim, k.x_descending, k.x_ticks, k.x_minor, k.pad, k.y_scope, k.labels, k.macro),
                         (None, False, None, None, (0.0985, 0.0017), 'frame', 'apex', 'chromatogram'))
        for path in ('gc/a.raw', 'gc/A.RAW'):
            self.assertIs(kinds.for_path(path), k)
        self.assertEqual(session.filing_folder('A.RAW'), 'gc')


@unittest.skipUnless(shutil.which('lualatex'), 'lualatex not installed')
class TexAgrees(GcCase):
    # Inherit the fixture helpers, without repeating Session's tests.
    def test_frames_full_package(self):
        self.measure(False)

    def test_frames_bundled_excerpt(self):
        self.measure(True)

    def measure(self, bundled):
        try:
            import pdfplumber
        except ImportError:
            self.skipTest('pdfplumber not installed')
        self.entry(**LR4)
        self.run_session()
        figs = self.figures()
        tex = texout.render_tex(figs)
        if bundled:
            tex = tex.replace(r'\IfFileExists{nulabreport.sty}', r'\IfFileExists{no-nulabreport.sty}')
        elif not session.nulabreport_installed():
            self.skipTest('nulabreport not installed')
        (self.folder / 't.tex').write_text(tex, encoding='utf-8')
        texout.write_excerpt(self.folder)
        r = subprocess.run(['lualatex', '-interaction=nonstopmode', '-halt-on-error', 't.tex'],
                           cwd=self.folder, env=self.env, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stdout[-1500:])
        with pdfplumber.open(self.folder / 't.pdf') as pdf:
            self.assertEqual(len(pdf.pages), len(figs))
            for pg, fig in zip(pdf.pages, figs):
                fr = max(pg.rects, key=lambda q: q['width'] * q['height'])
                def num(text):
                    text = text.replace('−', '-').replace(',', '')
                    return float(text) if re.fullmatch(r'-?\d+(\.\d+)?', text) else None
                # A thin thousands separator may split a GC tick into several PDF words.
                rows = {}
                for w in pg.extract_words():
                    center = (w['top'] + w['bottom']) / 2
                    if (num(w['text']) is not None and 0 < fr['x0'] - w['x1'] < 70
                            and fr['top'] - 2 <= center <= fr['bottom'] + 2):
                        rows.setdefault(round(center), []).append(w)
                yl = [(float(''.join(w['text'] for w in sorted(words, key=lambda w: w['x0']))
                             .replace('−', '-').replace(',', '')), float(center))
                      for center, words in rows.items()]
                a, b = np.polyfit([v for v, _ in yl], [c for _, c in yl], 1)
                got = ((fr['bottom'] - b) / a, (fr['top'] - b) / a)
                data = np.genfromtxt(self.folder / fig.csv, delimiter=',', skip_header=1)
                _, want, _, _ = layout.frame(data[:, 0], data[:, 1], kinds.GC,
                                             fig.xmin, fig.xmax, fig.ymin, fig.ymax)
                for actual, expected in zip(got, want):
                    self.assertAlmostEqual(actual, expected, delta=0.005 * (want[1] - want[0]))



class Tables(GcCase):
    def integration_oracle(self, plain, settings):
        argv = ['gc', 'integrate', plain, '--landscape',
                '--peaks', settings.get('compounds', ''), '--solvent', settings.get('solvent', ''),
                '--baseline', settings.get('baseline', 'auto'), '--known', settings.get('known', ''),
                '--min-prominence', str(settings.get('min_prominence', 20.0)),
                '--window', str(settings.get('window', 0.08))]
        for key in ('ymax', 'xmin', 'xmax'):
            if settings.get(key) is not None:
                argv.extend(['--' + key, str(settings[key])])
        r = subprocess.run([sys.executable, '-m', 'irspec', *argv], cwd=self.folder,
                           env=self.env, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr.decode('utf-8'))
        return r.stdout

    def test_full_and_crop_tables_known_and_rerun(self):
        known = 'Methanol=6.67,Ethanol=13.33,1-Propanol=20,1-Butanol=26.67,1-Pentanol=33.33'
        e = self.entry(**dict(LR4, known=known))
        obj = self.run_session()
        expected_paths = ['integrate/gc_lab4.txt', 'integrate/gc_lab4_crop.txt']
        self.assertEqual(obj['outputs']['integrate'], expected_paths)
        for record, fig, path, cropped in zip(obj['spectra'], self.figures(), expected_paths, (False, True)):
            settings = dict(e)
            if cropped:
                settings.update(baseline='none', solvent='')
            self.assertEqual(record['integrate'], path)
            self.assertEqual((self.folder / path).read_bytes(), self.integration_oracle(fig.csv, settings))
        self.assertIn('Known', (self.folder / expected_paths[1]).read_text(encoding='utf-8'))
        self.assertNotIn('Acetone', (self.folder / expected_paths[1]).read_text(encoding='utf-8'))
        before = {path: (self.folder / path).read_bytes() for path in expected_paths}
        self.run_session()
        self.assertEqual(before, {path: (self.folder / path).read_bytes() for path in expected_paths})
        other = self.folder / 'other'
        self.assertFalse(other.exists() and any(other.iterdir()))
        stored = json.loads((self.folder / 'manifest.json').read_text(encoding='utf-8'))[0]
        self.assertEqual(stored['known'], known)

    def test_auto_and_custom_settings_tables(self):
        for settings in ({}, dict(compounds=COMPOUNDS, solvent='3.30=Acetone', baseline='flat:0.5',
                                  min_prominence=12, window=0.12, ymax=900000, xmin=2.6, xmax=9.6,
                                  known='Methanol=6.67')):
            self.entry(**settings)
            obj = self.run_session()
            self.assertEqual(obj['outputs']['integrate'], ['integrate/gc_lab4.txt'])
            self.assertEqual((self.folder / 'integrate/gc_lab4.txt').read_bytes(),
                             self.integration_oracle('plain/gc_lab4_plain.csv', settings))

    def test_crop_only_writes_only_its_table(self):
        self.entry(**dict(LR4, full=False))
        obj = self.run_session()
        self.assertEqual(obj['outputs']['integrate'], ['integrate/gc_lab4_crop.txt'])
        self.assertFalse((self.folder / 'integrate/gc_lab4.txt').exists())
        self.assertEqual((self.folder / 'integrate/gc_lab4_crop.txt').read_bytes(),
                         self.integration_oracle('plain/gc_lab4_crop.csv',
                                                 dict(compounds=COMPOUNDS, baseline='none')))
