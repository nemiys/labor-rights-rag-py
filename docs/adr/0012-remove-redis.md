# ADR-0012: Remove Redis, and clean up what the project skeleton left behind

## Status
Accepted.

## Context
The Compose stack, the settings and the README listed Redis, but no code used it: the
`redis_url` setting was read nowhere, there was no Redis client in the dependencies, and no
test or CI step touched it. It came in with the first project skeleton, planned as the
queue of pages for a crawler. This project has no crawler (a closed list of laws and an
API), so the reason was gone before the first commit.

An audit for other leftovers (unused modules, functions, settings fields and dependencies)
found the code clean, and these remains in the configuration:
- the `httpx2` dev dependency, which nothing imports (`httpx` is the one in use);
- the package description in `pyproject.toml`, which still described technical documentation;
- the Postgres user, password and database called `docs`, from the old project name.

## Decision
- Remove the Redis service, its setting, and every mention of it.
- Remove `httpx2`, fix the package description, and rename the Postgres user, password and
  database to `labor`. These are local development credentials, not secrets.
- Redis can come back if a real need appears: caching embeddings of repeated questions, or a
  rate limit in front of a public demo. It would then be justified in its own ADR.

## Consequences
- One container less to start and to explain.
- Whoever has the old Postgres volume must recreate it (the credentials changed).
