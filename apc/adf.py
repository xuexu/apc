from apc.logging_config import get_logger

logger = get_logger(__name__)

import contextlib
import random
import struct
import zlib
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from apc import config, fur_seed
from apc.adf_profile import (AdfArray, create_f32, create_u8, create_u32,
                             insert_data, read_f32, read_u8, read_u32,
                             write_value)
from deca.ff_adf import Adf, AdfValue
from deca.file import ArchiveFile


class FileNotFound(Exception):
    pass

class DecompressedAdfFile():
    def __init__(self, basename: str, filename: Path, file_header: bytearray, header: bytearray, data: bytearray) -> None:
        self.basename = basename
        self.filename = filename
        self.file_header = file_header
        self.header = header
        self.data = data
        self.org_size = len(header + data)

    def save(self, destination: Path) -> None:
        decompressed_data_bytes = self.header + self.data
        new_size = len(decompressed_data_bytes)
        if self.org_size != new_size:
          logger.debug(f"Original: {self.org_size} >> New: {new_size} :: Change: {new_size - self.org_size}")
          decompressed_size = struct.pack("I", new_size)
          self.file_header[8:12] = decompressed_size
          self.file_header[24:28] = decompressed_size
        commpressed_data_bytes = self.file_header + _compress_bytes(decompressed_data_bytes)

        adf_file = destination / self.basename
        logger.debug(f"Saving modded file to {adf_file}")
        _save_file(adf_file, commpressed_data_bytes)

class ParsedAdfFile():
    decompressed: DecompressedAdfFile
    adf: Adf

    def __init__(self, decompressed: DecompressedAdfFile, adf: Adf) -> None:
        self.decompressed = decompressed
        self.adf = adf
class LoadedReserve:
    reserve_key: str
    reserve_name: str
    popfilename: str
    filename: str
    json_config: dict
    modded: bool
    changed: bool
    parsed_adf = ParsedAdfFile
    population_description: list[list]
    species_groups: dict

    def __init__(self, reserve_key: str, modded: bool = False, parse: bool = False) -> None:
        self.reserve_key = reserve_key
        self.reserve_name = config.get_reserve_name(reserve_key)
        self.popfilename = config.get_population_file_name(reserve_key)
        self.filename = _get_file_name(reserve_key, modded)
        self.json_config = config.RESERVES[reserve_key]
        self.modded = modded
        self.changed = False  # should the file be reloaded when changing UI views?
        self.parse() if parse else None
        self.population_description = None
        self.species_groups = None

    def parse(self, txt: bool = False) -> None:
        self.parsed_adf = load_adf(self.filename, txt=False)

    # def describe_reserve(self) -> None:
    #     self.population_description, self.species_groups = describe_reserve(reserve_key, loaded_reserve.parsed_adf.adf)

    def save(self) -> None:
        self.parsed_adf.decompressed.save(config.MOD_DIR_PATH)
        self.filename = _get_file_name(self.reserve_key, mod=True)
        self.modded = True
        self.parse()

# @dataclass
# class StatWithOffset:
#   value: any
#   offset: int

