"""
CHIA BỘ CÂU HỎI BENCHMARK THÀNH TẬP DEV VÀ TẬP TEST
====================================================
Chạy:                python chia_tap_benchmark.py
Xem trước, không ghi: python chia_tap_benchmark.py --thu

VÌ SAO PHẢI CHIA
  Hệ thống không huấn luyện mô hình nào, nhưng vẫn có tham số được CHỌN theo
  kết quả đo: trọng số rerank trong hybrid_retrieval.py, cặp ngưỡng chặn lạc đề
  quét bằng `benchmark_chatbot.py --do-nguong`, số chunk đưa vào prompt... Chọn
  tham số trên bộ câu nào thì điểm trên chính bộ đó là ước lượng LẠC QUAN - đó
  là vai trò của tập validation, không phải tập test. Vì vậy:
    dev  : dùng thoải mái để tinh chỉnh, chạy bao nhiêu lần cũng được.
    test : chỉ chạy SAU KHI đã đóng băng tham số, và lấy con số đó vào báo cáo.

CÁCH CHIA
  - Phân tầng theo `nhom`: mỗi nhóm góp khoảng TY_LE_TEST số câu vào tập test,
    để nhóm nhỏ (video chỉ 5 câu) không bị dồn hết về một phía.
  - Mỗi nhóm có từ 2 câu trở lên được bảo đảm ít nhất 1 câu ở mỗi tập.
  - Ngẫu nhiên nhưng TẤT ĐỊNH: hạt giống cố định, trộn riêng từng nhóm.
  - CHỈ GÁN CHO CÂU CHƯA CÓ `tap`. Câu đã gán không bao giờ bị đổi tập: đổi một
    câu từ test sang dev sau khi đã nhìn kết quả test chính là rò rỉ cần tránh.
    Câu mới thêm vào bộ thì chạy lại script này, hoặc gán tay `"tap": "test"`
    cho câu viết riêng làm tập test (cách sạch nhất - xem README).

GIỚI HẠN CẦN NÊU TRONG BÁO CÁO
  Các tham số hiện có đã được chọn khi nhìn TOÀN BỘ 127 câu gốc, trước khi
  chia. Tập test tách từ bộ này vì thế chỉ sạch đối với những lần tinh chỉnh
  từ nay về sau; muốn một ước lượng hoàn toàn không thiên lệch thì phải viết
  câu mới - 373 câu thêm ngày 06/10/2026 là những câu như vậy.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_BO_CAU_HOI = os.path.join(THU_MUC_DU_AN, "bo_cau_hoi_benchmark.json")

TAP_DEV = "dev"
TAP_TEST = "test"
CAC_TAP = (TAP_DEV, TAP_TEST)
# 40% thay vì 20-30% quen thuộc: bộ gốc chỉ có 127 câu, test 20% thì nhóm video còn
# đúng 1 câu và Hit@1 của nhóm chỉ có thể là 0% hoặc 100%.
TY_LE_TEST = 0.4
HAT_GIONG = 20261001


def so_cau_test_muc_tieu(so_cau_nhom: int, ty_le: float = TY_LE_TEST) -> int:
    """Số câu test mong muốn cho một nhóm. Làm tròn nửa lên (không dùng round()
    vì round() làm tròn về số chẵn: round(2.5) == 2), rồi kẹp vào [1, n-1] để
    nhóm nào có từ 2 câu cũng có mặt ở cả hai tập."""
    if so_cau_nhom < 2:
        return 0
    muc_tieu = int(so_cau_nhom * ty_le + 0.5)
    return min(max(muc_tieu, 1), so_cau_nhom - 1)


def gan_tap(
    danh_sach: list[dict],
    ty_le: float = TY_LE_TEST,
    hat_giong: int = HAT_GIONG,
) -> list[dict]:
    """
    Trả về danh sách mới (không sửa danh sách vào) trong đó câu nào cũng có
    trường `tap`. Câu đã có `tap` giữ nguyên; câu chưa có được gán sao cho tỷ lệ
    test của TỪNG NHÓM tiến về `ty_le` nhất có thể mà không phải đổi câu cũ.
    """
    ket_qua = [dict(muc) for muc in danh_sach]
    for muc in ket_qua:
        if "tap" in muc and muc["tap"] not in CAC_TAP:
            raise ValueError(
                f"Giá trị tap không hợp lệ {muc['tap']!r} ở câu: {muc['cau_hoi'][:60]}"
            )

    theo_nhom: dict[str, list[dict]] = defaultdict(list)
    for muc in ket_qua:
        theo_nhom[muc.get("nhom", "")].append(muc)

    for nhom, cac_muc in theo_nhom.items():
        chua_gan = [muc for muc in cac_muc if "tap" not in muc]
        if not chua_gan:
            continue
        da_test = sum(1 for muc in cac_muc if muc.get("tap") == TAP_TEST)
        can_them = max(0, so_cau_test_muc_tieu(len(cac_muc), ty_le) - da_test)
        # Hạt giống riêng cho từng nhóm: thêm câu vào nhóm này không xáo trộn
        # cách gán của nhóm khác. Random(str) tất định qua mọi lần chạy.
        random.Random(f"{hat_giong}:{nhom}").shuffle(chua_gan)
        for thu_tu, muc in enumerate(chua_gan):
            muc["tap"] = TAP_TEST if thu_tu < can_them else TAP_DEV
    return ket_qua


def thong_ke(danh_sach: list[dict]) -> dict[str, Counter]:
    """{nhom: Counter({'dev': a, 'test': b})}, để in bảng và để test."""
    bang: dict[str, Counter] = defaultdict(Counter)
    for muc in danh_sach:
        bang[muc.get("nhom", "")][muc.get("tap", "?")] += 1
    return dict(bang)


def ghi_bo_cau_hoi(bo: dict, duong_dan: str) -> None:
    """Giữ đúng định dạng tệp gốc - mỗi câu một dòng, một dòng trống giữa hai
    nhóm - để diff trong Git chỉ hiện đúng những dòng bị thêm `tap`. Ghi tệp
    tạm rồi đổi tên."""
    dong_cau_hoi = ""
    for thu_tu, muc in enumerate(bo["cau_hoi"]):
        if thu_tu:
            sang_nhom_moi = muc.get("nhom") != bo["cau_hoi"][thu_tu - 1].get("nhom")
            dong_cau_hoi += ",\n\n" if sang_nhom_moi else ",\n"
        dong_cau_hoi += "    " + json.dumps(muc, ensure_ascii=False)
    phan_dau = {k: v for k, v in bo.items() if k != "cau_hoi"}
    dong_dau = "".join(
        f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},\n"
        for k, v in phan_dau.items()
    )
    tam = duong_dan + ".tmp"
    with open(tam, "w", encoding="utf-8", newline="\n") as f:
        f.write("{\n" + dong_dau + '  "cau_hoi": [\n' + dong_cau_hoi + "\n  ]\n}\n")
    os.replace(tam, duong_dan)


def in_bang(danh_sach: list[dict]) -> None:
    bang = thong_ke(danh_sach)
    print(f"{'Nhóm':<16}{'Tổng':>6}{'dev':>6}{'test':>6}")
    for nhom in sorted(bang, key=lambda n: -sum(bang[n].values())):
        dem = bang[nhom]
        print(f"{nhom:<16}{sum(dem.values()):>6}{dem[TAP_DEV]:>6}{dem[TAP_TEST]:>6}")
    tong = Counter(muc.get("tap") for muc in danh_sach)
    print(f"{'Toàn bộ':<16}{len(danh_sach):>6}{tong[TAP_DEV]:>6}{tong[TAP_TEST]:>6}")


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thu", action="store_true", help="chỉ in bảng, không ghi tệp")
    tham_so = parser.parse_args()

    with open(DUONG_DAN_BO_CAU_HOI, encoding="utf-8") as f:
        bo = json.load(f)
    so_chua_gan = sum(1 for muc in bo["cau_hoi"] if "tap" not in muc)
    bo["cau_hoi"] = gan_tap(bo["cau_hoi"])
    in_bang(bo["cau_hoi"])

    if not so_chua_gan:
        print("\nMọi câu đã có tập, không có gì để gán.")
    elif tham_so.thu:
        print(f"\n(--thu) Sẽ gán tập cho {so_chua_gan} câu, chưa ghi gì.")
    else:
        ghi_bo_cau_hoi(bo, DUONG_DAN_BO_CAU_HOI)
        print(f"\nĐã gán tập cho {so_chua_gan} câu và ghi vào {DUONG_DAN_BO_CAU_HOI}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
