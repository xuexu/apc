from apc.logging_config import get_logger
logger = get_logger(__name__)

import json, subprocess, pyautogui, time, re
from pathlib import Path
from apc import populations, adf, config, utils
from apc.adf import ParsedAdfFile
from typing import List

def extract_animal_names(path: Path) -> dict:
  data = json.load(path.open())
  names = {}
  for animal in data.keys():
    names[animal] = { "animal_name": config.format_key(animal) }
  return {
    "animal_names": names
  }
  
def extract_reserve_names(path: Path) -> dict:
  data = json.load(path.open())
  names = {}
  for reserve in data.keys():
    names[reserve] = { "reserve_name": data[reserve]["name"] }
  return {
    "reserve_names": names
  }  

def extract_furs_names(path: Path) -> dict:
  data = json.load(path.open())
  fur_names = {}
  for animal in list(data.keys()):
    for _gender, furs in data[animal]["diamonds"]["furs"].items():
      for fur in furs.keys():        
        if fur not in fur_names:
          fur_name = config.format_key(fur)
          fur_names[fur] = { "fur_name": fur_name }
    if "go" in data[animal]:
      for fur in data[animal]["go"]["furs"].keys():
        if fur not in fur_names:
          fur_name = config.format_key(fur)
          fur_names[fur] = { "fur_name": fur_name }
  return {
    "fur_names": fur_names
  }

def bad_scores(path: Path) -> None:
  data = json.load(path.open())
  for animal_key in data.keys():
    animal = data[animal_key]
    if animal["diamonds"]["score_low"] > animal["diamonds"]["score_high"]:
      print(animal_key, animal)

def merge_furs() -> None:
  scan = json.load(Path("scans/furs.json").open())
  details = json.load(Path("apc/config/animal_details.json").open())
  for animal_name, furs in scan.items():
    existing_animal = details[animal_name]
    if existing_animal:
      existing_animal_furs = existing_animal["diamonds"]["furs"]
      if list(existing_animal_furs["male"].values())[0] == 0:
        details[animal_name]["diamonds"]["furs"] = furs
  Path("apc/config/animal_details2.json").write_text(json.dumps(details, indent=2))

def analyze_reserve(path: Path) -> None:
  pops = populations._get_populations(adf.load_adf(path, txt=True).adf)
  group_weight = {}
  for p_i, p in enumerate(pops):
    groups = p.value["Groups"].value
    high_weight = 0
    for g in groups:
      animals = g.value["Animals"].value
      for a in animals:
        a = populations.AdfAnimal(a, "unknown")
        if a.weight > high_weight:
          high_weight = a.weight
    group_weight[p_i] = high_weight
  print(json.dumps(group_weight, indent=2))

def compare_fur_cnt() -> None:
  details = json.load(Path("apc/config/animal_details.json").open())
  global_furs = json.load(Path("scans/global_furs.json").open())
  for animal_name, detail in details.items():
    if animal_name == "eg_kangaroo":
      animal_name = "eastern_grey_kangaroo"
    elif animal_name == "sw_crocodile":
      animal_name = "saltwater_crocodile"
    if animal_name in global_furs:
      global_male_cnt = global_furs[animal_name]["male_cnt"]
      global_female_cnt = global_furs[animal_name]["female_cnt"]
      male_cnt = len(detail["diamonds"]["furs"]["male"])
      female_cnt = len(detail["diamonds"]["furs"]["female"])
      missing_male = global_male_cnt != male_cnt
      missing_female = global_female_cnt != female_cnt
      if missing_male or missing_female:
        print(f"{animal_name} (male: {global_male_cnt - male_cnt}) (female: {global_female_cnt - female_cnt})")
    else:
      print("** MISSING:", animal_name)

FURS_PATH = Path("scans/furs.json")
LEVELS_PATH = Path("scans/levels.json")
SCORES_PATH = Path("scans/scores.json")

class ApsAnimal:
  def __init__(self, animal_line: str) -> None:
    animal_parts = animal_line.split(",")
    self.species = utils.unformat_key(animal_parts[0])
    self.difficulty = animal_parts[1]
    self.gender = "male" if animal_parts[2].lower() == "male" else "female"
    self.weight = float(animal_parts[3].split(" ")[0])
    self.score = float(animal_parts[4].split(" ")[0])
    self.fur = animal_parts[5].lower().rstrip()
  
  def __repr__(self) -> str:
    return f"{self.species}, {self.difficulty}, {self.gender}, {self.weight}, {self.score}, {self.fur}"

