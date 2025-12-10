"""
Algorithm for calculating what fur a given VisualVariationSeed will produce
Helper functions for generating VisualVariationSeeds for a given fur
Credit to xpltive/0xsthsth1337 for cracking the algorithm and sharing their code
- https://github.com/xpltive
- https://next.nexusmods.com/profile/0xSthSth1337
"""

import math
import random
import struct

from apc import config
from apc.logging_config import get_logger

logger = get_logger(__name__)


def seed_to_probability(seed: int) -> float:
    """
    Convert a seed int to a floating-point probability
    """
    converted = (((0x343FD * seed + 0x269EC3) >> 16) | 0x3F8000) << 8
    converted &= 0xFFFFFFFF  # Mask to 32-bit
    float_bytes = struct.pack("<I", converted)
    fl_probability = struct.unpack("<f", float_bytes)[0]
    return abs(fl_probability) - 1.0


def get_fur_for_seed(seed: int, species_key: str, gender: str, great_one: bool = False) -> str | None:
    """
    Attempt to calculate the `fur_key` for a given seed
    This is not always successful due to the imperfect cracked fur algorithm
    """
    if great_one:
        gender = f"great_one_{gender}"
    species_config = config.get_species(species_key)
    if not species_config:
        # logger.warning("Unable to get species data for %s", species_key)
        return None
    gender_config = species_config.get("gender", {}).get(gender, {})
    if not gender_config:
        # logger.warning("Unable to read gender data for %s - %s", species_key, gender)
        return None

    fl_probability = seed_to_probability(seed)
    if math.isnan(fl_probability) or math.isinf(fl_probability):
        # logger.debug(f"Cannot calculate probability for seed {seed} :: {gender} {species_key} >> fl_prob: {fl_probability}")
        return None
    fur_total_probability = gender_config["fur_total_probability"]
    cumulative = 0.0
    # logger.debug(f"SPECIES: {species_key}   GENDER: {gender}   TOTAL_PROB: {fur_total_probability}")
    for fur_key, fur_prob in gender_config["furs"].items():
        # logger.debug(f" FUR: {fur_key}   PROB: {fur_prob}")
        cumulative += fur_prob / fur_total_probability
        if cumulative >= fl_probability:
            return fur_key
    logger.error(f"Unable to find fur for seed {seed} >> fl_prob {fl_probability}")
    raise ValueError(f"Unable to find fur for seed {seed} >> fl_prob {fl_probability}")


def find_fur_seed(
    species_key: str,
    gender: str,
    great_one: bool = False,
    fur_key: str | None = None,
    max_attempts: int = 10_000_000,
) -> int | None:
    """
    Find a single seed that generates a valid fur or a specific fur if `fur_key` is provided.
    Raises ValueError if no match is found within `max_attempts`.
    """
    for i in range(max_attempts):
        seed = random.randint(0, 0xFFFFFFFF)
        try:
            # logger.debug(f"Generating{f' {fur_key}' if fur_key else ''} seed for {species_key} {gender}{f' {great_one}' if great_one else ''} - {i}")
            if seeded_fur_key := get_fur_for_seed(seed, species_key, gender, great_one):
                if seeded_fur_key == fur_key or fur_key is None:
                    logger.debug(f"Found seed: {seed}{f' for fur: {fur_key}' if fur_key else ''}")
                    return seed
        except ValueError as ex:
            logger.error(ex)
            continue
    msg = (
        f"Failed to generate valid fur seed for {species_key} :: {fur_key}"
        if fur_key
        else f"Failed to generate valid fur seed for {species_key}"
    )
    raise ValueError(msg)


def is_valid_fur_seed(seed: int, species_key: str, gender: str, great_one: bool = False, fur_key: str = None):
    seeded_fur_key = get_fur_for_seed(seed, species_key, gender, great_one)
    if fur_key and seeded_fur_key == fur_key:
        return True
    if fur_key is None:
        if great_one:
            gender = f"great_one_{gender}"
        gender_config = config.get_species(species_key)["gender"][gender]
        if seeded_fur_key in gender_config["furs"]:
            return True
    return False


def find_seeds_for_fur(
    fur_key: str,
    species_key: str,
    gender: str,
    great_one: bool = False,
    max_results: int = 10,
) -> list[int]:
    """
    Find up to `max_results` unique seeds that correspond with the the given `fur_key`.
    """
    found = set()
    while len(found) < max_results:
        seed = find_fur_seed(species_key, gender, great_one=great_one, fur_key=fur_key)
        if seed is None:
            break
        found.add(seed)
    return sorted(found)


def get_fur_name_for_seed(seed: int, species_key: str, gender: str, great_one: bool = False):
    """
    Attempt to calculate the `fur_key` and parse the name for a given seed
    """
    if species_key not in config.ANIMALS:
        return "???"
    fur_key = get_fur_for_seed(seed, species_key, gender, great_one=great_one)
    if fur_key:
        return config.get_fur_name(fur_key)
    return "-"


if __name__ == "__main__":
    SPECIES_KEY = "caribou"
    GENDER = "male"
    GREAT_ONE = False
    SEED = 3837140181
    CALCULATED_FUR = get_fur_for_seed(SEED, SPECIES_KEY, GENDER, great_one=GREAT_ONE)
    logger.info(
        f"Species: {SPECIES_KEY}   Gender: {GENDER}   Great One: {GREAT_ONE}  Seed: {SEED} >> Fur: {CALCULATED_FUR}"
    )
    FUR_KEY = "albino"
    CALCULATED_SEED = find_fur_seed(SPECIES_KEY, GENDER, great_one=GREAT_ONE, fur_key=FUR_KEY)
    logger.info(
        f"Species: {SPECIES_KEY}  Gender: {GENDER}  Great One: {GREAT_ONE}  Fur: {FUR_KEY} >> Seed: {CALCULATED_SEED}"
    )
