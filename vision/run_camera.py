"""YOLO odamlarni track qiladi va virtual eshik chizig‘idan o‘tish hodisasini API ga yuboradi."""
import argparse, json, time, uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import cv2, requests
from ultralytics import YOLO

class EventSender:
    def __init__(self, api, queue_file):
        self.api, self.queue_file = api.rstrip("/"), Path(queue_file)
    def send(self, data):
        try:
            requests.post(self.api + "/api/events", json=data, timeout=3).raise_for_status()
            return
        except requests.RequestException:
            with self.queue_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(data) + "\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="0"); p.add_argument("--camera-id", default="front-door")
    p.add_argument("--line", type=float, default=.5); p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--model", default="yolo11n.pt")
    args = p.parse_args()
    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    assert cap.isOpened(), f"Kamera/video ochilmadi: {args.source}"
    model, sender = YOLO(args.model), EventSender(args.api, "data/offline_events.jsonl")
    last_side, last_event = {}, defaultdict(float)
    while True:
        ok, frame = cap.read()
        if not ok: break
        h, w = frame.shape[:2]; xline = int(w * args.line)
        result = model.track(frame, persist=True, classes=[0], verbose=False, tracker="bytetrack.yaml")[0]
        if result.boxes and result.boxes.id is not None:
            for box, tid in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.id.int().cpu().tolist()):
                x1,y1,x2,y2 = map(int, box); cx = (x1+x2)//2; side = "R" if cx >= xline else "L"; old = last_side.get(tid)
                if old and old != side and time.time() - last_event[tid] > 3:
                    direction = "IN" if old == "L" and side == "R" else "OUT"
                    sender.send({"event_id": str(uuid.uuid4()), "camera_id": args.camera_id, "track_id": str(tid), "direction": direction, "occurred_at": datetime.now(timezone.utc).isoformat()})
                    last_event[tid] = time.time()
                last_side[tid] = side
                cv2.rectangle(frame,(x1,y1),(x2,y2),(50,220,140),2); cv2.putText(frame,f"#{tid}",(x1,y1-8),cv2.FONT_HERSHEY_SIMPLEX,.7,(50,220,140),2)
        cv2.line(frame,(xline,0),(xline,h),(0,190,255),3); cv2.putText(frame,"IN ->",(xline+8,30),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,190,255),2)
        cv2.imshow("VisionTime AI | q = exit",frame)
        if cv2.waitKey(1)&0xFF == ord("q"): break
    cap.release(); cv2.destroyAllWindows()
if __name__ == "__main__":
    main()
