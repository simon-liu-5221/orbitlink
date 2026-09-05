"""Pure algorithm layer.

RULE (CLAUDE.md #1, ADR-0003): modules in this package must not import
``app.db``, ``app.api``, ``app.jobs``, ``app.services``, ``app.ingest``,
``sqlalchemy``, ``fastapi``, ``httpx``, ``redis``, or read environment
variables. Inputs: ``networkx`` graphs, ``pandas`` DataFrames, primitives,
dataclasses. Outputs: dataclasses / dicts / DataFrames. Enforced by
import-linter in CI.
"""
