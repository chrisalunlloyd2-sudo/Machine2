package com.viper.notes;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

public class ViperLabSuiteServer {
    private static final String SDK_VERSION = "0.4.1-training-lab";
    private static final int PORT = 18181;
    private static final Path ROOT = Paths.get("C:\\Users\\viper\\VIPER_JAVA_RISC");
    private static final Path SUITE_ROOT = ROOT.resolve("java_notes_suite");
    private static final Path DATA_DIR = SUITE_ROOT.resolve("data");
    private static final Path SETTINGS_FILE = DATA_DIR.resolve("sdk_settings.json");
    private static final Path TEST_LOG = DATA_DIR.resolve("system_tests.jsonl");
    private static final Path AB_LOG = DATA_DIR.resolve("ab_tests.jsonl");
    private static final Path TRAINING_LOG = DATA_DIR.resolve("training_runs.jsonl");
    private static final Path TRAINING_EPOCH_LOG = DATA_DIR.resolve("recursive_training_epochs.jsonl");
    private static final Path LOIHI_LOG = DATA_DIR.resolve("loihi_experiments.jsonl");
    private static final Path BENCHMARK_LOG = DATA_DIR.resolve("benchmark_snapshots.jsonl");
    private static final Path ASCII_EPOCH_LOG = DATA_DIR.resolve("ascii_epoch_queue.jsonl");
    private static final Path EPOCH_UPGRADE_LOG = DATA_DIR.resolve("epoch_upgrade_proofs.jsonl");
    private static final Path PERSISTENCE_LOG = DATA_DIR.resolve("persistence_events.jsonl");
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();

    public static void main(String[] args) throws Exception {
        ensurePersistence();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", new PageHandler());
        server.createContext("/health", new HealthHandler());
        server.createContext("/api/state", new StateHandler());
        server.createContext("/api/settings", new SettingsHandler());
        server.createContext("/api/run-test", new RunTestHandler());
        server.createContext("/api/ab-test", new AppendJsonHandler(AB_LOG, "ab_test"));
        server.createContext("/api/training", new TrainingHandler());
        server.createContext("/api/recursive-training", new RecursiveTrainingHandler());
        server.createContext("/api/loihi-experiment", new AppendJsonHandler(LOIHI_LOG, "loihi_experiment"));
        server.createContext("/api/benchmarks", new BenchmarksHandler());
        server.createContext("/api/benchmark-snapshot", new BenchmarkSnapshotHandler());
        server.createContext("/api/ascii-epochs", new AsciiEpochHandler());
        server.createContext("/api/epoch-upgrade-proof", new EpochUpgradeProofHandler());
        server.createContext("/api/log-tail", new LogTailHandler());
        server.createContext("/api/design", new DesignHandler());
        server.setExecutor(null);
        server.start();
        appendJsonLine(PERSISTENCE_LOG, mapOf(
                "event", "lab_suite_start",
                "port", PORT,
                "root", ROOT.toString()
        ));
        System.out.println("VIPER JAVA SDK ACTIVE: http://127.0.0.1:" + PORT);
    }

    private static void ensurePersistence() throws IOException {
        Files.createDirectories(DATA_DIR);
        if (!Files.exists(SETTINGS_FILE)) {
            String defaults = "{\n"
                    + "  \"mode\": \"planning\",\n"
                    + "  \"chatReplyTokens\": 512,\n"
                    + "  \"planningReplyTokens\": 1024,\n"
                    + "  \"buildReplyTokens\": 1536,\n"
                    + "  \"karooProposalOnly\": true,\n"
                    + "  \"loihiMode\": \"simulated_spike_topology_sidecar\",\n"
                    + "  \"heartbeatSeconds\": 300,\n"
                    + "  \"autoAdvanceSuccess\": 99.99,\n"
                    + "  \"autoAdvanceSpeedGain\": 10,\n"
                    + "  \"autoAdvanceResourceDrop\": 10,\n"
                    + "  \"notesDestination\": \"viper_laptop_notes\"\n"
                    + "}\n";
            Files.writeString(SETTINGS_FILE, defaults, StandardCharsets.UTF_8);
        }
        touch(TEST_LOG);
        touch(AB_LOG);
        touch(TRAINING_LOG);
        touch(TRAINING_EPOCH_LOG);
        touch(LOIHI_LOG);
        touch(BENCHMARK_LOG);
        touch(ASCII_EPOCH_LOG);
        touch(EPOCH_UPGRADE_LOG);
        touch(PERSISTENCE_LOG);
    }

    private static void touch(Path path) throws IOException {
        if (!Files.exists(path)) {
            Files.writeString(path, "", StandardCharsets.UTF_8);
        }
    }

