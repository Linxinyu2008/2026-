"""附件协议对应的官方模拟器 HTTP 客户端。

客户端只负责串行请求、响应校验、现实时间预算和同一 request_id 重试；
策略状态仍由上层控制器维护。未启动官方模拟器时不会自动发起请求。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OfficialClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class OfficialSession:
    enter_response: dict[str, Any]
    started_monotonic: float
    max_real_duration_s: float


class OfficialSimulatorClient:
    def __init__(self, base_url: str, robot_id: str, *, timeout_s: float = 5.0, retries: int = 2) -> None:
        self.base_url = base_url.rstrip("/")
        self.robot_id = robot_id
        self.timeout_s = float(timeout_s)
        self.retries = int(retries)
        self.session: OfficialSession | None = None
        self._request_counter = 0
        self.http_request_count = 0
        self.retry_count = 0
        # 按附件要求保留完整的请求/响应轨迹，供演练复盘和提交材料整理使用。
        self.request_log: list[dict[str, Any]] = []

    def _request_id(self, prefix: str) -> str:
        self._request_counter += 1
        return f"{prefix}-{self._request_counter:06d}"

    def _base(self, request_id: str) -> dict[str, Any]:
        return {"arena_id": "default", "robot_id": self.robot_id, "request_id": request_id}

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            started = time.monotonic()
            try:
                self.http_request_count += 1
                if attempt:
                    self.retry_count += 1
                with urlopen(request, timeout=self.timeout_s) as response:
                    result = json.loads(response.read().decode("utf-8"))
                if not isinstance(result, dict):
                    raise OfficialClientError("官方响应不是JSON对象")
                self.request_log.append({
                    "sequence": self.http_request_count,
                    "path": path,
                    "request_id": payload.get("request_id"),
                    "attempt": attempt + 1,
                    "payload": payload,
                    "response": result,
                    "error": None,
                    "elapsed_wall_s": time.monotonic() - started,
                })
                return result
            except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, OfficialClientError) as exc:
                last_error = exc
                self.request_log.append({
                    "sequence": self.http_request_count,
                    "path": path,
                    "request_id": payload.get("request_id"),
                    "attempt": attempt + 1,
                    "payload": payload,
                    "response": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "elapsed_wall_s": time.monotonic() - started,
                })
                time.sleep(0.05)
        raise OfficialClientError(f"请求{path}失败，已用同一request_id重试: {last_error}")

    def enter(self) -> dict[str, Any]:
        response = self._post("/enter", self._base(self._request_id("enter")))
        if response.get("accepted") is not True:
            raise OfficialClientError(f"/enter未接受: {response}")
        max_real = float(response.get("max_real_duration_s", 1200.0))
        self.session = OfficialSession(response, time.monotonic(), max_real)
        return response

    def _check_budget(self) -> None:
        if self.session is None:
            raise OfficialClientError("必须先成功调用/enter")
        elapsed = time.monotonic() - self.session.started_monotonic
        remaining = float(self.session.enter_response.get("remaining_real_duration_s", self.session.max_real_duration_s))
        if elapsed >= min(self.session.max_real_duration_s, remaining):
            raise OfficialClientError("现实运行时间预算已耗尽，停止发送新动作")

    def measure(self, x: float, y: float, channel: int) -> dict[str, Any]:
        self._check_budget()
        payload = self._base(self._request_id("measure"))
        payload.update({"position": {"x": float(x), "y": float(y)}, "channel": int(channel)})
        response = self._post("/measure", payload)
        if response.get("accepted") is not True:
            raise OfficialClientError(f"/measure未接受: {response}")
        return response

    def clear(self, x: float, y: float, channel: int) -> dict[str, Any]:
        self._check_budget()
        payload = self._base(self._request_id("clear"))
        payload.update({"position": {"x": float(x), "y": float(y)}, "channel": int(channel)})
        response = self._post("/clear", payload)
        if response.get("accepted") is not True:
            raise OfficialClientError(f"/clear未接受: {response}")
        return response

    def exit(self) -> dict[str, Any]:
        if self.session is None:
            raise OfficialClientError("没有正在运行的官方会话")
        response = self._post("/exit", self._base(self._request_id("exit")))
        if response.get("accepted") is not True:
            raise OfficialClientError(f"/exit未接受: {response}")
        return response
