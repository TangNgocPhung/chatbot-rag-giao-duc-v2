"""
SỔ QUAN HỆ VĂN BẢN - HIỆU LỰC VÀ VĂN BẢN ĐI KÈM
================================================
Một văn bản quy phạm hiếm khi đọc riêng được. Thông tư A có thể:
  - đã bị Thông tư B THAY THẾ (A hết hiệu lực, phải trả lời theo B);
  - bị B BÃI BỎ MỘT PHẦN (vài điều của A không còn áp dụng);
  - được B SỬA ĐỔI, BỔ SUNG (đọc A mà không đọc B là trả lời theo chữ cũ);
  - được B HƯỚNG DẪN THI HÀNH (Luật -> Nghị định -> Thông tư);
  - có Quy chế/Phụ lục B BAN HÀNH KÈM THEO nằm ở tệp riêng.

van_ban_meta trích các quan hệ đó từ chính nội dung từng tệp. Module này gom
chúng lại thành một đồ thị trên SỐ HIỆU (không phải tên tệp - văn bản cũ có
thể không còn trong kho mà vẫn phải biết nó đã bị thay), bổ sung bằng sổ nhập
tay so_quan_he_van_ban.json cho những gì máy không tự đọc ra, rồi trả lời ba
câu hỏi cho tầng hỏi đáp:

  1. Văn bản này đang ở tình trạng hiệu lực nào?          -> nhan_hieu_luc()
  2. Khi trích văn bản này thì phải kéo thêm văn bản nào?  -> di_kem()
  3. Câu hỏi nhắc tới văn bản cũ thì văn bản nào thay nó?  -> van_ban_trong_cau_hoi()

CẬP NHẬT KHI CÓ VĂN BẢN MỚI: không huấn luyện lại gì cả. Văn bản mới vào kho
-> lượt nạp đêm lập chỉ mục -> dịch vụ khởi động lại dựng lại hồ sơ và đồ thị
này từ nội dung -> văn bản cũ tự đổi nhãn "Hết hiệu lực" và câu trả lời tự
chuyển sang văn bản mới. Sổ tay chỉ dùng khi máy đọc sót (ảnh quét hỏng) hoặc
đọc sai (ghi vào "loai_bo").

LƯU Ở ĐÂU: sổ tay vẫn là JSON (sửa tay, xem diff trên Git); đồ thị đã gộp được
ghi vào SQLite quan_he_van_ban.db (csdl_quan_he.py) mỗi lần dựng lại. Khi chạy,
đồ thị nằm trong bộ nhớ (self.ra / self.vao) để tra trên đường trả lời.

Chạy trực tiếp để xem báo cáo:  python quan_he_van_ban.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta

import csdl_quan_he
import van_ban_meta

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_SO_TAY = os.path.abspath(os.getenv(
    "RAG_SO_QUAN_HE", os.path.join(THU_MUC_DU_AN, "so_quan_he_van_ban.json")
))

# (tên quan hệ khi đọc xuôi "A ... B", khi đọc ngược "B ... bởi A")
TEN_QUAN_HE = {
    "thay_the": ("Thay thế", "Bị thay thế bởi"),
    "bai_bo_mot_phan": ("Bãi bỏ một phần", "Bị bãi bỏ một phần bởi"),
    "sua_doi": ("Sửa đổi, bổ sung", "Được sửa đổi, bổ sung bởi"),
    "huong_dan": ("Hướng dẫn thi hành", "Được hướng dẫn bởi"),
    "kem_theo": ("Ban hành kèm theo", "Có văn bản kèm theo"),
}

# Quan hệ làm đổi hiệu lực văn bản kia từ một ngày cụ thể - ngày hiệu lực của
# văn bản tác động. Hướng dẫn/kèm theo không có mốc riêng.
QUAN_HE_CO_MOC = {"thay_the", "bai_bo_mot_phan", "sua_doi"}

# Thứ tự ưu tiên khi chọn văn bản đi kèm để đưa thêm vào prompt: cái nào đọc
# thiếu thì câu trả lời SAI đứng trước, cái chỉ làm câu trả lời ĐẦY ĐỦ HƠN đứng sau.
# (loại quan hệ, chiều) - "vao": văn bản kia tác động lên văn bản đang trích.
UU_TIEN_DI_KEM = [
    ("thay_the", "vao"),         # văn bản mới thay văn bản đang trích
    ("sua_doi", "vao"),          # văn bản sửa đổi văn bản đang trích
    ("bai_bo_mot_phan", "vao"),
    ("kem_theo", "ra"),          # đang trích phụ lục -> văn bản chính
    ("kem_theo", "vao"),         # đang trích văn bản chính -> phụ lục
    ("sua_doi", "ra"),           # đang trích văn bản sửa đổi -> văn bản gốc
    ("bai_bo_mot_phan", "ra"),
    ("huong_dan", "vao"),        # Luật/Nghị định đang trích -> văn bản hướng dẫn
    ("huong_dan", "ra"),         # văn bản hướng dẫn -> Luật/Nghị định gốc
    # Văn bản cũ mà văn bản đang trích đã thay: đáng hiện cho người đọc biết,
    # còn di_kem() tự bỏ vì nó đã hết hiệu lực.
    ("thay_the", "ra"),
]
# Vai trò của văn bản được kéo thêm, nói từ phía nó: "Văn bản sửa đổi, bổ sung"
# (của nguồn đang trích).
VAI_TRO_DI_KEM = {
    ("thay_the", "vao"): "Văn bản thay thế",
    ("sua_doi", "vao"): "Văn bản sửa đổi, bổ sung",
    ("bai_bo_mot_phan", "vao"): "Văn bản bãi bỏ một phần",
    ("kem_theo", "ra"): "Văn bản chính",
    ("kem_theo", "vao"): "Phụ lục/Quy chế kèm theo",
    ("sua_doi", "ra"): "Văn bản gốc được sửa đổi",
    ("bai_bo_mot_phan", "ra"): "Văn bản gốc bị bãi bỏ một phần",
    ("huong_dan", "vao"): "Văn bản hướng dẫn thi hành",
    ("huong_dan", "ra"): "Văn bản được hướng dẫn",
    ("thay_the", "ra"): "Văn bản cũ đã bị thay",
}

# "124/2024" trong câu hỏi, không kèm mã loại.
MAU_SO_NAM = re.compile(r"(?<![\d/])(\d{1,4})\s*/\s*(\d{4})(?![\d/])")

# Thời điểm người hỏi muốn tra: "ngày 15/3/2023", "ngày 15 tháng 3 năm 2023",
# "tháng 3/2023", "năm 2023". Viết không dấu vì so trên câu đã bỏ dấu.
MAU_NGAY_CU_THE = re.compile(r"\bngay\s+(\d{1,2})\s*(?:/|-|\s+thang\s+)(\d{1,2})\s*(?:/|-|\s+nam\s+)(\d{4})\b")
MAU_THANG_NAM = re.compile(r"\bthang\s+(\d{1,2})\s*(?:/|-|\s+nam\s+)(\d{4})\b")
MAU_NAM = re.compile(r"\b(?:nam|nam hoc|thoi diem|vao|trong|tai)\s+(\d{4})\b")


def thoi_diem_trong_cau_hoi(cau_hoi: str, hom_nay: date | None = None) -> date | None:
    """
    Ngày mà câu hỏi muốn tra hiệu lực, hoặc None nếu hỏi về hiện tại.

    "Năm 2023 quy định dạy thêm thế nào?" cần văn bản ÁP DỤNG năm 2023, dù nay
    nó đã bị thay - chính vì thế văn bản cũ được giữ lại chứ không xoá. Chỉ có
    năm thì lấy ngày cuối năm (quy định đang áp dụng khi năm đó khép lại).
    Mốc từ năm nay trở đi coi như hỏi hiện tại; số hiệu "29/2023" không phải
    mốc thời gian vì mẫu đòi chữ "năm/ngày/tháng" đứng trước.
    """
    chuoi = van_ban_meta._bo_dau_thuong(cau_hoi or "")
    hom_nay = hom_nay or date.today()
    ung_vien = None
    if khop := MAU_NGAY_CU_THE.search(chuoi):
        ngay, thang, nam = (int(x) for x in khop.groups())
        try:
            ung_vien = date(nam, thang, ngay)
        except ValueError:
            return None
    elif khop := MAU_THANG_NAM.search(chuoi):
        thang, nam = (int(x) for x in khop.groups())
        if 1 <= thang <= 12:
            # Ngày cuối tháng = ngày đầu tháng sau lùi một ngày.
            ung_vien = date(nam + (thang == 12), thang % 12 + 1, 1) - timedelta(days=1)
    elif khop := MAU_NAM.search(chuoi):
        nam = int(khop.group(1))
        if nam < hom_nay.year:
            ung_vien = date(nam, 12, 31)
    if ung_vien and 1990 <= ung_vien.year and ung_vien < hom_nay:
        return ung_vien
    return None


# Câu hỏi tra quy định cũ mà không nêu mốc ngày: "Trước đây theo văn bản 124
# quy định thế nào?", "quy định cũ về dạy thêm", "trước khi bị thay thế".
MAU_LICH_SU = re.compile(
    r"\b(?:truoc day|truoc kia|hoi truoc|ngay truoc|thoi truoc|luc truoc|truoc khi"
    r"|quy dinh cu|van ban cu|ban cu|thong tu cu|nghi dinh cu|luat cu"
    r"|da het hieu luc|lich su|cac lan sua doi|qua cac thoi ky)\b"
)


def che_do_thoi_gian(cau_hoi: str, hom_nay: date | None = None) -> tuple[str, date | None]:
    """
    ("hien_hanh", None) - hỏi quy định đang áp dụng: chỉ tìm văn bản còn hiệu
    lực, văn bản mới hơn được ưu tiên.
    ("lich_su", ngày hoặc None) - hỏi quy định trước đây: mở kho văn bản cũ, và
    nếu có mốc ngày thì hiệu lực được tính tại mốc đó thay vì hôm nay.
    """
    thoi_diem = thoi_diem_trong_cau_hoi(cau_hoi, hom_nay)
    if thoi_diem:
        return "lich_su", thoi_diem
    if MAU_LICH_SU.search(van_ban_meta._bo_dau_thuong(cau_hoi or "")):
        return "lich_su", None
    return "hien_hanh", None


@dataclass(frozen=True)
class QuanHe:
    tu: str
    loai: str
    den: str
    nguon: str = "tu_dong"  # "tu_dong" | "so_tay"
    can_cu: str = ""


def chuan_so_hieu(so_hieu: str) -> str:
    """'08/2012/QH13' -> '8/2012/QH13', 'ND' -> 'NĐ' - cùng dạng van_ban_meta sinh ra."""
    so_hieu = (so_hieu or "").strip()
    if so_hieu.startswith("tep:"):
        return so_hieu  # nút phụ lục: tên tệp có thể chứa số hiệu của văn bản khác
    cac_so = van_ban_meta.trich_so_hieu(so_hieu)
    return cac_so[0] if cac_so else so_hieu


def tai_so_tay() -> dict:
    try:
        with open(DUONG_DAN_SO_TAY, encoding="utf-8") as tep:
            du_lieu = json.load(tep)
        return du_lieu if isinstance(du_lieu, dict) else {}
    except (OSError, ValueError):
        return {}


def _viet_ngay(iso: str) -> str:
    nam, thang, ngay = iso.split("-")
    return f"{int(ngay)}/{int(thang)}/{nam}"


class SoQuanHe:
    """Đồ thị quan hệ trên số hiệu, dựng từ hồ sơ văn bản + sổ nhập tay."""

    def __init__(self, ho_so: dict | None = None, tinh_trang: dict | None = None,
                 so_tay: dict | None = None):
        self.ho_so = ho_so or {}
        self.tinh_trang = tinh_trang or {}
        so_tay = tai_so_tay() if so_tay is None else so_tay

        # Nút của đồ thị là số hiệu; tệp không có số hiệu riêng (phụ lục tách
        # tệp) mang nút "tep:<tên>" để vẫn nối được vào văn bản chính.
        self.nut_cua_tep: dict[str, str] = {}
        self.tep_cua_nut: dict[str, list[str]] = {}
        self.thong_tin: dict[str, dict] = {}
        for so_hieu, muc in (so_tay.get("van_ban") or {}).items():
            self.thong_tin[chuan_so_hieu(so_hieu)] = dict(muc or {})

        for ten_file, muc in self.ho_so.items():
            if muc.so_hieu:
                self._gan_tep(ten_file, muc.so_hieu)
            elif muc.kem_theo:
                self._gan_tep(ten_file, f"tep:{ten_file}")
        for so_hieu, muc in self.thong_tin.items():
            for ten_file in muc.get("tep") or []:
                self._gan_tep(ten_file, so_hieu)

        loai_bo = {
            (chuan_so_hieu(q.get("tu", "")), q.get("loai"), chuan_so_hieu(q.get("den", "")))
            for q in so_tay.get("loai_bo") or []
        }
        self.loai_bo = sorted(loai_bo)
        cac_quan_he: dict[tuple, QuanHe] = {}
        for ten_file, muc in self.ho_so.items():
            nut = self.nut_cua_tep.get(ten_file)
            # Dự thảo "sửa đổi Thông tư X" chưa sửa đổi gì cả; tệp không nhận
            # ra số hiệu thì cũng không chắc là văn bản đã ban hành.
            if not nut or self._la_du_thao(ten_file):
                continue
            cac_cap = [("thay_the", s) for s in muc.thay_the]
            cac_cap += [("bai_bo_mot_phan", s) for s in getattr(muc, "bai_bo_mot_phan", [])]
            cac_cap += [("sua_doi", s) for s in muc.sua_doi]
            cac_cap += [("huong_dan", s) for s in getattr(muc, "huong_dan", [])]
            cac_cap += [
                ("huong_dan", s) for ten in getattr(muc, "huong_dan_ten", [])
                for s in [self._tra_ten_luat(ten, muc.ngay_ban_hanh)] if s
            ]
            if getattr(muc, "kem_theo", None):
                cac_cap.append(("kem_theo", muc.kem_theo))
            for loai, den in cac_cap:
                if den != nut and (nut, loai, den) not in loai_bo:
                    cac_quan_he.setdefault((nut, loai, den), QuanHe(nut, loai, den))
        for q in so_tay.get("quan_he") or []:
            tu, den, loai = chuan_so_hieu(q.get("tu", "")), chuan_so_hieu(q.get("den", "")), q.get("loai")
            if tu and den and loai in TEN_QUAN_HE:
                # "nguon" chỉ có khi nạp lại từ CSDL; sổ tay viết tay không ghi.
                nguon = "tu_dong" if q.get("nguon") == "tu_dong" else "so_tay"
                cac_quan_he[(tu, loai, den)] = QuanHe(tu, loai, den, nguon, q.get("can_cu", ""))
        # Vừa thay toàn bộ vừa bãi bỏ một phần (hai câu khác nhau) -> toàn bộ.
        self.quan_he = [
            q for q in cac_quan_he.values()
            if not (q.loai == "bai_bo_mot_phan" and (q.tu, "thay_the", q.den) in cac_quan_he)
        ]
        self.ra: dict[str, list[QuanHe]] = {}
        self.vao: dict[str, list[QuanHe]] = {}
        for q in self.quan_he:
            self.ra.setdefault(q.tu, []).append(q)
            self.vao.setdefault(q.den, []).append(q)

    # ------------------------------------------------------------------
    def _gan_tep(self, ten_file: str, nut: str) -> None:
        cu = self.nut_cua_tep.get(ten_file)
        if cu and ten_file in self.tep_cua_nut.get(cu, []):
            self.tep_cua_nut[cu].remove(ten_file)
        self.nut_cua_tep[ten_file] = nut
        self.tep_cua_nut.setdefault(nut, []).append(ten_file)

    def _la_du_thao(self, ten_file: str) -> bool:
        muc = self.ho_so.get(ten_file)
        thoi_gian = self.tinh_trang.get(ten_file)
        return bool((muc and muc.la_du_thao) or (thoi_gian and thoi_gian.la_du_thao))

    def _tra_ten_luat(self, ten: str, ngay_van_ban: str | None) -> str | None:
        """'Luật Giáo dục' -> số hiệu. Nhiều Luật cùng tên (2005, 2019) thì lấy
        bản mới nhất ban hành TRƯỚC văn bản đang xét: Nghị định năm 2020 hướng
        dẫn Luật Giáo dục 2019, không phải Luật 2005.

        Không có bản nào ban hành trước văn bản đang xét thì trả None: Nghị định
        2001 nhắc "Luật Giáo dục" là Luật 1998 mà sổ tay không có, gán sang Luật
        2019 thì thành "Luật 2019 được hướng dẫn bởi Nghị định 2001"."""
        ten_chuan = " ".join(ten.lower().split())
        nam_van_ban = int(ngay_van_ban[:4]) if ngay_van_ban else 9999
        ung_vien = []
        for so_hieu, muc in self.thong_tin.items():
            if any(" ".join(t.lower().split()) == ten_chuan for t in muc.get("ten_goi") or []):
                ung_vien.append((self._nam(so_hieu), so_hieu))
        truoc = [uv for uv in ung_vien if uv[0] <= nam_van_ban]
        chon = max(truoc, default=None)
        return chon[1] if chon else None

    def _nam(self, nut: str) -> int:
        muc = self.thong_tin.get(nut) or {}
        if muc.get("nam"):
            return int(muc["nam"])
        ngay = muc.get("ngay_ban_hanh") or self._ngay_ban_hanh(nut)
        if ngay:
            return int(ngay[:4])
        khop = re.match(r"\d+/(\d{4})/", nut)
        return int(khop.group(1)) if khop else 0

    def _ngay_ban_hanh(self, nut: str) -> str | None:
        for ten_file in self.tep_cua_nut.get(nut, []):
            muc = self.ho_so.get(ten_file)
            if muc and muc.ngay_ban_hanh:
                return muc.ngay_ban_hanh
        return (self.thong_tin.get(nut) or {}).get("ngay_ban_hanh")

    def ngay_hieu_luc(self, nut: str) -> str | None:
        ngay = (self.thong_tin.get(nut) or {}).get("ngay_hieu_luc")
        if ngay:
            return ngay
        for ten_file in self.tep_cua_nut.get(nut, []):
            thoi_gian = self.tinh_trang.get(ten_file)
            if thoi_gian and thoi_gian.ngay_hieu_luc:
                return thoi_gian.ngay_hieu_luc
        return None

    def _ngay_bat_dau(self, nut: str) -> str | None:
        """Ngày văn bản bắt đầu áp dụng, ước lượng khi thiếu: không đọc được
        ngày hiệu lực thì lấy ngày ban hành, rồi đến năm trong số hiệu. Khi tra
        một mốc quá khứ, văn bản 2026 chưa hề tồn tại năm 2023 dù ta không biết
        chính xác ngày nó có hiệu lực."""
        ngay = self.ngay_hieu_luc(nut) or self._ngay_ban_hanh(nut)
        if not ngay:
            khop = re.match(r"\d+/(\d{4})/", nut)
            ngay = f"{khop.group(1)}-01-01" if khop else None
        return ngay

    def _chua_hieu_luc(self, nut: str, hom_nay: date | None) -> bool:
        ngay = self._ngay_bat_dau(nut)
        return bool(ngay and ngay > (hom_nay or date.today()).isoformat())

    def nhan_nut(self, nut: str) -> str:
        """'Nghị định 279/2026/NĐ-CP' - hoặc tên tệp với nút phụ lục."""
        if nut.startswith("tep:"):
            return nut[4:]
        loai = van_ban_meta.suy_loai_van_ban(nut)
        return f"{loai} {nut}" if loai else nut

    # ------------------------------------------------------------------
    # 1. TÌNH TRẠNG HIỆU LỰC
    # ------------------------------------------------------------------
    def tinh_trang_nut(self, nut: str, hom_nay: date | None = None,
                       _dang_theo_kem_theo: bool = False) -> dict:
        """
        {"code", "thay_boi", "tu_ngay"...} theo quan hệ trong đồ thị.

        Văn bản thay thế CHƯA tới ngày hiệu lực thì văn bản cũ vẫn đang áp
        dụng - nói "đã hết hiệu lực" lúc đó là sai y như không cảnh báo gì.
        """
        # Phụ lục/Quy chế tách tệp chung số phận với văn bản chính của nó.
        chinh = [q.den for q in self.ra.get(nut, []) if q.loai == "kem_theo"]
        if chinh and not _dang_theo_kem_theo:
            return self.tinh_trang_nut(chinh[0], hom_nay, _dang_theo_kem_theo=True)
        vao = self.vao.get(nut, [])
        thay_boi = [q.tu for q in vao if q.loai == "thay_the"]
        if thay_boi:
            da_hieu_luc = [t for t in thay_boi if not self._chua_hieu_luc(t, hom_nay)]
            if da_hieu_luc:
                return {"code": "het_hieu_luc", "boi": da_hieu_luc}
            ngay = min(self._ngay_bat_dau(t) for t in thay_boi)
            return {"code": "sap_het_hieu_luc", "boi": thay_boi, "tu_ngay": ngay}
        if self._chua_hieu_luc(nut, hom_nay):
            return {"code": "chua_hieu_luc", "tu_ngay": self._ngay_bat_dau(nut)}
        bai_bo = [q.tu for q in vao if q.loai == "bai_bo_mot_phan"
                  and not self._chua_hieu_luc(q.tu, hom_nay)]
        if bai_bo:
            return {"code": "het_mot_phan", "boi": bai_bo}
        sua_doi = [q.tu for q in vao if q.loai == "sua_doi"
                   and not self._chua_hieu_luc(q.tu, hom_nay)]
        if sua_doi:
            return {"code": "da_sua_doi", "boi": sua_doi}
        return {"code": "con_hieu_luc"}

    def het_hieu_luc(self, ten_file: str, hom_nay: date | None = None) -> bool:
        nut = self.nut_cua_tep.get(ten_file)
        return bool(nut) and self.tinh_trang_nut(nut, hom_nay)["code"] == "het_hieu_luc"

    def nhan_hieu_luc(self, ten_file: str, noi_dung: str = "",
                      hom_nay: date | None = None) -> dict | None:
        """
        Nhãn ngắn cạnh chip nguồn: {code, label, note, level}; None với tài liệu
        không phải văn bản quy phạm (bài giảng, bảng tính...) - gắn nhãn cho
        chúng chỉ làm nhiễu. Mã giữ nguyên như hieu_luc_bo_sung.nhan_hieu_luc
        (bi_thay_the, bi_sua_doi...) vì gợi ý câu hỏi tiếp theo dựa vào đó.
        """
        import hieu_luc_bo_sung  # nhập muộn: hieu_luc_bo_sung cũng nhập van_ban_meta

        thoi_gian = self.tinh_trang.get(ten_file)
        if thoi_gian is not None and thoi_gian.la_du_thao:
            return {
                "code": "du_thao",
                "label": "Dự thảo",
                "note": "Ô số hiệu và ngày ban hành còn bỏ trống - chưa phải văn bản đã ban hành.",
                "level": "cao",
            }
        nut = self.nut_cua_tep.get(ten_file)
        if not nut:
            return None
        tt = self.tinh_trang_nut(nut, hom_nay)
        ten_boi = ", ".join(self.nhan_nut(t) for t in tt.get("boi", [])[:2])
        if tt["code"] == "het_hieu_luc":
            return {
                "code": "bi_thay_the",
                "label": "Hết hiệu lực",
                "note": f"Đã bị thay thế bởi {ten_boi}.",
                "level": "cao",
            }
        if tt["code"] == "sap_het_hieu_luc":
            return {
                "code": "sap_het_hieu_luc",
                "label": f"Hết hiệu lực {_viet_ngay(tt['tu_ngay'])}",
                "note": f"Còn áp dụng đến trước {_viet_ngay(tt['tu_ngay'])}, sau đó thay bằng {ten_boi}.",
                "level": "vua",
            }
        if tt["code"] == "chua_hieu_luc":
            return {
                "code": "chua_hieu_luc",
                "label": f"Hiệu lực {_viet_ngay(tt['tu_ngay'])}",
                "note": "Đã ban hành nhưng chưa tới ngày thi hành.",
                "level": "vua",
            }
        if hieu_luc_bo_sung.van_ban_sua_doan(noi_dung):
            return {
                "code": "doan_sua_doi",
                "label": "Đoạn đã sửa",
                "note": "Chính đoạn được trích đã bị một văn bản khác sửa đổi hoặc bãi bỏ.",
                "level": "vua",
            }
        if tt["code"] == "het_mot_phan":
            return {
                "code": "het_mot_phan",
                "label": "Hết hiệu lực một phần",
                "note": f"Một số điều, khoản đã bị bãi bỏ bởi {ten_boi}.",
                "level": "vua",
            }
        if tt["code"] == "da_sua_doi":
            return {
                "code": "bi_sua_doi",
                "label": "Đã được sửa đổi",
                "note": f"Còn hiệu lực, đã được sửa đổi, bổ sung bởi {ten_boi}.",
                "level": "vua",
            }
        if nut.startswith("tep:"):
            return None
        ngay = self.ngay_hieu_luc(nut)
        return {
            "code": "con_hieu_luc",
            "label": "Đang hiệu lực",
            "note": f"Có hiệu lực từ {_viet_ngay(ngay)}." if ngay else "Văn bản đã ban hành và đang có hiệu lực.",
            "level": "thap",
        }

    # ------------------------------------------------------------------
    # 2. VĂN BẢN LIÊN QUAN / ĐI KÈM
    # ------------------------------------------------------------------
    def lien_quan(self, ten_file: str, gioi_han: int = 8) -> list[dict]:
        """
        Mọi văn bản có quan hệ với tệp này, kể cả văn bản KHÔNG có trong kho
        (vẫn đáng biết "đã thay thế Thông tư 17/2012"), theo thứ tự ưu tiên.
        Mỗi mục: {quan_he, chieu, mo_ta, so_hieu, nhan, tep, tu_ngay}.

        tu_ngay: ngày quan hệ bắt đầu có tác dụng (ISO), tức ngày hiệu lực của
        văn bản tác động (bên thay thế/sửa đổi/bãi bỏ) - "thay thế Thông tư 33
        từ ngày nào". Chỉ lấy ngày hiệu lực đọc được thật, không đoán từ ngày
        ban hành như _ngay_bat_dau: ghi sai ngày còn tệ hơn để trống.
        None với quan hệ không mang mốc thời gian (hướng dẫn, kèm theo).
        """
        nut = self.nut_cua_tep.get(ten_file)
        if not nut:
            return []
        ket_qua = []
        da_co = set()
        for loai, chieu in UU_TIEN_DI_KEM:
            cac_q = self.vao.get(nut, []) if chieu == "vao" else self.ra.get(nut, [])
            for q in cac_q:
                kia = q.tu if chieu == "vao" else q.den
                # Một văn bản vừa sửa đổi vừa bãi bỏ vài điều của văn bản này
                # chỉ hiện một lần, với quan hệ nặng hơn (đứng trước).
                if q.loai != loai or kia in da_co:
                    continue
                da_co.add(kia)
                ket_qua.append({
                    "quan_he": loai,
                    "chieu": chieu,
                    "mo_ta": TEN_QUAN_HE[loai][1 if chieu == "vao" else 0],
                    "vai_tro": VAI_TRO_DI_KEM[(loai, chieu)],
                    "so_hieu": None if kia.startswith("tep:") else kia,
                    "nhan": self.nhan_nut(kia),
                    "tep": [t for t in self.tep_cua_nut.get(kia, []) if not self._la_du_thao(t)],
                    "tu_ngay": self.ngay_hieu_luc(q.tu) if loai in QUAN_HE_CO_MOC else None,
                })
        # Văn bản thay thế đứng trước: giao diện cắt bớt thì phần quan trọng còn.
        return ket_qua[:gioi_han]

    def di_kem(self, ten_file: str, hom_nay: date | None = None) -> list[dict]:
        """
        Văn bản trong kho phải đọc CÙNG tệp này, theo thứ tự ưu tiên. Bỏ văn
        bản đã hết hiệu lực: kéo văn bản cũ vào chỉ làm câu trả lời lẫn chữ cũ.
        Mỗi mục như lien_quan() nhưng chỉ còn mục có tệp, và "tep" là một tệp.
        """
        ket_qua = []
        for muc in self.lien_quan(ten_file, gioi_han=50):
            for tep in muc["tep"]:
                if tep == ten_file or self.het_hieu_luc(tep, hom_nay):
                    continue
                ket_qua.append({**muc, "tep": tep})
        return ket_qua

    # ------------------------------------------------------------------
    # 3. VĂN BẢN ĐƯỢC NHẮC TRONG CÂU HỎI
    # ------------------------------------------------------------------
    def _cac_nut_da_biet(self) -> set[str]:
        nut = set(self.tep_cua_nut) | set(self.thong_tin)
        for q in self.quan_he:
            nut.update((q.tu, q.den))
        return {n for n in nut if not n.startswith("tep:")}

    def van_ban_trong_cau_hoi(self, cau_hoi: str) -> list[str]:
        """Số hiệu đồ thị biết mà câu hỏi nhắc tới: đủ ("124/2024/NĐ-CP") hoặc
        rút gọn ("nghị định 124/2024") - người hỏi hiếm khi gõ đủ mã cơ quan."""
        da_biet = self._cac_nut_da_biet()
        ket_qua = [s for s in van_ban_meta.trich_so_hieu(cau_hoi or "") if s in da_biet]
        for khop in MAU_SO_NAM.finditer(cau_hoi or ""):
            tien_to = f"{int(khop.group(1))}/{khop.group(2)}/"
            trung = sorted(n for n in da_biet if n.startswith(tien_to))
            # Hai văn bản cùng số cùng năm (Thông tư 12/2020 và Nghị định
            # 12/2020) thì không đoán.
            if len(trung) == 1 and trung[0] not in ket_qua:
                ket_qua.append(trung[0])
        return ket_qua

    def ghi_chu_cau_hoi(self, cau_hoi: str, hom_nay: date | None = None) -> tuple[list[str], list[dict]]:
        """
        (ghi chú hiệu lực cho prompt/giao diện, văn bản thay thế cần kéo vào).
        Chỉ lên tiếng khi văn bản được hỏi KHÔNG còn nguyên hiệu lực - đó là
        lúc người hỏi đang dựa trên thông tin cũ mà không biết.
        """
        ghi_chu, can_keo = [], []
        for nut in self.van_ban_trong_cau_hoi(cau_hoi):
            tt = self.tinh_trang_nut(nut, hom_nay)
            ten_boi = ", ".join(self.nhan_nut(t) for t in tt.get("boi", []))
            if tt["code"] == "het_hieu_luc":
                ghi_chu.append(f"{self.nhan_nut(nut)} đã hết hiệu lực, bị thay thế bởi {ten_boi}.")
            elif tt["code"] == "sap_het_hieu_luc":
                ghi_chu.append(
                    f"{self.nhan_nut(nut)} còn áp dụng đến trước {_viet_ngay(tt['tu_ngay'])}, "
                    f"sau đó thay bằng {ten_boi}."
                )
            elif tt["code"] == "het_mot_phan":
                ghi_chu.append(f"{self.nhan_nut(nut)} đã bị bãi bỏ một phần bởi {ten_boi}.")
            elif tt["code"] == "da_sua_doi":
                ghi_chu.append(f"{self.nhan_nut(nut)} đã được sửa đổi, bổ sung bởi {ten_boi}.")
            else:
                continue
            loai = {"het_hieu_luc": "thay_the", "sap_het_hieu_luc": "thay_the",
                    "het_mot_phan": "bai_bo_mot_phan"}.get(tt["code"], "sua_doi")
            for boi in tt.get("boi", []):
                for tep in self.tep_cua_nut.get(boi, []):
                    if not self._la_du_thao(tep):
                        can_keo.append({
                            "quan_he": loai,
                            "chieu": "vao",
                            "mo_ta": f"{TEN_QUAN_HE[loai][0]} {self.nhan_nut(nut)} (văn bản được hỏi)",
                            "vai_tro": VAI_TRO_DI_KEM[(loai, "vao")],
                            "cua": self.nhan_nut(nut),
                            "so_hieu_goc": nut,
                            "so_hieu": boi,
                            "nhan": self.nhan_nut(boi),
                            "tep": tep,
                        })
        return ghi_chu, can_keo

    # ------------------------------------------------------------------
    # CẢNH BÁO KÈM CÂU TRẢ LỜI
    # ------------------------------------------------------------------
    def canh_bao(self, cac_nguon: list[dict], hom_nay: date | None = None) -> list[dict]:
        """Thay cho van_ban_meta.canh_bao_hieu_luc: cùng dạng dict, thêm hai
        tình trạng mà quan hệ trên tệp không nói được (bãi bỏ một phần, văn
        bản thay thế chưa tới ngày hiệu lực) và biết cả quan hệ ở sổ tay.
        Dự thảo / chưa tới ngày hiệu lực của CHÍNH văn bản do
        hieu_luc_bo_sung.canh_bao lo, ở đây không lặp lại."""
        so_evidence = {}
        for nguon in cac_nguon:
            nut = self.nut_cua_tep.get(nguon.get("name"))
            if nut and nut not in so_evidence:
                so_evidence[nut] = nguon.get("evidence")

        def ten_kem_evidence(cac_nut):
            phan = []
            for t in cac_nut[:2]:
                so = so_evidence.get(t)
                phan.append(f"{self.nhan_nut(t)} (nguồn [{so}])" if so else self.nhan_nut(t))
            con = len(cac_nut) - len(phan)
            return ", ".join(phan) + (f" và {con} văn bản khác" if con > 0 else "")

        ket_qua, da_bao = [], set()
        for nguon in cac_nguon:
            ten_file = nguon.get("name")
            nut = self.nut_cua_tep.get(ten_file)
            if not nut or nut in da_bao or self._la_du_thao(ten_file):
                continue
            tt = self.tinh_trang_nut(nut, hom_nay)
            so = nguon.get("evidence")
            ten = self.nhan_nut(nut)
            if tt["code"] == "het_hieu_luc":
                loai = "thay_the"
                thong_bao = f"Nguồn [{so}] {ten} đã hết hiệu lực: bị thay thế bởi {ten_kem_evidence(tt['boi'])}."
            elif tt["code"] == "sap_het_hieu_luc":
                loai = "sap_thay_the"
                thong_bao = (
                    f"Nguồn [{so}] {ten} chỉ còn áp dụng đến trước {_viet_ngay(tt['tu_ngay'])}, "
                    f"sau đó thay bằng {ten_kem_evidence(tt['boi'])}."
                )
            elif tt["code"] == "het_mot_phan":
                loai = "bai_bo_mot_phan"
                thong_bao = (
                    f"Nguồn [{so}] {ten} đã bị bãi bỏ một phần bởi {ten_kem_evidence(tt['boi'])} "
                    "- đối chiếu xem điều khoản đang trích còn áp dụng không."
                )
            elif tt["code"] == "da_sua_doi":
                loai = "sua_doi"
                thong_bao = (
                    f"Nguồn [{so}] {ten} đã được sửa đổi, bổ sung bởi {ten_kem_evidence(tt['boi'])} "
                    "- nên đối chiếu thêm."
                )
            else:
                continue
            da_bao.add(nut)
            ket_qua.append({
                "evidence": so, "nguon": ten_file, "loai": loai,
                "boi": tt.get("boi", []), "thong_bao": thong_bao,
            })
        return ket_qua

    # ------------------------------------------------------------------
    def ngay_cua_tep(self, ten_file: str) -> str | None:
        """Ngày áp dụng của văn bản chứa tệp này - cho trọng số thời gian."""
        nut = self.nut_cua_tep.get(ten_file)
        if not nut or nut.startswith("tep:"):
            return None
        return self._ngay_bat_dau(nut)

    def xuat(self, hom_nay: date | None = None) -> dict:
        """
        Bảng trạng thái hiệu lực của MỌI văn bản đồ thị biết - kể cả văn bản cũ
        không còn trong kho - cùng các quan hệ, để luu() ghi vào CSDL: văn
        bản 124 mang trạng thái het_hieu_luc và "boi": ["125/..."], văn bản
        125 mang con_hieu_luc; nội dung và vector của cả hai vẫn nằm riêng.
        """
        van_ban = {}
        for nut in sorted(self._cac_nut_da_biet() | {
            n for n in self.tep_cua_nut if n.startswith("tep:")
        } | {n for q in self.quan_he for n in (q.tu, q.den)}):
            tt = self.tinh_trang_nut(nut, hom_nay)
            la_phu_luc = nut.startswith("tep:")
            van_ban[nut] = {
                "nhan": self.nhan_nut(nut),
                "loai_van_ban": None if la_phu_luc else van_ban_meta.suy_loai_van_ban(nut),
                "ngay_ban_hanh": None if la_phu_luc else self._ngay_ban_hanh(nut),
                "tinh_trang": tt["code"],
                "boi": tt.get("boi", []),
                "tu_ngay": tt.get("tu_ngay"),
                "ngay_hieu_luc": self.ngay_hieu_luc(nut),
                "tep": self.tep_cua_nut.get(nut, []),
            }
        return {
            "ngay_tinh": (hom_nay or date.today()).isoformat(),
            "thong_ke": self.thong_ke(),
            "van_ban": van_ban,
            "quan_he": [
                {"tu": q.tu, "loai": q.loai, "den": q.den, "nguon": q.nguon, "can_cu": q.can_cu}
                for q in sorted(self.quan_he, key=lambda q: (q.den, q.loai, q.tu))
            ],
            "loai_quan_he": TEN_QUAN_HE,
            "loai_bo": [{"tu": tu, "loai": loai, "den": den} for tu, loai, den in self.loai_bo],
        }

    def luu(self, duong_dan: str | None = None) -> None:
        """Ghi đè đồ thị vào SQLite (csdl_quan_he.DUONG_DAN_CSDL nếu không chỉ định)."""
        csdl_quan_he.ghi(self.xuat(), duong_dan)

    @classmethod
    def tu_csdl(cls, duong_dan: str | None = None) -> "SoQuanHe":
        """
        Đồ thị đã lưu ở lần dựng gần nhất - dùng khi không dựng lại được từ
        kho (chỉ mục hỏng, chưa nạp xong): biết văn bản nào đã bị thay vẫn hơn
        không biết gì. Chưa từng lưu thì trả đồ thị rỗng.

        Dựng lại qua đường sổ tay: tên gọi Luật lấy từ sổ tay thật, tệp và
        ngày lấy từ CSDL, cạnh giữ nguyên nguồn tu_dong/so_tay.
        """
        du_lieu = csdl_quan_he.doc(duong_dan)
        if not du_lieu:
            return cls(so_tay={})
        thong_tin = {
            chuan_so_hieu(so_hieu): dict(muc or {})
            for so_hieu, muc in (tai_so_tay().get("van_ban") or {}).items()
        }
        for so_hieu, muc in du_lieu["van_ban"].items():
            dich = thong_tin.setdefault(so_hieu, {})
            dich["tep"] = muc["tep"]
            for khoa in ("ngay_ban_hanh", "ngay_hieu_luc"):
                if muc.get(khoa) and not dich.get(khoa):
                    dich[khoa] = muc[khoa]
        return cls(so_tay={
            "van_ban": thong_tin,
            "quan_he": du_lieu["quan_he"],
            "loai_bo": du_lieu["loai_bo"],
        })

    def dau_hieu_luc(self, hom_nay: date | None = None) -> str:
        """
        Mã băm ngắn của trạng thái hiệu lực mọi văn bản và mọi quan hệ, tính
        tại `hom_nay`. Cache câu trả lời lưu nguyên nhãn "Đang hiệu lực / Đã
        được sửa đổi..." của từng nguồn; ghép mã này vào vân tay cache thì đồ
        thị đổi (sửa cách đọc, thêm văn bản thay thế) hay sang ngày văn bản mới
        bắt đầu có hiệu lực, câu trả lời cũ không còn được phát lại với nhãn cũ.
        Tính một lần mỗi ngày.
        """
        ngay = (hom_nay or date.today()).isoformat()
        if getattr(self, "_dau_hieu_luc", (None,))[0] != ngay:
            bang = self.xuat(date.fromisoformat(ngay))
            noi_dung = json.dumps(
                [bang["van_ban"], bang["quan_he"]], ensure_ascii=False, sort_keys=True
            )
            self._dau_hieu_luc = (ngay, hashlib.sha256(noi_dung.encode("utf-8")).hexdigest()[:10])
        return self._dau_hieu_luc[1]

    def thong_ke(self) -> dict:
        dem: dict[str, int] = {}
        for q in self.quan_he:
            dem[q.loai] = dem.get(q.loai, 0) + 1
        hai_dau_trong_kho = [
            q for q in self.quan_he if self.tep_cua_nut.get(q.tu) and self.tep_cua_nut.get(q.den)
        ]
        return {
            "so_van_ban": len([n for n in self.tep_cua_nut if not n.startswith("tep:")]),
            "quan_he": dem,
            "quan_he_ca_hai_trong_kho": len(hai_dau_trong_kho),
            "tu_so_tay": sum(1 for q in self.quan_he if q.nguon == "so_tay"),
        }


# ============================================================
# CHỌN ĐOẠN CỦA VĂN BẢN ĐI KÈM
# ============================================================
def chon_doan_tot_nhat(cac_doan: list, cau_hoi: str, so_hieu_lien_quan: str | None = None):
    """
    Đoạn đáng đưa vào prompt nhất trong một văn bản đi kèm.

    Đếm từ trùng với câu hỏi (cả dạng bỏ dấu), cộng điểm cho đoạn nhắc đúng số
    hiệu văn bản đang được trích: trong một Thông tư sửa đổi, đoạn "sửa đổi
    khoản 2 Điều 5 Thông tư số X" chính là đoạn cần đọc cùng Thông tư X.
    Đối chiếu từ thay vì gọi embedding vì chỉ xét vài chục đoạn của một tệp,
    và bước này nằm trên đường trả lời mọi câu hỏi.
    """
    from hybrid_retrieval import tach_tu_mo_rong

    if not cac_doan:
        return None
    tu_hoi = {t for t in tach_tu_mo_rong(cau_hoi or "") if len(t) > 1}
    tot_nhat, diem_tot_nhat = cac_doan[0], -1.0
    for vi_tri, doan in enumerate(cac_doan):
        tu_doan = set(tach_tu_mo_rong(doan.page_content))
        diem = len(tu_hoi & tu_doan) / (1 + len(tu_hoi) ** 0.5)
        if so_hieu_lien_quan and so_hieu_lien_quan in van_ban_meta.trich_so_hieu(doan.page_content):
            diem += 2.0
        # Hoà điểm thì đoạn đứng trước (trích yếu, phạm vi điều chỉnh) thắng.
        diem -= vi_tri * 1e-4
        if diem > diem_tot_nhat:
            tot_nhat, diem_tot_nhat = doan, diem
    return tot_nhat


def main() -> int:
    """Báo cáo đồ thị quan hệ từ hồ sơ đã lưu (không cần nạp mô hình).
    Thêm --ghi-csdl để ghi luôn đồ thị vào quan_he_van_ban.db."""
    import sys

    import hieu_luc_bo_sung

    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    so = SoQuanHe(van_ban_meta.tai_ho_so(), hieu_luc_bo_sung.tai())
    print(json.dumps(so.thong_ke(), ensure_ascii=False, indent=1))
    print("\nVăn bản trong kho không còn nguyên hiệu lực:")
    for nut, cac_tep in sorted(so.tep_cua_nut.items()):
        tt = so.tinh_trang_nut(nut)
        if tt["code"] != "con_hieu_luc":
            print(f"  {so.nhan_nut(nut)} [{tt['code']}] <- {', '.join(tt.get('boi', []))}  ({cac_tep[0][:50]})")
    if "--ghi-csdl" in sys.argv[1:]:
        so.luu()
        print(f"Đã ghi đồ thị vào {csdl_quan_he.DUONG_DAN_CSDL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
