"""Dừng câu trả lời phải nhả được khoá sinh phía máy chủ.

Lỗi gốc: bấm "Cuộc trò chuyện mới", bấm dừng hay đóng tab thì trình duyệt chỉ
cắt kết nối. Bộ sinh chạy ngay trong luồng phát HTTP treo lại ở chỗ yield dở
dang - không ai gọi tiếp, cũng không ai đóng nó - nên khối "with khoá" không bao
giờ thoát: máy chủ báo "Đang xử lý một câu hỏi" mãi và mọi câu hỏi sau xếp hàng
vô hạn, phải khởi động lại dịch vụ mới hỏi tiếp được.

Test tự điều khiển dòng phát chứ không qua TestClient: TestClient gom trọn phản
hồi rồi mới trả về, nên không dựng lại được cảnh bên nhận bỏ đi giữa chừng -
đúng cái cảnh sinh ra lỗi này.
"""

import asyncio
import time
import unittest
from unittest.mock import patch

import api
from api import ChatRequest
from rag_service import service


def cho_den(dieu_kien, giay=10.0):
    het = time.monotonic() + giay
    while time.monotonic() < het:
        if dieu_kien():
            return True
        time.sleep(0.05)
    return dieu_kien()


def tra_loi_dai(question, history, tep_ids, pham_vi):
    """Giả một lượt sinh dài, giữ khoá đúng như bản thật."""
    service.huy_sinh.clear()
    with service._generation_lock:
        yield {"type": "sources", "sources": []}
        for _ in range(3000):
            yield {"type": "token", "content": "x"}
            time.sleep(0.01)
        yield {"type": "done", "elapsed_seconds": 30.0}


class DungTraLoiTests(unittest.TestCase):
    def setUp(self):
        self.state_cu = service.status.state
        service.status.state = "ready"
        service.huy_sinh.clear()
        self.vong = asyncio.new_event_loop()
        gia = patch.object(service, "stream_answer", tra_loi_dai)
        gia.start()
        self.addCleanup(gia.stop)

    def tearDown(self):
        service.huy_sinh.set()  # dọn luồng sinh nếu test hỏng giữa chừng
        da_nha = cho_den(lambda: not service._generation_lock.locked())
        self.vong.close()
        service.huy_sinh.clear()
        service.status.state = self.state_cu
        self.assertTrue(da_nha, "khoá sinh câu trả lời còn kẹt sau khi test xong")

    def _mo_dong(self):
        """Mở một lượt hỏi và đọc sự kiện đầu, lúc này máy chủ đang giữ khoá."""
        phan_hoi = api.chat_stream(ChatRequest(question="Câu hỏi thử"), None)
        dong = phan_hoi.body_iterator
        self._doc(dong)
        self.assertTrue(service._generation_lock.locked())
        return dong

    def _doc(self, dong):
        return self.vong.run_until_complete(dong.__anext__())

    def test_bam_dung_thi_nha_khoa(self):
        dong = self._mo_dong()
        self.assertEqual(api.chat_dung(), {"dung": True})

        bat_dau = time.monotonic()
        while True:  # đọc nốt phần đã sinh cho tới khi máy chủ đóng dòng
            try:
                self._doc(dong)
            except StopAsyncIteration:
                break
        self.assertLess(time.monotonic() - bat_dau, 10.0)
        self.assertFalse(service._generation_lock.locked())

    def test_tab_bo_di_giua_chung_cung_nha_khoa(self):
        han_cu = api.GIAY_CHO_BEN_NHAN
        api.GIAY_CHO_BEN_NHAN = 1.0  # rút ngắn để test khỏi chờ 20 giây
        try:
            dong = self._mo_dong()
            # Thôi đọc, và cũng không đóng: đúng cảnh cái tab bị đóng cái rụp.
            self.assertTrue(
                cho_den(lambda: not service._generation_lock.locked(), 15.0),
                "bỏ kết nối giữa chừng vẫn để lại khoá kẹt",
            )
            del dong
        finally:
            api.GIAY_CHO_BEN_NHAN = han_cu

    def test_dung_luc_rang_roi_khong_giet_cau_hoi_sau(self):
        self.assertEqual(api.chat_dung(), {"dung": False})
        self.assertFalse(service.huy_sinh.is_set())

        su_kien = iter([
            {"type": "token", "content": "Xong"},
            {"type": "done", "elapsed_seconds": 0.1},
        ])
        with patch.object(service, "stream_answer", return_value=su_kien):
            phan_hoi = api.chat_stream(ChatRequest(question="Câu hỏi kế tiếp"), None)
            dong = phan_hoi.body_iterator
            noi_dung = ""
            while True:
                try:
                    noi_dung += self._doc(dong)
                except StopAsyncIteration:
                    break
        self.assertIn("Xong", noi_dung)


if __name__ == "__main__":
    unittest.main()
