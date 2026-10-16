"""Cách ly nguồn chưa xác nhận, bản trùng và phạm vi mâu thuẫn khỏi truy hồi."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
import hashlib
import re

import hieu_luc_bo_sung as hl
import phan_loai_giao_duc as pl
import van_ban_meta as vm

PHIEN_BAN = "nguon-v1"


def trang_thai_phan_dau(ten: str, noi_dung: str) -> tuple[str, list[str]]:
    header = vm.cat_khoi_tieu_de(noi_dung[:hl.DO_DAI_PHAN_DAU])
    dau = hl.nen(header)
    # Sách/bài giảng có thể dẫn thông tư và chứa mẫu "ngày tháng năm".
    # Chỉ áp quy tắc ô trống khi có cấu trúc tiêu đề văn bản hành chính.
    if not hl.co_tieu_de_hanh_chinh(header):
        return "su_dung", []
    if not hl.MAU_DANG_VAN_BAN.search(dau):
        return "su_dung", []
    if hl.MAU_DU_THAO.search(dau):
        return "du_thao", ["Có dấu dự thảo trong tiêu đề"]
    # Giữ tương thích bản ký số có số bị OCR hỏng; tên tệp không vượt được
    # dấu DỰ THẢO rõ ràng ở trên.
    if "signed" in ten.casefold():
        return "su_dung", []
    so_trong = bool(hl.MAU_O_SO_HIEU_TRONG.search(dau))
    ngay_trong = bool(hl.MAU_O_NGAY_TRONG.search(dau))
    if so_trong and ngay_trong:
        return "du_thao", ["Ô số hiệu và ngày ban hành đều để trống"]
    if so_trong or ngay_trong:
        return "can_xac_minh", ["Thông tin định danh trong nội dung chưa đầy đủ; không lấy tên tệp để xác nhận"]
    return "su_dung", []


def xay_dung(doan_theo_tep: dict) -> dict:
    bang = {}
    nhom_hash = {}
    for ten, docs in doan_theo_tep.items():
        if not ten:
            continue
        # Khử chunk trùng trong cùng nguồn trước khi so bản sao giữa hai tệp.
        chunks = sorted({" ".join(d.page_content.split()) for d in docs})
        digest = hashlib.sha256("\n".join(chunks).encode("utf-8")).hexdigest()
        text = "\n".join(d.page_content for d in docs)
        trang_thai, ly_do = trang_thai_phan_dau(ten, text)
        bang[ten] = {"trang_thai": trang_thai, "ly_do": ly_do, "sha256_noi_dung": digest,
                     "so_doan": len(docs), "so_ky_tu": len(text), "ban_chinh": None,
                     "cap_dieu_chinh": sorted(_nhom_cap(vm.cat_khoi_tieu_de(text[:hl.DO_DAI_PHAN_DAU])))}
        if trang_thai == "su_dung" and chunks and any(chunks):
            nhom_hash.setdefault(digest, []).append(ten)
    for names in nhom_hash.values():
        if len(names) < 2:
            continue
        canonical = min(names, key=lambda n: ("signed" not in n.casefold(), len(n), n))
        for ten in names:
            if ten != canonical:
                bang[ten].update(trang_thai="ban_trung", ban_chinh=canonical,
                                 ly_do=["Trùng toàn bộ tập nội dung đoạn đã chuẩn hóa với bản chính"])
    return bang


def dau_danh_muc(bang: dict) -> str:
    return hashlib.sha256("\n".join(
        f"{ten}:{m['trang_thai']}:{m.get('ban_chinh')}:{m['sha256_noi_dung']}"
        for ten, m in sorted(bang.items())
    ).encode("utf-8")).hexdigest()[:16]


def _nhom_cap(text: str) -> set[str]:
    text = " ".join(pl._chuan_hoa(text).split())
    groups = set()
    for label, pattern in (
        ("mam_non", r"\bmam non\b"),
        ("tieu_hoc", r"\btieu hoc\b"),
        ("thcs", r"\b(?:trung hoc co so|thcs)\b"),
        ("thpt", r"\b(?:trung hoc pho thong|thpt)\b"),
        ("dai_hoc", r"\bdai hoc\b"),
        ("nghe", r"\b(?:giao duc nghe nghiep|trung cap|cao dang|trung hoc nghe)\b"),
    ):
        if re.search(pattern, text):
            groups.add(label)
    if re.search(r"\b(?:giao duc pho thong|truong pho thong)\b", text):
        groups.update(("tieu_hoc", "thcs", "thpt"))
    return groups


def mau_thuan_pham_vi(doc, cau_hoi: str) -> bool:
    # Chỉ loại mâu thuẫn rõ ràng. Tài liệu chung/không nhãn vẫn được giữ.
    title = " ".join(str(doc.metadata.get(k) or "") for k in
                     ("source_file", "article", "context_label"))
    qgroups, dgroups = _nhom_cap(cau_hoi), _nhom_cap(title)
    if qgroups and dgroups and not qgroups.intersection(dgroups):
        return True
    wanted = pl.nhan_dien_cau_hoi(cau_hoi)
    if not wanted:
        return False
    labels = asdict(pl.suy_phan_loai(title))
    # Nhãn explicit của chunk ưu tiên hơn suy luận lại từ tên.
    labels.update({k: doc.metadata[k] for k in ("mon_hoc", "lop") if doc.metadata.get(k)})
    scope = {k: wanted[k] for k in ("mon_hoc", "lop") if wanted.get(k)}
    return not pl.khong_mau_thuan(labels, scope)


def di_kem_dung_chu_de(muc: dict, doc, cau_hoi: str) -> bool:
    if muc.get("quan_he") != "huong_dan":
        return True
    # Một Luật có nhiều nghị định hướng dẫn các chủ đề khác nhau. Quan hệ
    # pháp lý không đồng nghĩa mọi nghị định đó trả lời được mọi câu về Luật.
    chung = set(("ai bao cac cai cho co cua dang duoc gi hay hien hoi khong la lam "
                 "mot nao nhung ra sao theo the thi trong tu va ve voi "
                 "quy dinh thong tu nghi dinh luat bo giao duc dao tao "
                 "quoc gia viet nam hoc").split())
    tokens = lambda s: set(pl._chuan_hoa(s).split()) - chung
    title = " ".join(str(doc.metadata.get(k) or "") for k in
                     ("source_file", "article", "context_label"))
    return bool(tokens(cau_hoi) & tokens(title))


def ly_do_loai(doc, cau_hoi: str, danh_muc: dict, tinh_trang: dict,
               hom_nay: date | None = None, di_kem: bool = False) -> str:
    ten = doc.metadata.get("source_file", "")
    muc = danh_muc.get(ten, {})
    text = hl.nen(cau_hoi)
    hoi_du_thao = "duthao" in text or "layykien" in text
    state = muc.get("trang_thai")
    if state in {"du_thao", "can_xac_minh"} and not hoi_du_thao:
        return state
    if state == "ban_trung":
        return "ban_trung"
    time_info = tinh_trang.get(ten)
    if (time_info and time_info.chua_toi_ngay_hieu_luc(hom_nay)
            and not any(x in text for x in ("chuacohieuluc", "saphieuluc", "duthao"))):
        return "chua_hieu_luc"
    # Văn bản đi kèm qua quan hệ pháp lý có thể áp dụng nhiều cấp học. Không
    # loại nó chỉ vì tiêu đề có thêm cấp học khác; vẫn phải qua kiểm tra nguồn.
    if not di_kem and mau_thuan_pham_vi(doc, cau_hoi):
        return "mau_thuan_pham_vi"
    if not di_kem:
        wanted = _nhom_cap(cau_hoi)
        scope = set(muc.get("cap_dieu_chinh", []))
        if wanted and scope and not wanted.intersection(scope):
            return "mau_thuan_pham_vi"
    return ""
