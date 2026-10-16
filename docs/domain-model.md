# Preciso GraphRAG

Preciso turns a corpus of source documents into a local, evidence-linked knowledge graph. This glossary defines the document lifecycle language used by users, agents, and maintainers.

## Language

**Source Document**:
A user-provided document whose facts may contribute entities, relationships, and evidence to the graph.
_Avoid_: Data file, input blob

**Extraction**:
The reviewed structured representation of one source document, containing its entities, relationships, chunks, and evidence links.
_Avoid_: Parsed graph, generated graph

**Document ID**:
The stable, unique identity of a source document across replays and explicit replacements.
_Avoid_: Version ID, chunk prefix

**Additive Ingestion**:
The operation that adds an extraction's contributions to the existing graph without removing earlier contributions.
_Avoid_: Graph replacement, document update

**Recovery Replay**:
An identical repeat of a previously attempted ingestion after an operational failure.
_Avoid_: Replacement, correction, update

**Graph Artifacts**:
The complete generated representation of the current graph, including graph structure, evidence stores, embeddings, summaries, and metadata.
_Avoid_: Source corpus, extraction backup

**Contribution Ledger**:
The retained current extraction for each tracked document, plus document versions
and persistent graph editing rules. It permits reconstruction of derived stores.

**Workspace Revision**:
An integer that changes when document contributions or graph editing rules change.
A destructive commit must use the revision returned by its preview.

**Document Replacement**:
An explicit operation that removes one document's previous contributions and
rebuilds derived data with its complete corrected extraction.

**Node Isolation**:
A reversible rule that withholds a canonical node, its incident relationships,
and cited evidence passages from the active derived stores. It is not access control.

**Canonical Node ID**:
The existing entity-name key used for graph identity. A display rename preserves
this key. An explicit merge redirects one canonical ID into another.

See [document lifecycle](document-lifecycle.md) for implemented operations and limits.

**Complete Valid Corpus**:
Every current source document and reviewed extraction that should be represented in the graph, excluding flawed or superseded versions.
_Avoid_: Latest document, changed files

**Full Rebuild**:
Creation of new graph artifacts from an empty graph using the complete valid corpus.
_Avoid_: Reingestion, replacement, partial rebuild
