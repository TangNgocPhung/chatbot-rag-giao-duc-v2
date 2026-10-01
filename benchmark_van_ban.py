"""
ĐO HÀNH VI CỦA TÁM LỚP XỬ LÝ VĂN BẢN QUY PHẠM
=============================================
Chạy nhanh (không gọi LLM):  python benchmark_van_ban.py
Một use case:                python benchmark_van_ban.py --use-case so_sanh
Gọi cả LLM:                  python benchmark_van_ban.py --bo
Số liệu cho báo cáo:         python benchmark_van_ban.py --tap test --chi-da-doi-chieu
Chỉ kiểm tra tệp câu hỏi:    python benchmark_van_ban.py --kiem-tra

benchmark_chatbot.py đo TRUY HỒI (tài liệu đúng có được tìm ra không) và hậu
kiểm chung. Tám lớp mới (chuyển tiếp, hết hiệu lực dây chuyền, tham chiếu chéo,
thứ bậc, so sánh phiên bản, đối tượng áp dụng, phân cấp, thủ tục) cần đo một
thứ khác: HÀNH VI - có rẽ sang đúng công cụ không, có phát đúng cảnh báo không,
prompt có nhận đúng khối/ghi chú không. Mỗi câu trong
bo_cau_hoi_van_ban_quy_pham.json mang:

  loai = duong_tinh   tính năng PHẢI kích hoạt  -> tỉ lệ đạt = độ nhạy
  loai = doi_chung    tính năng KHÔNG được kích hoạt -> tỉ lệ đạt = độ đặc hiệu

Thiếu câu đối chứng thì một tính năng kích hoạt bừa bãi vẫn đạt 100%.

CHẾ ĐỘ NHANH (mặc định) chạy trọn RAGService._sinh_cau_tra_loi trên chỉ mục
thật nhưng thay bước gọi LLM bằng một hàm ghi lại prompt: mọi kiểm tra về
prompt, cảnh báo, nguồn, gợi ý, công cụ đều chấm được trong vài giây mỗi câu.
Kiểm tra "tra_loi_chua" với câu đi đường RAG chỉ chấm ở --bo (cần câu chữ thật);
câu đi công cụ thì câu trả lời có sẵn nên chấm cả ở chế độ nhanh.

do_tin_cay / da_doi_chieu: câu "gia_dinh" viết theo nội dung văn bản thường gặp,
chưa đối chiếu với kho - báo riêng, và --chi-da-doi-chieu bỏ chúng khỏi số liệu.
Cache câu trả lời bị tắt (RAG_BAT_CACHE=0): câu lấy từ cache không đi qua prompt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from unittest import mock

import chia_tap_benchmark

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_BO = os.path.join(THU_MUC_DU_AN, "bo_cau_hoi_van_ban_quy_pham.json")
CAC_USE_CASE = (
    "chuyen_tiep", "het_theo_goc", "tham_chieu", "thu_bac", "so_sanh", "doi_tuong", "phan_cap", "thu_tuc",
)
CAC_LOAI_CAU = ("duong_tinh", "doi_chung")
CAC_DO_TIN_CAY = ("tinh_toan", "so_tay", "bo_cu", "gia_dinh")
# loại kiểm tra -> kiểu của gia_tri
CAC_LOAI_KIEM_TRA = {
    "cong_cu": str, "khong_cong_cu": str, "tra_loi_chua": str,
    "ngu_canh_chua": str, "ngu_canh_khong_chua": str, "ngu_canh_chua_mot_trong": list,
    "canh_bao": str, "khong_canh_bao": str, "nguon_chua": str, "nhan_nguon_khac": dict, "goi_y_chua": str,
}
CAC_TAP = ("dev", "test", "tat_ca")


# ============================================================
# BỘ CÂU HỎI
# ============================================================
def kiem_tra_bo(bo: dict) -> list[str]:
    """Danh sách lỗi của tệp câu hỏi (rỗng là hợp lệ)."""
    loi = []
    da_gap = set()
    for thu_tu, muc in enumerate(bo.get("cau_hoi") or [], 1):
        dau = f"câu {thu_tu} ({str(muc.get('cau_hoi'))[:40]})"
        if not muc.get("cau_hoi"):
            loi.append(f"{dau}: thiếu cau_hoi")
        if muc.get("cau_hoi") in da_gap:
            loi.append(f"{dau}: câu hỏi trùng")
        da_gap.add(muc.get("cau_hoi"))
        if muc.get("use_case") not in CAC_USE_CASE:
            loi.append(f"{dau}: use_case không hợp lệ {muc.get('use_case')!r}")
        if muc.get("loai") not in CAC_LOAI_CAU:
            loi.append(f"{dau}: loai không hợp lệ {muc.get('loai')!r}")
        if muc.get("do_tin_cay") not in CAC_DO_TIN_CAY:
            loi.append(f"{dau}: do_tin_cay không hợp lệ {muc.get('do_tin_cay')!r}")
        if muc.get("tap") not in chia_tap_benchmark.CAC_TAP:
            loi.append(f"{dau}: chưa gán tap (chạy chia_tap_benchmark.gan_tap)")
        if not isinstance(muc.get("da_doi_chieu"), bool):
            loi.append(f"{dau}: da_doi_chieu phải là true/false")
        if not muc.get("kiem_tra"):
            loi.append(f"{dau}: không có kiem_tra nào")
        for kt in muc.get("kiem_tra") or []:
            kieu = CAC_LOAI_KIEM_TRA.get(kt.get("loai"))
            if kieu is None:
                loi.append(f"{dau}: loại kiểm tra lạ {kt.get('loai')!r}")
            elif not isinstance(kt.get("gia_tri"), kieu):
                loi.append(f"{dau}: {kt['loai']} cần gia_tri kiểu {kieu.__name__}")
    return loi


def nap_bo(duong_dan: str = DUONG_DAN_BO, tap: str = "dev", use_case: str | None = None,
           chi_da_doi_chieu: bool = False) -> list[dict]:
    with open(duong_dan, encoding="utf-8") as tep:
        bo = json.load(tep)
    loi = kiem_tra_bo(bo)
    if loi:
        raise ValueError("; ".join(loi[:5]))
    return [
        muc for muc in bo["cau_hoi"]
        if (tap == "tat_ca" or muc["tap"] == tap)
        and (use_case is None or muc["use_case"] == use_case)
        and (not chi_da_doi_chieu or muc["da_doi_chieu"])
    ]


# ============================================================
# QUAN SÁT MỘT LƯỢT TRẢ LỜI
# ============================================================
@dataclass
class QuanSat:
    tra_loi: str = ""
    ngu_canh: str = ""
    nguon: list[dict] = field(default_factory=list)
    canh_bao: list[str] = field(default_factory=list)
    goi_y: list[str] = field(default_factory=list)
    cong_cu: str | None = None
    da_tu_choi: bool = False
    co_llm: bool = False
    loi: str = ""


def quan_sat(service, cau_hoi: str, dung_llm: bool = False) -> QuanSat:
    """Chạy một câu qua đường trả lời thật. Không dùng LLM thì bước sinh chữ
    được thay bằng hàm ghi lại prompt; có dùng thì vẫn ghi prompt rồi sinh thật."""
    qs = QuanSat(co_llm=dung_llm)
    goc = service._phat_token

    def phat_token(chuoi, dau_vao):
        qs.ngu_canh = dau_vao.get("context", "")
        if dung_llm:
            yield from goc(chuoi, dau_vao)

    try:
        with mock.patch.object(service, "_phat_token", side_effect=phat_token):
            for su_kien in service._sinh_cau_tra_loi(cau_hoi):
                loai = su_kien.get("type")
                if loai == "token":
                    qs.tra_loi += su_kien.get("content", "")
                elif loai == "sources":
                    qs.nguon = su_kien.get("sources") or []
                elif loai == "hieu_luc":
                    qs.canh_bao.append(su_kien.get("kind"))
                elif loai == "goi_y":
                    qs.goi_y = su_kien.get("goi_y") or []
                elif loai == "done":
                    qs.cong_cu = su_kien.get("cong_cu")
                    qs.da_tu_choi = bool(su_kien.get("abstained"))
    except Exception as exc:
        qs.loi = f"{type(exc).__name__}: {exc}"
    return qs


def _nfc(chuoi: str) -> str:
    return unicodedata.normalize("NFC", chuoi or "").lower()


def cham(muc: dict, qs: QuanSat) -> list[dict]:
    """[{loai, gia_tri, ket_qua: 'dat'|'truot'|'bo_qua', ghi_chu}] cho từng kiểm tra."""
    ket_qua = []
    for kt in muc["kiem_tra"]:
        loai, gia_tri = kt["loai"], kt["gia_tri"]
        dat, ghi_chu = None, ""
        if qs.loi:
            dat, ghi_chu = False, qs.loi
        elif loai == "cong_cu":
            dat, ghi_chu = qs.cong_cu == gia_tri, f"công cụ: {qs.cong_cu}"
        elif loai == "khong_cong_cu":
            dat, ghi_chu = qs.cong_cu != gia_tri, f"công cụ: {qs.cong_cu}"
        elif loai == "tra_loi_chua":
            if qs.cong_cu is None and not qs.co_llm:
                ghi_chu = "câu đi đường RAG: chỉ chấm câu chữ ở --bo"
            else:
                dat = _nfc(gia_tri) in _nfc(qs.tra_loi)
        elif loai in ("ngu_canh_chua", "ngu_canh_khong_chua", "ngu_canh_chua_mot_trong"):
            if not qs.ngu_canh:
                # Không có prompt: rẽ công cụ hoặc bị chặn lạc đề. Câu "không
                # chứa" vẫn đúng; câu "chứa" thì trượt, ghi rõ vì sao.
                ghi_chu = "không có prompt (" + (f"công cụ {qs.cong_cu}" if qs.cong_cu else "bị chặn/không truy hồi") + ")"
            if loai == "ngu_canh_chua":
                dat = gia_tri in qs.ngu_canh
            elif loai == "ngu_canh_khong_chua":
                dat = gia_tri not in qs.ngu_canh
            else:
                dat = any(g in qs.ngu_canh for g in gia_tri)
        elif loai == "canh_bao":
            dat, ghi_chu = gia_tri in qs.canh_bao, f"cảnh báo: {qs.canh_bao}"
        elif loai == "khong_canh_bao":
            dat, ghi_chu = gia_tri not in qs.canh_bao, f"cảnh báo: {qs.canh_bao}"
        elif loai == "nguon_chua":
            ten = [n.get("name", "") for n in qs.nguon]
            dat, ghi_chu = any(_nfc(gia_tri) in _nfc(t) for t in ten), f"nguồn: {ten[:4]}"
        elif loai == "nhan_nguon_khac":
            khop = [n for n in qs.nguon if _nfc(gia_tri["nguon"]) in _nfc(n.get("name", ""))]
            ma = [(n.get("validity") or {}).get("code") for n in khop]
            if not khop:
                dat, ghi_chu = False, "không truy hồi được nguồn cần xét nhãn"
            else:
                dat, ghi_chu = all(m != gia_tri["ma"] for m in ma), f"nhãn: {ma}"
        elif loai == "goi_y_chua":
            dat, ghi_chu = any(gia_tri in g for g in qs.goi_y), f"gợi ý: {qs.goi_y[:3]}"
        ket_qua.append({
            "loai": loai, "gia_tri": gia_tri,
            "ket_qua": "bo_qua" if dat is None else ("dat" if dat else "truot"),
            "ghi_chu": ghi_chu,
        })
    return ket_qua


def ket_luan(cac_kiem_tra: list[dict]) -> str:
    """Một câu đạt khi mọi kiểm tra được chấm đều đạt; toàn bỏ qua thì 'bo_qua'."""
    da_cham = [k for k in cac_kiem_tra if k["ket_qua"] != "bo_qua"]
    if not da_cham:
        return "bo_qua"
    return "dat" if all(k["ket_qua"] == "dat" for k in da_cham) else "truot"


# ============================================================
# TỔNG KẾT
# ============================================================
def tong_ket(cac_ket_qua: list[dict]) -> dict:
    """{use_case: {duong_tinh: [đạt, tổng], doi_chung: [...]}} - tách câu đã đối chiếu."""
    bang: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for kq in cac_ket_qua:
        if kq["ket_luan"] == "bo_qua":
            continue
        nhom = "da_doi_chieu" if kq["da_doi_chieu"] else "chua_doi_chieu"
        for khoa in (kq["use_case"], "TONG"):
            for phan in (kq["loai"], f"{kq['loai']}:{nhom}"):
                o = bang[khoa][phan]
                o[0] += kq["ket_luan"] == "dat"
                o[1] += 1
    return {k: dict(v) for k, v in bang.items()}


def _ty_le(o) -> str:
    return f"{o[0]}/{o[1]} ({100 * o[0] / o[1]:.0f}%)" if o and o[1] else "-"


def in_bang(bang: dict) -> None:
    print(f"\n{'use case':<14}{'độ nhạy (dương tính)':<26}{'độ đặc hiệu (đối chứng)':<26}{'chưa đối chiếu (dt/đc)'}")
    for use_case in list(CAC_USE_CASE) + ["TONG"]:
        o = bang.get(use_case)
        if not o:
            continue
        chua = f"{_ty_le(o.get('duong_tinh:chua_doi_chieu'))} / {_ty_le(o.get('doi_chung:chua_doi_chieu'))}"
        print(f"{use_case:<14}{_ty_le(o.get('duong_tinh')):<26}{_ty_le(o.get('doi_chung')):<26}{chua}")


def chay(service, cac_muc: list[dict], dung_llm: bool = False) -> list[dict]:
    ket_qua = []
    for thu_tu, muc in enumerate(cac_muc, 1):
        qs = quan_sat(service, muc["cau_hoi"], dung_llm)
        cac_kiem_tra = cham(muc, qs)
        kl = ket_luan(cac_kiem_tra)
        print(f"[{thu_tu:>2}/{len(cac_muc)}] {kl:<6} {muc['use_case']:<12} {muc['cau_hoi'][:70]}")
        for kt in cac_kiem_tra:
            if kt["ket_qua"] == "truot":
                print(f"         ✗ {kt['loai']} {str(kt['gia_tri'])[:50]} - {kt['ghi_chu'][:80]}")
        ket_qua.append({
            **{k: muc[k] for k in ("cau_hoi", "use_case", "loai", "do_tin_cay", "da_doi_chieu", "tap")},
            "ket_luan": kl, "kiem_tra": cac_kiem_tra,
            "quan_sat": {**asdict(qs), "ngu_canh": qs.ngu_canh[:3000]},
        })
    return ket_qua


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tap", choices=CAC_TAP, default="dev")
    parser.add_argument("--use-case", choices=CAC_USE_CASE, default=None)
    parser.add_argument("--bo", action="store_true", help="gọi cả LLM (chậm, ~150 giây/câu trên CPU)")
    parser.add_argument("--chi-da-doi-chieu", action="store_true",
                        help="bỏ các câu gia_dinh chưa đối chiếu với kho")
    parser.add_argument("--kiem-tra", action="store_true", help="chỉ kiểm tra tệp câu hỏi")
    tham_so = parser.parse_args()

    try:
        cac_muc = nap_bo(tap=tham_so.tap, use_case=tham_so.use_case,
                         chi_da_doi_chieu=tham_so.chi_da_doi_chieu)
    except ValueError as loi:
        print(f"LỖI BỘ CÂU HỎI: {loi}")
        return 1
    if tham_so.kiem_tra:
        print(f"Tệp hợp lệ: {len(cac_muc)} câu trong tập '{tham_so.tap}'.")
        return 0
    if tham_so.tap == "test":
        print("⚠️  Tập TEST: chỉ chạy khi đã đóng băng tham số các lớp xử lý văn bản.")

    os.environ.setdefault("RAG_BAT_CACHE", "0")
    from rag_service import RAGService  # nạp muộn: --kiem-tra không cần mô hình

    service = RAGService()
    service.initialize()
    if service.status.state != "ready":
        print(f"LỖI KHỞI TẠO: {service.status.message}")
        return 1
    ket_qua = chay(service, cac_muc, tham_so.bo)
    bang = tong_ket(ket_qua)
    in_bang(bang)
    duong_dan = os.path.join(
        THU_MUC_DU_AN, f"ket_qua_benchmark_van_ban_{tham_so.tap}{'_bo' if tham_so.bo else ''}.json"
    )
    with open(duong_dan, "w", encoding="utf-8") as tep:
        json.dump({"tong_ket": bang, "cau_hoi": ket_qua}, tep, ensure_ascii=False, indent=1)
    print(f"\nĐã ghi {duong_dan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
