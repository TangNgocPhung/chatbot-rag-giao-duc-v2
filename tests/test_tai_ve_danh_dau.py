"""Tải tài liệu về kèm các nét bút / tô sáng / khoanh đã vẽ trong sổ tay."""

import io
from unittest.mock import patch

import pypdfium2
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject, RectangleObject

import trinh_doc_tai_lieu as t
from api import app

NET = {1: [
    {"c": "but", "m": "#d64534", "d": 0.01, "p": [0.2, 0.25, 0.5, 0.25, 0.8, 0.25]},
    {"c": "to-sang", "m": "#ffd43b", "d": 0.03, "p": [0.85, 0.5, 0.85, 0.9]},
    {"c": "khoanh", "h": "cn", "p": [0.1, 0.7, 0.3, 0.9]},
]}


def pdf_mau(tmp_path, xoay=0, hop=None, so_trang=1):
    ghi = PdfWriter()
    for _ in range(so_trang):
        trang = ghi.add_blank_page(width=600, height=800)
        if hop:
            trang.mediabox = RectangleObject([0, 0, 700, 900])
            trang.cropbox = RectangleObject(hop)
        trang[NameObject("/Rotate")] = NumberObject(xoay)
    duong_dan = tmp_path / f"mau-{xoay}-{bool(hop)}.pdf"
    with open(duong_dan, "wb") as tep:
        ghi.write(tep)
    return str(duong_dan)


def ve_lai(du_lieu, so_trang=0):
    anh = pypdfium2.PdfDocument(du_lieu)[so_trang].render(scale=1).to_pil().convert("RGB")
    rong, cao = anh.size
    return lambda u, v: anh.getpixel((min(rong - 1, int(u * rong)), min(cao - 1, int(v * cao))))


@pytest.mark.parametrize("xoay", [0, 90, 180, 270])
@pytest.mark.parametrize("hop", [None, [50, 60, 650, 860]])
def test_net_nam_dung_cho_nguoi_dung_nhin_thay(tmp_path, xoay, hop):
    """Toạ độ nét là toạ độ trên trang đã xoay / đã cắt, giống ảnh giao diện hiển thị."""
    diem = ve_lai(t.xuat_pdf_danh_dau(pdf_mau(tmp_path, xoay, hop), NET))
    assert diem(0.5, 0.25) == (214, 69, 52)            # bút đỏ
    vang = diem(0.85, 0.7)
    # Tô sáng vàng #ffd43b trong suốt 38% trên nền trắng: xanh lam 255 - .38 * 196 ≈ 181.
    assert vang[0] == 255 and 175 < vang[2] < 190
    assert diem(0.2, 0.8) not in {(255, 255, 255)}      # nền mờ của vùng khoanh
    assert diem(0.5, 0.6) == (255, 255, 255)            # chỗ không vẽ vẫn trắng


def test_giu_nguyen_noi_dung_va_so_trang(tmp_path):
    duong_dan = pdf_mau(tmp_path, so_trang=3)
    du_lieu = t.xuat_pdf_danh_dau(duong_dan, {2: NET[1]})
    doc = PdfReader(io.BytesIO(du_lieu))
    assert len(doc.pages) == 3
    assert ve_lai(du_lieu, 0)(0.5, 0.25) == (255, 255, 255)  # trang không có nét
    assert ve_lai(du_lieu, 1)(0.5, 0.25) == (214, 69, 52)


def test_trang_khong_ton_tai(tmp_path):
    with pytest.raises(t.LoiDocTaiLieu):
        t.xuat_pdf_danh_dau(pdf_mau(tmp_path), {5: NET[1]})


def test_mau_la_bi_bo_qua(tmp_path):
    net = {1: [{"c": "but", "m": "red) Tj (x", "d": 0.01, "p": [0.2, 0.25, 0.8, 0.25]}]}
    diem = ve_lai(t.xuat_pdf_danh_dau(pdf_mau(tmp_path), net))
    assert diem(0.5, 0.25) == (31, 42, 68)  # về màu mực mặc định, không chèn được lệnh PDF


def test_anh_chup_thanh_pdf_mot_trang(tmp_path):
    duong_dan = tmp_path / "trang-sach.png"
    Image.new("RGB", (400, 600), (255, 255, 255)).save(duong_dan)
    du_lieu = t.xuat_pdf_danh_dau(str(duong_dan), NET)
    assert len(PdfReader(io.BytesIO(du_lieu)).pages) == 1
    assert ve_lai(du_lieu)(0.5, 0.25) == (214, 69, 52)


def test_api_tai_ve(tmp_path):
    duong_dan = pdf_mau(tmp_path)
    client = TestClient(app)
    with patch("api._tai_lieu_can_doc", return_value=duong_dan) as tim:
        phan_hoi = client.post("/api/doc/tai-ve", json={
            "nguon": "Quy định.pdf", "ten": "Quy định.pdf", "net": {"1": NET[1]},
        })
    assert phan_hoi.status_code == 200
    assert tim.call_args.args[:2] == (None, "Quy định.pdf")
    assert phan_hoi.headers["content-type"] == "application/pdf"
    assert "filename*=UTF-8''Quy%20%C4%91%E1%BB%8Bnh%20%28%C4%91%C3%A3" in phan_hoi.headers["content-disposition"]
    assert ve_lai(phan_hoi.content)(0.5, 0.25) == (214, 69, 52)


def test_api_tu_choi_net_la(tmp_path):
    client = TestClient(app)
    with patch("api._tai_lieu_can_doc", return_value=pdf_mau(tmp_path)):
        phan_hoi = client.post("/api/doc/tai-ve", json={
            "nguon": "a.pdf", "net": {"1": [{"c": "javascript", "p": [0.1, 0.1]}]},
        })
    assert phan_hoi.status_code == 422
