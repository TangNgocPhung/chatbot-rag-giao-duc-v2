"""Câu hỏi sau một câu bị dừng phải gửi được.

Lỗi gốc: bấm dừng trước khi có chữ nào thì trình duyệt lưu câu trả lời rỗng vào
lịch sử. Câu hỏi kế tiếp gửi kèm lượt rỗng đó, ChatMessage đòi nội dung ít nhất
một ký tự nên cả yêu cầu bị từ chối 422 và giao diện hiện "[object Object]".
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import ChatRequest, app
from rag_service import service


def tra_loi_ngan(question, history, tep_ids, pham_vi):
    yield {"type": "token", "content": f"da nhan {len(history)} luot"}
    yield {"type": "done", "elapsed_seconds": 0.1}


class LichSuRongTests(unittest.TestCase):
    def test_bo_luot_rong_thay_vi_tu_choi_ca_cau_hoi(self):
        yeu_cau = ChatRequest(
            question="đánh giá học sinh",
            history=[
                {"role": "user", "content": "đánh giá học sinh cấp"},
                {"role": "assistant", "content": ""},
                {"role": "assistant", "content": "   "},
            ],
        )
        self.assertEqual(
            [m.model_dump() for m in yeu_cau.history],
            [{"role": "user", "content": "đánh giá học sinh cấp"}],
        )

    def test_van_kiem_tra_cac_loi_khac_cua_lich_su(self):
        with self.assertRaises(ValidationError):
            ChatRequest(question="câu hỏi", history=[{"role": "system", "content": "x"}])

    def test_gui_duoc_qua_api_sau_cau_bi_dung(self):
        state_cu = service.status.state
        service.status.state = "ready"
        self.addCleanup(setattr, service.status, "state", state_cu)
        with patch.object(service, "stream_answer", tra_loi_ngan):
            phan_hoi = TestClient(app).post("/api/chat/stream", json={
                "question": "đánh giá học sinh",
                "history": [
                    {"role": "user", "content": "đánh giá học sinh cấp"},
                    {"role": "assistant", "content": ""},
                ],
            })
        self.assertEqual(phan_hoi.status_code, 200, phan_hoi.text)
        self.assertIn("da nhan 1 luot", phan_hoi.text)


if __name__ == "__main__":
    unittest.main()
