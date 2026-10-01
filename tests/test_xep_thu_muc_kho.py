"""Tệp vào kho phải nằm đúng thư mục con theo định dạng và loại nội dung.

Người quản trị xem kho qua WinSCP: hơn một nghìn tệp trộn lẫn ở gốc kho thì
không tìm được gì. Nhưng chuyển tệp là đổi đường dẫn mà sổ ghi chép, FAISS và
drive_state.json đều nhớ - nên phần lớn test ở đây là test "không làm hỏng".
"""

import json
import os
import pickle
import zipfile

import pytest
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.documents import Document

import drive_sync
import phan_loai_giao_duc
import rag_service
import van_ban_meta
import xep_kho_theo_loai
from phan_loai_giao_duc import PhanLoai
from rag_service import service
from van_ban_meta import HoSoVanBan
from xep_thu_muc_kho import chon_thu_muc


def _docx(duong_dan, *cac_dong):
    """Tệp .docx tối giản: chỉ cần word/document.xml là đủ để đọc chữ."""
    than = "".join(f"<w:p><w:r><w:t>{dong}</w:t></w:r></w:p>" for dong in cac_dong)
    with zipfile.ZipFile(duong_dan, "w") as goi:
        goi.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            f'wordprocessingml/2006/main"><w:body>{than}</w:body></w:document>',
        )
    return str(duong_dan)


# ------------------------------------------------------------
# CHỌN THƯ MỤC
# ------------------------------------------------------------
@pytest.mark.parametrize("ten, thu_muc", [
    # Tên tệp thật trong kho trên VPS.
    ("Vở bài tập Toán 5 - Tập một.pdf", "pdf/sach_bai_tap"),
    ("Vở bài tập Tiếng Việt 2 - Tập hai.pdf", "pdf/sach_bai_tap"),
    ("VoNhat_NhanVatTrang.pptx", "trinh_chieu"),
    ("YTDown.com_YouTube_Giao-Duc-Le-Giao.mp4", "video"),
    ("SGK Tin học 4.pdf", "pdf/sach_giao_khoa"),
    ("SGV Toán 3.docx", "word/sach_giao_vien"),
    ("Ke hoach bai day Toan 5.docx", "word/giao_an"),
    ("De kiem tra giua ki Toan 4.docx", "word/de_kiem_tra"),
    # Văn bản quy phạm: loại văn bản suy từ tên tệp.
    ("27-2020-TT-BGDDT.pdf", "pdf/van_ban_quy_pham/thong_tu"),
    ("Luat Giao duc 2019.pdf", "pdf/van_ban_quy_pham/luat"),
    ("Nghị định 24-2021.docx", "word/van_ban_quy_pham/nghi_dinh"),
    ("Thong tu lien tich 10.pdf", "pdf/van_ban_quy_pham/thong_tu_lien_tich"),
    ("ND24-2023.pdf", "pdf/van_ban_quy_pham/nghi_dinh"),
    # Định dạng không chia tiếp theo nội dung.
    ("bai-hat.mp3", "am_thanh"),
    ("trang-sach.jpg", "hinh_anh"),
    ("thoi-khoa-bieu.xlsx", "bang_tinh"),
    ("ghi-chu.txt", "van_ban_khac"),
    # Không có dấu hiệu gì: không đoán.
    ("Yeucau_Baithuchanh_01B.pdf", "pdf/chua_phan_loai"),
    ("XD KHDH KHỐI 5.docx", "word/chua_phan_loai"),
])
def test_chon_thu_muc_theo_ten(ten, thu_muc):
    assert chon_thu_muc(ten) == thu_muc


@pytest.mark.parametrize("ten", [
    # "tt", "ct" trong tên bài học không phải thông tư, chỉ thị.
    "Bai 2 tt 5.pdf",
    # Mở đầu bằng tên loại nhưng là học liệu, không phải văn bản hành chính.
    "Huong dan giai bai tap Toan 5.pdf",
    "Thong bao lich thi.pdf",
])
def test_khong_nham_hoc_lieu_thanh_van_ban(ten):
    assert "van_ban_quy_pham" not in chon_thu_muc(ten)


