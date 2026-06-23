"""Helpers for reproducible comparison manifests."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from tts_lab.infrastructure.reference_bundle import ReferenceBundle


@dataclass(frozen=True)
class ComparisonCase:
    """A single comparison configuration."""

    case_id: str
    bundle_path: str
    segment_path: str
    text_label: str
    target_text: str
    language: str
    mode: str
    transcription_validated: bool
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ComparisonResult:
    """The result of a generated comparison case."""

    case: ComparisonCase
    status: str
    output_path: str | None
    duration_seconds: float | None
    error_message: str | None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["case"] = self.case.to_dict()
        return payload


def slugify(value: str) -> str:
    """Convert human labels into stable file-safe ids."""
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered or "case"


def build_case_prefix(bundle: ReferenceBundle, *, bundle_path: str) -> str:
    """Build a stable, human-readable prefix for comparison case ids."""
    bundle_slug = slugify(Path(bundle.segment_path).stem)
    bundle_hash = hashlib.sha1(bundle_path.encode("utf-8")).hexdigest()[:8]
    return f"{bundle_slug}-{bundle_hash}"


def build_default_cases(
    bundle: ReferenceBundle,
    *,
    bundle_path: str,
    target_text: str,
    text_label: str,
) -> list[ComparisonCase]:
    """Build the default small comparison matrix for one bundle."""
    case_prefix = build_case_prefix(bundle, bundle_path=bundle_path)
    warnings = bundle.warnings
    base = [
        ComparisonCase(
            case_id=f"{case_prefix}-auto-icl",
            bundle_path=bundle_path,
            segment_path=bundle.segment_path,
            text_label=text_label,
            target_text=target_text,
            language="auto",
            mode="icl",
            transcription_validated=bundle.transcription_validated,
            warnings=warnings,
        ),
        ComparisonCase(
            case_id=f"{case_prefix}-auto-embedding",
            bundle_path=bundle_path,
            segment_path=bundle.segment_path,
            text_label=text_label,
            target_text=target_text,
            language="auto",
            mode="embedding",
            transcription_validated=bundle.transcription_validated,
            warnings=warnings,
        ),
    ]
    return base


def build_manifest(*, model_path: str, cases: list[ComparisonResult], output_dir: Path, target_text: str) -> dict[str, object]:
    """Build a JSON-serializable manifest for a comparison run."""
    return {
        "model_path": model_path,
        "target_text": target_text,
        "output_dir": str(output_dir),
        "cases": [case.to_dict() for case in cases],
    }
