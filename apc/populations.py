from apc.logging_config import get_logger

logger = get_logger(__name__)

import random
import time
from typing import Callable

import FreeSimpleGUI as sg
import numpy as np

from apc import adf, adf_profile, config, fur_seed
from apc.adf import AdfAnimal, LoadedReserve
from apc.config import (get_level_name, get_reserve,
                        get_reserve_name, get_species_name,
                        valid_species_for_reserve)
from apc.utils import update_float, update_uint, format_key
from deca.ff_adf import Adf, AdfValue


class NoAnimalsException(Exception):
  pass

def _get_species_population(reserve_key: str, reserve_adf: Adf, species_key: str) -> AdfValue:
  reserve = config.RESERVES[reserve_key]
  species_index = reserve["species"].index(species_key)
  populations = _get_populations(reserve_adf)
  return populations[species_index]

def _get_species_groups(reserve_key: str, reserve_adf: Adf, species_key: str) -> list[AdfValue]:
  species_population =_get_species_population(reserve_key, reserve_adf, species_key)
  groups = species_population.value["Groups"].value
  if len(groups) == 0:
    raise NoAnimalsException(f"Invalid population data: There are no animal groups for {species_key} on {reserve_key}.")
  return groups

def _get_populations(reserve_adf: Adf) -> list[AdfValue]:
  populations = reserve_adf.table_instance_full_values[0].value["Populations"].value
  return populations
  # return [p for p in populations if len(p.value["Groups"].value) > 0]

def _find_animal_level(weight: float, levels: list) -> int:
  if levels == []:
    return 0
  level = 1
  weight = round(weight, 2) if weight > 10 else round(weight, 3)
  for value_i, value in enumerate(levels):
    low_bound, high_bound = value
    high_bound = round(high_bound, 2) if high_bound > 10 else round(high_bound, 3)
    if (weight <= high_bound and weight > low_bound) or weight > high_bound:
      level = value_i + 1
  return level

def _is_great_one(animal: AdfAnimal) -> bool:
  return animal.great_one

def _is_diamond(animal: AdfAnimal) -> bool:
  known_species = config.valid_species(animal.species_key)
  diamond_config = config.ANIMALS[animal.species_key]["trophy"]["diamond"]
  diamond_score = diamond_config["score_low"] if known_species else config.HIGH_NUMBER
  diamond_gender = config.get_diamond_gender(animal.species_key)
  return animal.score >= diamond_score and (animal.gender == diamond_gender or diamond_gender == "both")

def find_animals(species_key: str, modded = False, good = False, top: bool = False, progress_bar: sg.ProgressBar = None) -> list:
  animals = []
  reserve_keys = config.reserve_keys()
  progress_per_reserve = 90/len(reserve_keys)
  for i, reserve_key in enumerate(reserve_keys):
    if valid_species_for_reserve(species_key, reserve_key):
      try:
        reserve_details = adf.load_reserve(reserve_key, modded)
        reserve_animals = describe_animals(reserve_key, species_key, reserve_details.adf, good=good)
        animals.extend(reserve_animals)
      except adf.FileNotFound as ex:
        save_path = config.MOD_DIR_PATH if modded else config.get_save_path()
        logger.error(f"{config.FILE_NOT_FOUND}: {save_path / config.get_population_file_name(reserve_key)}")
    if progress_bar:
      progress_bar.update((i+1)*progress_per_reserve)
  animals = sorted(animals, key = lambda x : x[4], reverse=True)
  return animals[:10] if top else animals

def describe_animals(reserve_key: str, species_key: str, reserve_adf: Adf, good = False, top: bool = False, precision: int = 2) -> list[list[list]]:
  populations = _get_populations(reserve_adf)
  population = populations[get_reserve(reserve_key)["species"].index(species_key)]
  groups = population.value["Groups"].value
  rows = []

  logger.debug(f"Processing {format_key(species_key)} animals...")
  species_config = config.get_species(species_key)
  if (
    species_config is None  # trying to parse an unknown animal - new map? use hacks2.parse_reserve_species()
    or not groups  # some maps have placeholder blank groups for animals that were removed during development
  ):
    logger.info("No groups found for %s", species_key)
    return []
  diamond_config = species_config["trophy"]["diamond"]
  diamond_weight = diamond_config["weight_low"]
  diamond_score = diamond_config["score_low"]
  logger.debug(f"Species: {species_key}   Diamond Weight: {diamond_weight}   Diamond Score: {diamond_score}")

  for group in groups:
    animals = group.value["Animals"].value
    rows.extend(describe_animal_group(reserve_key, species_key, animals, good=good, top=top, precision=precision))
  rows.sort(key=lambda x: x[4], reverse=True)
  return rows[:10] if top else rows