def test_doc_tieu_de_trong_noi_dung_docx(tmp_path):
    tep = _docx(
        tmp_path / "van-ban-moi.docx",
        "BỘ GIÁO DỤC VÀ ĐÀO TẠO", "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "THÔNG TƯ", "Ban hành Quy định về đánh giá học sinh tiểu học",
        "Căn cứ Luật Giáo dục ngày 14 tháng 6 năm 2019;",
    )
    assert chon_thu_muc("van-ban-moi.docx", tep) == "word/van_ban_quy_pham/thong_tu"


def test_so_hieu_trong_noi_dung_quyet_dinh_loai(tmp_path):
    """Kế hoạch của Sở có mã KH trong số hiệu - suy_loai_van_ban không biết mã
    này, nhưng không được rơi vào 'khac'."""
    tep = _docx(
        tmp_path / "tai-lieu.docx",
        "SỞ GIÁO DỤC VÀ ĐÀO TẠO", "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "Số: 123/KH-SGDĐT", "Triển khai nhiệm vụ năm học 2026-2027",
    )
    assert chon_thu_muc("tai-lieu.docx", tep) == "word/van_ban_quy_pham/ke_hoach"


def test_cong_van_nhan_theo_trich_yeu(tmp_path):
    tep = _docx(
        tmp_path / "cv.docx",
        "BỘ GIÁO DỤC VÀ ĐÀO TẠO", "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "Số: 4567/BGDĐT-GDTH", "V/v hướng dẫn thực hiện nhiệm vụ năm học",
    )
    assert chon_thu_muc("cv.docx", tep) == "word/van_ban_quy_pham/cong_van"


def test_quoc_hieu_viet_hoa_kieu_cu_va_cong_dien(tmp_path):
    """"CỘNG HOÀ" (dấu đặt kiểu cũ) và "Ð" của OCR từng làm công điện của Thủ
    tướng rơi vào chưa phân loại."""
    tep = _docx(
        tmp_path / "Về việc thực hiện chế độ.docx",
        "THỦ TƯỚNG CHÍNH PHỦ", "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "Số: 62/CÐ-TTg", "CÔNG ĐIỆN", "Về việc thực hiện chế độ, chính sách",
    )
    assert chon_thu_muc(os.path.basename(tep), tep) == "word/van_ban_quy_pham/cong_dien"


def test_phu_luc_ban_hanh_kem_theo_thong_tu(tmp_path):
    tep = _docx(
        tmp_path / "cttin_hoc.docx", "BỘ GIÁO DỤC VÀ ĐÀO TẠO",
        "CHƯƠNG TRÌNH GIÁO DỤC PHỔ THÔNG MÔN TIN HỌC",
        "(Ban hành kèm theo Thông tư số 32/2018/TT-BGDĐT ngày 26 tháng 12 năm 2018)",
    )
    assert chon_thu_muc("cttin_hoc.docx", str(tep)) == "word/van_ban_quy_pham/thong_tu"


def test_ke_hoach_cua_truong_co_quoc_hieu_van_la_ke_hoach_day_hoc(tmp_path):
    tep = _docx(
        tmp_path / "PPCT TIN 3.docx", "TRƯỜNG TIỂU HỌC",
        "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "KẾ HOẠCH THỰC HIỆN CHƯƠNG TRÌNH MÔN TIN HỌC KHỐI 3",
    )
    assert chon_thu_muc("PPCT TIN 3.docx", str(tep)) == "word/ke_hoach_day_hoc"


def test_van_ban_hop_nhat_chi_co_ten(tmp_path):
    assert (chon_thu_muc("2026_172_40_VBHN-VPQH.docx")
            == "word/van_ban_quy_pham/van_ban_hop_nhat")


def test_trang_bia_sach_trong_noi_dung(tmp_path):
    tep = _docx(tmp_path / "toan5.docx", "SÁCH GIÁO VIÊN", "TOÁN 5")
    assert chon_thu_muc("toan5.docx", tep) == "word/sach_giao_vien"


def test_pdf_scan_dung_ban_ocr_da_co(tmp_path, monkeypatch):
    """PDF không có lớp chữ: lấy chữ từ cache OCR (khoá theo hash nội dung)."""
    import ocr_pdf

    tep = tmp_path / "scan.pdf"
    tep.write_bytes(b"khong phai pdf that")
    monkeypatch.setattr(ocr_pdf, "doc_cache", lambda _: [
        "QUỐC HỘI\nCỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nLUẬT\nGIÁO DỤC", "trang 2",
    ])
    assert chon_thu_muc("scan.pdf", str(tep)) == "pdf/van_ban_quy_pham/luat"