class AdfAnimal:
    def __init__(self, adf_value: AdfValue, species_key: str, reserve_key: str = "") -> None:
      self.adf = adf_value
      self.species_key: str = species_key
      self.reserve_key: str = reserve_key
      self._parse_details()

    def _parse_details(self) -> None:
      self.gender = "male" if self.adf.value["Gender"].value == 1 else "female"
      self.weight = float(self.adf.value["Weight"].value)
      self.score = float(self.adf.value["Score"].value)
      self.visual_seed = int(self.adf.value["VisualVariationSeed"].value)
      self.id = int(self.adf.value["Id"].value)
      self.map_position_x = float(self.adf.value["MapPosition"].value["X"].value)
      self.map_position_y = float(self.adf.value["MapPosition"].value["Y"].value)
      self.gender_offset = int(self.adf.value["Gender"].data_offset)
      self.weight_offset = int(self.adf.value["Weight"].data_offset)
      self.score_offset = int(self.adf.value["Score"].data_offset)
      self.visual_seed_offset = int(self.adf.value["VisualVariationSeed"].data_offset)
      self.id_offset = int(self.adf.value["Id"].data_offset)
      self.map_position_x_offset = float(self.adf.value["MapPosition"].value["X"].data_offset)
      self.map_position_y_offset = float(self.adf.value["MapPosition"].value["Y"].data_offset)
      self._parse_great_one()
      self._parse_is_scripted()
      self._parse_trophy()
      fur_key = fur_seed.get_fur_for_seed(self.visual_seed, self.species_key, self.gender, self.great_one)
      self.fur_key = fur_key if fur_key else "unknown"
      if fur_key:
        self.fur_name = fur_seed.get_fur_name_for_seed(self.visual_seed, self.species_key, self.gender, great_one=self.great_one)
      else:
        self.fur_name = "unknown"
      self.offset = self.gender_offset  # gender is the first byte of the animal data

    def _parse_great_one(self) -> None:
      if "IsGreatOne" in self.adf.value:
        self.great_one = self.adf.value["IsGreatOne"].value == 1
        self.great_one_offset = int(self.adf.value["IsGreatOne"].data_offset)
        return
      if "FeatureModifiers" in self.adf.value:
        self.great_one = self.adf.value["FeatureModifiers"].value["Flags"].value == 1
        self.great_one_offset = int(self.adf.value["FeatureModifiers"].value["Flags"].data_offset)
        return
      raise ValueError

    def _parse_is_scripted(self) -> None:
      if "IsScripted" in self.adf.value:
        self.scripted = self.adf.value["IsScripted"].value == 1
        self.scripted_offset = int(self.adf.value["IsScripted"].data_offset)
      else:
        self.scripted = False
        self.scripted_offset = self.great_one_offset + 1

    def _parse_trophy(self) -> None:
      if self.great_one:
        self.trophy = config.GREATONE
        return
      species_config = config.get_species(self.species_key)
      if species_config is None:
        self.trophy = config.UNKNOWN
        return
      trophy_config = species_config.get("trophy", {})
      for level in ["bronze", "silver", "gold", "diamond"]:
        data = trophy_config.get(level)
        if data and data["score_low"] <= self.score <= data["score_high"]:
            self.trophy = getattr(config, level.upper())
            return
      self.trophy = config.NONE

    def __repr__(self) -> str:
      return str({
        "species": self.species_key,
        "gender": self.gender,
        "weight": self.weight,
        "score": self.score,
        "great_one": self.great_one,
        "seed": self.visual_seed,
        "offset": self.offset
      })

    def to_bytes(self) -> bytearray:
      _ = create_u8(0, small=True)
      gender = create_u8(1 if self.gender == "male" else 2, small=True)
      weight = create_f32(self.weight)
      score = create_f32(self.score)
      is_great_one = create_u8(int(self.great_one), small=True)
      is_scripted = create_u8(int(self.scripted), small=True)
      visual_variation_seed = create_u32(self.visual_seed)
      id = create_u32(self.id)
      map_position_x = create_f32(self.map_position_x)
      map_position_y = create_f32(self.map_position_y)
      animal_bytes = gender+_+_+_+weight+score+is_great_one+is_scripted+_+_+visual_variation_seed+id+map_position_x+map_position_y
      return animal_bytes

    def clone(self) -> 'AdfAnimal':
      logger.debug(f"Cloning animal: {self.species_key} {self.gender} @ {self.reserve_key}")
      cloned_adf = deepcopy(self.adf)
      clone = AdfAnimal(cloned_adf, self.species_key, self.reserve_key)
      return clone

    def _randomize(self, gender: str = None, fur_key: str = None, keep_great_one: bool = False) -> None:
      '''
      Generate random gender, weight, score, and fur seed.
      Does not randomly generate Great Ones due to unknown in-game spawn chance.
      Options to specify gender, fur_key, and keep Great One status.
      fur_key == "copy" will attempt to generate a new seed for the same fur if it's valid for the new gender
      Great One status will be removed if gender cannot be a Great One
      '''
      logger.debug(self)
      great_one_gender = config.get_great_one_gender(self.species_key)
      great_one = (
          keep_great_one
          and self.great_one
          and great_one_gender is not None
      )
      if great_one and gender is not None and gender not in (great_one_gender, "both"):
          great_one = False  # Don't keep Great One if we're specifying an invalid gender
          fur_key = None
      if gender is None:
          if great_one and great_one_gender != "both":
              gender = great_one_gender
          else:
              gender = random.choice(("male", "female"))
      gender_key = f"great_one_{gender}" if great_one else gender
      gender_config = config.get_species(self.species_key)["gender"][gender_key]

      new_weight, new_score = config.generate_weight_and_score(gender_config)

      if fur_key == "copy":
        fur_key = fur_seed.get_fur_for_seed(self.visual_seed, self.species_key, self.gender, self.great_one)
      if fur_key not in config.get_furs(self.species_key, gender, great_one):
        # fur_key is invalid for new gender/Great One status or can't be parsed from seed
        fur_key = None
      new_fur_seed = fur_seed.find_fur_seed(self.species_key, gender, great_one=great_one, fur_key=fur_key)

      self.adf.value["Gender"].value = 1 if gender == "male" else 2
      self.adf.value["Weight"].value = new_weight
      self.adf.value["Score"].value = new_score
      if "IsGreatOne" in self.adf.value:
        self.adf.value["IsGreatOne"].value = 1 if great_one else 0
      if "FeatureModifiers" in self.adf.value:
        self.adf.value["FeatureModifiers"].value["Flags"].value = 1 if great_one else 0
      if "IsScripted" in self.adf.value:
        self.adf.value["IsScripted"].value = 0
      self.adf.value["VisualVariationSeed"].value = new_fur_seed
      self.adf.value["Id"].value = 0
      self._parse_details()
      logger.debug(f"Cloned animal: {self}")

