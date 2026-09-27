#!/usr/bin/env python3
"""Basic output-shape check. Use the organizers' evaluate.py for official validation."""
import argparse
import json
from pathlib import Path

CLASSES = {
    "accident", "near_miss", "red_light", "wrong_way", "illegal_u_turn",
    "stopped_vehicle", "jaywalking", "failure_to_yield", "illegal_turn",
    "solid_line_crossing", "stop_line", "congestion", "road_obstacle", "fire_smoke",
}


def validate(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data.get("team"), str)
    assert isinstance(data.get("videos"), dict)
    for name, video in data["videos"].items():
        assert isinstance(name, str) and isinstance(video.get("events"), list)
        assert isinstance(video.get("risk"), list)
        for event in video["events"]:
            assert len(event) == 3 and isinstance(event[0], (float, int)) and isinstance(event[1], (float, int))
            assert 0 <= event[0] < event[1] and event[2] in CLASSES, (name, event)
        for point in video["risk"]:
            assert len(point) == 2 and 0 <= float(point[1]) <= 1, (name, point)
    print(f"Basic format OK: {len(data['videos'])} videos")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions")
    validate(Path(parser.parse_args().predictions))
