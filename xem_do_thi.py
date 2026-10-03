"""Xem đồ thị quan hệ văn bản (sổ nhập tay) dạng tương tác.
Chạy từ thư mục gốc của repo:  python xem_do_thi.py   rồi mở do_thi.html bằng trình duyệt.
Cần:  pip install pyvis   (Python 3.9+)
"""
from datetime import date
from pyvis.network import Network
import quan_he_van_ban as qh

HOM_NAY = date.today()
so = qh.SoQuanHe(ho_so={}, tinh_trang={}, so_tay=qh.tai_so_tay())   # chính lớp dự án dùng

MAU_NUT = {"con_hieu_luc": "#2e9d62", "het_hieu_luc": "#d9534f", "het_mot_phan": "#f0a030",
           "da_sua_doi": "#e6c200", "sap_het_hieu_luc": "#8a63d2", "chua_hieu_luc": "#7f8c9a"}
MAU_CANH = {"thay_the": "#c0392b", "bai_bo_mot_phan": "#e67e22", "sua_doi": "#2c7fb8",
            "huong_dan": "#16a085", "kem_theo": "#7f8c9a"}

net = Network(height="900px", width="100%", directed=True, cdn_resources="in_line",
              notebook=False, bgcolor="#ffffff")
nut = {q.tu for q in so.quan_he} | {q.den for q in so.quan_he}
for n in sorted(nut):
    tt = so.tinh_trang_nut(n, HOM_NAY)
    ghi_chu = (so.thong_tin.get(n) or {}).get("ten_goi") or []
    net.add_node(n, label=n, color=MAU_NUT.get(tt["code"], "#7f8c9a"), size=14,
                 font={"size": 13, "color": "#222222", "face": "sans-serif"},
                 title=f"{so.nhan_nut(n)}\nTrạng thái: {tt['code']}\n{' / '.join(ghi_chu)}")
for q in so.quan_he:
    net.add_edge(q.tu, q.den, color=MAU_CANH.get(q.loai, "#999999"), title=f"{qh.TEN_QUAN_HE[q.loai][0]}\n{q.can_cu}")
# Chữ bị ẩn khi thu nhỏ quá mức mặc định; hạ ngưỡng để luôn thấy số hiệu, cuộn chuột để phóng to.
net.set_options('{"nodes": {"scaling": {"label": {"drawThreshold": 1}}}, "physics": {"stabilization": {"iterations": 200}}}')
# Tự ghi bằng UTF-8: write_html của pyvis dùng mã hóa mặc định, trên Windows sẽ lỗi với tiếng Việt.
with open("do_thi.html", "w", encoding="utf-8") as f:
    f.write(net.generate_html())
print("Đã ghi do_thi.html:", len(nut), "nút,", len(so.quan_he), "cạnh")
