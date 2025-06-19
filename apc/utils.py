from apc.logging_config import get_logger

logger = get_logger(__name__)

import random
import re
import struct

from rich.table import Table


def list_to_table(
    data: list,
    table: Table,
) -> Table:
    for row in data:
        row = [str(x) for x in row]
        table.add_row(*row)

    return table

def random_float(low: int, high: int) -> float:
     return random.uniform(low, high)

def update_uint(data_bytes: bytearray, offset: int, new_value: int) -> None:
    try:
        new_value = int(new_value)
    except ValueError:
        logger.error(f"Value '{new_value}' cannot be cast to int")
        return
    value_bytes = new_value.to_bytes(4, byteorder='little')
    for i in range(0, len(value_bytes)):
        data_bytes[offset + i] = value_bytes[i]

def update_float(data_bytes: bytearray, offset: int, new_value: float) -> None:
    try:
        new_value = float(new_value)
    except ValueError:
        logger.error(f"Value '{new_value}' cannot be cast to float")
        return
    hex_float = struct.pack("f", new_value)
    for i in range(0, 4):
        data_bytes[offset + i] = hex_float[i]

def format_key(key: str) -> str:
  key = [s.capitalize() for s in re.split("_|-", key)]
  return " ".join(key)

def unformat_key(value: str) -> str:
  """do not use in production code"""
  parts = value.lower().split(" ")
  return "_".join(parts)