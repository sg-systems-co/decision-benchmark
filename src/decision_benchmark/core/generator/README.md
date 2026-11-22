# generator (core)

Shared generator framework. It reads everything task-specific from the task set's `TaskSetSpec.generation` and never names a task set or a country.

| Module | What it does |
| --- | --- |
| `seeds.py` | Derived seeds: `random.Random(derive(split_seed, *purpose))`, the first 8 bytes of sha256 (step 11 plan §8.1). |
| `quotas.py` | Exact counts: largest remainder, shares that must come out whole, even country halves. `InfeasibleDemand` stops the build. |
| `spec.py` | The generic generation config (exception types and tiers, two-problem pairs, hard cases and the precedence rows, mixed cases, lines, foreign suppliers, the rule floor, date boundaries) and `SplitSpec`. |
| `slots.py` | The slot allocator (B1 plan §3.6): one deterministic pass that turns a split's quotas into case slots and the `report/slots.json` tables. |
| `provenance.py` | `pipeline_hash` over the files that shape the data. |
| `cli.py` | `db-generate --task-set <id> --split train|test` (release seeds) or `--split-spec spec.yaml`. B1-1 writes the slot report and provenance; later B1 PRs add the cases. |

What a case contains (entities, the clean base scenario, edit operations, hard-case templates, consistency checks) lives in the task set, under `task_sets/<id>/generator/` (from B1-2).