def _get_file_name(reserve_key: str, mod: bool = False) -> Path:
    save_path = config.MOD_DIR_PATH if mod else config.get_save_path()
    if save_path is None:
        raise FileNotFound(config.CONFIGURE_GAME_PATH_ERROR)
    filename = save_path / config.get_population_file_name(reserve_key)
    if not filename.exists():
        raise FileNotFound(f"{config.FILE_NOT_FOUND}: {filename}")
    return filename

def _read_file(filename: Path):
    logger.debug(f"Reading {filename}")
    return filename.read_bytes()

def _decompress_bytes(data_bytes: bytearray) -> bytearray:
    decompress = zlib.decompressobj()
    decompressed = decompress.decompress(data_bytes)
    decompressed = decompressed + decompress.flush()
    return decompressed

def _compress_bytes(data_bytes: bytearray) -> bytearray:
    compress = zlib.compressobj()
    compressed = compress.compress(data_bytes)
    compressed = compressed + compress.flush()
    return compressed

def _save_file(filename: Path, data_bytes: bytearray):
    Path(filename.parent).mkdir(exist_ok=True)
    filename.write_bytes(data_bytes)
    logger.debug(f"Saved {filename}")

def _parse_adf_file(filename: Path, txt: bool = False, suffix: str = None) -> Adf:
    obj = Adf()
    with ArchiveFile(open(filename, 'rb')) as f:
        with contextlib.redirect_stdout(None):
            obj.deserialize(f)
    if txt or suffix:
      content = obj.dump_to_string()
      suffix = f"_{suffix}.txt" if suffix else ".txt"
      txt_filename = config.APP_DIR_PATH / f".working/{filename.name}{suffix}"
      _save_file(txt_filename, bytearray(content, 'utf-8'))
    return obj

def _decompress_adf_file(filename: Path) -> DecompressedAdfFile:
    # read entire adf file
    data_bytes = _read_file(filename)
    data_bytes = bytearray(data_bytes)

    # split out header
    header = data_bytes[0:32]
    data_bytes = data_bytes[32:]

    # decompress data
    decompressed_data_bytes = _decompress_bytes(data_bytes)
    decompressed_data_bytes = bytearray(decompressed_data_bytes)

    # split out compression header
    decompressed_header = decompressed_data_bytes[0:5]
    decompressed_data_bytes = decompressed_data_bytes[5:]

    # save uncompressed adf data to file
    parsed_basename = filename.name
    adf_file = config.APP_DIR_PATH / f".working/{parsed_basename}_sliced"
    _save_file(adf_file, decompressed_data_bytes)

    return DecompressedAdfFile(
        parsed_basename,
        adf_file,
        header,
        decompressed_header,
        decompressed_data_bytes
    )

def parse_adf(filename: Path, txt: bool = False, suffix: str = None) -> Adf:
    logger.debug(f"Parsing {filename}")
    return _parse_adf_file(filename, txt=txt, suffix=suffix)

def load_adf(filename: Path, txt: bool = False, suffix: str = None) -> ParsedAdfFile:
    data = _decompress_adf_file(filename)
    adf = parse_adf(data.filename, txt=txt, suffix=suffix)
    return ParsedAdfFile(data, adf)

