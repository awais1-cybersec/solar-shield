import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"Ai-engine"))
from telemetry import extract_features,FEATURES
from demo_telemetry import records
from evaluate import metrics

class ContractTests(unittest.TestCase):
    def test_demo_repeatable(self):
        self.assertEqual(list(records()),list(records()))
        self.assertEqual(len(extract_features(next(records()))),8)
    def test_missing(self):
        with self.assertRaises(KeyError): extract_features({})
    def test_invalid(self):
        for invalid in (float("nan"),float("inf"),True):
            row=next(records());row[FEATURES[0]]=invalid
            with self.assertRaises(ValueError): extract_features(row)
    def test_metrics(self):
        result=metrics([1,1,0,0],[1,0,1,0])
        self.assertEqual(result["precision"],.5)
        self.assertEqual(result["recall"],.5)
        self.assertEqual(result["false_positive_rate"],.5)
    def test_undefined_metrics(self):
        self.assertIsNone(metrics([0],[0])["precision"])
    def test_empty_metrics(self):
        with self.assertRaises(ValueError): metrics([],[])

if __name__ == "__main__": unittest.main()
