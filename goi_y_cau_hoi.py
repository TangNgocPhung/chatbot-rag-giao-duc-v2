"""Sinh câu hỏi gợi ý cho giao diện: gợi ý mở đầu và gợi ý hỏi tiếp.

Hai chỗ cần gợi ý: màn hình chào (ngoài bốn thẻ chủ đề cố định) và cuối mỗi câu
trả lời. Màn hình chào mặc định là bộ 17 câu viết tay chia bốn nhóm chủ đề, lần
nào mở cũng như nhau. Không dùng bộ tĩnh (RAG_GOI_Y_MO_DAU=metadata) thì màn
hình chào, cũng như hàng hỏi tiếp, dựng câu từ metadata văn bản - số hiệu, nhãn
hiệu lực, quan hệ thay thế - đi qua một cây quyết định viết tay
(_nhanh_theo_nguon). Không chỗ nào gọi thêm mô hình: một lượt sinh nữa trên CPU
là thêm hàng chục giây chỉ để có một hàng nút bấm, mà câu do mô hình tự nghĩ
lại hay hỏi sang thứ kho không có tài liệu để trả lời.
"""

from __future__ import annotations

import os
import random
import re
import unicodedata
from itertools import zip_longest

import hieu_luc_bo_sung


SO_GOI_Y_MO_DAU = 6
SO_GOI_Y_TIEP = 3

# Hai cách dựng gợi ý cho màn hình chào, chọn bằng RAG_GOI_Y_MO_DAU.
CHE_DO_TINH = "tinh"
CHE_DO_METADATA = "metadata"
CAC_CHE_DO = (CHE_DO_TINH, CHE_DO_METADATA)

# Câu hỏi mở đầu viết tay theo bốn nhóm chủ đề trên màn hình chào. Mỗi câu đều
# có văn bản tương ứng trong kho để bấm vào là ra được câu trả lời có nguồn.
NHOM_GOI_Y_CHU_DE = (
    ("Mầm non & phổ thông", (
        "Chương trình giáo dục phổ thông 2018 đặt ra những yêu cầu nào về phẩm chất và năng lực?",
        "Việc đánh giá học sinh tiểu học được thực hiện theo những hình thức nào?",
        "Kế hoạch bài dạy theo Công văn 5512 gồm những phần nào?",
        "Ma trận và bản đặc tả đề kiểm tra được xây dựng theo các bước nào?",
        "Quy định về dạy thêm, học thêm hiện nay như thế nào?",
        "Học sinh phổ thông được miễn học phí và sách giáo khoa trong những trường hợp nào?",
    )),
    ("Giáo dục nghề nghiệp", (
        "Khung trình độ quốc gia Việt Nam gồm những bậc trình độ nào?",
        "Khung cơ cấu hệ thống giáo dục quốc dân gồm những cấp học và trình độ nào?",
        "Cơ sở giáo dục nghề nghiệp được tự chủ những nội dung gì?",
    )),
    ("Giáo dục đại học", (
        "Quy định về tự chủ của cơ sở giáo dục đại học gồm những nội dung nào?",
        "Việc ứng dụng công nghệ trong giáo dục đại học và giáo dục nghề nghiệp được quy định thế nào?",
        "Quỹ Học bổng Quốc gia được tổ chức, quản lý và sử dụng ra sao?",
        "Chương trình xây dựng nguồn tài nguyên giáo dục mở có những mục tiêu nào?",
    )),
    ("Chính sách và đội ngũ nhà giáo", (
        "Luật Nhà giáo được hướng dẫn thi hành với những nội dung chính nào?",
        "Nhà giáo và cán bộ quản lý giáo dục được hưởng phụ cấp ưu đãi theo nghề thế nào?",
        "Lộ trình nâng trình độ chuẩn được đào tạo của giáo viên mầm non, tiểu học, trung học cơ sở ra sao?",
        "Sở Giáo dục và Đào tạo có những chức năng, nhiệm vụ và quyền hạn nào?",
    )),
)
GOI_Y_CHU_DE = tuple(cau for _, cac_cau in NHOM_GOI_Y_CHU_DE for cau in cac_cau)
# Đủ để một lần gọi API lấy trọn bộ câu tĩnh.
SO_GOI_Y_TOI_DA = len(GOI_Y_CHU_DE)

# Tên tệp bắt đầu bằng một trong các từ này thì đọc lên đã thành tên văn bản,
# chỉ cần ghép thêm phần hỏi.
_LOAI_VAN_BAN_MO_DAU = (
    "thông tư", "nghị định", "nghị quyết", "quyết định", "công văn", "công điện",
    "chỉ thị", "thông báo", "luật", "kế hoạch", "đề án", "hướng dẫn", "quy định",
    "quy chế", "phê duyệt", "sửa đổi",
)

