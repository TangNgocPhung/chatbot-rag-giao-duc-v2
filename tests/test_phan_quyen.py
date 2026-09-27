"""Phân quyền theo vai: khách chỉ hỏi; tài khoản chưa xác minh email xem thêm
được kho chung; đã xác minh thì có sổ tay và tải tệp lên hỏi; quản trị viên
được tất cả."""

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import tai_khoan
from api import app
from rag_service import service
from tep_dinh_kem import kho_tep

MAT_KHAU = "matkhau-rat-dai-1"
NOI_DUNG = (
    "Ôn tập chương 3: hàm số bậc nhất, đồ thị và ứng dụng trong các bài toán "
    "thực tế về chuyển động và chi phí."
).encode("utf-8")
CHI_XEM_KHO = {"xem_kho": True, "so_tay": False, "tai_tep": False}


@pytest.fixture(autouse=True)
def co_so_du_lieu_moi(tmp_path, monkeypatch):
    monkeypatch.setattr(tai_khoan, "DUONG_DAN_DB", str(tmp_path / "tai_khoan.db"))
    monkeypatch.delenv("RAG_EMAIL_QUAN_TRI", raising=False)
    monkeypatch.setenv("RAG_KHOA_QUAN_TRI", "1")
    tai_khoan.dong_ket_noi()
    yield
    tai_khoan.dong_ket_noi()


def dang_ky(email, xac_minh=False):
    client = TestClient(app)
    nd = client.post("/api/tai-khoan/dang-ky", json={"email": email, "mat_khau": MAT_KHAU}).json()["nguoi_dung"]
    if xac_minh:
        tai_khoan.xac_minh_ho(nd["id"])
    return client, nd


@pytest.fixture
def bon_vai():
    quan_tri, _ = dang_ky("qt@x.vn")  # tài khoản đầu tiên là quản trị
    chua_xac_minh, _ = dang_ky("chua@x.vn")
    da_xac_minh, _ = dang_ky("roi@x.vn", xac_minh=True)
    return {
        "khach": TestClient(app),
        "chua_xac_minh": chua_xac_minh,
        "da_xac_minh": da_xac_minh,
        "quan_tri": quan_tri,
    }


@pytest.fixture
def don_tep():
    """Tệp tải lên trong test: đợi đọc xong rồi xoá."""
    cac_id = []
    yield cac_id
    for tep_id in cac_id:
        het = time.monotonic() + 20
        while (tep := kho_tep.lay(tep_id)) and tep.trang_thai == "dang_xu_ly" and time.monotonic() < het:
            time.sleep(0.05)
        kho_tep.xoa(tep_id, kiem_chu=False)


def test_quyen_cua_theo_vai():
    assert tai_khoan.quyen_cua(None) == dict.fromkeys(tai_khoan.QUYEN, False)
    assert tai_khoan.quyen_cua({"quan_tri": False, "da_xac_minh": False}) == CHI_XEM_KHO
    assert tai_khoan.quyen_cua({"quan_tri": False, "da_xac_minh": True}) == dict.fromkeys(tai_khoan.QUYEN, True)
    assert tai_khoan.quyen_cua({"quan_tri": True, "da_xac_minh": False}) == dict.fromkeys(tai_khoan.QUYEN, True)


def test_tat_khoa_quan_tri_thi_khach_du_quyen(monkeypatch):
    """Máy cá nhân một người dùng (RAG_KHOA_QUAN_TRI=0) giữ hành vi cũ."""
    monkeypatch.setenv("RAG_KHOA_QUAN_TRI", "0")
    assert tai_khoan.quyen_cua(None) == dict.fromkeys(tai_khoan.QUYEN, True)


def test_tai_khoan_gui_kem_quyen_cho_giao_dien(bon_vai):
    toi = lambda vai: bon_vai[vai].get("/api/tai-khoan/toi").json()["nguoi_dung"]  # noqa: E731
    assert toi("khach") is None
    assert toi("chua_xac_minh")["quyen"] == CHI_XEM_KHO
    assert all(toi("da_xac_minh")["quyen"].values())
    assert all(toi("quan_tri")["quyen"].values())


def test_doi_email_thi_mat_quyen_toi_khi_xac_minh_lai():
    tai_khoan.dang_ky("qt@x.vn", MAT_KHAU)
    nd = tai_khoan.dang_ky("a@x.vn", MAT_KHAU)
    tai_khoan.xac_minh_ho(nd["id"])
    assert all(tai_khoan.lay_nguoi_dung(nd["id"])["quyen"].values())
    assert tai_khoan.doi_thong_tin(nd["id"], email="b@x.vn", mat_khau=MAT_KHAU)["quyen"] == CHI_XEM_KHO


def test_chi_khach_khong_xem_duoc_kho_chung(bon_vai):
    with patch.object(service, "document_inventory", return_value={"documents": [], "summary": {}}), \
            patch.object(service, "resolve_source_file", return_value=None):
        for vai, client in bon_vai.items():
            khach = vai == "khach"
            assert client.get("/api/documents").status_code == (401 if khach else 200), vai
            # 404: đã qua cửa quyền, chỉ là kho không có tệp tên đó.
            for duong_dan in ("/api/source?name=khong-co.pdf", "/api/doc/thong-tin?nguon=khong-co.pdf",
                              "/api/doc/trang?so=1&nguon=khong-co.pdf"):
                assert client.get(duong_dan).status_code == (401 if khach else 404), (vai, duong_dan)
    assert bon_vai["khach"].get("/api/documents").json()["detail"] == "Hãy đăng nhập để xem kho tài liệu."