def test_bang_da_lap_tu_toan_van_duoc_uu_tien():
    """Nhãn lập lúc lập chỉ mục đã thấy toàn văn (cả OCR) - tin hơn tên tệp."""
    assert chon_thu_muc(
        "tai-lieu-1.pdf",
        phan_loai=PhanLoai(ten_file="tai-lieu-1.pdf", loai_noi_dung="sach_giao_khoa"),
    ) == "pdf/sach_giao_khoa"
    assert chon_thu_muc(
        "311-cp.signed.pdf",
        phan_loai=PhanLoai(ten_file="311-cp.signed.pdf", loai_noi_dung="van_ban_quy_pham"),
        ho_so=HoSoVanBan(ten_file="311-cp.signed.pdf", so_hieu="29/NQ-CP", loai="Nghị quyết"),
    ) == "pdf/van_ban_quy_pham/nghi_quyet"


def test_chua_phan_loai_trong_bang_van_thu_quy_tac_ten():
    """'hoc_lieu_khac' chỉ là 'không thấy dấu hiệu', không chặn quy tắc tên."""
    assert chon_thu_muc(
        "Luat Giao duc 2019.pdf",
        phan_loai=PhanLoai(ten_file="Luat Giao duc 2019.pdf"),
    ) == "pdf/van_ban_quy_pham/luat"


# ------------------------------------------------------------
# TẢI LÊN QUA GIAO DIỆN
# ------------------------------------------------------------
@pytest.fixture
def kho_tam(tmp_path, monkeypatch):
    kho = tmp_path / "data_giao_duc"
    kho.mkdir()
    monkeypatch.setattr(rag_service, "DATA_PATH", str(kho))
    monkeypatch.setattr(rag_service, "DUONG_DAN_SO_GHI_CHEP", str(tmp_path / "so.json"))
    monkeypatch.setattr(service, "_hen_cap_nhat_chi_muc", lambda: None)
    monkeypatch.setattr(service, "_vao_thang_kho", staticmethod(lambda nguoi: True))
    monkeypatch.setattr(rag_service.quan_ly_kho, "ghi_vao_kho", lambda *a, **k: None)
    service.tep_cho_nap.clear()
    yield kho
    service.tep_cho_nap.clear()


def test_tai_len_vao_dung_thu_muc(kho_tam):
    trang_thai, thong_bao = service.nhap_tep_tu_giao_dien(
        "Vở bài tập Toán 5 - Tập một.pdf", b"%PDF-1.4 noi dung"
    )
    assert trang_thai == "da_luu"
    assert (kho_tam / "pdf" / "sach_bai_tap" / "Vở bài tập Toán 5 - Tập một.pdf").is_file()
    assert "data_giao_duc/pdf/sach_bai_tap" in thong_bao


def test_tat_xep_thu_muc_thi_luu_nhu_cu(kho_tam, monkeypatch):
    monkeypatch.setenv("RAG_XEP_THU_MUC_THEO_LOAI", "0")
    trang_thai, _ = service.nhap_tep_tu_giao_dien("SGK Toan 5.pdf", b"%PDF-1.4 x")
    assert trang_thai == "da_luu"
    assert (kho_tam / rag_service.THU_MUC_TEP_TRONG_KHO / "SGK Toan 5.pdf").is_file()


def test_trung_noi_dung_chua_lap_chi_muc_o_thu_muc_con(kho_tam):
    """Tệp vừa tải lên nằm ở pdf/sach_bai_tap, chưa vào sổ ghi chép. Tải lại
    cùng nội dung với tên khác vẫn phải bị nhận ra là trùng."""
    service.nhap_tep_tu_giao_dien("SBT Toan 5.pdf", b"%PDF-1.4 cung noi dung")
    trang_thai, thong_bao = service.nhap_tep_tu_giao_dien(
        "ten-khac.pdf", b"%PDF-1.4 cung noi dung"
    )
    assert trang_thai == "da_co"
    assert "SBT Toan 5.pdf" in thong_bao


def test_ten_van_duy_nhat_giua_cac_thu_muc(kho_tam):
    """Trích dẫn mở tệp theo tên: hai thư mục có cùng tên tệp là mất liên kết."""
    (kho_tam / "video").mkdir()
    (kho_tam / "video" / "SGK Toan 5.pdf").write_bytes(b"ban khac")
    service.nhap_tep_tu_giao_dien("SGK Toan 5.pdf", b"%PDF-1.4 moi")
    assert (kho_tam / "pdf" / "sach_giao_khoa" / "SGK Toan 5 (2).pdf").is_file()