# "...về các công nghệ ch--caa14599": cổng văn bản cắt tên dài rồi dán mã băm.
_MA_BAM_CUOI = re.compile(r"-{2}[0-9a-f]{6,}$")
# Số hiệu trong tên tệp tải về bị đổi dấu "/" thành "_": "86_2021_NĐ-CP".
_SO_HIEU_GACH_DUOI = re.compile(r"(\d)_(\d{4})_([A-Za-zĐđ])")
_KY_TU_CO_DAU = re.compile(
    "[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]"
)
_DIEU_DAU = re.compile(r"^\s*(Điều\s+\d+)", re.IGNORECASE)
_KHONG_PHAI_CHU = re.compile(r"\W+", re.UNICODE)

_DO_DAI_TIEU_DE_TOI_THIEU = 30
_SO_TU_TIEU_DE_TOI_THIEU = 5
_SO_DAU_TOI_THIEU = 3
# Tên văn bản dài 150 ký tự vẫn là tên hợp lệ, nhưng nhồi cả vào một nút gợi ý
# thì không ai đọc; kho còn thừa tên ngắn để chọn nên bỏ qua là rẻ nhất.
_DO_DAI_CAU_HOI_TOI_DA = 120


def _chuan_hoa(cau: str) -> str:
    """Dạng rút gọn chỉ để so trùng, không dùng để hiển thị."""
    return _KHONG_PHAI_CHU.sub(" ", str(cau or "").casefold()).strip()


def _loc_trung(cac_cau, da_co=(), gioi_han: int | None = None) -> list[str]:
    """Bỏ câu trùng nhau và câu trùng với những gì đã hỏi/đã có.

    Có gioi_han thì dừng ngay khi đủ số câu: ứng viên dựng từ cả kho dài hàng
    nghìn câu, mà câu nào cũng phải so với mọi câu đã giữ.
    """
    da_thay = [_chuan_hoa(cau) for cau in da_co if cau]
    ket_qua = []
    for cau in cac_cau:
        if gioi_han is not None and len(ket_qua) >= gioi_han:
            break
        khoa = _chuan_hoa(cau)
        if not khoa:
            continue
        # Bao nhau cũng coi là trùng: "Tóm tắt tệp A" và "Tóm tắt tệp A gồm gì"
        # đặt cạnh nhau chỉ làm loãng ba chỗ gợi ý ít ỏi.
        if any(khoa == cu or khoa in cu or cu in khoa for cu in da_thay):
            continue
        da_thay.append(khoa)
        ket_qua.append(str(cau).strip())
    return ket_qua


def _lam_sach_tieu_de(ten_file: str) -> str | None:
    """Đổi tên tệp thành cụm từ đọc được, trả None nếu tên chỉ là mã số.

    Kho có hai kiểu tên lẫn nhau: tên tải từ cổng văn bản ("Thông tư quy định về
    dạy thêm, học thêm.pdf") dùng làm gợi ý rất tốt, còn tên mã hóa
    ("5512_BGDDT-GDTrH_462988.doc", "PPCT-5.docx", "20-bgddt.pdf") thì không đọc
    lên thành câu hỏi được nên phải loại.
    """
    ten = os.path.splitext(str(ten_file or ""))[0].strip()
    ten = _SO_HIEU_GACH_DUOI.sub(r"\1/\2/\3", ten).replace("_", " ")
    khop_ma = _MA_BAM_CUOI.search(ten)
    if khop_ma:
        # Chữ cuối thường bị cắt dở ("...về các công nghệ ch") nên bỏ luôn.
        ten = ten[: khop_ma.start()].rstrip(" -")
        ten = ten.rsplit(" ", 1)[0]
    ten = re.sub(r"\s+", " ", ten).strip(" -.,;")
    if len(ten) < _DO_DAI_TIEU_DE_TOI_THIEU or len(ten.split()) < _SO_TU_TIEU_DE_TOI_THIEU:
        return None
    # Không có dấu tiếng Việt thì gần như chắc chắn là tên viết tắt, viết liền
    # ("PhanPhoi-ChuongTrinh-Tin4", "QUAN 10 - NOI DUNG GDKNCDS KHOI LOP 3-4-5").
    if len(_KY_TU_CO_DAU.findall(ten.casefold())) < _SO_DAU_TOI_THIEU:
        return None
    return ten


