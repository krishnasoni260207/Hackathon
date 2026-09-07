from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_loads_without_import_errors() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"

    app = AppTest.from_file(str(app_path), default_timeout=20).run()

    assert not app.exception


def test_streamlit_typed_pipeline_returns_mock_output() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"

    app = AppTest.from_file(str(app_path), default_timeout=20).run()
    app.chat_input(key="voice_chat_input").set_value("Explain recursion simply").run()

    assert not app.exception
    assert app.session_state["latest_response_text"]
    assert app.session_state["latest_audio_bytes"][:4] == b"RIFF"
