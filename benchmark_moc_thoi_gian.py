"""
ĐO TÍNH NĂNG HỎI THEO MỐC THỜI GIAN
====================================
Chạy:            python benchmark_moc_thoi_gian.py
Chỉ một cặp:     python benchmark_moc_thoi_gian.py --cap day_them
Truy hồi sâu:    python benchmark_moc_thoi_gian.py --sau 24

Bộ câu hỏi: bo_cau_hoi_moc_thoi_gian.json (45 câu, 20 cặp văn bản; 14 cặp có nhãn
đã đối chiếu với sổ quan hệ nhập tay). Tách khỏi bo_cau_hoi_benchmark.json
để con số MRR "toàn bộ" của các lần đo cũ vẫn so được với lần đo mới.

ĐO A/B TRONG CÙNG MỘT LẦN CHẠY
  Mỗi câu truy hồi hai lần trên cùng chỉ mục:
    - "tắt mốc": ép quan_he_van_ban.che_do_thoi_gian luôn trả "hien_hanh" -
      văn bản hết hiệu lực bị LỌC BỎ, văn bản mới hơn được cộng điểm, bất kể
      câu hỏi hỏi về năm nào. Đây là hành vi khi hệ thống không biết mốc.
    - "bật mốc": chế độ tự chọn từ câu hỏi, như khi chạy thật.
  Cùng câu, cùng chỉ mục, chỉ khác đúng một yếu tố, nên chênh lệch giữa hai
  cột là tác động của riêng tính năng này.

  Đo ở khâu truy hồi (RAGService._retrieve), TRƯỚC bước kéo thêm văn bản đi
  kèm (_them_van_ban_di_kem). Bước đó có thể đưa thêm văn bản thay thế vào
  prompt; muốn đo cả nó thì phải chạy luồng trả lời đầy đủ.

NHÃN LÀ SỐ HIỆU, KHÔNG PHẢI TÊN FILE
  Bộ câu hỏi viết được mà không cần nhìn vào kho. Lúc chạy, số hiệu được đổi
  ra file qua ho_so_van_ban. Văn bản chưa có trong kho thì câu đó bị BỎ QUA
  (in ra để biết cần bổ sung văn bản nào), không tính là trượt.

CHỈ SỐ
  - Nhận chế độ đúng:  che_do_thoi_gian chọn đúng "lich_su"/"hien_hanh" như nhãn.
  - Hit@1, MRR@10:     của văn bản đúng mốc, ở mức tài liệu.
  - Đúng phiên bản:    trong hai phiên bản của cùng quy định, bản đúng mốc có
                       xếp TRƯỚC bản sai mốc không. Đây là chỉ số chính.
  - Đúng vào prompt:   mọi văn bản đúng mốc đều có mặt trong cửa sổ chunk đi vào
                       prompt (với câu so sánh: cả hai phiên bản đều có mặt).
  - Sai lọt prompt:    bản sai mốc có nằm trong cửa sổ đó không.
  - McNemar chính xác: trên chỉ số "đúng phiên bản", đếm số câu bật mốc làm
                       tốt lên / tệ đi rồi tính p hai phía. Bộ câu nhỏ, nên đọc
                       p để biết chênh lệch có đủ lớn để không phải do may rủi,
                       không phải để ước lượng độ chính xác trên dân số câu hỏi.

CHẨN ĐOÁN
  Với mỗi cặp văn bản, in ra đồ thị quan hệ (quan_he_van_ban) có cạnh "thay
  thế" từ văn bản mới sang văn bản cũ không, và ngày bắt đầu hiệu lực của
  từng bên. Cặp nào thiếu cạnh thì văn bản cũ không bao giờ "hết hiệu lực" -
  lỗi nằm ở khâu trích quan hệ (van_ban_meta) hoặc sổ nhập tay
  so_quan_he_van_ban.json, không ở khâu chọn chế độ thời gian.

LƯU Ý PHƯƠNG PHÁP
  Nhãn được viết tay từ văn bản gốc, không suy ra từ hồ sơ mà hệ thống tự
  trích. Nếu suy nhãn từ chính hồ sơ đó thì phép đo thành vòng tròn: hệ thống
  trích sai ngày thì nhãn cũng sai theo, và điểm vẫn đẹp.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field

from unittest.mock import patch

import chi_so_ir
import quan_he_van_ban
from hybrid_retrieval import SO_KET_QUA_CUOI

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_BO = os.path.join(THU_MUC_DU_AN, "bo_cau_hoi_moc_thoi_gian.json")
DUONG_DAN_KET_QUA = os.path.join(THU_MUC_DU_AN, "ket_qua_moc_thoi_gian.json")
SO_CHUNK_MAC_DINH = 24
CHE_DO = ("tat_moc", "bat_moc")


# ============================================================
# ĐỔI SỐ HIỆU RA FILE
# ============================================================
def khoa_so_hieu(so_hieu: str) -> str:
    """
    Khóa so khớp: bỏ số 0 đầu và phần cơ quan sau dấu gạch.
      "05/2025/TT-BGDĐT" -> "5/2025/tt"      "23/2015/TTLT-BGDĐT-BNV" -> "23/2015/ttlt"
      "43/2019/QH14"     -> "43/2019/qh14"   "527/QĐ-TTg"             -> "527/qđ"
    Bỏ phần cơ quan vì đó là chỗ OCR và cách viết lệch nhau nhiều nhất (BGDĐT,
    BGDDT, BGDĐT-BNV), trong khi số + năm + loại đã đủ phân biệt văn bản.
    """
    phan = [p.strip() for p in (so_hieu or "").split("/")]
    if not phan or not phan[0]:
        return ""
    if phan[0].isdigit():
        phan[0] = str(int(phan[0]))
    phan[-1] = phan[-1].split("-")[0]
    return "/".join(phan).casefold()


def tep_theo_so_hieu(ho_so: dict, so_hieu: str, so_quan_he=None) -> list[str]:
    """Tệp của văn bản trong kho. Lấy theo đồ thị quan hệ trước (nó gom cả số
    hiệu đọc từ tên tệp), rồi bù bằng hồ sơ với khoá nới lỏng khoa_so_hieu."""
    tep = set()
    if so_quan_he is not None:
        tep.update(so_quan_he.tep_cua_nut.get(quan_he_van_ban.chuan_so_hieu(so_hieu), []))
    khoa = khoa_so_hieu(so_hieu)
    tep.update(
        ten_file for ten_file, muc in (ho_so or {}).items()
        if getattr(muc, "so_hieu", None) and khoa_so_hieu(muc.so_hieu) == khoa
    )
    return sorted(tep)


# ============================================================
# CHẤM MỘT LƯỢT TRUY HỒI (hàm thuần, không cần chỉ mục)
# ============================================================
@dataclass
class DoMotCheDo:
    tai_lieu_xep_hang: list[str] = field(default_factory=list)
    hang_dung: int | None = None      # hạng tài liệu (1-based) của bản đúng đầu tiên
    hang_sai: int | None = None
    # True/False: bản đúng xếp trước/sau bản sai. None: không bản nào được truy hồi.
    dung_phien_ban: bool | None = None
    dung_trong_cua_so: bool = False   # mọi nhãn đúng đều có mặt trong cửa sổ prompt
    sai_trong_cua_so: bool = False
    loi: str = ""


def cham(
    nguon_theo_chunk: list[str],
    tep_dung: dict[str, list[str]],
    tep_sai: dict[str, list[str]],
    so_chunk_prompt: int = SO_KET_QUA_CUOI,
) -> DoMotCheDo:
    """
    nguon_theo_chunk: tên file của từng chunk, theo đúng thứ tự truy hồi.
    tep_dung / tep_sai: {số hiệu: [các file của văn bản đó trong kho]}.
    """
    tai_lieu = chi_so_ir.xep_hang_tai_lieu(nguon_theo_chunk)
    tat_ca_dung = {t for ds in tep_dung.values() for t in ds}
    tat_ca_sai = {t for ds in tep_sai.values() for t in ds}

    def hang_dau(tap: set[str]) -> int | None:
        return next((i for i, t in enumerate(tai_lieu, 1) if t in tap), None)

    hang_dung, hang_sai = hang_dau(tat_ca_dung), hang_dau(tat_ca_sai)
    if hang_dung is None and hang_sai is None:
        dung_phien_ban = None
    elif hang_sai is None:
        dung_phien_ban = True
    elif hang_dung is None:
        dung_phien_ban = False
    else:
        dung_phien_ban = hang_dung < hang_sai

    cua_so = set(nguon_theo_chunk[:so_chunk_prompt])
    return DoMotCheDo(
        tai_lieu_xep_hang=tai_lieu,
        hang_dung=hang_dung,
        hang_sai=hang_sai,
        dung_phien_ban=dung_phien_ban,
        dung_trong_cua_so=bool(tep_dung) and all(
            cua_so & set(ds) for ds in tep_dung.values()
        ),
        sai_trong_cua_so=bool(cua_so & tat_ca_sai),
    )


def mcnemar_chinh_xac(tot_len: int, te_di: int) -> float:
    """p hai phía của kiểm định McNemar chính xác (nhị thức, p = 0.5) trên các
    cặp bất đồng. Không có cặp bất đồng nào thì không có bằng chứng: p = 1."""
    n = tot_len + te_di
    if n == 0:
        return 1.0
    k = min(tot_len, te_di)
    duoi = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * duoi)


# ============================================================
# CHẠY TRÊN CHỈ MỤC THẬT
# ============================================================
@dataclass
class KetQuaMoc:
    cau_hoi: str
    cap: str
    loai: str
    che_do_mong_doi: str
    che_do_nhan_ra: str = ""
    nhan_moc_dung: bool = False
    tep_dung: dict[str, list[str]] = field(default_factory=dict)
    tep_sai: dict[str, list[str]] = field(default_factory=dict)
    bo_qua: str = ""
    # Nhãn của cặp này đã đối chiếu với văn bản gốc chưa (cap_van_ban.da_doi_chieu).
    da_doi_chieu: bool = False
    ket_qua: dict[str, DoMotCheDo] = field(default_factory=dict)


def _nap_bo(cap_loc: str | None) -> dict:
    with open(DUONG_DAN_BO, encoding="utf-8") as tep:
        bo = json.load(tep)
    if cap_loc:
        bo["cau_hoi"] = [m for m in bo["cau_hoi"] if m.get("cap") == cap_loc]
    return bo


def chan_doan_cap(service, cap_van_ban: dict) -> list[dict]:
    """Đồ thị có cạnh "thay thế" mới -> cũ không, và mỗi bên bắt đầu hiệu lực khi nào?"""
    so = service.so_quan_he
    ket_qua = []
    for ten_cap, cap in cap_van_ban.items():
        nut_cu = quan_he_van_ban.chuan_so_hieu(cap["cu"])
        nut_moi = quan_he_van_ban.chuan_so_hieu(cap["moi"])
        cac_canh = {(q.tu, q.loai) for q in so.vao.get(nut_cu, [])}
        ket_qua.append({
            "cap": ten_cap,
            "tep_cu": tep_theo_so_hieu(service.ho_so_van_ban, cap["cu"], so),
            "tep_moi": tep_theo_so_hieu(service.ho_so_van_ban, cap["moi"], so),
            "quan_he_nhan_ra": sorted(
                loai for tu, loai in cac_canh if khoa_so_hieu(tu) == khoa_so_hieu(nut_moi)
            ),
            "cu_bat_dau": so._ngay_bat_dau(nut_cu),
            "moi_bat_dau": so._ngay_bat_dau(nut_moi),
            "moi_co_hieu_luc_theo_nhan": cap.get("moi_co_hieu_luc"),
            "da_doi_chieu": bool(cap.get("da_doi_chieu")),
        })
    return ket_qua


def chay_mot_cau(service, muc: dict, so_chunk: int) -> KetQuaMoc:
    from rag_service import RAGService

    ho_so, so = service.ho_so_van_ban, service.so_quan_he
    kq = KetQuaMoc(
        cau_hoi=muc["cau_hoi"], cap=muc.get("cap", ""), loai=muc.get("loai", ""),
        che_do_mong_doi=muc.get("che_do_mong_doi", "lich_su"),
    )
    kq.tep_dung = {s: tep_theo_so_hieu(ho_so, s, so) for s in muc.get("so_hieu_dung", [])}
    kq.tep_sai = {s: tep_theo_so_hieu(ho_so, s, so) for s in muc.get("so_hieu_sai", [])}
    thieu = [s for s, ds in kq.tep_dung.items() if not ds]
    if thieu or not kq.tep_dung:
        kq.bo_qua = "chưa có trong kho: " + ", ".join(thieu or ["(không có nhãn đúng)"])
        return kq

    che_do_thoi_gian, thoi_diem = quan_he_van_ban.che_do_thoi_gian(kq.cau_hoi)
    kq.che_do_nhan_ra = f"{che_do_thoi_gian} {thoi_diem or ''}".strip()
    kq.nhan_moc_dung = che_do_thoi_gian == kq.che_do_mong_doi

    cau_truy_hoi, _ = RAGService._conversation_inputs(kq.cau_hoi, None)
    for che_do in CHE_DO:
        try:
            if che_do == "tat_moc":
                with patch.object(quan_he_van_ban, "che_do_thoi_gian",
                                  lambda *a, **k: ("hien_hanh", None)):
                    tai_lieu = service._retrieve(cau_truy_hoi, so_ket_qua=so_chunk)
            else:
                tai_lieu = service._retrieve(cau_truy_hoi, so_ket_qua=so_chunk)
            nguon = [d.metadata.get("source_file", "") for d in tai_lieu]
            kq.ket_qua[che_do] = cham(nguon, kq.tep_dung, kq.tep_sai)
        except Exception as exc:
            kq.ket_qua[che_do] = DoMotCheDo(loi=f"{type(exc).__name__}: {exc}")
    return kq


# ============================================================
# BÁO CÁO
# ============================================================
def tong_hop(cac_kq: list[KetQuaMoc]) -> dict:
    """Số liệu cho một nhóm câu. Tách khỏi phần in để test được."""
    do_duoc = [k for k in cac_kq if not k.bo_qua]
    ket_qua = {"so_cau": len(do_duoc), "nhan_moc_dung": sum(k.nhan_moc_dung for k in do_duoc)}
    for che_do in CHE_DO:
        cap_luot = [(k, k.ket_qua[che_do]) for k in do_duoc if not k.ket_qua[che_do].loi]
        luot = [r for _, r in cap_luot]
        # "Đúng phiên bản" chỉ có nghĩa khi bản sai mốc cũng có trong kho và ít
        # nhất một trong hai bản được truy hồi.
        co_cap = [
            r.dung_phien_ban for k, r in cap_luot
            if any(k.tep_sai.values()) and r.dung_phien_ban is not None
        ]
        ket_qua[che_do] = {
            "hit@1": sum(r.hang_dung == 1 for r in luot),
            "mrr@10": (
                sum(1 / r.hang_dung for r in luot if r.hang_dung and r.hang_dung <= 10)
                / len(luot) if luot else 0.0
            ),
            "dung_phien_ban": sum(co_cap),
            "so_cau_co_cap": len(co_cap),
            "dung_trong_cua_so": sum(r.dung_trong_cua_so for r in luot),
            "sai_trong_cua_so": sum(r.sai_trong_cua_so for r in luot),
            "so_luot": len(luot),
        }
    tot_len = te_di = 0
    for k in do_duoc:
        truoc, sau = k.ket_qua["tat_moc"], k.ket_qua["bat_moc"]
        if truoc.loi or sau.loi:
            continue
        a, b = bool(truoc.dung_phien_ban), bool(sau.dung_phien_ban)
        tot_len += (not a) and b
        te_di += a and not b
    ket_qua["tot_len"], ket_qua["te_di"] = tot_len, te_di
    ket_qua["p_mcnemar"] = mcnemar_chinh_xac(tot_len, te_di)
    return ket_qua


def in_bao_cao(cac_kq: list[KetQuaMoc], chan_doan: list[dict]) -> dict:
    theo_loai: dict[str, list[KetQuaMoc]] = {}
    for k in cac_kq:
        theo_loai.setdefault(k.loai or "khac", []).append(k)
    bang = {loai: tong_hop(ds) for loai, ds in theo_loai.items()}
    # Số đưa vào báo cáo chỉ nên lấy từ dòng "nhãn đã đối chiếu".
    bang["nhãn đã đối chiếu"] = tong_hop([k for k in cac_kq if k.da_doi_chieu])
    bang["nhãn chưa đối chiếu"] = tong_hop([k for k in cac_kq if not k.da_doi_chieu])
    bang["TOÀN BỘ"] = tong_hop(cac_kq)

    print("\n" + "=" * 96)
    print("HỎI THEO MỐC THỜI GIAN - mỗi ô là  tắt mốc → bật mốc")
    print("=" * 96)
    print(f"{'Loại câu':<20}{'Câu':>4}{'Chế độ':>10}{'Hit@1':>12}{'MRR@10':>15}"
          f"{'Đúng phiên bản':>17}{'Đúng vào prompt':>17}{'Sai lọt prompt':>16}")
    for loai, tt in bang.items():
        if loai in ("nhãn đã đối chiếu", "TOÀN BỘ"):
            print("-" * 96)
        if not tt["so_cau"] and loai != "TOÀN BỘ":
            continue
        t, b = tt["tat_moc"], tt["bat_moc"]
        print(
            f"{loai:<20}{tt['so_cau']:>4}{tt['nhan_moc_dung']:>6}/{tt['so_cau']:<3}"
            f"{t['hit@1']:>6} → {b['hit@1']:<3}"
            f"{t['mrr@10']:>8.2f} → {b['mrr@10']:<4.2f}"
            f"{t['dung_phien_ban']:>6}/{t['so_cau_co_cap']} → {b['dung_phien_ban']}/{b['so_cau_co_cap']:<3}"
            f"{t['dung_trong_cua_so']:>9} → {b['dung_trong_cua_so']:<5}"
            f"{t['sai_trong_cua_so']:>8} → {b['sai_trong_cua_so']:<3}"
        )
    toan_bo = bang["TOÀN BỘ"]
    print(f"\nĐúng phiên bản: bật mốc làm tốt lên {toan_bo['tot_len']} câu, tệ đi "
          f"{toan_bo['te_di']} câu · McNemar chính xác p = {toan_bo['p_mcnemar']:.3f}")
    if toan_bo["so_cau"] < 30:
        print(f"Chỉ {toan_bo['so_cau']} câu đo được: đọc bảng như bộ ca kiểm thử, "
              "chưa phải ước lượng độ chính xác.")

    bo_qua = [k for k in cac_kq if k.bo_qua]
    if bo_qua:
        print(f"\nBỏ qua {len(bo_qua)} câu vì văn bản chưa có trong kho:")
        for k in bo_qua:
            print(f"    · [{k.cap}] {k.bo_qua}")

    print("\nChẩn đoán từng cặp văn bản (hệ thống tự trích):")
    for cd in chan_doan:
        if not (cd["tep_cu"] and cd["tep_moi"]):
            thieu = ("cả hai văn bản" if not (cd["tep_cu"] or cd["tep_moi"])
                     else "văn bản cũ" if not cd["tep_cu"] else "văn bản mới")
            print(f"    · {cd['cap']:<20} thiếu {thieu} trong kho")
            continue
        quan_he = ", ".join(cd["quan_he_nhan_ra"]) or "KHÔNG có cạnh nào"
        nhan = "" if cd["da_doi_chieu"] else " [nhãn chưa đối chiếu]"
        print(f"    · {cd['cap']:<20}{nhan} mới -> cũ: {quan_he}; cũ từ {cd['cu_bat_dau']}, "
              f"mới từ {cd['moi_bat_dau']} (nhãn: mới có hiệu lực {cd['moi_co_hieu_luc_theo_nhan']})")

    sai_moc = [k for k in cac_kq if not k.bo_qua and not k.nhan_moc_dung]
    if sai_moc:
        print("\nChọn chế độ thời gian sai:")
        for k in sai_moc:
            print(f"    · mong đợi {k.che_do_mong_doi}, hệ thống {k.che_do_nhan_ra}"
                  f"  ·  {k.cau_hoi[:60]}")

    te_di = [
        k for k in cac_kq if not k.bo_qua
        and k.ket_qua["tat_moc"].dung_phien_ban and not k.ket_qua["bat_moc"].dung_phien_ban
    ]
    if te_di:
        print("\nBật mốc làm TỆ ĐI (xem kỹ trước tiên):")
        for k in te_di:
            print(f"    · {k.cau_hoi[:70]}")
    return bang


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cap", default=None, help="chỉ chạy một cặp văn bản")
    parser.add_argument("--sau", type=int, default=SO_CHUNK_MAC_DINH,
                        help=f"số chunk truy hồi (mặc định {SO_CHUNK_MAC_DINH})")
    tham_so = parser.parse_args()

    from rag_service import RAGService

    bo = _nap_bo(tham_so.cap)
    service = RAGService()
    service.initialize()
    if service.status.state != "ready":
        print(f"LỖI KHỞI TẠO: {service.status.message}")
        return 1

    cap_van_ban = bo.get("cap_van_ban", {})
    if tham_so.cap:
        cap_van_ban = {k: v for k, v in cap_van_ban.items() if k == tham_so.cap}
    chan_doan = chan_doan_cap(service, cap_van_ban)

    cac_kq = []
    for thu_tu, muc in enumerate(bo["cau_hoi"], 1):
        kq = chay_mot_cau(service, muc, tham_so.sau)
        kq.da_doi_chieu = bool(bo.get("cap_van_ban", {}).get(kq.cap, {}).get("da_doi_chieu"))
        cac_kq.append(kq)
        if kq.bo_qua:
            dong = "BỎ QUA"
        else:
            t, b = kq.ket_qua["tat_moc"], kq.ket_qua["bat_moc"]
            dong = f"hạng {t.hang_dung} → {b.hang_dung}"
        print(f"[{thu_tu:>2}/{len(bo['cau_hoi'])}] {dong:<16} {kq.cau_hoi[:64]}", flush=True)

    bang = in_bao_cao(cac_kq, chan_doan)
    with open(DUONG_DAN_KET_QUA, "w", encoding="utf-8") as tep:
        json.dump({
            "chay_luc": time.strftime("%Y-%m-%d %H:%M:%S"),
            "so_vector": service.status_dict()["vector_count"],
            "so_chunk_truy_hoi": tham_so.sau,
            "so_chunk_vao_prompt": SO_KET_QUA_CUOI,
            "tong_hop": bang,
            "chan_doan_cap": chan_doan,
            "ket_qua": [asdict(k) for k in cac_kq],
        }, tep, ensure_ascii=False, indent=1)
    print(f"\nĐã ghi {DUONG_DAN_KET_QUA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
