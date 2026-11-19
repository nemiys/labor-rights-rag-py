# ADR-0013: A per-client limit on /ask, kept in memory

## Status
Accepted.

## Context
`POST /ask` was open to anyone with no limit. Every question that passes the similarity
threshold calls the answer model: with `ANSWERER=claude` that costs money per question, and
with a free tier it uses up a shared quota. One script sending questions in a loop could run
up the bill or lock everyone else out. ADR-0012 named a rate limit in front of a public demo
as the reason Redis might come back.

## Decision
- **A sliding window per client address**: at most `ASK_LIMIT` questions (10 by default) in
  any `ASK_WINDOW_SECONDS` (60) ending now. Over the limit the answer is `429` with
  `Retry-After`, and the model is not called.
- **Kept in the memory of the process** (`api/rate_limit.py`): a queue of request times per
  address. A refused request is not counted, so a client that keeps trying is not blocked
  forever.
- **The address is the connection's**, never `X-Forwarded-For`, which any client can set.
  Behind a proxy, uvicorn's `--forwarded-allow-ips` fills in the real address.
- **The answer model being down** (after its own retries) is a `503` with `Retry-After`,
  not a `500`, so the page can say "try again later" and the log shows the cause.

## Alternatives considered
- **Redis, as in `tinyurl-py`**: one limit shared by several application processes, and it
  survives a restart. It adds a service to run for a demo that runs as one process. If the
  demo ever runs as several processes, this is the change to make, behind the same
  dependency.
- **A limit at a gateway (nginx, a cloud WAF)**: the better place in production, but it
  depends on how the demo is deployed and cannot be tested with the application.
- **No limit until there is a public demo**: simplest, but the endpoint would be exposed the
  day the demo goes up.

## Consequences
- With several processes, each keeps its own count: the real limit is the per-process limit
  times the number of processes.
- The counts are lost on restart, and an address that stops asking keeps a few bytes until
  the process restarts. At demo scale both are acceptable.
- People behind one shared address (an office) share one allowance.