def describe_animal_group(reserve_key: str, species_key: str, animals: list[AdfValue], good: bool = False, top: bool = False, precision: int = 2) -> list[list]:
  animal_data = []

  species_config = config.get_species(species_key)
  animal_levels = species_config.get("level", [])

  for animal in animals:
    adf_animal = AdfAnimal(animal, species_key, reserve_key)
    is_diamond = _is_diamond(adf_animal)
    is_great_one = _is_great_one(adf_animal)

    if ((good and (is_diamond or is_great_one)) or not good):
      level = _find_animal_level(adf_animal.weight, animal_levels) if not is_great_one else 10
      level_name = get_level_name(config.Levels(level))
      animal_data.append([
        get_reserve_name(reserve_key),
        f"{level} : {level_name}",
        config.MALE if adf_animal.gender == "male" else config.FEMALE,
        round(adf_animal.weight, precision),
        round(adf_animal.score, precision),
        adf_animal.fur_name,
        adf_animal.trophy,
        adf_animal
      ])
  return animal_data

def describe_reserve(reserve_key: str, reserve_adf: Adf, include_species = True) -> tuple[list[list], dict]:
    populations = _get_populations(reserve_adf)
    reserve_species = config.get_reserve(reserve_key)["species"]
    logger.debug(f"processing {len(populations)} species...")

    rows = []
    total_cnt = 0
    species_groups = {}

    for population_i, population in enumerate(populations):
      groups = population.value["Groups"].value
      animal_cnt = 0
      population_high_weight = 0
      population_high_score = 0
      female_cnt = 0
      male_cnt = 0
      great_one_cnt = 0
      diamond_cnt = 0
      female_groups = []
      male_groups = []

      species_key = config.RESERVES[reserve_key]["species"][population_i] if include_species else str(population_i)
      species_config = config.get_species(species_key)
      if (
        species_config is None  # trying to parse an unknown animal - new map? use hacks2.parse_reserve_species()
        or not groups  # some maps have placeholder blank groups for animals that were removed during development
      ):
        logger.info("No groups found for %s", species_key)
        continue
      diamond_weight = species_config["trophy"]["diamond"]["weight_low"]
      diamond_score = species_config["trophy"]["diamond"]["score_low"]
      species_max_level = len(species_config.get("level", []))
      species_name = f"{species_max_level}. {config.get_reserve_species_name(species_key, reserve_key)}"

      if diamond_score != config.HIGH_NUMBER:
        logger.debug(f"Species: {species_name}, Diamond Weight: {diamond_weight}, Diamond Score: {diamond_score}")

      for group_i, group in enumerate(groups):
        animals = group.value["Animals"].value
        group_animal_cnt = len(animals)
        animal_cnt += group_animal_cnt
        total_cnt += group_animal_cnt
        group_male_cnt = 0
        group_female_cnt = 0

        for animal_i, animal in enumerate(animals):
          animal = AdfAnimal(animal, species_key, reserve_key)

          if animal.gender == "male":
            male_cnt += 1
            group_male_cnt += 1
            if animal.score > population_high_score:
                population_high_score = animal.score
          else:
            female_cnt += 1
            group_female_cnt += 1

          if animal.weight > population_high_weight:
              population_high_weight = animal.weight

          if animal.great_one:
            great_one_cnt += 1
          elif _is_diamond(animal):
            diamond_cnt += 1
        if group_male_cnt > 0:
          male_groups.append(group_i)
        if group_female_cnt > 0:
          female_groups.append(group_i)

      species_groups[reserve_species[population_i]] = { "male": male_groups, "female": female_groups }

      rows.append([
        species_key,
        species_max_level,
        species_name,
        animal_cnt,
        male_cnt,
        female_cnt,
        round(population_high_weight, 2),
        round(population_high_score, 2),
        diamond_cnt,
        great_one_cnt
      ])

    return (sorted(rows, key = lambda x: x[1]), species_groups)

def _get_eligible_animals(groups: list[AdfValue], species_key: str, reserve_key: str, gender: str, include_diamonds: bool = False, include_great_ones: bool = False) -> list[AdfAnimal]:
  eligible_animals: list[AdfAnimal] = []
  for group_i, group in enumerate(groups):
    animals = group.value["Animals"].value
    for animal_i, animal in enumerate(animals):
      animal = AdfAnimal(animal, species_key, reserve_key=reserve_key)
      if _is_great_one(animal) and not include_great_ones:
        continue
      if _is_diamond(animal) and not include_diamonds:
        continue
      if animal.gender == gender or gender == "both":
        eligible_animals.append(animal)
  logger.info(f"Found {len(eligible_animals)} eligible animals")
  return eligible_animals

def _get_eligible_groups(groups: list[AdfValue], minimum_animals: int = 1) -> list[AdfAnimal]:
  eligible_groups: list[AdfValue] = []
  for group_i, group in enumerate(groups):
    animals = group.value["Animals"].value
    if len(animals) >= minimum_animals:
      eligible_groups.append(group)
  logger.debug(f"Found {len(eligible_groups)} eligible groups")
  return eligible_groups