def reset_ini() -> None:
  filename = Path("imgui.ini")
  content = filename.read_text()
  new_content = re.sub("Pos=\d+,\d+", "Pos=0,0", content, flags=re.RegexFlag.MULTILINE)
  new_content = re.sub(r"LastPopFile=.*", "LastPopFile=", new_content)
  filename.write_text(new_content)
  
def launch_aps() -> None:  
  reset_ini()
  subprocess.Popen(f"AnimalPopulationScanner.exe -p > scans\scan.csv", shell=True)  

def map_aps(reserve_name: str, species_key: str) -> str:
  if species_key == "eu_rabbit":
    return "euro_rabbit"
  if species_key == "eu_bison":
    return "euro_bison"
  if species_key == "siberian_musk_deer":
    return "musk_deer"
  if species_key == "eurasian_brown_bear":
    return "brown_bear"
  if species_key == "western_capercaillie":
    return "W.Capercaillie"
  if species_key == "gray_wolf":
    return "grey_wolf"
  if species_key == "eurasian_wigeon":
    return "Eu.Wigeon"
  if species_key == "sidestriped_jackal":
    return "S-Striped_jackal"
  if species_key == "cinnamon_teal":
    return "cin_teal"
  if species_key == "collared_peccary":
    return "coll._peccary"
  if species_key == "harlequin_duck":
    return "h_duck"
  if species_key == "gray_wolf":
    return "grey_wolf"
  if species_key == "eu_hare":
    return "european_hare"
  if species_key == "southeastern_ibex":
    return "ses_ibex"
  if species_key == "wild_turkey":
    return "turkey"
  if species_key == "prong_horn":
    return "pronghorn"
  # if reserve_name == "silver" and species_key == "puma":
  #   return "mountain_lion"
  if species_key == "rockymountain_elk":
    return "rm_elk"
  if species_key == "rio_grande_turkey":
    return "rg_turkey"
  if species_key == "antelope_jackrabbit":
    return "ant._jackrabbit"
  if species_key == "northern_bobwhite_quail":
    return "Bobwhite_Quail"
  if species_key == "green_wing_teal":
    return "green-winged_teal"
  if species_key == "eastern_cottontail_rabbit":
    return "ect_rabbit"
  if species_key == "eastern_wild_turkey":
    return "ew_turkey"
  if reserve_name == "mississippi" and species_key == "feral_pig":
    return "wild_hog"
  if species_key == "american_alligator":
    return "Am._Alligator"
  if species_key == "tundra_bean_goose":
    return "t.bean_goose"
  if species_key == "eurasian_teal":
    return "eu.teal"
  
  return species_key

"""
Captures first seed that gives fur
"""
def process_aps(species_key: str, filename: Path) -> None:
  scanned_furs = {}
  scanned_levels = {}
  with filename.open() as csvfile:
    animals = csvfile.readlines()
    for animal in animals:
      try:
        animal = ApsAnimal(animal)
        if animal.species_key.lower() == species_key.lower():
          # parse furs
          if animal.gender not in scanned_furs:
            scanned_furs[animal.gender] = {}
          if animal.fur not in scanned_furs[animal.gender]:
            scanned_furs[animal.gender][animal.fur] = animal.weight * 10  # weight = seed / 10
          # parse difficulty by weight bracket
          if animal.difficulty not in scanned_levels:
            scanned_levels[animal.difficulty] = [animal.weight, animal.weight]
          if animal.weight < scanned_levels[animal.difficulty][0]:
            scanned_levels[animal.difficulty][0] = animal.weight
          if animal.weight > scanned_levels[animal.difficulty][1]:
            scanned_levels[animal.difficulty][1] = animal.weight
      except:
        pass
  return scanned_furs, scanned_levels

def process_aps2(species_key: str, filename: Path) -> None:
  scanned_levels = {}
  with filename.open() as csvfile:
    animals = csvfile.readlines()
    for animal in animals:
      try:
        animal = ApsAnimal(animal)
        if animal.species_key.lower() == species_key.lower():
          # parse difficulty by weight bracket
          if animal.difficulty not in scanned_levels:
            scanned_levels[animal.difficulty] = [animal.weight, animal.weight]
          if animal.weight < scanned_levels[animal.difficulty][0]:
            scanned_levels[animal.difficulty][0] = animal.weight
          if animal.weight > scanned_levels[animal.difficulty][1]:
            scanned_levels[animal.difficulty][1] = animal.weight
      except:
        pass
  return scanned_levels

