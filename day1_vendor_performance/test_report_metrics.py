import sqlite3
import unittest

from build_case_study import calculate_metrics


class ReportMetricsTests(unittest.TestCase):
    def test_calculate_metrics_reconciles_vendor_summary(self):
        with sqlite3.connect("inventory.db") as connection:
            metrics = calculate_metrics(connection)

        self.assertEqual(metrics["record_count"], 10648)
        self.assertGreater(metrics["vendor_count"], 0)
        self.assertGreater(metrics["total_sales"], 0)
        self.assertGreater(metrics["total_purchase"], 0)
        self.assertEqual(metrics["total_sales"], metrics["vendor_sales_total"])
        self.assertGreaterEqual(metrics["pareto_top_10_share"], 0)
        self.assertLessEqual(metrics["pareto_top_10_share"], 1)
        self.assertGreaterEqual(metrics["margin_ttest_pvalue"], 0)
