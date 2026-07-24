"""Application settings via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Archium application settings.

    Missing API keys do not prevent startup; LLM calls fail at runtime with
    a clear :class:`ConfigurationError`.

    Domain groupings (``retrieval.*``, ``review.*``, ``repair.*``, ``render.*``)
    are documented in :mod:`archium.config.registry` and generated into
    ``docs/configuration-reference.md``.
    """

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # ── app.* ────────────────────────────────────────────────────────────────
    app_name: str = Field(default="Archium", description="Application display name.")
    environment: str = Field(
        default="development",
        description="Runtime environment label (development, staging, production).",
    )
    log_level: str = Field(default="INFO", description="Root logger level.")

    # ── storage.* ────────────────────────────────────────────────────────────
    database_path: Path = Field(
        default=Path("data/database/archium.db"),
        validation_alias=AliasChoices("DATABASE_PATH"),
        description="SQLite database file path, relative to project root unless absolute.",
    )
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL"),
        description=(
            "Optional SQLAlchemy URL override. When unset, database_path is used. "
            "Set to postgresql+psycopg://user:pass@host:5432/dbname for multi-user deployments."
        ),
    )
    database_pool_size: int = Field(
        default=5,
        ge=1,
        description="PostgreSQL connection pool size (ignored for SQLite).",
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        description="PostgreSQL pool overflow connections beyond pool_size.",
    )
    database_pool_recycle_seconds: int = Field(
        default=3600,
        ge=0,
        description="Recycle PostgreSQL connections after this many seconds (0 = disabled).",
    )
    database_pool_pre_ping: bool = Field(
        default=True,
        description="Ping PostgreSQL connections before checkout to drop stale connections.",
    )
    database_sqlite_busy_timeout_ms: int = Field(
        default=30000,
        ge=0,
        description="SQLite busy timeout in milliseconds (WAL + busy_timeout reduce 'database is locked').",
    )
    database_sqlite_wal_enabled: bool = Field(
        default=True,
        description="Enable SQLite WAL journal mode for better concurrent read/write behavior.",
    )
    workflow_checkpoint_path: Path = Field(
        default=Path("data/database/workflow_checkpoints.db"),
        description="LangGraph SqliteSaver checkpoint database path.",
    )
    workflow_checkpoint_commit_enabled: bool = Field(
        default=True,
        description=(
            "Commit the SQLAlchemy session after each workflow checkpoint so "
            "Streamlit and other clients can poll WorkflowRun progress."
        ),
    )
    streamlit_background_workflows_enabled: bool = Field(
        default=True,
        description="Run LangGraph presentation workflows in a background thread from Streamlit.",
    )
    project_storage_path: Path = Field(
        default=Path("data/projects"),
        description="Uploaded project documents and assets root directory.",
    )
    output_path: Path = Field(
        default=Path("data/outputs"),
        description="Generated presentation export output directory.",
    )
    chroma_path: Path = Field(
        default=Path("data/chroma"),
        description="Chroma vector index storage directory.",
    )
    chroma_max_documents: int = Field(
        default=10000,
        ge=100,
        description="Maximum number of documents in Chroma vector store to prevent memory issues.",
    )
    workflow_checkpoint_retention_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Auto-delete workflow checkpoints older than this many days to manage storage.",
    )

    # ── llm.* ────────────────────────────────────────────────────────────────
    llm_provider: str = Field(
        default="openai_compatible",
        description="LLM provider backend identifier.",
    )
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "GEMINI_API_KEY"),
        description="OpenAI-compatible API key (e.g. Gemini). Unset allows startup; LLM calls fail at runtime.",
    )
    llm_base_url: str | None = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        validation_alias=AliasChoices("LLM_BASE_URL", "GEMINI_BASE_URL"),
        description="OpenAI-compatible API base URL.",
    )
    llm_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("LLM_MODEL", "GEMINI_MODEL"),
        description="Default chat/completion model name.",
    )
    llm_max_retries: int = Field(default=2, ge=0, le=5, description="Maximum LLM request retries.")
    llm_repair_attempts: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum structured-output repair attempts per LLM call.",
    )
    llm_timeout_seconds: float = Field(default=60.0, gt=0, description="LLM request timeout in seconds.")
    llm_max_concurrent_requests: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent LLM API requests to prevent rate limiting and resource exhaustion.",
    )

    # ── embedding.* ──────────────────────────────────────────────────────────
    embedding_provider: str = Field(
        default="openai_compatible",
        description="Embedding provider backend identifier.",
    )
    embedding_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_API_KEY"),
        description="Embedding API key. Falls back to LLM key when unset.",
    )
    embedding_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_BASE_URL"),
        description="Embedding API base URL. Falls back to LLM base URL when unset.",
    )
    embedding_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_MODEL"),
        description="Embedding model name. Required for remote embedding providers when retrieval is enabled.",
    )
    embedding_dimensions: int | None = Field(
        default=None,
        ge=1,
        validation_alias=AliasChoices("EMBEDDING_DIMENSIONS"),
        description="Optional embedding vector dimension override.",
    )

    # ── retrieval.* ──────────────────────────────────────────────────────────
    retrieval_enabled: bool = Field(
        default=False,
        description="Enable Chroma vector retrieval during generation. Auto-disabled when embedding is not configured.",
    )
    retrieval_top_k: int = Field(default=12, ge=1, le=50, description="Top-k chunks returned from vector search.")
    asset_vision_rag_enabled: bool = Field(
        default=True,
        description=(
            "When true, generate heuristic or LLM vision captions for drawing/image assets "
            "at ingest and index them as searchable RAG chunks."
        ),
    )
    asset_vision_llm_enabled: bool = Field(
        default=False,
        description=(
            "When true and LLM is configured, use multimodal vision to caption drawing assets "
            "at ingest (falls back to heuristic caption when unavailable)."
        ),
    )
    asset_vision_llm_model: str | None = Field(
        default=None,
        description="Optional vision-capable model override for asset captioning at ingest.",
    )
    vision_image_generation_enabled: bool = Field(
        default=False,
        description=(
            "When true, Vision Engine may call an external/local image backend "
            "(openai_compatible | local_sd | comfyui). When false or unavailable, uses Pillow stub."
        ),
    )
    vision_image_generation_provider: str = Field(
        default="stub",
        description=(
            "Vision Engine image backend: stub | openai_compatible | local_sd "
            "(aliases: a1111, forge, automatic1111) | comfyui."
        ),
    )
    vision_image_generation_model: str = Field(
        default="dall-e-3",
        description="Image model id for openai_compatible Vision Engine provider.",
    )
    vision_image_generation_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "VISION_IMAGE_GENERATION_API_KEY",
            "OPENAI_API_KEY",
        ),
        description="Optional API key for Vision Engine; falls back to LLM_API_KEY.",
    )
    vision_image_generation_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VISION_IMAGE_GENERATION_BASE_URL"),
        description="Optional OpenAI-compatible base URL for image generation.",
    )
    vision_local_sd_base_url: str = Field(
        default="http://127.0.0.1:7860",
        validation_alias=AliasChoices("VISION_LOCAL_SD_BASE_URL"),
        description="AUTOMATIC1111 / Forge WebUI base URL for local_sd provider.",
    )
    vision_local_sd_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VISION_LOCAL_SD_MODEL"),
        description="Optional checkpoint name override for local_sd (sd_model_checkpoint).",
    )
    vision_local_sd_steps: int = Field(
        default=24,
        ge=5,
        le=80,
        description="Local SD sampling steps for txt2img / img2img.",
    )
    vision_local_sd_cfg_scale: float = Field(
        default=6.5,
        ge=1.0,
        le=20.0,
        description="Local SD CFG scale.",
    )
    vision_local_sd_denoising_strength: float = Field(
        default=0.55,
        ge=0.05,
        le=1.0,
        description="Default img2img denoising strength for local_sd conditioned edit.",
    )
    vision_local_sd_sampler: str = Field(
        default="Euler a",
        description="Local SD sampler name (A1111/Forge).",
    )
    vision_local_sd_timeout_seconds: float = Field(
        default=180.0,
        ge=10.0,
        le=900.0,
        description="HTTP timeout for local_sd txt2img/img2img calls.",
    )
    vision_comfyui_base_url: str = Field(
        default="http://127.0.0.1:8188",
        validation_alias=AliasChoices("VISION_COMFYUI_BASE_URL"),
        description="ComfyUI server base URL for comfyui provider.",
    )
    vision_comfyui_checkpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VISION_COMFYUI_CHECKPOINT"),
        description=(
            "Checkpoint filename for builtin ComfyUI graphs; "
            "falls back to VISION_LOCAL_SD_MODEL / VISION_IMAGE_GENERATION_MODEL."
        ),
    )
    vision_comfyui_sampler: str = Field(
        default="euler",
        description="ComfyUI KSampler sampler_name for builtin graphs.",
    )
    vision_comfyui_scheduler: str = Field(
        default="normal",
        description="ComfyUI KSampler scheduler for builtin graphs.",
    )
    vision_comfyui_timeout_seconds: float = Field(
        default=300.0,
        ge=10.0,
        le=1800.0,
        description="Total wait budget for ComfyUI prompt completion.",
    )
    vision_comfyui_poll_interval_seconds: float = Field(
        default=1.0,
        ge=0.2,
        le=10.0,
        description="Polling interval when waiting for ComfyUI /history.",
    )
    slide_recovery_ocr_enabled: bool = Field(
        default=True,
        description="When true, run OCR (pytesseract) for raster slide recovery inputs.",
    )
    slide_recovery_vlm_enabled: bool = Field(
        default=True,
        description=(
            "When true and LLM is configured, use vision LLM for non-text region detection "
            "during slide recovery (falls back to heuristic analysis)."
        ),
    )
    slide_recovery_vlm_model: str | None = Field(
        default=None,
        description="Optional vision-capable model override for slide recovery VLM analysis.",
    )
    slide_recovery_pptx_perceptual_enabled: bool = Field(
        default=True,
        description=(
            "When true, rasterize PPTX slides (when tools available) and supplement "
            "structural parsing with OCR/VLM perceptual regions."
        ),
    )
    retrieval_keyword_boost_enabled: bool = Field(
        default=True,
        description=(
            "When true, rerank vector hits with keyword overlap (helps metrics, drawing captions, "
            "and proper nouns that pure embeddings may miss)."
        ),
    )
    chunk_context_max_chars: int = Field(
        default=600,
        ge=100,
        le=2000,
        description="Maximum characters injected per retrieved chunk into LLM context.",
    )

    # ── chunking.* ───────────────────────────────────────────────────────────
    embedding_chunking_enabled: bool = Field(
        default=True,
        description="Use embedding breakpoint detection for long paragraph splitting.",
    )
    embedding_chunk_min_segment_chars: int = Field(
        default=1200,
        ge=400,
        le=8000,
        description="Minimum segment size before embedding breakpoint chunking applies.",
    )
    embedding_breakpoint_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Cosine-distance threshold for embedding breakpoint splits.",
    )
    semantic_chunking_enabled: bool = Field(
        default=True,
        description="Enable semantic paragraph merging and recursive text splitting on import.",
    )
    chunk_max_chars: int = Field(default=800, ge=100, le=4000, description="Maximum characters per document chunk.")
    chunk_min_chars: int = Field(default=80, ge=1, le=500, description="Minimum characters per document chunk.")
    chunk_overlap_chars: int = Field(
        default=120,
        ge=0,
        le=500,
        description="Character overlap between adjacent chunks.",
    )

    # ── workflow.* ─────────────────────────────────────────────────────────────
    fact_extraction_enabled: bool = Field(
        default=True,
        description=(
            "When true, extract ProjectFact records at document ingest (rule-based metrics) "
            "and after context retrieval (LLM for remaining standard facts)."
        ),
    )

    # ── review.* ─────────────────────────────────────────────────────────────
    block_export_on_critical_review: bool = Field(
        default=False,
        description="When true, open CRITICAL ReviewIssue records block JSON/Marp export.",
    )
    llm_professional_review_enabled: bool = Field(
        default=False,
        description=(
            "When true and LLM is configured, run LLM-assisted review across all four "
            "layers (content/evidence/architectural/layout) and Brief semantic alignment."
        ),
    )
    image_derivatives_enabled: bool = Field(
        default=True,
        description=(
            "When true and Pillow is available, run ImageTreatmentSpec → ImageDerivative "
            "after RenderScene compile (cache under project/cache/derivatives). "
            "Never mutates originals; never applies filters inside PptxGenJS."
        ),
    )
    visual_qa_enabled: bool = Field(
        default=True,
        description=(
            "When true and Pillow is available, run explainable image QA on matched slide assets "
            "(dimensions, margins, contrast, clipping, text density, north arrow, legend, drawing type)."
        ),
    )
    visual_critic_enabled: bool = Field(
        default=True,
        description=(
            "When true, run read-only Visual Critic after visual render "
            "(Visual Quality heuristics; never auto-repairs or blocks PPTX export)."
        ),
    )
    visual_deck_qa_enabled: bool = Field(
        default=True,
        description=(
            "When true, run read-only deck-level consistency QA after visual render "
            "(footer/chrome/typography/family rhythm; never blocks PPTX export)."
        ),
    )
    visual_critic_llm_enabled: bool = Field(
        default=False,
        description=(
            "When true and LLM is configured, enrich Visual Critic with multimodal "
            "vision on slide PNGs (soft-fail; never blocks PPTX)."
        ),
    )
    visual_critic_llm_model: str | None = Field(
        default=None,
        description="Optional vision-capable model override for Visual Critic LLM path.",
    )
    visual_pptx_screenshots_enabled: bool = Field(
        default=True,
        description=(
            "When true, attempt PPTX→PNG screenshots (LibreOffice + pdftoppm) after "
            "export for Visual Critic. Soft-skips when tools are missing."
        ),
    )
    induction_screenshot_clustering_enabled: bool = Field(
        default=True,
        description=(
            "When true, blend deterministic screenshot fingerprints into reference "
            "slide clustering when per-slide PNGs exist."
        ),
    )
    induction_screenshot_clustering_weight: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Weight of screenshot distance vs structural embedding distance.",
    )

    # ── generation.* ─────────────────────────────────────────────────────────
    slide_per_page_generation: bool = Field(
        default=True,
        description=(
            "When true, SlidePlanner invokes the LLM once per page with "
            "SlideGenerationContext instead of one batch SlidePlan call."
        ),
    )

    # ── repair.* ─────────────────────────────────────────────────────────────
    slide_repair_enabled: bool = Field(
        default=False,
        description="When true and LLM is available, auto-repair slide-level CRITICAL/HIGH review issues.",
    )
    slide_repair_max_rounds: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum automated repair → four-layer re-review cycles per workflow run.",
    )
    scene_repair_enabled: bool = Field(
        default=True,
        description="When true, compile RenderScenes after render and run deterministic scene repair.",
    )
    scene_repair_max_rounds: int = Field(
        default=2,
        ge=0,
        le=3,
        description="Maximum semantic QA → RenderScene repair rounds in visual workflow.",
    )

    # ── render.* ─────────────────────────────────────────────────────────────
    marp_command: str = Field(default="marp", description="Marp CLI executable name or path.")
    marp_preview_images_enabled: bool = Field(
        default=True,
        description="When true and Marp Markdown is exported, generate PNG slide previews via Marp CLI.",
    )
    marp_preview_image_format: str = Field(
        default="png",
        description="Image format for Marp --images export (png or jpeg).",
    )
    pptxgen_node_command: str = Field(
        default="node",
        validation_alias=AliasChoices("PPTXGEN_NODE_COMMAND"),
        description="Node.js executable used for PptxGenJS editable PPTX export.",
    )
    pptxgen_script_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("PPTXGEN_SCRIPT_PATH"),
        description="Path to render.mjs. Defaults to bundled archium/infrastructure/renderers/pptxgen/render.mjs.",
    )
    pptx_structure_mode: str = Field(
        default="flat",
        validation_alias=AliasChoices("PPTX_STRUCTURE_MODE"),
        description=(
            "PPTX package structure mode: 'flat' (absolute freeform shapes) or "
            "'structured' (native slide masters/layouts/placeholders)."
        ),
    )
    pptx_chart_export_mode: str = Field(
        default="cross_app_stable",
        validation_alias=AliasChoices("PPTX_CHART_EXPORT_MODE"),
        description=(
            "Chart/table PPTX strategy: 'cross_app_stable' (shapes/images) or "
            "'native_data_backed' (PowerPoint Chart/Table with embedded workbook)."
        ),
    )
    allow_legacy_presentation_spec_pptx_fallback: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_LEGACY_PRESENTATION_SPEC_PPTX_FALLBACK"),
        description=(
            "When true, editable PPTX export may fall back to legacy PresentationSpec "
            "templates if no visual LayoutPlan exists. Formal delivery prefers RenderScene."
        ),
    )
    export_layout_plan_validation_pptx: bool = Field(
        default=False,
        validation_alias=AliasChoices("EXPORT_LAYOUT_PLAN_VALIDATION_PPTX"),
        description=(
            "When true, visual workflow also writes presentation.layout_plan.validation.pptx "
            "from LayoutPlan instructions (non-formal validation artifact)."
        ),
    )

    # ── visual.* ─────────────────────────────────────────────────────────────
    visual_fallback_enabled: bool = Field(
        default=True,
        description="When true, export tries relaxed asset matching and programmatic diagram fallbacks.",
    )
    visual_fallback_relaxed_matching: bool = Field(
        default=True,
        description="When true, unmatched visuals may bind to the best available project asset at export time.",
    )
    visual_fallback_relaxed_min_score: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Minimum score for relaxed asset fallback during export.",
    )
    visual_fallback_generate_diagrams: bool = Field(
        default=True,
        description="When true, generate schematic PNG diagrams for unmatched diagram/plan/timeline visuals.",
    )
    layout_min_body_font_pt: float = Field(
        default=14.0,
        gt=0,
        description="Minimum body text size (pt) for LayoutValidator.",
    )
    layout_min_caption_font_pt: float = Field(
        default=9.0,
        gt=0,
        description="Minimum caption text size (pt) for LayoutValidator.",
    )
    layout_min_source_font_pt: float = Field(
        default=8.0,
        gt=0,
        description="Minimum source text size (pt) for LayoutValidator.",
    )
    layout_min_hero_area_ratio: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Minimum hero area ratio of safe area for hero/drawing pages.",
    )
    layout_min_whitespace_ratio: float = Field(
        default=0.08,
        ge=0.0,
        le=1.0,
        description="Minimum whitespace ratio for LayoutValidator.",
    )
    layout_max_whitespace_ratio: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Maximum whitespace ratio for LayoutValidator.",
    )
    visual_capacity_block_overloaded: bool = Field(
        default=True,
        description=(
            "When true, CAPACITY.OVERLOAD slides do not emit LayoutPlan candidates "
            "(force content adaptation / split before layout planning)."
        ),
    )
    visual_require_approved_design_brief: bool = Field(
        default=False,
        description=(
            "When true, VisualIntent generation requires an APPROVED SlideDesignBrief "
            "for each slide (blocks skipping page design review)."
        ),
    )
    web_image_search_enabled: bool = Field(
        default=True,
        description=(
            "When true, export may download licensed stock photos for rendering/site-photo/reference visuals "
            "before falling back to schematic diagrams."
        ),
    )
    web_image_search_provider: str = Field(
        default="pexels",
        description="Stock photo provider used for web image search (currently only pexels).",
    )
    pexels_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PEXELS_API_KEY"),
        description="Pexels API key for web image search during export.",
    )
    web_image_search_timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        le=120.0,
        description="HTTP timeout for stock photo search and download.",
    )
    web_image_search_per_page: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Number of Pexels results to consider per visual requirement.",
    )
    web_image_search_persist_to_library: bool = Field(
        default=True,
        description="When true, downloaded web images are copied into the project asset library.",
    )
    unsplash_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("UNSPLASH_ACCESS_KEY"),
        description="Unsplash access key (reserved for future provider support).",
    )

    @model_validator(mode="after")
    def _validate_chunk_settings(self) -> Settings:
        if self.chunk_overlap_chars >= self.chunk_max_chars:
            raise ValueError("chunk_overlap_chars must be smaller than chunk_max_chars")
        if self.chunk_min_chars > self.chunk_max_chars:
            raise ValueError("chunk_min_chars must not exceed chunk_max_chars")
        if self.retrieval_enabled and not self.embedding_configured:
            self.retrieval_enabled = False
        return self

    @field_validator(
        "database_path",
        "project_storage_path",
        "output_path",
        "chroma_path",
        "workflow_checkpoint_path",
        mode="after",
    )
    @classmethod
    def _resolve_relative_paths(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return (_PROJECT_ROOT / value).resolve()

    @property
    def resolved_database_url(self) -> str:
        """Return a stable SQLAlchemy URL independent of process working directory."""
        if self.database_url:
            return self._normalize_database_url(self.database_url.strip())
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def database_backend(self) -> str:
        """Primary database dialect label: sqlite, postgresql, or other."""
        url = self.resolved_database_url
        if url.startswith("sqlite"):
            return "sqlite"
        if url.startswith("postgresql"):
            return "postgresql"
        return "other"

    @property
    def is_sqlite(self) -> bool:
        return self.database_backend == "sqlite"

    @property
    def is_postgresql(self) -> bool:
        return self.database_backend == "postgresql"

    @staticmethod
    def _normalize_database_url(url: str) -> str:
        if not url.startswith("sqlite:///"):
            return url
        if url.startswith("sqlite:////") or url == "sqlite:///:memory:":
            return url
        path_part = url.removeprefix("sqlite:///")
        if Path(path_part).is_absolute():
            return url
        resolved = (_PROJECT_ROOT / path_part).resolve()
        return f"sqlite:///{resolved.as_posix()}"

    def ensure_directories(self) -> None:
        """Create data directories if they do not exist."""
        for path in (
            self.project_storage_path,
            self.output_path,
            self.chroma_path,
            self.workflow_checkpoint_path.parent,
            self.database_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def llm_configured(self) -> bool:
        """Return True when an LLM API key is available."""
        return bool(self.llm_api_key)

    @property
    def effective_vision_image_api_key(self) -> str | None:
        """Vision Engine key with fallback to the LLM key."""
        return self.vision_image_generation_api_key or self.llm_api_key

    @property
    def effective_vision_image_base_url(self) -> str | None:
        """Vision Engine base URL with fallback to the LLM base URL."""
        return self.vision_image_generation_base_url or self.llm_base_url

    @property
    def vision_image_api_configured(self) -> bool:
        """True when an external Vision Engine image API can be attempted."""
        return bool(
            self.vision_image_generation_enabled
            and self.vision_image_generation_provider == "openai_compatible"
            and self.effective_vision_image_api_key
        )

    @property
    def vision_local_sd_configured(self) -> bool:
        """True when local_sd (A1111/Forge) provider is enabled with a base URL."""
        provider = (self.vision_image_generation_provider or "").strip().lower()
        return bool(
            self.vision_image_generation_enabled
            and provider in {"local_sd", "a1111", "forge", "automatic1111"}
            and (self.vision_local_sd_base_url or "").strip()
        )

    @property
    def vision_comfyui_configured(self) -> bool:
        """True when comfyui provider is enabled with a base URL."""
        provider = (self.vision_image_generation_provider or "").strip().lower()
        return bool(
            self.vision_image_generation_enabled
            and provider == "comfyui"
            and (self.vision_comfyui_base_url or "").strip()
        )

    @property
    def effective_embedding_api_key(self) -> str | None:
        """Embedding key with optional fallback to the LLM key."""
        return self.embedding_api_key or self.llm_api_key

    @property
    def effective_embedding_base_url(self) -> str | None:
        """Embedding base URL with optional fallback to the LLM base URL."""
        return self.embedding_base_url or self.llm_base_url

    @property
    def embedding_configured(self) -> bool:
        """Return True when embeddings can run with the configured provider."""
        provider = self.embedding_provider.lower()
        if provider == "mock":
            return True
        if provider == "local":
            return bool(self.embedding_model)
        return bool(self.effective_embedding_api_key and self.embedding_model)

    @property
    def retrieval_configured(self) -> bool:
        """Return True when retrieval is enabled with a usable embedding backend."""
        return self.retrieval_enabled and self.embedding_configured

    @property
    def resolved_pptxgen_script_path(self) -> Path:
        """Return the Node render script path for editable PPTX export."""
        if self.pptxgen_script_path is not None:
            path = self.pptxgen_script_path
            if path.is_absolute():
                return path
            return (_PROJECT_ROOT / path).resolve()
        return (
            Path(__file__).resolve().parents[1]
            / "infrastructure"
            / "renderers"
            / "pptxgen"
            / "render.mjs"
        ).resolve()


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    settings = Settings()
    settings.ensure_directories()
    return settings


def reset_settings() -> None:
    """Clear cached settings (for tests)."""
    cache_clear = getattr(get_settings, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()