# ------------------------------------------------------------
# XẾP LẠI KHO ĐANG CÓ
# ------------------------------------------------------------
@pytest.fixture
def kho_cu(tmp_path, monkeypatch):
    """Kho phẳng đã lập chỉ mục: sổ ghi chép, FAISS và Drive đều nhớ đường dẫn."""
    kho = tmp_path / "data_giao_duc"
    kho.mkdir()
    for ten in ("Vở bài tập Toán 5 - Tập một.pdf", "27-2020-TT-BGDDT.pdf",
                "bai-giang.pptx", "khong-ro.pdf"):
        (kho / ten).write_bytes(b"%PDF-1.4 " + ten.encode())
    # Quản trị viên đã tự xếp tệp này - không được đụng.
    (kho / "pdf" / "giao_an").mkdir(parents=True)
    (kho / "pdf" / "giao_an" / "da-xep-tay.pdf").write_bytes(b"x")

    so_ghi_chep = tmp_path / "so.json"
    so_ghi_chep.write_text(json.dumps({
        str(kho / "Vở bài tập Toán 5 - Tập một.pdf"): {"hash": "a", "chunk_ids": ["1"]},
        str(kho / "27-2020-TT-BGDDT.pdf"): {"hash": "b", "chunk_ids": ["2"]},
    }), encoding="utf-8")

    chi_muc = tmp_path / "faiss"
    chi_muc.mkdir()
    docstore = InMemoryDocstore({
        "1": Document(page_content="bai tap", metadata={
            "source": str(kho / "Vở bài tập Toán 5 - Tập một.pdf"),
            "source_file": "Vở bài tập Toán 5 - Tập một.pdf", "loai_thu_muc": "goc"}),
        "2": Document(page_content="thong tu", metadata={
            "source": str(kho / "27-2020-TT-BGDDT.pdf"),
            "source_file": "27-2020-TT-BGDDT.pdf", "loai_thu_muc": "goc"}),
    })
    with open(chi_muc / "index.pkl", "wb") as f:
        pickle.dump((docstore, {0: "1", 1: "2"}), f)

    drive_state = tmp_path / "drive_state.json"
    drive_state.write_text(json.dumps({
        "ma1": {"duong_dan": "bai-giang.pptx", "md5": "m", "size": 10},
    }), encoding="utf-8")

    monkeypatch.setattr(xep_kho_theo_loai, "DATA_PATH", str(kho))
    monkeypatch.setattr(xep_kho_theo_loai, "DUONG_DAN_SO_GHI_CHEP", str(so_ghi_chep))
    monkeypatch.setattr(xep_kho_theo_loai, "DUONG_DAN_INDEX", str(chi_muc))
    monkeypatch.setattr(xep_kho_theo_loai, "DUONG_DAN_DRIVE_STATE", str(drive_state))
    # Bảng nhãn thật của dự án không được lọt vào test.
    monkeypatch.setattr(phan_loai_giao_duc, "DUONG_DAN_PHAN_LOAI", str(tmp_path / "pl.json"))
    monkeypatch.setattr(van_ban_meta, "DUONG_DAN_HO_SO", str(tmp_path / "hs.json"))
    return kho, so_ghi_chep, chi_muc, drive_state


