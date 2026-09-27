"""Lượt bị dừng trước khi có chữ nào không được làm hỏng câu hỏi kế tiếp.

Lỗi gốc: bấm Dừng khi chưa có token thì trình duyệt lưu câu trả lời rỗng vào
lịch sử. Câu hỏi sau gửi kèm lịch sử đó, ChatMessage(min_length=1) từ chối, máy
chủ trả 422 với detail là mảng object và giao diện hiện "[object Object]".
"""

import unittest

from pydantic import ValidationError

from api import ChatRequest


class LichSuTinRongTests(unittest.TestCase):
    def test_bo_cau_tra_loi_rong_thay_vi_tu_choi(self):
        yeu_cau = ChatRequest(question="dịch sang tiếng Anh", history=[
            {"role": "user", "content": "Tóm tắt tệp này"},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "Tóm tắt lại"},
            {"role": "assistant", "content": "   \n"},
        ])
        self.assertEqual(
            [(tin.role, tin.content) for tin in yeu_cau.history],
            [("user", "Tóm tắt tệp này"), ("user", "Tóm tắt lại")],
        )

    def test_van_giu_tin_co_noi_dung(self):
        yeu_cau = ChatRequest(question="Hỏi tiếp", history=[
            {"role": "user", "content": "Câu hỏi"},
            {"role": "assistant", "content": "Câu trả lời"},
        ])
        self.assertEqual(len(yeu_cau.history), 2)

    def test_van_kiem_vai_tro_sai(self):
        with self.assertRaises(ValidationError):
            ChatRequest(question="Hỏi tiếp", history=[{"role": "system", "content": "x"}])


if __name__ == "__main__":
    unittest.main()
