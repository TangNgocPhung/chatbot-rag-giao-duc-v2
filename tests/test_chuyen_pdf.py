"""Sổ tay đọc được Word / Excel / PowerPoint / HTML: chuyển sang PDF bằng LibreOffice rồi đọc như PDF."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

import chuyen_pdf
from api import app


@pytest.fixture(autouse=True)
def thu_muc_ban_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(chuyen_pdf, "THU_MUC", str(tmp_path / "ban_pdf"))


def soffice_gia(so_lan: list):
    """Thay subprocess.run: ghi ra tai-lieu.pdf một trang như LibreOffice."""

    def chay(lenh, **_):
        so_lan.append(lenh)
        thu_muc = lenh[lenh.index("--outdir") + 1]
        ghi = PdfWriter()
        ghi.add_blank_page(width=595, height=842)
        with open(os.path.join(thu_muc, "tai-lieu.pdf"), "wb") as tep:
            ghi.write(tep)

    return chay


def test_lam_sach_html_bo_script_va_duong_dan_ngoai():
    html = (
        '<html><head><meta charset="utf-8"><link rel="stylesheet" href="http://x/a.css">'
        '<style>@import url(http://x/b.css); p{background:url(http://127.0.0.1:8010/api/status)}</style>'
        '</head><body><h1>Tiêu đề</h1><script>alert(1)</script>'
        '<img src="http://127.0.0.1:11434/api/tags"><img src="file:///etc/passwd">'
        '<img src="data:image/png;base64,AAAA"><a href="#muc-1">Mục 1</a>'
        '<iframe src="http://x"></iframe></body></html>'
    ).encode("utf-8")
    sach = chuyen_pdf.lam_sach_html(html).decode("utf-8")
    for bi_cam in ("<script", "alert(1)", "<iframe", "<link", "127.0.0.1", "file:///", "@import", "http://x"):
        assert bi_cam not in sach, bi_cam
    assert "data:image/png;base64,AAAA" in sach
    assert 'href="#muc-1"' in sach
    assert "Tiêu đề" in sach
    assert sach.startswith('<meta charset="utf-8">')


def test_chuyen_mot_lan_roi_dung_lai(tmp_path):
    goc = tmp_path / "giao-an.docx"
    goc.write_bytes(b"PK gia docx")
    so_lan = []
    with patch("chuyen_pdf.tim_soffice", return_value="soffice"), \
            patch("chuyen_pdf._cach_ly_mang", return_value=[]), \
            patch("chuyen_pdf.subprocess.run", side_effect=soffice_gia(so_lan)):
        ban_1 = chuyen_pdf.ban_pdf(str(goc))
        ban_2 = chuyen_pdf.ban_pdf(str(goc))
    assert ban_1 == ban_2 and ban_1.endswith(".pdf") and os.path.isfile(ban_1)
    assert len(so_lan) == 1
    assert "--convert-to" in so_lan[0] and "pdf" in so_lan[0]


def test_html_dung_bo_loc_writer_va_duoc_lam_sach(tmp_path):
    goc = tmp_path / "trang.html"
    goc.write_bytes(b'<html><body><img src="http://127.0.0.1:8010/"><p>Xin chao</p></body></html>')
    so_lan, noi_dung_da_chuyen = [], []

    def chay(lenh, **kw):
        with open(lenh[-1], "rb") as tep:
            noi_dung_da_chuyen.append(tep.read())
        soffice_gia(so_lan)(lenh, **kw)

    with patch("chuyen_pdf.tim_soffice", return_value="soffice"), \
            patch("chuyen_pdf._cach_ly_mang", return_value=["unshare", "-rn"]), \
            patch("chuyen_pdf.subprocess.run", side_effect=chay):
        chuyen_pdf.ban_pdf(str(goc))
    assert so_lan[0][:2] == ["unshare", "-rn"]  # LibreOffice chạy không có mạng
    assert "--infilter=HTML (StarWriter)" in so_lan[0]
    assert b"127.0.0.1" not in noi_dung_da_chuyen[0]


def test_thieu_libreoffice_bao_loi_de_hieu(tmp_path):
    goc = tmp_path / "a.docx"
    goc.write_bytes(b"x")
    with patch("chuyen_pdf.tim_soffice", return_value=None):
        with pytest.raises(chuyen_pdf.LoiChuyenPdf, match="LibreOffice"):
            chuyen_pdf.ban_pdf(str(goc))


def test_api_doc_duoc_word(tmp_path):
    goc = tmp_path / "ke-hoach.docx"
    goc.write_bytes(b"PK gia docx")
    client = TestClient(app)
    with patch("chuyen_pdf.tim_soffice", return_value="soffice"), \
            patch("chuyen_pdf._cach_ly_mang", return_value=[]), \
            patch("chuyen_pdf.subprocess.run", side_effect=soffice_gia([])), \
            patch("rag_service.service.resolve_source_file", return_value=str(goc)):
        thong_tin = client.get("/api/doc/thong-tin", params={"nguon": "ke-hoach.docx"})
        anh = client.get("/api/doc/trang", params={"nguon": "ke-hoach.docx", "so": 1, "rong": 400})
    assert thong_tin.status_code == 200 and thong_tin.json()["so_trang"] == 1
    assert anh.status_code == 200 and anh.headers["content-type"].startswith("image/")

    with patch("chuyen_pdf.tim_soffice", return_value=None), \
            patch("rag_service.service.resolve_source_file", return_value=str(tmp_path / "khac.docx")):
        (tmp_path / "khac.docx").write_bytes(b"y")
        loi = client.get("/api/doc/thong-tin", params={"nguon": "khac.docx"})
    assert loi.status_code == 422 and "LibreOffice" in loi.json()["detail"]


@pytest.mark.parametrize("ten, bo_loc", [
    ("ke-hoach.xlsx", None),
    ("bai-giang.pptx", None),
    ("diem.csv", "--infilter=CSV:44,34,76"),
    ("diem.tsv", "--infilter=CSV:9,34,76"),
])
def test_excel_powerpoint_csv(tmp_path, ten, bo_loc):
    goc = tmp_path / ten
    goc.write_bytes("STT,Họ tên\n1,Lan\n".encode("utf-8"))
    so_lan = []
    with patch("chuyen_pdf.tim_soffice", return_value="soffice"), \
            patch("chuyen_pdf._cach_ly_mang", return_value=[]), \
            patch("chuyen_pdf.subprocess.run", side_effect=soffice_gia(so_lan)):
        assert chuyen_pdf.ban_pdf(str(goc)).endswith(".pdf")
    lenh = so_lan[0]
    assert lenh[lenh.index("--convert-to") + 1] == "pdf"
    assert (bo_loc in lenh) if bo_loc else not any(t.startswith("--infilter") for t in lenh)


def test_dinh_dang_khong_ho_tro():
    assert not chuyen_pdf.chuyen_duoc("phim.mp4")
    assert chuyen_pdf.chuyen_duoc("Bai 1.PPTX") and chuyen_pdf.chuyen_duoc("so-lieu.XLS")
