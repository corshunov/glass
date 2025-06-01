import json
from pathlib import Path


def clamp(v, low, high):
    return max(low, min(high, v))

def linear_map(v, low, high, begin, end):
    v = clamp(v, low, high)
    v = (v - low) / (high - low) * (end - begin) + begin
    return v

def load_json(path):
    with Path(path).open("r") as f:
        content = json.load(f)
    return content
