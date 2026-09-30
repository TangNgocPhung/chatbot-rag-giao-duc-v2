"""
XẾP LẠI KHO TÀI LIỆU ĐANG CÓ VÀO THƯ MỤC CON THEO LOẠI
======================================================
Tệp tải lên từ nay tự vào đúng thư mục (xep_thu_muc_kho.py). Script này lo
phần còn lại: hơn một nghìn tệp đang nằm phẳng ở gốc kho.

    data_giao_duc/Vở bài tập Toán 5 - Tập một.pdf
        -> data_giao_duc/pdf/sach_bai_tap/Vở bài tập Toán 5 - Tập một.pdf

Làm ngược chiều gop_kho_mot_thu_muc.py và cùng lý do phải cẩn thận: ba nơi
đang nhớ đường dẫn tệp. Chỉ chuyển tệp mà không sửa kèm thì

  * sổ ghi chép (data_giao_duc_da_xu_ly.json) coi mọi tệp là mới -> lập chỉ
    mục lại toàn bộ kho, nhiều giờ CPU;
  * chỉ mục FAISS vẫn trỏ vào đường dẫn cũ -> bấm trích dẫn không mở được tệp;
  * drive_state.json không thấy tệp ở chỗ cũ -> lượt đồng bộ Drive kế tiếp
    tải lại cả kho.

Nên script chuyển tệp VÀ viết lại cả ba (sao lưu bản cũ trước khi ghi).

Chỉ đụng tới tệp nằm NGAY Ở GỐC kho. Tệp đã ở trong thư mục con - kể cả tệp
quản trị viên tự kéo sang thư mục khác vì máy xếp sai - được giữ nguyên, nên
chạy lại bao nhiêu lần cũng không xáo trộn phần đã xếp.

Phân loại dùng nhãn lập từ TOÀN VĂN lúc lập chỉ mục (phan_loai_tai_lieu.json,
ho_so_van_ban.json - có cả chữ OCR của bản scan) nếu có, không thì đọc 2 trang
đầu của tệp.

Chạy khi ứng dụng đã TẮT (nó giữ chỉ mục trong RAM và sẽ ghi đè bản đã sửa):

  Trên VPS:
    sudo systemctl stop chatbot-rag
    cd /opt/chatbot-rag
    sudo -u rag .venv/bin/python xep_kho_theo_loai.py --thu-xem   # xem trước
    sudo -u rag .venv/bin/python xep_kho_theo_loai.py             # làm thật
    sudo systemctl start chatbot-rag

  Trên Windows:
    .venv\\Scripts\\python.exe xep_kho_theo_loai.py --thu-xem
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pickle
import shutil
import socket
import sys
import time
from collections import Counter

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.abspath(os.getenv(
    "RAG_DATA_PATH",
    os.path.join(THU_MUC_DU_AN, "ollama-rag-desktop", "data_giao_duc"),
))
DUONG_DAN_SO_GHI_CHEP = os.getenv(
    "RAG_LEDGER_PATH", os.path.join(THU_MUC_DU_AN, "data_giao_duc_da_xu_ly.json")
)
DUONG_DAN_INDEX = os.getenv(
    "RAG_INDEX_PATH", os.path.join(THU_MUC_DU_AN, "faiss_index_data_giao_duc")
)
DUONG_DAN_DRIVE_STATE = os.getenv(
    "RAG_DRIVE_STATE", os.path.join(THU_MUC_DU_AN, "drive_state.json")
)
# Cổng của dịch vụ chatbot-rag trên VPS (01_cai_dat_vps.sh).
CONG_UNG_DUNG = int(os.getenv("RAG_CONG_UNG_DUNG", "8010"))
DUOI_SAO_LUU = ".truoc-khi-xep-loai-"


def _chuan(duong_dan: str) -> str:
    return os.path.normcase(os.path.abspath(duong_dan))


# ------------------------------------------------------------
# LẬP KẾ HOẠCH
# ------------------------------------------------------------
def lap_ke_hoach(bao_tien_do=None) -> tuple[dict[str, str], list[str]]:
    """Trả về ({đường dẫn cũ: đường dẫn mới}, [cảnh báo]).

    Tên tệp vốn đã duy nhất trong cả kho (resolve_source_file cần thế), chuyển
    tệp giữ nguyên tên nên không sinh trùng. Vẫn kiểm tra: nếu đích đã có tệp
    cùng tên thì bỏ qua tệp đó, không ghi đè.
    """
    import phan_loai_giao_duc
    import van_ban_meta
    import xep_thu_muc_kho
    from document_loaders import DINH_DANG_HO_TRO

    bang_phan_loai = phan_loai_giao_duc.tai()
    ho_so = van_ban_meta.tai_ho_so()

    cac_ten = sorted(
        ten for ten in os.listdir(DATA_PATH)
        if os.path.isfile(os.path.join(DATA_PATH, ten))
        and os.path.splitext(ten)[1].lower() in DINH_DANG_HO_TRO
    )
    ke_hoach: dict[str, str] = {}
    canh_bao: list[str] = []
    for thu_tu, ten in enumerate(cac_ten, 1):
        if bao_tien_do:
            bao_tien_do(thu_tu, len(cac_ten), ten)
        cu = os.path.join(DATA_PATH, ten)
        try:
            thu_muc = xep_thu_muc_kho.chon_thu_muc(
                ten, cu, phan_loai=bang_phan_loai.get(ten), ho_so=ho_so.get(ten),
            )
        except Exception as exc:  # một tệp hỏng không được làm dừng cả kho
            canh_bao.append(f"{ten}: không phân loại được ({exc}), để nguyên ở gốc.")
            continue
        moi = os.path.join(DATA_PATH, xep_thu_muc_kho.thu_muc_he_dieu_hanh(thu_muc), ten)
        if os.path.exists(moi):
            canh_bao.append(f"{ten}: {thu_muc}/ đã có tệp cùng tên, để nguyên ở gốc.")
            continue
        ke_hoach[cu] = moi
    return ke_hoach, canh_bao


def thong_ke_thu_muc(ke_hoach: dict[str, str]) -> list[tuple[str, int]]:
    dem = Counter(
        os.path.relpath(os.path.dirname(moi), DATA_PATH).replace(os.sep, "/")
        for moi in ke_hoach.values()
    )
    return sorted(dem.items())


def ghi_bao_cao(ke_hoach: dict[str, str], duong_dan: str) -> None:
    """CSV mở được bằng Excel (utf-8-sig) để soát lại trước khi làm thật."""
    with open(duong_dan, "w", encoding="utf-8-sig", newline="") as f:
        viet = csv.writer(f)
        viet.writerow(["ten_tep", "thu_muc_moi"])
        for cu, moi in sorted(ke_hoach.items(), key=lambda cap: (cap[1], cap[0])):
            viet.writerow([
                os.path.basename(cu),
                os.path.relpath(os.path.dirname(moi), DATA_PATH).replace(os.sep, "/"),
            ])


# ------------------------------------------------------------
# THỰC HIỆN
# ------------------------------------------------------------
def chuyen_tep(ke_hoach: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Trả về (các tệp ĐÃ chuyển được, lỗi). Chỉ tệp đã chuyển mới được sửa
    trong sổ ghi chép / FAISS / Drive - lỗi giữa chừng không làm lệch sổ."""
    da_chuyen: dict[str, str] = {}
    loi: list[str] = []
    for cu, moi in ke_hoach.items():
        try:
            os.makedirs(os.path.dirname(moi), exist_ok=True)
            # Cùng ổ đĩa nên move là đổi tên: giữ nguyên mtime, sổ ghi chép
            # so size + modified_ns vẫn khớp, không bị coi là tệp đã sửa.
            shutil.move(cu, moi)
            da_chuyen[cu] = moi
        except OSError as exc:
            loi.append(f"{os.path.basename(cu)}: {exc}")
    return da_chuyen, loi


