"""Traffic-event baseline: local YOLO detector plus fixed-camera rules."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import random
import threading
from typing import Any

import numpy as np

CLASSES = [
    "accident", "near_miss", "red_light", "wrong_way", "illegal_u_turn",
    "stopped_vehicle", "jaywalking", "failure_to_yield", "illegal_turn",
    "solid_line_crossing", "stop_line", "congestion", "road_obstacle", "fire_smoke",
]
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "camera.json"
WEIGHTS_PATH = ROOT / "weights" / "yolo11n.pt"
VEHICLES = {"car", "motorcycle", "bus", "truck", "bicycle"}
MOVERS = VEHICLES | {"person"}
RISK_HORIZON_SEC = 5.0
_INFERENCE_LOCK = threading.Lock()


@dataclass
class Detection:
    box: tuple[float, float, float, float]
    class_id: int
    name: str
    confidence: float

    @property
    def foot(self):
        return ((self.box[0] + self.box[2]) / 2, self.box[3])

    @property
    def center(self):
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)

    @property
    def width(self):
        return max(1.0, self.box[2] - self.box[0])


@dataclass
class Track:
    id: int
    name: str
    class_id: int
    box: tuple[float, float, float, float]
    first: float
    last: float
    stationary_speed: float = 3.0
    points: deque = field(default_factory=lambda: deque(maxlen=64))
    speeds: deque = field(default_factory=lambda: deque(maxlen=24))
    stationary_since: float | None = None
    speed: float = 0.0
    prior_speed: float = 0.0

    def push(self, detection: Detection, t: float):
        self.prior_speed = self.speed
        self.box = detection.box
        self.last = t
        x, y = detection.foot
        self.points.append((t, x, y))
        self.speed = math.hypot(*self.velocity)
        self.speeds.append((t, self.speed))
        if self.speed <= self.stationary_speed:
            if self.stationary_since is None:
                self.stationary_since = t
        else:
            self.stationary_since = None

    @property
    def foot(self):
        return ((self.box[0] + self.box[2]) / 2, self.box[3])

    @property
    def center(self):
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)

    @property
    def width(self):
        return max(1.0, self.box[2] - self.box[0])

    @property
    def velocity(self):
        if len(self.points) < 2:
            return (0.0, 0.0)
        # Least-squares velocity over past observations reduces detector jitter.
        recent = [p for p in self.points if self.last - p[0] <= .55]
        if len(recent) < 2:
            recent = list(self.points)[-2:]
        mean_t = sum(p[0] for p in recent) / len(recent)
        denominator = sum((p[0] - mean_t) ** 2 for p in recent)
        if denominator < 1e-8:
            return (0.0, 0.0)
        return tuple(sum((p[0] - mean_t) * p[k] for p in recent) / denominator
                     for k in (1, 2))

    @property
    def mature(self):
        return len(self.points) >= 4 and self.last - self.points[0][0] >= .35

    @property
    def braking(self):
        recent = [s for t, s in self.speeds if .15 <= self.last - t <= .9]
        peak = max(recent, default=0.0)
        return self.mature and peak > max(10.0, self.width * .15) and self.speed < .5 * peak

    @property
    def turn_degrees(self):
        recent = [p for p in self.points if self.last - p[0] <= 2.0]
        if len(recent) < 6 or recent[-1][0] - recent[0][0] < .6:
            return 0.0
        n = max(1, len(recent) // 3)
        _, ax, ay = recent[0]
        _, bx, by = recent[n]
        _, cx, cy = recent[-n-1]
        _, dx, dy = recent[-1]
        u, v = (bx - ax, by - ay), (dx - cx, dy - cy)
        if min(math.hypot(*u), math.hypot(*v)) < max(3, .1 * self.width):
            return 0.0
        return math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    ab = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / max(1e-6, aa + ab - inter)


class Tracker:
    """Deterministic nearest-centroid tracker for sparse frame sampling."""
    def __init__(self, stationary_speed: float = 3.0):
        self.items: dict[int, Track] = {}
        self.next_id = 1
        self.stationary_speed = stationary_speed

    def update(self, detections: list[Detection], t: float):
        pairs = []
        for di, d in enumerate(detections):
            for tid, tr in self.items.items():
                if tr.name != d.name or t - tr.last > 1.5:
                    continue
                scale = max(tr.width, d.width)
                vx, vy = tr.velocity
                dt = min(.5, max(0.0, t - tr.last))
                predicted = (tr.foot[0] + vx * dt, tr.foot[1] + vy * dt)
                distance = _dist(predicted, d.foot)
                overlap = _iou(tr.box, d.box)
                if distance <= max(30, 1.2 * scale + 35 * (t - tr.last)) or overlap > 0.08:
                    pairs.append((distance - overlap * 50, di, tid))
        used_d, used_t = set(), set()
        for _, di, tid in sorted(pairs):
            if di in used_d or tid in used_t:
                continue
            self.items[tid].push(detections[di], t)
            used_d.add(di)
            used_t.add(tid)
        for di, d in enumerate(detections):
            if di in used_d:
                continue
            tr = Track(self.next_id, d.name, d.class_id, d.box, t, t, self.stationary_speed)
            tr.push(d, t)
            self.items[self.next_id] = tr
            self.next_id += 1
        self.items = {i: tr for i, tr in self.items.items() if t - tr.last <= 2}
        # Stale boxes are not new observations and must not generate events.
        return [tr for tr in self.items.values() if abs(t - tr.last) < 1e-6]


class Scene:
    def __init__(self, width: int, height: int):
        path = Path(os.environ.get("TRAFFIC_CONFIG", CONFIG_PATH))
        try:
            self.cfg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.cfg = {}
        self.width, self.height = width, height

    def point(self, p):
        if not p or len(p) != 2:
            return None
        return float(p[0]) * self.width, float(p[1]) * self.height

    def poly(self, name):
        return [self.point(p) for p in (self.cfg.get(name) or [])]

    def polys(self, name):
        return [[self.point(p) for p in poly] for poly in (self.cfg.get(name) or [])]

    @staticmethod
    def contains(point, polygon):
        if not polygon or len(polygon) < 3:
            return False
        x, y = point
        inside, j = False, len(polygon) - 1
        for i, (xi, yi) in enumerate(polygon):
            xj, yj = polygon[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                inside = not inside
            j = i
        return inside

    def line(self, name):
        vals = self.cfg.get(name)
        return tuple(self.point(p) for p in vals) if vals and len(vals) == 2 else None

    def line_from(self, vals):
        return tuple(self.point(p) for p in vals) if vals and len(vals) == 2 else None

    def red(self, frame):
        roi = self.cfg.get("signal_roi")
        if not roi:
            return False
        try:
            import cv2
            x1, y1, x2, y2 = [int(v * n) for v, n in zip(roi, [self.width, self.height, self.width, self.height])]
            crop = frame[max(0, y1):max(y1 + 1, y2), max(0, x1):max(x1 + 1, x2)]
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            mask = ((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 90) & (hsv[:, :, 2] > 120)
            return bool(mask.size and mask.mean() >= float(self.cfg.get("red_signal_pixel_fraction", 0.015)))
        except Exception:
            return False


class Analyzer:
    def __init__(self, width: int, height: int):
        self.scene = Scene(width, height)
        self.tracker = Tracker(float(self.scene.cfg.get("stationary_speed_px_s", 3.0)))
        self.active: dict[tuple[str, str], list[float]] = {}
        self.events: list[list[Any]] = []
        self.previous: dict[int, tuple[float, tuple[float, float]]] = {}
        self.contact: defaultdict[tuple[int, int], int] = defaultdict(int)
        self.pair_history: dict[tuple[int, int], deque] = {}
        self.condition_since: dict[tuple[str, str], float] = {}
        self.congestion_since: dict[int, float] = {}
        self.red_until: dict[int, float] = {}
        self.red_start: dict[int, float] = {}
        self._one_shot: list[tuple[str, str, float]] = []
        self.last_risk = 0.0
        self.last_time: float | None = None
        self.sample_interval = .12

    def process(self, frame, t, detections):
        t = float(t)
        if self.last_time is not None and t > self.last_time:
            self.sample_interval = min(.5, t - self.last_time)
        self.last_time = t
        tracks = self.tracker.update(detections, t)
        scene = self.scene
        road, intersection = scene.poly("road_polygon"), scene.poly("intersection_polygon")
        crossings, lanes = scene.polys("crosswalk_polygons"), scene.polys("lanes")
        red = scene.red(frame)
        candidates: list[tuple[str, str, float]] = []
        vehicles = [tr for tr in tracks if tr.name in VEHICLES]
        people = [tr for tr in tracks if tr.name == "person"]
        others = [tr for tr in tracks if tr.name not in MOVERS]
        risk = 0.01
        self._line_crossings(tracks, t, red, scene)

        # Motion direction and stopped vehicles.
        direction = scene.cfg.get("road_direction")
        if direction:
            dx, dy = float(direction[0]), float(direction[1])
            norm = math.hypot(dx, dy) or 1
            dx, dy = dx / norm, dy / norm
            for tr in vehicles:
                vx, vy = tr.velocity
                if tr.mature and scene.contains(tr.foot, road) and vx * dx + vy * dy < -float(scene.cfg.get("wrong_way_speed_px_s", 8)):
                    candidates.append(("wrong_way", f"v:{tr.id}", t))
        for tr in vehicles:
            queued = any(scene.contains(tr.foot, p) for p in scene.polys("queue_polygons"))
            stationary = scene.contains(tr.foot, road) and tr.speed <= tr.stationary_speed and not queued
            since = self._condition("stopped_vehicle", f"v:{tr.id}", stationary, t)
            if since is not None and t - since >= 10:
                candidates.append(("stopped_vehicle", f"v:{tr.id}", since))
            if tr.mature and red and self._past_line(tr.foot) and tr.speed <= tr.stationary_speed:
                candidates.append(("stop_line", f"v:{tr.id}", t))
            if self.red_until.get(tr.id, -1) >= t and scene.contains(tr.foot, intersection):
                candidates.append(("red_light", f"v:{tr.id}", self.red_start.get(tr.id, t)))
            turn = tr.turn_degrees
            if scene.contains(tr.foot, intersection) and abs(turn) >= 35:
                name = "right" if turn > 0 else "left"
                if abs(turn) >= 135 and not scene.cfg.get("u_turn_allowed", False):
                    candidates.append(("illegal_u_turn", f"v:{tr.id}", max(tr.first, t - 0.8)))
                elif name in (scene.cfg.get("prohibited_turns") or []) and abs(turn) < 135:
                    candidates.append(("illegal_turn", f"v:{tr.id}", max(tr.first, t - 0.8)))

        # Pedestrians in the carriageway and vehicles inside marked crossings.
        for person in people:
            on_road = scene.contains(person.foot, road)
            on_crossing = any(scene.contains(person.foot, p) for p in crossings)
            if on_road and not on_crossing:
                candidates.append(("jaywalking", f"p:{person.id}", t))
            if on_crossing:
                for vehicle in vehicles:
                    same_crossing = any(scene.contains(vehicle.foot, p) and scene.contains(person.foot, p) for p in crossings)
                    if vehicle.mature and vehicle.speed > vehicle.stationary_speed and same_crossing:
                        candidates.append(("failure_to_yield", f"y:{person.id}:{vehicle.id}", t))

        # Contact, near miss and time-to-collision cues.
        road_users = vehicles + people
        live_pairs = set()
        for i, a in enumerate(road_users):
            for b in road_users[i + 1:]:
                if (a.name == b.name == "person") or not (a.mature and b.mature):
                    continue
                pair = tuple(sorted((a.id, b.id)))
                live_pairs.add(pair)
                overlap = _iou(a.box, b.box)
                distance = _dist(a.foot, b.foot)
                history = self.pair_history.setdefault(pair, deque(maxlen=16))
                closing = any(.1 <= t - pt <= .8 and pd - distance > max(3, .06 * (a.width + b.width))
                              for pt, pd in history)
                history.append((t, distance))
                abrupt = a.braking or b.braking
                close = distance < max(20, .65 * (a.width + b.width))
                if overlap >= .15 and close:
                    self.contact[pair] += 1
                else:
                    self.contact[pair] = 0
                if closing and abrupt and self.contact[pair] >= 2:
                    candidates.append(("accident", f"pair:{pair}", max(a.first, b.first, t - .4)))
                elif closing and close and overlap < .05 and abrupt:
                    candidates.append(("near_miss", f"pair:{pair}", max(a.first, b.first, t - .4)))
                # Part B is prospective: retrospective event flags do not raise it.
                risk = max(risk, self._ttc(a, b))
        self.pair_history = {p: h for p, h in self.pair_history.items() if p in live_pairs}
        self.contact = defaultdict(int, {p: n for p, n in self.contact.items() if p in live_pairs})

        # Queue congestion: configure each direction's lane polygon.
        groups = scene.cfg.get("congestion_lane_groups") or [list(range(len(lanes)))]
        for idx, group in enumerate(groups):
            per_lane = [[v for v in vehicles if scene.contains(v.foot, lanes[j])]
                        for j in group if isinstance(j, int) and 0 <= j < len(lanes)]
            occupants = {v.id: v for values in per_lane for v in values}.values()
            slow = (bool(per_lane) and all(per_lane) and
                    len(occupants) >= int(scene.cfg.get("congestion_min_vehicles", 3)) and
                    all(sum(v.speed for v in values) / len(values) <= float(scene.cfg.get("congestion_speed_px_s", 4))
                        for values in per_lane))
            if slow:
                self.congestion_since.setdefault(idx, t)
                if t - self.congestion_since[idx] >= 5:
                    candidates.append(("congestion", f"lane:{idx}", self.congestion_since[idx]))
            else:
                self.congestion_since.pop(idx, None)

        # Static non-vehicle objects and optional custom fire/smoke classes.
        obstacle_names = set(scene.cfg.get("obstacle_class_names") or [])
        for tr in others:
            stationary = tr.name in obstacle_names and scene.contains(tr.foot, road) and tr.speed <= tr.stationary_speed
            since = self._condition("road_obstacle", f"o:{tr.id}", stationary, t)
            if since is not None and t - since >= 3:
                candidates.append(("road_obstacle", f"o:{tr.id}", since))
            if tr.name.lower() in {"fire", "smoke"}:
                candidates.append(("fire_smoke", f"fire:{tr.id}", t))

        self._update_events(t, candidates)
        live_ids = set(self.tracker.items)
        self.previous = {i: p for i, p in self.previous.items() if i in live_ids}
        self.red_until = {i: end for i, end in self.red_until.items() if i in live_ids and end >= t}
        self.red_start = {i: start for i, start in self.red_start.items() if i in self.red_until}
        observed_keys = {f"v:{tr.id}" for tr in vehicles} | {f"o:{tr.id}" for tr in others}
        self.condition_since = {key: start for key, start in self.condition_since.items() if key[1] in observed_keys}
        self.last_risk = float(np.clip(risk, 0, 1))
        return self.last_risk

    def _condition(self, label, key, flag, t):
        identity = (label, key)
        if flag:
            return self.condition_since.setdefault(identity, t)
        self.condition_since.pop(identity, None)
        return None

    def _past_line(self, point):
        line, direction = self.scene.line("stop_line"), self.scene.cfg.get("intersection_direction")
        if not line or not direction:
            return False
        mid = ((line[0][0] + line[1][0]) / 2, (line[0][1] + line[1][1]) / 2)
        return (point[0] - mid[0]) * float(direction[0]) + (point[1] - mid[1]) * float(direction[1]) > 0

    def _line_crossings(self, tracks, t, red, scene):
        stop_line = scene.line("stop_line")
        for tr in tracks:
            prior = self.previous.get(tr.id)
            if prior and tr.name in VEHICLES:
                if stop_line and red and not self._past_line(prior[1]) and self._past_line(tr.foot) and _crosses(prior[1], tr.foot, stop_line):
                    self.red_until[tr.id] = t + 3
                    self.red_start[tr.id] = prior[0]
                for values in (scene.cfg.get("solid_lines") or []):
                    line = scene.line_from(values)
                    if line and _crosses(prior[1], tr.foot, line):
                        self._one_shot.append(("solid_line_crossing", f"v:{tr.id}", prior[0]))
            self.previous[tr.id] = (t, tr.foot)

    def _update_events(self, t, candidates):
        # One-shot crossing candidates are added once and expire after the merge gap.
        candidates = list(candidates) + getattr(self, "_one_shot", [])
        self._one_shot = []
        seen = set()
        for label, key, start_hint in candidates:
            identity = (label, key)
            seen.add(identity)
            if identity not in self.active:
                self.active[identity] = [min(t, start_hint), t]
            else:
                self.active[identity][1] = t
        for identity, state in list(self.active.items()):
            if identity not in seen and t - state[1] >= .6:
                self._close(identity, t)

    def _close(self, identity, end):
        start, last = self.active.pop(identity)
        # Debounce controls merging, not event end: don't label the quiet gap.
        end = min(end, last + self.sample_interval)
        end = max(end, start + .01)
        instantaneous = {"accident", "near_miss", "red_light", "illegal_turn", "illegal_u_turn", "solid_line_crossing"}
        if identity[0] not in instantaneous and end - start < .35:
            return
        self.events.append([float(max(0, start)), float(end), identity[0]])

    @staticmethod
    def _ttc(a, b):
        if not (a.mature and b.mature):
            return 0.0
        rx, ry = b.foot[0] - a.foot[0], b.foot[1] - a.foot[1]
        avx, avy = a.velocity
        bvx, bvy = b.velocity
        vx, vy = bvx - avx, bvy - avy
        vv = vx * vx + vy * vy
        scale = max(12, .45 * (a.width + b.width))
        if vv < max(4, .04 * scale * scale):
            return 0.0
        ttc = -(rx * vx + ry * vy) / vv
        if not 0 < ttc <= RISK_HORIZON_SEC:
            return 0.0
        closest = math.hypot(rx + vx * ttc, ry + vy * ttc)
        # Image-plane extrapolation is an uncalibrated cue, not metric TTC.
        return float(np.clip((1 - closest / scale) * (1 - ttc / (RISK_HORIZON_SEC + 1)), 0, .85)) if closest < scale else 0.0

    def finish(self, duration):
        for identity in list(self.active):
            self._close(identity, duration)
        merged = []
        for e in sorted(self.events, key=lambda x: (x[2], x[0], x[1])):
            if merged and merged[-1][2] == e[2] and e[0] <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e[1])
            else:
                merged.append(e[:])
        return sorted(merged, key=lambda x: (x[0], x[2]))


def _crosses(a, b, line):
    # Both finite segments must intersect; crossing an extended line is not enough.
    def cross(u, v):
        return u[0] * v[1] - u[1] * v[0]
    c, d = line
    movement = (b[0] - a[0], b[1] - a[1])
    marking = (d[0] - c[0], d[1] - c[1])
    delta = (c[0] - a[0], c[1] - a[1])
    denominator = cross(movement, marking)
    if abs(denominator) < 1e-9:
        return False
    along_path = cross(delta, marking) / denominator
    along_line = cross(delta, movement) / denominator
    return 0 < along_path <= 1 and 0 <= along_line <= 1


@lru_cache(maxsize=1)
def _model():
    weights = Path(os.environ.get("TRAFFIC_WEIGHTS", WEIGHTS_PATH))
    if not weights.is_file():
        raise FileNotFoundError(f"Missing {weights}; run weights/download.sh first.")
    try:
        import torch
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install requirements.txt before inference.") from exc
    random.seed(0)
    np.random.seed(0)
    torch.manual_seed(0)
    torch.set_num_threads(min(4, max(1, os.cpu_count() or 1)))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(0)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    return YOLO(str(weights))


def _detect(frame):
    model = _model()
    try:
        import torch
        device = 0 if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"
    with _INFERENCE_LOCK:
        result = model.predict(frame, conf=.25, imgsz=640, device=device, max_det=150, verbose=False)[0]
    if result.boxes is None or len(result.boxes) == 0:
        return []
    boxes = result.boxes
    coords, ids, confs = boxes.xyxy.cpu().numpy(), boxes.cls.cpu().numpy().astype(int), boxes.conf.cpu().numpy()
    names = result.names
    return [Detection(tuple(map(float, b)), int(c), str(names.get(int(c), c)).lower(), float(s))
            for b, c, s in zip(coords, ids, confs)]


def _runtime_config():
    try:
        return json.loads(Path(os.environ.get("TRAFFIC_CONFIG", CONFIG_PATH)).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _frame_stride(fps=25.0):
    raw = _runtime_config()
    fps = float(fps)
    if not math.isfinite(fps) or fps <= 0:
        fps = 25.0
    target = max(1.0, float(raw.get("max_analyzed_fps", 8.0)))
    return max(1, int(raw.get("frame_stride", 3)), math.ceil(fps / target))


def _prepare_frame(frame, maximum):
    height, width = frame.shape[:2]
    scale = min(1.0, maximum / max(width, height))
    if scale < 1:
        import cv2
        return cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
    return frame


def detect_events(video_path: str) -> list[list]:
    """Part A. Return [[start_sec, end_sec, label], ...] for one mp4."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required; install requirements.txt.") from exc
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25)
    if not math.isfinite(fps) or fps <= 0:
        fps = 25.0
    maximum = max(320, int(_runtime_config().get("max_frame_dimension", 1280)))
    analyzer, stride, index = None, _frame_stride(fps), 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % stride == 0:
                frame = _prepare_frame(frame, maximum)
                if analyzer is None:
                    analyzer = Analyzer(frame.shape[1], frame.shape[0])
                analyzer.process(frame, index / fps, _detect(frame))
            index += 1
    finally:
        cap.release()
    if analyzer is None:
        raise ValueError(f"No decodable frames in video: {video_path}")
    duration = index / fps
    events = analyzer.finish(duration)
    clean = []
    for s, e, label in events:
        start = max(0.0, min(float(s), max(0.0, duration - 0.01)))
        end = min(duration, max(start + 0.01, float(e)))
        if label in CLASSES and start < end:
            clean.append([start, end, label])
    return clean


