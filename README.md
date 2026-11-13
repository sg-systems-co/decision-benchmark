# SG Systems Decision Benchmark

Open benchmarks that test how well AI models and agents decide real-looking business cases in Southeast Asia, and whether they hand uncertain cases to a person. Work in progress.

## Task sets

- Supplier-invoice decisions: Malaysia and Singapore (in progress). Spec: [v0.9](docs/task-sets/ap-invoices-my-sg/spec-v0.9.md), tax rules: [v0.9](docs/task-sets/ap-invoices-my-sg/tax-rules-v0.9.md)

## Tracks

- Decision track: a model gets the full case file
- Agent track: an agent starts with only the document and looks up the rest in a simulated company system

## Data

- Public dataset: [sgsystems/decision-benchmark-ap-my-sg](https://huggingface.co/datasets/sgsystems/decision-benchmark-ap-my-sg) on Hugging Face, in the collection "SG Systems Decision Benchmark". Train and test splits only.
- The hidden split is never published. It is used only for verified leaderboard runs.

## Results

- How to submit: [docs/submitting-results.md](docs/submitting-results.md)

## Changelog

- [CHANGELOG.md](CHANGELOG.md)

## Licence

- Code: Apache-2.0 (see [LICENSE](LICENSE))
- Data: CC BY 4.0 (see [LICENSE-DATA](LICENSE-DATA))