def combine_furs(existing: dict, latest: dict) -> None:
  existing_female_furs = existing["female"] if "female" in existing else {}
  latest_female_furs = latest["female"] if "female" in latest else {}
  existing_male_furs = existing["male"] if "male" in existing else {}
  latest_male_furs = latest["male"] if "male" in latest else {}
    
  for fur, seed in latest_female_furs.items():
    fur = fur.replace(" ", "_")
    if fur not in existing_female_furs and seed != 0.0:
      print(f"New female fur: {fur} - {seed}")
      existing_female_furs[fur] = int(seed)
  for fur, seed in latest_male_furs.items():
    fur = fur.replace(" ", "_")
    if fur not in existing_male_furs and seed != 0.0:
      print(f"New male fur: {fur} - {seed}")
      existing_male_furs[fur] = int(seed)
      
  new_existing = {
    "male": existing_male_furs,
    "female": existing_female_furs
  }
  return new_existing

def combine_furs2(existing: dict, latest: dict, gender: str, last_seed: float, new_seed: float) -> None:
  existing_furs = existing[gender] if gender in existing else {}
  latest_furs = latest[gender] if gender in latest else {}

  for fur, seed in latest_furs.items():
    seed = int(seed)
    if fur not in existing_furs:
      existing_furs[fur] = range(last_seed, new_seed)
    else:
      existing_fur = existing_furs[fur]
      if existing_fur.stop == last_seed:
        existing_fur = range(existing_fur.start, seed)
      else:
        existing_furs[f'{fur}2'] = range(last_seed, new_seed)

  combined_furs = {
    "male": existing_furs if gender == "male" else existing["male"],
    "female": existing_furs if gender == "female" else existing["female"]
  }
  return combined_furs

"""
define ranges of matching fur variation seeds
{
  "fallow_deer": {
    "male": {
      "piebald": [
        [0, 19], [41, 70]
      ],
      "brown": [
        [20, 40]
      ]
    }
  }
}
"""

# def combine_stats2(existing: dict, latest: dict, gender: str) -> None:
#   existing_stats = existing[gender] if gender in existing else {}

#   for level, stats in latest.items():
#     if level not in existing_stats:
#       existing_stats[level] = stats
#     if stats[0] < existing_stats[level][0]:
#       existing_stats[level][0] = stats[0]
#     if stats[1] > existing_stats[level][1]:
#       existing_stats[level][1] = stats[1]

#   combined_stats = {
#      "male": existing_stats if gender == "male" else existing["male"],
#     "female": existing_stats if gender == "female" else existing["female"]
#   }
#   return combined_stats


def show_mouse() -> None:
  try:
      while True:
          x, y = pyautogui.position()
          positionStr = 'X: ' + str(x).rjust(4) + ' Y: ' + str(y).rjust(4)
          print(positionStr, end='')
          print('\b' * len(positionStr), end='', flush=True)
  except KeyboardInterrupt:
      print('\n')  

def click() -> None:
  pyautogui.mouseDown()
  time.sleep(0.2)
  pyautogui.mouseUp()

def doubleClick() -> None:
  pyautogui.mouseDown()
  pyautogui.mouseUp()
  pyautogui.mouseDown()
  pyautogui.mouseUp()  

def reserve_coords(line: float) -> int:
  x_pos = 200
  y_pos_base = 179
  line_pixels = 17
  y_pos = y_pos_base + (line_pixels * line)
  return (x_pos, y_pos)

def click_reserve(reserve_name: str) -> None:
  action_duration = 1
  dropdown = (450, 175)
  scrollbar_top = (450, 200)
  scrollbar_middle = (450, 250)
  scrollbar_bottom = (450, 325)
  pop_file = (200, 290)
  exit_x = (1600, 115)

  pyautogui.moveTo(dropdown, duration=action_duration)
  click()
  if reserve_name == "hirsch":
    line = 1
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "layton":
    line = 2
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "medved":
    line = 3
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "vurhonga":
    line = 4
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "parque":
    line = 5
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "yukon":
    line = 6
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "cuatro":
    line = 7
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "silver":
    line = 8
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "teawaroa":
    line = 2.5
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "rancho":
    line = 3.5
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "mississippi":
    line = 4.5
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "revontuli":
    line = 5.5
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "newengland":
    line = 6.5
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "emerald":
    line = 7.5
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()
  if reserve_name == "sundarpatan":
    line = 8.5
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line))
    click()

  pyautogui.moveTo(pop_file)
  doubleClick()
  pyautogui.moveTo(exit_x, duration=action_duration)
  click()

