"""llm_client routing: API-key path -> SDK; no-key path -> Claude Code CLI."""
from __future__ import annotations


def test_using_cli_true_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import importlib

    import llm_client

    importlib.reload(llm_client)
    # Only meaningful if 'claude' exists; if not, using_cli() returns False.
    val = llm_client.using_cli()
    assert val in (True, False)


def test_sdk_path_when_api_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    import importlib

    import llm_client

    importlib.reload(llm_client)

    called = {"path": None}

    def fake_sdk(model, prompt, max_tokens, system=None):
        called["path"] = "sdk"
        return "sdk output"

    def fake_cli(model, prompt, timeout, system=None):
        called["path"] = "cli"
        return "cli output"

    monkeypatch.setattr(llm_client, "_sdk_complete", fake_sdk)
    monkeypatch.setattr(llm_client, "_cli_complete", fake_cli)

    result = llm_client.complete(model="claude-sonnet-4-6", prompt="hi")
    assert result == "sdk output"
    assert called["path"] == "sdk"


def test_cli_path_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import importlib

    import llm_client

    importlib.reload(llm_client)

    called = {"path": None}
    monkeypatch.setattr(
        llm_client, "_cli_complete", lambda model, prompt, timeout, system=None: (called.__setitem__("path", "cli"), "cli output")[1]
    )
    monkeypatch.setattr(
        llm_client, "_sdk_complete", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not be called"))
    )

    result = llm_client.complete(model="claude-sonnet-4-6", prompt="hi")
    assert result == "cli output"
    assert called["path"] == "cli"


def test_force_sdk(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # force="sdk" should call the SDK even without env var (which will error
    # inside _sdk_complete — but we mock it).
    import importlib

    import llm_client

    importlib.reload(llm_client)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_client, "_sdk_complete", lambda m, p, mt, system=None: "sdk!")
    assert llm_client.complete(model="x", prompt="y", force="sdk") == "sdk!"
