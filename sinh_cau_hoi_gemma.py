"""
SINH LẠI BỘ CÂU HỎI BENCHMARK BẰNG MỘT MÔ HÌNH THỨ BA (Gemma 3 4B)
=================================================================
Chatbot trả lời bằng Qwen; bộ câu hỏi cũ do Claude soạn. Để bộ đo độc lập với
cả hai, script này cho Gemma 3 4B (Google, chạy cục bộ qua Ollama) đặt lại từng
câu hỏi từ CHÍNH đoạn văn bản trong kho:

  1. Giữ nguyên khung của bộ cũ: cùng số câu, cùng nhóm, cùng tập dev/test, cùng
     tài liệu được hỏi (nhãn nguon_mong_doi). Như vậy so được điểm hai bộ.
  2. Với mỗi câu, CODE chọn ngẫu nhiên (hạt giống cố định) một đoạn của tài liệu
     nhãn trong chỉ mục FAISS, đưa cho Gemma đặt một câu hỏi mà đoạn đó trả lời
     được. Nhãn vì thế đúng theo cách dựng, không do mô hình nào gán.
  3. Code lọc câu hỏi hỏng rồi cho đặt lại (tối đa SO_LAN_THU lần): không có dấu
     "?", nhắc tới "đoạn trích/văn bản này", nhóm phap_luat_noi_dung lại nêu số
     hiệu, nhóm phap_luat_so_hieu lại thiếu số hiệu, hoặc chép nguyên một chuỗi
     dài từ đoạn văn (làm truy hồi từ khoá dễ một cách giả tạo).
  4. Câu ngoai_pham_vi: Gemma tự đặt câu hỏi theo danh sách lĩnh vực bên dưới.

Đầu ra:
  bo_cau_hoi_benchmark_gemma.json    bộ câu hỏi, cùng định dạng bộ cũ
  nhat_ky_sinh_cau_hoi_gemma.jsonl   từng câu kèm đoạn gốc, số lần thử, lý do
                                     loại - để rà tay và để chạy tiếp khi đứt
Chạy:  python sinh_cau_hoi_gemma.py            (chạy tiếp từ chỗ dừng)
       python sinh_cau_hoi_gemma.py --so 5     (thử 5 câu đầu)
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import random
import re
import sys
import time
import unicodedata

import requests

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_BO_CU = os.path.join(THU_MUC_DU_AN, "bo_cau_hoi_benchmark.json")
DUONG_DAN_BO_MOI = os.path.join(THU_MUC_DU_AN, "bo_cau_hoi_benchmark_gemma.json")
DUONG_DAN_NHAT_KY = os.path.join(THU_MUC_DU_AN, "nhat_ky_sinh_cau_hoi_gemma.jsonl")
DUONG_DAN_INDEX = os.getenv(
    "RAG_INDEX_PATH", os.path.join(THU_MUC_DU_AN, "faiss_index_data_giao_duc")
)

MO_HINH = os.getenv("MO_HINH_SINH_CAU_HOI", "gemma3:4b")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
HAT_GIONG = 20261006
SO_LAN_THU = 4
SO_KY_TU_DOAN = 1800
# Chép nguyên từ 7 chữ liền trở lên là coi như bê câu trong văn bản.
CHUOI_CHEP_TOI_DA = 6

NHOM_NGOAI = "ngoai_pham_vi"
NHOM_SO_HIEU = "phap_luat_so_hieu"
NHOM_NOI_DUNG = "phap_luat_noi_dung"

VAI_NGUOI_HOI = [
    "một phụ huynh học sinh",
    "một giáo viên phổ thông",
    "một hiệu trưởng",
    "một sinh viên",
    "một cán bộ phòng giáo dục",
    "một giảng viên đại học",
]

# Lĩnh vực cho câu ngoài phạm vi: nửa đầu là pháp luật NGOÀI giáo dục (nghe
# giống, dễ lọt cổng chặn), nửa sau lạc đề hẳn. 25 lĩnh vực x 3 = 75 câu.
LINH_VUC_NGOAI = [
    "luật đất đai, sổ đỏ, chuyển nhượng đất",
    "luật lao động: hợp đồng, nghỉ phép năm của công nhân",
    "luật hôn nhân và gia đình, ly hôn",
    "thuế thu nhập cá nhân",
    "luật giao thông đường bộ, mức phạt vi phạm",
    "bảo hiểm y tế khi đi khám bệnh",
    "thủ tục đăng ký kinh doanh, thành lập công ty",
    "thừa kế tài sản, di chúc",
    "đăng ký cư trú, tạm trú",
    "luật nhà ở, mua bán chung cư",
    "nghĩa vụ quân sự",
    "luật bảo vệ người tiêu dùng",
    "thủ tục làm hộ chiếu, xuất nhập cảnh",
    "nấu ăn, công thức món ăn",
    "thời tiết, dự báo mưa bão",
    "bóng đá, thể thao",
    "du lịch, đặt vé máy bay",
    "sức khỏe, triệu chứng bệnh",
    "điện thoại, máy tính, phần mềm",
    "giá vàng, chứng khoán, tiền ảo",
    "chăm sóc cây cảnh, làm vườn",
    "nuôi chó mèo, thú cưng",
    "âm nhạc, phim ảnh, ca sĩ",
    "sửa chữa xe máy, ô tô",
    "chăm sóc sắc đẹp, mỹ phẩm",
]

CUM_TU_THAM_CHIEU = (
    "đoạn trích", "đoạn văn", "văn bản này", "tài liệu này", "nêu trên",
    "trên đây", "văn bản trên", "tài liệu trên", "đoạn trên",
)
# "Những quy định này...", "hệ thống đó..." - trỏ về đoạn trích người đọc không thấy.
MAU_TRO_NGU_CANH = re.compile(
    r"\bnày\b|\b(quy định|văn bản|tài liệu|hệ thống|thông tư|nghị định|chương trình"
    r"|điều|bảng|danh sách|nội dung)\s+(đó|trên|kể trên)\b",
    re.IGNORECASE,
)
MAU_SO_HIEU = re.compile(r"\d{1,4}\s*/\s*\d{4}\s*/\s*[A-ZĐ]")
MAU_NEU_VAN_BAN = re.compile(
    r"(nghị định|thông tư|luật|nghị quyết|quyết định|công văn)\s+(số\s+)?\d",
    re.IGNORECASE,
)
MAU_DIEU_KHOAN = re.compile(r"\b(điều|khoản)\s+\d", re.IGNORECASE)
CHU_GIAO_DUC = ("giáo dục", "học sinh", "giáo viên", "trường", "sinh viên",
                "học phí", "nhà giáo", "đào tạo", "thi ", "hiệu trưởng", "lớp học",
                "giảng viên")

LOAI_THEO_KY_HIEU = [
    ("NĐ-CP", "Nghị định"), ("TT", "Thông tư"), ("NQ", "Nghị quyết"),
    ("QĐ", "Quyết định"), ("QH", "Luật"),
]
MAU_NHAN_SO_HIEU = re.compile(
    r"^(Luật|Nghị-định|Thông-tư|Nghị-quyết|Quyết-định)-(\d+)-(\d{4})-(.+)$"
)
MAU_SO_HIEU_DAY_DU = re.compile(
    r"(\d{1,4})\s*/\s*(\d{4})\s*/\s*([A-ZĐ]{1,4}(?:\s*-\s*[A-ZĐ]{1,8})?\d{0,2})"
)


# ------------------------------------------------------------------ kho đoạn văn
def nap_doan_theo_tep() -> dict[str, list]:
    """Đọc thẳng docstore của FAISS - không cần model embedding."""
    with open(os.path.join(DUONG_DAN_INDEX, "index.pkl"), "rb") as f:
        docstore = pickle.load(f)[0]
    theo_tep: dict[str, list] = {}
    for ma, doc in docstore._dict.items():
        ten = doc.metadata.get("source_file")
        if ten:
            theo_tep.setdefault(ten, []).append((ma, doc))
    return theo_tep


def _ty_le_chu(van_ban: str) -> float:
    if not van_ban:
        return 0.0
    return sum(c.isalpha() for c in van_ban) / len(van_ban)


def doan_ung_vien(cac_doan: list) -> list:
    """Đoạn đủ dài, ít rác OCR, không phải phần căn cứ / nơi nhận / chữ ký."""
    tot = []
    for i, (ma, doc) in enumerate(cac_doan):
        noi_dung = doc.page_content
        if len(noi_dung) < 300 or _ty_le_chu(noi_dung) < 0.6:
            continue
        thap = noi_dung.lower()
        if "nơi nhận" in thap or thap.count("căn cứ") >= 3:
            continue
        # Điều khoản thi hành văn bản nào cũng có ("có hiệu lực từ ngày...") -
        # câu hỏi đặt từ đó không chỉ được về một văn bản cụ thể.
        if "hiệu lực thi hành" in thap or "chịu trách nhiệm thi hành" in thap:
            continue
        tot.append((i, ma, doc))
    # Văn bản quy phạm: ưu tiên đoạn có "Điều" (nội dung quy định thật).
    co_dieu = [x for x in tot if re.search(r"\bĐiều\s+\d", x[2].page_content)]
    return co_dieu or tot or [(i, ma, doc) for i, (ma, doc) in enumerate(cac_doan)]


def tep_cua_nhan(theo_tep: dict, nhan: str) -> list[str]:
    khoa = nhan.casefold().strip()
    return sorted(t for t in theo_tep if khoa in t.casefold())


def so_hieu_van_ban(nhan: str, cac_doan: list) -> str:
    """'Nghị định 238/2025/NĐ-CP' - lấy từ nhãn nếu nhãn mang số hiệu, không thì từ đầu văn bản."""
    khop = MAU_NHAN_SO_HIEU.match(nhan)
    if khop:
        loai, so, nam, ky_hieu = khop.groups()
        return f"{loai.replace('-', ' ')} {so}/{nam}/{ky_hieu}"
    dau = cac_doan[0][1].page_content if cac_doan else ""
    dau = dau.split("Căn cứ")[0]
    khop = MAU_SO_HIEU_DAY_DU.search(dau)
    if khop:
        so, nam, ky_hieu = khop.groups()
    elif khop := re.match(r"^(\d{1,4})_(\d{4})_([A-Z]{2,3}-[A-Z]+)", nhan):
        # Nhãn kiểu '02_2026_TT-BGDDT' (tên tệp viết không dấu).
        so, nam, ky_hieu = khop.groups()
        ky_hieu = ky_hieu.replace("BGDDT", "BGDĐT").replace("ND-", "NĐ-")
    elif (khop := re.match(r"^(\d{1,4})-(bgddt|ndcp)", nhan, re.IGNORECASE)) and (
        nam_dau := re.search(r"/\s*(\d{4})\s*/", dau)
    ):
        # Bản PDF ký số để trống chỗ số ('Số /2025/TT-BGDĐT'), số nằm ở tên tệp.
        so, nam = khop.group(1), nam_dau.group(1)
        ky_hieu = "TT-BGDĐT" if khop.group(2).lower() == "bgddt" else "NĐ-CP"
    else:
        return ""
    ky_hieu = re.sub(r"\s+", "", ky_hieu)
    loai = next((ten for kh, ten in LOAI_THEO_KY_HIEU if kh in ky_hieu), "Văn bản")
    # Tiêu đề in hoa ở đầu văn bản chắc hơn ký hiệu (QH dùng cho cả luật lẫn nghị quyết).
    for hoa, ten in (("NGHỊ QUYẾT", "Nghị quyết"), ("THÔNG TƯ", "Thông tư"),
                     ("NGHỊ ĐỊNH", "Nghị định"), ("QUYẾT ĐỊNH", "Quyết định"),
                     ("LUẬT", "Luật")):
        if hoa in dau:
            loai = ten
            break
    return f"{loai} {so}/{nam}/{ky_hieu}"


# ------------------------------------------------------------------ kiểm câu hỏi
def _tu(van_ban: str) -> list[str]:
    van_ban = unicodedata.normalize("NFC", van_ban.lower())
    return re.findall(r"\w+", van_ban)


def chuoi_chep_dai_nhat(cau_hoi: str, doan: str) -> int:
    """Số chữ liền nhau dài nhất câu hỏi chép nguyên từ đoạn văn."""
    a, b = _tu(cau_hoi), _tu(doan)
    if not a or not b:
        return 0
    vi_tri: dict[str, list[int]] = {}
    for j, w in enumerate(b):
        vi_tri.setdefault(w, []).append(j)
    dai_nhat = 0
    for i in range(len(a)):
        for j in vi_tri.get(a[i], []):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            dai_nhat = max(dai_nhat, k)
    return dai_nhat


def don_cau_tra_ve(van_ban: str) -> str:
    van_ban = van_ban.strip().strip('"“”').strip()
    van_ban = re.sub(r"^(câu hỏi|question)\s*:\s*", "", van_ban, flags=re.IGNORECASE)
    dong = [d.strip() for d in van_ban.splitlines() if d.strip()]
    # Mô hình hay thêm lời dẫn; lấy dòng đầu tiên có dấu hỏi.
    for d in dong:
        if "?" in d:
            return d[: d.rindex("?") + 1].strip().strip('*"“” ')
    return dong[0] if dong else ""


def ly_do_loai(cau_hoi: str, nhom: str, doan: str, so_hieu: str) -> list[str]:
    ly_do = []
    thap = cau_hoi.lower()
    so_tu = len(_tu(cau_hoi))
    if not cau_hoi.endswith("?"):
        ly_do.append("không kết thúc bằng ?")
    if so_tu < 6 or so_tu > 45:
        ly_do.append(f"độ dài {so_tu} chữ")
    if any(c in thap for c in CUM_TU_THAM_CHIEU) or MAU_TRO_NGU_CANH.search(cau_hoi):
        ly_do.append("trỏ về đoạn trích ('này', 'đó', 'nêu trên') - phải gọi đúng tên sự việc")
    if nhom == NHOM_NGOAI:
        if any(c in thap for c in CHU_GIAO_DUC):
            ly_do.append("câu ngoài phạm vi lại dính giáo dục")
        return ly_do
    if nhom == NHOM_SO_HIEU:
        so = so_hieu.split(" ", 2)[-1].split("/")
        if so_hieu and not re.search(rf"\b{re.escape(so[0])}\s*/\s*{so[1]}\b", cau_hoi):
            ly_do.append("thiếu số hiệu")
    elif MAU_SO_HIEU.search(cau_hoi) or MAU_NEU_VAN_BAN.search(cau_hoi):
        ly_do.append("nêu số hiệu văn bản")
    if nhom != NHOM_SO_HIEU and MAU_DIEU_KHOAN.search(cau_hoi):
        ly_do.append("nêu số điều/khoản")
    chep = chuoi_chep_dai_nhat(cau_hoi, doan)
    # Câu số hiệu bắt buộc chép số hiệu và tên loại văn bản - nới thêm 4 chữ.
    gioi_han = CHUOI_CHEP_TOI_DA + (4 if nhom == NHOM_SO_HIEU else 0)
    if chep > gioi_han:
        ly_do.append(f"chép nguyên {chep} chữ liền")
    return ly_do


# ------------------------------------------------------------------ gọi Gemma
def goi_mo_hinh(he_thong: str, nguoi_dung: str, hat_giong: int) -> str:
    phan_hoi = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": MO_HINH,
            "messages": [
                {"role": "system", "content": he_thong},
                {"role": "user", "content": nguoi_dung},
            ],
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.8, "top_p": 0.95, "seed": hat_giong,
                        "num_ctx": 4096, "num_predict": 120},
        },
        timeout=900,
    )
    phan_hoi.raise_for_status()
    return phan_hoi.json()["message"]["content"]


HE_THONG = (
    "Bạn giúp xây dựng bộ câu hỏi kiểm thử cho một chatbot tra cứu tài liệu "
    "tiếng Việt. Bạn chỉ trả về đúng MỘT câu hỏi tiếng Việt, không giải thích, "
    "không đánh số, không ngoặc kép."
)


def loi_nhac(nhom: str, doan: str, so_hieu: str, vai: str, ly_do_truoc: list[str]) -> str:
    if nhom == NHOM_NGOAI:
        nhac = (
            f"Hãy viết một câu hỏi tự nhiên mà một người dân bình thường "
            f"có thể hỏi về chủ đề: {doan}.\n"
            "Yêu cầu: câu hỏi KHÔNG liên quan tới giáo dục, trường học, học sinh, "
            "giáo viên; dài 10-30 chữ; kết thúc bằng dấu ?"
        )
    else:
        quy_tac = [
            f"Đặt mình vào vai {vai} cần tra cứu. Đọc đoạn trích dưới đây rồi viết "
            "MỘT câu hỏi mà đoạn trích trả lời được.",
            "- Câu hỏi phải tự đứng được: người đọc không thấy đoạn trích, nên "
            "không được viết 'đoạn trích', 'quy định này', 'hệ thống này', 'nêu "
            "trên'; hãy gọi đúng tên sự việc (vd 'hệ thống giáo dục quốc dân', "
            "'việc dạy thêm, học thêm').",
            "- Diễn đạt bằng lời lẽ đời thường của bạn, KHÔNG chép nguyên cụm dài "
            "từ đoạn trích.",
            "- Dài 10-30 chữ, kết thúc bằng dấu ?",
        ]
        if nhom == NHOM_SO_HIEU and so_hieu:
            quy_tac.append(f"- Câu hỏi PHẢI nêu rõ văn bản: {so_hieu}.")
        elif nhom.startswith("phap_luat"):
            quy_tac.append("- KHÔNG nêu số hiệu, tên văn bản hay số điều, khoản: "
                           "người hỏi không biết văn bản nào quy định.")
        else:
            quy_tac.append("- KHÔNG nêu tên tệp hay tên tài liệu.")
        nhac = "\n".join(quy_tac) + f"\n\nĐOẠN TRÍCH:\n{doan}"
    if ly_do_truoc:
        nhac += "\n\nLần trước câu hỏi bị loại vì: " + "; ".join(ly_do_truoc) + ". Hãy sửa."
    return nhac


# ------------------------------------------------------------------ dây chuyền
def lap_ke_hoach(bo_cu: list[dict], theo_tep: dict) -> list[dict]:
    """
    Với mỗi câu của bộ cũ, chọn trước tài liệu + đoạn sẽ đưa cho Gemma. Làm hết
    bằng code và hạt giống cố định, trước khi gọi mô hình lần nào.
    """
    rng = random.Random(HAT_GIONG)
    da_dung: dict[str, set] = {}
    # Kho thay thế: các văn bản pháp luật giáo dục mà bộ cũ đã hỏi tới (thư mục
    # van_ban_quy_pham còn lẫn thông tư ngành khác, vd quản lý năng lượng).
    van_ban_qp = sorted({
        t
        for muc in bo_cu if muc.get("nhom", "").startswith("phap_luat")
        for nhan in muc.get("nguon_mong_doi") or []
        for t in tep_cua_nhan(theo_tep, nhan)
    })
    ke_hoach = []
    dem_ngoai = 0
    for stt, muc in enumerate(bo_cu):
        nhom = muc.get("nhom", "")
        moi = {"stt": stt, "nhom": nhom, "tap": muc.get("tap")}
        if nhom == NHOM_NGOAI:
            moi["chu_de"] = LINH_VUC_NGOAI[dem_ngoai % len(LINH_VUC_NGOAI)]
            dem_ngoai += 1
            ke_hoach.append(moi)
            continue
        nhan = list(muc.get("nguon_mong_doi") or [])
        tep = tep_cua_nhan(theo_tep, nhan[0]) if nhan else []
        if not tep:
            # Tài liệu của nhãn cũ không còn trong kho (video, slide đã gỡ):
            # thay bằng một văn bản quy phạm bốc ngẫu nhiên.
            ten = rng.choice(van_ban_qp)
            moi.update(nhom=NHOM_NOI_DUNG, thay_the_cho=nhan, nhan=[ten])
            tep = [ten]
        else:
            moi["nhan"] = nhan
        ten_tep = rng.choice(tep)
        cac_doan = theo_tep[ten_tep]
        ung_vien = doan_ung_vien(cac_doan)
        con_lai = [x for x in ung_vien if x[1] not in da_dung.get(ten_tep, set())]
        i, ma, doc = rng.choice(con_lai or ung_vien)
        da_dung.setdefault(ten_tep, set()).add(ma)
        moi.update(
            tep=ten_tep, ma_doan=ma, chi_so_doan=i, trang=doc.metadata.get("page"),
            doan=doc.page_content[:SO_KY_TU_DOAN],
            so_hieu=so_hieu_van_ban(nhan[0] if nhan and "thay_the_cho" not in moi else ten_tep,
                                    cac_doan),
        )
        ke_hoach.append(moi)
    return ke_hoach


def sinh_mot_cau(muc: dict, so_lan_thu: int = SO_LAN_THU, lech_hat: int = 0,
                 cau_cam: frozenset = frozenset()) -> dict:
    """lech_hat/cau_cam dùng khi --thu-lai: hạt giống mới, không trùng câu đã có."""
    nhom = muc["nhom"]
    vai = ("một người dân" if nhom == NHOM_NGOAI
           else VAI_NGUOI_HOI[muc["stt"] % len(VAI_NGUOI_HOI)])
    doan = muc.get("doan") or muc.get("chu_de", "")
    so_hieu = muc.get("so_hieu", "")
    ly_do_truoc: list[str] = []
    cac_lan = []
    tot_nhat = None
    for lan in range(so_lan_thu):
        bat_dau = time.perf_counter()
        tho = goi_mo_hinh(HE_THONG, loi_nhac(nhom, doan, so_hieu, vai, ly_do_truoc),
                          HAT_GIONG + lech_hat + muc["stt"] * 10 + lan)
        cau = don_cau_tra_ve(tho)
        ly_do = ly_do_loai(cau, nhom, doan, so_hieu)
        if cau in cau_cam:
            ly_do.append("trùng một câu đã có trong bộ")
        cac_lan.append({"cau_hoi": cau, "ly_do_loai": ly_do,
                        "giay": round(time.perf_counter() - bat_dau, 1)})
        if tot_nhat is None or len(ly_do) < len(tot_nhat[1]):
            tot_nhat = (cau, ly_do)
        if not ly_do:
            break
        ly_do_truoc = ly_do
    cau, ly_do = tot_nhat
    return {
        **{k: v for k, v in muc.items() if k != "chu_de" or nhom == NHOM_NGOAI},
        "vai": vai, "cau_hoi": cau, "con_loi": ly_do, "so_lan_thu": len(cac_lan),
        "cac_lan": cac_lan,
        "chuoi_chep_dai_nhat": chuoi_chep_dai_nhat(cau, doan) if nhom != NHOM_NGOAI else 0,
        "mo_hinh": MO_HINH,
    }


def doc_nhat_ky() -> dict[int, dict]:
    if not os.path.exists(DUONG_DAN_NHAT_KY):
        return {}
    xong = {}
    with open(DUONG_DAN_NHAT_KY, encoding="utf-8") as f:
        for dong in f:
            if dong.strip():
                ban_ghi = json.loads(dong)
                xong[ban_ghi["stt"]] = ban_ghi
    return xong


def ghi_bo_moi(bo_cu_day_du: dict, ket_qua: list[dict]) -> None:
    cau_hoi = []
    for r in sorted(ket_qua, key=lambda x: x["stt"]):
        muc = {"cau_hoi": r["cau_hoi"]}
        if r["nhom"] == NHOM_NGOAI:
            muc["mong_doi_tu_choi"] = True
        else:
            muc["nguon_mong_doi"] = r["nhan"]
        muc.update(nhom=r["nhom"], tap=r["tap"], sinh_boi=r["mo_hinh"])
        if r["con_loi"]:
            # Sau cả hai lượt vẫn vi phạm quy tắc - người rà quyết định giữ, sửa hay bỏ.
            muc["can_ra_soat"] = r["con_loi"]
        cau_hoi.append(muc)
    mo_ta = (
        f"Bộ câu hỏi sinh lại bằng {MO_HINH} (sinh_cau_hoi_gemma.py) - mô hình độc "
        "lập với Qwen (mô hình trả lời của chatbot) và Claude (người soạn bộ cũ). "
        "Giữ khung bộ cũ: cùng nhóm, tập dev/test, tài liệu được hỏi; mỗi câu được "
        "đặt từ một đoạn văn bản do code chọn ngẫu nhiên trong tài liệu nhãn, nên "
        "nhãn đúng theo cách dựng. Đoạn gốc của từng câu nằm trong "
        "nhat_ky_sinh_cau_hoi_gemma.jsonl. " + bo_cu_day_du.get("mo_ta", "")
    )
    with open(DUONG_DAN_BO_MOI, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"mo_ta": mo_ta, "cau_hoi": cau_hoi}, f, ensure_ascii=False, indent=2)
        f.write("\n")


def thu_lai(ke_hoach: list[dict], xong: dict[int, dict], bo_cu_day_du: dict) -> int:
    """
    Lượt hai cho câu còn vi phạm quy tắc hoặc trùng câu khác: cùng đoạn văn,
    hạt giống mới, 6 lần thử. Câu nào vẫn hỏng thì giữ bản ít lỗi nhất và để
    nguyên cờ con_loi cho người rà.
    """
    da_gap: set[str] = set()
    can_lam = []
    for stt in sorted(xong):
        r = xong[stt]
        if r["con_loi"] or r["cau_hoi"] in da_gap:
            can_lam.append(stt)
        da_gap.add(r["cau_hoi"])
    print(f"Đặt lại {len(can_lam)} câu: {can_lam}", flush=True)
    theo_stt = {m["stt"]: m for m in ke_hoach}
    for stt in can_lam:
        cau_cam = frozenset(r["cau_hoi"] for s, r in xong.items() if s != stt)
        moi = sinh_mot_cau(theo_stt[stt], so_lan_thu=6, lech_hat=100_000, cau_cam=cau_cam)
        cu = xong[stt]
        if len(moi["con_loi"]) <= len(cu["con_loi"]) or cu["cau_hoi"] in cau_cam:
            moi["lan_dat_lai"] = {"cau_cu": cu["cau_hoi"], "loi_cu": cu["con_loi"]}
            xong[stt] = moi
        dau = "!" if xong[stt]["con_loi"] else " "
        print(f"[{stt:>3}] {dau} {xong[stt]['cau_hoi'][:100]}", flush=True)
    tam = DUONG_DAN_NHAT_KY + ".tmp"
    with open(tam, "w", encoding="utf-8", newline="\n") as f:
        for stt in sorted(xong):
            f.write(json.dumps(xong[stt], ensure_ascii=False) + "\n")
    os.replace(tam, DUONG_DAN_NHAT_KY)
    ket_qua = [xong[m["stt"]] for m in ke_hoach if m["stt"] in xong]
    ghi_bo_moi(bo_cu_day_du, ket_qua)
    print(f"\nCòn {sum(1 for r in ket_qua if r['con_loi'])} câu vi phạm, "
          f"{len(ket_qua) - len({r['cau_hoi'] for r in ket_qua})} câu trùng.")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--so", type=int, default=None, help="chỉ sinh N câu đầu")
    parser.add_argument("--thu-lai", action="store_true",
                        help="đặt lại các câu còn lỗi hoặc trùng nhau trong nhật ký")
    tham_so = parser.parse_args()

    with open(DUONG_DAN_BO_CU, encoding="utf-8") as f:
        bo_cu_day_du = json.load(f)
    print("Đang đọc docstore FAISS...", flush=True)
    theo_tep = nap_doan_theo_tep()
    ke_hoach = lap_ke_hoach(bo_cu_day_du["cau_hoi"], theo_tep)
    if tham_so.so:
        ke_hoach = ke_hoach[: tham_so.so]

    xong = doc_nhat_ky()
    if tham_so.thu_lai:
        return thu_lai(ke_hoach, xong, bo_cu_day_du)
    print(f"{len(ke_hoach)} câu, đã có {len(xong)} trong nhật ký, mô hình {MO_HINH}", flush=True)
    bat_dau = time.perf_counter()
    lam_moi = 0
    with open(DUONG_DAN_NHAT_KY, "a", encoding="utf-8", newline="\n") as nhat_ky:
        for muc in ke_hoach:
            if muc["stt"] in xong:
                continue
            for lan_loi in range(3):
                try:
                    ban_ghi = sinh_mot_cau(muc)
                    break
                except requests.RequestException as loi:
                    print(f"  lỗi Ollama ({loi}), thử lại sau 30 giây", flush=True)
                    time.sleep(30)
            else:
                print(f"Bỏ dở ở câu {muc['stt']}: Ollama lỗi liên tục.", flush=True)
                return 1
            nhat_ky.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")
            nhat_ky.flush()
            xong[muc["stt"]] = ban_ghi
            lam_moi += 1
            tb = (time.perf_counter() - bat_dau) / lam_moi
            con = sum(1 for m in ke_hoach if m["stt"] not in xong)
            dau = "!" if ban_ghi["con_loi"] else " "
            print(f"[{muc['stt']:>3}] {dau} {ban_ghi['nhom'][:18]:<18} "
                  f"{ban_ghi['so_lan_thu']} lần · {ban_ghi['cau_hoi'][:90]}"
                  f"  (TB {tb:.0f}s/câu, còn ~{con * tb / 3600:.1f} giờ)", flush=True)

    ket_qua = [xong[m["stt"]] for m in ke_hoach if m["stt"] in xong]
    ghi_bo_moi(bo_cu_day_du, ket_qua)
    loi = sum(1 for r in ket_qua if r["con_loi"])
    print(f"\nXong {len(ket_qua)} câu -> {DUONG_DAN_BO_MOI}")
    print(f"{loi} câu vẫn vi phạm quy tắc sau {SO_LAN_THU} lần thử (cần xem tay, "
          f"trường con_loi trong nhật ký).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
