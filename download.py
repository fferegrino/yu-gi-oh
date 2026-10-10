import hashlib
import io
import os
import sys
import time
from datetime import datetime

import pandas as pd
import requests

API_ROOT = "https://db.ygoprodeck.com/api/v7"
MIN_SETS = 100
MIN_CARDS = 1000
RETRY_DELAYS_SECONDS = (1, 2, 4, 8, 16)

MAIN_ATTRIBUTES = [
    "id",
    "name",
    "type",
    "desc",
    "atk",
    "def",
    "level",
    "race",
    "attribute",
    "scale",
    "archetype",
    "linkval",
    "linkmarkers",
]
BAN_ATTRIBUTES = [
    "ban_tcg",
    "ban_ocg",
    "ban_goat",
]
MISC_ATTRIBUTES = [
    "staple",
    "views",
    "viewsweek",
    "upvotes",
    "downvotes",
    "formats",
    "treated_as",
    "tcg_date",
    "ocg_date",
    "konami_id",
    "has_effect",
]
CARD_COLUMNS = (
    MAIN_ATTRIBUTES
    + ["image_url", "image_url_small"]
    + BAN_ATTRIBUTES
    + MISC_ATTRIBUTES
)
SET_COLUMNS = ["id", "set_name", "set_code", "num_of_cards", "tcg_date"]
PRINTING_COLUMNS = ["card_id", "set_id", "set_code", "set_rarity", "set_rarity_code"]
# Page counters move between downloads even when no card, printing, or set changed.
VOLATILE_CARD_COLUMNS = ("views", "viewsweek", "upvotes", "downvotes")


def digest(text):
    return hashlib.md5(text.encode()).hexdigest()


def fetch_json(session, url):
    """GET JSON, retrying network blips and transient HTTP statuses."""
    last_error = None
    for attempt, delay in enumerate(RETRY_DELAYS_SECONDS, start=1):
        try:
            response = session.get(url, timeout=(10, 180))
        except requests.RequestException as exc:
            last_error = str(exc)
        else:
            if response.status_code not in (403, 408, 429, 500, 502, 503, 504):
                return decode_json(response, url)
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"

        print(
            f"Attempt {attempt} failed for {url}: {last_error}",
            file=sys.stderr,
        )
        if attempt < len(RETRY_DELAYS_SECONDS):
            time.sleep(delay)

    raise SystemExit(f"Giving up on {url}: {last_error}")


def decode_json(response, url):
    try:
        payload = response.json()
    except ValueError:
        body = response.text[:300].replace("\n", " ")
        raise SystemExit(
            f"Non-JSON response from {url} (HTTP {response.status_code}): {body}"
        )

    if response.status_code >= 400 or is_error_payload(payload):
        message = payload.get("error") if isinstance(payload, dict) else payload
        raise SystemExit(
            f"API error from {url} (HTTP {response.status_code}): {message}"
        )
    return payload


def is_error_payload(payload):
    return isinstance(payload, dict) and "error" in payload and "data" not in payload


def build_cardsets(payload):
    if not isinstance(payload, list):
        raise SystemExit(
            f"Card sets response was {type(payload).__name__}, expected a list"
        )

    frame = pd.DataFrame(payload)
    for column in ("set_name", "set_code", "num_of_cards", "tcg_date"):
        if column not in frame.columns:
            frame[column] = pd.NA

    usable = frame["set_name"].notna() & frame["set_code"].notna()
    skipped = int((~usable).sum())
    if skipped:
        print(f"Skipping {skipped} card sets with no name or code", file=sys.stderr)
    frame = frame.loc[usable].copy()
    if len(frame) < MIN_SETS:
        raise SystemExit(f"Only {len(frame)} usable card sets; refusing to replace the dataset")

    frame["set_name"] = frame["set_name"].astype(str)
    frame["set_code"] = frame["set_code"].astype(str)
    frame["id"] = (frame["set_name"] + " " + frame["set_code"]).map(digest)
    frame["tcg_date"] = pd.to_datetime(frame["tcg_date"], errors="coerce")
    return frame[SET_COLUMNS].sort_values(by=["tcg_date", "set_name"])


def primary_image(images, card_id):
    if not isinstance(images, list):
        return None, []

    pictures = [image for image in images if isinstance(image, dict)]
    matches = [image for image in pictures if image.get("id") == card_id]
    primary = matches[0] if matches else (pictures[0] if pictures else None)
    alternates = [
        image.get("id")
        for image in pictures
        if image.get("id") not in (None, card_id)
    ]
    return primary, alternates


