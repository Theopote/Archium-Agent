<!-- AUTO-GENERATED from archium/config/settings.py — do not edit manually. -->
<!-- Regenerate: python scripts/generate_config_docs.py -->

# Configuration Reference

Single source of truth: [`archium/config/settings.py`](../archium/config/settings.py).

This file and [`.env.example`](../.env.example) are generated and checked in CI.
Do not edit them manually.

> The app starts without an API Key. LLM-dependent features fail at runtime with a clear error.

## Application {#app}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `APP_NAME` | `Archium` | No | Application display name. |
| `ENVIRONMENT` | `development` | No | Runtime environment label (development, staging, production). |
| `LOG_LEVEL` | `INFO` | No | Root logger level. |
| `STREAMLIT_BACKGROUND_WORKFLOWS_ENABLED` | `true` | No | Run LangGraph presentation workflows in a background thread from Streamlit. |

## Storage paths {#storage}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `DATABASE_PATH` | `data/database/archium.db` | No | SQLite database file path, relative to project root unless absolute. |
| `DATABASE_URL` | `*(unset)*` | No | Optional SQLAlchemy URL override. When unset, database_path is used. Set to postgresql+psycopg://user:pass@host:5432/dbname for multi-user deployments. |
| `DATABASE_POOL_SIZE` | `5` | No | PostgreSQL connection pool size (ignored for SQLite). |
| `DATABASE_MAX_OVERFLOW` | `10` | No | PostgreSQL pool overflow connections beyond pool_size. |
| `DATABASE_POOL_RECYCLE_SECONDS` | `3600` | No | Recycle PostgreSQL connections after this many seconds (0 = disabled). |
| `DATABASE_POOL_PRE_PING` | `true` | No | Ping PostgreSQL connections before checkout to drop stale connections. |
| `DATABASE_SQLITE_BUSY_TIMEOUT_MS` | `30000` | No | SQLite busy timeout in milliseconds (WAL + busy_timeout reduce 'database is locked'). |
| `DATABASE_SQLITE_WAL_ENABLED` | `true` | No | Enable SQLite WAL journal mode for better concurrent read/write behavior. |
| `WORKFLOW_CHECKPOINT_PATH` | `data/database/workflow_checkpoints.db` | No | LangGraph SqliteSaver checkpoint database path. |
| `WORKFLOW_CHECKPOINT_COMMIT_ENABLED` | `true` | No | Commit the SQLAlchemy session after each workflow checkpoint so Streamlit and other clients can poll WorkflowRun progress. |
| `PROJECT_STORAGE_PATH` | `data/projects` | No | Uploaded project documents and assets root directory. |
| `OUTPUT_PATH` | `data/outputs` | No | Generated presentation export output directory. |
| `CHROMA_PATH` | `data/chroma` | No | Chroma vector index storage directory. |
| `CHROMA_MAX_DOCUMENTS` | `10000` | No | Maximum number of documents in Chroma vector store to prevent memory issues. |
| `WORKFLOW_CHECKPOINT_RETENTION_DAYS` | `7` | No | Auto-delete workflow checkpoints older than this many days to manage storage. |

