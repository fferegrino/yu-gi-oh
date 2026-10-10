---
license: cc-by-sa-3.0
pretty_name: Yu-Gi-Oh! Cards
tags:
- yu-gi-oh
- trading-card-games
- games
size_categories:
- 10K<n<100K
configs:
- config_name: cards
  data_files: cards.csv
  default: true
- config_name: cardsets
  data_files: cardsets.csv
- config_name: cards_cardsets
  data_files: cards_cardsets.csv
- config_name: cards_variants
  data_files: cards_variants.csv
---

# Yu-Gi-Oh! Cards

All the Yu-Gi-Oh! cards available on [YGOPRODeck](https://ygoprodeck.com/), downloaded weekly through its API. Visit YGOPRODeck for the best Yu-Gi-Oh! online experience.

| File | Contents |
| --- | --- |
| `cards.csv` | Every card: stats, text, ban list status, images and popularity |
| `cardsets.csv` | Every card set, identified by a hash of its name and code |
| `cards_cardsets.csv` | Which cards were printed in which sets, and at what rarity |
| `cards_variants.csv` | Alternate artworks, mapping each original card ID to its variant IDs |

Card IDs match the decks in the [Yu-Gi-Oh! Decks](https://huggingface.co/datasets/feregrino/yugioh-decks) dataset.

Also available on [Kaggle](https://www.kaggle.com/datasets/ioexception/yugioh-cards). The code that builds it lives at [fferegrino/yu-gi-oh](https://github.com/fferegrino/yu-gi-oh).

The literal and graphical information presented on this dataset Yu-Gi-Oh!, including card images, the attribute, level/rank and type symbols, and card text, is copyright of 4K Media Inc, a subsidiary of Konami Digital Entertainment, Inc.