def test_xep_lai_kho_sua_ca_ba_noi_nho_duong_dan(kho_cu):
    kho, so_ghi_chep, chi_muc, drive_state = kho_cu
    ke_hoach, canh_bao = xep_kho_theo_loai.lap_ke_hoach()
    assert canh_bao == []
    ket_qua = xep_kho_theo_loai.thuc_hien(ke_hoach)
    assert ket_qua["loi"] == []

    bai_tap = kho / "pdf" / "sach_bai_tap" / "Vở bài tập Toán 5 - Tập một.pdf"
    thong_tu = kho / "pdf" / "van_ban_quy_pham" / "thong_tu" / "27-2020-TT-BGDDT.pdf"
    assert bai_tap.is_file() and thong_tu.is_file()
    assert (kho / "trinh_chieu" / "bai-giang.pptx").is_file()
    assert (kho / "pdf" / "chua_phan_loai" / "khong-ro.pdf").is_file()
    assert (kho / "pdf" / "giao_an" / "da-xep-tay.pdf").is_file()
    assert [p.name for p in kho.iterdir() if p.is_file()] == []

    # Sổ ghi chép: khoá mới, bản ghi giữ nguyên -> không phải lập chỉ mục lại.
    so = json.loads(so_ghi_chep.read_text(encoding="utf-8"))
    assert so == {
        str(bai_tap): {"hash": "a", "chunk_ids": ["1"]},
        str(thong_tu): {"hash": "b", "chunk_ids": ["2"]},
    }
    # FAISS: trích dẫn trỏ đúng chỗ mới.
    with open(chi_muc / "index.pkl", "rb") as f:
        docstore, _ = pickle.load(f)
    assert docstore._dict["1"].metadata["source"] == str(bai_tap)
    assert docstore._dict["1"].metadata["loai_thu_muc"] == "pdf"
    assert docstore._dict["2"].metadata["source"] == str(thong_tu)
    # Drive: lượt đồng bộ sau không tải lại.
    trang_thai = json.loads(drive_state.read_text(encoding="utf-8"))
    assert trang_thai["ma1"]["duong_dan"] == os.path.join("trinh_chieu", "bai-giang.pptx")
    # Có bản sao lưu để quay lại.
    assert any(".truoc-khi-xep-loai-" in p.name for p in so_ghi_chep.parent.iterdir())


def test_chay_lai_khong_xao_tron(kho_cu):
    xep_kho_theo_loai.thuc_hien(xep_kho_theo_loai.lap_ke_hoach()[0])
    ke_hoach, _ = xep_kho_theo_loai.lap_ke_hoach()
    assert ke_hoach == {}


def test_xep_lai_chua_phan_loai_chi_khi_duoc_yeu_cau(kho_cu):
    """Tệp trong chua_phan_loai/ nay đã xếp được thì chuyển; tệp vẫn không rõ
    và tệp quản trị viên đã xếp tay thì giữ nguyên."""
    kho, so_ghi_chep, _, _ = kho_cu
    chua = kho / "pdf" / "chua_phan_loai"
    chua.mkdir(parents=True)
    sgk = chua / "11-sgk-giao-duc-kinh-te-va-phap-luat-11.pdf"
    sgk.write_bytes(b"%PDF-1.4 sgk")
    (chua / "van-khong-ro.pdf").write_bytes(b"%PDF-1.4 x")
    so_ghi_chep.write_text(json.dumps({str(sgk): {"hash": "c"}}), encoding="utf-8")

    ke_hoach, _ = xep_kho_theo_loai.lap_ke_hoach()
    assert str(sgk) not in ke_hoach

    ke_hoach, _ = xep_kho_theo_loai.lap_ke_hoach(xep_lai_chua_phan_loai=True)
    dich = kho / "pdf" / "sach_giao_khoa" / sgk.name
    assert ke_hoach[str(sgk)] == str(dich)
    assert str(chua / "van-khong-ro.pdf") not in ke_hoach
    assert not any("da-xep-tay" in cu for cu in ke_hoach)

    xep_kho_theo_loai.thuc_hien(ke_hoach)
    assert dich.is_file() and (chua / "van-khong-ro.pdf").is_file()
    assert json.loads(so_ghi_chep.read_text(encoding="utf-8")) == {str(dich): {"hash": "c"}}


def test_thu_xem_khong_dung_vao_tep(kho_cu, monkeypatch, capsys):
    kho, so_ghi_chep, _, _ = kho_cu
    truoc = so_ghi_chep.read_text(encoding="utf-8")
    monkeypatch.setattr(xep_kho_theo_loai, "THU_MUC_DU_AN", str(kho.parent))
    monkeypatch.setattr("sys.argv", ["xep_kho_theo_loai.py", "--thu-xem"])
    assert xep_kho_theo_loai.main() == 0
    assert (kho / "27-2020-TT-BGDDT.pdf").is_file()
    assert so_ghi_chep.read_text(encoding="utf-8") == truoc
    assert "pdf/van_ban_quy_pham/thong_tu/" in capsys.readouterr().out


def test_dung_khi_ung_dung_con_chay(kho_cu, monkeypatch):
    kho, _, _, _ = kho_cu
    monkeypatch.setattr(xep_kho_theo_loai, "ung_dung_dang_chay", lambda cong: True)
    monkeypatch.setattr("sys.argv", ["xep_kho_theo_loai.py"])
    assert xep_kho_theo_loai.main() == 1
    assert (kho / "27-2020-TT-BGDDT.pdf").is_file()


