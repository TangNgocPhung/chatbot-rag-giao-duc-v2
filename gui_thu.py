"""
GỬI THƯ ĐIỆN TỬ (mã xác minh tài khoản)
=======================================
Chỉ dùng smtplib của thư viện chuẩn. Mặc định là Gmail: bật xác minh 2 bước
cho hộp thư gửi đi, tạo "Mật khẩu ứng dụng" ở
https://myaccount.google.com/apppasswords rồi đặt trong khoa_api.bat:

    set "RAG_SMTP_TAI_KHOAN=hopthu@gmail.com"
    set "RAG_SMTP_MAT_KHAU=abcd efgh ijkl mnop"

Dịch vụ khác (Outlook, Brevo...) thì đặt thêm RAG_SMTP_MAY_CHU, RAG_SMTP_CONG
(465 = SSL, 587 = STARTTLS) và RAG_SMTP_NGUOI_GUI nếu địa chỉ gửi khác tài khoản.
Chưa đặt tài khoản thì da_cau_hinh() trả về False và giao diện ẩn nút xác minh.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

TEN_NGUOI_GUI = "Chatbot RAG Giáo dục"
GIAY_CHO_MAY_CHU = 20


class LoiGuiThu(RuntimeError):
    pass


def _cau_hinh() -> dict:
    tai_khoan = os.getenv("RAG_SMTP_TAI_KHOAN", "").strip()
    return {
        "may_chu": os.getenv("RAG_SMTP_MAY_CHU", "smtp.gmail.com").strip(),
        "cong": int(os.getenv("RAG_SMTP_CONG", "465") or 465),
        "tai_khoan": tai_khoan,
        # Google hiển thị mật khẩu ứng dụng thành 4 cụm có dấu cách; bỏ cách đi.
        "mat_khau": os.getenv("RAG_SMTP_MAT_KHAU", "").replace(" ", ""),
        "nguoi_gui": os.getenv("RAG_SMTP_NGUOI_GUI", "").strip() or tai_khoan,
    }


def da_cau_hinh() -> bool:
    ch = _cau_hinh()
    return bool(ch["tai_khoan"] and ch["mat_khau"])


def gui(den: str, tieu_de: str, noi_dung: str, noi_dung_html: str | None = None) -> None:
    ch = _cau_hinh()
    if not (ch["tai_khoan"] and ch["mat_khau"]):
        raise LoiGuiThu("Máy chủ chưa cấu hình gửi thư.")
    thu = EmailMessage()
    thu["From"] = formataddr((TEN_NGUOI_GUI, ch["nguoi_gui"]))
    thu["To"] = den
    thu["Subject"] = tieu_de
    thu["Message-ID"] = make_msgid(domain=ch["nguoi_gui"].rsplit("@", 1)[-1])
    thu.set_content(noi_dung)
    if noi_dung_html:
        thu.add_alternative(noi_dung_html, subtype="html")
    ngu_canh = ssl.create_default_context()
    try:
        if ch["cong"] == 465:
            with smtplib.SMTP_SSL(ch["may_chu"], ch["cong"], context=ngu_canh, timeout=GIAY_CHO_MAY_CHU) as smtp:
                smtp.login(ch["tai_khoan"], ch["mat_khau"])
                smtp.send_message(thu)
        else:
            with smtplib.SMTP(ch["may_chu"], ch["cong"], timeout=GIAY_CHO_MAY_CHU) as smtp:
                smtp.starttls(context=ngu_canh)
                smtp.login(ch["tai_khoan"], ch["mat_khau"])
                smtp.send_message(thu)
    except smtplib.SMTPAuthenticationError as exc:
        raise LoiGuiThu("Máy chủ thư từ chối đăng nhập - kiểm tra lại mật khẩu ứng dụng.") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise LoiGuiThu(f"Không gửi được thư: {exc}") from exc


def gui_ma_xac_minh(den: str, ten: str, ma: str, phut_hieu_luc: int) -> None:
    tieu_de = f"{ma} là mã xác minh tài khoản của bạn"
    van_ban = (
        f"Chào {ten},\n\n"
        f"Mã xác minh email cho tài khoản Chatbot RAG Giáo dục của bạn là:\n\n"
        f"    {ma}\n\n"
        f"Mã có hiệu lực trong {phut_hieu_luc} phút. Nếu bạn không yêu cầu mã này, "
        f"hãy bỏ qua thư - tài khoản của bạn vẫn an toàn.\n"
    )
    ten_html = ten.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:440px;margin:0 auto;color:#10233f">
  <p>Chào {ten_html},</p>
  <p>Mã xác minh email cho tài khoản <b>Chatbot RAG Giáo dục</b> của bạn là:</p>
  <p style="font-size:30px;font-weight:700;letter-spacing:8px;margin:18px 0;padding:14px 0;
     text-align:center;background:#eef3fb;border-radius:12px">{ma}</p>
  <p style="color:#51607a;font-size:13px">Mã có hiệu lực trong {phut_hieu_luc} phút. Nếu bạn
     không yêu cầu mã này, hãy bỏ qua thư - tài khoản của bạn vẫn an toàn.</p>
</div>"""
    gui(den, tieu_de, van_ban, html)
