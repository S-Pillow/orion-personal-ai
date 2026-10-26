#!/usr/bin/env python3
"""Offline Sherpa KWS grid evaluator for Orion wake-word research.

This is development/evaluation tooling only. It does not edit Hermes config,
start Hermes, open a microphone, install packages, or download a model.

Inputs must be 16 kHz, mono, PCM16 WAV files captured from the intended
deployment path. Positive files should contain intended "Hey Orion" attempts.
Negative files should contain representative non-wake ambient/speech audio.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280
TRAILING_SILENCE_SECONDS = 0.5


@dataclass(frozen=True)
class AudioFile:
    path: Path
    samples: "object"
    duration_seconds: float
    sha256: str


def parse_float_list(raw: str, *, name: str) -> list[float]:
    values: list[float] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        try:
            value = float(text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name}: invalid float {text!r}") from exc
        if not math.isfinite(value) or value < 0:
            raise argparse.ArgumentTypeError(f"{name}: values must be finite and >= 0")
        values.append(value)
    if not values:
        raise argparse.ArgumentTypeError(f"{name}: at least one value is required")
    return values


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wav_paths(root: Path) -> list[Path]:
    if not root.is_dir():
        raise RuntimeError(f"audio directory missing: {root}")
    paths = sorted(p for p in root.rglob("*.wav") if p.is_file())
    if not paths:
        raise RuntimeError(f"no WAV files found under: {root}")
    return paths


def load_pcm16_mono_16k(path: Path, np) -> AudioFile:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.getnframes()
        if channels != 1 or width != 2 or rate != SAMPLE_RATE:
            raise RuntimeError(
                f"{path}: expected mono PCM16 {SAMPLE_RATE} Hz; "
                f"got channels={channels}, width={width}, rate={rate}"
            )
        raw = wav.readframes(frames)
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return AudioFile(
        path=path,
        samples=samples,
        duration_seconds=len(samples) / SAMPLE_RATE,
        sha256=sha256_file(path),
    )


def find_model_file(model_dir: Path, stem: str) -> Path:
    # Match the accepted Hermes source first: use the non-int8 model files.
    hits = sorted(model_dir.glob(f"{stem}-*[!8].onnx"))
    if not hits:
        hits = sorted(
            p for p in model_dir.glob(f"{stem}-*.onnx")
            if "int8" not in p.name.lower()
        )
    if not hits:
        raise RuntimeError(f"missing {stem} model under {model_dir}")
    return hits[0]


def make_keywords_file(model_dir: Path, phrase: str, text2token) -> Path:
    tokens_path = model_dir / "tokens.txt"
    bpe_path = model_dir / "bpe.model"
    if not tokens_path.is_file() or not bpe_path.is_file():
        raise RuntimeError("model_dir must contain tokens.txt and bpe.model")
    tokenized = text2token(
        [phrase.upper()],
        tokens=str(tokens_path),
        tokens_type="bpe",
        bpe_model=str(bpe_path),
    )
    if not tokenized or not tokenized[0]:
        raise RuntimeError("phrase tokenization produced no tokens")
    display = phrase.upper().replace(" ", "_")
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        prefix="orion-sherpa-kws-",
        delete=False,
        encoding="utf-8",
    )
    with handle:
        handle.write(" ".join(tokenized[0]) + f" @{display}\n")
    return Path(handle.name)


def build_spotter(
    sherpa_onnx,
    *,
    model_dir: Path,
    keywords_file: Path,
    threshold: float,
    score: float,
):
    return sherpa_onnx.KeywordSpotter(
        tokens=str(model_dir / "tokens.txt"),
        encoder=str(find_model_file(model_dir, "encoder")),
        decoder=str(find_model_file(model_dir, "decoder")),
        joiner=str(find_model_file(model_dir, "joiner")),
        keywords_file=str(keywords_file),
        keywords_threshold=threshold,
        keywords_score=score,
        num_threads=1,
    )


def count_detections(spotter, audio: AudioFile, np) -> int:
    stream = spotter.create_stream()
    count = 0

    def feed(samples) -> None:
        nonlocal stream, count
        stream.accept_waveform(SAMPLE_RATE, samples)
        while spotter.is_ready(stream):
            spotter.decode_stream(stream)
            result = spotter.get_result(stream)
            if result:
                count += 1
                # Match accepted Hermes behavior: one phrase should not keep
                # firing on the decoder state that produced the first match.
                spotter.reset_stream(stream)

    for offset in range(0, len(audio.samples), CHUNK_SAMPLES):
        feed(audio.samples[offset: offset + CHUNK_SAMPLES])

    tail = np.zeros(
        int(SAMPLE_RATE * TRAILING_SILENCE_SECONDS),
        dtype=np.float32,
    )
    for offset in range(0, len(tail), CHUNK_SAMPLES):
        feed(tail[offset: offset + CHUNK_SAMPLES])

    return count


def corpus_manifest(files: Iterable[AudioFile]) -> dict:
    entries = [
        {
            "path": str(item.path),
            "sha256": item.sha256,
            "duration_seconds": round(item.duration_seconds, 6),
        }
        for item in files
    ]
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {
        "files": entries,
        "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
        "file_count": len(entries),
        "duration_seconds": round(sum(x["duration_seconds"] for x in entries), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--positive-dir", type=Path, required=True)
    parser.add_argument("--negative-dir", type=Path, required=True)
    parser.add_argument("--phrase", default="hey orion")
    parser.add_argument("--thresholds", default="0.25,0.21,0.17,0.13")
    parser.add_argument("--scores", default="1.0")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    thresholds = parse_float_list(args.thresholds, name="thresholds")
    scores = parse_float_list(args.scores, name="scores")
    if any(value > 1.0 for value in thresholds):
        raise SystemExit("thresholds must be in [0, 1]")

    try:
        import numpy as np
        import sherpa_onnx
        from sherpa_onnx import text2token
    except ImportError as exc:
        raise SystemExit(
            "sherpa_onnx/numpy are not installed in this Python environment"
        ) from exc

    model_dir = args.model_dir.resolve(strict=True)
    positives = [
        load_pcm16_mono_16k(path, np) for path in wav_paths(args.positive_dir)
    ]
    negatives = [
        load_pcm16_mono_16k(path, np) for path in wav_paths(args.negative_dir)
    ]
    negative_hours = sum(item.duration_seconds for item in negatives) / 3600.0
    if negative_hours <= 0:
        raise SystemExit("negative corpus duration must be > 0")

    keywords_file = make_keywords_file(model_dir, args.phrase, text2token)
    try:
        cells = []
        for threshold in thresholds:
            for score in scores:
                spotter = build_spotter(
                    sherpa_onnx,
                    model_dir=model_dir,
                    keywords_file=keywords_file,
                    threshold=threshold,
                    score=score,
                )
                positive_counts = [
                    count_detections(spotter, item, np) for item in positives
                ]
                negative_counts = [
                    count_detections(spotter, item, np) for item in negatives
                ]
                hits = sum(1 for count in positive_counts if count > 0)
                false_accepts = sum(negative_counts)
                cells.append({
                    "threshold": threshold,
                    "score": score,
                    "positive_hits": hits,
                    "positive_total": len(positives),
                    "positive_rate": hits / len(positives),
                    "false_accepts": false_accepts,
                    "negative_hours": negative_hours,
                    "false_accepts_per_hour": false_accepts / negative_hours,
                })
    finally:
        try:
            keywords_file.unlink()
        except OSError:
            pass

    payload = {
        "schema_version": 1,
        "engine": "sherpa_onnx.KeywordSpotter",
        "phrase": args.phrase,
        "model_dir": str(model_dir),
        "model_files": {
            name: {
                "path": str(path),
                "sha256": sha256_file(path),
            }
            for name, path in (
                ("tokens", model_dir / "tokens.txt"),
                ("bpe", model_dir / "bpe.model"),
                ("encoder", find_model_file(model_dir, "encoder")),
                ("decoder", find_model_file(model_dir, "decoder")),
                ("joiner", find_model_file(model_dir, "joiner")),
            )
        },
        "positive_corpus": corpus_manifest(positives),
        "negative_corpus": corpus_manifest(negatives),
        "cells": cells,
        "mutation_scope": "optional local JSON result only",
        "hermes_config_changed": False,
        "gateway_used": False,
        "microphone_opened": False,
        "network_used": False,
    }

    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        output = args.json_out.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".tmp")
        temporary.write_text(rendered + "\n", encoding="utf-8")
        os.replace(temporary, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
