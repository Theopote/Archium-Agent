"""Manage the Visual QA labeled calibration corpus."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from archium.application.visual_qa_calibration import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_REPORT_PATH,
    corpus_progress,
    load_manifest,
    run_calibration,
    write_calibration_report,
)
from archium.infrastructure.vision.corpus_generator import (
    generate_corpus,
    samples_to_manifest_entries,
)

LABEL_KEYS = (
    "drawing_type",
    "has_north_arrow",
    "has_legend",
    "is_low_resolution",
    "is_clipped",
    "excessive_margins",
    "high_text_density",
    "low_contrast",
)
VALID_CATEGORIES = frozenset(
    {"site_plan", "floor_plan", "section", "elevation", "diagram", "photo"}
)


class VisualQACorpusService:
    """Read/write calibration manifest, seed synthetic corpus, run calibration."""

    def __init__(
        self,
        *,
        corpus_root: Path | None = None,
        manifest_path: Path | None = None,
        report_path: Path | None = None,
    ) -> None:
        self.manifest_path = manifest_path or DEFAULT_MANIFEST_PATH
        self.corpus_root = corpus_root or self.manifest_path.parent
        self.report_path = report_path or DEFAULT_REPORT_PATH
        self.images_dir = self.corpus_root / "images"

    def load(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            return self._empty_manifest()
        return load_manifest(self.manifest_path)

    def save(self, manifest: dict[str, Any]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def progress(self) -> dict[str, Any]:
        return corpus_progress(self.load())

    def list_samples(self) -> list[dict[str, Any]]:
        manifest = self.load()
        return list(manifest.get("samples", []))

    def get_sample(self, sample_id: str) -> dict[str, Any] | None:
        for sample in self.list_samples():
            if str(sample.get("id")) == sample_id:
                return sample
        return None

    def upsert_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        errors = validate_sample(sample)
        if errors:
            raise ValueError("; ".join(errors))

        manifest = self.load()
        samples: list[dict[str, Any]] = list(manifest.get("samples", []))
        sample_id = str(sample["id"])
        payload = normalize_sample(sample)
        replaced = False
        for index, existing in enumerate(samples):
            if str(existing.get("id")) == sample_id:
                samples[index] = payload
                replaced = True
                break
        if not replaced:
            samples.append(payload)
        samples.sort(key=lambda item: str(item.get("id")))
        manifest["samples"] = samples
        self.save(manifest)
        return payload

    def delete_sample(self, sample_id: str) -> bool:
        manifest = self.load()
        samples = list(manifest.get("samples", []))
        kept: list[dict[str, Any]] = []
        removed: dict[str, Any] | None = None
        for sample in samples:
            if str(sample.get("id")) == sample_id:
                removed = sample
            else:
                kept.append(sample)
        if removed is None:
            return False
        manifest["samples"] = kept
        self.save(manifest)
        image_path = self.corpus_root / str(removed.get("path", ""))
        if image_path.is_file():
            image_path.unlink()
        return True

    def import_image(
        self,
        *,
        source_path: Path,
        category: str,
        labels: dict[str, Any],
        sample_id: str | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        if not source_path.is_file():
            raise ValueError(f"Image not found: {source_path}")
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Unsupported category: {category}")

        assigned_id = sample_id or f"{category}_{uuid4().hex[:8]}"
        suffix = source_path.suffix.lower() or ".png"
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            suffix = ".png"
        relative_path = f"images/{assigned_id}{suffix}"
        dest = self.corpus_root / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest)

        merged_labels = {
            "drawing_type": category,
            "has_north_arrow": None,
            "has_legend": None,
            "is_low_resolution": None,
            "is_clipped": None,
            "excessive_margins": None,
            "high_text_density": None,
            "low_contrast": None,
        }
        merged_labels.update(labels)
        if category == "photo":
            merged_labels["has_north_arrow"] = None
            merged_labels["has_legend"] = None

        return self.upsert_sample(
            {
                "id": assigned_id,
                "path": relative_path,
                "category": category,
                "labels": merged_labels,
                "notes": notes.strip() or "人工导入样本",
                "source": "manual_import",
            }
        )

    def seed_synthetic_corpus(
        self,
        *,
        overwrite_images: bool = False,
        replace_manifest: bool = True,
    ) -> dict[str, Any]:
        generated = generate_corpus(
            self.corpus_root,
            overwrite_images=overwrite_images,
        )
        manifest = self.load() if not replace_manifest else self._empty_manifest()
        manifest["corpus_kind"] = "synthetic_bootstrap"
        manifest["samples"] = samples_to_manifest_entries(generated)
        self.save(manifest)
        return {
            "generated_count": len(generated),
            "progress": corpus_progress(manifest),
        }

    def run_calibration_report(self) -> dict[str, Any]:
        return run_calibration(self.manifest_path, corpus_root=self.corpus_root)

    def write_calibration_report(self, report: dict[str, Any]) -> Path:
        write_calibration_report(report, self.report_path)
        return self.report_path

    def calibrate(self) -> dict[str, Any]:
        report = self.run_calibration_report()
        self.write_calibration_report(report)
        return report

    def _empty_manifest(self) -> dict[str, Any]:
        base = {}
        if self.manifest_path.is_file():
            try:
                base = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                base = {}
        return {
            "version": base.get("version", 1),
            "description": base.get(
                "description",
                "Visual QA calibration corpus. Add labeled samples under samples[].",
            ),
            "category_targets": base.get("category_targets"),
            "label_schema": base.get("label_schema"),
            "samples": [],
        }


def normalize_sample(sample: dict[str, Any]) -> dict[str, Any]:
    labels = dict(sample.get("labels", {}))
    normalized_labels: dict[str, Any] = {}
    for key in LABEL_KEYS:
        if key not in labels:
            normalized_labels[key] = None
        else:
            value = labels[key]
            if value is None:
                normalized_labels[key] = None
            elif key == "drawing_type":
                normalized_labels[key] = str(value)
            else:
                normalized_labels[key] = bool(value)
    return {
        "id": str(sample["id"]).strip(),
        "path": str(sample["path"]).strip().replace("\\", "/"),
        "category": str(sample["category"]).strip(),
        "labels": normalized_labels,
        "notes": str(sample.get("notes", "")).strip(),
        "source": str(sample.get("source", "manual")),
    }


def validate_sample(sample: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(sample.get("id", "")).strip():
        errors.append("sample id is required")
    if not str(sample.get("path", "")).strip():
        errors.append("sample path is required")
    category = str(sample.get("category", "")).strip()
    if category not in VALID_CATEGORIES:
        errors.append(f"invalid category: {category}")
    labels = sample.get("labels")
    if not isinstance(labels, dict):
        errors.append("labels must be an object")
        return errors
    drawing_type = labels.get("drawing_type")
    if drawing_type is not None and str(drawing_type) not in VALID_CATEGORIES:
        errors.append(f"invalid drawing_type: {drawing_type}")
    return errors
