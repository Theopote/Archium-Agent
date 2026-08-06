VQ-008 Architect Blind Review Pack
================================

1. 把 reviewer_pack.json + assets/ 截图发给 ≥5 名建筑师（勿发 sealed_key.json）。
2. 每位评审填写 ballot 模板（见 CLI --ballot-template reviewer_id）。
3. 导入选票:
   py -3 scripts/evaluate_vq008_blind_review.py session.sealed.json --import-ballots ballots/architect_01.json
4. 校验:
   py -3 scripts/evaluate_vq008_blind_review.py session.sealed.json --validate
5. 评估 Beta 门:
   py -3 scripts/evaluate_vq008_blind_review.py session.sealed.json
6. 仅当 exit 0 且 beta_allowed=true 时，VQ-008 视觉硬门才可清。