def _update_animal(data: bytearray, animal: AdfAnimal, great_one: bool, gender: str, weight: float, score: float, visual_seed: int) -> None:
  update_uint(data, animal.gender_offset, 1 if gender == "male" else 2)
  update_float(data, animal.weight_offset, weight)
  update_float(data, animal.score_offset, score)
  update_uint(data, animal.great_one_offset, 1 if great_one else 0)
  update_uint(data, animal.visual_seed_offset, visual_seed)

def _create_great_one(animal: AdfAnimal, species_config: dict, data: bytearray, fur_key: str = None, kwargs: dict = {}) -> None:
  gender_config = species_config["gender"][f"great_one_{animal.gender}"]
  new_weight, new_score = config.generate_weight_and_score(gender_config)
  visual_seed = fur_seed.find_fur_seed(animal.species_key, animal.gender, great_one=True, fur_key=fur_key)
  update_uint(data, animal.visual_seed_offset, visual_seed)
  update_float(data, animal.weight_offset, new_weight)
  update_float(data, animal.score_offset, new_score)
  update_uint(data, animal.great_one_offset, 1)
  update_uint(data, animal.gender_offset, 1 if animal.gender == "male" else 2)

def _create_diamond(animal: AdfAnimal, species_config: dict, data: bytearray, fur_key: str = None, kwargs: dict = {}) -> None:
  safe_diamonds_config = config.get_safe_diamond_values(species_config)
  new_weight, new_score = config.generate_weight_and_score(safe_diamonds_config)
  if fur_key:
    visual_seed = fur_seed.find_fur_seed(animal.species_key, animal.gender, fur_key=fur_key)
    update_uint(data, animal.visual_seed_offset, visual_seed)
  update_float(data, animal.weight_offset, new_weight)
  update_float(data, animal.score_offset, new_score)
  update_uint(data, animal.great_one_offset, 0)
  update_uint(data, animal.gender_offset, 1 if animal.gender == "male" else 2)

def _create_fur(animal: AdfAnimal, _species_config: dict, data: bytearray, fur_key: str = None, kwargs: dict = {}) -> None:
  rares = kwargs.get("rares", False)
  if fur_key is None and rares and not animal.great_one:
      rare_fur_keys = config.get_rare_furs(animal.species_key, animal.gender)
      fur_key = random.choice(rare_fur_keys)
  visual_seed = fur_seed.find_fur_seed(animal.species_key, animal.gender, great_one=animal.great_one, fur_key=fur_key)
  update_uint(data, animal.visual_seed_offset, visual_seed)

def _create_male(animal: AdfAnimal, species_config: dict, data: bytearray, kwargs: dict = {}) -> None:
  old_gender_config = species_config["gender"][animal.gender]
  weight_percentile = (animal.weight - old_gender_config["weight_low"]) / (old_gender_config["weight_high"] - old_gender_config["weight_low"])
  male_config = species_config["gender"]["male"]
  new_weight, new_score = config.generate_weight_and_score(male_config, percentile=weight_percentile, fuzz=False)
  update_float(data, animal.weight_offset, new_weight)
  update_float(data, animal.score_offset, new_score)
  update_uint(data, animal.gender_offset, 1)

def _create_female(animal: AdfAnimal, species_config: dict, data: bytearray, kwargs: dict = {}) -> None:
  old_gender_config = species_config["gender"][animal.gender]
  weight_percentile = (animal.weight - old_gender_config["weight_low"]) / (old_gender_config["weight_high"] - old_gender_config["weight_low"])
  female_config = species_config["gender"]["female"]
  new_weight, new_score = config.generate_weight_and_score(female_config, percentile=weight_percentile, fuzz=False)
  update_float(data, animal.weight_offset, new_weight)
  update_float(data, animal.score_offset, new_score)
  update_uint(data, animal.gender_offset, 2)

def get_callable_message(cb: callable) -> str:
  callable_names = {
    "_create_great_one": config.GREATONES,
    "_create_diamond": config.DIAMONDS,
    "_create_fur": config.JUST_FURS,
    "_create_male": config.MORE_MALES,
    "_create_female": config.MORE_FEMALES,
  }
  return callable_names.get(cb.__name__)

