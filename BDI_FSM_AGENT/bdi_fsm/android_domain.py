"""ANDROID DOMAIN — the domain node configured for an Android/Termux target.

Binds the generic DomainGate + SymbolMapper + IntersectionSynthesizer to the
Android Framework. The generator emits ONLY code that is (a) inside the Android
namespace and (b) in the structural intersection of the reference projects.
"""
from typing import Dict, List, Set, Tuple

from .domain_node import DomainSpec, DomainGate, SymbolMapper, IntersectionSynthesizer

ANDROID_SPEC = DomainSpec(
    name="android",
    allowed_packages={
        "android.content", "android.os", "android.view", "android.widget",
        "android.app", "androidx.appcompat.app", "android.bluetooth",
        "android.net", "com.android.tools",
    },
    allowed_commands={"adb_shell", "gradlew_build", "install_apk", "logcat_stream"},
    allowed_tools={"adb", "gradlew"},
)

# package -> import line to add when a mapped symbol needs it
TYPE_IMPORTS = {
    "Context": "android.content.Context",
    "BluetoothAdapter": "android.bluetooth.BluetoothAdapter",
    "ConnectivityManager": "android.net.ConnectivityManager",
    "Intent": "android.content.Intent",
}


class AndroidCodeGenerator:
    """Generate a Java class from the mapped symbols + code-construct
    intersection, after the domain gate passes."""

    def __init__(self, spec: DomainSpec = ANDROID_SPEC,
                 threshold_dban: float = 5.0):
        self.gate = DomainGate(spec)
        self.threshold_dban = threshold_dban

    def synthesize(self, target_intent: str,
                   mapped_vars: List[Tuple], intersection: List[str],
                   commands: List[str]) -> str:
        # derive imports ONLY from the mapped symbol types (never a blanket
        # list — a non-intersection symbol must not leak an import)
        needed = set()
        for a, b, _ in mapped_vars:
            for n in (a.type_hint, b.type_hint):
                if n in TYPE_IMPORTS:
                    needed.add(TYPE_IMPORTS[n])
        import_lines = sorted(needed)

        # 1. domain gate — reject any out-of-bound import/command
        bad_i, bad_c = self.gate.violations(import_lines, commands)
        if bad_i or bad_c:
            raise PermissionError(
                f"outside android domain: imports={bad_i} commands={bad_c}")

        lines = [
            "// Auto-generated at the project intersection (Android domain)",
            f"// intent: {target_intent}",
            "package com.generated.domain;",
            "",
        ]
        for imp in import_lines:
            lines.append(f"import {imp};")
        lines += ["", "public class GeneratedActivity extends android.app.Activity {", ""]

        # 3. inject unified variable bindings from the symbol mapper
        for a, b, score in mapped_vars:
            lines.append(f"    // map ({score:.1f} dBan): "
                         f"{a.project}.{a.name} <==> {b.project}.{b.name}")
            lines.append(f"    private {a.type_hint} unified_{a.name};")

        # 4. inject only the lifecycle methods that are in the intersection
        if intersection:
            lines.append("")
        if "onCreate" in intersection:
            lines += ["    @Override",
                      "    protected void onCreate(android.os.Bundle b) {",
                      "        super.onCreate(b);",
                      "        // intersection onCreate",
                      "    }"]
        if "onResume" in intersection:
            lines += ["    @Override",
                      "    protected void onResume() {",
                      "        super.onResume();",
                      "    }"]
        if "onDestroy" in intersection:
            lines += ["    @Override",
                      "    protected void onDestroy() {",
                      "        super.onDestroy();",
                      "    }"]
        lines += ["", "}"]
        return "\n".join(lines)


def synthesize_android(target_intent: str, project_a: Dict, project_b: Dict,
                       a_features: Set[str], b_features: Set[str],
                       commands: List[str]) -> str:
    """End-to-end: map symbols, compute the intersection, generate the class."""
    mapper = SymbolMapper()
    for name, (t, scope) in project_a.items():
        mapper.register("A", name, t, scope)
    for name, (t, scope) in project_b.items():
        mapper.register("B", name, t, scope)
    mapped = mapper.find_intersections()

    synth = IntersectionSynthesizer()
    synth.register_constructs(sorted(a_features | b_features))
    synth.observe_project(a_features)
    synth.observe_project(b_features)
    inter = synth.extract()

    gen = AndroidCodeGenerator()
    return gen.synthesize(target_intent, mapped, inter, commands=commands)