def _cau_hoi_tu_tieu_de(tieu_de: str) -> str:
    if tieu_de.casefold().startswith(_LOAI_VAN_BAN_MO_DAU):
        return f"{tieu_de} có những nội dung chính nào?"
    return f"Nội dung chính của tài liệu \"{tieu_de}\" là gì?"


def _ten_goi(nguon: dict) -> str:
    """Cách gọi nguồn trong câu gợi ý: ưu tiên số hiệu, sau đó tới tên tài liệu."""
    van_ban = nguon.get("van_ban") or {}
    if van_ban.get("so_hieu"):
        return f"{van_ban.get('loai') or 'Văn bản'} {van_ban['so_hieu']}"
    ten_file = nguon.get("name") or ""
    return _lam_sach_tieu_de(ten_file) or str(ten_file) or "tài liệu này"


# ============================================================
# CÂY QUYẾT ĐỊNH: METADATA VĂN BẢN -> CÂU HỎI GỢI Ý
# ============================================================
# Cây viết tay theo luật, không học từ dữ liệu. Một nguồn đi từ gốc xuống, dừng
# ở nút đầu tiên khớp; mỗi lá là một khuôn câu hỏi. Mã hiệu lực do
# hieu_luc_bo_sung.nhan_hieu_luc chọn sẵn (mỗi nguồn đúng một mã), nên bốn nhánh
# hiệu lực loại trừ nhau.
#
#   nguồn
#   ├─ bị thay thế?                  -> Văn bản nào đã thay thế X?
#   ├─ bị sửa đổi (văn bản / đoạn)?  -> X đã được sửa đổi, bổ sung những nội dung nào?
#   ├─ chưa tới ngày hiệu lực?       -> X có hiệu lực từ ngày nào và áp dụng ra sao?
#   ├─ dự thảo?                      -> Đã có văn bản chính thức nào thay cho bản dự thảo X chưa?
#   ├─ trích đúng một Điều?          -> Điều n của X quy định chi tiết những gì?
#   ├─ thay thế văn bản khác?        -> X thay thế những văn bản nào?
#   └─ còn lại                       -> hỏi tiếp: không có câu riêng;
#                                       màn hình chào: X có những nội dung chính nào?
_NHANH_NOI_DUNG = "noi_dung_chinh"
# Các lá theo đúng thứ tự trên cây.
CAC_NHANH = (
    "bi_thay_the", "bi_sua_doi", "chua_hieu_luc", "du_thao", "trich_dieu",
    "thay_the_van_ban_khac", _NHANH_NOI_DUNG,
)


def _nhanh_theo_nguon(nguon: dict, ten: str) -> tuple[str, str] | None:
    """Đi cây quyết định cho một nguồn: (tên lá, câu hỏi), hoặc None khi nguồn
    không vướng gì để hỏi riêng.

    Vướng hiệu lực là thứ phải hỏi trước tiên - đọc tiếp một văn bản đã bị thay
    thế thì càng đọc càng sai. Hết chuyện hiệu lực mới tới đọc sâu vào Điều đang
    được trích, rồi mới tới quan hệ với các văn bản cũ.
    """
    ma_hieu_luc = (nguon.get("validity") or {}).get("code")
    if ma_hieu_luc == "bi_thay_the":
        return "bi_thay_the", f"Văn bản nào đã thay thế {ten}?"
    if ma_hieu_luc in {"bi_sua_doi", "doan_sua_doi"}:
        return "bi_sua_doi", f"{ten} đã được sửa đổi, bổ sung những nội dung nào?"
    if ma_hieu_luc == "chua_hieu_luc":
        return "chua_hieu_luc", f"{ten} có hiệu lực từ ngày nào và áp dụng ra sao?"
    if ma_hieu_luc == "du_thao":
        return "du_thao", (
            f"Đã có văn bản chính thức nào ban hành thay cho bản dự thảo {ten} chưa?"
        )
    khop_dieu = _DIEU_DAU.match(str(nguon.get("article") or ""))
    if khop_dieu:
        return "trich_dieu", f"{khop_dieu.group(1)} của {ten} quy định chi tiết những gì?"
    if (nguon.get("van_ban") or {}).get("thay_the"):
        return "thay_the_van_ban_khac", f"{ten} thay thế những văn bản nào?"
    return None


def _cau_hoi_theo_nguon(nguon: dict, ten: str) -> str | None:
    """Câu hỏi tiếp cho đúng nguồn này - lá của cây, bỏ tên lá."""
    nhanh = _nhanh_theo_nguon(nguon, ten)
    return nhanh[1] if nhanh else None