# ------------------------------------------------------------
# ĐỒNG BỘ DRIVE SAU KHI KHO ĐÃ XẾP
# ------------------------------------------------------------
@pytest.fixture
def kho_drive(tmp_path, monkeypatch):
    kho = tmp_path / "data"
    kho.mkdir()
    monkeypatch.setattr(drive_sync, "DATA_PATH", str(kho))
    monkeypatch.setattr(drive_sync, "DUONG_DAN_TRANG_THAI", str(tmp_path / "state.json"))
    monkeypatch.setattr(drive_sync, "THU_MUC_DA_GO", str(tmp_path / "da_go"))
    monkeypatch.setattr(drive_sync, "NGHI_GIAY", 0)
    monkeypatch.setattr(drive_sync, "API_KEY", "")
    monkeypatch.setattr(drive_sync, "da_cau_hinh", lambda: (True, ""))
    da_tai = []

    def tai(ma_file, dich, mime, bao_tien_do=None):
        da_tai.append(ma_file)
        with open(dich, "wb") as f:
            f.write(b"%PDF-1.4 tu drive")
        return 17

    monkeypatch.setattr(drive_sync, "_tai_co_thu_lai", tai)
    return kho, tmp_path / "state.json", da_tai


def _muc_drive(ma, ten, size=17):
    return {"id": ma, "name": ten, "mimeType": "application/pdf",
            "md5Checksum": "x", "size": str(size)}


def test_drive_khong_tai_lai_tep_da_xep(kho_drive, monkeypatch):
    kho, state, da_tai = kho_drive
    (kho / "pdf" / "sach_bai_tap").mkdir(parents=True)
    (kho / "pdf" / "sach_bai_tap" / "SBT Toan 5.pdf").write_bytes(b"%PDF-1.4 tu drive")
    state.write_text(json.dumps({"ma1": {
        "duong_dan": os.path.join("pdf", "sach_bai_tap", "SBT Toan 5.pdf"),
        "md5": "x", "size": 17,
    }}), encoding="utf-8")
    monkeypatch.setattr(drive_sync, "liet_ke_qua_manifest",
                        lambda: [_muc_drive("ma1", "SBT Toan 5.pdf")])

    drive_sync.dong_bo()
    assert da_tai == []
    assert not (kho / "SBT Toan 5.pdf").exists()


def test_drive_nhan_tep_da_co_o_thu_muc_con(kho_drive, monkeypatch):
    """Máy chạy đồng bộ lần đầu, kho đã xếp sẵn: chỉ ghi nhận, không tải."""
    kho, state, da_tai = kho_drive
    (kho / "pdf" / "sach_giao_khoa").mkdir(parents=True)
    (kho / "pdf" / "sach_giao_khoa" / "SGK Toan 5.pdf").write_bytes(b"%PDF-1.4 tu drive")
    monkeypatch.setattr(drive_sync, "liet_ke_qua_manifest",
                        lambda: [_muc_drive("ma2", "SGK Toan 5.pdf")])

    ket_qua = drive_sync.dong_bo()
    assert da_tai == []
    assert ket_qua.da_co == ["SGK Toan 5.pdf"]
    ban_ghi = json.loads(state.read_text(encoding="utf-8"))["ma2"]
    assert ban_ghi["duong_dan"] == os.path.join("pdf", "sach_giao_khoa", "SGK Toan 5.pdf")


def test_drive_tep_moi_vao_thu_muc_theo_loai(kho_drive, monkeypatch):
    kho, state, da_tai = kho_drive
    monkeypatch.setattr(drive_sync, "liet_ke_qua_manifest",
                        lambda: [_muc_drive("ma3", "SGV Toan 3.pdf")])

    drive_sync.dong_bo()
    assert da_tai == ["ma3"]
    assert (kho / "pdf" / "sach_giao_vien" / "SGV Toan 3.pdf").is_file()
    assert not (kho / "SGV Toan 3.pdf").exists()
    ban_ghi = json.loads(state.read_text(encoding="utf-8"))["ma3"]
    assert ban_ghi["duong_dan"] == os.path.join("pdf", "sach_giao_vien", "SGV Toan 3.pdf")