def load_reserve(reserve_key: str, mod: bool = False, txt: bool = False, suffix: str = None) -> ParsedAdfFile:
    filename = _get_file_name(reserve_key, mod)
    logger.debug(f"[bright_blue]{filename}[/bright_blue]")
    return load_adf(filename, txt=txt, suffix=suffix)

def update_offsets(value, changed_size: int, reserve_bytes: bytearray = None, offset_to_check: int = 0) -> None:
    if isinstance(value, AdfValue):
        update_value_offsets(value, changed_size, reserve_bytes=reserve_bytes, offset_to_check=offset_to_check)
    elif isinstance(value, dict):
        for obj in value.values():
            update_offsets(obj, changed_size, reserve_bytes=reserve_bytes, offset_to_check=offset_to_check)
    elif isinstance(value, list):
        for obj in value:
            update_offsets(obj, changed_size, reserve_bytes=reserve_bytes, offset_to_check=offset_to_check)

def update_value_offsets(value: AdfValue, changed_size: int, reserve_bytes: bytearray = None, offset_to_check: int = 0) -> None:
    '''
    Adjust offsets of all values located later in the file than `offset_to_check`
    Write modified info_offset values to the bytearray if it is provided
    '''
    if value.data_offset > offset_to_check:
        if reserve_bytes and value.data_offset != value.info_offset:
            offset = value.info_offset
            current = read_u32(reserve_bytes[offset:offset+4])
            # logger.debug(f"{offset} :: {current} >> {current+changed_size}")  # this is absurdly verbose
            write_value(reserve_bytes, create_u32(max(0, current + changed_size)), offset)
        value.data_offset = max(0, int(value.data_offset) + changed_size)
    if value.info_offset > offset_to_check:
        value.info_offset = max(0, int(value.info_offset) + changed_size)
    if value.data_offset != offset_to_check:
        update_offsets(value.value, changed_size, reserve_bytes=reserve_bytes, offset_to_check=offset_to_check)

def _update_non_instance_offsets(loaded_reserve: LoadedReserve, changed_size: int) -> list[dict]:
    extracted_adf = loaded_reserve.parsed_adf.adf
    reserve_bytes = loaded_reserve.parsed_adf.decompressed.data
    logger.debug(f"  Updating file header offsets by {changed_size}")
    offsets_and_values = [
        (extracted_adf.header_profile["instance_offset_offset"], extracted_adf.instance_offset),
        (extracted_adf.header_profile["typedef_offset_offset"], extracted_adf.typedef_offset),
        (extracted_adf.header_profile["stringhash_offset_offset"], extracted_adf.stringhash_offset),
        (extracted_adf.header_profile["nametable_offset_offset"], extracted_adf.nametable_offset),
        (extracted_adf.header_profile["total_size_offset"], extracted_adf.total_size),
        (extracted_adf.table_instance[0].header_profile["size_offset"], extracted_adf.table_instance[0].size),
    ]

    # Update values in the bytearray
    for offset, value in offsets_and_values:
        if value > 0:  # do not modify offsets of 0
            new_value = max(value + changed_size, 0)  # do not let offsets go below 0
            write_value(reserve_bytes, create_u32(new_value), offset)

    # Update values in the extracted ADF
    extracted_adf.instance_offset += changed_size
    extracted_adf.typedef_offset += changed_size
    if extracted_adf.stringhash_offset:  # ADF that extracts to XLSX don't have `stringhash_offset`
        extracted_adf.stringhash_offset += changed_size
    extracted_adf.nametable_offset += changed_size
    extracted_adf.total_size += changed_size
    extracted_adf.table_instance[0].size += changed_size
    # Update offsets in header_profile
    for k, v in extracted_adf.table_instance[0].header_profile.items():
        extracted_adf.table_instance[0].header_profile[k] = v + changed_size

def _update_instance_offsets(loaded_reserve: LoadedReserve, changed_size: int, offset_to_check: int) -> list[dict]:
    logger.debug(f"Updating all offsets larger than {offset_to_check}")
    reserve_bytes = loaded_reserve.parsed_adf.decompressed.data
    update_offsets(loaded_reserve.parsed_adf.adf.table_instance_full_values[0], changed_size, reserve_bytes=reserve_bytes, offset_to_check=offset_to_check)