def _nhanh_theo_van_ban(ten_file: str, muc_ho_so=None, muc_thoi_gian=None) -> tuple[str, str] | None:
    """Đưa một văn bản trong kho qua cùng cây quyết định với gợi ý hỏi tiếp.

    Dựng từ hồ sơ một "nguồn" cấp văn bản cùng dạng rag_service._sources trả
    về; nhãn hiệu lực lấy đúng hàm gắn nhãn cho chip nguồn. Ở cấp văn bản
    không có Điều nào đang được trích, nên văn bản không vướng gì rơi xuống lá
    "nội dung chính". Không có số hiệu mà tên tệp chỉ là mã số thì bỏ: không
    gọi được bằng cái tên nào người đọc hiểu.
    """
    so_hieu = getattr(muc_ho_so, "so_hieu", None)
    tieu_de = _lam_sach_tieu_de(ten_file)
    if not so_hieu and not tieu_de:
        return None
    nguon = {
        "name": ten_file,
        "van_ban": {
            "so_hieu": so_hieu,
            "loai": muc_ho_so.loai,
            "thay_the": list(muc_ho_so.thay_the or []),
        } if so_hieu else None,
        "validity": hieu_luc_bo_sung.nhan_hieu_luc(muc_ho_so, muc_thoi_gian),
    }
    ten = _ten_goi(nguon)
    # Tên tệp tải từ cổng văn bản nói rõ văn bản về gì hơn số hiệu, nên lá
    # "nội dung chính" ưu tiên tên đó.
    return _nhanh_theo_nguon(nguon, ten) or (_NHANH_NOI_DUNG, _cau_hoi_tu_tieu_de(tieu_de or ten))


# ============================================================
# GỢI Ý MÀN HÌNH CHÀO
# ============================================================
def _chan_so_luong(so_luong) -> int:
    try:
        so_luong = int(so_luong)
    except (TypeError, ValueError):
        so_luong = SO_GOI_Y_MO_DAU
    return max(1, min(so_luong, SO_GOI_Y_TOI_DA))


def che_do_goi_y_mo_dau(che_do: str | None = None) -> str:
    """Chế độ gợi ý màn hình chào: theo tham số, không có thì theo biến môi
    trường RAG_GOI_Y_MO_DAU; giá trị lạ quay về bộ câu tĩnh mặc định."""
    gia_tri = str(che_do or os.getenv("RAG_GOI_Y_MO_DAU") or CHE_DO_TINH).strip().casefold()
    return gia_tri if gia_tri in CAC_CHE_DO else CHE_DO_TINH


def nhom_goi_y_tinh() -> list[dict]:
    """Bộ câu tĩnh giữ nguyên bốn nhóm, để giao diện vẽ theo chủ đề."""
    return [
        {"chu_de": chu_de, "cau_hoi": list(cac_cau)}
        for chu_de, cac_cau in NHOM_GOI_Y_CHU_DE
    ]


def goi_y_tinh(so_luong: int | None = None) -> list[str]:
    """Bộ câu tĩnh, thứ tự cố định: lần lượt mỗi nhóm một câu.

    Xen kẽ các nhóm để khi chỉ cần vài câu (lời từ chối chỉ chừa ba chỗ) vẫn
    trải đủ các chủ đề thay vì dồn cả vào nhóm đầu.
    """
    xen_ke = [
        cau
        for vong in zip_longest(*(cac_cau for _, cac_cau in NHOM_GOI_Y_CHU_DE))
        for cau in vong if cau
    ]
    return xen_ke if so_luong is None else xen_ke[:_chan_so_luong(so_luong)]


def goi_y_tu_kho(ho_so=None, tinh_trang=None, bo_ngau_nhien=None, gioi_han: int | None = None) -> list[str]:
    """Câu hỏi dựng từ metadata văn bản trong kho qua cây quyết định - gợi ý
    nào cũng có nguồn.

    Lấy xen kẽ giữa các lá theo thứ tự trên cây: để nguyên thì lá "nội dung
    chính" chiếm gần hết kho, một mẻ sáu câu toàn "X có những nội dung chính
    nào?" và mất hẳn loại câu hỏi về hiệu lực. Có bo_ngau_nhien thì đảo thứ tự
    trong từng lá để mỗi mẻ một khác.
    """
    theo_nhanh: dict[str, list[str]] = {}
    for ten_file, muc in (ho_so or {}).items():
        ket_qua = _nhanh_theo_van_ban(ten_file, muc, (tinh_trang or {}).get(ten_file))
        if ket_qua and len(ket_qua[1]) <= _DO_DAI_CAU_HOI_TOI_DA:
            theo_nhanh.setdefault(ket_qua[0], []).append(ket_qua[1])
    cac_nhanh = [theo_nhanh[nhanh] for nhanh in CAC_NHANH if nhanh in theo_nhanh]
    if bo_ngau_nhien is not None:
        for cac_cau in cac_nhanh:
            bo_ngau_nhien.shuffle(cac_cau)
    xen_ke = (cau for vong in zip_longest(*cac_nhanh) for cau in vong if cau)
    return _loc_trung(xen_ke, gioi_han=gioi_han)


