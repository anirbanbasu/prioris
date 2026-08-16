import json
from types import SimpleNamespace

import _mcp_client as helper
import anyio
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData
from pydantic import BaseModel


class _Widget(BaseModel):
    name: str


def test_client_builds_against_in_process_app() -> None:
    assert isinstance(helper.client(), Client)


def test_call_tool_returns_validated_model(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        assert name == "some_tool"
        assert arguments == {"x": 1}
        return SimpleNamespace(structured_content={"name": "widget"}, data=None)

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    async def run() -> _Widget:
        async with helper.client() as c:
            return await helper.call_tool(c, "some_tool", {"x": 1}, _Widget)

    assert anyio.run(run) == _Widget(name="widget")


def test_call_tool_without_model_returns_raw_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(structured_content={"result": False}, data=False)

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    async def run() -> object:
        async with helper.client() as c:
            return await helper.call_tool(c, "research_notes_delete", {"note_id": "x"})

    assert anyio.run(run) is False


def test_call_tool_exits_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        raise ToolError("boom")

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    async def run() -> object:
        async with helper.client() as c:
            return await helper.call_tool(c, "some_tool", {}, _Widget)

    with pytest.raises(SystemExit, match="boom"):
        anyio.run(run)


def test_call_tool_exits_on_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(structured_content={"unexpected": "shape"}, data=None)

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    async def run() -> object:
        async with helper.client() as c:
            return await helper.call_tool(c, "some_tool", {}, _Widget)

    with pytest.raises(SystemExit, match="unexpected response shape"):
        anyio.run(run)


def test_read_resource_returns_validated_model(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_read_resource(
        self: Client, uri: str, **kwargs: object
    ) -> list[object]:
        return [SimpleNamespace(text=json.dumps({"name": "widget"}))]

    monkeypatch.setattr(Client, "read_resource", fake_read_resource)

    async def run() -> _Widget:
        async with helper.client() as c:
            return await helper.read_resource(c, "research://fake", _Widget)

    assert anyio.run(run) == _Widget(name="widget")


def test_read_resource_exits_on_mcp_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_read_resource(
        self: Client, uri: str, **kwargs: object
    ) -> list[object]:
        raise McpError(ErrorData(code=-1, message="not found"))

    monkeypatch.setattr(Client, "read_resource", fake_read_resource)

    async def run() -> _Widget:
        async with helper.client() as c:
            return await helper.read_resource(c, "research://fake", _Widget)

    with pytest.raises(SystemExit, match="not found"):
        anyio.run(run)


def test_read_resource_exits_on_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_read_resource(
        self: Client, uri: str, **kwargs: object
    ) -> list[object]:
        return [SimpleNamespace(text="not json")]

    monkeypatch.setattr(Client, "read_resource", fake_read_resource)

    async def run() -> _Widget:
        async with helper.client() as c:
            return await helper.read_resource(c, "research://fake", _Widget)

    with pytest.raises(SystemExit, match="unexpected response shape"):
        anyio.run(run)