def _insert_animal(loaded_reserve: LoadedReserve, group: AdfValue, animal: AdfAnimal) -> None:
  reserve_bytes = loaded_reserve.parsed_adf.decompressed.data
  # read Animals array length in reserve_bytes and update by 1
  group_animals: AdfValue = group.value["Animals"]
  array_length_offset = group_animals.info_offset + 8
  array_length = read_u32(reserve_bytes[array_length_offset:array_length_offset+4])
  logger.debug(f"Updating array length at offset {array_length_offset} from {array_length} to {array_length+1}")
  write_value(reserve_bytes, create_u32(array_length + 1), array_length_offset)
  # write animal bytes into reserve_bytes
  animal_bytes = animal.to_bytes()
  logger.debug(f"Writing animal data at offset {animal.offset}: {animal_bytes}")
  insert_data(reserve_bytes, animal_bytes, animal.offset)
  write_value(reserve_bytes, create_u32(3), 4)  # ADFv3 to prevent crash on load
  # insert animal into Group list in extracted ADF
  logger.debug(f"Inserting animal into ADF >> Species: {animal.species_key}")
  group_animals.value.insert(0, animal.adf)

def _remove_animal(loaded_reserve: LoadedReserve, group: AdfValue, animal: AdfAnimal) -> None:
  reserve_bytes = loaded_reserve.parsed_adf.decompressed.data
  # read Animals array length in reserve_bytes and decrease by 1
  group_animals: AdfValue = group.value["Animals"]
  array_length_offset = group_animals.info_offset + 8
  array_length = read_u32(reserve_bytes[array_length_offset:array_length_offset+4])
  logger.debug(f"Updating array length at offset {array_length_offset} from {array_length} to {array_length-1}")
  write_value(reserve_bytes, create_u32(array_length - 1), array_length_offset)
  # delete animal bytes from reserve_bytes
  animal_bytes = animal.to_bytes()
  if reserve_bytes[animal.offset:animal.offset+len(animal_bytes)] != animal_bytes:
    raise ValueError("Encountered an error removing the animal. Try again.")
  logger.debug(f"Deleting animal data at offset {animal.offset}: {animal_bytes}")
  logger.debug(f"sanity check for data @ offset {animal.offset}: {reserve_bytes[animal.offset:animal.offset+len(animal_bytes)]}")
  del reserve_bytes[animal.offset:animal.offset+len(animal_bytes)]
  write_value(reserve_bytes, create_u32(3), 4)  # ADFv3 to prevent crash on load
  # insert animal into Group list in extracted ADF
  logger.debug(f"Deleting animal from ADF >> Species: {animal.species_key}")
  del group_animals.value[0]

def add_animal_to_group(loaded_reserve: LoadedReserve, group: AdfValue, species_key: str, gender: str) -> None:
    # Clone the first animal in the group
    adf_to_clone = group.value["Animals"].value[0]
    animal_to_clone = AdfAnimal(adf_to_clone, species_key, loaded_reserve.reserve_key)
    clone = animal_to_clone.clone()
    # Randomize the cloned animal's stats
    clone._randomize(gender=gender)
    added_size = len(clone.to_bytes())
    # Update file header offsets and offsets of everything located after the cloned animal in the file
    _update_non_instance_offsets(loaded_reserve, added_size)
    _update_instance_offsets(loaded_reserve, added_size, clone.offset)
    # Insert the cloned animal at the beginning of the group
    _insert_animal(loaded_reserve, group, clone)

def remove_animal_from_group(loaded_reserve: LoadedReserve, group: AdfValue, species_key: str, gender: str) -> bool:
    # Select the first eligible animal in the group to remove
    for animal in group.value["Animals"].value:
      animal_to_remove = AdfAnimal(animal, species_key, loaded_reserve.reserve_key)
      if animal_to_remove.gender != gender:
        continue
      removed_size = -len(animal_to_remove.to_bytes())
      # Update file header offsets and offsets of everything located after the cloned animal in the file
      _update_non_instance_offsets(loaded_reserve, removed_size)
      _update_instance_offsets(loaded_reserve, removed_size, animal_to_remove.offset)
      # Delete the animal at the beginning of the group
      _remove_animal(loaded_reserve, group, animal_to_remove)
      return True
    # Return False if we did not find an eligible animal to remove
    return False
