import os
import json
import uuid
import time
import httpx
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from core.config import DATA_DIR

ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")

class MuseAccount(BaseModel):
    id: str
    email: str
    cookie: str
    status: str = "active"  # "active", "expired", "quota_limit", "disabled"
    daily_limit: int = -1   # -1: unlimited
    used_today: int = 0
    total_used: int = 0
    last_used: Optional[str] = None
    last_checked: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str
    auth_type: str = "cookie"  # "cookie" or "otp"
    state_dir: Optional[str] = None

def parse_cookie_line(line: str) -> tuple[str, str]:
    """Parse line formatted as email|cookie or just cookie."""
    line = line.strip()
    if not line:
        return "", ""
    
    if "|" in line:
        parts = line.split("|", 1)
        email_cand = parts[0].strip()
        cookie_cand = parts[1].strip()
        if "@" in email_cand:
            return email_cand, cookie_cand
    
    # Try finding email inside cookie or generate a label
    label = f"acc_{int(time.time() * 1000) % 100000}"
    return label, line


def cookie_string_to_jar(cookie_str: str, domain: str = "muse.ai") -> list[dict]:
    """Convert raw Cookie header string to structured cookies.json list."""
    items = []
    for pair in (cookie_str or "").split(";"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            name = k.strip()
            val = v.strip()
            if name:
                items.append({
                    "name": name,
                    "value": val,
                    "domain": domain,
                    "path": "/",
                })
    return items

class AccountManager:
    def __init__(self):
        self.accounts: List[MuseAccount] = []
        self._current_index = 0
        self._pending_otp: dict = {}
        self.load()

    def load(self):
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.accounts = [MuseAccount(**item) for item in data]
                self._check_daily_reset()
            except Exception as e:
                print(f"[AccountManager] Load error: {e}")
                self.accounts = []
        else:
            self.accounts = []

    def save(self):
        os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump([acc.model_dump() for acc in self.accounts], f, indent=2, ensure_ascii=False)

    def _check_daily_reset(self):
        today = datetime.now().strftime("%Y-%m-%d")
        updated = False
        for acc in self.accounts:
            if acc.last_used and not acc.last_used.startswith(today):
                acc.used_today = 0
                if acc.status == "quota_limit":
                    acc.status = "active"
                updated = True
        if updated:
            self.save()

    def add_bulk(self, text: str) -> dict:
        added = 0
        skipped = 0
        now = datetime.now().isoformat()
        
        for raw_line in text.strip().splitlines():
            line = raw_line.strip()
            if not line:
                continue
            email, cookie = parse_cookie_line(line)
            if not cookie:
                skipped += 1
                continue
            
            # Check duplicate cookie
            existing = next((a for a in self.accounts if a.cookie == cookie), None)
            if existing:
                skipped += 1
                continue
            
            acc = MuseAccount(
                id=uuid.uuid4().hex[:12],
                email=email or f"muse_{len(self.accounts)+1}",
                cookie=cookie,
                status="active",
                created_at=now
            )
            self.accounts.append(acc)
            added += 1

        self.save()
        return {"added": added, "skipped": skipped, "total": len(self.accounts)}

    def add_one(self, email: str, cookie: str) -> MuseAccount:
        acc = MuseAccount(
            id=uuid.uuid4().hex[:12],
            email=email or f"muse_{len(self.accounts)+1}",
            cookie=cookie,
            status="active",
            created_at=datetime.now().isoformat(),
        )
        self.accounts.append(acc)
        self.save()
        return acc

    def delete(self, account_id: str) -> bool:
        initial_len = len(self.accounts)
        self.accounts = [a for a in self.accounts if a.id != account_id]
        if len(self.accounts) < initial_len:
            self.save()
            return True
        return False

    def toggle_status(self, account_id: str) -> Optional[MuseAccount]:
        acc = next((a for a in self.accounts if a.id == account_id), None)
        if acc:
            acc.status = "disabled" if acc.status == "active" else "active"
            self.save()
            return acc
        return None

    def get_available_accounts(self) -> List[MuseAccount]:
        self._check_daily_reset()
        avail = []
        for a in self.accounts:
            if a.status == "active":
                if a.daily_limit > 0 and a.used_today >= a.daily_limit:
                    continue
                avail.append(a)
        return avail

    def get_next_account(self, mode: str = "round_robin") -> Optional[MuseAccount]:
        avail = self.get_available_accounts()
        if not avail:
            return None

        if mode == "least_used":
            # Pick the one with the lowest used_today
            return min(avail, key=lambda a: (a.used_today, a.total_used))
        
        # Round-robin
        self._current_index = (self._current_index + 1) % len(avail)
        return avail[self._current_index]

    def record_usage(self, account_id: str, success: bool = True, error: str = None):
        acc = next((a for a in self.accounts if a.id == account_id), None)
        if not acc:
            return
        
        now = datetime.now().isoformat()
        acc.last_used = now
        
        if success:
            acc.used_today += 1
            acc.total_used += 1
            acc.status = "active"
            acc.last_error = None
        else:
            acc.last_error = error or "Unknown error"
            err_lower = (error or "").lower()
            # Only change account status if the error actually pertains to the Muse account/session
            is_muse_related = any(kw in err_lower for kw in ["muse", "metaaivm", "session", "cookie", "token", "hatch_vm", "notary"])
            if is_muse_related:
                if "quota" in err_lower or "hết lượt" in err_lower:
                    acc.status = "quota_limit"
                elif "unauthorized" in err_lower or "401" in err_lower or "auth" in err_lower or "expired" in err_lower:
                    acc.status = "expired"

        self.save()

    async def check_health(self, account_id: str, proxy: Optional[str] = None) -> dict:
        acc = next((a for a in self.accounts if a.id == account_id), None)
        if not acc:
            return {"success": False, "error": "Account not found"}
        
        headers = {
            "Cookie": acc.cookie,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        }
        
        url = "https://muse.ai/api/session"
        try:
            async with httpx.AsyncClient(timeout=10.0, proxy=proxy) as client:
                resp = await client.get(url, headers=headers)
                now = datetime.now().isoformat()
                acc.last_checked = now
                
                if resp.status_code in (200, 201):
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    acc.status = "active"
                    acc.last_error = None
                    self.save()
                    return {"success": True, "status": "active", "status_code": resp.status_code, "data": data}
                elif resp.status_code == 401:
                    acc.status = "expired"
                    acc.last_error = "Cookie hết hạn hoặc không hợp lệ (401)"
                    self.save()
                    return {"success": False, "status": "expired", "error": acc.last_error}
                else:
                    acc.last_error = f"HTTP {resp.status_code}"
                    self.save()
                    return {"success": False, "status": acc.status, "error": acc.last_error}
        except Exception as e:
            acc.last_error = str(e)
            self.save()
            return {"success": False, "error": str(e)}

    async def check_all(self, proxy: Optional[str] = None) -> dict:
        active = 0
        dead = 0
        for acc in self.accounts:
            res = await self.check_health(acc.id, proxy=proxy)
            if res.get("success"):
                active += 1
            else:
                dead += 1
        return {"total": len(self.accounts), "active": active, "dead": dead}

    def ensure_account_state(self, acc: MuseAccount) -> str:
        """Ensure an account has a valid state_dir with cookies.json for MuseClient."""
        if not acc.state_dir or not os.path.exists(acc.state_dir):
            acc.state_dir = os.path.join(DATA_DIR, "muse_states", acc.id)
            os.makedirs(acc.state_dir, exist_ok=True)
            self.save()

        cookie_file = os.path.join(acc.state_dir, "cookies.json")
        if not os.path.exists(cookie_file) and acc.cookie:
            jar = cookie_string_to_jar(acc.cookie)
            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump(jar, f, indent=2, ensure_ascii=False)
        return acc.state_dir

    async def request_otp(self, email: str, proxy: Optional[str] = None) -> dict:
        """Send an OTP code to user's email via MuseAuth."""
        email = email.strip()
        if not email or "@" not in email:
            return {"success": False, "error": "Email không hợp lệ"}

        from core.muse_ai.auth import MuseAuth

        temp_state = os.path.join(
            DATA_DIR, "muse_states", f"temp_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        )
        os.makedirs(temp_state, exist_ok=True)

        try:
            auth = MuseAuth(state_dir=temp_state)
            await auth.restart_login()
            await auth.send_otp(email)
            self._pending_otp[email] = {
                "auth": auth,
                "state_dir": temp_state,
                "created_at": time.time(),
            }
            return {
                "success": True,
                "email": email,
                "message": f"Mã xác thực OTP đã được gửi đến {email}. Vui lòng kiểm tra hộp thư.",
            }
        except Exception as exc:
            return {"success": False, "error": f"Không thể gửi OTP: {exc}"}

    async def confirm_otp(self, email: str, otp_code: str) -> dict:
        """Verify OTP code and save session into account pool."""
        email = email.strip()
        otp_code = otp_code.strip()
        if not email or not otp_code:
            return {"success": False, "error": "Vui lòng nhập đầy đủ Email và Mã OTP"}

        pending = self._pending_otp.get(email)
        if not pending:
            return {
                "success": False,
                "error": "Phiên OTP không tồn tại hoặc đã hết hạn. Vui lòng bấm gửi lại mã.",
            }

        auth = pending["auth"]
        try:
            await auth.confirm_otp(otp_code)
            await auth.save_account()
            check = await auth.auth_check()
            if not check.get("ok"):
                return {"success": False, "error": f"Xác thực tài khoản thất bại: {check}"}

            acc_id = f"acc_{uuid.uuid4().hex[:8]}"
            final_state_dir = os.path.join(DATA_DIR, "muse_states", acc_id)
            os.makedirs(final_state_dir, exist_ok=True)
            cookie_file = os.path.join(final_state_dir, "cookies.json")
            await auth.save_cookies(cookie_file)

            cookie_str = ""
            if os.path.exists(cookie_file):
                with open(cookie_file, "r", encoding="utf-8") as f:
                    raw_cookies = json.load(f)
                    cookie_str = "; ".join(
                        [
                            f"{c['name']}={c['value']}"
                            for c in raw_cookies
                            if "name" in c and "value" in c
                        ]
                    )

            existing = next((a for a in self.accounts if a.email == email), None)
            now = datetime.now().isoformat()
            if existing:
                existing.cookie = cookie_str
                existing.state_dir = final_state_dir
                existing.status = "active"
                existing.auth_type = "otp"
                existing.last_error = None
                existing.last_checked = now
                target_acc = existing
            else:
                target_acc = MuseAccount(
                    id=acc_id,
                    email=email,
                    cookie=cookie_str,
                    status="active",
                    created_at=now,
                    auth_type="otp",
                    state_dir=final_state_dir,
                )
                self.accounts.append(target_acc)

            self.save()
            self._pending_otp.pop(email, None)
            return {
                "success": True,
                "account": target_acc.model_dump(),
                "message": f"Đăng nhập thành công tài khoản {email} qua OTP!",
            }
        except Exception as exc:
            return {"success": False, "error": f"Lỗi xác thực OTP: {exc}"}

account_manager = AccountManager()
