"""Chặn câu hỏi chửi thề, tục tĩu, 18+ mà không chặn nhầm câu hỏi học tập.

Hai kiểu hỏng cần chốt chặn, và kiểu thứ hai nguy hiểm hơn:
  - Bỏ sót: viết lách luật ("đ.ị.t", "l0z", "vcllll") lọt qua bộ lọc.
  - Chặn nhầm: bỏ dấu đi thì "lồn" thành "lon", "cặc" thành "các", "buồi"
    thành "buổi", "đéo" thành "đeo". Một bộ lọc chặn "Các môn học lớp 10" hay
    "Lịch buổi học" thì làm hỏng chính việc trợ lý sinh ra để làm, mà người
    dùng chỉ thấy bị mắng vô cớ chứ không biết vì sao.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import loc_tu_ngu

FILE_JS = Path(__file__).resolve().parent.parent / "static" / "loc-tu-ngu.js"

# (câu, nhóm phải báo)
CAU_VI_PHAM = [
    ("Địt mẹ mày", "chui_the"),
    ("ĐỤ MÁ cái hệ thống này", "chui_the"),
    ("đéo hiểu gì cả", "chui_the"),
    ("deo hieu gi het", "chui_the"),
    ("dcm trả lời sai rồi", "chui_the"),
    ("vcl thật", "chui_the"),
    ("clgt", "chui_the"),
    ("fuck this bot", "chui_the"),
    ("cái lồn gì vậy", "tuc_tiu"),
    ("cho xem phim sex", "tinh_duc"),
    ("phim heo ở đâu", "tinh_duc"),
    ("thằng ngu này", "xuc_pham"),
    ("đồ óc chó", "xuc_pham"),
]

# Viết lách: dấu câu, khoảng trắng chen giữa, lặp chữ, số thay chữ, ký tự
# vô hình, che bằng dấu *, chữ hoa, tổ hợp Unicode dạng tách (NFD, máy Mac).
CAU_VIET_LACH = [
    "đ.ị.t",
    "đ ị t m ẹ",
    "địttttt",
    "VCLLLLL",
    "cái l0z gì",
    "sh!t",
    "f*ck",
    "đ*t",
    "l​ồn",
    "v c l",
    "đmmmm",
    "đ.m.m",
]

# Câu học tập bình thường có chứa từ trùng với từ tục khi bỏ dấu, ghép chữ
# hoặc chữ hoa - mỗi câu từng là ứng viên chặn nhầm khi viết danh sách.
CAU_HOP_LE = [
    "Lịch buổi học tuần này",
    "Các môn học lớp 10",
    "con cac mon khac thi sao",          # còn các môn khác
    "an cac loai rau",                   # ăn các loại rau
    "đeo khẩu trang khi đến trường",
    "du lịch hè cho học sinh",
    "chích ngừa cho học sinh",
    "giải thích cho dễ hiểu",
    "giai thich cho de hieu",
    "tiền dư mà không dùng",
    "dù mẹ không cho phép",
    "du me khong cho phep",
    "lon nuoc ngot",
    "bù lon và đai ốc",
    "cái lồng chim",
    "đm tiết dạy giáo viên THPT",        # đm = định mức
    "1 dm bằng bao nhiêu cm",
    "VL 10 bài 3",
    "hạt óc chó có tốt không",
    "ốc lớn",
    "con chó của tôi",
    "đồ ngủ",
    "giáo dục giới tính lớp 8",
    "quan hệ tình dục an toàn",
    "sức khỏe sinh sản vị thành niên",
    "xử lý học sinh phát tán ảnh nóng",
    "Luật Trẻ em cấm văn hóa phẩm khiêu dâm",
    "chương trình cấp ba",
    "C++ là gì",
    "lớp 10a1",
    "classic assessment",
    "Cocktail party",
]


class LocTuNguTests(unittest.TestCase):
    def test_chan_tu_vi_pham_va_bao_dung_nhom(self):
        for cau, nhom in CAU_VI_PHAM:
            with self.subTest(cau=cau):
                ket_qua = loc_tu_ngu.kiem_tra(cau)
                self.assertTrue(ket_qua.vi_pham)
                self.assertIn(nhom, ket_qua.nhom)

    def test_chan_cach_viet_lach(self):
        for cau in CAU_VIET_LACH:
            with self.subTest(cau=cau):
                self.assertTrue(loc_tu_ngu.co_tu_ngu_khong_phu_hop(cau))

    def test_khong_chan_nham_cau_hoc_tap(self):
        for cau in CAU_HOP_LE:
            with self.subTest(cau=cau):
                ket_qua = loc_tu_ngu.kiem_tra(cau)
                self.assertFalse(ket_qua.vi_pham, ket_qua.tu_khop)

    def test_nfd_cung_bi_chan(self):
        import unicodedata
        self.assertTrue(loc_tu_ngu.co_tu_ngu_khong_phu_hop(
            unicodedata.normalize("NFD", "địt mẹ")
        ))

    def test_cau_rong(self):
        self.assertFalse(loc_tu_ngu.kiem_tra("").vi_pham)
        self.assertFalse(loc_tu_ngu.kiem_tra("   ...  ").vi_pham)

    def test_danh_sach_khong_dau_that_su_khong_dau(self):
        """Mục có dấu lọt vào TU_KHONG_DAU sẽ không bao giờ khớp, vì góc nhìn
        không dấu đã thay mọi chữ có dấu bằng ô trống - hỏng lặng lẽ."""
        from can_cu_van_ban import bo_dau
        for nhom, cac_tu in loc_tu_ngu.TU_KHONG_DAU.items():
            for tu in cac_tu:
                with self.subTest(nhom=nhom, tu=tu):
                    self.assertEqual(bo_dau(tu), tu)

    def test_tat_bang_bien_moi_truong(self):
        with patch.dict("os.environ", {"RAG_LOC_TU_NGU": "0"}):
            self.assertFalse(loc_tu_ngu.dang_bat())
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("RAG_LOC_TU_NGU", None)
            self.assertTrue(loc_tu_ngu.dang_bat())


class TuChoiTrongLuotHoiTests(unittest.TestCase):
    """Câu vi phạm không được đi tới truy hồi hay mô hình."""

    def test_stream_answer_tu_choi_truoc_khi_sinh(self):
        from rag_service import service

        with patch.object(service, "_sinh_cau_tra_loi") as sinh, \
                patch.dict("os.environ", {"RAG_LOC_TU_NGU": "1"}):
            su_kien = list(service.stream_answer("đ.m.m trả lời đi"))
        sinh.assert_not_called()
        self.assertEqual(
            [e["type"] for e in su_kien], ["sources", "token", "goi_y", "done"]
        )
        self.assertEqual(su_kien[1]["content"], loc_tu_ngu.LOI_NHAC)
        self.assertTrue(su_kien[-1]["abstained"])
        self.assertTrue(su_kien[-1]["ly_do_chan"].startswith("tu_ngu_khong_phu_hop"))

    def test_tat_loc_thi_cau_di_tiep(self):
        from rag_service import service

        with patch.object(service, "_sinh_cau_tra_loi", return_value=iter([])) as sinh, \
                patch.dict("os.environ", {"RAG_LOC_TU_NGU": "0"}):
            list(service.stream_answer("vcl"))
        sinh.assert_called_once()


class GiaoDienTests(unittest.TestCase):
    """static/loc-tu-ngu.js là bản port tay của loc_tu_ngu.py. Hai bản lệch
    nhau thì giao diện chặn câu máy chủ cho qua (người dùng bị giữ câu vô cớ)
    hoặc ngược lại - nên chạy cùng bộ câu qua cả hai và so từng câu."""

    def test_endpoint_tra_danh_sach(self):
        from fastapi.testclient import TestClient
        from api import app

        du_lieu = TestClient(app).get("/api/loc-tu-ngu").json()
        self.assertEqual(du_lieu["co_dau"].keys(), loc_tu_ngu.TU_CO_DAU.keys())
        self.assertIn("hop_le", du_lieu)

    @unittest.skipUnless(shutil.which("node"), "cần Node.js để chạy bản JS")
    def test_ban_js_cho_cung_ket_qua_voi_python(self):
        import unicodedata
        cac_cau = (
            [cau for cau, _ in CAU_VI_PHAM] + CAU_VIET_LACH + CAU_HOP_LE
            + [unicodedata.normalize("NFD", "địt mẹ"), "", "  ...  ",
               "đ.m.m trả lời đi", "d.c.m.m", "l ồ n g", "đmmmm", "hạt óc chó"]
        )
        dau_vao = json.dumps({
            "du_lieu": loc_tu_ngu.du_lieu_cho_giao_dien() | {"bat": True},
            "cac_cau": cac_cau,
        }, ensure_ascii=False)
        ma_node = (
            "const L = require(process.argv[1]);"
            "let s = ''; process.stdin.on('data', (d) => { s += d; });"
            "process.stdin.on('end', () => { const v = JSON.parse(s);"
            " L.nap(v.du_lieu);"
            " console.log(JSON.stringify(v.cac_cau.map((c) => L.kiemTra(c)))); });"
        )
        chay = subprocess.run(
            ["node", "-e", ma_node, str(FILE_JS)], input=dau_vao,
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(chay.returncode, 0, chay.stderr)
        ket_qua_js = json.loads(chay.stdout)
        for cau, js in zip(cac_cau, ket_qua_js):
            py = loc_tu_ngu.kiem_tra(cau)
            with self.subTest(cau=cau):
                self.assertEqual(js["viPham"], py.vi_pham)
                self.assertEqual(tuple(js["nhom"]), py.nhom)

    @unittest.skipUnless(shutil.which("node"), "cần Node.js để chạy bản JS")
    def test_tat_loc_thi_giao_dien_khong_chan(self):
        ma_node = (
            "const L = require(process.argv[1]);"
            "L.nap({bat: false, co_dau: {a: ['địt']}, khong_dau: {}});"
            "console.log(JSON.stringify([L.dangBat(), L.kiemTra('địt').viPham]));"
        )
        chay = subprocess.run(
            ["node", "-e", ma_node, str(FILE_JS)],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(chay.returncode, 0, chay.stderr)
        self.assertEqual(json.loads(chay.stdout), [False, False])


class TuQuanTriThemTests(unittest.TestCase):
    """Từ quản trị viên thêm qua giao diện: có hiệu lực ngay, đi đúng danh
    sách có dấu / không dấu, và không lưu được dạng sẽ không bao giờ khớp."""

    def test_them_co_hieu_luc_ngay_va_xoa_la_bo_chan(self):
        self.assertFalse(loc_tu_ngu.kiem_tra("đồ khỉ gió").vi_pham)
        muc = loc_tu_ngu.them_tu("Khỉ Gió", "xuc_pham", {"ten": "Cô Lan"})
        self.assertEqual(muc["tu"], "khỉ gió")
        self.assertEqual(muc["tao_boi"], "Cô Lan")
        ket_qua = loc_tu_ngu.kiem_tra("đồ khỉ gió")
        self.assertTrue(ket_qua.vi_pham)
        self.assertEqual(ket_qua.nhom, ("xuc_pham",))
        self.assertTrue(loc_tu_ngu.kiem_tra("đồ KHỈ GIÓÓÓÓ").vi_pham)
        loc_tu_ngu.xoa_tu(muc["id"])
        self.assertFalse(loc_tu_ngu.kiem_tra("đồ khỉ gió").vi_pham)

    def test_tu_luu_ben_vung_qua_lan_mo_lai(self):
        loc_tu_ngu.them_tu("khỉ gió", "xuc_pham")
        loc_tu_ngu.dong_ket_noi()  # như khởi động lại máy chủ
        self.assertTrue(loc_tu_ngu.kiem_tra("khỉ gió").vi_pham)

    def test_tu_co_dau_khong_chan_ban_khong_dau_va_nguoc_lai(self):
        loc_tu_ngu.them_tu("khỉ gió", "xuc_pham")
        self.assertFalse(loc_tu_ngu.kiem_tra("khi gio").vi_pham)
        loc_tu_ngu.them_tu("dmvl", "chui_the")
        self.assertTrue(loc_tu_ngu.kiem_tra("dmvl").vi_pham)
        muc = loc_tu_ngu.danh_sach_tu_them()
        self.assertEqual({m["tu"]: m["khong_dau"] for m in muc}, {"khỉ gió": False, "dmvl": True})

    def test_tu_moi_vao_danh_sach_cho_giao_dien(self):
        loc_tu_ngu.them_tu("dmvl", "chui_the")
        self.assertIn("dmvl", loc_tu_ngu.du_lieu_cho_giao_dien()["khong_dau"]["chui_the"])

    def test_tu_choi_tu_khong_hop_le(self):
        for tu, nhom in [
            ("đ.m", "chui_the"),      # dấu chấm bị chuẩn hoá thành khoảng trắng
            ("l0n", "tuc_tiu"),       # "0" kẹp giữa chữ thành "o": sẽ chặn "lon"
            ("a", "chui_the"),        # quá ngắn
            ("123", "chui_the"),      # không có chữ
            ("x" * 61, "chui_the"),   # quá dài
            ("hạt óc chó", "xuc_pham"),  # đang là cụm hợp lệ
            ("khỉ gió", "khong_co"),  # nhóm lạ
        ]:
            with self.subTest(tu=tu), self.assertRaises(loc_tu_ngu.LoiTuNgu):
                loc_tu_ngu.them_tu(tu, nhom)
        self.assertEqual(loc_tu_ngu.danh_sach_tu_them(), [])

    def test_khong_them_trung(self):
        with self.assertRaises(loc_tu_ngu.LoiTuNgu) as loi:
            loc_tu_ngu.them_tu("VCL", "chui_the")  # có sẵn
        self.assertEqual(loi.exception.ma_http, 409)
        loc_tu_ngu.them_tu("khỉ gió", "xuc_pham")
        with self.assertRaises(loc_tu_ngu.LoiTuNgu):
            loc_tu_ngu.them_tu("khỉ  gió", "chui_the")  # trùng sau chuẩn hoá

    def test_xem_truoc_dem_cau_ma_rieng_tu_moi_chan(self):
        cac_cau = ["Các môn học lớp 10", "cac mon hoc lop 10", "vcl", "cac ban oi"]
        kq = loc_tu_ngu.thu_tu_moi("cac", "tuc_tiu", cac_cau)
        self.assertTrue(kq["khong_dau"])
        # "vcl" vốn đã bị chặn nhưng không do từ này; "Các" có dấu không khớp.
        self.assertEqual(kq["so_cau_bi_chan"], 2)
        self.assertEqual(kq["vi_du"], ["cac mon hoc lop 10", "cac ban oi"])
        self.assertEqual(loc_tu_ngu.danh_sach_tu_them(), [])  # xem trước không lưu


class ApiQuanTriTuNguTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from api import app

        self.client = TestClient(app)

    def test_them_xem_truoc_thu_cau_xoa(self):
        import lich_su_chat

        lich_su_chat.ghi_luot(client_id="k", cau_hoi="cac mon hoc", tra_loi="x")
        kq = self.client.post("/api/quan-ly/tu-ngu/xem-truoc",
                              json={"tu": "cac", "nhom": "tuc_tiu"}).json()
        self.assertGreaterEqual(kq["so_cau_bi_chan"], 1)

        thieu_header = self.client.post("/api/quan-ly/tu-ngu", json={"tu": "dmvl", "nhom": "chui_the"})
        self.assertEqual(thieu_header.status_code, 403)
        moi = self.client.post(
            "/api/quan-ly/tu-ngu", json={"tu": "dmvl", "nhom": "chui_the"},
            headers={"X-RAG-Action": "them-tu-ngu"},
        ).json()["tu_ngu"]
        thu = self.client.post("/api/quan-ly/tu-ngu/thu-cau", json={"cau": "dmvl that"}).json()
        self.assertEqual(thu, {"vi_pham": True, "nhom": ["chui_the"], "tu_khop": ["dmvl"]})
        ds = self.client.get("/api/quan-ly/tu-ngu").json()
        self.assertEqual([m["tu"] for m in ds["them"]], ["dmvl"])
        self.assertIn("chui_the", ds["co_san"]["co_dau"])

        xoa = self.client.delete(f"/api/quan-ly/tu-ngu/{moi['id']}", headers={"X-RAG-Action": "xoa-tu-ngu"})
        self.assertEqual(xoa.status_code, 200)
        lai = self.client.delete(f"/api/quan-ly/tu-ngu/{moi['id']}", headers={"X-RAG-Action": "xoa-tu-ngu"})
        self.assertEqual(lai.status_code, 404)

    def test_loi_dau_vao_tra_400(self):
        r = self.client.post("/api/quan-ly/tu-ngu", json={"tu": "l0n", "nhom": "tuc_tiu"},
                             headers={"X-RAG-Action": "them-tu-ngu"})
        self.assertEqual(r.status_code, 400)

    def test_khach_khong_vao_duoc(self):
        with patch.dict("os.environ", {"RAG_KHOA_QUAN_TRI": "1"}):
            for phuong_thuc, duong_dan in [
                ("get", "/api/quan-ly/tu-ngu"),
                ("post", "/api/quan-ly/tu-ngu/xem-truoc"),
                ("post", "/api/quan-ly/tu-ngu/thu-cau"),
                ("post", "/api/quan-ly/tu-ngu"),
                ("delete", "/api/quan-ly/tu-ngu/abc"),
                ("get", "/api/quan-ly/tu-ngu/thong-ke"),
            ]:
                with self.subTest(duong_dan=duong_dan):
                    kwargs = {"json": {"tu": "dmvl", "nhom": "chui_the", "cau": "x"}} \
                        if phuong_thuc == "post" else {}
                    r = getattr(self.client, phuong_thuc)(
                        duong_dan, headers={"X-RAG-Action": "them-tu-ngu"}, **kwargs)
                    self.assertEqual(r.status_code, 401)
        self.assertEqual(loc_tu_ngu.danh_sach_tu_them(), [])


class ThongKeChanTests(unittest.TestCase):
    """Đếm số lần bị chặn theo nhóm, tách nguồn ô nhập / máy chủ."""

    def setUp(self):
        import api
        from fastapi.testclient import TestClient

        import lich_su_chat

        # Sổ lịch sử dùng chung cả phiên test (conftest): xoá bảng cho mỗi test.
        conn = lich_su_chat._connect()
        conn.execute("DELETE FROM chan_tu_ngu")
        conn.commit()
        api._bao_chan_gan_day.clear()
        self.api = api
        self.client = TestClient(api.app)

    def thong_ke(self, so_ngay=30):
        import lich_su_chat
        return lich_su_chat.thong_ke_chan_tu_ngu(so_ngay, list(loc_tu_ngu.NHOM))

    def test_dem_theo_nhom_nguon_vai_tro(self):
        import lich_su_chat

        lich_su_chat.ghi_chan_tu_ngu(["chui_the"], "giao_dien", "hoc_sinh")
        lich_su_chat.ghi_chan_tu_ngu(["chui_the", "tinh_duc"], "may_chu")
        kq = self.thong_ke()
        self.assertEqual(kq["so_lan"], 2)
        self.assertEqual(kq["theo_nguon"], {"giao_dien": 1, "may_chu": 1})
        # Đủ bốn nhóm, đúng thứ tự, kể cả nhóm 0 lần: biểu đồ không đổi chỗ thanh.
        self.assertEqual([n["nhom"] for n in kq["theo_nhom"]], list(loc_tu_ngu.NHOM))
        theo_nhom = {n["nhom"]: n for n in kq["theo_nhom"]}
        self.assertEqual(theo_nhom["chui_the"], {
            "nhom": "chui_the", "so_lan": 2, "giao_dien": 1, "may_chu": 1})
        self.assertEqual(theo_nhom["tinh_duc"]["so_lan"], 1)
        self.assertEqual(theo_nhom["tuc_tiu"]["so_lan"], 0)
        self.assertEqual(kq["theo_vai_tro"], [{"vai_tro": "hoc_sinh", "so_lan": 1},
                                              {"vai_tro": "", "so_lan": 1}])
        self.assertEqual(sum(n["so_lan"] for n in kq["theo_ngay"]), 2)

    def test_tat_luu_lich_su_thi_khong_dem(self):
        import lich_su_chat

        with patch.dict("os.environ", {"RAG_LUU_LICH_SU": "0"}):
            self.assertFalse(lich_su_chat.ghi_chan_tu_ngu(["chui_the"], "giao_dien"))
        self.assertEqual(self.thong_ke()["so_lan"], 0)

    def test_qua_han_giu_thi_xoa(self):
        import time
        import lich_su_chat

        lich_su_chat.ghi_chan_tu_ngu(["chui_the"], "giao_dien")
        lich_su_chat.xoa_qua_han(so_ngay=1, bay_gio=time.time() + 2 * 86400)
        self.assertEqual(self.thong_ke(3650)["so_lan"], 0)

    def test_giao_dien_bao_chan_may_chu_kiem_tra_lai(self):
        r = self.client.post("/api/loc-tu-ngu/bi-chan", json={"cau": "phim heo vcl", "vai_tro": "hoc_sinh"})
        self.assertEqual(r.json(), {"ghi": True})
        # Câu sạch (hoặc giao diện cũ chặn theo danh sách đã bị xoá) không được đếm.
        r = self.client.post("/api/loc-tu-ngu/bi-chan", json={"cau": "Các môn học lớp 10"})
        self.assertEqual(r.json(), {"ghi": False})
        kq = self.thong_ke()
        self.assertEqual(kq["so_lan"], 1)
        self.assertEqual(kq["theo_nguon"]["giao_dien"], 1)
        theo_nhom = {n["nhom"]: n["so_lan"] for n in kq["theo_nhom"]}
        self.assertEqual((theo_nhom["chui_the"], theo_nhom["tinh_duc"]), (1, 1))

    def test_gioi_han_so_lan_bao_moi_phut(self):
        for _ in range(self.api.SO_BAO_CHAN_MOI_PHUT + 5):
            self.client.post("/api/loc-tu-ngu/bi-chan", json={"cau": "vcl"})
        self.assertEqual(self.thong_ke()["so_lan"], self.api.SO_BAO_CHAN_MOI_PHUT)

    def test_cau_len_toi_may_chu_bi_chan_thi_dem_nguon_may_chu(self):
        from rag_service import service

        with patch.object(service, "hoi_kho_duoc", return_value=True):
            r = self.client.post("/api/chat/stream", json={"question": "đ.m.m trả lời đi"},
                                 headers={"X-RAG-Client": "khach-1"})
        self.assertIn(loc_tu_ngu.LOI_NHAC, r.text)
        kq = self.thong_ke()
        self.assertEqual(kq["theo_nguon"], {"giao_dien": 0, "may_chu": 1})

    def test_endpoint_quan_tri_va_thong_ke_chung(self):
        self.client.post("/api/loc-tu-ngu/bi-chan", json={"cau": "vcl"})
        kq = self.client.get("/api/quan-ly/tu-ngu/thong-ke?so_ngay=7").json()
        self.assertEqual((kq["so_ngay"], kq["so_lan"]), (7, 1))
        chung = self.client.get("/api/thong-ke").json()
        self.assertEqual(chung["tu_ngu_bi_chan"]["so_lan"], 1)


if __name__ == "__main__":
    unittest.main()