def goi_y_mo_dau(
    ho_so=None,
    so_luong: int = SO_GOI_Y_MO_DAU,
    bo_ngau_nhien=None,
    che_do: str | None = None,
    tinh_trang=None,
) -> list[str]:
    """Gợi ý cho màn hình chào.

    Mặc định là bộ câu tĩnh, lần nào gọi cũng như nhau. Chế độ "metadata" dựng
    câu từ hồ sơ văn bản trong kho qua cây quyết định và đổi mẻ mỗi lần gọi;
    kho có ít văn bản dùng được quá thì bù bằng câu tĩnh để hàng gợi ý không
    bao giờ trống.
    """
    so_luong = _chan_so_luong(so_luong)
    if che_do_goi_y_mo_dau(che_do) == CHE_DO_TINH:
        return goi_y_tinh(so_luong)
    tu_kho = goi_y_tu_kho(ho_so, tinh_trang, bo_ngau_nhien or random, gioi_han=so_luong)
    return _loc_trung(tu_kho + goi_y_tinh(), gioi_han=so_luong)


# Cụm từ rút từ câu trả lời mà đem đi hỏi tiếp thì vô nghĩa: lời dẫn, nhãn vị
# trí, câu từ chối. Chỉ cần mở đầu bằng một trong các chữ này là bỏ.
_CUM_BO_QUA = (
    "tôi", "theo", "trong", "tuy nhiên", "ngoài ra", "như vậy", "kết luận", "lưu ý",
    "tóm lại", "cụ thể", "nguồn", "evidence", "trang", "slide", "sheet", "phút",
    "điều", "khoản", "điểm", "chương", "mục", "bảng", "tài liệu", "tệp", "nội dung",
    "câu trả lời", "ví dụ", "đây", "đó", "này", "các", "những", "một", "có", "không",
    "phần", "ý chính",
)
_IN_DAM = re.compile(r"\*\*([^*\n]{3,60})\*\*")
_DAU_MUC = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+([^:\n]{3,50}):", re.MULTILINE)
_TRICH_DAN = re.compile(r"\[(\d{1,2})\]")
# "ICT (Tin học ứng dụng)": viết tắt rồi mở ngoặc giải nghĩa - gần như chắc chắn
# là thuật ngữ chính của câu trả lời.
_VIET_TAT_GIAI_NGHIA = re.compile(r"\b[A-ZĐ]{2,6}\s*\(([^()\n]{3,40})\)")
_TRONG_NGOAC_KEP = re.compile(r"[\"“]([^\"”\n]{6,50})[\"”]")
# Tên riêng hay gặp trong câu trả lời nhưng hỏi tiếp về nó thì chẳng ai cần.
_TEN_RIENG_CHUNG = {
    "việt nam", "nhà xuất bản", "giáo dục việt nam", "bộ giáo dục", "chính phủ",
    "quốc hội", "thủ tướng", "thủ tướng chính phủ", "đào tạo", "giáo dục và đào tạo",
}
# Chữ hỏi và chữ đệm: bỏ đi thì phần còn lại của câu hỏi mới là chủ đề.
_TU_HOI = {
    "là", "gì", "như", "thế", "nào", "ra", "sao", "có", "không", "những", "các",
    "về", "của", "được", "và", "trong", "cho", "bao", "nhiêu", "môn", "hãy", "cho",
    "biết", "tôi", "em", "mình", "ở", "với", "thì", "này", "đó", "hỏi", "nêu",
}
_SO_Y_CHINH_TOI_DA = 3
_MA_HIEU_LUC_CAN_HOI = {"bi_thay_the", "bi_sua_doi", "doan_sua_doi", "chua_hieu_luc", "du_thao"}


def _la_cum_dung_duoc(cum: str, cau_hoi_chuan: str) -> bool:
    khoa = _chuan_hoa(cum)
    if len(khoa) < 3 or khoa.replace(" ", "").isdigit():
        return False
    if any(khoa == tu or khoa.startswith(tu + " ") for tu in _CUM_BO_QUA):
        return False
    # Cụm đã nằm nguyên trong câu vừa hỏi thì hỏi lại chỉ là hỏi vòng.
    return khoa not in cau_hoi_chuan


