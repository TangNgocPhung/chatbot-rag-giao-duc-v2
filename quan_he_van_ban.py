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
  4. Văn bản đã bị thay còn áp dụng cho ai theo điều khoản chuyển tiếp?
                                                       -> mo_theo_chuyen_tiep()
  5. Văn bản hướng dẫn có thể đã hết hiệu lực theo văn bản nó hướng dẫn?
                                                       -> het_theo_goc()

CẬP NHẬT KHI CÓ VĂN BẢN MỚI: không huấn luyện lại gì cả. Văn bản mới vào kho
-> lượt nạp đêm lập chỉ mục -> dịch vụ khởi động lại dựng lại hồ sơ và đồ thị
này từ nội dung -> văn bản cũ tự đổi nhãn "Hết hiệu lực" và câu trả lời tự
chuyển sang văn bản mới. Sổ tay chỉ dùng khi máy đọc sót (ảnh quét hỏng) hoặc
đọc sai (ghi vào "loai_bo").

Chạy trực tiếp để xem báo cáo:  python quan_he_van_ban.py
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta

import chuyen_tiep
import thu_bac
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
DUONG_DAN_XUAT = os.path.abspath(os.getenv(
    "RAG_QUAN_HE_XUAT", os.path.join(THU_MUC_DU_AN, "quan_he_van_ban.json")
))


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


# "Thông tư này", "Nghị định này"... trong điều kiện chuyển tiếp, để thay bằng
# tên văn bản mới khi câu được hiện cạnh văn bản cũ.
MAU_LOAI_NAY = re.compile(
    r"\b(?:Thông tư liên tịch|Thông tư|Nghị định|Luật|Quyết định|Nghị quyết|Quy chế)\s+này\b",
    re.IGNORECASE,
)


