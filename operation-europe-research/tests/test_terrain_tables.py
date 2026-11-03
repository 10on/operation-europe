import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import terrain_tables as tt  # noqa: E402

EXE = ROOT / "private/game-dos-working/main.exe"


@unittest.skipUnless(EXE.exists(), "working copy not present (private/, not in git)")
class TerrainTablesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = tt.tables(EXE.read_bytes())

    def test_names(self):
        self.assertEqual([x["name"] for x in self.t["terrain"]],
                         ["Can't enter", "City", "Road", "Plains", "Desert", "River", "Swamp", "Wasteland", "Forest",
                          "Hill", "Bridge"])

    def test_classes(self):
        self.assertEqual(list(self.t["class_of_category"].values()), [0, 1, 2, 3, 4, 3, 1, 1])

    def test_weather_tables(self):
        w = self.t["weather_tables"]
        self.assertEqual(len(w), 6)
        for table in w.values():
            self.assertEqual(table["rows"]["Can't enter"], [255] * 5)
            self.assertEqual(table["rows"]["River"][1:], [255] * 4)  # vehicles never enter a river
        # DIVXY/MOVE-226: after a weather change to Cloudy, DS:0x9D (Wasteland, class 4) was rewritten to 7
        self.assertEqual(w["Cloudy"]["rows"]["Wasteland"][4], 7)
        self.assertEqual(self.t["scale"], 2)


if __name__ == "__main__":
    unittest.main()
