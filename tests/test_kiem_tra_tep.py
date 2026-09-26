"""Kiểm tra an toàn tệp tải lên: chặn macro, nội dung khớp đuôi, zip bomb, ClamAV."""

import io
import subprocess
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import kiem_tra_tep
from api import app
from kiem_tra_tep import TepKhongAnToan, kiem_tra_tai_len

# Chuỗi kiểm thử EICAR: vô hại, nhưng mọi trình diệt virus đều báo là virus.
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

DOCX_RELS = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    b'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
)


def tao_zip(cac_muc: dict[str, bytes]) -> bytes:
    bo_dem = io.BytesIO()
    with zipfile.ZipFile(bo_dem, "w", zipfile.ZIP_DEFLATED) as tep_zip:
        for ten, noi_dung in cac_muc.items():
            tep_zip.writestr(ten, noi_dung)
    return bo_dem.getvalue()


def docx_sach(**them) -> bytes:
    return tao_zip({"_rels/.rels": DOCX_RELS, "word/document.xml": b"<w:document/>", **them})


@pytest.fixture(autouse=True)
def tat_clamav(monkeypatch):
    """Mặc định bỏ ClamAV để các test lớp 2-3 không phụ thuộc máy có cài hay không."""
    monkeypatch.setenv("RAG_QUET_VIRUS", "tat")


# ----- Lớp 3: macro -----
def test_tu_choi_xlsm():
    with pytest.raises(TepKhongAnToan, match="macro"):
        kiem_tra_tai_len("bang-diem.xlsm", tao_zip({"xl/workbook.xml": b"<x/>"}))


def test_tu_choi_docx_co_vba_project():
    with pytest.raises(TepKhongAnToan, match="macro"):
        kiem_tra_tai_len("giao-an.docx", docx_sach(**{"word/vbaProject.bin": b"\x00" * 64}))


def test_tu_choi_xlsx_doi_ten_tu_xlsm():
    """Đổi đuôi .xlsm thành .xlsx không lách được: nhìn vào nội dung, không nhìn tên."""
    with pytest.raises(TepKhongAnToan, match="macro"):
        kiem_tra_tai_len("bang-diem.xlsx", tao_zip({"xl/vbaProject.bin": b"\x00" * 64}))


def test_tu_choi_template_injection():
    rels = (
        b'<Relationships><Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate" '
        b'Target="http://ke-xau.example/mau.dotm" TargetMode="External"/></Relationships>'
    )
    with pytest.raises(TepKhongAnToan, match="bên ngoài"):
        kiem_tra_tai_len("giao-an.docx", docx_sach(**{"word/_rels/settings.xml.rels": rels}))


def test_nhan_docx_co_lien_ket_ngoai_binh_thuong():
    """Hyperlink cũng là quan hệ External, nhưng chỉ mở khi người đọc bấm - không chặn."""
    rels = (
        b'<Relationships><Relationship Id="rId5" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        b'Target="https://moet.gov.vn" TargetMode="External"/></Relationships>'
    )
    kiem_tra_tai_len("giao-an.docx", docx_sach(**{"word/_rels/document.xml.rels": rels}))


def test_tu_choi_doc_ole_co_vba():
    du_lieu = kiem_tra_tep.CHU_KY_OLE + b"\x00" * 100 + "_VBA_PROJECT".encode("utf-16-le")
    with pytest.raises(TepKhongAnToan, match="macro"):
        kiem_tra_tai_len("de-thi.doc", du_lieu)


def test_nhan_doc_ole_khong_macro():
    kiem_tra_tai_len("de-thi.doc", kiem_tra_tep.CHU_KY_OLE + b"\x00" * 512)