def _sao_luu(duong_dan: str, moc: str) -> str | None:
    if not os.path.exists(duong_dan):
        return None
    ban_sao = f"{duong_dan}{DUOI_SAO_LUU}{moc}"
    shutil.copy2(duong_dan, ban_sao)
    return ban_sao


def sua_so_ghi_chep(doi_chieu: dict[str, str], moc: str) -> int:
    try:
        with open(DUONG_DAN_SO_GHI_CHEP, encoding="utf-8") as f:
            so = json.load(f)
    except (OSError, ValueError):
        return 0
    if not isinstance(so, dict):
        return 0
    moi, dem = {}, 0
    for duong_dan, ban_ghi in so.items():
        dich = doi_chieu.get(_chuan(duong_dan))
        if dich:
            dem += 1
        moi[dich or duong_dan] = ban_ghi
    if dem:
        _sao_luu(DUONG_DAN_SO_GHI_CHEP, moc)
        with open(DUONG_DAN_SO_GHI_CHEP, "w", encoding="utf-8") as f:
            json.dump(moi, f, ensure_ascii=False, indent=1)
    return dem


def sua_chi_muc_faiss(doi_chieu: dict[str, str], moc: str) -> int:
    """Viết lại metadata 'source' và 'loai_thu_muc' (chunking_utils.suy_metadata
    lấy tầng thư mục đầu tiên) để trích dẫn vẫn mở được tệp."""
    duong_dan_pkl = os.path.join(DUONG_DAN_INDEX, "index.pkl")
    if not os.path.isfile(duong_dan_pkl):
        return 0
    with open(duong_dan_pkl, "rb") as f:
        goi = pickle.load(f)
    kho = getattr(goi[0], "_dict", None)
    if not isinstance(kho, dict):
        print("  ! Không đọc được docstore, bỏ qua bước sửa chỉ mục.")
        return 0

    dem = 0
    for tai_lieu in kho.values():
        meta = getattr(tai_lieu, "metadata", None)
        if not isinstance(meta, dict):
            continue
        dich = doi_chieu.get(_chuan(meta.get("source", "")))
        if not dich:
            continue
        meta["source"] = dich
        meta["loai_thu_muc"] = os.path.relpath(dich, DATA_PATH).split(os.sep)[0]
        dem += 1
    if dem:
        _sao_luu(duong_dan_pkl, moc)
        with open(duong_dan_pkl, "wb") as f:
            pickle.dump(goi, f)
    return dem