def _ten_rieng(van_ban: str) -> list[tuple[str, bool]]:
    """Các cụm 2-4 âm tiết viết hoa liền nhau ("Sơn Tinh", "Hùng Vương"), kèm
    cờ "có đứng giữa câu". Tự so chữ hoa bằng str thay vì lớp ký tự regex: dải
    À-Ỹ của Unicode lẫn cả chữ thường có dấu."""
    ket_qua = []
    cum: list[str] = []
    cum_o_dau_cau = True
    dau_cau = True  # đầu văn bản coi như đầu câu
    for khop in re.finditer(r"\w+|\n|[^\w\s]", van_ban):
        tu = khop.group(0)
        if len(tu) > 1 and tu[0].isupper() and tu[1:].islower():
            if not cum:
                cum_o_dau_cau = dau_cau
            cum.append(tu)
            dau_cau = False
            continue
        if 2 <= len(cum) <= 4:
            ket_qua.append((" ".join(cum), not cum_o_dau_cau))
        cum = []
        dau_cau = tu in {".", "!", "?", ":", "-", "*", "•", "\n"}
    if 2 <= len(cum) <= 4:
        ket_qua.append((" ".join(cum), not cum_o_dau_cau))
    return ket_qua


def rut_y_chinh(cau_tra_loi: str, cau_hoi: str = "") -> list[tuple[str, bool]]:
    """Rút vài cụm ý chính từ câu trả lời, kèm cờ "là tên riêng".

    Không gọi thêm mô hình: câu trả lời vốn đã in đậm thuật ngữ, mở gạch đầu dòng
    bằng "Tên ý: ..." và giữ nguyên tên riêng - đọc lại chính những dấu đó là đủ
    để gợi ý bám đúng nội dung vừa trả lời thay vì khuôn mẫu chung chung.
    """
    van_ban = str(cau_tra_loi or "")
    if not van_ban.strip():
        return []
    cau_hoi_chuan = _chuan_hoa(cau_hoi)
    ung_vien: list[tuple[str, bool]] = []

    for khop in _VIET_TAT_GIAI_NGHIA.finditer(van_ban):
        # "THPT (từ lớp 10 trở lên)" là chú thích phạm vi, không phải tên thuật
        # ngữ; tên giải nghĩa thật luôn viết hoa chữ đầu.
        if khop.group(1)[0].isupper():
            ung_vien.append((khop.group(1).strip(" :.,;"), False))
    for khop in _IN_DAM.finditer(van_ban):
        ung_vien.append((khop.group(1).strip(" :.,;"), False))
    for khop in _DAU_MUC.finditer(van_ban):
        ung_vien.append((khop.group(1).replace("**", "").strip(" :.,;"), False))
    for khop in _TRONG_NGOAC_KEP.finditer(van_ban):
        ung_vien.append((khop.group(1).strip(" :.,;"), False))

    # Tên riêng: đứng đầu câu thì chữ đầu viết hoa là chuyện ngữ pháp, nên cụm
    # chỉ đứng đầu câu phải xuất hiện ít nhất hai lần mới tính.
    dem: dict[str, int] = {}
    giua_cau: set[str] = set()
    for cum, o_giua in _ten_rieng(van_ban.replace("**", "")):
        dem[cum] = dem.get(cum, 0) + 1
        if o_giua:
            giua_cau.add(cum)
    for cum, so_lan in sorted(dem.items(), key=lambda muc: -muc[1]):
        if (cum in giua_cau or so_lan >= 2) and cum.casefold() not in _TEN_RIENG_CHUNG:
            ung_vien.append((cum, True))
    # Cụm nào chạm đúng chủ đề câu hỏi ("Tin học ứng dụng" khi hỏi về môn tin
    # học) được đưa lên trước; sort ổn định nên thứ tự còn lại giữ nguyên.
    chu_de = _cap_tu_chu_de(cau_hoi)
    if chu_de:
        ung_vien.sort(key=lambda muc: not (_cap_tu(muc[0]) & chu_de))

    ket_qua: list[tuple[str, bool]] = []
    da_thay: list[str] = []
    for cum, ten_rieng in ung_vien:
        cum = re.sub(r"\s+", " ", _TRICH_DAN.sub("", cum)).strip(" :.,;")
        if len(cum.split()) > 8 or not _la_cum_dung_duoc(cum, cau_hoi_chuan):
            continue
        khoa = _chuan_hoa(cum)
        if any(khoa == cu or khoa in cu or cu in khoa for cu in da_thay):
            continue
        da_thay.append(khoa)
        ket_qua.append((cum, ten_rieng))
        if len(ket_qua) >= _SO_Y_CHINH_TOI_DA:
            break
    return ket_qua