def _process_all(species_key: str, species_config: dict, groups: list, loaded_reserve: LoadedReserve, cb: Callable, kwargs: dict = {}, gender: str = None, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  if gender is None:
    raise ValueError(f"No gender provided to _process_all: {species_key} @ {loaded_reserve.reserve_key} >> {cb} >> {kwargs}")
  animals = _get_eligible_animals(groups, species_key, loaded_reserve.reserve_key, gender)
  if len(animals) == 0:
    raise NoAnimalsException(f"There are not enough {get_species_name(species_key)} to process")
  if progress_bar is not None:
    progress_bar.update(0, max=len(animals))
  count = 0
  for animal in animals:
    count += 1
    if progress_bar is not None:
      progress_bar.update(count)
    if message_box is not None:
      message_box.update(f"{get_callable_message(cb)} ({config.get_species_name(species_key)}): {count}/{len(animals)}")
    cb(animal, species_config, loaded_reserve, kwargs=kwargs)

def _great_one_all(species_key: str, groups: list, loaded_reserve: LoadedReserve, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  species_config = config.get_species(species_key)
  great_one_gender = config.get_great_one_gender(species_key)
  _process_all(species_key, species_config, groups, loaded_reserve, _create_great_one, { "include_diamonds": True} , gender=great_one_gender, progress_bar=progress_bar, message_box=message_box)

def _diamond_all(species_key: str, groups: list, loaded_reserve: LoadedReserve, rares: bool = False, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  species_config = config.get_species(species_key)
  diamond_gender = config.get_diamond_gender(species_key)
  _process_all(species_key, species_config, groups, loaded_reserve, _create_diamond, { "rares": rares }, gender=diamond_gender, progress_bar=progress_bar, message_box=message_box)

def diamond_test_seed(species_key: str, groups: list, data: bytearray, seed: int, gender: int = 1) -> None:
  eligible_animals = []
  for group in groups:
    animals = group.value["Animals"].value
    for animal in animals:
      animal = AdfAnimal(animal, species_key)
      eligible_animals.append(animal)

  for animal in eligible_animals:
    update_float(data, animal.weight_offset, seed)
    update_float(data, animal.score_offset, seed / 10000)
    update_uint(data, animal.visual_seed_offset, seed)
    update_uint(data, animal.gender_offset, gender)
    seed += 1
  return seed

def diamond_test_single_seed(species_key: str, groups: list, data: bytearray, gender: int = 1) -> None:
  seed = 12345
  eligible_animals = []
  for group in groups:
    animals = group.value["Animals"].value
    for animal in animals:
      animal = AdfAnimal(animal, species_key)
      eligible_animals.append(animal)
  for animal in eligible_animals:
    update_float(data, animal.weight_offset, seed)
    update_float(data, animal.score_offset, seed)# / 10000)
    update_uint(data, animal.visual_seed_offset, seed)
    update_uint(data, animal.gender_offset, gender)

def diamond_test_seeds(species_key: str, groups: list, data: bytearray, seeds: list[int]) -> None:
  eligible_animals = []
  for group in groups:
    animals = group.value["Animals"].value
    for animal in animals[:len(seeds)]:
      animal = AdfAnimal(animal, species_key)
      eligible_animals.append(animal)

  for animal_i, animal in enumerate(eligible_animals[:len(seeds)]):
    seed = seeds[animal_i]
    update_float(data, animal.weight_offset, seed)
    update_float(data, animal.score_offset, seed / 10000)
    update_uint(data, animal.visual_seed_offset, seed)
    update_uint(data, animal.gender_offset, 1)
    seed += 1
  return seed

def diamond_test_seed2(species_key: str, groups: list, data: bytearray, seed: int, gender: int, base_weight: int = None) -> int:
  eligible_animals = []
  for group in groups:
    animals = group.value["Animals"].value
    for animal in animals:
      animal = AdfAnimal(animal, species_key)
      eligible_animals.append(animal)
  for animal in eligible_animals:
    update_float(data, animal.weight_offset, seed / 10)
    update_float(data, animal.score_offset, seed / 10000)
    update_uint(data, animal.visual_seed_offset, seed)
    update_uint(data, animal.gender_offset, gender)
    seed += 1
  return seed

def fur_test_seed(species_key: str, groups: list, data: bytearray, seed: int, gender: int) -> int:
  eligible_animals = []
  for group in groups:
    animals = group.value["Animals"].value
    for animal in animals:
      animal = AdfAnimal(animal, species_key)
      eligible_animals.append(animal)
  for animal in eligible_animals:
    update_float(data, animal.weight_offset, seed)
    update_float(data, animal.score_offset, seed / 10000)
    update_uint(data, animal.visual_seed_offset, seed)
    update_uint(data, animal.gender_offset, gender)
    seed += 1
  return seed

def weight_test_seed(species_key: str, groups: list, data: bytearray, seed: int, gender: int, base_weight: int = None) -> int:
  eligible_animals = []
  for group in groups:
    animals = group.value["Animals"].value
    for animal in animals:
      animal = AdfAnimal(animal, species_key)
      eligible_animals.append(animal)
  for animal in eligible_animals:
    if base_weight:
      weight_offset = (seed / 1000) - int(seed / 1000)
      weight = base_weight + weight_offset
    else:
      weight = seed / 10
    update_float(data, animal.weight_offset, weight)
    update_float(data, animal.score_offset, seed / 10000)
    update_uint(data, animal.visual_seed_offset, seed)
    update_uint(data, animal.gender_offset, gender)
    seed += 1
  return seed

def score_test_seed(species_key: str, groups: list, data: bytearray, seed: int, gender: int, weight: float, score_range: tuple) -> int:
  eligible_animals = []
  for group in groups:
    animals = group.value["Animals"].value
    for animal in animals:
      animal = AdfAnimal(animal, species_key)
      eligible_animals.append(animal)
  score_values = np.linspace(score_range[0], score_range[1], len(eligible_animals))
  for i, animal in enumerate(eligible_animals):
    update_float(data, animal.weight_offset, weight)
    update_float(data, animal.score_offset, score_values[i])
    update_uint(data, animal.visual_seed_offset, seed)
    update_uint(data, animal.gender_offset, gender)
    seed += 1
  return seed

def _process_furs(species_key, species_config: dict, furs: list[str], groups: list, loaded_reserve: LoadedReserve, cb: Callable, gender: str = "male", progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  eligible_animals = _get_eligible_animals(groups, species_key, loaded_reserve.reserve_key, gender)
  if len(eligible_animals) == 0:
    raise NoAnimalsException(f"There are not enough {get_species_name(species_key)} to process")
  chosen_animals = random.sample(eligible_animals, k = len(furs))
  total_count = len(chosen_animals)
  if progress_bar is not None:
    progress_bar.update(0, max=total_count)
  for animal_i, animal in enumerate(chosen_animals):
    if progress_bar is not None:
      progress_bar.update(animal_i + 1)
    if message_box is not None:
      message_box.update(f"{get_callable_message(cb)} ({config.get_species_name(species_key)}): {animal_i + 1}/{len(chosen_animals)}")
    cb(animal, species_config, loaded_reserve, fur = furs[animal_i])

def _great_one_furs(species_key: str, groups: list, loaded_reserve: LoadedReserve, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  species_config = config.get_species(species_key)
  great_one_gender = config.get_great_one_gender(species_key)
  great_one_furs= config.get_species_furs(species_key, great_one_gender, great_one=True)
  _process_furs(species_key, species_config, great_one_furs, groups, loaded_reserve, _create_great_one, gender=great_one_gender, progress_bar=progress_bar, message_box=message_box)

def _diamond_furs(species_key: str, groups: list, loaded_reserve: LoadedReserve, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  species_config = config.get_species(species_key)
  diamond_gender = config.get_diamond_gender(species_key)
  diamond_furs = config.get_species_furs(species_key, diamond_gender, great_one=False)
  _process_furs(species_key, species_config, diamond_furs, groups, loaded_reserve, _create_diamond, gender=diamond_gender, progress_bar=progress_bar, message_box=message_box)

def _update_with_furs(loaded_reserve: LoadedReserve, species_key: str, groups: list, male_fur_keys: list[str], female_fur_keys: list[str], male_fur_cnt: int, female_fur_cnt: int, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  species_config = config.get_species(species_key)
  male_animals = _get_eligible_animals(groups, species_key, loaded_reserve.reserve_key, "male", include_diamonds=True)
  male_animals = random.sample(male_animals, k = male_fur_cnt)
  female_animals = _get_eligible_animals(groups, species_key, loaded_reserve.reserve_key, "female", include_diamonds=True)
  female_animals = random.sample(female_animals, k = female_fur_cnt)
  total_count = male_fur_cnt+female_fur_cnt
  if progress_bar is not None:
    progress_bar.update(0, max=total_count)
  count = 0
  reserve_data = loaded_reserve.parsed_adf.decompressed.data
  for animal in male_animals:
    count += 1
    if progress_bar is not None:
      progress_bar.update(count)
    if message_box is not None:
      message_box.update(f"{config.UPDATE_ANIMALS}: {count}/{total_count}")
    fur_key = random.choice(male_fur_keys)
    _create_fur(animal, species_config, reserve_data, fur_key)
  for animal in female_animals:
    count += 1
    if progress_bar is not None:
      progress_bar.update(count)
    if message_box is not None:
      message_box.update(f"{config.UPDATE_ANIMALS}: {count}/{total_count}")
    fur_key = random.choice(female_fur_keys)
    _create_fur(animal, species_config, reserve_data, fur_key)

def _process_some(species_key: str, species_config: dict, groups: list, loaded_reserve: LoadedReserve, modifier: int, percentage: bool, cb: Callable, kwargs: dict = {}, gender: str = None, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  if gender is None:
    raise ValueError(f"No gender provided to _process_some: {species_key} @ {loaded_reserve.reserve_key} >> {cb} >> MOD:{modifier}   %:{percentage} >> {kwargs}")
  callable_name = cb.__name__
  party = kwargs.get("party", False)
  include_diamonds = (
    kwargs.get("include_diamonds", False)
    or (party and callable_name in ("_diamond_some", "_great_one_some"))
  )
  include_great_ones = (
    kwargs.get("include_great_ones", False)
    or (party and callable_name == "_great_one_some")
  )
  eligible_animals = _get_eligible_animals(groups, species_key, loaded_reserve.reserve_key, gender, include_diamonds=include_diamonds, include_great_ones=include_great_ones)
  logger.info(f"There are {len(eligible_animals)} eligible animals")
  animal_cnt = round((modifier / 100) * len(eligible_animals)) if percentage else modifier
  if party and animal_cnt > len(eligible_animals):
    animal_cnt = len(eligible_animals)  # just convert all eligible animals for a party
  if (len(eligible_animals) == 0 or len(eligible_animals) < animal_cnt) and not party:
    raise NoAnimalsException(f"There are not enough {get_species_name(species_key)} to process")
  if progress_bar is not None:
    progress_bar.update(0, max=animal_cnt)
  count = 0
  chosen_animals = random.sample(eligible_animals, k = animal_cnt)
  logger.debug(f"{callable_name} >> {animal_cnt} x {species_key}")
  for animal in chosen_animals:
    count += 1
    if progress_bar is not None:
      progress_bar.update(count)
    if message_box is not None:
      message_box.update(f"{get_callable_message(cb)} ({config.get_species_name(species_key)}): {count}/{animal_cnt}")
    cb(animal, species_config, loaded_reserve.parsed_adf.decompressed.data, kwargs=kwargs)

def _great_one_some(species_key: str, groups: list, loaded_reserve: LoadedReserve, modifier: int = None, percentage: bool = False, party: bool = False, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  species_config = config.get_species(species_key)
  great_one_gender = config.get_great_one_gender(species_key)
  _process_some(species_key, species_config, groups, loaded_reserve, modifier, percentage, _create_great_one, { "party": party, "include_diamonds": True }, gender=great_one_gender, progress_bar=progress_bar, message_box=message_box)

def _diamond_some(species_key: str, groups: list, loaded_reserve: LoadedReserve, modifier: int = None, percentage: bool = False, rares: bool = False, party: bool = False, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  species_config = config.get_species(species_key)
  diamond_gender = config.get_diamond_gender(species_key)
  _process_some(species_key, species_config, groups, loaded_reserve, modifier, percentage, _create_diamond, { "party": party, "rares": rares }, gender=diamond_gender, progress_bar=progress_bar, message_box=message_box)

def _furs_some(species_key: str, groups: list, loaded_reserve: LoadedReserve, modifier: int = None, percentage: bool = False, rares: bool = False, party: bool = False, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None)-> None:
  species_config = config.get_species(species_key)
  _process_some(species_key, species_config, groups, loaded_reserve, modifier, percentage, _create_fur, { "party": party, "rares": rares, "include_diamonds": True }, gender="both", progress_bar=progress_bar, message_box=message_box)

def _male_some(species_key: str, groups: list, loaded_reserve: LoadedReserve, modifier: int = None, percentage: bool = False, party: bool = False, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  species_config = config.get_species(species_key)
  _process_some(species_key, species_config, groups, loaded_reserve, modifier, percentage, _create_male, { "party": party }, gender="female", progress_bar=progress_bar, message_box=message_box)

def _female_some(species_key: str, groups: list, loaded_reserve: LoadedReserve, modifier: int = None, percentage: bool = False, party: bool = False, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  species_config = config.get_species(species_key)
  _process_some(species_key, species_config, groups, loaded_reserve, modifier, percentage, _create_female, { "party": party }, gender="male", progress_bar=progress_bar, message_box=message_box)

def _add_animals(loaded_reserve: LoadedReserve, species_key: str, animal_count: int, gender: str, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> int:
  '''
  Loops through non-empty groups and duplicate the first animal in each group
  Animal stats are re-rolled after duplication to ensure uniqueness
  '''
  groups = _get_species_groups(loaded_reserve.reserve_key, loaded_reserve.parsed_adf.adf, species_key)
  eligible_groups = _get_eligible_groups(groups, 1)
  if progress_bar is not None:
    progress_bar.update(0, max=animal_count)
  added_count = 0
  skipped_groups = []
  while added_count < animal_count and len(eligible_groups) > len(skipped_groups):
    group_index = added_count % len(eligible_groups)
    selected_group = eligible_groups[group_index]
    if len(selected_group.value["Animals"].value) >= 30:
      logger.info(f"skipping group {group_index}")
      skipped_groups.append(group_index)
      continue
    added_count += 1
    if progress_bar is not None:
      progress_bar.update(added_count)
    if message_box is not None:
      message_box.update(f"{config.ADD_ANIMALS}: {added_count}/{animal_count} {config.MALE if gender == "male" else config.FEMALE} {config.get_species_name(species_key)}")
    adf.add_animal_to_group(loaded_reserve, selected_group, species_key, gender)
  return added_count

def _remove_animals(loaded_reserve: LoadedReserve, species_key: str, animal_count: int, gender: str, loop_data: dict = {}, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> int:
  '''
  Loops through groups with at least 2 animals and removes the first animal in each group
  Currently need to save and re-parse the ADF after each loop due to an issue with
    incorrect offsets when attempting to remove multiple animals from a group
  '''
  removed_count = loop_data.get("removed_count", 0)
  progress_max = loop_data.get("progress_max", animal_count)
  groups = _get_species_groups(loaded_reserve.reserve_key, loaded_reserve.parsed_adf.adf, species_key)
  eligible_groups = _get_eligible_groups(groups, 2)
  if len(eligible_groups) == 0:
    raise NoAnimalsException(f"{config.REMOVE_ANIMALS_ERROR}: {config.TOO_FEW_GROUP_ANIMALS}")
  if progress_bar is not None:
    progress_bar.update(removed_count, max=progress_max)
  loop_count = -1
  skipped_groups = []
  while removed_count < progress_max and len(eligible_groups) > len(skipped_groups):
    loop_count += 1
    logger.debug(f"loop: {loop_count}   removed: {removed_count}   remaining groups: {len(eligible_groups) - len(skipped_groups)}")
    group_index = loop_count % len(eligible_groups)
    if group_index == 0 and loop_count > 0:  # back at the beginning of the list
      loaded_reserve.save()
      loop_data = {
        "removed_count": removed_count,
        "progress_max": progress_max,
      }
      removed_count = _remove_animals(loaded_reserve, species_key, animal_count, gender, loop_data=loop_data, progress_bar=progress_bar, message_box=message_box)
      return removed_count
    if group_index in skipped_groups:
      continue
    selected_group = eligible_groups[group_index]
    if len(selected_group.value["Animals"].value) <= 1:  # Don't remove the last animal from a group
      logger.info(f"skipping group {group_index}")
      skipped_groups.append(group_index)
      continue
    if adf.remove_animal_from_group(loaded_reserve, selected_group, species_key, gender):
      removed_count += 1
      if progress_bar is not None:
        progress_bar.update(removed_count)
      if message_box is not None:
        message_box.update(f'{config.REMOVE_ANIMALS}: {removed_count}/{animal_count} {config.MALE if gender == "male" else config.FEMALE} {config.get_species_name(species_key)}')
    else:
      # couldn't find a valid animal to delete
      skipped_groups.append(group_index)
      continue
  return removed_count

def mod_furs(loaded_reserve: LoadedReserve, species_key: str, male_fur_keys: list[str], female_fur_keys: list[str], male_fur_cnt: int, female_fur_cnt: int, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> None:
  groups = _get_species_groups(loaded_reserve.reserve_key, loaded_reserve.parsed_adf.adf, species_key)
  species_name = config.get_species_name(species_key)
  _update_with_furs(loaded_reserve, species_key, groups, male_fur_keys, female_fur_keys, male_fur_cnt, female_fur_cnt, progress_bar=progress_bar, message_box=message_box)
  logger.info(f"[green]All {species_name} furs have been updated![/green]")
  loaded_reserve.save()

def mod_diamonds(loaded_reserve: LoadedReserve, species_key: str, diamond_cnt: int, male_fur_keys: list[str], female_fur_keys: list[str], progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> list:
  species_population =_get_species_population(loaded_reserve.reserve_key, loaded_reserve.parsed_adf.adf, species_key)
  groups: AdfValue = species_population.value["Groups"].value
  species_name = config.get_species_name(species_key)
  reserve_data = loaded_reserve.parsed_adf.decompressed.data
  diamond_gender = config.get_diamond_gender(species_key)
  animals = _get_eligible_animals(groups, species_key, loaded_reserve.reserve_key, diamond_gender)
  animals = random.sample(animals, k=diamond_cnt)
  if progress_bar is not None:
    progress_bar.update(0, max=len(animals))
  count = 0

  species_config = config.get_species(species_key)
  for animal in animals:
    count += 1
    if progress_bar is not None:
      progress_bar.update(count)
    if message_box is not None:
      message_box.update(f"{get_callable_message(_create_diamond)} ({config.get_species_name(species_key)}): {count}/{len(animals)}")
    if not male_fur_keys:
      male_fur_keys = config.get_furs(species_key, "male")
    if not female_fur_keys:
      female_fur_keys = config.get_furs(species_key, "female")
    if diamond_gender == "both":
      diamond_gender = random.choice(["male", "female"])
    if diamond_gender == "male":
      animal.gender = "male"
      _create_diamond(animal, species_config, reserve_data, fur_key=random.choice(male_fur_keys))
    elif diamond_gender == "female":
      animal.gender = "female"
      _create_diamond(animal, species_config, reserve_data, fur_key=random.choice(female_fur_keys))

  logger.info(f"[green]All {diamond_cnt} {species_name} diamonds have been added![/green]")
  loaded_reserve.save()

def mod_animal(loaded_reserve: LoadedReserve, animal: AdfAnimal, great_one: bool, gender: str, weight: float, score: float, fur_key_or_seed: str | int = None) -> list:
  # an integer is passed if we are keeping an existing VisualVariationSeed
  if isinstance(fur_key_or_seed, int):
    visual_seed = fur_key_or_seed
  else:
    visual_seed = fur_seed.find_fur_seed(animal.species_key, gender, great_one, fur_key=fur_key_or_seed)
  _update_animal(loaded_reserve.parsed_adf.decompressed.data, animal, great_one, gender, weight, score, visual_seed)
  logger.info(f"[green]Animal has been updated![/green]")

def mod_animal_cnt(loaded_reserve: LoadedReserve, species_key: str, animal_cnt: int, gender: str, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None) -> list:
  species_name = config.get_species_name(species_key)
  logger.debug(f"Modding animal count: {species_key} + {animal_cnt} {gender}")
  if animal_cnt > 0:
    result = _add_animals(loaded_reserve, species_key, animal_cnt, gender, progress_bar=progress_bar, message_box=message_box)
    if result < animal_cnt:
      message_box.update(f"{config.ADD_ANIMALS_ERROR}: {config.TOO_MANY_GROUP_ANIMALS}")
      time.sleep(2)
  elif animal_cnt < 0:
    result = _remove_animals(loaded_reserve, species_key, abs(animal_cnt), gender, progress_bar=progress_bar, message_box=message_box)
    if result < abs(animal_cnt):
      message_box.update(f"{config.REMOVE_ANIMALS_ERROR}: {config.TOO_FEW_GROUP_ANIMALS}")
      time.sleep(2)
  loaded_reserve.save()
  logger.info(f"[green]All {abs(animal_cnt)} {gender} {species_name} animals have been {'added' if animal_cnt > 0 else 'removed'}![/green]")

def mod(loaded_reserve: LoadedReserve, species_key: str, strategy: str, modifier: int = None, percentage: bool = False, rares: bool = False, party: bool = False, progress_bar: sg.ProgressBar = None, message_box: sg.Text = None):
  groups = _get_species_groups(loaded_reserve.reserve_key, loaded_reserve.parsed_adf.adf, species_key)
  species_name = config.get_species_name(species_key)

  if (strategy == config.Strategy.great_one_all):
    _great_one_all(species_key, groups, loaded_reserve, progress_bar=progress_bar, message_box=message_box)
    logger.info(f"[green]All {species_name} are now Great Ones![/green]")
  elif (strategy == config.Strategy.great_one_furs):
    _great_one_furs(species_key, groups, loaded_reserve, progress_bar=progress_bar, message_box=message_box)
    logger.info(f"[green]All {species_name} Great One furs have been added![/green]")
  elif (strategy == config.Strategy.great_one_some):
    _great_one_some(species_key, groups, loaded_reserve, modifier, percentage, party=party, progress_bar=progress_bar, message_box=message_box)
    logger.info(f"[green]All {modifier}{'%' if percentage else ''} {species_name} are now Great Ones![/green]")
  elif (strategy == config.Strategy.diamond_all):
    _diamond_all(species_key, groups, loaded_reserve, rares, progress_bar=progress_bar, message_box=message_box)
    logger.info(f"[green]All {species_name} are now Diamonds![/green]")
  elif (strategy == config.Strategy.diamond_furs):
    _diamond_furs(species_key, groups, loaded_reserve, progress_bar=progress_bar, message_box=message_box)
    logger.info(f"[green]All {species_name} are now Diamonds![/green]")
  elif (strategy == config.Strategy.diamond_some):
    _diamond_some(species_key, groups, loaded_reserve, modifier, percentage, rares, party=party, progress_bar=progress_bar, message_box=message_box)
    logger.info(f"[green]All {modifier}{'%' if percentage else ''} {species_name} are now Diamonds![/green]")
  elif (strategy == config.Strategy.males):
    _male_some(species_key, groups, loaded_reserve, modifier, percentage, party=party, progress_bar=progress_bar, message_box=message_box)
    logger.info(f"[green]All {modifier}{'%' if percentage else ''} {species_name} are now males![/green]")
  elif (strategy == config.Strategy.females):
    _female_some(species_key, groups, loaded_reserve, modifier, percentage, party=party, progress_bar=progress_bar, message_box=message_box)
    logger.info(f"[green]All {modifier}{'%' if percentage else ''} {species_name} are now females![/green]")
  elif (strategy == config.Strategy.furs_some):
    _furs_some(species_key, groups, loaded_reserve, modifier, percentage, rares, progress_bar=progress_bar, message_box=message_box)
    logger.info(f"[green]All {modifier}{'%' if percentage else ''} {species_name} are now {'rare' if rares else 'random'} furs![/green]")
  else:
    logger.error(f"Unknown strategy: {strategy}")

  loaded_reserve.save()
