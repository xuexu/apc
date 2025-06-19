from apc.logging_config import setup_logging
setup_logging()

from apc import fur_seed, hacks, hacks2, config

def main():
  #hacks.seed_animals("emerald")
  #hacks.seed_animals("sundarpatan")
  #hacks.merge_animal_details()
  hacks2.update_global_animal_data()
  hacks2.seed_reserve_animal_details("alberta")
  # hacks2.seed_all_reserves()
  # for reserve, reserve_data in config.RESERVES.items():
  #  print(f'{reserve} - {reserve_data["reserve_name"]}')
  #  hacks.launch_aps()
  #  hacks.click_reserve(reserve)
    # hacks.seed_animals3(reserve)
    # hacks2a.seed_fur_ids(reserve)


if __name__ == "__main__":
  main()
