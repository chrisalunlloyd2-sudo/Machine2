


ArchivalMoe
agent_db.py — ONE uniform DB attachment + retrieve/submit schema + BM25 for every MoA agent.

branch main  ·  32 Python modules  ·  generated 2026-06-23

Overview
agent_db.py — ONE uniform DB attachment + retrieve/submit schema + BM25 for every MoA agent.
Architecture
  .gitignore
  Blueprint.md
  CLAUDE.md
  MOE_BLUEPRINT.md
  MoeGUI_BLUEPRINT.md
  README.md
  context_injector.py
  conv_map.py
  file_watcher.py
  genetic_compare.py
  genetic_fitness.py
  kqml.py
  agents/
    __init__.py
    agent_db.py
    backup_agent.py
    binary_agent.py
    embed_agent.py
    github_agent.py
    graph_agent.py
    llm_agent.py
    memory_agent.py
    onedrive_agent.py
    project_agent.py
    project_scaffold.py
  crawler/
    __init__.py
    playwright_crawler.py
  tests/
    test_moe_core.py
Dependencies
ctransformers, handshake_watcher, headless, httpx, kqml_bridge, kqml_hook, numpy, playwright, pytest, sentence_transformers, sovereign_daemons, watchdog
Modules
agents/agent_db.py
agent_db.py — ONE uniform DB attachment + retrieve/submit schema + BM25 for every MoA agent.
class AgentDB  — submit, retrieve, stats
roster_stats()
agents/backup_agent.py
BackupAgent — restore from any backup by prompt. OneDrive + local + cross-machine.
list_backups()
restore_agents(timestamp)
onedrive_360()
run(query)
agents/binary_agent.py
BinaryAgent — compile/decompile, dependency mapping, execution time profiling.
decompile_java(class_file)
compile_java(src_file, output_dir)
scan_deps_python(project_path)
install_deps(project_path)
profile_exec(cmd)
run(query)
agents/embed_agent.py
Embed Agent — semantic vector search via sentence-transformers.
Embeddings stored as numpy float32 blobs in code.db.
Normalized at encode time so cosine = dot product (fast).
store(source, source_id, text) — Embed text and upsert into code.db embeddings table.
search_similar(query, top_k) — Embed query, cosine-rank all stored embeddings, return top_k.
count() — How many embeddings are indexed.
run(query) — Moe pipeline entry — semantic similarity search.
agents/github_agent.py
GitHubAgent — permanent GitHub auth + repo management + archival.
Uses gh CLI (GCM-backed). Never asks for auth. Token stored in Windows Credential Manager.
confirm_push(repo_name, local_sha, repo_dir) — Confirm a push actually landed on the remote (the user's "check each step").
auth_status()
auth_permanent_setup(token) — Store PAT permanently in GCM. Call once with a long-lived token.
list_repos(limit)
sync_all()
mirror_repo(repo_name)
import_to_db() — Pull all repos from GitHub and upsert into projects.db.
commit_and_push(repo_path, message, files) — Stage, commit, push. Uses existing GCM auth — never asks for token.
auto_push_all_dirty() — Scan all local Viper repos, commit+push any with uncommitted changes.
run(query)
agents/graph_agent.py
Graph Agent — query the entity-edge knowledge graph in graph.db.
Answers: "how does X relate to Y", "what depends on Z", "what does project X use"
run(query)
agents/llm_agent.py
llm_agent.py — Viper Tier-3 LLM Synthesis Agent
is_available()
direct_chat(query, system_prompt) — Pure LLM response — no BM25 context. For conversational and general queries.
synthesize(query, agent_results, model) — Synthesize results from specialist agents into one coherent answer.
run(query, agent_results) — Entry point matching other agent signatures.
agents/memory_agent.py
Memory Agent — Moe episodic + semantic memory (moe_memory.py).
Handles: "what did we decide about X", "remember X", "do you know about Y",
         "how did we solve Z last time", "what do you remember about..."
run(query)
agents/onedrive_agent.py
OneDriveAgent — 360 view of OneDrive + ViperNote BM25 search.
bm25_notes(query)
tree_view(path, max_depth)
run(query)
agents/project_agent.py
ProjectAgent — answers all project status/next-action queries from projects.db.
Pure SQLite. No LLM needed. Answers in milliseconds.
run(query)
agents/project_scaffold.py
project_scaffold.py — Live Project Inspector and Editor for Moe
list_projects() — Return all registered projects from projects.db.
find_project(name_or_path) — Find a project by partial name or exact path.
get_live_status(project_name) — Full machine-readable status of a project.
status_report(project_name) — Human-readable status report for a project.
all_projects_status() — Machine-language status snapshot of ALL projects. Used for MoE scaffold context.
read_file(project_name, relative_path) — Read a file from a project. Returns content or error.
list_files(project_name, subdir, ext) — List files in a project, optionally filtered by subdirectory or extension.
apply_patch(project_name, relative_path, new_content, reason) — Apply a new file content to a project file.
run(query) — Entry point called by moe_core.project_agent().
agents/prompt_agent.py
Prompt Agent — retrieves the best-fit prompt pattern from prompts.db via BM25.
Also handles template filling and usage tracking.
find_prompt(query, category, top_k) — BM25 search over prompt_fts (OR-keyword mode for natural language). Returns top_k matches.
fill_template(prompt) — Fill {placeholders} in user_template with provided kwargs.
log_usage(prompt_id, success, elapsed_ms) — Increment use_count and update rolling success_rate.
save_pattern(name, category, system_prompt, user_template, tags) — Save a new learned pattern to prompts.db.
run(query) — Moe pipeline entry: find best prompt pattern for a task.
agents/search_agent.py
SearchAgent — BM25 research.db + Playwright web search + crawl pipeline.
run(query)
agents/tool_agent.py
ToolAgent — tree-of-knowledge tool recommendations from tools.db.
run(query)
agents/update_agent.py
update_agent.py — Continuous background improvement loop.
class UpdateAgent  — start, stop, _loop
start_background() — Call once from moe_server.py to start the background loop.
pending_count()
set_status(update_id, status, comment)
pending_updates(limit)
context_injector.py
context_injector.py — Topology-aware context injection for all queries.
get_topology_cache()
get_topology_context(max_chars) — Return compact topology string for injection into synthesis prompts.
extract_performatives(text) — Extract action items, requests, questions, and bug reports from text.
route_performatives(items, project) — Route extracted performatives to the right place:
extract_and_route(chat_text, project) — Full pipeline: extract performatives from chat + route to agents.
query_pages(query, project, limit, max_chars) — BM25 search over indexed file pages (from file_segmenter.py).
start_background_refresh() — Warm the topology cache in background every 60s.
conv_map.py
conv_map.py — Conversation Symbolic Map + Markov Logic + Lyapunov Convergence
Blueprint steps 804-816 (a15436d.md).
class MarkovMatrix  — _load_from_db, record, probs, next_likely
class ConvMap  — transition, update_v, is_converging, is_diverging, corrective_hint, ascii_map, kqml_header, synthesis_prefix, persist_snapshot
infer_state(query) — Classify query text into one of the 8 FSM states.
lyapunov_v(ema_density, ema_refusal, state_dist) — V(X) = 0.4 * ema_density + 0.4 * ema_refusal + 0.2 * H_norm
crawler/playwright_crawler.py
playwright_crawler.py — Viper E2E Web Crawler & Research Indexer
class CrawlResult
crawl_url(url, force) — Crawl a single URL with Playwright. Caches result in research.db.
deep_crawl(seed_url, max_depth, max_pages, same_domain) — Breadth-first crawl starting from seed_url.
search_duckduckgo(query, max_results) — Search DuckDuckGo (HTML, no API key).
search_and_crawl(query, max_results, crawl) — Full pipeline:
bm25_search(query, top_k) — Search already-crawled content in research.db via BM25 FTS5.
file_watcher.py
file_watcher.py — watch C:\Viper\agents\ for config changes and auto-archive them.
Uses watchdog. Run as a background daemon.
archive_now(label) — Snapshot the entire agents/ directory to backups/agents/<timestamp>/.
watch()
genetic_compare.py
genetic_compare.py — Genetic code quality scorer and champion tracker.
Scores code blocks on multiple axes, keeps the best "champion" per (project, area).
Repeated improvement until no better version found.
extract_code_blocks(text) — Extract all ```...``` fenced code blocks from text.
quality_score(code) — Multi-axis quality score. Higher = better.
best_block(blocks) — Return (best_block, score) from a list of code blocks.
get_champion(project, area) — Return current champion for (project, area), or None.
challenge_champion(project, area, challenger_code) — Compare challenger against current champion.
run_genetic_loop(project, area, candidates, max_rounds) — Iteratively challenge champion with candidates until no improvement.
genetic_fitness.py
genetic_fitness.py — Viper Genetic Fitness Scoring System
class FitnessScore  — compute, grade
score(code, name, entity_id, correctness, performance, coverage, notes) — Score a piece of code or artifact.
score_and_save(code, name, description, language, correctness, performance, coverage) — Score code, save to code.db if fitness >= 0.5 (never-make-twice).
top_by_fitness(n) — Return top-n code entries by fitness score.
report(fs) — Human-readable fitness report (ASCII-safe for Windows console).
kqml.py
kqml.py — KQML Agent Communication Language for Viper MoE
Full ACL structure with modern NLP kernel routing.
class KQMLRouter  — register, on_broadcast, dispatch, subscribe, publish
message(performative, sender, receiver, content, ontology, language, in_reply_to)
ask(sender, receiver, content, ontology)
tell(sender, receiver, content, ontology)
inform(sender, receiver, content, ontology)
request(sender, receiver, content, ontology)
achieve(sender, receiver, content, ontology)
error(sender, receiver, content, in_reply_to)
fitness_report(sender, score, metadata)
send_ask(from_agent, to_agent, query) — Send an ask and return a formatted string for logging.
send_tell(from_agent, to_agent, fact, ontology)
get_message_log(n)
lexical_grabber.py
lexical_grabber.py — Exhaustive Lexical Pattern Grabber + Mathematical Thought Tracker
class ScanResult
class ThoughtTracker  — record, should_suppress, should_reroute, suppression_prompt, stats, _persist
class RecursiveThought  — feed, population, print_population
class PatternLearner  — _clean, _update_one, update, top_patterns, generate_targeted_hint, inject_status, full_injection, _persist
scan(text) — Scan a response for all lexical patterns.
strip_patterns(text, categories) — Remove matched phrases from text (optional utility).
main.py
ArchivalMoe (Moe) — GitHub management and agent network archival.
audit() — List all GitHub repos and check local clone status.
mirror(repo_name) — Mirror a GitHub repo to backups/github/{repo}/{timestamp}.
archive_agents() — Snapshot all agent configs in C:\Viper\agents\ to backups/agents.
sync_all() — Pull latest on all locally cloned repos.
moa_orchestrator.py
moa_orchestrator.py — Mixture of Agents: proposer/aggregator hierarchy.
moa_propose(project, project_summary) — Run 3 proposers + 1 aggregator against ONE real function from the project.
run_batch(projects, count) — Generate `count` proposals for rotating projects. Returns list of dicts.
moe_core.py
Moe — Mixture of Agents core router.
Tiered pipeline: hash cache → BM25 intent → parallel agents → synthesis.
RAID: every result dual-written to telemetry.db before returning.
project_agent(query) — Answers questions about project status, tasks, what's next, roadmap.
github_agent(query) — GitHub repo management, sync, auth, archival.
backup_agent(query) — Backup restore, machine images, OneDrive recovery.
onedrive_agent(query) — OneDrive 360 view, ViperNote search, document lookup.
binary_agent(query) — Compile, decompile, dependency install, exec time profiling.
search_agent(query) — BM25 research.db + Playwright web crawl for novel approaches.
tool_agent(query) — tools.db tree-of-knowledge: best tool for the job.
embed_agent(query) — Semantic vector search across all indexed Viper artifacts.
graph_agent(query) — Entity-edge knowledge graph: project relationships, dependencies, DB access.
prompt_agent(query) — Retrieve best prompt pattern from prompts.db for a given task.
memory_agent(query) — Episodic + semantic memory: recall facts, decisions, lessons, past cases.
ask_async(query, project)
ask(query, project) — Synchronous entry point.
moe_memory.py
moe_memory.py — Moe's Episodic + Semantic Memory System
remember(kind, key, value, source, confidence, project) — Store a memory. Idempotent: same kind+key+value → INSERT OR IGNORE.
update(kind, key, new_value, source, confidence) — Update existing memory (overwrites value for kind+key pair).
forget(kind, key) — Remove a memory (semantic refinement / correction).
recall(key, kind, limit) — Retrieve memories by key (exact or partial match).
recall_recent(kind, limit) — Most recently updated memories, optionally filtered by kind.
build_context(query, max_chars) — Pull relevant memories for a query and format as context for LLM prompt.
seed_lore() — Seed Moe's self-model on first run.
self_reflect(recent_interactions) — Moe's self-reflection step: review recent interactions, extract durable facts.
run(query) — Called by memory_agent in moe_core. Handles:
moe_server.py
Moe JSON-over-stdio server — persistent process for MoeGUI Java bridge.
Reads JSON lines from stdin, writes JSON answer lines to stdout.
main()
nod.py
nod.py — NOD (Name, Occupation, Designation) Agent Registry for Viper MoE
class NODEntry
get(name)
all_agents()
by_ontology(ontology)
capabilities(name) — Return human-readable NOD description for an agent.
who_handles(query) — Lightweight keyword-based capability lookup (BM25-lite).
update_stats(name, latency, error) — Update call stats for an agent. Called by moe_core after each dispatch.
update_fitness(name, score) — Set genetic fitness score for an agent (0-1).
register(entry) — Register or update a NOD entry.
dump() — Return full registry as JSON for inspection.
tests/test_moe_core.py
Tests for moe_core.py — scientific method: each component tested in isolation.
Run: python -m pytest tests/ -v
test_hash_deterministic()
test_hash_case_insensitive()
test_hash_length()
test_fts_safe_strips_special()
test_fts_safe_keeps_words()
test_intent_github_keywords()
test_intent_backup_keywords()
test_intent_search_keywords()
test_intent_project_default()
test_intent_memory_keywords()
test_intent_tool_keywords()
test_intent_multiple_signals()
test_intent_returns_list()
test_synthesize_single_agent()
test_synthesize_multiple_agents_fallback()
Public API
Status
Branch: main
Last commit: 2026-06-23 20:41:10 -0600
Recent commits
68f43ad feat(agents): uniform DB attachment + submit/retrieve/BM25 schema (verified) for the MoA agents
fac61e6 [Moe autonomous] ArchivalMoe 2026-06-20 16:34
39538b5 [Moe autonomous] ArchivalMoe 2026-06-20 09:18
c9eeb99 [Moe autonomous] ArchivalMoe 2026-06-20 08:41
d567c91 [Moe autonomous] ArchivalMoe 2026-06-20 08:09
b66b76c [Moe autonomous] ArchivalMoe 2026-06-20 07:58
fe3aacc [Moe autonomous] ArchivalMoe 2026-06-20 03:58
8c8d038 [Moe autonomous] ArchivalMoe 2026-06-20 02:52
Module | Function | Signature
agent_db | roster_stats | roster_stats()
backup_agent | list_backups | list_backups()
backup_agent | onedrive_360 | onedrive_360()
backup_agent | restore_agents | restore_agents(timestamp)
backup_agent | run | run(query)
binary_agent | compile_java | compile_java(src_file, output_dir)
binary_agent | decompile_java | decompile_java(class_file)
binary_agent | install_deps | install_deps(project_path)
binary_agent | profile_exec | profile_exec(cmd)
binary_agent | run | run(query)
binary_agent | scan_deps_python | scan_deps_python(project_path)
context_injector | extract_and_route | extract_and_route(chat_text, project)
context_injector | extract_performatives | extract_performatives(text)
context_injector | get_topology_cache | get_topology_cache()
context_injector | get_topology_context | get_topology_context(max_chars)
context_injector | query_pages | query_pages(query, project, limit, max_chars)
context_injector | route_performatives | route_performatives(items, project)
context_injector | start_background_refresh | start_background_refresh()
conv_map | infer_state | infer_state(query)
conv_map | lyapunov_v | lyapunov_v(ema_density, ema_refusal, state_dist)
embed_agent | count | count()
embed_agent | run | run(query)
embed_agent | search_similar | search_similar(query, top_k)
embed_agent | store | store(source, source_id, text)
file_watcher | archive_now | archive_now(label)
file_watcher | watch | watch()
genetic_compare | best_block | best_block(blocks)
genetic_compare | challenge_champion | challenge_champion(project, area, challenger_code)
genetic_compare | extract_code_blocks | extract_code_blocks(text)
genetic_compare | get_champion | get_champion(project, area)
genetic_compare | quality_score | quality_score(code)
genetic_compare | run_genetic_loop | run_genetic_loop(project, area, candidates, max_rounds)
genetic_fitness | report | report(fs)
genetic_fitness | score | score(code, name, entity_id, correctness, performance, coverage, notes)
genetic_fitness | score_and_save | score_and_save(code, name, description, language, correctness, performance, coverage)
genetic_fitness | top_by_fitness | top_by_fitness(n)
github_agent | auth_permanent_setup | auth_permanent_setup(token)
github_agent | auth_status | auth_status()
github_agent | auto_push_all_dirty | auto_push_all_dirty()
github_agent | commit_and_push | commit_and_push(repo_path, message, files)
github_agent | confirm_push | confirm_push(repo_name, local_sha, repo_dir)
github_agent | import_to_db | import_to_db()
github_agent | list_repos | list_repos(limit)
github_agent | mirror_repo | mirror_repo(repo_name)
github_agent | run | run(query)
github_agent | sync_all | sync_all()
graph_agent | run | run(query)
kqml | achieve | achieve(sender, receiver, content, ontology)
kqml | ask | ask(sender, receiver, content, ontology)
kqml | error | error(sender, receiver, content, in_reply_to)
kqml | fitness_report | fitness_report(sender, score, metadata)
kqml | get_message_log | get_message_log(n)
kqml | inform | inform(sender, receiver, content, ontology)
kqml | message | message(performative, sender, receiver, content, ontology, language, in_reply_to)
kqml | request | request(sender, receiver, content, ontology)
kqml | send_ask | send_ask(from_agent, to_agent, query)
kqml | send_tell | send_tell(from_agent, to_agent, fact, ontology)
kqml | tell | tell(sender, receiver, content, ontology)
lexical_grabber | scan | scan(text)
lexical_grabber | strip_patterns | strip_patterns(text, categories)
llm_agent | direct_chat | direct_chat(query, system_prompt)
llm_agent | is_available | is_available()
llm_agent | run | run(query, agent_results)
llm_agent | synthesize | synthesize(query, agent_results, model)
main | archive_agents | archive_agents()
main | audit | audit()
main | mirror | mirror(repo_name)
main | sync_all | sync_all()
memory_agent | run | run(query)
moa_orchestrator | moa_propose | moa_propose(project, project_summary)
moa_orchestrator | run_batch | run_batch(projects, count)
moe_core | ask | ask(query, project)
moe_core | ask_async | ask_async(query, project)
moe_core | backup_agent | backup_agent(query)
moe_core | binary_agent | binary_agent(query)
moe_core | embed_agent | embed_agent(query)
moe_core | github_agent | github_agent(query)
moe_core | graph_agent | graph_agent(query)
moe_core | memory_agent | memory_agent(query)
moe_core | onedrive_agent | onedrive_agent(query)