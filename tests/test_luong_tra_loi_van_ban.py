"""Chạy trọn _sinh_cau_tra_loi với mô hình giả: các lớp xử lý văn bản quy phạm
(chuyển tiếp, hết hiệu lực dây chuyền, tham chiếu chéo, thứ bậc, đối tượng áp
dụng, so sánh phiên bản) phải tới được prompt, cảnh báo và gợi ý."""

import contextlib
import unittest
from unittest import mock

from langchain_core.documents import Document

import hieu_luc_bo_sung as hl
import quan_he_van_ban as qh
import van_ban_meta as vm

DAU = "BỘ GIÁO DỤC VÀ ĐÀO TẠO\nSố: {} Hà Nội, ngày {}\nTHÔNG TƯ\nCăn cứ Luật;\nĐiều 1. Phạm vi\n{}"
NOI_DUNG = {
    "tt08.pdf": DAU.format(
        "08/2021/TT-BGDĐT", "18 tháng 3 năm 2021",
        "Quy chế đào tạo trình độ đại học.\nĐiều 2. Hiệu lực thi hành\n1. Thông tư này có hiệu lực thi hành từ "
        "ngày 03 tháng 5 năm 2021 và thay thế Quyết định số 43/2007/QĐ-BGDĐT.\n2. Các khóa tuyển sinh trước "
        "ngày Thông tư này có hiệu lực thi hành tiếp tục thực hiện theo quy định cũ.",
    ),
    "qd43.pdf": DAU.format("43/2007/QĐ-BGDĐT", "15 tháng 8 năm 2007", "Quy chế đào tạo theo tín chỉ."),
    "cv.pdf": DAU.format("1234/BGDĐT-GDĐH", "5 tháng 1 năm 2026", "Hướng dẫn đăng ký học phần."),
}


def chunk(ten, tieu_de, than, cap_hoc=None):
    md = {"source_file": ten, "article": tieu_de}
    if cap_hoc:
        md["cap_hoc"] = cap_hoc
    return Document(page_content=f"{tieu_de}\n{than}", metadata=md)


CHUNK = {
    "tt08.pdf": [
        chunk("tt08.pdf", "Điều 2. Giải thích từ ngữ",
              "1. Cố vấn học tập là giảng viên được phân công hỗ trợ sinh viên trong học tập."),
        chunk("tt08.pdf", "Điều 8. Đăng ký học phần",
              "1. Sinh viên đại học được đăng ký tối đa 25 tín chỉ, trừ trường hợp quy định tại khoản 2 "
              "Điều 9 Quy chế này. Cố vấn học tập duyệt đăng ký."),
        chunk("tt08.pdf", "Điều 9. Ngoại lệ", "1. Học kỳ phụ.\n2. Sinh viên năm cuối được đăng ký tối đa 30 tín chỉ."),
    ],
    "qd43.pdf": [
        chunk("qd43.pdf", "Điều 2. Giải thích từ ngữ",
              "1. Cố vấn học tập là giảng viên được phân công hỗ trợ sinh viên trong học tập."),
        chunk("qd43.pdf", "Điều 7. Đăng ký học phần",
              "1. Sinh viên đại học được đăng ký tối đa 24 tín chỉ, trừ trường hợp quy định tại khoản 2 "
              "Điều 9 Quy chế này. Cố vấn học tập duyệt đăng ký."),
    ],
    "cv.pdf": [chunk("cv.pdf", "Điều 1. Hướng dẫn", "Trường cao đẳng sư phạm cho đăng ký tối đa 20 tín chỉ.")],
}


class ChuoiGia:
    """Thay chuỗi LLM: ghi lại prompt, trả về một câu cố định."""

    def __init__(self):
        self.dau_vao = None


def dich_vu():
    from main import tao_rag_chain
    from rag_service import RAGService

    ho_so = vm.xay_dung_ho_so(NOI_DUNG)
    service = RAGService.__new__(RAGService)
    service.so_quan_he = qh.SoQuanHe(ho_so, hl.xay_dung(NOI_DUNG, ho_so), so_tay={})
    service.ho_so_van_ban = ho_so
    service.tinh_trang_hieu_luc = {}
    service._doan_theo_tep = CHUNK
    service.phan_loai = {}
    service.tu_vung = None
    service.embeddings = None
    service.llm_model = "gia"
    service.huy_sinh = mock.Mock(is_set=lambda: False)
    _, service.format_docs = tao_rag_chain(None, lambda _: "")
    return service