def _chu_thuong_dau(chuoi: str) -> str:
    """Viết thường chữ đầu để ghép vào giữa câu ("Riêng các khóa ...")."""
    return chuoi[:1].lower() + chuoi[1:] if chuoi else chuoi


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
        cac_quan_he: dict[tuple, QuanHe] = {}
        # Quan hệ máy trích ra mà trái thứ bậc: công văn "sửa đổi" Thông tư,
        # Thông tư "thay thế" Nghị định, Nghị định "hướng dẫn" Thông tư. Pháp
        # luật không cho phép những chiều này, nên đó là câu trích nhầm (thường
        # là câu kể lại văn bản khác). Giữ danh sách để còn rà, không đưa vào đồ thị.
        self.quan_he_trai_thu_bac: list[QuanHe] = []
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
                if den == nut or (nut, loai, den) in loai_bo:
                    continue
                if (loai in QUAN_HE_CO_MOC and thu_bac.thap_hon(nut, den)) or (
                    loai == "huong_dan" and thu_bac.thap_hon(den, nut)
                ):
                    self.quan_he_trai_thu_bac.append(QuanHe(nut, loai, den))
                    continue
                cac_quan_he.setdefault((nut, loai, den), QuanHe(nut, loai, den))
        for q in so_tay.get("quan_he") or []:
            tu, den, loai = chuan_so_hieu(q.get("tu", "")), chuan_so_hieu(q.get("den", "")), q.get("loai")
            if tu and den and loai in TEN_QUAN_HE:
                cac_quan_he[(tu, loai, den)] = QuanHe(tu, loai, den, "so_tay", q.get("can_cu", ""))
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

        # Điều khoản chuyển tiếp: văn bản mới giữ văn bản cũ còn áp dụng cho
        # một nhóm đối tượng. Không thành cạnh trong self.quan_he vì nó không
        # đổi tình trạng chung của văn bản cũ (vẫn hết hiệu lực), chỉ mở một
        # ngoại lệ - phải dựng SAU self.ra để hiểu được "quy định cũ" là gì.
        self.chuyen_tiep: dict[str, list[dict]] = {}  # nút mới -> quy định của nó
        self.giu_lai: dict[str, list[dict]] = {}      # nút cũ -> quy định giữ nó lại
        loai_bo_chuyen_tiep = {(tu, den) for tu, loai, den in loai_bo if loai == "chuyen_tiep"}
        for ten_file, thoi_gian in self.tinh_trang.items():
            nut = self.nut_cua_tep.get(ten_file)
            if not nut or nut.startswith("tep:") or self._la_du_thao(ten_file):
                continue
            for quy_dinh in getattr(thoi_gian, "chuyen_tiep", None) or []:
                self._them_chuyen_tiep(nut, quy_dinh, "tu_dong", loai_bo_chuyen_tiep)
        for quy_dinh in so_tay.get("chuyen_tiep") or []:
            nut = chuan_so_hieu(quy_dinh.get("van_ban", ""))
            if nut:
                self._them_chuyen_tiep(nut, quy_dinh, "so_tay", set())

        # Văn bản mới cho văn bản quy định chi tiết của văn bản cũ tiếp tục áp
        # dụng: {nút văn bản mới: câu nguyên văn}. Sổ tay ghi được bằng
        # van_ban.<số hiệu>.giu_van_ban_huong_dan khi máy không đọc ra.
        self.giu_huong_dan: dict[str, str] = {}
        for ten_file, thoi_gian in self.tinh_trang.items():
            nut = self.nut_cua_tep.get(ten_file)
            cau = getattr(thoi_gian, "giu_van_ban_huong_dan", None)
            if nut and cau and not self._la_du_thao(ten_file):
                self.giu_huong_dan.setdefault(nut, cau)
        for nut, muc in self.thong_tin.items():
            if muc.get("giu_van_ban_huong_dan"):
                self.giu_huong_dan[nut] = muc["giu_van_ban_huong_dan"]

    # ------------------------------------------------------------------
    def _them_chuyen_tiep(self, nut: str, quy_dinh: dict, nguon: str, loai_bo: set) -> None:
        """Nối một câu chuyển tiếp của văn bản `nut` vào văn bản cũ nó giữ lại.

        Câu nêu số hiệu thì theo đúng số hiệu đó. Câu chỉ nói "quy định cũ"
        (hay không nói theo gì) thì là các văn bản mà `nut` đã thay hoặc bãi bỏ
        một phần - biết được nhờ đồ thị, kể cả quan hệ ở sổ tay.
        """
        cu = [chuan_so_hieu(s) for s in quy_dinh.get("ap_dung_theo") or []]
        if not cu and quy_dinh.get("theo_quy_dinh_cu"):
            cu = [q.den for q in self.ra.get(nut, []) if q.loai in ("thay_the", "bai_bo_mot_phan")]
        cu = [c for c in dict.fromkeys(cu) if c and c != nut and (nut, c) not in loai_bo]
        moc = quy_dinh.get("moc")
        if not moc and quy_dinh.get("moc_la_ngay_hieu_luc"):
            # Ngày hiệu lực đọc được; không có thì ước theo ngày ban hành/năm
            # trong số hiệu - mốc chỉ dùng để so theo năm.
            moc = self._ngay_bat_dau(nut)
        muc = {
            "van_ban": nut,
            "cu": cu,
            "dieu_kien": quy_dinh.get("dieu_kien") or "",
            "trich": quy_dinh.get("trich") or quy_dinh.get("dieu_kien") or "",
            "doi_tuong": quy_dinh.get("doi_tuong") or "khac",
            "moc": moc,
            "nguon": nguon,
            "can_cu": quy_dinh.get("can_cu", ""),
        }
        if any(m["cu"] == cu and m["trich"] == muc["trich"] for m in self.chuyen_tiep.get(nut, [])):
            return
        self.chuyen_tiep.setdefault(nut, []).append(muc)
        for c in cu:
            self.giu_lai.setdefault(c, []).append(muc)

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
        dẫn Luật Giáo dục 2019, không phải Luật 2005."""
        ten_chuan = " ".join(ten.lower().split())
        nam_van_ban = int(ngay_van_ban[:4]) if ngay_van_ban else 9999
        ung_vien = []
        for so_hieu, muc in self.thong_tin.items():
            if any(" ".join(t.lower().split()) == ten_chuan for t in muc.get("ten_goi") or []):
                ung_vien.append((self._nam(so_hieu), so_hieu))
        truoc = [uv for uv in ung_vien if uv[0] <= nam_van_ban]
        chon = max(truoc or ung_vien, default=None)
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

    def mo_ta_thu_bac(self, ten_file: str) -> str | None:
        """Dòng "Loại:" cho prompt (xem thu_bac.mo_ta); phụ lục theo văn bản chính."""
        nut = self._nut_chinh(ten_file)
        if not nut or nut.startswith("tep:"):
            return None
        return thu_bac.mo_ta(van_ban_meta.suy_loai_van_ban(nut), nut)

    def cap_cua_tep(self, ten_file: str) -> int | None:
        muc = thu_bac.thu_bac(self._nut_chinh(ten_file))
        return muc.cap if muc else None

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
                tt = {"code": "het_hieu_luc", "boi": da_hieu_luc}
                giu = [
                    m for m in self.giu_lai.get(nut, [])
                    if not self._chua_hieu_luc(m["van_ban"], hom_nay)
                ]
                if giu:
                    tt["chuyen_tiep"] = giu
                return tt
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
        if tt["code"] == "het_hieu_luc" and tt.get("chuyen_tiep"):
            # Giữ mã bi_thay_the (gợi ý câu hỏi tiếp theo dựa vào nó); mức
            # "vua" vì với đúng nhóm đối tượng này văn bản vẫn là căn cứ.
            return {
                "code": "bi_thay_the",
                "chuyen_tiep": True,
                "label": "Hết hiệu lực · còn áp dụng chuyển tiếp",
                "note": (
                    f"Đã bị thay thế bởi {ten_boi}; vẫn áp dụng cho: "
                    f"{self.dieu_kien_viet(tt['chuyen_tiep'][0])}."
                ),
                "level": "vua",
            }
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
        het_goc = self.het_theo_goc(nut, hom_nay) if tt["code"] in (
            "con_hieu_luc", "da_sua_doi", "het_mot_phan"
        ) else None
        if het_goc:
            return {
                "code": "het_theo_goc",
                "label": "Sắp cần kiểm tra hiệu lực" if het_goc["sap"] else "Cần kiểm tra hiệu lực",
                "note": (
                    f"Văn bản này {self.mo_ta_het_theo_goc(het_goc)}. Văn bản quy định chi tiết "
                    "thường hết hiệu lực cùng văn bản được hướng dẫn, trừ khi văn bản mới cho giữ lại."
                ),
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
                ghi_chu.append(
                    f"{self.nhan_nut(nut)} đã hết hiệu lực, bị thay thế bởi {ten_boi}."
                    + (
                        f" Riêng {_chu_thuong_dau(self.dieu_kien_viet(tt['chuyen_tiep'][0]))}"
                        " vẫn áp dụng văn bản này (quy định chuyển tiếp)."
                        if tt.get("chuyen_tiep") else ""
                    )
                )
            elif tt["code"] == "sap_het_hieu_luc":
                ghi_chu.append(
                    f"{self.nhan_nut(nut)} còn áp dụng đến trước {_viet_ngay(tt['tu_ngay'])}, "
                    f"sau đó thay bằng {ten_boi}."
                )
            elif tt["code"] != "chua_hieu_luc" and (het_goc := self.het_theo_goc(nut, hom_nay)):
                # Không kéo văn bản nào vào: chưa có văn bản thay chính nó.
                ghi_chu.append(
                    f"{self.nhan_nut(nut)} {self.mo_ta_het_theo_goc(het_goc)} - cần kiểm tra "
                    "văn bản này còn được áp dụng không."
                )
                continue
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
            if tt["code"] == "het_hieu_luc" and tt.get("chuyen_tiep"):
                loai = "chuyen_tiep"
                quy_dinh = tt["chuyen_tiep"][0]
                thong_bao = (
                    f"Nguồn [{so}] {ten} đã bị thay thế bởi {ten_kem_evidence(tt['boi'])}, "
                    f"nhưng vẫn áp dụng cho {_chu_thuong_dau(self.dieu_kien_viet(quy_dinh))} "
                    f"theo quy định chuyển tiếp của {self.nhan_nut(quy_dinh['van_ban'])}."
                )
            elif tt["code"] == "het_hieu_luc":
                loai = "thay_the"
                thong_bao = f"Nguồn [{so}] {ten} đã hết hiệu lực: bị thay thế bởi {ten_kem_evidence(tt['boi'])}."
            elif tt["code"] == "sap_het_hieu_luc":
                loai = "sap_thay_the"
                thong_bao = (
                    f"Nguồn [{so}] {ten} chỉ còn áp dụng đến trước {_viet_ngay(tt['tu_ngay'])}, "
                    f"sau đó thay bằng {ten_kem_evidence(tt['boi'])}."
                )
            elif tt["code"] != "chua_hieu_luc" and (het_goc := self.het_theo_goc(nut, hom_nay)):
                loai = "het_theo_goc"
                thong_bao = (
                    f"Nguồn [{so}] {ten} {self.mo_ta_het_theo_goc(het_goc)}. Văn bản quy định "
                    "chi tiết thường hết hiệu lực cùng văn bản được hướng dẫn - cần kiểm tra "
                    "văn bản này còn được áp dụng không."
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
    # 4. ĐIỀU KHOẢN CHUYỂN TIẾP
    # ------------------------------------------------------------------
    def dieu_kien_viet(self, quy_dinh: dict) -> str:
        """Điều kiện chuyển tiếp đọc được khi đứng cạnh văn bản CŨ: "trước
        ngày Thông tư này có hiệu lực" -> "trước ngày Thông tư 8/2021/TT-BGDĐT
        có hiệu lực" (đặt cạnh văn bản cũ thì "này" chỉ nhầm sang nó)."""
        ten_moi = self.nhan_nut(quy_dinh["van_ban"])
        # Kèm ngày khi mốc chính là ngày hiệu lực ĐỌC ĐƯỢC của văn bản mới -
        # người hỏi cần ngày đó để tự đối chiếu khóa của mình. Mốc ước theo
        # ngày ban hành thì không ghi: ghi sai ngày còn tệ hơn để trống.
        moc = quy_dinh.get("moc")
        if moc and moc == self.ngay_hieu_luc(quy_dinh["van_ban"]):
            ten_moi += f" ({_viet_ngay(moc)})"
        return MAU_LOAI_NAY.sub(lambda _: ten_moi, quy_dinh.get("dieu_kien") or "", count=1)

    def _nut_chinh(self, ten_file: str) -> str | None:
        """Nút của tệp; phụ lục tách tệp thì theo văn bản chính của nó."""
        nut = self.nut_cua_tep.get(ten_file)
        chinh = [q.den for q in self.ra.get(nut, []) if q.loai == "kem_theo"] if nut else []
        return chinh[0] if chinh else nut

    def _con_duoc_giu(self, nut_cu: str, hom_nay: date | None = None) -> bool:
        """Văn bản cũ thật sự không còn nguyên hiệu lực - chỉ khi đó câu
        "tiếp tục thực hiện theo X" mới là chuyển tiếp. X còn hiệu lực thì đó
        là câu viện dẫn thường bị trích nhầm, báo "văn bản cũ" là sai."""
        return self.tinh_trang_nut(nut_cu, hom_nay)["code"] in ("het_hieu_luc", "het_mot_phan")

    def mo_theo_chuyen_tiep(self, cau_hoi: str) -> dict[str, dict]:
        """
        {nút văn bản cũ: quy định chuyển tiếp} mà câu hỏi thuộc đúng đối tượng.

        Câu hỏi phải tự nói người hỏi thuộc khóa/đợt nào ("khóa tuyển sinh
        2019", "đã nhập học", "khóa cũ"). Không nói gì thì coi là hỏi quy định
        hiện hành - mở văn bản cũ cho mọi câu hỏi chỉ làm lẫn chữ cũ vào câu
        trả lời của đa số người hỏi.
        """
        dau_hieu = chuyen_tiep.dau_hieu_trong_cau_hoi(cau_hoi)
        if not dau_hieu.co:
            return {}
        mo: dict[str, dict] = {}
        for cu, cac_quy_dinh in self.giu_lai.items():
            if not self._con_duoc_giu(cu):
                continue
            for quy_dinh in cac_quy_dinh:
                # Dấu hiệu trong câu hỏi là về khóa học/hồ sơ; câu chuyển tiếp
                # về đối tượng khác (cơ sở được cấp phép...) không so được.
                if quy_dinh["doi_tuong"] == "khac":
                    continue
                if chuyen_tiep.so_voi_moc(quy_dinh["moc"], dau_hieu.nam) != "khong":
                    mo.setdefault(cu, quy_dinh)
        return mo

    def mo_cho_tep(self, ten_file: str, mo: dict[str, dict]) -> bool:
        return bool(mo) and self._nut_chinh(ten_file) in mo

    def di_kem_chuyen_tiep(self, ten_file: str, mo: dict[str, dict]) -> list[dict]:
        """Tệp văn bản cũ phải đọc cùng `ten_file` (văn bản mới có điều khoản
        chuyển tiếp) khi câu hỏi thuộc diện chuyển tiếp - cùng dạng di_kem()."""
        nut = self.nut_cua_tep.get(ten_file)
        ket_qua = []
        for quy_dinh in self.chuyen_tiep.get(nut, []) if nut and mo else []:
            for cu in quy_dinh["cu"]:
                if mo.get(cu) is not quy_dinh:
                    continue
                for tep in self.tep_cua_nut.get(cu, []):
                    if tep != ten_file and not self._la_du_thao(tep):
                        ket_qua.append({
                            "quan_he": "chuyen_tiep",
                            "chieu": "ra",
                            "mo_ta": "Còn áp dụng chuyển tiếp",
                            "vai_tro": "Văn bản cũ còn áp dụng chuyển tiếp",
                            "so_hieu": cu,
                            "nhan": self.nhan_nut(cu),
                            "tep": tep,
                        })
        return ket_qua

    def _chuyen_tiep_cua_nguon(self, cac_nguon: list[dict], cau_hoi: str,
                               hom_nay: date | None) -> list[tuple[dict, dict]]:
        """(nguồn, quy định) cho mọi câu chuyển tiếp dính tới các nguồn đang trích.

        Phía văn bản MỚI: chỉ báo khi câu chuyển tiếp còn có thể áp dụng cho
        người hỏi - câu hỏi nêu khóa thì so với mốc; không nêu thì bỏ những
        mốc đã quá RAG_CHUYEN_TIEP_SO_NAM năm (khóa tuyển sinh từ 2007 nay đã
        ra trường cả; nhắc lại chỉ làm dài câu trả lời).
        Phía văn bản CŨ: nó có mặt trong nguồn nghĩa là đã được mở (hỏi đúng
        khóa, hoặc hỏi quy định trước đây), nên luôn báo.
        """
        dau_hieu = chuyen_tiep.dau_hieu_trong_cau_hoi(cau_hoi)
        nam_nay = (hom_nay or date.today()).year
        so_nam = int(os.getenv("RAG_CHUYEN_TIEP_SO_NAM", "6"))
        ket_qua, da_co = [], set()
        for nguon in cac_nguon:
            nut = self._nut_chinh(nguon.get("name"))
            if not nut:
                continue
            cac_quy_dinh = [(m, "moi") for m in self.chuyen_tiep.get(nut, [])]
            if self.tinh_trang_nut(nut, hom_nay).get("chuyen_tiep"):
                cac_quy_dinh += [(m, "cu") for m in self.giu_lai.get(nut, [])]
            for quy_dinh, phia in cac_quy_dinh:
                if id(quy_dinh) in da_co or not any(
                    self._con_duoc_giu(c, hom_nay) for c in quy_dinh["cu"]
                ):
                    continue
                if phia == "moi":
                    if dau_hieu.co and quy_dinh["doi_tuong"] != "khac":
                        if chuyen_tiep.so_voi_moc(quy_dinh["moc"], dau_hieu.nam) == "khong":
                            continue
                    elif quy_dinh["moc"] and int(quy_dinh["moc"][:4]) < nam_nay - so_nam:
                        continue
                da_co.add(id(quy_dinh))
                ket_qua.append((nguon, quy_dinh))
        return ket_qua

    def canh_bao_chuyen_tiep(self, cac_nguon: list[dict], cau_hoi: str = "",
                             hom_nay: date | None = None) -> list[dict]:
        """Cảnh báo cho giao diện, cùng dạng canh_bao(): nguồn là văn bản mới
        có điều khoản chuyển tiếp. Phía văn bản cũ đã có canh_bao() báo."""
        noi_cau_hoi = chuyen_tiep.dau_hieu_trong_cau_hoi(cau_hoi).co
        nut_nguon = {self._nut_chinh(n.get("name")) for n in cac_nguon}
        ket_qua = []
        for nguon, quy_dinh in self._chuyen_tiep_cua_nguon(cac_nguon, cau_hoi, hom_nay):
            # Văn bản cũ cũng đang là nguồn thì canh_bao() đã báo kèm nó.
            if self._nut_chinh(nguon.get("name")) != quy_dinh["van_ban"] or any(
                c in nut_nguon for c in quy_dinh["cu"]
            ):
                continue
            ten_cu = ", ".join(self.nhan_nut(c) for c in quy_dinh["cu"][:2])
            thong_bao = (
                f"Nguồn [{nguon.get('evidence')}] {self.nhan_nut(quy_dinh['van_ban'])} có quy định "
                f"chuyển tiếp: {_chu_thuong_dau(self.dieu_kien_viet(quy_dinh))} vẫn áp dụng {ten_cu}."
            )
            if not any(self.tep_cua_nut.get(c) for c in quy_dinh["cu"]):
                # Nói thẳng để người đọc không tưởng câu trả lời đã đối chiếu văn bản cũ.
                thong_bao += " Văn bản cũ này không có trong kho."
            elif not noi_cau_hoi:
                thong_bao += " Nếu bạn thuộc diện này, hãy hỏi kèm khóa/năm nhập học để được trả lời theo văn bản cũ."
            ket_qua.append({
                "evidence": nguon.get("evidence"),
                "nguon": nguon.get("name"),
                "loai": "chuyen_tiep",
                "boi": [quy_dinh["van_ban"]],
                "thong_bao": thong_bao,
            })
        return ket_qua

    def ghi_chu_chuyen_tiep(self, cac_nguon: list[dict], cau_hoi: str = "",
                            hom_nay: date | None = None) -> list[str]:
        """Nguyên văn các câu chuyển tiếp liên quan, để đưa vào prompt: mô hình
        cần đúng chữ của điều khoản để trả lời có điều kiện, không phải tóm tắt."""
        return [
            f"{self.nhan_nut(quy_dinh['van_ban'])} quy định: \"{quy_dinh['trich']}\" "
            f"(văn bản cũ: {', '.join(self.nhan_nut(c) for c in quy_dinh['cu'][:3])})."
            for _, quy_dinh in self._chuyen_tiep_cua_nguon(cac_nguon, cau_hoi, hom_nay)
        ]

    # ------------------------------------------------------------------
    # 5. HẾT HIỆU LỰC DÂY CHUYỀN THEO VĂN BẢN ĐƯỢC HƯỚNG DẪN
    # ------------------------------------------------------------------
    def het_theo_goc(self, nut: str, hom_nay: date | None = None,
                     _dang_xet: frozenset = frozenset()) -> dict | None:
        """
        Văn bản `nut` quy định chi tiết/hướng dẫn một văn bản đã (hoặc sắp) hết
        hiệu lực - trực tiếp, hay qua chuỗi Luật -> Nghị định -> Thông tư.

        Luật Ban hành VBQPPL 2015 (Điều 154 khoản 3) quy định văn bản quy định
        chi tiết hết hiệu lực đồng thời với văn bản (hoặc điều, khoản) được quy
        định chi tiết. Nhưng quy tắc có ngoại lệ, luật mới hay cho giữ lại văn
        bản hướng dẫn cũ, và cạnh "hướng dẫn" trích bằng máy có thể chỉ đúng
        một phần - nên kết quả chỉ dùng để CẢNH BÁO "cần kiểm tra", không
        bao giờ để lọc văn bản khỏi truy hồi như het_hieu_luc().

        Không cảnh báo khi:
          - văn bản thay thế văn bản gốc có câu giữ lại văn bản quy định chi
            tiết (self.giu_huong_dan);
          - chính `nut` còn được sửa đổi/bãi bỏ một phần SAU ngày văn bản gốc
            hết hiệu lực - không ai sửa một văn bản đã chết;
          - `nut` ban hành sau ngày đó (cạnh hướng dẫn gần như chắc là trích nhầm);
          - sổ tay ghi van_ban.<số hiệu>.giu_hieu_luc.

        Trả về {"goc", "thay_goc", "tu_ngay", "sap", "chuoi"} hoặc None.
        "chuoi": các văn bản từ cấp trên trực tiếp tới văn bản đã hết hiệu lực.
        """
        if not nut or nut in _dang_xet or len(_dang_xet) > 4:
            return None
        chinh = [q.den for q in self.ra.get(nut, []) if q.loai == "kem_theo"]
        if chinh:
            return self.het_theo_goc(chinh[0], hom_nay, _dang_xet | {nut})
        if (self.thong_tin.get(nut) or {}).get("giu_hieu_luc"):
            return None
        dang_xet = _dang_xet | {nut}
        for q in self.ra.get(nut, []):
            if q.loai != "huong_dan":
                continue
            tt = self.tinh_trang_nut(q.den, hom_nay)
            if tt["code"] in ("het_hieu_luc", "sap_het_hieu_luc"):
                if any(t in self.giu_huong_dan for t in tt["boi"]):
                    continue
                ngay = [n for n in (self._ngay_bat_dau(t) for t in tt["boi"]) if n]
                ket_qua = {
                    "goc": q.den,
                    "thay_goc": tt["boi"],
                    "tu_ngay": min(ngay) if ngay else None,
                    "sap": tt["code"] == "sap_het_hieu_luc",
                    "chuoi": [q.den],
                }
            else:
                tren = self.het_theo_goc(q.den, hom_nay, dang_xet)
                if not tren:
                    continue
                ket_qua = {**tren, "chuoi": [q.den] + tren["chuoi"]}
            if self._con_song_sau(nut, ket_qua["tu_ngay"]):
                continue
            return ket_qua
        return None

    def _con_song_sau(self, nut: str, tu_ngay: str | None) -> bool:
        """Dấu hiệu `nut` vẫn được áp dụng sau ngày `tu_ngay`: ban hành sau
        ngày đó, hoặc bị sửa đổi/bãi bỏ một phần bởi văn bản có hiệu lực từ
        ngày đó trở đi."""
        if not tu_ngay:
            return False
        ngay_nut = self._ngay_ban_hanh(nut) or self.ngay_hieu_luc(nut)
        if ngay_nut and ngay_nut >= tu_ngay:
            return True
        return any(
            q.loai in ("sua_doi", "bai_bo_mot_phan") and (self._ngay_bat_dau(q.tu) or "") >= tu_ngay
            for q in self.vao.get(nut, [])
        )

    def mo_ta_het_theo_goc(self, ket_qua: dict) -> str:
        """"hướng dẫn Luật 8/2012/QH13, đã bị thay bởi Luật 125/2025/QH15 từ
        1/1/2026" - kèm cả chuỗi khi đi qua văn bản trung gian."""
        chuoi = ket_qua["chuoi"]
        dau = f"hướng dẫn {self.nhan_nut(chuoi[0])}"
        if len(chuoi) > 1:
            dau += f" (văn bản này lại hướng dẫn {' → '.join(self.nhan_nut(n) for n in chuoi[1:])})"
        thay = ", ".join(self.nhan_nut(t) for t in ket_qua["thay_goc"][:2])
        ngay = f" từ {_viet_ngay(ket_qua['tu_ngay'])}" if ket_qua.get("tu_ngay") else ""
        dong_tu = "sẽ bị thay" if ket_qua.get("sap") else "đã bị thay"
        return f"{dau}; {self.nhan_nut(ket_qua['goc'])} {dong_tu} bởi {thay}{ngay}"

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
        không còn trong kho - cùng các quan hệ. Ghi ra quan_he_van_ban.json mỗi
        lần dựng lại, để xem/đối chiếu như một bảng trong cơ sở dữ liệu: văn
        bản 124 mang trạng thái het_hieu_luc và "boi": ["125/..."], văn bản
        125 mang con_hieu_luc; nội dung và vector của cả hai vẫn nằm riêng.
        """
        van_ban = {}
        for nut in sorted(self._cac_nut_da_biet() | {
            n for n in self.tep_cua_nut if n.startswith("tep:")
        }):
            tt = self.tinh_trang_nut(nut, hom_nay)
            van_ban[nut] = {
                "nhan": self.nhan_nut(nut),
                "tinh_trang": tt["code"],
                "boi": tt.get("boi", []),
                "tu_ngay": tt.get("tu_ngay"),
                "ngay_hieu_luc": self.ngay_hieu_luc(nut),
                "tep": self.tep_cua_nut.get(nut, []),
                "thu_bac": (thu_bac.thu_bac(nut).cap if thu_bac.thu_bac(nut) else None),
                # Chỉ là nghi vấn cần đối chiếu, không đổi "tinh_trang".
                "het_theo_goc": self.het_theo_goc(nut, hom_nay)
                if tt["code"] in ("con_hieu_luc", "da_sua_doi", "het_mot_phan") else None,
            }
        return {
            "ngay_tinh": (hom_nay or date.today()).isoformat(),
            "thong_ke": self.thong_ke(),
            "van_ban": van_ban,
            "quan_he": [
                {"tu": q.tu, "loai": q.loai, "den": q.den, "nguon": q.nguon, "can_cu": q.can_cu}
                for q in sorted(self.quan_he, key=lambda q: (q.den, q.loai, q.tu))
            ],
            "chuyen_tiep": [
                quy_dinh for nut in sorted(self.chuyen_tiep) for quy_dinh in self.chuyen_tiep[nut]
            ],
            "quan_he_trai_thu_bac": [
                {"tu": q.tu, "loai": q.loai, "den": q.den} for q in self.quan_he_trai_thu_bac
            ],
        }

    def luu(self, duong_dan: str = DUONG_DAN_XUAT) -> None:
        with open(duong_dan, "w", encoding="utf-8") as tep:
            json.dump(self.xuat(), tep, ensure_ascii=False, indent=1)

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
            "chuyen_tiep": sum(len(v) for v in self.chuyen_tiep.values()),
            "van_ban_con_ap_dung_chuyen_tiep": len(self.giu_lai),
            "quan_he_trai_thu_bac_da_loai": len(self.quan_he_trai_thu_bac),
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
    """Báo cáo đồ thị quan hệ từ hồ sơ đã lưu (không cần nạp mô hình)."""
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
    print("\nĐiều khoản chuyển tiếp (văn bản mới -> văn bản cũ còn áp dụng):")
    for nut in sorted(so.chuyen_tiep):
        for quy_dinh in so.chuyen_tiep[nut]:
            cu = ", ".join(quy_dinh["cu"]) or "(chưa xác định văn bản cũ)"
            print(f"  {so.nhan_nut(nut)} -> {cu} [{quy_dinh['doi_tuong']}, mốc {quy_dinh['moc'] or '?'}]")
            print(f"      \"{quy_dinh['trich'][:160]}\"")
    print("\nQuan hệ máy trích bị loại vì trái thứ bậc (văn bản cấp dưới không thay/sửa được cấp trên):")
    for q in so.quan_he_trai_thu_bac:
        print(f"  {so.nhan_nut(q.tu)} --{q.loai}--> {so.nhan_nut(q.den)}")
    print("\nCó thể hết hiệu lực theo văn bản được hướng dẫn (cần đối chiếu):")
    for nut in sorted(n for n in so.tep_cua_nut if not n.startswith("tep:")):
        if so.tinh_trang_nut(nut)["code"] in ("con_hieu_luc", "da_sua_doi", "het_mot_phan"):
            if het_goc := so.het_theo_goc(nut):
                print(f"  {so.nhan_nut(nut)}: {so.mo_ta_het_theo_goc(het_goc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
