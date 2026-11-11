import unittest
from irspec import spa_tool, texout
from irspec.figure import Figure


class LatexEscape(unittest.TestCase):
    def test_free_text_is_escaped_once(self):
        title = r"Run ^2 ~ C:\data {x} & 50%_#$"
        expected = r"Run \textasciicircum{}2 \textasciitilde{} C:\textbackslash{}data \{x\} \& 50\%\_\#\$"
        self.assertEqual(spa_tool.latex_escape(title), expected)
        fig = Figure(csv="plain/x.csv", title=title, peaks=[])
        self.assertIn(expected, texout.render_md([fig]))
        self.assertIn(expected, texout.render_tex([fig]))
