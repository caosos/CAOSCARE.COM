"""Small shared shapes for truth-preserving community runtime projections."""


def source_status(status: str, error: str | None = None) -> dict:
    return {"status": status, "error": error}


def append_error(errors: list[dict], source: str, code: str) -> None:
    errors.append({"source": source, "code": code})
