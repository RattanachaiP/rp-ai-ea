"""Build the mandatory human-readable decision explanation."""


def explain_decision(decision, expectancy, risk, confidence, executable):
    gates = (f"expectancy={expectancy.status}", f"risk={risk.status}",
             f"confidence={confidence.band}({confidence.value:.6f})", f"executable={executable}")
    return f"{decision}: " + "; ".join(gates)
