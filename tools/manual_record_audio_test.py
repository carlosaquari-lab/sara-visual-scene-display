from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.audio import AudioManager
from app.services.audio_recording_service import recording_path_for_hotspot, record_wav


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manual microphone recording test for Sara. Does not modify projects."
    )
    parser.add_argument("--seconds", type=float, default=3.0, help="Recording duration in seconds. Default: 3")
    parser.add_argument("--samplerate", type=int, default=44100, help="Sample rate. Default: 44100")
    parser.add_argument("--channels", type=int, default=1, help="Number of channels. Default: 1")
    parser.add_argument("--play", action="store_true", help="Play the recorded WAV using Sara's AudioManager")
    parser.add_argument("--scene-id", default="manual", help="Scene id component for the generated file name")
    parser.add_argument("--hotspot-id", default="hotspot", help="Hotspot id component for the generated file name")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        destination = recording_path_for_hotspot(args.scene_id, args.hotspot_id)
        print(f"Recording {args.seconds:.1f} seconds...")
        print(f"Destination: {destination}")
        record_wav(destination, args.seconds, samplerate=args.samplerate, channels=args.channels)
        print(f"Recorded WAV: {destination}")
        if args.play:
            audio = AudioManager()
            print("Playing recorded WAV with Sara AudioManager...")
            if not audio.play_file(str(destination)):
                print("Playback could not be started.", file=sys.stderr)
                return 2
            # Give asynchronous playback a brief window before the script exits.
            time.sleep(min(max(float(args.seconds), 1.0), 10.0))
            audio.stop()
        return 0
    except ImportError as exc:
        print(f"Audio recording dependency is not available: {exc}", file=sys.stderr)
        print("Install dependencies with: py -m pip install -r requirements.txt", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Recording failed: {exc}", file=sys.stderr)
        print("Check microphone availability, Windows privacy permissions, and selected input device.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())