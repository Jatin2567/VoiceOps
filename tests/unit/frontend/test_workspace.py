"""Navigation must preserve an open call; ending it must clear the session."""
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest


def test_navigation_preserves_call_and_end_clears_it():
    response = Mock(status_code=200)
    response.json.return_value = {"session_id": "test-call"}
    with patch("httpx.Client") as client, patch("httpx.post", return_value=response), patch("httpx.delete", return_value=response):
        client.return_value.__enter__.return_value.get.return_value.status_code = 200
        client.return_value.__enter__.return_value.get.return_value.json.return_value = []
        app = AppTest.from_file(Path(__file__).resolve().parents[3] / "frontend/app.py", default_timeout=15).run()
        assert not app.exception
        next(b for b in app.button if b.label.startswith("Start a conversation")).click().run()
        assert not app.exception
        assert app.session_state["call_id"] == "test-call"
        for page in ("Reference", "Run history", "Benchmark lab", "Live call"):
            app.radio(key="workspace_page").set_value(page).run()
            assert not app.exception
            assert app.session_state["call_id"] == "test-call"
        next(b for b in app.button if b.label == "End conversation").click().run()
        assert not app.exception
        assert "call_id" not in app.session_state
