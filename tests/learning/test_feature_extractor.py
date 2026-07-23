from learning.extractor import FeatureExtractor, FeatureRegistry, FeatureVectorValidator

def test_evidence_becomes_immutable_valid_vector():
 vector=FeatureExtractor(clock=lambda:"2026-01-01T00:00:00.000Z").extract({"trade_id":"trade-1","rsi":72,"adx":40,"session":"LONDON","net_profit":12,"result":"WIN","rr":2.5})
 assert vector.features["rsi_zone"] == "OVERBOUGHT"
 assert vector.features["london"] is True
 assert vector.features["rr_bucket"] == "HIGH"
 FeatureVectorValidator().validate(vector)
 try: vector.features["rsi_zone"]="LOW"
 except TypeError: pass
 else: raise AssertionError("vector features must be immutable")
def test_registry_contains_dictionary_features():
 assert FeatureRegistry.get("rsi_zone").source == "RSI14"
