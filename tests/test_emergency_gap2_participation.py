import unittest

import ai_decision_engine_xauusd_v26_execution_confidence_engine as engine


class EmergencyGap2ParticipationTests(unittest.TestCase):
    def base_trade(self):
        return {
            "symbol": "XAUUSD",
            "decision": "TRADE",
            "action": "SELL",
            "bias": "SELL",
            "buy_score": 1,
            "sell_score": 3,
            "score_gap": 2,
            "market_mode": "TREND",
            "bb_state": "WALK_DOWN",
            "execution_state": "EXECUTE_NORMAL",
            "management": "SCALP_TP",
            "allowed": True,
            "entry_allowed": True,
            "payload_valid": True,
            "market_state_fresh": True,
            "market_state_age_sec": 0,
            "decision_age_sec": 0,
            "entry_price": 2300.0,
            "price": 2300.0,
            "bid": 2300.0,
            "bb_upper": 2310.0,
            "bb_middle": 2305.0,
            "bb_lower": 2290.0,
            "rsi": 40.0,
            "macd_hist": -0.4,
            "trend_exhaustion_score": 0,
            "exhaustion_score": 0,
            "late_entry_score": 0,
        }

    def test_gap2_aligned_trade_becomes_cautious(self):
        result = engine.apply_expectancy_entry_filters_v26_6_2(self.base_trade())

        self.assertEqual(result["decision"], "TRADE")
        self.assertEqual(result["execution_state"], "EXECUTE_CAUTIOUS")
        self.assertEqual(result["decision_output_state"], "TRADE")
        self.assertEqual(result["execution_mode"], "CAUTIOUS")
        self.assertEqual(result["participation_type"], "CAUTIOUS")
        self.assertTrue(result["EMERGENCY_GAP2_APPROVED"])
        self.assertEqual(result["participation_size_factor"], 0.25)
        self.assertFalse(result["runner_enabled"])
        self.assertFalse(result["pyramid_enabled"])
        self.assertFalse(result["continuation_add_enabled"])
        self.assertEqual(result["original_veto"], "V26_6_2_WEAK_GAP_NO_TRADE")
        self.assertEqual(result["final_veto_owner"], "NONE")

    def test_gap1_remains_no_trade(self):
        payload = self.base_trade()
        payload.update({"buy_score": 2, "sell_score": 3, "score_gap": 1})

        result = engine.apply_expectancy_entry_filters_v26_6_2(payload)

        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertEqual(result["effective_veto_code"], "V26_6_2_WEAK_GAP_NO_TRADE")
        self.assertTrue(result["EMERGENCY_GAP2_REJECTED"])

    def test_bias_action_conflict_remains_no_trade(self):
        payload = self.base_trade()
        payload["bias"] = "BUY"

        result = engine.apply_expectancy_entry_filters_v26_6_2(payload)

        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertEqual(result["effective_veto_code"], "V26_6_2_WEAK_GAP_NO_TRADE")
        self.assertTrue(result["EMERGENCY_GAP2_REJECTED"])

    def test_hard_safety_block_remains_no_trade(self):
        payload = self.base_trade()
        payload["reason"] = "ABNORMAL_SPREAD"

        result = engine.apply_expectancy_entry_filters_v26_6_2(payload)

        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertEqual(result["effective_veto_code"], "V26_6_2_WEAK_GAP_NO_TRADE")
        self.assertIn("ABNORMAL_SPREAD", result["supporting_vetoes"])

    def test_severe_exhaustion_remains_no_trade(self):
        payload = self.base_trade()
        payload["trend_exhaustion_score"] = engine.TREND_EXHAUSTION_BLOCK_LEVEL

        result = engine.apply_expectancy_entry_filters_v26_6_2(payload)

        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertEqual(result["effective_veto_code"], "V26_6_2_WEAK_GAP_NO_TRADE")
        self.assertIn("SEVERE_EXHAUSTION", result["supporting_vetoes"])

    def test_transition_normal_middle_chop_remains_no_trade(self):
        payload = self.base_trade()
        payload.update({
            "market_mode": "TRANSITION",
            "bb_state": "NORMAL",
            "bb_upper": 2310.0,
            "bb_middle": 2300.0,
            "bb_lower": 2290.0,
            "rsi": 50.0,
            "macd_hist": 0.0,
        })

        result = engine.apply_expectancy_entry_filters_v26_6_2(payload)

        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertIn("BB_MIDDLE_CHOP", result["supporting_vetoes"])

    def test_approved_gap2_is_not_rekilled_by_duplicate_weak_gap_filter(self):
        payload = engine.apply_expectancy_entry_filters_v26_6_2(self.base_trade())

        result = engine.apply_expectancy_entry_filters_v26_6_2(payload)

        self.assertEqual(result["decision"], "TRADE")
        self.assertEqual(result["execution_state"], "EXECUTE_CAUTIOUS")
        self.assertEqual(result["effective_veto_code"], "NONE")
        self.assertEqual(result["final_veto_owner"], "NONE")
        self.assertTrue(result["recovery_applied"])

    def test_final_trace_reports_trade_schema_compatibility_not_needed(self):
        payload = engine.apply_expectancy_entry_filters_v26_6_2(self.base_trade())
        payload = engine.initialize_final_decision_trace(payload)

        trace = payload["FINAL_DECISION_TRACE"]
        self.assertEqual(trace["initial_decision"], "TRADE")
        self.assertEqual(trace["last_executable_candidate"], "TRADE")
        self.assertEqual(trace["final_published_decision"], "TRADE")
        self.assertEqual(trace["schema_trade_cautious_compatible"], "NOT_NEEDED")
        self.assertEqual(trace["downstream_trade_cautious_recognized"], "NOT_NEEDED")

    def test_cooldown_wait_entry_window_gap2_trend_bypass_creates_cautious_trade(self):
        payload = self.base_trade()
        payload.update({
            "candle_trend": "UP",
            "structure_trend": "HH_HL",
            "bb_state": "WALK_UP",
            "rsi": 65.0,
            "macd_hist": 0.4,
            "open_positions": 0,
            "max_open_positions": 1,
        })

        result = engine.apply_execution_timing_layer_v26_6_5(payload)

        self.assertEqual(result["decision"], "TRADE")
        self.assertEqual(result["execution_state"], "EXECUTE_CAUTIOUS")
        self.assertEqual(result["execution_mode"], "CAUTIOUS")
        self.assertEqual(result["participation_size_factor"], 0.25)
        self.assertFalse(result["runner_enabled"])
        self.assertFalse(result["pyramid_enabled"])
        self.assertFalse(result["continuation_add_enabled"])
        self.assertTrue(result["COOLDOWN_GATE_BYPASS_APPROVED"])
        self.assertFalse(result["COOLDOWN_GATE_BYPASS_REJECTED"])
        self.assertTrue(result["WAIT_ENTRY_WINDOW_CONVERTED_TO_EXECUTE_CAUTIOUS"])
        self.assertEqual(result["entry_window_validation"], "WAIT_ENTRY_WINDOW_CONVERTED_TO_EXECUTE_CAUTIOUS")
        self.assertEqual(result["final_veto_owner"], "NONE")
        self.assertEqual(result["effective_veto_code"], "NONE")

    def test_cooldown_wait_entry_window_bypass_rejects_strong_opposite_macd(self):
        payload = self.base_trade()
        payload.update({
            "candle_trend": "UP",
            "structure_trend": "HH_HL",
            "bb_state": "WALK_UP",
            "rsi": 65.0,
            "macd_hist": 1.3,
            "open_positions": 0,
            "max_open_positions": 1,
        })

        result = engine.apply_execution_timing_layer_v26_6_5(payload)

        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertEqual(result["wait_state"], "WAIT_ENTRY_WINDOW")
        self.assertTrue(result["COOLDOWN_GATE_BYPASS_REJECTED"])
        self.assertEqual(result["COOLDOWN_GATE_BYPASS_CHECK"], "REJECTED")
        self.assertIn("STRONG_OPPOSITE_MACD", result["cooldown_gate_bypass_supporting_vetoes"])


if __name__ == "__main__":
    unittest.main()
