from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ControlCenterLowRiskSchedulerContractTests(unittest.TestCase):
    def test_social_operator_helpers_imported_by_control_center_exist(self):
        control_tree = ast.parse((ROOT / "api/control_center.py").read_text(encoding="utf-8"))
        operator_tree = ast.parse((ROOT / "services/social_operator.py").read_text(encoding="utf-8"))

        operator_functions = {
            node.name
            for node in ast.walk(operator_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        imported_helpers = {
            alias.name
            for node in ast.walk(control_tree)
            if isinstance(node, ast.ImportFrom) and node.module == "services.social_operator"
            for alias in node.names
            if alias.name.startswith("_")
        }

        self.assertIn("_next_growth_slot", imported_helpers)
        self.assertNotIn("_schedule_time", imported_helpers)
        missing = sorted(imported_helpers - operator_functions)
        self.assertEqual([], missing, f"Control Center imports missing Social Operator helpers: {missing}")

        control_source = (ROOT / "api/control_center.py").read_text(encoding="utf-8")
        self.assertIn("_next_growth_slot(platform).isoformat()", control_source)


if __name__ == "__main__":
    unittest.main()
