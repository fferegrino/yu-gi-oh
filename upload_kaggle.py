import os
import sys
import time
from datetime import date


def main():
    if not os.environ.get("KAGGLE_KEY") or not os.environ.get("KAGGLE_USERNAME"):
        raise SystemExit("KAGGLE_KEY and KAGGLE_USERNAME must be set")

    from kaggle import api

    update_message = f"{date.today()} update"
    delays = (0, 15, 45)
    last_error = None
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            time.sleep(delay)
        try:
            api.dataset_create_version("data", update_message, dir_mode="zip", quiet=False)
            return
        except Exception as exc:
            last_error = exc
            print(f"Kaggle upload attempt {attempt} failed: {exc}", file=sys.stderr)

    raise SystemExit(f"Kaggle upload failed: {last_error}")


if __name__ == "__main__":
    main()
