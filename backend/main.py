"""Backend entry point and health check."""

PROJECT_NAME = "Interruptible Study Assistant"


def health_check() -> dict:
    """Return basic project health info."""
    return {"project": PROJECT_NAME, "status": "ok"}


if __name__ == "__main__":
    import json
    print(json.dumps(health_check(), indent=2))