class RiskEstimator:
    """Causal Part B estimator; it sees only frames passed to step()."""
    def reset(self, meta: dict) -> None:
        self.meta = dict(meta)
        self.analyzer = None
        self.stride = _frame_stride(meta.get("fps", 25))
        self.maximum = max(320, int(_runtime_config().get("max_frame_dimension", 1280)))
        self.frame_index = 0
        self.score = 0.0
        self.last_t = -math.inf

    def step(self, frame: np.ndarray, t_sec: float) -> float:
        if not hasattr(self, "analyzer"):
            self.reset({"width": frame.shape[1], "height": frame.shape[0]})
        t_sec = float(t_sec)
        if not math.isfinite(t_sec) or t_sec < 0:
            raise ValueError("RiskEstimator requires a finite nonnegative timestamp")
        if t_sec < self.last_t:
            raise ValueError("Call reset before starting a new video; timestamps must be chronological")
        if self.frame_index % self.stride == 0:
            frame = _prepare_frame(frame, self.maximum)
            if self.analyzer is None:
                self.analyzer = Analyzer(frame.shape[1], frame.shape[0])
            self.score = self.analyzer.process(frame, t_sec, _detect(frame))
        self.frame_index += 1
        self.last_t = t_sec
        return float(np.clip(self.score, 0, 1))
