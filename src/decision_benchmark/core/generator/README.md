# generator (core)

Shared generator framework: derived seeds, exact quotas per split, the phrasebank loader and assembler, the parquet writers and the `db-generate` CLI. It reads each task set's quotas from its TaskSetSpec.

What a case contains (entities, the clean base scenario, the named edit operations, hard-case templates, consistency checks) lives in the task set, under `task_sets/<id>/generator/`.

Lands in build B1 (step-11 plan §3, §12).
