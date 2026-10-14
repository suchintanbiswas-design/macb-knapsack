"""Quick correctness tests:  python -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from macb import CLASSES, exhaustive, generate_instance, run_method, sort_items  # noqa: E402


class TestSolvers(unittest.TestCase):
    def test_worked_example_from_paper(self):
        # four items (2,3) (3,4) (4,5) (5,8), C = 8  ->  z* = 12 with items {4, 2}
        w, v, cap = [2, 3, 4, 5], [3, 4, 5, 8], 8
        order, ws, vs = sort_items(w, v)
        self.assertEqual(order, [3, 0, 1, 2])           # ratio order: item4, item1, item2, item3
        r = run_method("macb", w, v, cap, order, ws, vs, budget=1)
        self.assertEqual(r["value"], 12)
        self.assertEqual(r["items"], "1 3")             # zero-based indices of items 2 and 4
        self.assertEqual(r["deferrals"], 0)             # nothing is deferred with B = 1 (Section II-C.3)

    def test_all_methods_match_exhaustive(self):
        for cls in CLASSES:
            for seed in range(6):
                w, v, cap = generate_instance(10, cls, 500 + seed)
                ref, _ = exhaustive(w, v, cap)
                order, ws, vs = sort_items(w, v)
                for m, b in [("dp", None), ("std_bnb", None), ("cta", None)] + [("macb", x) for x in (1, 4, 16, 64)]:
                    r = run_method(m, w, v, cap, order, ws, vs, budget=b, time_limit=None)
                    self.assertEqual(r["value"], ref, (cls, seed, m, b))
                    self.assertTrue(r["feasible"])
                    if m == "macb":
                        self.assertLessEqual(r["peak_active"], b)               # Eq. (2)
                        self.assertLessEqual(r["activations"], r["deferrals"])

    def test_generator_is_deterministic(self):
        self.assertEqual(generate_instance(20, "weak", 7), generate_instance(20, "weak", 7))


if __name__ == "__main__":
    unittest.main()
