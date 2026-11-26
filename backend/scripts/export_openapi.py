"""Export the FastAPI OpenAPI schema to JSON for frontend TypeScript type generation."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/export_openapi.py <output_path>")

    output_path = Path(sys.argv[1]).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    output_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Exported OpenAPI schema to {output_path}")


if __name__ == "__main__":
    main()

