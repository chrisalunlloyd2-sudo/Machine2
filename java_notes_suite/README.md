# VIPER Java Notes Dev Suite

Current SDK version:

```text
0.3.0-rolling-triplet-proof
```

Small Java/JDK HTTP notes and script index suite.

- Append-only notes in `java_notes_suite/data/notes.jsonl`.
- Script index for `.ps1`, `.bat`, and `.py` files under the project.
- No deletes. Existing files are merged by appending new notes only.
- Intended port: `8091`.

Run:

```powershell
.\java_notes_suite\START_NOTES_SUITE.ps1
```

Optional Cloudflare tunnel:

```powershell
.\java_notes_suite\START_NOTES_TUNNEL.ps1
```

Java must be installed and on `PATH`.

## VIPER Lab Suite

`ViperLabSuiteServer.java` is now the persistent Java SDK surface. It is a
separate VS Code-like dark control panel for backend benchmarks, user topology,
predictive prefetch, health checks, training logs, AB tests, quick settings,
Loihi/Lava experiment logging, service probes, and log tails.

It does not modify the locked main GUI.

Recursive training status:

```text
current: proposal/evaluation epochs are logged with SHA-256 proof
current: benchmark snapshots are graphed in the Java SDK
current: ASCII epoch proposals can wait in a queue for chooser/DB/Karoo/Loihi/Lava/SOAP/ledger/network work
current: queued ASCII epochs include a VS Code-like proposed-change diagram with highlighted subsystem, variable, and judge
current: upgrade proof epochs analyze live subsystem evidence and generate concrete proposed changes with acceptance tests
current: upgrade proposals are high-contrast cards with highlighted proposed changes and `TBD` test results
current: rolling triplet restore, tail continuation, inference optimization stack, distributed resource app, and axiomatic weighted truth tables are approved upgrade proposals pending tests
not yet: real model-weight recursive training submission
```

Run:

```powershell
.\java_notes_suite\START_LAB_SUITE.ps1
```

Local URL:

```text
http://127.0.0.1:18181
```

Standalone desktop app:

```powershell
.\java_notes_suite\BUILD_STANDALONE_APP.ps1
.\java_notes_suite\RUN_STANDALONE_APP.ps1
```

Output:

```text
java_notes_suite/dist/viper-java-sdk-standalone.jar
java_notes_suite/dist/app-image/VIPERJavaSDK/VIPERJavaSDK.exe
```

The standalone app starts or reuses the SDK server, then gives a small Java
desktop control surface with buttons for health, state, benchmarks, benchmark
capture, and ASCII epochs. The full themed SDK remains at `http://127.0.0.1:18181`.

Upgrade proof concept:

```text
POST /api/epoch-upgrade-proof
  -> reads bridge benchmarks, house health, shipper health, shipper log tail,
     and topology loop tail
  -> proposes surgical epoch upgrades
  -> highlights the subsystem/change/test
  -> appends SHA-256 proof to epoch_upgrade_proofs.jsonl
  -> does not auto-apply code
```

APK skeleton:

```text
android_apk_skeleton/
```

The APK skeleton is an Android WebView shell that loads the SDK endpoint. On a
phone, update `DEFAULT_SDK_URL` in `MainActivity.java` to the phone-hosted,
LAN, Cloudflare, or tunnel URL you want it to control.

If `javac` is missing, the script exits cleanly without changing the main
system.

Persistent files:

```text
java_notes_suite/data/sdk_settings.json
java_notes_suite/data/system_tests.jsonl
java_notes_suite/data/ab_tests.jsonl
java_notes_suite/data/training_runs.jsonl
java_notes_suite/data/recursive_training_epochs.jsonl
java_notes_suite/data/benchmark_snapshots.jsonl
java_notes_suite/data/ascii_epoch_queue.jsonl
java_notes_suite/data/epoch_upgrade_proofs.jsonl
java_notes_suite/data/loihi_experiments.jsonl
java_notes_suite/data/persistence_events.jsonl
```

Important endpoints:

```text
GET  /api/state
POST /api/run-test
POST /api/ab-test
POST /api/training
POST /api/recursive-training
GET  /api/benchmarks
POST /api/benchmark-snapshot
GET  /api/ascii-epochs
POST /api/ascii-epochs
POST /api/epoch-upgrade-proof
POST /api/loihi-experiment
GET  /api/log-tail?file=system&lines=80
GET  /api/design
```

Design document:

```text
C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
```