def chay(service, cau_hoi, docs):
    chuoi = ChuoiGia()

    def phat_token(_, dau_vao):
        chuoi.dau_vao = dau_vao
        yield "Trả lời [1]."

    with contextlib.ExitStack() as ngan:
        ngan.enter_context(mock.patch.object(type(service), "hoi_kho_duoc", return_value=True))
        ngan.enter_context(mock.patch.object(type(service), "_retrieve", return_value=docs))
        ngan.enter_context(mock.patch.object(type(service), "_luot_sinh_tep", contextlib.nullcontext))
        ngan.enter_context(mock.patch.object(type(service), "_chain_tra_loi", return_value=None))
        ngan.enter_context(mock.patch.object(type(service), "_phat_token", side_effect=phat_token, autospec=False))
        ngan.enter_context(mock.patch("kiem_tra_tra_loi.ly_do_bo_qua", return_value=None))
        su_kien = list(service._sinh_cau_tra_loi(cau_hoi, ten_mo_hinh="gia"))
    return su_kien, (chuoi.dau_vao or {}).get("context", "")


class LuongTraLoiTests(unittest.TestCase):
    def test_cac_lop_toi_duoc_prompt_canh_bao_va_goi_y(self):
        service = dich_vu()
        docs = [CHUNK["tt08.pdf"][1], CHUNK["cv.pdf"][0]]
        # "người học" không chọn cấp học (khác "sinh viên" - từ điển CAP_HOC coi
        # là Đại học); "cố vấn học tập" có trong câu hỏi nên định nghĩa đứng đầu.
        su_kien, ngu_canh = chay(
            service, "Cố vấn học tập cho người học đăng ký tối đa bao nhiêu tín chỉ?", docs
        )
        # Tham chiếu chéo: khoản 2 Điều 9 được kéo vào; định nghĩa "cố vấn học tập".
        self.assertIn("Đi kèm: Điều khoản được viện dẫn (khoản 2 Điều 9)", ngu_canh)
        self.assertIn("Định nghĩa thuật ngữ (Cố vấn học tập)", ngu_canh)
        # Thứ bậc: dòng Loại và quy tắc vì có công văn lẫn Thông tư.
        self.assertIn("Loại: Công văn - văn bản hành chính", ngu_canh)
        self.assertIn("THỨ BẬC VĂN BẢN", ngu_canh)
        # Chuyển tiếp: câu hỏi không nêu khóa -> nhắc nguyên văn điều khoản.
        self.assertIn("QUY ĐỊNH CHUYỂN TIẾP", ngu_canh)
        # Đối tượng áp dụng: Đại học [1] và Giáo dục nghề nghiệp (cao đẳng) [2].
        self.assertIn("PHẠM VI ÁP DỤNG", ngu_canh)
        canh_bao = [e for e in su_kien if e["type"] == "hieu_luc"]
        self.assertIn("chuyen_tiep", {e["kind"] for e in canh_bao})
        goi_y = next(e for e in su_kien if e["type"] == "goi_y")["goi_y"]
        self.assertTrue(goi_y[0].endswith("(Giáo dục nghề nghiệp)?") or goi_y[0].endswith("(Đại học)?"), goi_y)
        self.assertEqual(su_kien[-1]["type"], "done")

    def test_hoi_dung_khoa_cu_keo_van_ban_cu(self):
        service = dich_vu()
        _, ngu_canh = chay(
            service, "Sinh viên khóa tuyển sinh 2019 được đăng ký tối đa bao nhiêu tín chỉ?", [CHUNK["tt08.pdf"][1]]
        )
        self.assertIn("Đi kèm: Văn bản cũ còn áp dụng chuyển tiếp", ngu_canh)
        self.assertIn("Hết hiệu lực · còn áp dụng chuyển tiếp", ngu_canh)

    def test_phan_cap_toi_prompt_va_canh_bao(self):
        service = dich_vu()
        doan = Document(page_content=(
            "Điều 9. Học phí\nCăn cứ khung học phí, mức thu học phí cụ thể do Hội đồng nhân dân "
            "cấp tỉnh quyết định."
        ), metadata={"source_file": "nd81.pdf", "article": "Điều 9. Học phí"})
        su_kien, ngu_canh = chay(service, "Học phí trường công lập bao nhiêu một tháng?", [doan])
        self.assertIn("PHÂN CẤP: Khối [1]", ngu_canh)
        self.assertIn("phan_cap", {e["kind"] for e in su_kien if e["type"] == "hieu_luc"})

    def test_so_sanh_phien_ban_khong_goi_mo_hinh(self):
        service = dich_vu()
        su_kien, ngu_canh = chay(service, "Thông tư 08/2021 có gì mới so với bản cũ?", [])
        self.assertEqual(ngu_canh, "")
        van_ban = "".join(e["content"] for e in su_kien if e["type"] == "token")
        self.assertIn("24 tín chỉ → 25 tín chỉ", van_ban)
        self.assertEqual(su_kien[-1]["cong_cu"], "so_sanh_phien_ban")


if __name__ == "__main__":
    unittest.main()
