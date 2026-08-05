1. 把 reviewer_pack.json + 截图发给 ≥5 名建筑师（勿发 sealed_key）。
2. 收集 ballots 写回 session.sealed.json 的 ballots 数组。
3. 运行: py -3 scripts/evaluate_vq008_blind_review.py session.sealed.json
4. 仅当 exit 0 且 beta_allowed=true 时，VQ-008 视觉硬门才可清。
