# Testing

From the Agent Skills Lab package root, run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_anime_director_contract \
  tests.test_anime_director_regressions \
  tests.test_storyboard_validator \
  tests.test_shot_contract_compiler \
  tests.test_shot_contract_validator -v
```

These tests cover board/reference schemas, timing, explicit unknowns, human approval, draft binding, source digests, board-to-contract drift, control-method compatibility, sequence conflicts, authority state, and stable CLI failure behavior.

The deterministic checks prove contract behavior only. They do not prove acting, physics, composition, taste, generated-media quality, or an executor's creative judgment. A future with-Skill/no-Skill model benchmark and human viewer review require separate authorization and evidence.

Historical executor/comparator outputs remain outside this public package. They are not generated or rewritten by these tests.