def load_json(file: Path) -> dict:
  try:
    data = json.load(file.open())
  except:
    data = {}
  return data

def save_json(file: Path, data: dict) -> None:
  file.write_text(json.dumps(data, indent=2))

def seed_animals(reserve_key: str) -> None:
  print()
  print(config.get_reserve_name(reserve_key))
  reserve_species = config.get_reserve(reserve_key)["species"]
  all_furs = load_json(FURS_PATH)
  all_levels = load_json(LEVELS_PATH)
  for species in reserve_species:
    aps_species = map_aps(reserve_key, species)
    print()
    print(species.upper())
    if species in all_furs:
      species_furs = all_furs[species]
    else:
      species_furs = {}
    if species in all_levels:
      species_levels = all_levels[species]
    else:
      species_levels = {}
    reserve = adf.load_reserve(reserve_key, False, False)
    species_population = populations._get_species_population(reserve_key, reserve.adf, species)
    groups = species_population.value["Groups"].value
    if not species_furs or not species_levels:
      for gender in [1, 2]:
        seed = 0
        while seed <= 15000:
          initial_seed = seed
          seed = populations.diamond_test_seed(species, groups, reserve.decompressed.data, seed, gender)
          print(f"[{initial_seed}-{seed}] {species}: {'male' if gender == 1 else 'female'}")
          reserve.decompressed.save(config.MOD_DIR_PATH, False)
          launch_aps()
          click_reserve(reserve_key)
          new_furs, new_levels = process_aps(aps_species, Path(f"scans/scan.csv"))
          if not bool(new_furs) and not bool(new_levels):
            print(f"we didn't find any animal data; probably have name wrong: {species.lower()}:{utils.unformat_key(aps_species).lower()}")
            seed = initial_seed
            continue
          species_furs = combine_furs(species_furs, new_furs)
          species_levels = combine_stats(species_levels, new_levels)
          # print(f"  {species_furs})
          # print(f"  {species_levels})
    # levels = species_levels.keys()
    max_weight = max([weight[1] for weight in species_levels.values()])
    for level, weights in species_levels.items():
      base_weight = weights[1]
      if "." in str(base_weight) and len(str(base_weight).split(".")[1]) > 1:
        continue
      if weights[1] == max_weight:
        continue
      seed = 0
      while seed <= 100:
        initial_seed = seed
        seed = populations.diamond_test_seed2(species, groups, reserve.decompressed.data, seed, base_weight)
        print(f"[{initial_seed}-{seed}] {species}: male")
        reserve.decompressed.save(config.MOD_DIR_PATH, False)
        launch_aps()
        click_reserve(reserve_key)
        new_levels = process_aps2(aps_species, Path(f"scans/scan.csv"))
        if not bool(new_levels):
          print(f"we didn't find any new level data; probably have name wrong: {species.lower()}:{utils.unformat_key(aps_species).lower()}")
          seed = initial_seed
          continue
        species_levels = combine_stats(species_levels, new_levels)
        #print(f"  {species_levels})
        print(f"  {level}: {species_levels[level]}")

    if bool(species_furs):
      print(species_furs)
      all_furs[species] = species_furs
      save_json(FURS_PATH, all_furs)
    if bool(species_levels):
      print(species_levels)
      all_levels[species] = species_levels
      save_json(LEVELS_PATH, all_levels)

"""
{
  "fallow_deer": {
    "male": {
      "piebald": range(0, 20), 0-19 inclusive
      "brown": range(20, 40)
    }
  }
}
"""

def seed_animals2(reserve_key: str, species: str) -> None:
  print()
  print(config.get_reserve_name(reserve_key))
  print()
  aps_species = map_aps(reserve_key, species)
  print(species.upper())
  reserve = adf.load_reserve(reserve_key, False, False)
  species_population = populations._get_species_population(reserve_key, reserve.adf, species)
  groups = species_population.value["Groups"].value
  species_furs = { "male": {}, "female": {} }
  for gender in [1, 2]:
    seed = 0
    while seed < 15000:
      initial_seed = seed
      seed = populations.diamond_test_seed(species, groups, reserve, seed, gender)
      print(f"[{initial_seed}-{seed}]")
      reserve.decompressed.save(config.MOD_DIR_PATH, False)
      launch_aps()
      click_reserve(reserve_key)
      new_furs = process_aps(aps_species, Path(f"scans/scan.csv"))
      species_furs = combine_furs2(species_furs, new_furs, "male" if gender == 1 else "female", initial_seed, seed)  
      print(species_furs)
      print()
  print(json.dumps(species_furs, indent=2))

