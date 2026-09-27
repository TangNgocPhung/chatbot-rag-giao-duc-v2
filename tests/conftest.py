"""
Cách ly test khỏi dữ liệu thật.

Chạy bộ test từng ghi thẳng vào lich_su_chat.db và cache_cau_tra_loi.json của
dự án - câu hỏi giả trong test lẫn vào thống kê vận hành, còn cache thì có thể
trả lại một câu trả lời giả cho người dùng thật. Chuyển hướng cả hai sang thư
mục tạm cho toàn bộ phiên chạy test.

Đặt trong conftest.py chứ không trong từng test: chỉ cần một test mới quên cách
ly là dữ liệu thật lại bị bẩn, mà kiểu quên đó không ai phát hiện ra ngay.
"""

import os
import tempfile

import pytest

import cache_ngu_nghia
import lich_su_chat
import tai_khoan


@pytest.fixture(autouse=True, scope="session")
def cach_ly_du_lieu_that():
    with tempfile.TemporaryDirectory(prefix="rag-test-") as thu_muc:
        db_that = lich_su_chat.DUONG_DAN_DB
        cache_that = cache_ngu_nghia.cache.duong_dan
        tai_khoan_that = tai_khoan.DUONG_DAN_DB

        lich_su_chat.DUONG_DAN_DB = os.path.join(thu_muc, "lich_su_test.db")
        lich_su_chat.dong_ket_noi()
        cache_ngu_nghia.cache.duong_dan = os.path.join(thu_muc, "cache_test.json")
        cache_ngu_nghia.cache._muc = []
        tai_khoan.DUONG_DAN_DB = os.path.join(thu_muc, "tai_khoan_test.db")
        tai_khoan.dong_ket_noi()
        try:
            yield
        finally:
            lich_su_chat.dong_ket_noi()
            lich_su_chat.DUONG_DAN_DB = db_that
            cache_ngu_nghia.cache.duong_dan = cache_that
            tai_khoan.dong_ket_noi()
            tai_khoan.DUONG_DAN_DB = tai_khoan_that


@pytest.fixture(autouse=True)
def cach_ly_quan_ly_kho(tmp_path, monkeypatch):
    """Sổ tệp gửi lên, hàng chờ duyệt và thùng rác của kho: mỗi test một bộ riêng."""
    import quan_ly_kho

    monkeypatch.setattr(quan_ly_kho, "DUONG_DAN_DB", str(tmp_path / "kho_tai_len.db"))
    monkeypatch.setattr(quan_ly_kho, "THU_MUC_CHO_DUYET", str(tmp_path / "kho_cho_duyet"))
    monkeypatch.setattr(quan_ly_kho, "THU_MUC_THUNG_RAC", str(tmp_path / "thung_rac_kho"))
    quan_ly_kho.dong_ket_noi()
    yield
    quan_ly_kho.dong_ket_noi()


@pytest.fixture(autouse=True)
def cach_ly_tep_dinh_kem(tmp_path, monkeypatch):
    """Tệp đính kèm giờ được ghi ra đĩa và nạp lại khi app khởi động: test
    không được đọc/ghi thư mục tep_dinh_kem thật của dự án."""
    import tep_dinh_kem

    monkeypatch.setattr(tep_dinh_kem, "THU_MUC_TEP", str(tmp_path / "tep_dinh_kem"))


@pytest.fixture(autouse=True)
def mo_khoa_quan_tri(monkeypatch):
    """Các test cũ gọi thẳng endpoint quản trị (cập nhật chỉ mục, đổi mô hình...)
    mà không đăng nhập. Chúng kiểm tra việc khác, nên tắt khoá quản trị cho
    chúng; test_tai_khoan.py tự bật lại để kiểm tra chính cái khoá đó."""
    monkeypatch.setenv("RAG_KHOA_QUAN_TRI", "0")
