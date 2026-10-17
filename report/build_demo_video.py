"""Assemble the five rendered demo-phase stills into a silent four-minute MP4."""

from __future__ import annotations

from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent
FRAME_FILES = (
    "D1-setup.png",
    "D2-refund-refresh.png",
    "D3-ledger-learning.png",
    "D4-drift-toggle.png",
    "D5-verifier.png",
)
OUTPUT = ROOT / "demo" / "healagent-demo-walkthrough.mp4"
FPS = 10
SECONDS_PER_PHASE = 48
FRAME_SIZE = (1440, 900)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(OUTPUT), cv2.VideoWriter_fourcc(*"mp4v"), FPS, FRAME_SIZE
    )
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not initialize the MP4 video writer")
    try:
        for filename in FRAME_FILES:
            frame = cv2.imread(str(OUTPUT.parent / filename))
            if frame is None:
                raise FileNotFoundError(OUTPUT.parent / filename)
            if (frame.shape[1], frame.shape[0]) != FRAME_SIZE:
                frame = cv2.resize(frame, FRAME_SIZE, interpolation=cv2.INTER_AREA)
            for _ in range(FPS * SECONDS_PER_PHASE):
                writer.write(frame)
    finally:
        writer.release()
    minutes = FPS * SECONDS_PER_PHASE * len(FRAME_FILES) / FPS / 60
    print(f"Wrote {minutes:.0f}-minute silent walkthrough: {OUTPUT}")


if __name__ == "__main__":
    main()