# ----- Lớp 2: nội dung khớp đuôi -----
@pytest.mark.parametrize("ten, du_lieu", [
    ("bai.pdf", b"%PDF-1.7\n1 0 obj\n"),
    ("bai.pdf", b"\xef\xbb\xbf  %PDF-1.4\n"),       # vài byte rác trước %PDF- vẫn hợp lệ
    ("giao-an.docx", docx_sach()),
    ("de-thi.doc", b"{\\rtf1\\ansi noi dung}"),     # RTF đặt đuôi .doc
    ("de-thi.doc", docx_sach()),                    # .docx đặt nhầm đuôi .doc
    ("diem.xls", kiem_tra_tep.CHU_KY_OLE + b"\x00" * 64),
    ("anh.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32),
    ("anh.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 32),
    ("anh.webp", b"RIFF\x24\x00\x00\x00WEBPVP8 "),
    ("ghi-chu.txt", "Giáo án môn Toán lớp 10".encode("utf-8")),
    ("ghi-chu.txt", b"MZ la hai chu cai dau tien, khong phai chuong trinh"),
    ("bai-giang.mp3", b"\xff\xfb\x90\x00" + b"\x00" * 64),
])
def test_nhan_tep_hop_le(ten, du_lieu):
    kiem_tra_tai_len(ten, du_lieu)


@pytest.mark.parametrize("ten, du_lieu", [
    ("bai.pdf", b"day khong phai pdf"),
    ("giao-an.docx", b"%PDF-1.4 nhung dat ten docx"),
    ("diem.xls", b"<html><table></table></html>"),
    ("anh.png", b"\xff\xd8\xff\xe0 thuc ra la jpg"),
    ("anh.webp", b"RIFF\x24\x00\x00\x00WAVEfmt "),
])
def test_tu_choi_noi_dung_khong_khop_duoi(ten, du_lieu):
    with pytest.raises(TepKhongAnToan, match="không phải định dạng"):
        kiem_tra_tai_len(ten, du_lieu)


def tao_pe_gia() -> bytes:
    du_lieu = bytearray(b"MZ" + b"\x00" * 0x7E)
    du_lieu[0x3C:0x40] = (0x40).to_bytes(4, "little")
    du_lieu[0x40:0x44] = b"PE\x00\x00"
    return bytes(du_lieu)


@pytest.mark.parametrize("ten", ["bai.pdf", "ghi-chu.txt", "bai-giang.mp4"])
@pytest.mark.parametrize("du_lieu", [tao_pe_gia(), b"\x7fELF\x02\x01\x01" + b"\x00" * 64])
def test_tu_choi_tep_thuc_thi_du_dat_ten_gi(ten, du_lieu):
    with pytest.raises(TepKhongAnToan, match="chương trình"):
        kiem_tra_tai_len(ten, du_lieu)


def test_tu_choi_zip_hong():
    with pytest.raises(TepKhongAnToan, match="hỏng"):
        kiem_tra_tai_len("giao-an.docx", kiem_tra_tep.CHU_KY_ZIP + b"\x00" * 100)


def test_tu_choi_zip_bomb_ti_le_nen():
    # 20 MB số 0 nén còn ~20 KB: tỉ lệ ~1000:1, vượt ngưỡng 200:1.
    with pytest.raises(TepKhongAnToan, match="zip bomb"):
        kiem_tra_tai_len("bang.xlsx", tao_zip({"xl/worksheets/sheet1.xml": b"\x00" * (20 * 1024 * 1024)}))


def test_tu_choi_zip_bomb_tong_dung_luong(monkeypatch):
    monkeypatch.setattr(kiem_tra_tep, "GIOI_HAN_GIAI_NEN", 1024 * 1024)
    with pytest.raises(TepKhongAnToan, match="zip bomb"):
        kiem_tra_tai_len("bang.xlsx", tao_zip({"a.xml": b"a" * 600_000, "b.xml": b"b" * 600_000}))


# ----- Lớp 1: ClamAV -----
def gia_clamdscan(ma_thoat: int, dau_ra: bytes = b""):
    return subprocess.CompletedProcess(args=[], returncode=ma_thoat, stdout=dau_ra, stderr=b"")


def test_clamav_sach_thi_nhan(monkeypatch):
    monkeypatch.setenv("RAG_QUET_VIRUS", "bat_buoc")
    monkeypatch.setenv("RAG_LENH_CLAMDSCAN", "/usr/bin/clamdscan")
    with patch("kiem_tra_tep.subprocess.run", return_value=gia_clamdscan(0, b"stream: OK\n")) as chay:
        kiem_tra_tai_len("ghi-chu.txt", b"noi dung sach")
    lenh = chay.call_args.args[0]
    assert lenh == ["/usr/bin/clamdscan", "--no-summary", "-"]
    assert chay.call_args.kwargs["input"] == b"noi dung sach"


def test_clamav_phat_hien_eicar(monkeypatch):
    monkeypatch.setenv("RAG_QUET_VIRUS", "tu_dong")
    monkeypatch.setenv("RAG_LENH_CLAMDSCAN", "/usr/bin/clamdscan")
    ket_qua = gia_clamdscan(1, b"stream: Eicar-Test-Signature FOUND\n")
    with patch("kiem_tra_tep.subprocess.run", return_value=ket_qua):
        with pytest.raises(TepKhongAnToan, match="Eicar-Test-Signature"):
            kiem_tra_tai_len("ghi-chu.txt", EICAR)


@pytest.mark.parametrize("loi", [
    gia_clamdscan(2, b"stream: INSTREAM size limit exceeded. ERROR\n"),
    subprocess.TimeoutExpired(cmd="clamdscan", timeout=120),
    FileNotFoundError("clamdscan"),
])
def test_clamav_loi_thi_tu_choi(monkeypatch, loi):
    """Fail-closed: đã bật quét mà quét không xong thì không nhận tệp."""
    monkeypatch.setenv("RAG_QUET_VIRUS", "tu_dong")
    monkeypatch.setenv("RAG_LENH_CLAMDSCAN", "/usr/bin/clamdscan")
    gia = {"side_effect": loi} if isinstance(loi, Exception) else {"return_value": loi}
    with patch("kiem_tra_tep.subprocess.run", **gia):
        with pytest.raises(TepKhongAnToan, match="chưa kiểm tra được"):
            kiem_tra_tai_len("ghi-chu.txt", b"noi dung")


def test_tu_dong_bo_qua_khi_may_khong_cai_clamav(monkeypatch):
    monkeypatch.setenv("RAG_QUET_VIRUS", "tu_dong")
    monkeypatch.delenv("RAG_LENH_CLAMDSCAN", raising=False)
    with patch("kiem_tra_tep.shutil.which", return_value=None), patch("kiem_tra_tep.subprocess.run") as chay:
        kiem_tra_tai_len("ghi-chu.txt", b"noi dung")
    chay.assert_not_called()


def test_bat_buoc_tu_choi_khi_may_khong_cai_clamav(monkeypatch):
    monkeypatch.setenv("RAG_QUET_VIRUS", "bat_buoc")
    monkeypatch.delenv("RAG_LENH_CLAMDSCAN", raising=False)
    with patch("kiem_tra_tep.shutil.which", return_value=None):
        with pytest.raises(TepKhongAnToan, match="chưa kiểm tra được"):
            kiem_tra_tai_len("ghi-chu.txt", b"noi dung")


def test_tat_khong_goi_clamav(monkeypatch):
    monkeypatch.setenv("RAG_QUET_VIRUS", "tat")
    with patch("kiem_tra_tep.subprocess.run") as chay:
        kiem_tra_tai_len("ghi-chu.txt", EICAR)
    chay.assert_not_called()


# ----- Qua API: tệp bị từ chối không được lưu -----
def test_api_tu_choi_tep_gia_pdf_va_khong_luu():
    client = TestClient(app)
    with patch("tep_dinh_kem.open", create=True) as mo_tep:
        phan_hoi = client.post(
            "/api/tep?ten=bai-tap.pdf", content=tao_pe_gia(),
            headers={"X-RAG-Action": "upload-file", "X-RAG-Client": "khach-kiem-tra-tep"},
        )
    assert phan_hoi.status_code == 400
    assert "chương trình" in phan_hoi.json()["detail"]
    mo_tep.assert_not_called()


def test_api_tu_choi_xlsm():
    phan_hoi = TestClient(app).post(
        "/api/tep?ten=bang-diem.xlsm", content=tao_zip({"xl/workbook.xml": b"<x/>"}),
        headers={"X-RAG-Action": "upload-file", "X-RAG-Client": "khach-kiem-tra-tep"},
    )
    assert phan_hoi.status_code == 400
    assert ".xlsm" in phan_hoi.json()["detail"]


def test_api_tu_choi_virus(monkeypatch):
    monkeypatch.setenv("RAG_QUET_VIRUS", "tu_dong")
    monkeypatch.setenv("RAG_LENH_CLAMDSCAN", "/usr/bin/clamdscan")
    ket_qua = gia_clamdscan(1, b"stream: Eicar-Test-Signature FOUND\n")
    with patch("kiem_tra_tep.subprocess.run", return_value=ket_qua):
        phan_hoi = TestClient(app).post(
            "/api/tep?ten=eicar.txt", content=EICAR,
            headers={"X-RAG-Action": "upload-file", "X-RAG-Client": "khach-kiem-tra-tep"},
        )
    assert phan_hoi.status_code == 400
    assert "mã độc" in phan_hoi.json()["detail"]
