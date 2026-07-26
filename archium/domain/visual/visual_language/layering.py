"""Scene layer roles — soft layering without a full SceneGraph tree."""

from __future__ import annotations

from enum import StrEnum


class SceneLayerRole(StrEnum):
    BACKGROUND = "background"
    IMAGE = "image"
    GEOMETRY = "geometry"
    DECORATION = "decoration"
    ANNOTATION = "annotation"
    TEXT = "text"
