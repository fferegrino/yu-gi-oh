import hashlib
from datetime import datetime

import pandas as pd
import requests


def hash(text):
    hash_object = hashlib.md5(text.encode())
    md5_hash = hash_object.hexdigest()
    return md5_hash


with open("info.txt", "w") as w:
    w.write(datetime.now().isoformat())
    w.write("\n")

response = requests.get("https://db.ygoprodeck.com/api/v7/cardsets.php")
cardsets_json = response.json()

card_sets = pd.DataFrame(cardsets_json)
card_sets["id"] = (card_sets["set_name"] + " " + card_sets["set_code"]).apply(hash)
card_sets["tcg_date"] = pd.to_datetime(card_sets["tcg_date"])
card_sets = card_sets[["id", "set_name", "set_code", "num_of_cards", "tcg_date"]]
card_sets = card_sets.sort_values(by=["tcg_date", "set_name"])
card_sets.to_csv("cardsets.csv", index=False)

cardset_to_id = {
    (row["set_name"], row["set_code"]): row["id"] for _, row in card_sets.iterrows()
}

"""# All cards"""

response = requests.get("https://db.ygoprodeck.com/api/v7/cardinfo.php?misc=yes")
cardinfo_json = response.json()

main_attributes = [
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
ban_attributes = [
    "ban_tcg",
    "ban_ocg",
    "ban_goat",
]

misc_attributes = [
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


def process_card(card):

    # Base info
    card_info = {attribute: card.get(attribute) for attribute in main_attributes}

    # Banlist info
    banlist_info = card.get("banlist_info", {})
    card_info.update(
        {attribute: banlist_info.get(attribute) for attribute in ban_attributes}
    )

    # Images
    og_id = card_info["id"]
    images = card["card_images"]
    [main_images] = [image for image in images if image["id"] == og_id]
    card_info.update(
        {
            "image_url": main_images["image_url"],
            "image_url_small": main_images["image_url_small"],
        }
    )

    # Alternate images
    alternate_images = [image["id"] for image in images if image["id"] != og_id]

    # Misc info
    misc_info = card["misc_info"][0] if card.get("misc_info") else {}
    card_info.update(
        {attribute: misc_info.get(attribute) for attribute in misc_attributes}
    )
    card_info["formats"] = (
        "|".join(card_info["formats"]) if card_info["formats"] else None
    )

    # Card sets
    card_sets = card.get("card_sets", [])
    sets = [
        {
            f"set_{set_attr}": card_set[f"set_{set_attr}"]
            for set_attr in ["name", "code", "rarity", "rarity_code"]
        }
        for card_set in card_sets
    ]

    return card_info, alternate_images, sets


cards = []
alternates = []
set_information = []
for card in cardinfo_json["data"]:
    card, alternate, set_info = process_card(card)
    cards.append(card)

    # Alternate
    alternates.extend([(card["id"], alter) for alter in alternate])

    # Set info
    for info in set_info:
        name = info.pop("set_name")
        set_id, _, set_code = info.pop("set_code").partition("-")
        set_hash_id = cardset_to_id.get((name, set_id))
        if set_hash_id:
            info["set_id"] = set_hash_id
            info["set_code"] = set_code
            info["card_id"] = card["id"]
            set_information.append(info)

all_cards = pd.DataFrame(cards)

columns = (
    [
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
    + ["image_url", "image_url_small"]
    + [
        "ban_tcg",
        "ban_ocg",
        "ban_goat",
    ]
    + [
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
)

all_cards = all_cards[columns].sort_values(by="name")
all_cards.to_csv("cards.csv", index=False)

card_set_relation = pd.DataFrame(set_information)
card_set_relation = card_set_relation[
    ["card_id", "set_id", "set_code", "set_rarity", "set_rarity_code"]
].sort_values(by=["card_id", "set_id"])
card_set_relation.to_csv("cards_cardsets.csv", index=False)

variants = pd.DataFrame(alternates, columns=["original", "variant"])
variants = variants.sort_values(by=["original", "variant"])
variants.to_csv("cards_variants.csv", index=False)