    private static class PageHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"GET".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }
            send(exchange, 200, html(), "text/html; charset=utf-8");
        }
    }

    private static class HealthHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            send(exchange, 200, jsonObject(mapOf(
                    "status", "ok",
                    "suite", "viper_java_sdk",
                    "version", SDK_VERSION,
                    "port", PORT,
                    "persistent", true,
                    "timestamp", Instant.now().toString()
            )), "application/json");
        }
    }

    private static class StateHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            Map<String, Object> state = new LinkedHashMap<>();
            state.put("status", "ok");
            state.put("version", SDK_VERSION);
            state.put("timestamp", Instant.now().toString());
            state.put("root", ROOT.toString());
            state.put("dataDir", DATA_DIR.toString());
            state.put("settings", readTextSafe(SETTINGS_FILE, "{}"));
            state.put("counts", mapOf(
                    "systemTests", countLines(TEST_LOG),
                    "abTests", countLines(AB_LOG),
                    "trainingRuns", countLines(TRAINING_LOG),
                    "recursiveTrainingEpochs", countLines(TRAINING_EPOCH_LOG),
                    "loihiExperiments", countLines(LOIHI_LOG),
                    "benchmarkSnapshots", countLines(BENCHMARK_LOG),
                    "asciiEpochs", countLines(ASCII_EPOCH_LOG),
                    "epochUpgradeProofs", countLines(EPOCH_UPGRADE_LOG),
                    "persistenceEvents", countLines(PERSISTENCE_LOG)
            ));
            state.put("services", serviceHealth());
            state.put("logs", mapOf(
                    "system", fileInfo(ROOT.resolve("system_log.txt")),
                    "shipper", fileInfo(ROOT.resolve("logic_blockchain_shipper.log")),
                    "topology", fileInfo(ROOT.resolve("topology_sidecar_loop.log")),
                    "houseStdout", fileInfo(ROOT.resolve("house_inference_stdout.log")),
                    "houseStderr", fileInfo(ROOT.resolve("house_inference_stderr.log"))
            ));
            send(exchange, 200, jsonObject(state), "application/json");
        }
    }

    private static class SettingsHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if ("GET".equals(exchange.getRequestMethod())) {
                send(exchange, 200, readTextSafe(SETTINGS_FILE, "{}"), "application/json");
                return;
            }
            if (!"POST".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }
            String body = readBody(exchange);
            if (body.isBlank()) {
                send(exchange, 400, jsonError("empty_settings_body"), "application/json");
                return;
            }
            Files.writeString(SETTINGS_FILE, body.strip() + "\n", StandardCharsets.UTF_8);
            appendJsonLine(PERSISTENCE_LOG, mapOf("event", "settings_update", "sha256", sha256(body)));
            send(exchange, 200, jsonObject(mapOf("status", "saved", "sha256", sha256(body))), "application/json");
        }
    }

    private static class RunTestHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }
            long start = System.currentTimeMillis();
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("kind", "system_test");
            result.put("timestamp", Instant.now().toString());
            result.put("request", readBody(exchange));
            result.put("services", serviceHealth());
            result.put("durationMs", System.currentTimeMillis() - start);
            result.put("policy", "one variable per test; end-to-end proof preferred");
            result.put("sha256", sha256(jsonObject(result)));
            appendJsonLine(TEST_LOG, result);
            send(exchange, 200, jsonObject(result), "application/json");
        }
    }

    private static class AppendJsonHandler implements HttpHandler {
        private final Path logPath;
        private final String kind;

        AppendJsonHandler(Path logPath, String kind) {
            this.logPath = logPath;
            this.kind = kind;
        }

        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }
            String body = readBody(exchange);
            Map<String, Object> event = new LinkedHashMap<>();
            event.put("kind", kind);
            event.put("timestamp", Instant.now().toString());
            event.put("body", body);
            event.put("sha256", sha256(kind + body + Instant.now()));
            if ("loihi_experiment".equals(kind)) {
                event.put("contract", "Loihi/Lava is a future sidecar: NLP -> topological codes -> spike topology -> code/logic readback.");
                event.put("safety", "simulation/proposal first; no claim of thinking kernel.");
            }
            appendJsonLine(logPath, event);
            appendJsonLine(PERSISTENCE_LOG, mapOf("event", kind + "_append", "sha256", event.get("sha256")));
            send(exchange, 200, jsonObject(mapOf("status", "logged", "kind", kind, "sha256", event.get("sha256"))), "application/json");
        }
    }

    private static class BenchmarksHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"GET".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }
            Map<String, String> query = parseQuery(exchange.getRequestURI().getRawQuery());
            int limit = Math.max(1, Math.min(parseInt(query.getOrDefault("limit", "40"), 40), 200));
            send(exchange, 200, jsonObject(mapOf(
                    "status", "ok",
                    "timestamp", Instant.now().toString(),
                    "current", currentBenchmark("read_only"),
                    "history", readJsonLines(BENCHMARK_LOG, limit),
                    "recursiveTrainingStatus", "active eval training: probes services, asks bridge prefetch, logs candidate/proof; no model-weight mutation submitted here"
            )), "application/json");
        }
    }

    private static class TrainingHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if ("GET".equals(exchange.getRequestMethod())) {
                Map<String, String> query = parseQuery(exchange.getRequestURI().getRawQuery());
                int limit = Math.max(1, Math.min(parseInt(query.getOrDefault("limit", "20"), 20), 100));
                send(exchange, 200, jsonObject(mapOf(
                        "status", "ok",
                        "version", SDK_VERSION,
                        "mode", "active_eval_training",
                        "runs", readJsonFragments(TRAINING_LOG, limit),
                        "policy", "runs real service probes and bridge prefetch; model weights remain untouched"
                )), "application/json");
                return;
            }
            if (!"POST".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }

            long started = System.currentTimeMillis();
            String body = readBody(exchange);
            String dataset = extractJsonString(body, "dataset", "successful_code_and_liked_logic");
            String route = extractJsonString(body, "route", "proposal_only_lens_improvement");
            String changedVariable = extractJsonString(body, "changedVariable",
                    extractJsonString(body, "variable", "retrieval_lens_instruction_card"));
            String objective = extractJsonString(body, "objective", "improve chooser/retrieval usefulness without changing the locked GUI");

            Map<String, Object> before = currentBenchmark("training_before");
            String prompt = trainingPrompt(dataset, route, changedVariable, objective);
            String prefetch = fetchText("http://127.0.0.1:8080/api/predictive/prefetch?q=" + urlEncode(prompt), 8);
            String bridgeBenchmarks = fetchText("http://127.0.0.1:8080/api/benchmarks?limit=5", 8);
            Map<String, Object> afterProbe = currentBenchmark("training_after_probe");
            Map<String, Object> evaluation = evaluateTrainingRun(before, afterProbe, prefetch, bridgeBenchmarks);

            Map<String, Object> run = new LinkedHashMap<>();
            run.put("kind", "training_run");
            run.put("status", "active_eval_logged");
            run.put("version", SDK_VERSION);
            run.put("timestamp", Instant.now().toString());
            run.put("durationMs", System.currentTimeMillis() - started);
            run.put("request", body);
            run.put("dataset", dataset);
            run.put("route", route);
            run.put("changedVariable", changedVariable);
            run.put("objective", objective);
            run.put("phases", List.of(
                    "capture_baseline_benchmark",
                    "probe_bridge_predictive_prefetch",
                    "read_recent_bridge_benchmarks",
                    "score_candidate_against_promotion_gate",
                    "write_training_and_epoch_logs"
            ));
            run.put("candidate", mapOf(
                    "lensDelta", "Prefer real retrieved evidence, concise Qwen chooser lens, and explicit safety gate.",
                    "oneChangedVariable", changedVariable,
                    "trainingPrompt", prompt,
                    "expectedEffect", "fewer thin replies, less raw metadata in lens, clearer task routing"
            ));
            run.put("prefetchProbe", compactStatus(prefetch));
            run.put("bridgeBenchmarkProbe", compactStatus(bridgeBenchmarks));
            run.put("benchmarkBefore", before);
            run.put("benchmarkAfterProbe", afterProbe);
            run.put("evaluation", evaluation);
            run.put("doesMutateModelWeights", false);
            run.put("doesSubmitRecursiveTraining", true);
            run.put("trainingMeaning", "Submits a real Java-lab eval epoch: data is probed, scored, hashed, and logged for the next chooser/Karoo cycle.");
            run.put("promotionGate", "success >= 99.99 and (+10% speed or -10% resources); otherwise record only");
            run.put("promotionDecision", Boolean.TRUE.equals(evaluation.get("promotionEligible")) ? "eligible_for_user_review" : "record_only_more_evidence_needed");
            run.put("sha256", sha256(jsonObject(run)));

            appendJsonLine(TRAINING_LOG, run);

            Map<String, Object> epoch = new LinkedHashMap<>();
            epoch.put("kind", "training_backed_recursive_epoch");
            epoch.put("status", "active_eval_logged");
            epoch.put("timestamp", Instant.now().toString());
            epoch.put("trainingRunSha256", run.get("sha256"));
            epoch.put("changedVariable", changedVariable);
            epoch.put("datasetSlice", dataset);
            epoch.put("scientificMethod", "one changed variable; compare service proof; do not self-apply");
            epoch.put("evaluation", evaluation);
            epoch.put("sha256", sha256(jsonObject(epoch)));
            appendJsonLine(TRAINING_EPOCH_LOG, epoch);

            Map<String, Object> benchmark = currentBenchmark("training_recorded");
            benchmark.put("trainingRunSha256", run.get("sha256"));
            benchmark.put("sha256", sha256(jsonObject(benchmark)));
            appendJsonLine(BENCHMARK_LOG, benchmark);
            appendJsonLine(PERSISTENCE_LOG, mapOf(
                    "event", "active_training_run",
                    "trainingRunSha256", run.get("sha256"),
                    "recursiveEpochSha256", epoch.get("sha256"),
                    "benchmarkSha256", benchmark.get("sha256")
            ));

            send(exchange, 200, jsonObject(mapOf(
                    "status", "trained_eval_logged",
                    "version", SDK_VERSION,
                    "trainingRun", run,
                    "recursiveEpoch", epoch,
                    "benchmark", benchmark
            )), "application/json");
        }
    }

    private static class BenchmarkSnapshotHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }
            Map<String, Object> snapshot = currentBenchmark("captured");
            snapshot.put("request", readBody(exchange));
            snapshot.put("sha256", sha256(jsonObject(snapshot)));
            appendJsonLine(BENCHMARK_LOG, snapshot);
            appendJsonLine(PERSISTENCE_LOG, mapOf("event", "benchmark_snapshot", "sha256", snapshot.get("sha256")));
            send(exchange, 200, jsonObject(snapshot), "application/json");
        }
    }

    private static class RecursiveTrainingHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }
            String body = readBody(exchange);
            Map<String, Object> epoch = new LinkedHashMap<>();
            epoch.put("kind", "recursive_training_epoch");
            epoch.put("status", "proposal_eval_only");
            epoch.put("timestamp", Instant.now().toString());
            epoch.put("body", body);
            epoch.put("doesSubmitRecursiveTraining", false);
            epoch.put("guard", "This records a recursive training proposal and benchmark context only. It does not mutate model weights.");
            epoch.put("promotionGate", "success >= 99.99 and (speed_gain >= 10 or resource_drop >= 10)");
            epoch.put("scientificMethod", "one changed variable per epoch; compare before/after; end-to-end proof required");
            epoch.put("benchmarkBefore", currentBenchmark("epoch_before"));
            epoch.put("sha256", sha256(jsonObject(epoch)));
            appendJsonLine(TRAINING_EPOCH_LOG, epoch);
            appendJsonLine(PERSISTENCE_LOG, mapOf("event", "recursive_training_epoch_append", "sha256", epoch.get("sha256")));
            send(exchange, 200, jsonObject(epoch), "application/json");
        }
    }

    private static class AsciiEpochHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if ("GET".equals(exchange.getRequestMethod())) {
                Map<String, String> query = parseQuery(exchange.getRequestURI().getRawQuery());
                int limit = Math.max(1, Math.min(parseInt(query.getOrDefault("limit", "20"), 20), 100));
                send(exchange, 200, jsonObject(mapOf(
                        "status", "ok",
                        "version", SDK_VERSION,
                        "queue", readJsonLines(ASCII_EPOCH_LOG, limit),
                        "policy", "always keep new ASCII epochs waiting; external judges weigh only; local proof promotes"
                )), "application/json");
                return;
            }
            if (!"POST".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }
            String body = readBody(exchange);
            Map<String, Object> epoch = new LinkedHashMap<>();
            epoch.put("kind", "ascii_epoch_proposal");
            epoch.put("version", SDK_VERSION);
            epoch.put("timestamp", Instant.now().toString());
            epoch.put("body", body);
            epoch.put("subsystems", List.of("chooser", "db_retrieval", "karoo", "abliterated", "loihi", "lava", "soap", "ledger", "network", "java_sdk"));
            epoch.put("judgeSlots", List.of("local_benchmark", "karoo_compare", "tiny_critic", "optional_copilot", "optional_gemini", "optional_cloud_agent"));
            epoch.put("quickEditVars", List.of(
                    "route",
                    "token_budget",
                    "retrieval_weight",
                    "web_research_gate",
                    "karoo_rounds",
                    "loihi_cube",
                    "lava_mode",
                    "soap_endpoint",
                    "promotion_gate"
            ));
            epoch.put("ascii", asciiEpochCube());
            epoch.put("proposedDiagram", proposedEpochDiagram(body));
            epoch.put("promotion", "proposal queue only until benchmark gate proves success >= 99.99 and speed/resource improvement");
            epoch.put("sha256", sha256(jsonObject(epoch)));
            appendJsonLine(ASCII_EPOCH_LOG, epoch);
            appendJsonLine(PERSISTENCE_LOG, mapOf("event", "ascii_epoch_append", "sha256", epoch.get("sha256")));
            send(exchange, 200, jsonObject(epoch), "application/json");
        }
    }

    private static class EpochUpgradeProofHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equals(exchange.getRequestMethod())) {
                send(exchange, 405, jsonError("method_not_allowed"), "application/json");
                return;
            }
            String body = readBody(exchange);
            Map<String, Object> proof = buildEpochUpgradeProof(body);
            proof.put("sha256", sha256(jsonObject(proof)));
            appendJsonLine(EPOCH_UPGRADE_LOG, proof);
            appendJsonLine(PERSISTENCE_LOG, mapOf("event", "epoch_upgrade_proof_append", "sha256", proof.get("sha256")));
            send(exchange, 200, jsonObject(proof), "application/json");
        }
    }

    private static class LogTailHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            Map<String, String> query = parseQuery(exchange.getRequestURI().getRawQuery());
            String file = query.getOrDefault("file", "system");
            int lines = parseInt(query.getOrDefault("lines", "80"), 80);
            Path path = switch (file) {
                case "shipper" -> ROOT.resolve("logic_blockchain_shipper.log");
                case "topology" -> ROOT.resolve("topology_sidecar_loop.log");
                case "house_stdout" -> ROOT.resolve("house_inference_stdout.log");
                case "house_stderr" -> ROOT.resolve("house_inference_stderr.log");
                case "tests" -> TEST_LOG;
                case "ab" -> AB_LOG;
                case "training" -> TRAINING_LOG;
                case "recursive_training" -> TRAINING_EPOCH_LOG;
                case "loihi" -> LOIHI_LOG;
                case "benchmarks" -> BENCHMARK_LOG;
                case "ascii_epochs" -> ASCII_EPOCH_LOG;
                case "epoch_upgrades" -> EPOCH_UPGRADE_LOG;
                case "persistence" -> PERSISTENCE_LOG;
                default -> ROOT.resolve("system_log.txt");
            };
            send(exchange, 200, jsonObject(mapOf(
                    "file", file,
                    "path", path.toString(),
                    "tail", tail(path, Math.max(1, Math.min(lines, 400)))
            )), "application/json");
        }
    }

    private static class DesignHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            send(exchange, 200, jsonObject(mapOf(
                    "sdk", "VIPER Java SDK",
                    "persistence", List.of(
                            "settings persisted in sdk_settings.json",
                            "system tests appended to system_tests.jsonl",
                            "AB tests appended to ab_tests.jsonl",
                            "training runs appended to training_runs.jsonl",
                            "recursive training epochs appended to recursive_training_epochs.jsonl",
                            "Loihi experiments appended to loihi_experiments.jsonl",
                            "benchmark snapshots appended to benchmark_snapshots.jsonl",
                            "ASCII epoch proposals appended to ascii_epoch_queue.jsonl",
                            "epoch upgrade proofs appended to epoch_upgrade_proofs.jsonl",
                            "persistence events appended to persistence_events.jsonl"
                    ),
                    "training", "Active eval training exists now: Java lab probes services, bridge prefetch, recent benchmarks, scores a candidate, writes training/epoch/benchmark proof logs, and keeps weights untouched.",
                    "recursiveTraining", "Recursive training records are now backed by actual eval probes. Real model-weight mutation is not submitted by this Java SDK.",
                    "loihi", "Future Lava/Loihi sidecar receives topological codes, not raw hidden thoughts. It maps codes to spike topology and returns measurable logic/code deltas.",
                    "karoo", "Proposal-only optimizer until 99.99% success plus speed/resource gate is proven.",
                    "fabric", "Tiny chooser writes 15-word cards for ask, DB, recent prompts, and repair state; larger model gets selected lens plus real retrieval.",
                    "externalJudges", "Copilot/Gemini/cloud agents are optional judge slots. They can weigh an epoch, but cannot auto-promote without local proof.",
                    "epochProof", "The upgrade proof endpoint analyzes current logs/benchmarks and emits concrete proposed changes with evidence and tests.",
                    "ui", "Separate VS Code-like SDK surface; locked main GUI remains unchanged."
            )), "application/json");
        }
    }

    private static Map<String, Object> serviceHealth() {
        Map<String, Object> services = new LinkedHashMap<>();
        services.put("bridge8080", probe("http://127.0.0.1:8080/api/benchmarks?limit=1"));
        services.put("house11435", probe("http://127.0.0.1:11435/health"));
        services.put("shipper18081", probe("http://127.0.0.1:18081/health"));
        return services;
    }

    private static Map<String, Object> currentBenchmark(String mode) {
        long start = System.currentTimeMillis();
        Map<String, Object> benchmark = new LinkedHashMap<>();
        benchmark.put("kind", "benchmark_snapshot");
        benchmark.put("mode", mode);
        benchmark.put("timestamp", Instant.now().toString());
        benchmark.put("services", serviceHealth());
        benchmark.put("counts", mapOf(
                "systemTests", countLines(TEST_LOG),
                "abTests", countLines(AB_LOG),
                "trainingRuns", countLines(TRAINING_LOG),
                "recursiveTrainingEpochs", countLines(TRAINING_EPOCH_LOG),
                "loihiExperiments", countLines(LOIHI_LOG),
                "benchmarkSnapshots", countLines(BENCHMARK_LOG),
                "persistenceEvents", countLines(PERSISTENCE_LOG)
        ));
        benchmark.put("logs", mapOf(
                "systemBytes", fileSize(ROOT.resolve("system_log.txt")),
                "shipperBytes", fileSize(ROOT.resolve("logic_blockchain_shipper.log")),
                "topologyBytes", fileSize(ROOT.resolve("topology_sidecar_loop.log")),
                "houseStdoutBytes", fileSize(ROOT.resolve("house_inference_stdout.log")),
                "houseStderrBytes", fileSize(ROOT.resolve("house_inference_stderr.log"))
        ));
        benchmark.put("policy", "benchmarks prove service latency, log growth, and proposal epochs before recursive automation is trusted");
        benchmark.put("durationMs", System.currentTimeMillis() - start);
        return benchmark;
    }

    private static String asciiEpochCube() {
        return """
                         z: subsystem / top-code family
                              ^
                              |
                 +------------+------------+
                /| chooser   /| karoo     /|
               / | db       / | lava     / |
              +------------+------------+  |
              |  | soap    |  | loihi   |  |
              |  +---------|--+---------|--+--> x: logic / code coordinate
              | / ledger   | / network  | /
              |/ java_sdk  |/ agents    |/
              +------------+------------+
             /
            v
          y: weight / confidence / resource cost

          propose -> weigh -> benchmark -> compare -> wait/promote
          """;
    }

    private static String proposedEpochDiagram(String body) {
        String lower = body == null ? "" : body.toLowerCase();
        String subsystem = firstMatch(lower, List.of(
                "chooser", "db_retrieval", "karoo", "abliterated", "loihi",
                "lava", "soap", "ledger", "network", "java_sdk"
        ), "proposed_node");
        String quickVar = firstMatch(lower, List.of(
                "retrieval_weight", "token_budget", "lava_mode", "loihi_cube",
                "soap_endpoint", "promotion_gate", "karoo_rounds", "web_research_gate"
        ), "quick_var");
        String judge = firstMatch(lower, List.of(
                "optional_copilot", "optional_gemini", "optional_cloud_agent",
                "local_benchmark", "karoo_compare", "tiny_critic"
        ), "judge_slot");
        return """
                VIPER_SDK_EPOCH_PROPOSAL  version: %s

                explorer
                +- system
                |  +- chooser
                |  +- db_retrieval
                |  +- karoo
                |  +- abliterated
                |  +- loihi
                |  +- lava
                |  +- soap
                |  +- ledger
                |  +- network
                |  +- java_sdk
                |
                +- proposed_change
                |  +- subsystem: >>> %s <<<
                |  +- variable:  >>> %s <<<
                |  +- judge:     >>> %s <<<
                |
                +- flow
                   +- ask.card
                   +- db.retrieve
                   +- lens.compose
                   +- route.execute
                   +- judge.weigh      [highlight]
                   +- benchmark.prove   [highlight]
                   +- sha256.log
                   +- promote.or.wait

                +------------------+     +------------------+     +------------------+
                | current baseline | --> | >>> proposal <<< | --> | benchmark gate   |
                +------------------+     +------------------+     +------------------+
                          |                        |                        |
                          v                        v                        v
                +------------------+     +------------------+     +------------------+
                | keep history     |     | one variable     |     | 99.99%% + 10%%    |
                +------------------+     +------------------+     +------------------+
                """.formatted(SDK_VERSION, subsystem, quickVar, judge);
    }

    private static Map<String, Object> buildEpochUpgradeProof(String requestBody) {
        String bridgeBenchmarks = fetchText("http://127.0.0.1:8080/api/benchmarks?limit=8", 6);
        String houseHealth = fetchText("http://127.0.0.1:11435/health", 4);
        String shipperHealth = fetchText("http://127.0.0.1:18081/health", 4);
        String shipperTail = tail(ROOT.resolve("logic_blockchain_shipper.log"), 40);
        String topologyTail = tail(ROOT.resolve("topology_sidecar_loop.log"), 40);

        List<Map<String, Object>> proposals = new ArrayList<>();
        proposals.add(epochProposal(
                "EPOCH_BRIDGE_HEADROOM_REPAIR",
                "bridge8080",
                "Thin replies and repaired planning turns show the orchestration works but needs a stronger response contract.",
                evidenceLine(bridgeBenchmarks, "response_chars\": 5", "bridge benchmark includes a very short response"),
                "Add a route-level completion proof card: answer_min_chars, required_sections, and retry reason before returning to the user.",
                "Replay the last thin prompt; pass only if response_chars >= 300 or route explicitly marks terse chat as intended."
        ));
        proposals.add(epochProposal(
                "EPOCH_SHIPPER_UPLINK_COMPAT",
                "logic_shipper18081",
                "Heartbeat succeeds, but local /api/uplink posts are repeatedly 404, so ledger shipping needs endpoint compatibility proof.",
                evidenceLine(shipperTail, "/api/uplink HTTP/1.1\" 404", "shipper log shows repeated /api/uplink 404 responses"),
                "Add an endpoint negotiation table: local_uplink_path, cloud_uplink_path, ledger_path, and preflight route check.",
                "Run health plus one dry-run uplink preflight; pass only if route returns 2xx/accepted or clear disabled status."
        ));
        proposals.add(epochProposal(
                "EPOCH_KAROO_COMPARATOR_ATTACH",
                "karoo_topology_loop",
                "Karoo is safely capturing baselines, but comparison_count is zero, so it cannot yet rank mutations like a real epoch judge.",
                evidenceLine(topologyTail, "comparison_count\": 0", "topology tail shows comparison_count is zero"),
                "Attach a comparator source set: project-local snippet, successful ledger block, and optional external judge score.",
                "Next Karoo candidate must include comparison_count >= 3 and one-variable score deltas before patch proposal."
        ));
        proposals.add(epochProposal(
                "EPOCH_SOVEREIGN_AGENT_CONTRACT",
                "agent_network",
                "The system is ready for orchestration if every agent declares capability, limits, endpoints, and proof outputs first.",
                "house=" + compactStatus(houseHealth) + "; shipper=" + compactStatus(shipperHealth),
                "Add an ACL/KQML capability card per agent: can_do, cannot_do, endpoint, token budget, storage role, heartbeat.",
                "Pass when each registered agent can answer capability ping and produce a SHA-256 proof envelope."
        ));
        proposals.add(epochProposal(
                "EPOCH_ROLLING_TRIPLET_RESTORE",
                "chooser_triplet_tail",
                "User-approved: restore the lighter rolling recursive triplet response because it felt better than a single heavy bridge pass.",
                "Active request approved rolling triplet plus tiny chooser/decider first.",
                "Tiny chooser selects route -> light model draft -> Karoo/action pass -> verifier/editor pass -> tail continuation stitches long responses.",
                "TBD: replay long planning prompt; pass when response is complete, sectioned, and no 'PASS.' or cutoff appears."
        ));
        proposals.add(epochProposal(
                "EPOCH_MISSION_DIRECTIVE_ALWAYS_ON",
                "mission_directive",
                "User-approved: display and inject the mission directive first so every model keeps the same purpose frame.",
                "Active request supplied always-on directive text.",
                "Prefix every route with the mission directive before variable context so prefix caching can reuse it.",
                "TBD: inspect prompt pack; pass when directive appears before retrieval/lens and output remains on mission."
        ));
        proposals.add(epochProposal(
                "EPOCH_LONG_RESPONSE_TAIL_STITCH",
                "tail_continuation",
                "Long answers should be allowed to take time and continue cleanly instead of collapsing under token or timeout pressure.",
                "Bridge defaults were raised; tail engineering is approved for long local responses.",
                "When answer may exceed token budget, ask model to end with TAIL_CONTINUE token and resume from the last outline point.",
                "TBD: request a long answer; pass when continuation joins without repeated intro or missing final section."
        ));
        proposals.add(epochProposal(
                "EPOCH_INFERENCE_OPTIMIZATION_STACK",
                "inference_runtime",
                "User supplied optimization stack: quantization, prefix caching, disaggregated prefill/decode, Flash Attention, continuous batching, KV cache management, speculative decoding.",
                "Imported optimization notes from active request.",
                "Create environment capability table and enable only supported optimizations: GGUF quant choice now; vLLM/Flash/PagedAttention/speculative later where hardware supports it.",
                "TBD: benchmark TTFT, tokens/sec, memory use, and accuracy before/after each single optimization."
        ));
        proposals.add(epochProposal(
                "EPOCH_DISTRIBUTED_RESOURCE_APP",
                "distributed_exe_network",
                "User-approved final phase: real distributable app that can lend/take CPU, memory, and storage across PCs and phones.",
                "Standalone Java EXE exists; APK skeleton exists; resource lending still needs a real protocol.",
                "Add node capability daemon: announce resources, accept signed tasks, return SHA-256 proof, enforce local opt-in quotas.",
                "TBD: two-node LAN smoke test; pass when node A sees node B resources and runs a harmless benchmark task."
        ));
        proposals.add(epochProposal(
                "EPOCH_AXIOMATIC_WEIGHTED_TRUTH_TABLES",
                "coding_truth_tables",
                "User-approved: all agents should use axiomatic truth tables with weighted truths for coding decisions.",
                "Active request: 'EVERYONE is using AXIOMATIC TRUTH TABLES WITH WEIGHTED TRUTHES FOR CODING'.",
                "Add coding decision table: axiom, evidence, counterexample, weight, confidence, test, verdict. Require it in Karoo proposal packets.",
                "TBD: next code proposal must include weighted truth table and pass/fail evidence before patch approval."
        ));
        proposals.add(epochProposal(
                "EPOCH_REAL_TINY_CHOOSER",
                "qwen2_5_chooser",
                "The previous chooser was too deterministic; Qwen2.5-0.5B now writes the active lens instead of merely validating a template.",
                "Tiny model runtime downloads and probes Qwen2.5-0.5B GGUF, then logs qwen_chooser benchmarks.",
                "Use Qwen to emit the max-100-word active lens after DB/user/web evidence is gathered; deterministic text is fallback only.",
                "TBD: pass when qwen_chooser_lens_100_words status is chosen_by_qwen2_5 and response route/layer are correct."
        ));
        proposals.add(epochProposal(
                "EPOCH_AXIOMATIC_RETRIEVAL_MATCHER",
                "smollm2_retrieval",
                "Keyword retrieval alone was noisy; SmolLM2-360M now selects the closest 50-word axiomatic DB match.",
                "Tiny model runtime downloads and probes SmolLM2-360M GGUF, with H2O-Danube3 as fallback.",
                "Run purpose-first DB retrieval, compress candidates, ask SmolLM2 for one closest match, then inject only that reduced card.",
                "TBD: pass when axiomatic_retrieval_match_50_words status is matched_by_smollm2 and does not exceed 50 words."
        ));
        proposals.add(epochProposal(
                "EPOCH_NAS_AGENT_SPINUP_SYNC",
                "nas_agent_bootstrap",
                "The resource network needs a repeatable way to copy project files and tiny models to new machines without guessing paths.",
                "VIPER_NAS_ROOT is optional and no hard-coded NAS path is assumed.",
                "Add CREATE_VIPER_NAS_LINK.ps1 and SPIN_UP_AGENT_NODE.ps1 for staging, env config, tiny model paths, and node bootstrap.",
                "TBD: pass when a second machine can run the generated env file and report model-path/status without manual file hunting."
        ));

        Map<String, Object> proof = new LinkedHashMap<>();
        proof.put("kind", "epoch_upgrade_proof");
        proof.put("version", SDK_VERSION);
        proof.put("timestamp", Instant.now().toString());
        proof.put("request", requestBody);
        proof.put("checkpoint", "C:\\Users\\viper\\VIPER_JAVA_RISC_CHECKPOINTS");
        proof.put("mode", "proof_of_concept_proposals_only");
        proof.put("approvalStatus", "approved_by_user_pending_tbd_tests");
        proof.put("systemRead", mapOf(
                "bridgeBenchmarks", bridgeBenchmarks.substring(0, Math.min(1200, bridgeBenchmarks.length())),
                "houseHealth", houseHealth,
                "shipperHealth", shipperHealth,
                "shipperTail", shipperTail,
                "topologyTail", topologyTail
        ));
        proof.put("proposals", proposals);
        proof.put("diagram", upgradeProofDiagram());
        proof.put("promotionGate", "No auto-apply. Promote only after one-variable test, e2e proof, success >= 99.99, and +10% speed or -10% resources.");
        return proof;
    }

    private static Map<String, Object> epochProposal(String id, String subsystem, String problem, String evidence, String proposedChange, String acceptanceTest) {
        return mapOf(
                "id", id,
                "subsystem", subsystem,
                "problem", problem,
                "evidence", evidence,
                "proposedChange", proposedChange,
                "acceptanceTest", acceptanceTest,
                "testResult", "TBD",
                "approvalStatus", "approved_by_user_pending_test",
                "visualHighlight", "HIGH_CONTRAST_YELLOW",
                "highlight", ">>> " + subsystem + " :: " + proposedChange + " <<<",
                "diagram", proposalFlowDiagram(id, subsystem)
        );
    }

    private static String evidenceLine(String text, String needle, String hit) {
        if (text != null && text.contains(needle)) {
            return hit;
        }
        return "No exact marker found in current tail; proposal remains queued for more evidence.";
    }

    private static String compactStatus(String text) {
        if (text == null || text.isBlank()) {
            return "empty";
        }
        String clean = text.replace("\r", " ").replace("\n", " ");
        return clean.substring(0, Math.min(180, clean.length()));
    }

    private static String proposalFlowDiagram(String id, String subsystem) {
        return """
                %s
                +- baseline.read
                |  +- logs
                |  +- benchmarks
                |  +- health
                +- proposed_change
                |  +- subsystem: >>> %s <<<
                |  +- scope: one variable
                |  +- mode: proposal only
                +- proof
                   +- run test
                   +- compare delta
                   +- sha256 record
                   +- wait for approval
                """.formatted(id, subsystem);
    }

    private static String upgradeProofDiagram() {
        return """
                VIPER_EPOCH_UPGRADE_PROOF

                +-----------------+      +------------------+      +------------------+
                | subsystem scan  | ---> | proposed epoch   | ---> | acceptance test  |
                +-----------------+      +------------------+      +------------------+
                         |                         |                         |
                         v                         v                         v
                +-----------------+      +------------------+      +------------------+
                | evidence tail   |      | >>> highlight <<<|      | benchmark + SHA |
                +-----------------+      +------------------+      +------------------+

                surgical agents:
                  bridge.headroom       -> fix thin replies with completion proof
                  shipper.uplink        -> fix endpoint compatibility before ledger shipping
                  karoo.comparator      -> require comparison_count before mutation scoring
                  sovereign.contract    -> every agent declares capability and proof envelope
                """;
    }

    private static String firstMatch(String text, List<String> choices, String fallback) {
        for (String choice : choices) {
            if (text.contains(choice)) {
                return choice;
            }
        }
        return fallback;
    }

    private static Map<String, Object> probe(String url) {
        long start = System.currentTimeMillis();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("url", url);
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(5))
                    .GET()
                    .build();
            HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
            result.put("status", response.statusCode());
            result.put("ok", response.statusCode() >= 200 && response.statusCode() < 300);
            result.put("durationMs", System.currentTimeMillis() - start);
            result.put("bodyPreview", response.body().substring(0, Math.min(240, response.body().length())));
        } catch (Exception e) {
            result.put("ok", false);
            result.put("durationMs", System.currentTimeMillis() - start);
            result.put("error", e.getClass().getSimpleName() + ": " + e.getMessage());
        }
        return result;
    }

    private static String fetchText(String url, int timeoutSeconds) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(timeoutSeconds))
                    .GET()
                    .build();
            return HTTP.send(request, HttpResponse.BodyHandlers.ofString()).body();
        } catch (Exception e) {
            return "FETCH_ERROR: " + e.getClass().getSimpleName() + ": " + e.getMessage();
        }
    }

    private static String trainingPrompt(String dataset, String route, String changedVariable, String objective) {
        return "VIPER Java lab training eval. dataset=" + dataset
                + "; route=" + route
                + "; changed_variable=" + changedVariable
                + "; objective=" + objective
                + "; use real retrieval, Qwen chooser lens, SmolLM match, rolling triplet, and proof logs.";
    }

    private static Map<String, Object> evaluateTrainingRun(
            Map<String, Object> before,
            Map<String, Object> after,
            String prefetch,
            String bridgeBenchmarks
    ) {
        boolean bridgeOk = serviceOk(before, "bridge8080") && serviceOk(after, "bridge8080");
        boolean houseOk = serviceOk(before, "house11435") && serviceOk(after, "house11435");
        boolean shipperOk = serviceOk(before, "shipper18081") && serviceOk(after, "shipper18081");
        boolean prefetchOk = prefetch != null && prefetch.contains("\"prediction\"");
        boolean benchmarkOk = bridgeBenchmarks != null && bridgeBenchmarks.contains("\"benchmarks\"");
        long beforeTotal = serviceMs(before, "bridge8080") + serviceMs(before, "house11435") + serviceMs(before, "shipper18081");
        long afterTotal = serviceMs(after, "bridge8080") + serviceMs(after, "house11435") + serviceMs(after, "shipper18081");
        long latencyDeltaMs = afterTotal - beforeTotal;
        int passSignals = 0;
        passSignals += bridgeOk ? 1 : 0;
        passSignals += houseOk ? 1 : 0;
        passSignals += shipperOk ? 1 : 0;
        passSignals += prefetchOk ? 1 : 0;
        passSignals += benchmarkOk ? 1 : 0;
        double score = passSignals / 5.0;
        boolean speedImproved = beforeTotal > 0 && afterTotal <= Math.round(beforeTotal * 0.90);
        return mapOf(
                "score", score,
                "bridgeOk", bridgeOk,
                "houseOk", houseOk,
                "shipperOk", shipperOk,
                "prefetchOk", prefetchOk,
                "benchmarkReadOk", benchmarkOk,
                "beforeServiceTotalMs", beforeTotal,
                "afterServiceTotalMs", afterTotal,
                "latencyDeltaMs", latencyDeltaMs,
                "speedImproved10Percent", speedImproved,
                "promotionEligible", score >= 0.9999 && speedImproved,
                "verdict", score >= 0.8 ? "training_eval_passed_recorded" : "training_eval_needs_attention",
                "nextAction", "keep logging; only promote after repeatable one-variable e2e proof"
        );
    }

    private static boolean serviceOk(Map<String, Object> benchmark, String name) {
        Object servicesObj = benchmark.get("services");
        if (!(servicesObj instanceof Map<?, ?> services)) {
            return false;
        }
        Object serviceObj = services.get(name);
        if (!(serviceObj instanceof Map<?, ?> service)) {
            return false;
        }
        return Boolean.TRUE.equals(service.get("ok"));
    }

    private static long serviceMs(Map<String, Object> benchmark, String name) {
        Object servicesObj = benchmark.get("services");
        if (!(servicesObj instanceof Map<?, ?> services)) {
            return 0L;
        }
        Object serviceObj = services.get(name);
        if (!(serviceObj instanceof Map<?, ?> service)) {
            return 0L;
        }
        Object value = service.get("durationMs");
        if (value instanceof Number number) {
            return number.longValue();
        }
        return 0L;
    }

    private static long fileSize(Path path) {
        try {
            return Files.exists(path) ? Files.size(path) : 0;
        } catch (IOException e) {
            return -1;
        }
    }

    private static Map<String, Object> fileInfo(Path path) {
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("path", path.toString());
        info.put("exists", Files.exists(path));
        try {
            info.put("bytes", Files.exists(path) ? Files.size(path) : 0);
            info.put("sha256", Files.exists(path) ? sha256(Files.readString(path, StandardCharsets.UTF_8)) : "");
        } catch (IOException e) {
            info.put("error", e.getMessage());
        }
        return info;
    }

    private static void appendJsonLine(Path path, Map<String, Object> event) throws IOException {
        Files.createDirectories(path.getParent());
        String line = jsonObject(event) + "\n";
        Files.writeString(path, line, StandardCharsets.UTF_8, Files.exists(path)
                ? java.nio.file.StandardOpenOption.APPEND
                : java.nio.file.StandardOpenOption.CREATE);
    }

    private static String readBody(HttpExchange exchange) throws IOException {
        return new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
    }

    private static void send(HttpExchange exchange, int status, String body, String contentType) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", contentType);
        exchange.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
        exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
        exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
        if ("OPTIONS".equals(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(204, -1);
            return;
        }
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }

    private static String readTextSafe(Path path, String fallback) {
        try {
            return Files.exists(path) ? Files.readString(path, StandardCharsets.UTF_8) : fallback;
        } catch (IOException e) {
            return fallback;
        }
    }

    private static long countLines(Path path) {
        if (!Files.exists(path)) {
            return 0;
        }
        try (Stream<String> stream = Files.lines(path, StandardCharsets.UTF_8)) {
            return stream.count();
        } catch (IOException e) {
            return -1;
        }
    }

    private static String tail(Path path, int lines) {
        if (!Files.exists(path)) {
            return "";
        }
        try {
            List<String> all = Files.readAllLines(path, StandardCharsets.UTF_8);
            int start = Math.max(0, all.size() - lines);
            return String.join("\n", all.subList(start, all.size()));
        } catch (IOException e) {
            return "TAIL_ERROR: " + e.getMessage();
        }
    }

    private static List<String> readJsonLines(Path path, int limit) {
        if (!Files.exists(path)) {
            return List.of();
        }
        try {
            List<String> all = Files.readAllLines(path, StandardCharsets.UTF_8);
            List<String> nonBlank = new ArrayList<>();
            for (String line : all) {
                if (!line.isBlank()) {
                    nonBlank.add(line);
                }
            }
            int start = Math.max(0, nonBlank.size() - limit);
            return nonBlank.subList(start, nonBlank.size());
        } catch (IOException e) {
            return List.of(jsonObject(mapOf("error", e.getMessage())));
        }
    }

    private static List<Object> readJsonFragments(Path path, int limit) {
        List<Object> fragments = new ArrayList<>();
        for (String line : readJsonLines(path, limit)) {
            String trimmed = line.trim();
            if ((trimmed.startsWith("{") && trimmed.endsWith("}")) ||
                    (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
                fragments.add(new JsonFragment(trimmed));
            } else {
                fragments.add(line);
            }
        }
        return fragments;
    }

    private static Map<String, String> parseQuery(String rawQuery) {
        Map<String, String> map = new LinkedHashMap<>();
        if (rawQuery == null || rawQuery.isBlank()) {
            return map;
        }
        for (String part : rawQuery.split("&")) {
            String[] pair = part.split("=", 2);
            String key = decode(pair[0]);
            String value = pair.length > 1 ? decode(pair[1]) : "";
            map.put(key, value);
        }
        return map;
    }

    private static String decode(String value) {
        return URLDecoder.decode(value, StandardCharsets.UTF_8);
    }

    private static int parseInt(String value, int fallback) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    private static String extractJsonString(String body, String key, String fallback) {
        if (body == null || body.isBlank()) {
            return fallback;
        }
        String needle = "\"" + key + "\"";
        int keyAt = body.indexOf(needle);
        if (keyAt < 0) {
            return fallback;
        }
        int colonAt = body.indexOf(':', keyAt + needle.length());
        if (colonAt < 0) {
            return fallback;
        }
        int valueAt = colonAt + 1;
        while (valueAt < body.length() && Character.isWhitespace(body.charAt(valueAt))) {
            valueAt++;
        }
        if (valueAt >= body.length()) {
            return fallback;
        }
        if (body.charAt(valueAt) == '"') {
            StringBuilder out = new StringBuilder();
            boolean escaping = false;
            for (int i = valueAt + 1; i < body.length(); i++) {
                char ch = body.charAt(i);
                if (escaping) {
                    out.append(switch (ch) {
                        case 'n' -> '\n';
                        case 'r' -> '\r';
                        case 't' -> '\t';
                        default -> ch;
                    });
                    escaping = false;
                } else if (ch == '\\') {
                    escaping = true;
                } else if (ch == '"') {
                    String value = out.toString().trim();
                    return value.isBlank() ? fallback : value;
                } else {
                    out.append(ch);
                }
            }
            return fallback;
        }
        int endAt = valueAt;
        while (endAt < body.length() && body.charAt(endAt) != ',' && body.charAt(endAt) != '}') {
            endAt++;
        }
        String value = body.substring(valueAt, endAt).trim();
        return value.isBlank() ? fallback : value;
    }

    private static String urlEncode(String value) {
        return URLEncoder.encode(value == null ? "" : value, StandardCharsets.UTF_8);
    }

    private static String sha256(String text) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            return "sha256_error";
        }
    }

    private static String jsonError(String error) {
        return jsonObject(mapOf("status", "error", "error", error));
    }

    private static Map<String, Object> mapOf(Object... values) {
        Map<String, Object> map = new LinkedHashMap<>();
        for (int i = 0; i + 1 < values.length; i += 2) {
            map.put(String.valueOf(values[i]), values[i + 1]);
        }
        return map;
    }

    private static String jsonObject(Map<String, ?> map) {
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, ?> entry : map.entrySet()) {
            if (!first) {
                sb.append(",");
            }
            first = false;
            sb.append("\"").append(escape(entry.getKey())).append("\":").append(jsonValue(entry.getValue()));
        }
        sb.append("}");
        return sb.toString();
    }

    private static String jsonValue(Object value) {
        if (value == null) {
            return "null";
        }
        if (value instanceof JsonFragment fragment) {
            return fragment.json();
        }
        if (value instanceof Number || value instanceof Boolean) {
            return String.valueOf(value);
        }
        if (value instanceof Map<?, ?> nested) {
            Map<String, Object> clean = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : nested.entrySet()) {
                clean.put(String.valueOf(entry.getKey()), entry.getValue());
            }
            return jsonObject(clean);
        }
        if (value instanceof Iterable<?> iterable) {
            List<String> parts = new ArrayList<>();
            for (Object item : iterable) {
                parts.add(jsonValue(item));
            }
            return "[" + String.join(",", parts) + "]";
        }
        return "\"" + escape(String.valueOf(value)) + "\"";
    }

    private static String escape(String value) {
        return value
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\r", "\\r")
                .replace("\n", "\\n")
                .replace("\t", "\\t");
    }

    private record JsonFragment(String json) {}

    private static String html() {
        return """
                <!doctype html>
                <html>
                <head>
                  <meta charset="utf-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1">
                  <title>VIPER Java SDK</title>
                  <style>
                    :root { color-scheme: dark; font-family: Consolas, "Cascadia Mono", monospace; }
                    * { box-sizing: border-box; }
                    body { margin:0; min-height:100vh; background:#0d1117; color:#c9d1d9; }
                    header { height:44px; display:flex; align-items:center; justify-content:space-between; padding:0 14px; background:#161b22; border-bottom:1px solid #30363d; }
                    header strong { color:#f0f6fc; font-size:14px; }
                    header span { color:#8b949e; font-size:12px; }
                    .shell { display:grid; grid-template-columns:48px 250px 1fr 360px; height:calc(100vh - 44px); }
                    .rail { background:#0d1117; border-right:1px solid #30363d; padding:8px 6px; display:flex; flex-direction:column; gap:8px; }
                    .rail button { height:36px; border:0; border-radius:6px; background:#161b22; color:#c9d1d9; cursor:pointer; }
                    .rail button:hover { background:#1f6feb; color:white; }
                    .sidebar { background:#161b22; border-right:1px solid #30363d; padding:12px; overflow:auto; }
                    .sidebar h2, .panel h2 { margin:0 0 10px; font-size:12px; letter-spacing:0; text-transform:uppercase; color:#8b949e; }
                    .tree { display:flex; flex-direction:column; gap:6px; }
                    .tree button, .cmd { width:100%; text-align:left; background:#0d1117; color:#c9d1d9; border:1px solid #30363d; border-radius:6px; padding:8px; cursor:pointer; }
                    .tree button:hover, .cmd:hover { border-color:#58a6ff; }
                    main { overflow:auto; background:#0d1117; }
                    .tabs { display:flex; height:36px; background:#161b22; border-bottom:1px solid #30363d; }
                    .tab { padding:10px 14px; border-right:1px solid #30363d; font-size:12px; color:#8b949e; }
                    .tab.active { background:#0d1117; color:#f0f6fc; }
                    .editor { padding:16px; display:grid; grid-template-columns:repeat(2,minmax(260px,1fr)); gap:12px; }
                    .panel { border:1px solid #30363d; border-radius:6px; background:#0f1520; padding:12px; min-height:130px; }
                    .panel.wide { grid-column:1 / -1; }
                    label { display:block; font-size:12px; color:#8b949e; margin:8px 0 4px; }
                    input, textarea, select { width:100%; background:#010409; color:#c9d1d9; border:1px solid #30363d; border-radius:6px; padding:8px; font-family:inherit; }
                    textarea { min-height:92px; resize:vertical; }
                    canvas { width:100%; height:230px; display:block; background:#010409; border:1px solid #30363d; border-radius:6px; }
                    pre { margin:0; white-space:pre-wrap; word-break:break-word; color:#d2a8ff; font-size:12px; line-height:1.45; }
                    aside { background:#0f1520; border-left:1px solid #30363d; padding:12px; overflow:auto; }
                    .status { display:grid; grid-template-columns:1fr auto; gap:6px; font-size:12px; margin-bottom:8px; }
                    .ok { color:#3fb950; }
                    .bad { color:#f85149; }
                    .muted { color:#8b949e; }
                    .proposal-grid { display:grid; grid-template-columns:1fr; gap:10px; margin-top:10px; }
                    .epoch-card { border:2px solid #f2cc60; border-left:10px solid #f2cc60; border-radius:6px; background:#161b22; padding:10px; box-shadow:0 0 0 1px #3d2f00 inset; }
                    .epoch-card h3 { margin:0 0 8px; color:#f2cc60; font-size:14px; }
                    .epoch-card b { color:#f0f6fc; }
                    .hot { background:#f2cc60; color:#010409; padding:1px 4px; border-radius:3px; font-weight:bold; }
                    .tbd { color:#ffa657; font-weight:bold; }
                    .diagram { color:#a5d6ff; background:#010409; border:1px solid #30363d; border-radius:6px; padding:8px; margin-top:8px; }
                  </style>
                </head>
                <body>
                  <header><strong>VIPER Java SDK <span class="muted">v0.4.1-training-lab</span></strong><span>persistent lab | tests | AB | training | Loihi topology</span></header>
                  <div class="shell">
                    <div class="rail">
                      <button title="State" onclick="loadState()">S</button>
                      <button title="Tests" onclick="runTest()">T</button>
                      <button title="A/B" onclick="logAb()">A/B</button>
                      <button title="Training" onclick="logTraining()">TR</button>
                      <button title="Benchmarks" onclick="captureBenchmark()">BM</button>
                      <button title="ASCII Epochs" onclick="queueAsciiEpoch()">AE</button>
                      <button title="Upgrade Proof" onclick="runUpgradeProof()">UP</button>
                      <button title="Loihi" onclick="logLoihi()">L</button>
                      <button title="Design" onclick="loadDesign()">D</button>
                    </div>
                    <div class="sidebar">
                      <h2>Explorer</h2>
                      <div class="tree">
                        <button onclick="tail('system')">system_log.txt</button>
                        <button onclick="tail('shipper')">logic_shipper.log</button>
                        <button onclick="tail('topology')">topology_sidecar.log</button>
                        <button onclick="tail('tests')">system_tests.jsonl</button>
                        <button onclick="tail('ab')">ab_tests.jsonl</button>
                        <button onclick="tail('training')">training_runs.jsonl</button>
                        <button onclick="tail('recursive_training')">recursive_training_epochs.jsonl</button>
                        <button onclick="tail('benchmarks')">benchmark_snapshots.jsonl</button>
                        <button onclick="tail('ascii_epochs')">ascii_epoch_queue.jsonl</button>
                        <button onclick="tail('epoch_upgrades')">epoch_upgrade_proofs.jsonl</button>
                        <button onclick="tail('loihi')">loihi_experiments.jsonl</button>
                        <button onclick="tail('persistence')">persistence_events.jsonl</button>
                      </div>
                    </div>
                    <main>
                      <div class="tabs"><div class="tab active">control.sdk</div><div class="tab">settings.json</div><div class="tab">loihi.plan</div></div>
                      <div class="editor">
                        <div class="panel">
                          <h2>Quick Test</h2>
                          <label>Test name</label><input id="testName" value="end_to_end_health">
                          <label>One variable</label><input id="variable" value="reply_headroom">
                          <button class="cmd" onclick="runTest()">Run Java SDK Test</button>
                        </div>
                        <div class="panel">
                          <h2>Settings</h2>
                          <label>Mode</label><select id="mode"><option>chat</option><option selected>planning</option><option>build</option><option>training</option></select>
                          <label>Planning reply tokens</label><input id="planningTokens" value="1024">
                          <button class="cmd" onclick="saveSettings()">Persist Settings</button>
                        </div>
                        <div class="panel">
                          <h2>A/B Test</h2>
                          <label>Variant A</label><input id="variantA" value="current_lens">
                          <label>Variant B</label><input id="variantB" value="candidate_lens">
                          <button class="cmd" onclick="logAb()">Log A/B Plan</button>
                        </div>
                        <div class="panel">
                          <h2>Loihi Experiment</h2>
                          <label>Topology cube</label><input id="cube" value="100x100x100">
                          <label>Spike contract</label><input id="spike" value="x/y/z top-code weights, SHA-256 edge ids">
                          <button class="cmd" onclick="logLoihi()">Log Loihi Sidecar Experiment</button>
                        </div>
                        <div class="panel">
                          <h2>Training Run</h2>
                          <label>Dataset</label><input id="dataset" value="successful_code_and_liked_logic">
                          <label>Route</label><input id="trainRoute" value="proposal_only_lens_improvement">
                          <button class="cmd" onclick="logTraining()">Log Training Plan</button>
                        </div>
                        <div class="panel">
                          <h2>Recursive Epoch</h2>
                          <label>Changed variable</label><input id="epochVariable" value="retrieval_lens_rerank_weight">
                          <label>Dataset slice</label><input id="epochDataset" value="liked_logic_successful_code_recent_failures">
                          <button class="cmd" onclick="logRecursiveEpoch()">Log Proposal Epoch</button>
                        </div>
                        <div class="panel">
                          <h2>ASCII Epoch Queue</h2>
                          <label>Subsystem</label><select id="epochSubsystem"><option>chooser</option><option>db_retrieval</option><option>karoo</option><option>abliterated</option><option>loihi</option><option>lava</option><option>soap</option><option>ledger</option><option>network</option><option>java_sdk</option></select>
                          <label>Quick var</label><input id="quickVar" value="retrieval_weight">
                          <label>External judge</label><select id="judgeSlot"><option>local_benchmark</option><option>karoo_compare</option><option>tiny_critic</option><option>optional_copilot</option><option>optional_gemini</option><option>optional_cloud_agent</option></select>
                          <button class="cmd" onclick="queueAsciiEpoch()">Queue ASCII Epoch</button>
                        </div>
                        <div class="panel">
                          <h2>Upgrade Proof</h2>
                          <label>Goal</label><input id="proofGoal" value="sovereign_orchestration_epoch">
                          <label>Scope</label><input id="proofScope" value="bridge shipper karoo agent_contract">
                          <button class="cmd" onclick="runUpgradeProof()">Analyze And Propose Epoch</button>
                        </div>
                        <div class="panel wide">
                          <h2>Benchmarks</h2>
                          <canvas id="benchChart" width="980" height="230"></canvas>
                          <button class="cmd" onclick="captureBenchmark()">Capture Benchmark Snapshot</button>
                        </div>
                        <div class="panel wide">
                          <h2>Output</h2>
                          <div id="out"><pre>Ready.</pre></div>
                        </div>
                      </div>
                    </main>
                    <aside>
                      <h2>Service Watch</h2>
                      <div id="watch" class="muted">Not loaded.</div>
                      <button class="cmd" onclick="loadState()">Refresh State</button>
                    </aside>
                  </div>
                  <script>
                    const out = document.getElementById('out');
                    const watch = document.getElementById('watch');
                    const benchChart = document.getElementById('benchChart');
                    async function api(url, opts){ const r = await fetch(url, opts); const t = await r.text(); try { return JSON.parse(t); } catch { return {raw:t}; } }
                    function print(x){ out.innerHTML = `<pre>${esc(JSON.stringify(x, null, 2))}</pre>`; }
                    function esc(v){ return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
                    function printHtml(html){ out.innerHTML = html; }
                    async function loadState(){ const x = await api('/api/state'); print(x); renderWatch(x.services || {}); loadBenchmarks(false); }
                    function renderWatch(s){ watch.innerHTML = Object.entries(s).map(([k,v]) => `<div class="status"><span>${k}</span><span class="${v.ok?'ok':'bad'}">${v.ok?'ok':'down'}</span></div>`).join(''); }
                    async function saveSettings(){
                      const body = {mode:mode.value, planningReplyTokens:Number(planningTokens.value), karooProposalOnly:true, heartbeatSeconds:300};
                      print(await api('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body,null,2)}));
                    }
                    async function runTest(){
                      const body = {testName:testName.value, variable:variable.value, rule:'one variable per test', timestamp:new Date().toISOString()};
                      print(await api('/api/run-test', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}));
                    }
                    async function logAb(){
                      const body = {variantA:variantA.value, variantB:variantB.value, metric:'success + speed + resources', promotionGate:'99.99% and 10%'};
                      print(await api('/api/ab-test', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}));
                    }
                    async function logLoihi(){
                      const body = {cube:cube.value, spike:spike.value, mode:'proposal_simulation', bridge:'NLP -> top codes -> spikes -> logic deltas'};
                      print(await api('/api/loihi-experiment', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}));
                    }
                    async function logTraining(){
                      const body = {dataset:dataset.value, route:trainRoute.value, rule:'log first; proposal-only until promotion gate'};
                      print(await api('/api/training', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}));
                    }
                    async function logRecursiveEpoch(){
                      const body = {
                        changedVariable:epochVariable.value,
                        datasetSlice:epochDataset.value,
                        rule:'proposal/eval only; one variable; no model-weight mutation',
                        promotionGate:'99.99% success and +10% speed or -10% resources'
                      };
                      const x = await api('/api/recursive-training', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
                      print(x);
                      await loadBenchmarks(false);
                    }
                    async function queueAsciiEpoch(){
                      const body = {
                        subsystem:epochSubsystem.value,
                        quickVar:quickVar.value,
                        judgeSlot:judgeSlot.value,
                        rule:'always keep new ASCII epochs waiting; optional outside judge weighs only',
                        theme:'keep current VS Code dark SDK theme'
                      };
                      const x = await api('/api/ascii-epochs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
                      print({status:x.status || 'queued', version:x.version, sha256:x.sha256, proposedDiagram:x.proposedDiagram, full:x});
                    }
                    async function runUpgradeProof(){
                      const body = {
                        goal:proofGoal.value,
                        scope:proofScope.value,
                        rule:'analyze evidence and produce concrete proposed epoch changes; no auto-apply'
                      };
                      const x = await api('/api/epoch-upgrade-proof', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
                      renderUpgradeProof(x);
                    }
                    function renderUpgradeProof(x){
                      const cards = (x.proposals || []).map(p => `
                        <div class="epoch-card">
                          <h3>${esc(p.id)} <span class="hot">${esc(p.subsystem)}</span></h3>
                          <div><b>Problem:</b> ${esc(p.problem)}</div>
                          <div><b>Evidence:</b> ${esc(p.evidence)}</div>
                          <div><b>PROPOSED CHANGE:</b> <span class="hot">${esc(p.proposedChange)}</span></div>
                          <div><b>Acceptance Test:</b> ${esc(p.acceptanceTest)}</div>
                          <div><b>Test Result:</b> <span class="tbd">${esc(p.testResult || 'TBD')}</span></div>
                          <pre class="diagram">${esc(p.diagram)}</pre>
                        </div>`).join('');
                      printHtml(`<div><b>Version:</b> ${esc(x.version)} | <b>SHA-256:</b> ${esc(x.sha256)} | <span class="tbd">${esc(x.approvalStatus)}</span></div>
                        <pre class="diagram">${esc(x.diagram)}</pre>
                        <div class="proposal-grid">${cards}</div>`);
                    }
                    async function captureBenchmark(){
                      const body = {reason:'manual_sdk_capture', timestamp:new Date().toISOString()};
                      const x = await api('/api/benchmark-snapshot', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
                      print(x);
                      await loadBenchmarks(false);
                    }
                    async function loadBenchmarks(show){
                      const x = await api('/api/benchmarks?limit=40');
                      renderBenchChart(x.history || []);
                      if (show) print(x);
                    }
                    function serviceMs(s, name){
                      return s && s[name] && typeof s[name].durationMs === 'number' ? s[name].durationMs : 0;
                    }
                    function parseHistory(lines){
                      return lines.map(line => { try { return JSON.parse(line); } catch { return null; } }).filter(Boolean);
                    }
                    function renderBenchChart(lines){
                      if (!benchChart) return;
                      const ctx = benchChart.getContext('2d');
                      const w = benchChart.width, h = benchChart.height;
                      ctx.clearRect(0,0,w,h);
                      ctx.fillStyle = '#010409'; ctx.fillRect(0,0,w,h);
                      ctx.strokeStyle = '#30363d'; ctx.lineWidth = 1;
                      for (let i=1;i<5;i++){ const y = i*h/5; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke(); }
                      const data = parseHistory(lines).slice(-40);
                      ctx.fillStyle = '#8b949e'; ctx.font = '12px Consolas';
                      if (!data.length){ ctx.fillText('Capture a benchmark snapshot to start graphing.', 16, 28); return; }
                      const series = [
                        {name:'bridge', color:'#58a6ff', values:data.map(d => serviceMs(d.services, 'bridge8080'))},
                        {name:'house', color:'#3fb950', values:data.map(d => serviceMs(d.services, 'house11435'))},
                        {name:'shipper', color:'#d29922', values:data.map(d => serviceMs(d.services, 'shipper18081'))}
                      ];
                      const max = Math.max(50, ...series.flatMap(s => s.values));
                      series.forEach((s, si) => {
                        ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.beginPath();
                        s.values.forEach((v, i) => {
                          const x = 28 + (data.length === 1 ? 0 : i * (w - 56) / (data.length - 1));
                          const y = h - 30 - ((v / max) * (h - 60));
                          if (i === 0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
                        });
                        ctx.stroke();
                        ctx.fillStyle = s.color; ctx.fillText(`${s.name} ${s.values.at(-1)}ms`, 16 + si*150, 18);
                      });
                      ctx.fillStyle = '#8b949e'; ctx.fillText(`snapshots ${data.length} | max ${Math.round(max)}ms`, 16, h-10);
                    }
                    async function tail(file){ print(await api('/api/log-tail?file='+encodeURIComponent(file)+'&lines=80')); }
                    async function loadDesign(){ print(await api('/api/design')); }
                    loadState();
                  </script>
                </body>
                </html>
                """;
    }
}
