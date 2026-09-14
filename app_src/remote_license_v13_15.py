"""V13-15 원격 이용권 클라이언트.

사용자 EXE에는 Supabase publishable key와 서명 검증용 공개키만 둔다.
승인 권한, service-role key, 서명 개인키는 Supabase Edge Function에만 둔다.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app_observability import protect_local_secret, unprotect_local_secret


VALID_STATUSES = frozenset({
    "payment_pending", "approval_pending", "approved", "rejected",
    "cancelled", "expired", "revoked",
})
STATUS_KO = {
    "payment_pending": "입금 확인 대기",
    "approval_pending": "관리자 승인 대기",
    "approved": "승인 완료",
    "rejected": "승인 거절",
    "cancelled": "요청 취소",
    "expired": "이용기간 만료",
    "revoked": "관리자 이용 중지",
}
DURATION_DAYS = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
LOCAL_ROOT = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "InsuranceAnalysisProgram" / "license"


class RemoteLicenseError(Exception):
    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 9 or len(digits) > 11:
        raise RemoteLicenseError("휴대폰번호를 정확히 입력해 주세요.")
    return digits


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) >= 7:
        return f"{digits[:3]}-****-{digits[-4:]}"
    return "***"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


class SecureLicenseStore:
    """승인 상태와 설치정보를 DPAPI 보호 + MAC 검증 형태로 저장한다."""

    def __init__(self, legacy_state_path):
        self.root = LOCAL_ROOT
        self.state_path = self.root / "license_state.json"
        self.identity_path = self.root / "installation_identity.bin"
        self.legacy_state_path = Path(legacy_state_path)
        self.root.mkdir(parents=True, exist_ok=True)
        self.install_id, self.install_secret = self._load_or_create_identity()
        self._migrate_once()

    def _load_or_create_identity(self):
        try:
            payload = json.loads(unprotect_local_secret(self.identity_path.read_bytes()).decode("utf-8"))
            install_id = str(uuid.UUID(str(payload["install_id"])))
            secret = bytes.fromhex(str(payload["secret"]))
            if len(secret) != 32:
                raise ValueError("invalid installation secret")
            return install_id, secret
        except Exception:
            install_id = str(uuid.uuid4())
            secret = secrets.token_bytes(32)
            encoded = json.dumps({"install_id": install_id, "secret": secret.hex()}).encode("utf-8")
            temporary = self.identity_path.with_suffix(".tmp")
            temporary.write_bytes(protect_local_secret(encoded))
            os.replace(temporary, self.identity_path)
            return install_id, secret

    @property
    def secret_hash(self) -> str:
        return hashlib.sha256(self.install_secret).hexdigest()

    def _sign(self, data: dict[str, Any]) -> str:
        canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(self.install_secret, canonical, hashlib.sha256).hexdigest()

    def _migrate_once(self) -> None:
        if self.state_path.exists() or not self.legacy_state_path.exists():
            return
        try:
            old = json.loads(self.legacy_state_path.read_text(encoding="utf-8"))
            if isinstance(old, dict):
                old["migrated_from_legacy"] = True
                self.save(old)
        except Exception:
            return

    def load(self) -> dict[str, Any]:
        try:
            envelope = json.loads(self.state_path.read_text(encoding="utf-8"))
            data = envelope.get("data")
            if not isinstance(data, dict):
                return {}
            if not hmac.compare_digest(str(envelope.get("mac", "")), self._sign(data)):
                return {}
            return data
        except Exception:
            return {}

    def save(self, state: dict[str, Any]) -> None:
        data = dict(state)
        envelope = {"version": 2, "data": data, "mac": self._sign(data)}
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.state_path)


@dataclass
class RemoteSnapshot:
    status: str = "payment_pending"
    request_id: str = ""
    requested_at: str = ""
    approved_at: str = ""
    starts_at: str = ""
    expires_at: str = ""
    admin_note: str = ""
    rejection_reason: str = ""
    license_code: str = ""
    server_time: str = ""

    @classmethod
    def from_payload(cls, payload):
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        if not isinstance(payload, dict):
            raise RemoteLicenseError("이용권 서버 응답을 확인할 수 없습니다.")
        status = str(payload.get("status", "") or "")
        if status not in VALID_STATUSES:
            raise RemoteLicenseError("서버에서 알 수 없는 이용권 상태를 받았습니다.")
        values = {}
        for name in cls.__dataclass_fields__:
            values[name] = str(payload.get(name, "") or "")
        return cls(**values)


class RemoteLicenseClient:
    def __init__(self, app, legacy_state_path, version):
        self.app = app
        self.store = SecureLicenseStore(legacy_state_path)
        self.version = version
        self.stop_event = threading.Event()
        self.after_id = None
        self.running = False
        self.last_snapshot: RemoteSnapshot | None = None
        self.last_error = ""

    def _rpc(self, function: str, payload: dict[str, Any]):
        obs = self.app.observability
        try:
            auth_result = obs.ensure_anonymous_auth()
            # Some AppObservability revisions return None on success; rely on token presence.
            if auth_result is False and not getattr(obs, "access_token", ""):
                raise RemoteLicenseError("인터넷 연결 또는 서버 인증을 확인해 주세요.")
        except RemoteLicenseError:
            raise
        except Exception as exc:
            raise RemoteLicenseError("인터넷 연결 또는 서버 인증을 확인해 주세요.", type(exc).__name__) from exc

        supabase_url = str(getattr(obs, "supabase_url", "") or "").rstrip("/")
        supabase_key = str(getattr(obs, "supabase_key", "") or "")
        access_token = str(getattr(obs, "access_token", "") or supabase_key)
        if not supabase_url or not supabase_key:
            raise RemoteLicenseError("인터넷 연결 또는 서버 인증을 확인해 주세요.")

        request = urllib.request.Request(
            f"{supabase_url}/rest/v1/rpc/{function}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            opener = getattr(obs, "_urlopen", urllib.request.urlopen)
            with opener(request, timeout=15) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
            if exc.code in {400, 404, 406} and ("PGRST202" in detail or exc.code in {404, 406}):
                raise RemoteLicenseError("이용권 데이터베이스 설정이 아직 완료되지 않았습니다.", detail) from exc
            raise RemoteLicenseError("이용권 서버가 요청을 처리하지 못했습니다.", f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RemoteLicenseError("인터넷 연결 또는 Supabase 서버 상태를 확인해 주세요.", type(exc).__name__) from exc
        try:
            return json.loads(raw) if raw else {}
        except Exception as exc:
            raise RemoteLicenseError("이용권 서버 응답을 확인할 수 없습니다.", type(exc).__name__) from exc

    def submit(self, *, applicant: str, depositor: str, phone: str, duration_label: str, memo: str, device_code: str):
        applicant = (applicant or "").strip()
        depositor = (depositor or "").strip()
        if not applicant or not depositor:
            raise RemoteLicenseError("신청자명과 입금자명을 입력해 주세요.")
        if duration_label not in DURATION_DAYS:
            raise RemoteLicenseError("신청 이용기간을 선택해 주세요.")
        payload = {
            "p_install_id": self.store.install_id,
            "p_install_secret_hash": self.store.secret_hash,
            "p_device_code": str(device_code or "")[:80],
            "p_applicant_name": applicant[:80],
            "p_depositor_name": depositor[:80],
            "p_phone_normalized": normalize_phone(phone),
            "p_requested_days": DURATION_DAYS[duration_label],
            "p_user_memo": str(memo or "")[:1000],
            "p_app_version": str(self.version or "")[:80],
        }
        return self._accept_snapshot(self._rpc("license_submit_request", payload))

    def check(self):
        payload = {"p_install_id": self.store.install_id, "p_install_secret_hash": self.store.secret_hash}
        return self._accept_snapshot(self._rpc("license_get_status", payload))

    def cancel(self):
        payload = {"p_install_id": self.store.install_id, "p_install_secret_hash": self.store.secret_hash}
        return self._accept_snapshot(self._rpc("license_cancel_request", payload))

    def _accept_snapshot(self, payload):
        snapshot = RemoteSnapshot.from_payload(payload)
        if snapshot.license_code:
            try:
                public_record = self.app.verify_license_code(snapshot.license_code, self.app.load_license_public_key())
            except Exception as exc:
                raise RemoteLicenseError("서버 승인 서명을 확인할 수 없습니다.", type(exc).__name__) from exc
            signed = str(public_record.get("rid", "") or "").upper()
            expected = str(self.app.license_device_request_code() or "").upper()
            if signed != expected:
                raise RemoteLicenseError("승인된 설치정보가 현재 PC와 일치하지 않습니다.")
            state = self.store.load()
            codes = list(state.get("codes", []))
            if snapshot.license_code not in codes:
                codes.append(snapshot.license_code)
            state["codes"] = codes
            state["remote_license"] = True
            self.store.save(state)

        state = self.store.load()
        state.update({
            "remote_request_id": snapshot.request_id,
            "remote_status": snapshot.status,
            "remote_requested_at": snapshot.requested_at,
            "remote_expires_at": snapshot.expires_at,
            "remote_admin_note": snapshot.admin_note,
            "remote_rejection_reason": snapshot.rejection_reason,
            "last_server_check_at": _utc_now().isoformat(),
            "last_server_time": snapshot.server_time,
        })
        self.store.save(state)
        self.last_snapshot = snapshot
        self.last_error = ""
        return snapshot

    def cached_status_text(self) -> str:
        state = self.store.load()
        status = str(state.get("remote_status", "") or "")
        requested = str(state.get("remote_requested_at", "") or "")
        if status in {"payment_pending", "approval_pending"} and requested:
            stamp = requested.replace("T", " ")[:16]
            return f"{STATUS_KO.get(status, status)} · 신청일시 {stamp}"
        return STATUS_KO.get(status, "신청 전")

    def offline_allowed(self) -> bool:
        state = self.store.load()
        checked = _parse_time(str(state.get("last_server_check_at", "") or ""))
        return bool(checked and (_utc_now() - checked) <= timedelta(days=3))

    def check_async(self, callback: Callable[[RemoteSnapshot | None, RemoteLicenseError | None], None]) -> None:
        if self.running or self.stop_event.is_set():
            return
        self.running = True

        def worker():
            snapshot = None
            error = None
            try:
                snapshot = self.check()
            except RemoteLicenseError as exc:
                error = exc
                self.last_error = exc.user_message
            finally:
                self.running = False
                if not self.stop_event.is_set():
                    try:
                        self.app.after(0, lambda: callback(snapshot, error))
                    except Exception:
                        pass

        threading.Thread(target=worker, name="license-status-check", daemon=True).start()

    def start_polling(self, callback) -> None:
        def tick() -> None:
            if self.stop_event.is_set():
                return
            self.check_async(callback)
            self.after_id = self.app.after(60000, tick)
        self.after_id = self.app.after(1500, tick)

    def stop(self) -> None:
        self.stop_event.set()
        if self.after_id is not None:
            try:
                self.app.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
