"""Tests for dynamic progress reporting during the expand phase."""
import queue

from scraper.worker import ScrapeWorker


def _make_worker() -> ScrapeWorker:
    return ScrapeWorker(post_url="https://example.com", event_queue=queue.Queue())


def _collect_progress_events(worker: ScrapeWorker, comment_count: int) -> list[dict]:
    worker._on_expand_progress(comment_count)
    events = []
    while not worker.event_queue.empty():
        events.append(worker.event_queue.get_nowait())
    return events


def test_progress_stays_at_43_when_total_unknown():
    worker = _make_worker()
    events = _collect_progress_events(worker, 50)
    progress_events = [e for e in events if e.type == "progress"]
    assert len(progress_events) == 1
    assert progress_events[0].payload["pct"] == 43


def test_progress_advances_when_total_known():
    worker = _make_worker()
    worker._total_count = 100

    # At 50% loaded — should land midway between 43 and 86
    events = _collect_progress_events(worker, 50)
    progress_events = [e for e in events if e.type == "progress"]
    pct = progress_events[0].payload["pct"]
    assert 43 < pct < 86


def test_progress_caps_at_86():
    worker = _make_worker()
    worker._total_count = 100

    # comment_count exceeds total — must not reach 87+ (that belongs to next stage)
    events = _collect_progress_events(worker, 200)
    progress_events = [e for e in events if e.type == "progress"]
    assert progress_events[0].payload["pct"] <= 86


def test_progress_label_includes_counts_when_total_known():
    worker = _make_worker()
    worker._total_count = 200

    events = _collect_progress_events(worker, 80)
    progress_events = [e for e in events if e.type == "progress"]
    label = progress_events[0].payload["action"]
    assert "80" in label
    assert "200" in label


def test_progress_label_shows_found_when_total_unknown():
    worker = _make_worker()
    events = _collect_progress_events(worker, 120)
    progress_events = [e for e in events if e.type == "progress"]
    label = progress_events[0].payload["action"]
    assert "120" in label