def _cau_hoi_tu_y_chinh(y_chinh: list[tuple[str, bool]]) -> list[str]:
    cau_hoi = []
    ten_rieng = [cum for cum, la_ten in y_chinh if la_ten]
    if len(ten_rieng) >= 2:
        cau_hoi.append(f"{ten_rieng[0]} và {ten_rieng[1]} có quan hệ với nhau thế nào?")
    mau = ("Nói rõ hơn về {}", "Tài liệu còn nói gì thêm về {}?", "Giải thích thêm về {}")
    for so, (cum, la_ten) in enumerate(y_chinh):
        # "Sính lễ" in đậm đầu dòng chỉ viết hoa vì đứng đầu dòng; đặt vào giữa
        # câu hỏi thì hạ xuống. Tên riêng và chữ viết tắt ("THPT") giữ nguyên.
        tu = cum.split()
        if not la_ten and len(tu) > 1 and tu[1].islower() and tu[0][1:].islower():
            cum = cum[0].lower() + cum[1:]
        cau_hoi.append(mau[so % len(mau)].format(cum))
    return cau_hoi


def _bo_dau(van_ban: str) -> str:
    van_ban = str(van_ban or "").casefold().replace("đ", "d")
    return "".join(
        ky_tu for ky_tu in unicodedata.normalize("NFD", van_ban)
        if unicodedata.category(ky_tu) != "Mn"
    )


def _cap_tu(van_ban: str) -> set[str]:
    """Các cặp âm tiết liền nhau, bỏ dấu - đủ để "tin học" khớp cả tên tệp
    "11-sgk-tin-hoc-11" mà không để một chữ "học" đứng riêng khớp mọi thứ."""
    tu = re.findall(r"[^\W_]+", _bo_dau(van_ban))
    return {f"{a} {b}" for a, b in zip(tu, tu[1:])}


def _cap_tu_chu_de(cau_hoi: str) -> set[str]:
    tu = [
        tu for tu in re.findall(r"[^\W_]+", str(cau_hoi or "").casefold())
        if tu not in _TU_HOI
    ]
    return _cap_tu(" ".join(tu)) if len(tu) >= 2 else set()


def _nguon_lien_quan(nguon: dict, chu_de: set[str]) -> bool:
    """Tên tài liệu có chạm chủ đề câu hỏi không. Chỉ xét tên chứ không xét đoạn
    trích: Điều 1 của một thông tư về thiết bị dạy học liệt kê đủ mọi môn, nên
    đoạn trích nào cũng "có nhắc tới" môn đang hỏi."""
    van_ban = nguon.get("van_ban") or {}
    ten = " ".join(filter(None, [
        nguon.get("name"), van_ban.get("trich_yeu"), van_ban.get("ten"),
    ]))
    return bool(_cap_tu(ten) & chu_de)


def _nguon_duoc_trich(cac_nguon: list[dict], cau_tra_loi: str) -> list[dict]:
    """Chỉ giữ nguồn mà câu trả lời thật sự trích [n].

    Truy hồi luôn kéo về vài đoạn "hơi liên quan"; hỏi tiếp về Điều 1 của một
    thông tư mà câu trả lời không hề dùng tới là gợi ý lạc đề. Câu trả lời không
    trích số nào (hoặc chưa có câu trả lời) thì giữ nguyên như cũ.
    """
    so_trich = {int(so) for so in _TRICH_DAN.findall(str(cau_tra_loi or ""))}
    duoc_trich = [
        nguon for so, nguon in enumerate(cac_nguon, 1)
        if so in so_trich
    ]
    return duoc_trich or ([] if so_trich else cac_nguon)


