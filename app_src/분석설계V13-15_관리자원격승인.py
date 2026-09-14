"""분석설계 V13-15 관리자 원격승인판.

V13-14의 분석/출력 코드는 그대로 불러오고 이용권 UI와 저장/통신 계층만 교체한다.
"""
from __future__ import annotations

import importlib.util
import sys
import threading
from datetime import date, datetime
from pathlib import Path

from remote_license_v13_15 import DURATION_DAYS, RemoteLicenseClient, RemoteLicenseError, STATUS_KO, mask_phone


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "분석설계V13-14_해지계약출력제외.pyc"
if getattr(sys, "frozen", False):
    BASE_PATH = Path(getattr(sys, "_MEIPASS", HERE)) / BASE_PATH.name
spec = importlib.util.spec_from_file_location("analysis_v13_14_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("V13-14 기반 프로그램을 불러오지 못했습니다.")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)

base.CURRENT_APP_VERSION = "V13-15"
base.APP_TITLE = "분석설계 V13-15"
OriginalApp = base.InsuranceAnalysisApp
_original_init = OriginalApp.__init__
_original_calculate = OriginalApp.calculate_license_status
_original_close = OriginalApp.on_application_close


def _state_load(self):
    client = getattr(self, "remote_license_client", None)
    return client.store.load() if client else {}


def _state_save(self, state):
    client = getattr(self, "remote_license_client", None)
    if client:
        client.store.save(state)


def _calculate(self):
    active, expires, message = _original_calculate(self)
    client = getattr(self, "remote_license_client", None)
    if not client:
        return active, expires, message
    state = client.store.load()
    if state.get("remote_status") == "revoked":
        return False, expires, "관리자가 이용권 사용을 중지했습니다."
    if active and state.get("remote_license") and not client.offline_allowed():
        return False, expires, "마지막 서버 확인 후 3일이 지났습니다. 인터넷 연결 후 이용권을 확인해 주세요."
    return active, expires, message


def _remote_status_callback(self, snapshot, error):
    if error:
        try:
            self.log(f"[이용권] {error.user_message}")
        except Exception:
            pass
    self.refresh_license_nav_button()
    refresh = getattr(self, "_remote_license_dialog_refresh", None)
    if callable(refresh):
        refresh(snapshot, error)


def _new_init(self):
    _original_init(self)
    self.remote_license_client = RemoteLicenseClient(self, base.LICENSE_STATE_PATH, "V13-15")
    self.remote_license_client.start_polling(lambda s, e: _remote_status_callback(self, s, e))


def _new_close(self):
    client = getattr(self, "remote_license_client", None)
    if client:
        client.stop()
    _original_close(self)


def _refresh_nav(self):
    button = getattr(self, "license_nav_button", None)
    if button is None:
        return
    active, expires, _message = self.calculate_license_status()
    client = getattr(self, "remote_license_client", None)
    state = client.store.load() if client else {}
    status = str(state.get("remote_status") or "")
    if active and expires:
        button.configure(text=f"이용권 D-{max(0, (expires - date.today()).days)}", fg="#16734C", bg="#F0FAF5")
    elif status in {"payment_pending", "approval_pending"}:
        button.configure(text="관리자 승인 대기", fg="#B85C00", bg="#FFF4E5")
    elif status == "revoked":
        button.configure(text="이용권 중지", fg="#C62828", bg="#FFF0F0")
    else:
        started, remaining = self.trial_status()
        if started and remaining > 0:
            button.configure(text=f"체험판 {remaining}회", fg="#B85C00", bg="#FFF4E5")
        else:
            button.configure(text="이용권 신청", fg="#C62828", bg="#FFF0F0")


def _show_dialog(self, locked=False):
    tk, ttk, messagebox = base.tk, base.ttk, base.messagebox
    existing = getattr(self, "license_window", None)
    if existing is not None and existing.winfo_exists():
        existing.lift(); existing.focus_force(); return
    window = tk.Toplevel(self)
    self.license_window = window
    window.title("프로그램 이용권 · 관리자 원격 승인")
    window.geometry("760x790")
    window.minsize(700, 700)
    window.configure(bg="#F4F8FB")
    window.transient(self)
    tk.Label(window, text="프로그램 이용권", bg="#F2A65A", fg="white", font=("Malgun Gothic", 17, "bold"), padx=22, pady=16, anchor="w").pack(fill="x")
    body = tk.Frame(window, bg="#F4F8FB", padx=22, pady=16)
    body.pack(fill="both", expand=True)
    status_var = tk.StringVar(value="이용권 상태를 확인하고 있습니다.")
    status_label = tk.Label(body, textvariable=status_var, bg="white", fg="#173E68", font=("Malgun Gothic", 11, "bold"), padx=14, pady=12, anchor="w", justify="left", wraplength=680, relief="solid", bd=1)
    status_label.pack(fill="x", pady=(0, 12))

    form = tk.Frame(body, bg="white", padx=16, pady=14, highlightbackground="#D8E5F1", highlightthickness=1)
    form.pack(fill="x")
    form.columnconfigure(1, weight=1)
    state = self.remote_license_client.store.load()
    profile = self.settings
    fields = [
        ("신청자명", "applicant", state.get("license_applicant") or profile.get("user_full_name", "")),
        ("입금자명", "depositor", state.get("license_depositor", "")),
    ]
    vars_ = {}
    for row, (label, key, value) in enumerate(fields):
        tk.Label(form, text=label, bg="white", fg="#20364F", font=("Malgun Gothic", 9, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
        vars_[key] = tk.StringVar(value=value)
        ttk.Entry(form, textvariable=vars_[key]).grid(row=row, column=1, sticky="ew", pady=5, ipady=4)
    tk.Label(form, text="신청 이용기간", bg="white", fg="#20364F", font=("Malgun Gothic", 9, "bold")).grid(row=2, column=0, sticky="w", padx=(0, 12), pady=5)
    duration_var = tk.StringVar(value=state.get("license_duration", "1개월"))
    ttk.Combobox(form, textvariable=duration_var, values=tuple(DURATION_DAYS), state="readonly").grid(row=2, column=1, sticky="ew", pady=5, ipady=3)
    tk.Label(form, text="요청사항(선택)", bg="white", fg="#20364F", font=("Malgun Gothic", 9, "bold")).grid(row=3, column=0, sticky="nw", padx=(0, 12), pady=5)
    memo = tk.Text(form, height=3, wrap="word", font=("Malgun Gothic", 9))
    memo.grid(row=3, column=1, sticky="ew", pady=5)
    memo.insert("1.0", state.get("license_memo", ""))
    registered_phone = str(profile.get("user_phone", "")).strip()
    tk.Label(form, text="등록 휴대폰", bg="white", fg="#20364F", font=("Malgun Gothic", 9, "bold")).grid(row=4, column=0, sticky="w", padx=(0, 12), pady=5)
    tk.Label(
        form,
        text=(mask_phone(registered_phone) if registered_phone else "등록된 번호 없음 · 환경설정에서 사용자 정보를 등록해 주세요"),
        bg="#F7FAFC", fg=("#40566B" if registered_phone else "#C62828"),
        font=("Malgun Gothic", 9), anchor="w", padx=10, pady=8,
    ).grid(row=4, column=1, sticky="ew", pady=5)
    request_code = self.license_device_request_code()
    tk.Label(form, text="기기 요청코드", bg="white", fg="#20364F", font=("Malgun Gothic", 9, "bold")).grid(row=5, column=0, sticky="w", padx=(0, 12), pady=5)
    request_var = tk.StringVar(value=request_code)
    ttk.Entry(form, textvariable=request_var, state="readonly").grid(row=5, column=1, sticky="ew", pady=5, ipady=4)
    window._license_display_vars = (request_var, duration_var)
    tk.Label(body, text="입력하신 정보는 입금 확인과 프로그램 이용권 승인 목적으로만 사용됩니다.", bg="#F4F8FB", fg="#62758A", font=("Malgun Gothic", 8), anchor="w").pack(fill="x", pady=(8, 10))

    buttons = tk.Frame(body, bg="#F4F8FB")
    buttons.pack(fill="x")
    busy_var = tk.BooleanVar(value=False)

    def run_background(action, success_title):
        if busy_var.get(): return
        busy_var.set(True)
        status_var.set("서버와 안전하게 통신하고 있습니다…")
        def worker():
            try: result, error = action(), None
            except RemoteLicenseError as exc: result, error = None, exc
            except Exception as exc: result, error = None, RemoteLicenseError("요청 처리 중 오류가 발생했습니다.", type(exc).__name__)
            def finish():
                busy_var.set(False)
                refresh(result, error)
                if result and success_title: messagebox.showinfo(success_title, status_var.get(), parent=window)
                elif error: messagebox.showwarning("이용권 안내", error.user_message, parent=window)
            try: self.after(0, finish)
            except Exception: pass
        threading.Thread(target=worker, name="license-dialog-request", daemon=True).start()

    def submit():
        saved = self.remote_license_client.store.load()
        if not registered_phone:
            raise RemoteLicenseError("등록된 휴대폰번호가 없습니다. 환경설정의 사용자 정보에서 연락처를 먼저 등록해 주세요.")
        saved.update({"license_applicant": vars_["applicant"].get().strip(), "license_depositor": vars_["depositor"].get().strip(), "license_duration": duration_var.get(), "license_memo": memo.get("1.0", "end").strip()})
        self.remote_license_client.store.save(saved)
        return self.remote_license_client.submit(applicant=vars_["applicant"].get(), depositor=vars_["depositor"].get(), phone=registered_phone, duration_label=duration_var.get(), memo=memo.get("1.0", "end"), device_code=request_code)

    def refresh(snapshot=None, error=None):
        active, expires, message = self.calculate_license_status()
        if snapshot is not None:
            status = snapshot.status
            if status in {"payment_pending", "approval_pending"}:
                status_var.set(f"{STATUS_KO[status]} · 신청일시 {snapshot.requested_at.replace('T', ' ')[:16]}")
                status_label.configure(fg="#B85C00")
            elif status == "approved" and active and expires:
                status_var.set(f"이용권 사용 가능 · 만료일 {expires.isoformat()} · D-{max(0, (expires-date.today()).days)}")
                status_label.configure(fg="#16734C")
            elif status in {"rejected", "revoked"}:
                reason = snapshot.rejection_reason or snapshot.admin_note
                status_var.set(f"{STATUS_KO[status]}" + (f" · {reason}" if reason else ""))
                status_label.configure(fg="#C62828")
            else:
                status_var.set(STATUS_KO.get(status, "신청 전"))
        elif error:
            cached = self.remote_license_client.cached_status_text()
            status_var.set(f"인터넷 연결 확인 필요 · {cached}\n{error.user_message}")
            status_label.configure(fg="#B85C00")
        elif active and expires:
            status_var.set(f"이용권 사용 가능 · 만료일 {expires.isoformat()} · D-{max(0, (expires-date.today()).days)}")
            status_label.configure(fg="#16734C")
        else:
            status_var.set(self.remote_license_client.cached_status_text() or message)
        self.refresh_license_nav_button()

    self._remote_license_dialog_refresh = refresh
    request_button = self.make_button(
        buttons, "관리자 승인 요청",
        lambda: run_background(submit, "승인 요청 완료"), "secondary",
    )
    request_button.configure(
        bg="#F28C28", fg="#FFFFFF", activebackground="#DB7615",
        activeforeground="#FFFFFF", highlightbackground="#F28C28",
        font=("Malgun Gothic", 12, "bold"), padx=24, pady=11,
    )
    request_button.pack(side="left", padx=(0, 7))
    self.make_button(buttons, "승인 상태 다시 확인", lambda: run_background(self.remote_license_client.check, ""), "primary").pack(side="left", padx=7)
    self.make_button(buttons, "요청 취소", lambda: run_background(self.remote_license_client.cancel, "요청 취소"), "secondary").pack(side="left", padx=7)

    utility = tk.Frame(body, bg="#F4F8FB")
    utility.pack(fill="x", pady=(10, 0))
    self.make_button(utility, "기기 요청코드 복사", lambda: (self.clipboard_clear(), self.clipboard_append(request_code)), "secondary").pack(side="left")
    manual_wrap = tk.Frame(body, bg="#F4F8FB")
    manual_visible = tk.BooleanVar(value=False)

    def toggle_manual():
        if manual_visible.get():
            manual_wrap.pack_forget(); manual_visible.set(False)
        else:
            manual_wrap.pack(fill="both", expand=True, pady=(12, 0)); manual_visible.set(True)
    self.make_button(utility, "기존 승인코드 수동 등록", toggle_manual, "secondary").pack(side="left", padx=8)
    self.make_button(utility, "닫기", window.destroy, "secondary").pack(side="right")
    tk.Label(manual_wrap, text="비상용 승인코드", bg="#F4F8FB", fg="#173E68", font=("Malgun Gothic", 9, "bold")).pack(anchor="w")
    code_text = tk.Text(manual_wrap, height=5, wrap="char", font=("Consolas", 9), padx=8, pady=8)
    code_text.pack(fill="x", pady=(5, 7))

    def activate_manual():
        try:
            code = code_text.get("1.0", "end").strip()
            payload = self.verify_license_code(code, self.load_license_public_key())
            saved = self.remote_license_client.store.load()
            codes = list(saved.get("codes", []))
            if code not in codes: codes.append(code)
            saved["codes"] = codes
            saved["last_seen"] = date.today().isoformat()
            saved["manual_emergency_code"] = True
            self.remote_license_client.store.save(saved)
            ok, expiry, _ = self.calculate_license_status()
            if not ok: raise RemoteLicenseError("승인코드의 이용기간을 확인해 주세요.")
            self.refresh_license_nav_button()
            messagebox.showinfo("등록 완료", f"비상 승인코드가 등록되었습니다.\n만료일: {expiry.isoformat()}", parent=window)
            window.destroy()
        except Exception as exc:
            messagebox.showerror("승인코드 확인 실패", getattr(exc, "user_message", str(exc)), parent=window)
    self.make_button(manual_wrap, "승인코드 등록", activate_manual, "warning").pack(fill="x")

    def close_dialog():
        self._remote_license_dialog_refresh = None
        window.destroy()
    window.protocol("WM_DELETE_WINDOW", close_dialog)
    refresh()
    self.remote_license_client.check_async(refresh)


OriginalApp.__init__ = _new_init
OriginalApp.load_license_state = _state_load
OriginalApp.save_license_state = _state_save
OriginalApp.calculate_license_status = _calculate
OriginalApp.show_license_dialog = _show_dialog
OriginalApp.refresh_license_nav_button = _refresh_nav
OriginalApp.on_application_close = _new_close


def main() -> int:
    app = OriginalApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
