import unittest

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


if __name__ == "__main__":
    unittest.main()
