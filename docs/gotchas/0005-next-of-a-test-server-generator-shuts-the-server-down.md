---
status: active
date: 2026-10-25
tags: [tests, http, false-pass]
---
# `next(_serve(...))` in a test shuts the fake server down at once

## Symptom
A test of a command that talks to a fake HTTP server passes, but only because the server is
already gone: the command gets "connection refused", exits 1, and the test expected a failure.
The same call with a healthy server and an expected pass fails with "the service did not answer".

## What to do
A fixture written as a generator (`yield` inside a `try` / `finally` that stops the server) stops
the server as soon as the generator is garbage collected, and `url = next(_serve(routes))` drops
the generator on the next line. Keep it alive for the whole test: use it as a context manager
(`with _server(routes) as url:`) or as a pytest fixture.

A test that expects a failure must also assert the reason (for example that the message names
`/health answered 503` and not "did not answer"); otherwise it passes with the server down.
Found in `tests/tooling/test_check_live.py` on 2026-10-25, where three existing tests had been
passing for the wrong reason.
