"""
ĐO ĐỘ CHÍNH XÁC CỦA BỘ TRÍCH QUAN HỆ VĂN BẢN (van_ban_meta.trich_quan_he_day_du)
=========================================================================
Bước 1 - lấy mẫu câu để gán nhãn tay:
    python danh_gia_trich_quan_he.py xuat --so 80
    -> nhan_quan_he.csv (mở bằng Excel, điền ba cột thay_the, bai_bo_mot_phan, sua_doi)

Bước 2 - chấm:
    python danh_gia_trich_quan_he.py cham nhan_quan_he.csv

So trước/sau một thay đổi mã nguồn, trên CÙNG bộ nhãn:
    git worktree add ../ban-cu main
    python danh_gia_trich_quan_he.py cham nhan_quan_he.csv --ma-nguon ../ban-cu

CHỌN CÂU THEO TỪ KHÓA, KHÔNG THEO KẾT QUẢ CỦA HỆ THỐNG
  Câu ứng viên là mọi câu trong kho có động từ quan hệ (thay thế, bãi bỏ, sửa
  đổi, hết hiệu lực) VÀ có ít nhất một số hiệu văn bản. Nếu chỉ lấy những câu
  hệ thống đã trích ra quan hệ thì đo được precision nhưng recall luôn đẹp giả
  tạo, vì câu hệ thống bỏ sót không bao giờ lọt vào mẫu. Giới hạn còn lại: quan
  hệ diễn đạt không dùng các động từ này thì nằm ngoài mẫu, recall đo được là
  recall TRÊN TẬP ỨNG VIÊN.

GÁN NHÃN MÙ
  Tệp CSV không có cột dự đoán của hệ thống. Người gán nhãn nhìn thấy dự đoán
  thì có xu hướng đồng ý với nó (thiên lệch mỏ neo), và độ chính xác đo được
  sẽ cao hơn thực tế.

QUY ƯỚC GÁN NHÃN (chỉ ghi quan hệ mà CHÍNH VĂN BẢN CHỨA CÂU tác động lên văn bản khác)
  thay_the        : văn bản kia hết hiệu lực TOÀN BỘ (thay thế, bãi bỏ, hết hiệu lực).
  bai_bo_mot_phan : BÃI BỎ hẳn vài điều, khoản, điểm của văn bản kia - phần đó
                    hết hiệu lực, phần còn lại vẫn áp dụng.
  sua_doi         : văn bản kia bị sửa đổi, bổ sung, THAY một điều khoản bằng
                    nội dung mới, hoặc thay / bỏ vài cụm từ.
  (Cùng quy ước với quan_he_van_ban - lệch quy ước là đo sai thứ khác.)
  Để trống : câu nói về quan hệ giữa hai văn bản KHÁC ("Nghị định 311 thay thế
             Nghị định 71"), câu ở thể bị động theo chiều ngược lại ("được sửa
             đổi bởi ..."), câu căn cứ, hoặc không có quan hệ nào.
  Nhiều số hiệu trong một ô thì ngăn cách bằng dấu chấm phẩy. Viết số hiệu như trong văn
  bản, không cần chuẩn hoá ("05/2025/TT-BGDĐT" hay "5/2025/TT-BGDDT" đều được).
  Câu OCR hỏng tới mức không đọc được thì ghi "bo qua" vào cột ghi_chu: câu đó
  bị loại khỏi phép chấm, và số câu bị loại được in ra để báo cáo trung thực.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import os
import random
import re
import sys
from dataclasses import dataclass, field

import van_ban_meta
from benchmark_moc_thoi_gian import khoa_so_hieu

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_NHAN = os.path.join(THU_MUC_DU_AN, "nhan_quan_he.csv")
HAT_GIONG = 20261001
DO_DAI_NGU_CANH = 150
DO_DAI_CAU_TOI_DA = 700
LOAI = ("thay_the", "bai_bo_mot_phan", "sua_doi")
COT = ["ma", "tep", "ngu_canh_truoc", "cau", "thay_the", "bai_bo_mot_phan", "sua_doi", "ghi_chu"]

MAU_DONG_TU = re.compile(r"thay\s*thế|bãi\s*bỏ|sửa\s*đổi|hết\s*hiệu\s*lực", re.IGNORECASE)


# ============================================================
# BƯỚC 1: LẤY MẪU CÂU ỨNG VIÊN
# ============================================================
def tach_cau(van_ban: str) -> list[tuple[int, str]]:
    """(vị trí bắt đầu, câu). Chỉ cắt ở dấu chấm/chấm phẩy, không cắt ở xuống
    dòng: OCR ngắt dòng giữa câu, cắt theo dòng sẽ tách chủ ngữ khỏi động từ."""
    ket_qua = []
    bat_dau = 0
    for khop in re.finditer(r"[.;]", van_ban or ""):
        cau = van_ban[bat_dau: khop.end()]
        if cau.strip():
            ket_qua.append((bat_dau, cau))
        bat_dau = khop.end()
    if (van_ban or "")[bat_dau:].strip():
        ket_qua.append((bat_dau, van_ban[bat_dau:]))
    return ket_qua


def la_ung_vien(cau: str) -> bool:
    return bool(MAU_DONG_TU.search(cau)) and bool(van_ban_meta.trich_so_hieu(cau))


def cau_ung_vien(van_ban_theo_file: dict[str, str]) -> list[dict]:
    ket_qua = []
    for ten_file in sorted(van_ban_theo_file):
        van_ban = van_ban_theo_file[ten_file]
        for vi_tri, cau in tach_cau(van_ban):
            if len(cau) > DO_DAI_CAU_TOI_DA or not la_ung_vien(cau):
                continue
            ket_qua.append({
                "tep": ten_file,
                "ngu_canh_truoc": " ".join(
                    van_ban[max(0, vi_tri - DO_DAI_NGU_CANH): vi_tri].split()
                ),
                "cau": " ".join(cau.split()),
            })
    return ket_qua


def lay_mau(ung_vien: list[dict], so: int, hat_giong: int = HAT_GIONG) -> list[dict]:
    """Mẫu ngẫu nhiên đơn giản, hạt giống cố định. Câu giống hệt nhau (bản sao
    của cùng văn bản dưới hai tên file) chỉ lấy một lần - gán nhãn hai lần một
    câu chỉ làm khoảng tin cậy hẹp giả tạo."""
    da_thay, duy_nhat = set(), []
    for muc in ung_vien:
        if muc["cau"] not in da_thay:
            da_thay.add(muc["cau"])
            duy_nhat.append(muc)
    mau = random.Random(hat_giong).sample(duy_nhat, min(so, len(duy_nhat)))
    return [{"ma": f"q{thu_tu:03d}", **muc, **{loai: "" for loai in LOAI}, "ghi_chu": ""}
            for thu_tu, muc in enumerate(mau, 1)]


def ghi_csv(duong_dan: str, cac_dong: list[dict]) -> None:
    # utf-8-sig: Excel trên Windows chỉ nhận ra UTF-8 khi có BOM, thiếu BOM là
    # tiếng Việt vỡ dấu ngay khi mở.
    with open(duong_dan, "w", encoding="utf-8-sig", newline="") as tep:
        viet = csv.DictWriter(tep, fieldnames=COT)
        viet.writeheader()
        viet.writerows(cac_dong)


def doc_csv(duong_dan: str) -> list[dict]:
    with open(duong_dan, encoding="utf-8-sig", newline="") as tep:
        return list(csv.DictReader(tep))


# ============================================================
# BƯỚC 2: CHẤM
# ============================================================
def wilson(dung: int, tong: int, z: float = 1.96) -> tuple[float, float]:
    """Khoảng tin cậy Wilson cho một tỉ lệ. Dùng thay khoảng Wald (p ± z·√(p(1-p)/n))
    vì Wald sụp về độ rộng 0 khi p = 0 hoặc 1 - đúng chỗ hay gặp với mẫu nhỏ."""
    if tong == 0:
        return 0.0, 1.0
    p = dung / tong
    mau = 1 + z * z / tong
    tam = (p + z * z / (2 * tong)) / mau
    le = z * math.sqrt(p * (1 - p) / tong + z * z / (4 * tong * tong)) / mau
    return max(0.0, tam - le), min(1.0, tam + le)


def _khoa_trong_o(o: str) -> set[str]:
    return {khoa_so_hieu(s) for s in re.split(r"[;,\n]", o or "") if s.strip()}


def nhan_vang(dong: dict) -> dict[str, set[str]]:
    return {loai: _khoa_trong_o(dong.get(loai, "")) for loai in LOAI}


def du_doan(dong: dict, trich) -> dict[str, set[str]]:
    """
    Chạy bộ trích trên ngữ cảnh + câu, đúng như khi nó đọc cả văn bản (luật
    "ngay trước động từ đã có số hiệu khác" cần phần chữ phía trước). Chỉ giữ
    số hiệu nằm TRONG câu: quan hệ rút ra từ phần ngữ cảnh thuộc về câu khác.
    `trich`: văn bản -> {loại: [số hiệu]} (xem nap_trich_quan_he).
    """
    quan_he = trich(f"{dong.get('ngu_canh_truoc', '')} {dong['cau']}")
    trong_cau = {khoa_so_hieu(s) for s in van_ban_meta.trich_so_hieu(dong["cau"])}
    return {
        loai: {khoa_so_hieu(s) for s in quan_he.get(loai, [])} & trong_cau
        for loai in LOAI
    }


@dataclass
class DiemMotLoai:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


@dataclass
class KetQuaCham:
    so_cau: int = 0
    so_cau_bo_qua: int = 0
    theo_loai: dict[str, DiemMotLoai] = field(
        default_factory=lambda: {loai: DiemMotLoai() for loai in LOAI}
    )
    # (nhãn vàng, dự đoán) -> số cặp (câu, số hiệu). "khong" là không có quan hệ.
    nham_lan: dict[tuple[str, str], int] = field(default_factory=dict)
    loi: list[dict] = field(default_factory=list)


def _lop(khoa: str, nhan: dict[str, set[str]]) -> str:
    return next((loai for loai in LOAI if khoa in nhan[loai]), "khong")


def cham(cac_dong: list[dict], trich) -> KetQuaCham:
    kq = KetQuaCham()
    for dong in cac_dong:
        if (dong.get("ghi_chu") or "").strip().lower().startswith("bo qua"):
            kq.so_cau_bo_qua += 1
            continue
        kq.so_cau += 1
        vang, doan = nhan_vang(dong), du_doan(dong, trich)
        for loai in LOAI:
            diem = kq.theo_loai[loai]
            diem.tp += len(vang[loai] & doan[loai])
            diem.fp += len(doan[loai] - vang[loai])
            diem.fn += len(vang[loai] - doan[loai])
        for khoa in set().union(*vang.values(), *doan.values()):
            cap = (_lop(khoa, vang), _lop(khoa, doan))
            kq.nham_lan[cap] = kq.nham_lan.get(cap, 0) + 1
            if cap[0] != cap[1]:
                kq.loi.append({"ma": dong.get("ma"), "so_hieu": khoa,
                               "vang": cap[0], "du_doan": cap[1], "cau": dong["cau"]})
    return kq


def _ba_loai(mo_dun):
    """Hàm văn bản -> {loại: [số hiệu]}. Bản cũ chỉ có trich_quan_he hai loại
    (thay thế, sửa đổi) thì bãi bỏ một phần coi như rỗng - vẫn so được trên
    cùng bộ nhãn, và ô nhầm lẫn bai_bo_mot_phan -> thay_the lộ ra đúng chỗ bản
    cũ gộp sai."""
    if hasattr(mo_dun, "trich_quan_he_day_du"):
        return mo_dun.trich_quan_he_day_du

    def trich(van_ban):
        thay_the, sua_doi = mo_dun.trich_quan_he(van_ban)
        return {"thay_the": thay_the, "bai_bo_mot_phan": [], "sua_doi": sua_doi}

    return trich


def nap_trich_quan_he(ma_nguon: str | None):
    """Bộ trích của thư mục mã nguồn khác (một git worktree) để so trước/sau
    trên cùng bộ nhãn. Nạp bằng đường dẫn tệp thay vì sys.path để không đụng
    vào van_ban_meta đã nạp trong tiến trình này."""
    if not ma_nguon:
        return _ba_loai(van_ban_meta)
    duong_dan = os.path.join(os.path.abspath(ma_nguon), "van_ban_meta.py")
    ten = f"van_ban_meta_ngoai_{abs(hash(duong_dan))}"
    dac_ta = importlib.util.spec_from_file_location(ten, duong_dan)
    mo_dun = importlib.util.module_from_spec(dac_ta)
    # @dataclass tra module của lớp trong sys.modules lúc định nghĩa lớp; thiếu
    # bước đăng ký này thì van_ban_meta thật (có HoSoVanBan) không nạp được.
    sys.modules[ten] = mo_dun
    dac_ta.loader.exec_module(mo_dun)
    return _ba_loai(mo_dun)


def in_ket_qua(kq: KetQuaCham) -> None:
    print("=" * 78)
    bo_qua = f", loại {kq.so_cau_bo_qua} câu OCR hỏng" if kq.so_cau_bo_qua else ""
    print(f"ĐỘ CHÍNH XÁC TRÍCH QUAN HỆ  ({kq.so_cau} câu đã gán nhãn{bo_qua})")
    print("=" * 78)
    print(f"{'Loại':<16}{'TP':>5}{'FP':>5}{'FN':>5}"
          f"{'Precision':>12}{'KTC 95%':>16}{'Recall':>9}{'KTC 95%':>16}{'F1':>7}")
    for loai, d in kq.theo_loai.items():
        p_thap, p_cao = wilson(d.tp, d.tp + d.fp)
        r_thap, r_cao = wilson(d.tp, d.tp + d.fn)
        print(f"{loai:<16}{d.tp:>5}{d.fp:>5}{d.fn:>5}"
              f"{d.precision:>12.2f}{f'{p_thap:.2f}–{p_cao:.2f}':>16}"
              f"{d.recall:>9.2f}{f'{r_thap:.2f}–{r_cao:.2f}':>16}{d.f1:>7.2f}")

    print("\nMa trận nhầm lẫn theo cặp (câu, số hiệu)  -  hàng: nhãn tay, cột: hệ thống")
    lop = (*LOAI, "khong")
    print(f"{'':<16}" + "".join(f"{c:>17}" for c in lop))
    for vang in lop:
        print(f"{vang:<16}" + "".join(f"{kq.nham_lan.get((vang, d), 0):>17}" for d in lop))
    mot_phan_thanh_toan_bo = sum(
        kq.nham_lan.get((vang, "thay_the"), 0) for vang in ("bai_bo_mot_phan", "sua_doi")
    )
    if mot_phan_thanh_toan_bo:
        print(f"\n{mot_phan_thanh_toan_bo} lần tác động một phần bị hiểu thành thay thế "
              "toàn bộ - lỗi nặng nhất: ở chế độ hiện hành cả văn bản còn hiệu lực "
              "bị lọc khỏi câu trả lời.")

    if kq.loi:
        print(f"\nCác cặp sai ({len(kq.loi)}):")
        for loi in kq.loi[:25]:
            print(f"    · {loi['ma']} {loi['so_hieu']}: nhãn {loi['vang']}, "
                  f"hệ thống {loi['du_doan']}  ·  {loi['cau'][:70]}")
    tong_vang = sum(d.tp + d.fn for d in kq.theo_loai.values())
    if tong_vang < 30:
        print(f"\nChỉ có {tong_vang} quan hệ trong nhãn tay: khoảng tin cậy còn rộng, "
              "nên gán thêm câu trước khi đưa con số vào báo cáo.")


# ============================================================
# DÒNG LỆNH
# ============================================================
def _van_ban_trong_kho() -> dict[str, str]:
    from langchain_community.vectorstores import FAISS

    from main import DUONG_DAN_LUU_INDEX, tao_embeddings_va_llm

    embeddings, _ = tao_embeddings_va_llm()
    kho = FAISS.load_local(
        DUONG_DAN_LUU_INDEX, embeddings, allow_dangerous_deserialization=True
    )
    theo_file: dict[str, list[str]] = {}
    for doc in kho.docstore._dict.values():
        ten_file = doc.metadata.get("source_file")
        if ten_file:
            theo_file.setdefault(ten_file, []).append(doc.page_content)
    return {ten: "\n".join(phan) for ten, phan in theo_file.items()}


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    lenh = parser.add_subparsers(dest="lenh", required=True)
    xuat = lenh.add_parser("xuat", help="lấy mẫu câu ứng viên ra CSV để gán nhãn")
    xuat.add_argument("--so", type=int, default=80)
    xuat.add_argument("--hat-giong", type=int, default=HAT_GIONG)
    xuat.add_argument("--ra", default=DUONG_DAN_NHAN)
    xuat.add_argument("--ghi-de", action="store_true",
                      help="cho phép ghi đè tệp đã có (mất nhãn đã gán)")
    cham_lenh = lenh.add_parser("cham", help="chấm trên CSV đã gán nhãn")
    cham_lenh.add_argument("tep", nargs="?", default=DUONG_DAN_NHAN)
    cham_lenh.add_argument("--ma-nguon", default=None,
                           help="thư mục mã nguồn khác (git worktree) để chấm bộ trích của nó")
    tham_so = parser.parse_args()

    if tham_so.lenh == "xuat":
        if os.path.exists(tham_so.ra) and not tham_so.ghi_de:
            print(f"{tham_so.ra} đã có - có thể đang chứa nhãn gán tay. "
                  "Thêm --ghi-de nếu thật sự muốn tạo lại.")
            return 1
        ung_vien = cau_ung_vien(_van_ban_trong_kho())
        mau = lay_mau(ung_vien, tham_so.so, tham_so.hat_giong)
        ghi_csv(tham_so.ra, mau)
        print(f"{len(ung_vien)} câu ứng viên trong kho, đã lấy mẫu {len(mau)} câu "
              f"vào {tham_so.ra}.\nĐiền cột thay_the / bai_bo_mot_phan / sua_doi theo "
              "quy ước ở đầu danh_gia_trich_quan_he.py, rồi chạy lệnh cham.")
        return 0

    cac_dong = doc_csv(tham_so.tep)
    kq = cham(cac_dong, nap_trich_quan_he(tham_so.ma_nguon))
    if tham_so.ma_nguon:
        print(f"Bộ trích của: {os.path.abspath(tham_so.ma_nguon)}")
    in_ket_qua(kq)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