def test_so_tay_chi_cho_email_da_xac_minh(bon_vai):
    ky_vong = {"khach": 401, "chua_xac_minh": 403, "da_xac_minh": 200, "quan_tri": 200}
    ban = {"id": "hoi-thoai-0001", "ghiChu": "<p>Ghi chú</p>", "bang": []}
    vung = {"nguon": "khong-co.pdf", "so": 1, "x0": 0, "y0": 0, "x1": 0.5, "y1": 0.5}
    with patch.object(service, "resolve_source_file", return_value=None):
        for vai, client in bon_vai.items():
            ma = ky_vong[vai]
            assert client.put("/api/so-tay/hoi-thoai-0001", json=ban).status_code == ma, vai
            assert client.get("/api/so-tay/hoi-thoai-0001").status_code == ma, vai
            # Khoanh vùng trong trình đọc cũng là một phần của sổ tay.
            assert client.post("/api/doc/vung", json=vung).status_code == (404 if ma == 200 else ma), vai
    phan_hoi = bon_vai["chua_xac_minh"].get("/api/so-tay/hoi-thoai-0001")
    assert phan_hoi.json()["detail"] == "Hãy xác minh email để dùng sổ tay."


def test_tai_tep_len_chi_cho_email_da_xac_minh(bon_vai, don_tep):
    ky_vong = {"khach": 401, "chua_xac_minh": 403, "da_xac_minh": 200, "quan_tri": 200}
    for vai, client in bon_vai.items():
        phan_hoi = client.post(
            "/api/tep?ten=on-tap.txt", content=NOI_DUNG,
            headers={"X-RAG-Action": "upload-file", "X-RAG-Client": f"trinh-duyet-{vai}"},
        )
        assert phan_hoi.status_code == ky_vong[vai], vai
        if phan_hoi.status_code == 200:
            don_tep.append(phan_hoi.json()["id"])
    # Nút "+" trong kho: người thường thì thành tài liệu riêng, cũng là tải tệp lên.
    for vai in ("khach", "chua_xac_minh", "da_xac_minh"):
        phan_hoi = bon_vai[vai].post(
            "/api/kho/tep?ten=on-tap-2.txt", content=NOI_DUNG, headers={"X-RAG-Action": "upload-library"},
        )
        assert phan_hoi.status_code == ky_vong[vai], vai
        if phan_hoi.status_code == 200:
            don_tep.append(phan_hoi.json()["tep"]["id"])


def test_khach_van_hoi_duoc_nhung_khong_hoi_ve_tep(bon_vai):
    trang_thai = service.status.state
    service.status.state = "ready"
    try:
        with patch.object(service, "stream_answer", side_effect=lambda *a, **k: iter([{"type": "done"}])) as hoi:
            phan_hoi = bon_vai["khach"].post(
                "/api/chat/stream", json={"question": "Hàm số bậc nhất là gì?"},
                headers={"X-RAG-Client": "trinh-duyet-khach"},
            )
            assert phan_hoi.status_code == 200
            for vai, ma in (("khach", 401), ("chua_xac_minh", 403)):
                phan_hoi = bon_vai[vai].post(
                    "/api/chat/stream", json={"question": "Tệp này nói gì?", "tep_ids": ["tep-bat-ky"]},
                )
                assert phan_hoi.status_code == ma, vai
        assert hoi.call_count == 1
    finally:
        service.status.state = trang_thai


def test_quan_tri_xac_minh_ho(bon_vai):
    _, nd = dang_ky("moi@x.vn")
    duong_dan = f"/api/quan-ly/tai-khoan/{nd['id']}/xac-minh"
    assert bon_vai["da_xac_minh"].post(duong_dan, headers={"X-RAG-Action": "xac-minh-ho"}).status_code == 403
    assert bon_vai["quan_tri"].post(duong_dan).status_code == 403  # thiếu header hành động
    phan_hoi = bon_vai["quan_tri"].post(duong_dan, headers={"X-RAG-Action": "xac-minh-ho"})
    assert phan_hoi.status_code == 200
    assert phan_hoi.json()["tai_khoan"]["da_xac_minh"] is True
    assert all(tai_khoan.lay_nguoi_dung(nd["id"])["quyen"].values())


def test_khong_xac_minh_ho_email_chi_dinh_quan_tri(monkeypatch):
    """Kẻ lạ đăng ký trước bằng email quản trị: bấm xác minh hộ không được
    biến tài khoản đó thành quản trị viên."""
    monkeypatch.setenv("RAG_EMAIL_QUAN_TRI", "admin@x.vn")
    with patch("gui_thu.da_cau_hinh", return_value=True):
        nd = tai_khoan.dang_ky("admin@x.vn", MAT_KHAU)
        with pytest.raises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.xac_minh_ho(nd["id"])
        assert loi.value.ma_http == 409
        assert not tai_khoan.lay_nguoi_dung(nd["id"])["quan_tri"]
