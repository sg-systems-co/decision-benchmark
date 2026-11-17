# Answer-key changes by engine version

Every golden key file `keys-<version>.yaml` holds the answer keys the rules and core tests write under that engine version (`tests/keys/collect.py`). `tests/keys/test_golden_keys.py` fails when a key changes without a version bump. Each version below lists what changed against the one before, by rule ID.

## 0.9.0a1

Baseline before A12: the v0.9 engine. 124 keys written in 118 tests (8 further engine calls end in `UnsupportedCase` by design and write no key).
