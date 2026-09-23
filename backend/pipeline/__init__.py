"""Background data pipeline: scrape -> clean -> features -> predict -> warm -> notify.

Stages are separate, testable functions (Prompt B.5) orchestrated by
`python -m pipeline.run --stage <name>` and scheduled by `pipeline.scheduler`.
"""
