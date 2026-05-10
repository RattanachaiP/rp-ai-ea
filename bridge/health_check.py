import os
import json
import time

SHARED_PATH = "D:/RP_AI_EA/shared/"

def file_ok(path):
    return os.path.exists(path)

def health_check():
    status = {
        "market_state": file_ok(SHARED_PATH + "market_state.json"),
        "decision": file_ok(SHARED_PATH + "decision.json"),
        "timestamp": time.time()
    }

    try:
        with open(SHARED_PATH + "health_status.json", "w") as f:
            json.dump(status, f)
    except Exception as e:
        print("WRITE ERROR:", e)

    print("HEALTH:", status)

while True:
    health_check()
    time.sleep(5)