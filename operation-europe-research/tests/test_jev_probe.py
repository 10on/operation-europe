import datetime as dt
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('jev_probe', Path(__file__).resolve().parents[1] / 'scripts/jev_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class BudgetTest(unittest.TestCase):
    def test_last_allowed_reservation(self):
        probe.check_budget(probe.EXPIRES - dt.timedelta(seconds=1), 49)

    def test_exhausted_and_invalid_ledger(self):
        for count in [50, 51, -1, True, 1.5]:
            with self.assertRaises(ValueError):
                probe.check_budget(probe.EXPIRES - dt.timedelta(seconds=1), count)

    def test_expiration_is_inclusive(self):
        with self.assertRaises(ValueError):
            probe.check_budget(probe.EXPIRES, 0)


if __name__ == '__main__':
    unittest.main()
