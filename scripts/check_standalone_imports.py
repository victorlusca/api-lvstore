from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
FORBIDDEN_PREFIXES = (
    "utils.",
    "commands.",
    "scripts.",
    "database.",
    "api.",
)


def main() -> int:
    violations = []
    pattern = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)", re.MULTILINE)

    for py_file in APP_DIR.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        for match in pattern.finditer(content):
            mod = match.group(1)
            if any(mod.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
                line = content[: match.start()].count("\n") + 1
                violations.append((py_file, line, mod))

    if not violations:
        print("OK: nenhum import externo proibido encontrado.")
        return 0

    print("ERRO: imports proibidos encontrados:")
    for file_path, line, mod in violations:
        rel = file_path.relative_to(ROOT)
        print(f" - {rel}:{line} -> {mod}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
