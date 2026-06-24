import json
import tempfile
import unittest
from pathlib import Path

import ai_decision_engine_xauusd_v26_execution_confidence_engine as engine


class ExecutorSlContractTests(unittest.TestCase):
    def base_trade(self):
        return {
            "symbol": "XAUUSD",
            "decision": "TRADE",
            "action": "SELL",
            "bias": "SELL",
            "execution_state": "EXECUTE_NORMAL",
            "management": "SCALP_TP",
            "allowed": True,
            "entry_allowed": True,
            "payload_valid": True,
            "sl": 0,
            "stop_loss": 0,
            "tp": 0,
            "tp1": 0,
            "entry_price": 2300.0,
            "price": 2300.0,
        }

    def test_tp_only_profile_accepts_zero_sl_when_contract_approved(self):
        payload = self.base_trade()
        payload.update({
            "active_profile": "TP_ONLY_1USD_TEST",
            "dashboard_active_profile": "TP_ONLY_1USD_TEST",
            "broker_sl_required": False,
            "broker_tp_required": False,
            "dashboard_tp_required": False,
            "initial_sl_usd_001_lot": 0.0,
            "fixed_take_profit_enabled_by_dashboard": True,
            "dashboard_exit_mode": "MARKET_CLOSE",
            "dashboard_fixed_take_profit": {"enable": True, "close_mode": "MARKET_CLOSE"},
        })

        validated = engine.validate_final_decision_payload(payload)

        self.assertEqual(validated["decision"], "TRADE")
        self.assertTrue(validated["payload_valid"])
        self.assertEqual(validated["stop_loss"], 0)
        self.assertTrue(validated["tp_only_validation_exception_applied"])
        self.assertEqual(validated["profile_sl_suppression_check"], "PROFILE_SL_SUPPRESSION_APPROVED")

    def test_production_profile_rejects_zero_sl_when_broker_sl_required(self):
        payload = self.base_trade()
        payload.update({
            "active_profile": "Balanced",
            "dashboard_active_profile": "Balanced",
            "broker_sl_required": True,
            "broker_tp_required": True,
            "tp": 2310.0,
            "tp1": 2310.0,
        })

        validated = engine.validate_final_decision_payload(payload)

        self.assertEqual(validated["decision"], "NO_TRADE")
        self.assertFalse(validated.get("payload_valid", False))
        self.assertIn("sl_invalid=0.0", validated["payload_validation_reason"])

    def test_dashboard_loader_falls_back_from_tp_only_to_balanced(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "dashboard_profiles").mkdir()
            (root / "trade_management_dashboard.json").write_text(
                json.dumps({"active_profile": "TP_ONLY_1USD_TEST", "enabled": True}),
                encoding="utf-8",
            )
            (root / "dashboard_profiles" / "Balanced.json").write_text(
                json.dumps({
                    "active_profile": "Balanced",
                    "risk": {"initial_sl_usd_001_lot": 1.0},
                    "fixed_take_profit": {"enable": False},
                }),
                encoding="utf-8",
            )

            dashboard = engine.load_trade_management_dashboard(root)

        self.assertEqual(dashboard["active_profile"], "Balanced")
        self.assertIn("TP_ONLY_PRODUCTION_BLOCK", dashboard.get("load_warnings", []))
        self.assertGreater(dashboard["risk"].get("initial_sl_usd_001_lot", 0), 0)
        self.assertFalse(dashboard["fixed_take_profit"].get("enable", False))

    def test_balanced_trade_constructs_required_broker_sl_tp(self):
        payload = self.base_trade()
        payload.update({
            "action": "BUY",
            "bias": "BUY",
            "entry_price": 2300.0,
            "price": 2300.0,
            "market_mode": "TRANSITION",
            "management": "SCALP_TP",
            "mgmt": "SCALP_TP",
        })

        constructed = engine.apply_trade_management_dashboard_v27(payload)
        constructed = engine.enforce_risk_payload_invariant_before_publication(constructed)

        self.assertEqual(constructed["dashboard_active_profile"], "Balanced")
        self.assertTrue(constructed["broker_sl_required"])
        self.assertTrue(constructed["broker_tp_required"])
        self.assertGreater(constructed["stop_loss"], 0)
        self.assertGreater(constructed["take_profit"], 0)
        self.assertGreater(constructed["risk_distance"], 0)
        self.assertTrue(constructed["payload_valid"])


if __name__ == "__main__":
    unittest.main()