def sua_drive_state(doi_chieu_tuong_doi: dict[str, str], moc: str) -> int:
    try:
        with open(DUONG_DAN_DRIVE_STATE, encoding="utf-8") as f:
            trang_thai = json.load(f)
    except (OSError, ValueError):
        return 0
    if not isinstance(trang_thai, dict):
        return 0
    dem = 0
    for ban_ghi in trang_thai.values():
        if not isinstance(ban_ghi, dict):
            continue
        cu = ban_ghi.get("duong_dan") or ""
        moi = doi_chieu_tuong_doi.get(os.path.normcase(os.path.normpath(cu)))
        if moi and moi != cu:
            ban_ghi["duong_dan"] = moi
            dem += 1
    if dem:
        _sao_luu(DUONG_DAN_DRIVE_STATE, moc)
        with open(DUONG_DAN_DRIVE_STATE, "w", encoding="utf-8") as f:
            json.dump(trang_thai, f, ensure_ascii=False, indent=1)
    return dem


def ung_dung_dang_chay(cong: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", cong), timeout=1):
            return True
    except OSError:
        return False


def thuc_hien(ke_hoach: dict[str, str]) -> dict:
    """Chuyển tệp rồi sửa cả ba nơi nhớ đường dẫn. Tách khỏi main() để test."""
    moc = time.strftime("%Y%m%d-%H%M%S")
    da_chuyen, loi = chuyen_tep(ke_hoach)
    doi_chieu = {_chuan(cu): moi for cu, moi in da_chuyen.items()}
    doi_chieu_tuong_doi = {
        os.path.normcase(os.path.relpath(cu, DATA_PATH)): os.path.relpath(moi, DATA_PATH)
        for cu, moi in da_chuyen.items()
    }
    return {
        "da_chuyen": len(da_chuyen),
        "loi": loi,
        "so_ghi_chep": sua_so_ghi_chep(doi_chieu, moc),
        "faiss": sua_chi_muc_faiss(doi_chieu, moc),
        "drive": sua_drive_state(doi_chieu_tuong_doi, moc),
    }


def main() -> int:
    bo_phan_tich = argparse.ArgumentParser(
        description="Xếp tệp ở gốc kho vào thư mục con theo định dạng và loại nội dung.",
    )
    bo_phan_tich.add_argument(
        "--thu-xem", action="store_true",
        help="Chỉ in kế hoạch và ghi báo cáo CSV, không chuyển tệp nào.",
    )
    bo_phan_tich.add_argument(
        "--bo-qua-kiem-tra-ung-dung", action="store_true",
        help=f"Không kiểm tra ứng dụng còn chạy ở cổng {CONG_UNG_DUNG} hay không.",
    )
    tham_so = bo_phan_tich.parse_args()

    if not os.path.isdir(DATA_PATH):
        print(f"Không thấy kho tài liệu: {DATA_PATH}")
        return 1
    if (
        not tham_so.thu_xem
        and not tham_so.bo_qua_kiem_tra_ung_dung
        and ung_dung_dang_chay(CONG_UNG_DUNG)
    ):
        print(f"DỪNG: ứng dụng còn đang chạy ở cổng {CONG_UNG_DUNG}. Nó giữ chỉ mục")
        print("trong RAM và sẽ ghi đè bản đã sửa đường dẫn. Tắt trước:")
        print("    sudo systemctl stop chatbot-rag")
        return 1

    print(f"Kho: {DATA_PATH}")
    print("Đang phân loại tệp ở gốc kho (đọc 1-2 trang đầu mỗi tệp)...")

    def bao(thu_tu, tong, _ten):
        if thu_tu % 50 == 0 or thu_tu == tong:
            print(f"  {thu_tu}/{tong}")

    ke_hoach, canh_bao = lap_ke_hoach(bao)
    print(f"\nSố tệp sẽ chuyển: {len(ke_hoach)}")
    for thu_muc, so in thong_ke_thu_muc(ke_hoach):
        print(f"  {so:5d}  {thu_muc}/")
    for dong in canh_bao:
        print(f"  ! {dong}")

    bao_cao = os.path.join(
        THU_MUC_DU_AN, f"bao_cao_xep_kho-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    )
    ghi_bao_cao(ke_hoach, bao_cao)
    print(f"\nDanh sách từng tệp: {bao_cao}")

    if not ke_hoach:
        print("Không có tệp nào ở gốc kho cần xếp.")
        return 0
    if tham_so.thu_xem:
        print("\n(Chạy lại không kèm --thu-xem để làm thật.)")
        return 0

    print("\nĐang chuyển tệp và sửa đường dẫn...")
    ket_qua = thuc_hien(ke_hoach)
    print(f"  Đã chuyển {ket_qua['da_chuyen']} tệp.")
    print(f"  Sổ ghi chép: đổi {ket_qua['so_ghi_chep']} đường dẫn.")
    print(f"  Chỉ mục FAISS: đổi {ket_qua['faiss']} đoạn văn bản.")
    print(f"  Drive: đổi {ket_qua['drive']} bản ghi.")
    for dong in ket_qua["loi"]:
        print(f"  ! Không chuyển được {dong}")

    print("\nXong. Khởi động lại ứng dụng - KHÔNG phải lập chỉ mục lại.")
    print(f"Bản sao lưu nằm cạnh tệp gốc, đuôi '{DUOI_SAO_LUU}...'; xoá được")
    print("sau khi kiểm tra thấy trích dẫn vẫn mở được tài liệu.")
    return 1 if ket_qua["loi"] else 0


if __name__ == "__main__":
    sys.exit(main())