## LLM (OpenAI-compatible) {#llm}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `LLM_PROVIDER` | `openai_compatible` | No | LLM provider backend identifier. |
| `LLM_API_KEY` / `GEMINI_API_KEY` | `*(unset)*` | No | OpenAI-compatible API key (e.g. Gemini). Unset allows startup; LLM calls fail at runtime. |
| `LLM_BASE_URL` / `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | No | OpenAI-compatible API base URL. |
| `LLM_MODEL` / `GEMINI_MODEL` | `gemini-2.5-flash` | No | Default chat/completion model name. |
| `LLM_MAX_RETRIES` | `2` | No | Maximum LLM request retries. |
| `LLM_REPAIR_ATTEMPTS` | `2` | No | Maximum structured-output repair attempts per LLM call. |
| `LLM_TIMEOUT_SECONDS` | `60.0` | No | LLM request timeout in seconds. |
| `LLM_MAX_CONCURRENT_REQUESTS` | `5` | No | Maximum concurrent LLM API requests to prevent rate limiting and resource exhaustion. |
| `SLIDE_PER_PAGE_GENERATION` | `true` | No | When true, SlidePlanner invokes the LLM once per page with SlideGenerationContext instead of one batch SlidePlan call. |

## Embedding {#embedding}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `EMBEDDING_PROVIDER` | `openai_compatible` | No | Embedding provider backend identifier. |
| `EMBEDDING_API_KEY` | `*(unset)*` | No | Embedding API key. Falls back to LLM key when unset. |
| `EMBEDDING_BASE_URL` | `*(unset)*` | No | Embedding API base URL. Falls back to LLM base URL when unset. |
| `EMBEDDING_MODEL` | `*(unset)*` | No | Embedding model name. Required for remote embedding providers when retrieval is enabled. |
| `EMBEDDING_DIMENSIONS` | `*(unset)*` | No | Optional embedding vector dimension override. |

## retrieval.* — Vector retrieval (Chroma) {#retrieval}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `RETRIEVAL_ENABLED` | `false` | No | Enable Chroma vector retrieval during generation. Auto-disabled when embedding is not configured. |
| `RETRIEVAL_TOP_K` | `12` | No | Top-k chunks returned from vector search. |
| `ASSET_VISION_RAG_ENABLED` | `true` | No | When true, generate heuristic or LLM vision captions for drawing/image assets at ingest and index them as searchable RAG chunks. |
| `ASSET_VISION_LLM_ENABLED` | `false` | No | When true and LLM is configured, use multimodal vision to caption drawing assets at ingest (falls back to heuristic caption when unavailable). |
| `ASSET_VISION_LLM_MODEL` | `*(unset)*` | No | Optional vision-capable model override for asset captioning at ingest. |
| `RETRIEVAL_KEYWORD_BOOST_ENABLED` | `true` | No | When true, rerank vector hits with keyword overlap (helps metrics, drawing captions, and proper nouns that pure embeddings may miss). |
| `CHUNK_CONTEXT_MAX_CHARS` | `600` | No | Maximum characters injected per retrieved chunk into LLM context. |

## Document chunking {#chunking}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `EMBEDDING_CHUNKING_ENABLED` | `true` | No | Use embedding breakpoint detection for long paragraph splitting. |
| `EMBEDDING_CHUNK_MIN_SEGMENT_CHARS` | `1200` | No | Minimum segment size before embedding breakpoint chunking applies. |
| `EMBEDDING_BREAKPOINT_THRESHOLD` | `0.65` | No | Cosine-distance threshold for embedding breakpoint splits. |
| `SEMANTIC_CHUNKING_ENABLED` | `true` | No | Enable semantic paragraph merging and recursive text splitting on import. |
| `CHUNK_MAX_CHARS` | `800` | No | Maximum characters per document chunk. |
| `CHUNK_MIN_CHARS` | `80` | No | Minimum characters per document chunk. |
| `CHUNK_OVERLAP_CHARS` | `120` | No | Character overlap between adjacent chunks. |

## Workflow {#workflow}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `FACT_EXTRACTION_ENABLED` | `true` | No | When true, extract ProjectFact records at document ingest (rule-based metrics) and after context retrieval (LLM for remaining standard facts). |

## review.* — Quality review & export gating {#review}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `BLOCK_EXPORT_ON_CRITICAL_REVIEW` | `false` | No | When true, open CRITICAL ReviewIssue records block JSON/Marp export. |
| `LLM_PROFESSIONAL_REVIEW_ENABLED` | `false` | No | When true and LLM is configured, run LLM-assisted review across all four layers (content/evidence/architectural/layout) and Brief semantic alignment. |
| `VISUAL_QA_ENABLED` | `true` | No | When true and Pillow is available, run explainable image QA on matched slide assets (dimensions, margins, contrast, clipping, text density, north arrow, legend, drawing type). |
| `VISUAL_CRITIC_ENABLED` | `true` | No | When true, run read-only Visual Critic after visual render (Visual Quality heuristics; never auto-repairs or blocks PPTX export). |
| `VISUAL_DECK_QA_ENABLED` | `true` | No | When true, run read-only deck-level consistency QA after visual render (footer/chrome/typography/family rhythm; never blocks PPTX export). |
| `VISUAL_CRITIC_LLM_ENABLED` | `false` | No | When true and LLM is configured, enrich Visual Critic with multimodal vision on slide PNGs (soft-fail; never blocks PPTX). |
| `VISUAL_CRITIC_LLM_MODEL` | `*(unset)*` | No | Optional vision-capable model override for Visual Critic LLM path. |
| `VISUAL_PPTX_SCREENSHOTS_ENABLED` | `true` | No | When true, attempt PPTX→PNG screenshots (LibreOffice + pdftoppm) after export for Visual Critic. Soft-skips when tools are missing. |
| `INDUCTION_SCREENSHOT_CLUSTERING_ENABLED` | `true` | No | When true, blend deterministic screenshot fingerprints into reference slide clustering when per-slide PNGs exist. |
| `INDUCTION_SCREENSHOT_CLUSTERING_WEIGHT` | `0.35` | No | Weight of screenshot distance vs structural embedding distance. |

## repair.* — Automated slide repair {#repair}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `SLIDE_REPAIR_ENABLED` | `false` | No | When true and LLM is available, auto-repair slide-level CRITICAL/HIGH review issues. |
| `SLIDE_REPAIR_MAX_ROUNDS` | `2` | No | Maximum automated repair → four-layer re-review cycles per workflow run. |
| `SCENE_REPAIR_ENABLED` | `true` | No | When true, compile RenderScenes after render and run deterministic scene repair. |
| `SCENE_REPAIR_MAX_ROUNDS` | `2` | No | Maximum semantic QA → RenderScene repair rounds in visual workflow. |

## render.* — Marp & PptxGenJS export {#render}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `MARP_COMMAND` | `marp` | No | Marp CLI executable name or path. |
| `MARP_PREVIEW_IMAGES_ENABLED` | `true` | No | When true and Marp Markdown is exported, generate PNG slide previews via Marp CLI. |
| `MARP_PREVIEW_IMAGE_FORMAT` | `png` | No | Image format for Marp --images export (png or jpeg). |
| `PPTXGEN_NODE_COMMAND` | `node` | No | Node.js executable used for PptxGenJS editable PPTX export. |
| `PPTXGEN_SCRIPT_PATH` | `*(unset)*` | No | Path to render.mjs. Defaults to bundled archium/infrastructure/renderers/pptxgen/render.mjs. |

## Visual fallback, layout thresholds & web image search {#visual}

| Environment variable | Default | Required at startup | Description |
|----------------------|---------|:-------------------:|-------------|
| `VISUAL_FALLBACK_ENABLED` | `true` | No | When true, export tries relaxed asset matching and programmatic diagram fallbacks. |
| `VISUAL_FALLBACK_RELAXED_MATCHING` | `true` | No | When true, unmatched visuals may bind to the best available project asset at export time. |
| `VISUAL_FALLBACK_RELAXED_MIN_SCORE` | `0.2` | No | Minimum score for relaxed asset fallback during export. |
| `VISUAL_FALLBACK_GENERATE_DIAGRAMS` | `true` | No | When true, generate schematic PNG diagrams for unmatched diagram/plan/timeline visuals. |
| `LAYOUT_MIN_BODY_FONT_PT` | `14.0` | No | Minimum body text size (pt) for LayoutValidator. |
| `LAYOUT_MIN_CAPTION_FONT_PT` | `9.0` | No | Minimum caption text size (pt) for LayoutValidator. |
| `LAYOUT_MIN_SOURCE_FONT_PT` | `8.0` | No | Minimum source text size (pt) for LayoutValidator. |
| `LAYOUT_MIN_HERO_AREA_RATIO` | `0.45` | No | Minimum hero area ratio of safe area for hero/drawing pages. |
| `LAYOUT_MIN_WHITESPACE_RATIO` | `0.08` | No | Minimum whitespace ratio for LayoutValidator. |
| `LAYOUT_MAX_WHITESPACE_RATIO` | `0.6` | No | Maximum whitespace ratio for LayoutValidator. |
| `WEB_IMAGE_SEARCH_ENABLED` | `true` | No | When true, export may download licensed stock photos for rendering/site-photo/reference visuals before falling back to schematic diagrams. |
| `WEB_IMAGE_SEARCH_PROVIDER` | `pexels` | No | Stock photo provider used for web image search (currently only pexels). |
| `PEXELS_API_KEY` | `*(unset)*` | No | Pexels API key for web image search during export. |
| `WEB_IMAGE_SEARCH_TIMEOUT_SECONDS` | `15.0` | No | HTTP timeout for stock photo search and download. |
| `WEB_IMAGE_SEARCH_PER_PAGE` | `5` | No | Number of Pexels results to consider per visual requirement. |
| `WEB_IMAGE_SEARCH_PERSIST_TO_LIBRARY` | `true` | No | When true, downloaded web images are copied into the project asset library. |
| `UNSPLASH_ACCESS_KEY` | `*(unset)*` | No | Unsplash access key (reserved for future provider support). |
