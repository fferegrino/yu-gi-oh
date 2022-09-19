from datetime import date

from kaggle import api

update_message = f"{date.today()} update"

api.dataset_create_version("data", update_message, dir_mode="zip", quiet=False)
