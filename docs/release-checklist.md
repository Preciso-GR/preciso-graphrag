# Release checks

Use this checklist before selecting an image for production. Record evidence for
each completed item. An unchecked item remains an open gate.

## Code and package

- [ ] Review the change and its compatibility impact.
- [ ] Pass the supported Python-version test matrix.
- [ ] Pass lint, compilation, and summary integrity guards.
- [ ] Build the locked test and runtime container stages.
- [ ] Verify installed-wheel imports outside the source checkout.
- [ ] Review dependency and base-image vulnerabilities.
- [ ] Verify that credentials, private inputs, and development tools are excluded.

## Data and operation

- [ ] Pin the embedding model revision and verify its fingerprint.
- [ ] Complete a backup and restore drill in a fresh directory.
- [ ] Test release rollback with compatible persisted artifacts.
- [ ] Test provider failure, cancellation, process interruption, and startup recovery.
- [ ] Verify ownership and persistent-volume permissions.
- [ ] Verify client disconnect and shutdown behavior.
- [ ] Establish memory, disk, latency, and request-admission budgets.
- [ ] Verify log redaction and cache retention.

## Evidence retrieval

- [ ] Freeze a reviewed corpus and required source spans.
- [ ] Evaluate held-out questions with the selected semantic model.
- [ ] Include bridge evidence, contradictions, and unsupported questions.
- [ ] Verify references and answer support separately from retrieval relevance.
- [ ] Record quality, latency, token, and memory tradeoffs.

The current synthetic [pilot](retrieval-pilot.md) covers direct chunk retrieval.
It does not complete these quality gates. Use [production readiness](production-readiness.md)
for implemented controls and known limitations.
