# VIPER Retrieval Upgrade Notes

These notes capture the research pass behind the upgraded chooser/database
retrieval epoch.

## Sources Checked

- Retrieval-Augmented Generation, Lewis et al.:
  https://arxiv.org/abs/2005.11401
- Self-RAG, Asai et al.:
  https://arxiv.org/abs/2310.11511
- RAGAS evaluation:
  https://arxiv.org/abs/2309.15217
- LangChain retrieval docs:
  https://docs.langchain.com/oss/python/langchain/retrieval
- LlamaIndex RAG docs:
  https://developers.llamaindex.ai/python/framework/understanding/rag/
- Google Cloud GenAI Databases Retrieval App:
  https://cloud.google.com/blog/products/databases/introducing-sample-genai-databases-retrieval-app

## Compared Logic

RAG baseline:

```text
query -> retrieve context -> generate answer
```

Problem in VIPER:

```text
query -> loose keyword DB rows -> prompt noise -> weak/flat answer
```

Industry pattern to adapt:

```text
query rewrite/expansion
  -> hybrid retrieval
  -> trust/rerank
  -> context compression
  -> sufficiency/critique
  -> grounded generation or more retrieval
```

Google Cloud's sample retrieval app adds the production shape:

```text
LLM/application orchestration
  -> ReACT/tool trigger
  -> separate retrieval service/API
  -> database-backed structured + semantic retrieval
  -> prompt augmentation with only relevant data
  -> security, scale, quality, latency, cost controls
```

Self-RAG logic adds a useful control point:

```text
retrieve only when needed
critique retrieved evidence
adapt behavior to task requirements
```

RAGAS/ARES-style evaluation gives the test dimensions:

```text
context relevance
answer faithfulness
answer relevance
```

## VIPER Domain Upgrade

The chooser now builds a purpose-first lens:

```text
PURPOSE
  -> DB_RETRIEVAL_CARDS
  -> WEB_SNIPPET_PLAN
  -> TASK_DIRECTIONS
  -> OUTPUT_RULES
```

Genetic comparison winner for the current VIPER domain:

```text
separate retrieval sidecar/API
+ purpose-first lens
+ local DB/ledger first
+ trust/rerank/compress cards
+ web snippet only when sufficiency is low
+ ReACT-style task directions
+ Java SDK persistent evaluation
```

Why this wins:

- Better than raw prompt stuffing: lower noise and lower latency.
- Better than pure chat: grounded in current project DB and ledger.
- Better than full webcrawl every turn: safer, cheaper, and less noisy.
- Better than self-mutation: auditable and approval-gated.

Local approximation of hybrid retrieval:

```text
ask text
  -> token extraction
  -> query variants
  -> prioritized VIPER tables
  -> broad table scan
  -> source trust weighting
  -> route-fit weighting
  -> 15-word evidence cards
  -> evidence sufficiency score
```

Trusted local source priority:

```text
CODE_BLOCKCHAIN_DB_SUCCESS
LOGIC_BLOCKCHAIN_QUEUE_SHIPPED
BLOCKCHAIN_LEDGER_SUCCESS
USER_TOPOLOGY_PROFILE
CHAT_MEMORY
TOPO_APPROVAL_REPORTS
KAROO_CANDIDATES
TOPO_CHUNKS
GLOBAL_TODO_QUEUE
GLOBAL_ACL_MESSAGES
TRIPLET_MANIFOLD
RAG_MANIFOLD
WEBCRAWL_RESEARCH_REQUESTS
```

Web/research is not raw prompt stuffing. It must be reduced to:

```text
claim
source_url_or_local_path
source_sha256
applicability
risk
```

## Applied System Changes

- Added query variants for chat/planning/build.
- Added source trust weights.
- Added route-fit scoring.
- Added compound rerank score.
- Added 15-word DB evidence cards.
- Added evidence sufficiency status.
- Added web snippet plan.
- Added task directions directly inside the Fabric lens.
- Wired chat route to receive the compact active lens.

## Next Epoch

When resources allow, upgrade from keyword hybrid scoring to:

```text
BM25/keyword score
+ embedding/vector similarity
+ graph/topology proximity
+ user preference fit
+ success/failure outcome history
+ latency/resource cost
```

Promotion should be tested with:

```text
same prompt before/after
context relevance
answer relevance
faithfulness to cards
latency
token cost
```
