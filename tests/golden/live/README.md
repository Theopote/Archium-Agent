# Layer 3: Live Model Evaluation

Manual or scheduled runs only. **Not part of default CI.**

Set `ARCHIUM_LIVE_LLM=1` and configure API keys in `.env`, then:

```bash
pytest tests/golden/live -v -m live_llm
```

Records output quality metrics manually; do not gate merges on live model variance.