def goi_y_tiep_theo(
    cau_hoi: str,
    cac_nguon=None,
    so_luong: int = SO_GOI_Y_TIEP,
    cau_tra_loi: str = "",
) -> list[str]:
    """Gợi ý hỏi tiếp sau một câu trả lời có trích nguồn."""
    cac_nguon = [nguon for nguon in (cac_nguon or []) if isinstance(nguon, dict)]
    if cau_tra_loi:
        cac_nguon = _nguon_duoc_trich(cac_nguon, cau_tra_loi)
    # Vướng hiệu lực vẫn phải hỏi trước tiên; ngay sau đó là các ý chính của
    # chính câu vừa trả lời, rồi mới tới đọc sâu vào Điều được trích.
    canh_bao_hieu_luc = []
    ung_vien = []
    tu_nguon = []  # đủ các câu theo đúng thứ tự nguồn
    da_co = set()
    # Mỗi văn bản chỉ góp một câu: một câu trả lời thường trích hai ba đoạn của
    # cùng một thông tư, để nguyên thì cả ba chỗ gợi ý đều hỏi về đúng văn bản
    # đó và người đọc mất hẳn hướng nhìn sang những nguồn còn lại.
    for nguon in cac_nguon[:4]:
        ten = _ten_goi(nguon)
        if ten in da_co:
            continue
        cau = _cau_hoi_theo_nguon(nguon, ten)
        if cau:
            da_co.add(ten)
            tu_nguon.append(cau)
            if (nguon.get("validity") or {}).get("code") in _MA_HIEU_LUC_CAN_HOI:
                canh_bao_hieu_luc.append(cau)
            else:
                ung_vien.append(cau)
    tu_y_chinh = _cau_hoi_tu_y_chinh(rut_y_chinh(cau_tra_loi, cau_hoi))
    if tu_y_chinh:
        # Đã có ý chính bám câu trả lời thì câu hỏi theo Điều chỉ được chen vào
        # khi văn bản đó đúng chủ đề đang hỏi: hỏi môn tin học mà gợi ý "Điều 1
        # của Thông tư về thiết bị dạy học tiểu học" là lạc đề.
        chu_de = _cap_tu_chu_de(cau_hoi)
        lien_quan = [n for n in cac_nguon if chu_de and _nguon_lien_quan(n, chu_de)]
        if chu_de:
            ten_lien_quan = {_ten_goi(n) for n in lien_quan}
            ung_vien = [
                cau for cau in ung_vien if any(ten in cau for ten in ten_lien_quan)
            ]
        cac_nguon = lien_quan if chu_de else cac_nguon
        ung_vien = canh_bao_hieu_luc + tu_y_chinh[:2] + ung_vien[:1] + tu_y_chinh[2:]
    else:
        ung_vien = tu_nguon
    # Tên tệp mã hóa ("11-sgk-tin-hoc-11-...pdf") nhét vào câu gợi ý thì không
    # ai đọc nổi, nên chỉ gợi ý tóm tắt khi gọi được văn bản bằng tên tử tế.
    if cac_nguon and (
        (cac_nguon[0].get("van_ban") or {}).get("so_hieu")
        or _lam_sach_tieu_de(cac_nguon[0].get("name") or "")
    ):
        ung_vien.append(f"Tóm tắt những nội dung chính của {_ten_goi(cac_nguon[0])}")
    # Câu chung "đối tượng áp dụng, lộ trình" chỉ hợp khi nguồn là văn bản quản
    # lý; nguồn là sách giáo khoa hay bài giảng thì hỏi vậy là lạc đề.
    if not cac_nguon or any((nguon.get("van_ban") or {}).get("so_hieu") for nguon in cac_nguon):
        ung_vien += [
            "Nội dung này áp dụng cho những đối tượng nào?",
            "Có mốc thời gian hoặc lộ trình thực hiện nào không?",
            "Còn văn bản nào khác trong kho quy định về nội dung này?",
        ]
    else:
        ung_vien += [
            "Còn tài liệu nào khác trong kho nói về nội dung này?",
            "Cho ví dụ cụ thể về nội dung này",
            "Tóm tắt ngắn gọn các ý trên",
        ]
    return _loc_trung(ung_vien, da_co=[cau_hoi])[:max(0, so_luong)]


def goi_y_theo_tep(
    cau_hoi: str,
    ten_tep=None,
    so_luong: int = SO_GOI_Y_TIEP,
    cau_tra_loi: str = "",
) -> list[str]:
    """Gợi ý hỏi tiếp khi câu trả lời chỉ dựa trên tệp người dùng đính kèm.

    Tệp đính kèm có thể là bất cứ thứ gì - một truyện cổ tích, một bài giảng -
    nên không dùng khuôn "mốc thời gian, số liệu" vốn chỉ hợp với văn bản quản
    lý; ý chính của chính câu trả lời được đưa lên trước.
    """
    ten_tep = [str(ten) for ten in (ten_tep or []) if ten]
    ung_vien = _cau_hoi_tu_y_chinh(rut_y_chinh(cau_tra_loi, cau_hoi))[:2]
    ung_vien += [f"Tóm tắt tệp {ten}" for ten in ten_tep[:2]]
    if len(ten_tep) > 1:
        ung_vien.append("So sánh nội dung giữa các tệp đã đính kèm")
    ung_vien += [f"Tệp {ten} gồm những phần nào?" for ten in ten_tep[:2]]
    ung_vien.append("Ý nghĩa hoặc thông điệp chính của nội dung trong tệp là gì?")
    return _loc_trung(ung_vien, da_co=[cau_hoi])[:max(0, so_luong)]
