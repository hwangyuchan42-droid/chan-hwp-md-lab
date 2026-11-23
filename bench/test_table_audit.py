import unittest
from xml.etree.ElementTree import fromstring

from table_audit import grade, source_table


class TableAuditTest(unittest.TestCase):
    def test_empty_cell_rowspan_values_and_order(self):
        def cell(col, row, span, value):
            return (f'<tc><cellAddr rowAddr="{row}" colAddr="{col}"/>'
                    f'<cellSpan rowSpan="{span}" colSpan="1"/><subList><p><run>'
                    f'<t>{value}</t></run></p></subList></tc>')

        xml = (f'<tbl rowCnt="2" colCnt="2"><tr>{cell(0, 0, 2, "품목")}{cell(1, 0, 1, "")}'
               f'</tr><tr>{cell(1, 1, 1, "42")}</tr></tbl>')
        ref = [source_table(fromstring(xml))], ["시작", "끝"], {}
        md = '시작\n\n<table><tr><td rowspan="2"><b>품목</b></td><td></td></tr><tr><td>42</td></tr></table>\n\n끝'
        result = grade(ref, md.encode())
        self.assertTrue(result["all_tables_in_order"])
        self.assertEqual(result["ordered_body_texts"], 2)
        self.assertEqual(result["merged_values_and_geometry"], 1)
        self.assertEqual(grade(ref, md.replace('rowspan="2"', '').encode())["table_geometry"], 0)
        changed = grade(ref, md.replace("42", "24").encode())
        self.assertEqual(changed["table_geometry"], 1)
        self.assertEqual(changed["table_values_and_geometry"], 0)
        self.assertEqual(grade(ref, md.replace("시작", "끝", 1).encode())["ordered_body_texts"], 1)

    def test_equivalent_gfm_and_html_in_mixed_markdown(self):
        from table_audit import Table

        ref = [Table(2, 2, ((0, 0, 1, 1, "열"), (0, 1, 1, 1, "값"),
                            (1, 0, 1, 1, "a|b"), (1, 1, 1, 1, "")))], [], {}
        gfm = "| 열 | 값 |\n|---|---|\n| **a\\|b** | |"
        self.assertTrue(grade(ref, gfm.encode())["all_tables_in_order"])
        self.assertFalse(grade(ref, (gfm + "\n\n" + gfm).encode())["all_tables_in_order"])


if __name__ == "__main__":
    unittest.main()
