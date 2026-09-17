"""Sổ ghi chép phải mô tả đúng tệp trên đĩa sau khi kho được chép sang máy khác.

tar và zip chỉ giữ mtime tới giây, nên đẩy kho lên VPS làm lệch phần lẻ của
modified_ns dù nội dung y nguyên. Trước đây giao diện so từng nano giây nên cả
kho hiện "Chờ cập nhật" vĩnh viễn: trình cập nhật so bằng hash, thấy không có
việc để làm nên không bao giờ ghi lại sổ.
"""

import json
import os
import tempfile
import unittest
import unittest.mock as mock

import capnhat_tailieu_moi
import rag_service
from chunking_utils import tinh_hash_file


class DungSaiMtimeTests(unittest.TestCase):
    """Lệch mtime trong phạm vi làm tròn của tar/zip không phải là tệp đã sửa."""

    def test_lech_duoi_nguong_van_coi_la_khop(self):
        ban_ghi = {"size": 100, "modified_ns": 1_700_000_000_500_000_000}
        self.assertFalse(
            rag_service.ban_ghi_lech_tep(ban_ghi, 100, 1_700_000_000_000_000_000)
        )

    def test_lech_qua_nguong_la_tep_khac(self):
        ban_ghi = {"size": 100, "modified_ns": 1_700_000_000_000_000_000}
        self.assertTrue(
            rag_service.ban_ghi_lech_tep(ban_ghi, 100, 1_700_000_100_000_000_000)
        )

    def test_khac_kich_thuoc_luon_la_tep_khac(self):
        ban_ghi = {"size": 100, "modified_ns": 1_700_000_000_000_000_000}
        self.assertTrue(
            rag_service.ban_ghi_lech_tep(ban_ghi, 101, 1_700_000_000_000_000_000)
        )


class LamTuoiSoGhiChepTests(unittest.TestCase):
    """Tệp không đổi nội dung phải được ghi lại dấu thời gian hiện tại."""

    def setUp(self):
        self.thu_muc = tempfile.TemporaryDirectory()
        self.addCleanup(self.thu_muc.cleanup)
        self.kho = os.path.join(self.thu_muc.name, "data_giao_duc")
        os.makedirs(self.kho)
        # Chỉ cần thư mục tồn tại: lượt chạy này dừng trước khi load FAISS.
        self.index = os.path.join(self.thu_muc.name, "faiss_index")
        os.makedirs(self.index)
        self.so_ghi_chep = os.path.join(self.thu_muc.name, "so_ghi_chep.json")

        self.tai_lieu = os.path.join(self.kho, "quy-che.txt")
        with open(self.tai_lieu, "w", encoding="utf-8") as tep:
            tep.write("Quy chế đào tạo dùng cho kiểm thử.")

        duong_dan = mock.patch.multiple(
            "capnhat_tailieu_moi",
            DATA_PATH=self.kho,
            DUONG_DAN_LUU_INDEX=self.index,
            DUONG_DAN_SO_GHI_CHEP=self.so_ghi_chep,
        )
        duong_dan.start()
        self.addCleanup(duong_dan.stop)

    def _ghi_so(self, ban_ghi: dict) -> None:
        with open(self.so_ghi_chep, "w", encoding="utf-8") as tep:
            json.dump({self.tai_lieu: ban_ghi}, tep, ensure_ascii=False)

    def _doc_so(self) -> dict:
        with open(self.so_ghi_chep, encoding="utf-8") as tep:
            return json.load(tep)[self.tai_lieu]

    def test_mtime_lech_duoc_ghi_lai_du_khong_co_gi_de_embed(self):
        thong_tin = os.stat(self.tai_lieu)
        self._ghi_so({
            "hash": tinh_hash_file(self.tai_lieu),
            "chunk_ids": ["abc"],
            "status": "processed",
            "size": thong_tin.st_size,
            # Đúng như tar để lại: cùng giây, mất phần lẻ.
            "modified_ns": thong_tin.st_mtime_ns // 1_000_000_000 * 1_000_000_000,
        })

        capnhat_tailieu_moi.main()

        ban_ghi = self._doc_so()
        self.assertEqual(ban_ghi["modified_ns"], thong_tin.st_mtime_ns)
        self.assertEqual(ban_ghi["status"], "processed")
        self.assertEqual(ban_ghi["chunk_ids"], ["abc"])

    def test_khong_ghi_lai_khi_so_da_khop(self):
        thong_tin = os.stat(self.tai_lieu)
        self._ghi_so({
            "hash": tinh_hash_file(self.tai_lieu),
            "chunk_ids": ["abc"],
            "status": "processed",
            "size": thong_tin.st_size,
            "modified_ns": thong_tin.st_mtime_ns,
        })
        mtime_so_truoc = os.stat(self.so_ghi_chep).st_mtime_ns

        capnhat_tailieu_moi.main()

        self.assertEqual(os.stat(self.so_ghi_chep).st_mtime_ns, mtime_so_truoc)


if __name__ == "__main__":
    unittest.main()