def seed_animals3(reserve_key: str) -> None:
  print()
  print(config.get_reserve_name(reserve_key))
  reserve_species = config.get_reserve(reserve_key)["species"]
  for species in reserve_species:
    aps_species = map_aps(reserve_key, species)
    print()
    print(species.upper())
    reserve = adf.load_reserve(reserve_key, False, False)
    species_population = populations._get_species_population(reserve_key, reserve.adf, species)
    groups = species_population.value["Groups"].value
    for gender in [1, 2]:
      populations.diamond_test_single_seed(species, groups, reserve.decompressed.data, gender)
      reserve.decompressed.save(config.MOD_DIR_PATH, False)
      launch_aps()
      click_reserve(reserve_key)


def merge_animal_details() -> None:
  animal_details = config.ANIMALS
  furs = load_json(FURS_PATH)
  levels = load_json(LEVELS_PATH)
  for animal in furs.keys():
    if animal not in animal_details:
      animal_details[animal] = {
        "diamonds": parse_diamond_details(animal, furs, levels)
      }
    if "Great One" in levels:
      pass
      #animal_details[animal]["go"] = parse_great_one_details(animal, furs, levels)
  #sorted_animal_details = {key: animal_details[key] for key in sorted(animal_details)}
  save_json(Path(config.CONFIG_PATH / "animal_details.json"), animal_details)

def get_reserve_keys() -> list:
  return list(dict.keys(config.RESERVES))

def test_reserve(reserve_key) -> None:
  print(reserve_key)
  launch_aps()
  click_reserve(reserve_key)

def seed_reserves() -> None:
  reserves_keys = get_reserve_keys()
  for reserve in reserves_keys:
    seed_animals(reserve)

def verify_seeds(seeds: List[int]) -> None:
  reserve_name = "cuatro"
  species = "beceite_ibex" 
  reserve = adf.load_reserve(reserve_name, False, False)
  species_population = populations._get_species_population(reserve_name, reserve.adf, species)
  groups = species_population.value["Groups"].value
  populations.diamond_test_seeds(species, groups, reserve.decompressed.data, seeds)
  reserve.decompressed.save(config.MOD_DIR_PATH, False)
  print("done")

def calc_seed(furs: List[int]) -> None:
  total = sum(furs)
  per = [fur / total for fur in furs]
  for i in range(0, 100000):
    block = 100 + i    
    fur_size = [round(block * fur) for fur in per]
    current = 0
    blocks = []
    for i, size in enumerate(fur_size):    
      if i == 0:
        blocks.append((current, current+size))
        current += size + 1
      else:
        blocks.append((current, size + blocks[i-1][1]))
        current += size
    if blocks[1][0] == 2497 and blocks[1][1] == 2506:
      print(block)    
      print(blocks)

def convert_fur_float_to_int(furs: dict) -> dict:
  for fur in furs["male"]:
    furs["male"][fur] = int(furs["male"][fur])
  for fur in furs["female"]:
    furs["female"][fur] = int(furs["female"][fur])
  return furs    

def merge_furs_into_animals() -> None:
  animals = json.load(Path("apc/config/animal_details.json").open())
  furs = load_json(FURS_PATH)
  
  for animal_name, animal in animals.items():
    animal_furs = convert_fur_float_to_int(furs[animal_name])
    animal["diamonds"]["furs"] = animal_furs
  Path("apc/config/animal_details.json").write_text(json.dumps(animals, indent=2))

def fix_furs() -> None:
  animals = json.load(Path("apc/config/animal_details.json").open())
  for _, animal in animals.items():
    if isinstance(list(animal["diamonds"]["furs"]["male"].values())[0], float):
      animal["diamonds"]["furs"] = convert_fur_float_to_int(animal["diamonds"]["furs"])
  Path("apc/config/animal_details.json").write_text(json.dumps(animals, indent=2))
      
if __name__ == "__main__":
  # analyze_reserve(config.get_save_path() / "animal_population_17")
  # fix_furs()
  # seed_animals("sundarpatan")
  # launch_aps()
  
  #reserves = config.Reserve
  #for reserve in reserves:
  #  click_reserve(reserve)

  compare_fur_cnt()