def process_card(card):
    card_info = {attribute: card.get(attribute) for attribute in MAIN_ATTRIBUTES}

    banlist_info = card.get("banlist_info") or {}
    if not isinstance(banlist_info, dict):
        banlist_info = {}
    card_info.update(
        {attribute: banlist_info.get(attribute) for attribute in BAN_ATTRIBUTES}
    )

    primary, alternate_images = primary_image(card.get("card_images"), card_info["id"])
    card_info["image_url"] = primary.get("image_url") if primary else None
    card_info["image_url_small"] = primary.get("image_url_small") if primary else None
    used_fallback = primary is not None and primary.get("id") != card_info["id"]

    misc_values = card.get("misc_info") or []
    misc_info = {}
    if isinstance(misc_values, list) and misc_values and isinstance(misc_values[0], dict):
        misc_info = misc_values[0]
    card_info.update(
        {attribute: misc_info.get(attribute) for attribute in MISC_ATTRIBUTES}
    )
    formats = card_info["formats"]
    card_info["formats"] = (
        "|".join(str(item) for item in formats) if isinstance(formats, list) and formats else None
    )

    sets = []
    for card_set in card.get("card_sets") or []:
        if not isinstance(card_set, dict):
            continue
        if not all(f"set_{attr}" in card_set for attr in ("name", "code", "rarity", "rarity_code")):
            continue
        sets.append(
            {
                f"set_{attr}": card_set[f"set_{attr}"]
                for attr in ("name", "code", "rarity", "rarity_code")
            }
        )

    return card_info, alternate_images, sets, used_fallback


def printing_rows(set_info, card_id, cardset_to_id):
    rows = []
    for info in set_info:
        name = info.get("set_name")
        raw_code = info.get("set_code")
        if not isinstance(name, str) or not isinstance(raw_code, str):
            continue
        set_id, _, set_code = raw_code.partition("-")
        set_hash_id = cardset_to_id.get((name, set_id))
        if not set_hash_id:
            continue
        rows.append(
            {
                "set_id": set_hash_id,
                "set_code": set_code,
                "set_rarity": info.get("set_rarity"),
                "set_rarity_code": info.get("set_rarity_code"),
                "card_id": card_id,
            }
        )
    return rows


def write_csv(frame, path):
    temporary = f"{path}.tmp"
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def same_table(path, frame, ignore=()):
    """True when the saved CSV matches this frame, ignoring volatile columns."""
    if not os.path.exists(path):
        return False
    try:
        current = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError):
        return False

    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    buffer.seek(0)
    fresh = pd.read_csv(buffer)
    for column in ignore:
        current = current.drop(columns=[column], errors="ignore")
        fresh = fresh.drop(columns=[column], errors="ignore")
    return fresh.equals(current)


def main():
    session = requests.Session()
    session.headers["User-Agent"] = "fferegrino-yu-gi-oh-dataset"

    card_sets = build_cardsets(fetch_json(session, f"{API_ROOT}/cardsets.php"))
    cardset_to_id = {
        (row["set_name"], row["set_code"]): row["id"] for _, row in card_sets.iterrows()
    }

    cardinfo = fetch_json(session, f"{API_ROOT}/cardinfo.php?misc=yes")
    if not isinstance(cardinfo, dict) or not isinstance(cardinfo.get("data"), list):
        raise SystemExit("Card info response did not include a data list")

    cards = []
    alternates = []
    set_information = []
    fallback_images = 0
    skipped_cards = 0
    for raw_card in cardinfo["data"]:
        if not isinstance(raw_card, dict):
            skipped_cards += 1
            continue
        card_info, alternate, set_info, used_fallback = process_card(raw_card)
        if card_info.get("id") is None:
            skipped_cards += 1
            continue
        cards.append(card_info)
        if used_fallback:
            fallback_images += 1
        alternates.extend((card_info["id"], alter) for alter in alternate)
        set_information.extend(printing_rows(set_info, card_info["id"], cardset_to_id))

    if len(cards) < MIN_CARDS:
        raise SystemExit(f"Only {len(cards)} usable cards; refusing to replace the dataset")
    if skipped_cards:
        print(f"Skipping {skipped_cards} cards with no id", file=sys.stderr)
    if fallback_images:
        print(f"Used a fallback image for {fallback_images} cards", file=sys.stderr)

    all_cards = pd.DataFrame(cards)[CARD_COLUMNS].sort_values(by="name")
    card_set_relation = pd.DataFrame(set_information, columns=PRINTING_COLUMNS).sort_values(
        by=["card_id", "set_id"]
    )
    variants = pd.DataFrame(alternates, columns=["original", "variant"]).sort_values(
        by=["original", "variant"]
    )

    outputs = [
        ("cardsets.csv", card_sets, ()),
        ("cards.csv", all_cards, VOLATILE_CARD_COLUMNS),
        ("cards_cardsets.csv", card_set_relation, ()),
        ("cards_variants.csv", variants, ()),
    ]
    if all(same_table(path, frame, ignore) for path, frame, ignore in outputs):
        print("No card updates; leaving the dataset unchanged")
        return

    for path, frame, _ignore in outputs:
        write_csv(frame, path)
    temporary_info = "info.txt.tmp"
    with open(temporary_info, "w") as handle:
        handle.write(datetime.now().isoformat())
        handle.write("\n")
    os.replace(temporary_info, "info.txt")
    print(
        f"Wrote {len(card_sets)} sets, {len(all_cards)} cards, "
        f"{len(card_set_relation)} printings, {len(variants)} variants"
    )


if __name__ == "__main__":
    main()
