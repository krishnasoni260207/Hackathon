# Testing

Run tests from the project root:

```bash
python -m pytest
```

Current tests cover the small in-memory conversation state and confirm that interruption detection is still not implemented. Later phases should replace placeholder tests with behavior-focused tests for voice handling, stale-response prevention, recovery, and latency.
