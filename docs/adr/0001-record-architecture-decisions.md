# ADR-0001: Record architecture decisions

## Status
Accepted

## Context
This project makes many technical choices (chunking strategy, how to merge
search results, which embedding model, how to build the prompt). The reasons
behind them are easy to forget and hard to reconstruct later.

## Decision
Each significant decision gets a short numbered file in `docs/adr/`, named
`NNNN-short-title.md`, with these sections: Status, Context, Decision,
Alternatives considered, Consequences. Records are never rewritten; a changed
decision gets a new ADR that supersedes the old one.

## Alternatives considered
- **Notes in the README**: gets crowded fast and mixes "what it does" with
  "why it was built this way".
- **No written record**: cheapest now, but the reasoning is lost and cannot be
  reviewed or defended later.

## Consequences
A few minutes of writing per decision. In exchange, every choice can be
explained and traced back to the alternatives that were considered.
