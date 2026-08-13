import math
import unittest

import physics_reference as physics


class PhysicsReferenceTests(unittest.TestCase):
    def test_initial_chord_sets_sixty_degree_center_angle(self) -> None:
        state = physics.quasistatic_state(30.0)
        self.assertAlmostEqual(state["beta_deg"], 30.0, places=8)
        self.assertAlmostEqual(state["distance_over_r"], 1.0, places=8)

    def test_b_rebuilds_equilibrium_and_support_decreases(self) -> None:
        path = physics.quasistatic_path(1.0)
        support = [state["support_b_over_mg"] for state in path]
        self.assertTrue(all(a >= b for a, b in zip(support, support[1:])))
        self.assertAlmostEqual(path[-1]["beta_deg"], 49.207662344, places=7)
        self.assertAlmostEqual(path[-1]["support_b_over_mg"], 1.0, places=8)

    def test_quasistatic_energy_ledger(self) -> None:
        final = physics.quasistatic_path(1.0)[-1]
        self.assertAlmostEqual(final["delta_gravity_energy_over_mgr"], 0.0787314447, places=8)
        self.assertAlmostEqual(final["delta_electric_energy_over_mgr"], 0.1160110052, places=8)
        self.assertAlmostEqual(final["external_work_over_mgr"], 0.1947424499, places=8)
        self.assertAlmostEqual(
            final["external_work_over_mgr"],
            final["delta_gravity_energy_over_mgr"]
            + final["delta_electric_energy_over_mgr"],
            places=11,
        )

    def test_post_release_energy_is_conserved(self) -> None:
        motion = physics.simulate_release(0.0, 1.0)
        baseline = motion[0]["total_energy_over_mgr"]
        drift = max(abs(item["total_energy_over_mgr"] - baseline) for item in motion)
        self.assertLess(drift, 2e-5)
        self.assertGreater(motion[1]["alpha_deg"], motion[0]["alpha_deg"])

    def test_wrong_coulomb_direction_is_rejected(self) -> None:
        errors = physics.self_check(coulomb_sign=-1.0)
        self.assertIn("Coulomb direction is reversed after release", errors)
        self.assertEqual(physics.self_check(), [])


if __name__ == "__main__":
    unittest.main()
