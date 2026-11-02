"""Fail if private namespaces or internal artifacts enter the public source tree."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
forbidden = {"f4_private", "f4-commercial", "client_data", "credentials", "product_spec.docx"}
violations = []
for path in root.rglob("*"):
    if any(
        part in {".git", ".venv", "build", "dist", "__pycache__"}
        for part in path.relative_to(root).parts
    ):
        continue
    if (
        path.name in forbidden
        or path.suffix.lower() in {".pem", ".key", ".docx"}
        or path.name == ".env"
    ):
        violations.append(str(path.relative_to(root)))
if violations:
    raise SystemExit("Unsafe public release paths: " + ", ".join(violations))
print("Public source boundary check passed")
