"""Đồng bộ Drive không được xoá tài liệu hàng loạt.

Ngày 23/9/2026: máy chạy không có API key lấy drive_manifest.json cũ (409 tệp)
làm "toàn bộ Drive" và xoá khoảng 300 tài liệu thêm vào kho sau đó.
"""

import json
import os

import pytest

import drive_sync


@pytest.fixture
def kho(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(drive_sync, "DATA_PATH", str(data))
    monkeypatch.setattr(drive_sync, "DUONG_DAN_TRANG_THAI", str(tmp_path / "state.json"))
    monkeypatch.setattr(drive_sync, "THU_MUC_DA_GO", str(tmp_path / "da_go"))
    monkeypatch.setattr(drive_sync, "NGHI_GIAY", 0)
    monkeypatch.setattr(drive_sync, "da_cau_hinh", lambda: (True, ""))
    trang_thai = {}
    for i in range(30):
        ten = f"tai-lieu-{i}.pdf"
        (data / ten).write_bytes(b"%PDF-1.4 noi dung")
        trang_thai[f"ma{i}"] = {"duong_dan": ten, "md5": "x", "size": 17}
    (tmp_path / "state.json").write_text(json.dumps(trang_thai), encoding="utf-8")
    return data


def _drive_con(so_tep):
    return [
        {"id": f"ma{i}", "name": f"tai-lieu-{i}.pdf", "mimeType": "application/pdf",
         "md5Checksum": "x", "size": "17", "_thu_muc": ""}
        for i in range(so_tep)
    ]


def test_manifest_khong_bao_gio_xoa(kho, monkeypatch):
    monkeypatch.setattr(drive_sync, "API_KEY", "")
    monkeypatch.setattr(drive_sync, "liet_ke_qua_manifest", lambda: _drive_con(5))
    monkeypatch.setattr(drive_sync, "_tai_co_thu_lai", lambda *a, **k: None)
    ket_qua = drive_sync.dong_bo()
    assert ket_qua.da_xoa == []
    assert len(os.listdir(kho)) == 30


def test_danh_sach_thieu_nhieu_thi_khong_go(kho, monkeypatch):
    monkeypatch.setattr(drive_sync, "API_KEY", "khoa")
    monkeypatch.setattr(drive_sync, "liet_ke_qua_api", lambda _: _drive_con(5))
    monkeypatch.setattr(drive_sync, "_tai_co_thu_lai", lambda *a, **k: None)
    ket_qua = drive_sync.dong_bo()
    assert ket_qua.da_xoa == []
    assert len(os.listdir(kho)) == 30
    assert any("quá nhiều" in loi for loi in ket_qua.loi)


def test_go_it_tep_thi_chuyen_vao_cach_ly(kho, monkeypatch, tmp_path):
    monkeypatch.setattr(drive_sync, "API_KEY", "khoa")
    monkeypatch.setattr(drive_sync, "liet_ke_qua_api", lambda _: _drive_con(28))
    monkeypatch.setattr(drive_sync, "_tai_co_thu_lai", lambda *a, **k: None)
    ket_qua = drive_sync.dong_bo()
    assert sorted(ket_qua.da_xoa) == ["tai-lieu-28.pdf", "tai-lieu-29.pdf"]
    assert len(os.listdir(kho)) == 28
    cach_ly = [f for _, _, cac in os.walk(tmp_path / "da_go") for f in cac]
    assert sorted(cach_ly) == ["tai-lieu-28.pdf", "tai-lieu-29.pdf"]
