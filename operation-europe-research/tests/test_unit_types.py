import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import unit_types as ut  # noqa: E402

EXE = ROOT / "private/game-dos-working/main.exe"

# Rows read from the Info > Intelligence > Armaments screen (France, 1940-05-10), UNITTYPES-64-20261103:
# type: (name, nation, AP, AT, Def, Spd, M.Rng, G.Rng)
SCREEN = {
    119: ("Infantry", "FRN", 10, 16, 10, 5, 0, 1),
    120: ("Mechanized", "FRN", 15, 16, 15, 80, 400, 1),
    121: ("APC HalfTrack", "FRN", 15, 16, 30, 60, 300, 1),
    123: ("H35", "FRN", 21, 12, 23, 28, 40, 1),
    124: ("Somua S35", "FRN", 27, 39, 23, 40, 232, 1),
    125: ("Char B", "FRN", 43, 33, 20, 28, 130, 1),
    126: ("75mm Guns", "FRN", 43, 34, 15, 35, 200, 1),
    127: ("155mm Guns", "FRN", 90, 49, 0, 30, 200, 7),
    2: ("Infantry I", "GER", 10, 16, 10, 5, 0, None),
    5: ("Combat Enginr", "GER", 25, 30, 20, 5, 0, None),
    6: ("Paratroop", "GER", 20, 24, 20, 5, 0, None),
    7: ("Mechanized", "GER", 15, 16, 15, 80, 400, None),
    8: ("APC HalfTrack", "GER", 15, 16, 25, 50, 300, None),
}


@unittest.skipUnless(EXE.exists(), "working copy not present (private/, not in git)")
class UnitTypesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {r["type"]: r for r in ut.records(EXE.read_bytes())}

    def test_count_and_names(self):
        self.assertEqual(len(self.rows), 158)
        self.assertTrue(all(r["name"] for r in self.rows.values()))

    def test_matches_armaments_screen(self):
        for t, (name, nat, ap, at, df, spd, mrng, grng) in SCREEN.items():
            r = self.rows[t]
            got = (r["name"], r["nations"][0], r["ap"], r["at"], r["defense"], r["speed"], r["m_rng"])
            self.assertEqual(got, (name, nat, ap, at, df, spd, mrng), t)
            if grng is not None:
                self.assertEqual(r["g_rng"], grng, t)

    def test_category_of_types_used_in_save_edits(self):
        self.assertEqual(self.rows[119]["category"], "Infnty")
        self.assertEqual(self.rows[99]["category"], "Tanks")  # 119 -> 99 moved strength Infntry -> Tanks (SCEARR-221)


if __name__ == "__main__":
    unittest.main()
