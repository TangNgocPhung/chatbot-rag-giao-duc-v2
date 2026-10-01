/* ============================================================
   VAI TRÒ NGƯỜI DÙNG
   ============================================================
   Người dùng tự chọn mình là ai (học sinh, phụ huynh...) ở bước đầu hộp giới
   thiệu hoặc ở màn hình chào. Vai trò chỉ để máy chủ đưa nhóm câu gợi ý hợp
   với người đó lên đầu (/api/goi-y?vai_tro=...): không lọc tài liệu khi tìm,
   không cấp quyền gì - người dùng tự khai thì không có gì để tin.

   Danh sách mã phải khớp VAI_TRO trong goi_y_cau_hoi.py (tests/test_goi_y.py
   kiểm tra). Lưu trong trình duyệt; bị chặn lưu trữ thì vẫn chọn được, chỉ là
   tải lại trang sẽ quên.
   ============================================================ */
window.vaiTroNguoiDung = (() => {
  const KHOA = 'rag-giao-duc-vai-tro-v1';
  const DANH_SACH = Object.freeze([
    { ma: 'hoc_sinh', nhan: 'Học sinh' },
    { ma: 'sinh_vien', nhan: 'Sinh viên' },
    { ma: 'giao_vien', nhan: 'Giáo viên, giảng viên' },
    { ma: 'can_bo_quan_ly', nhan: 'Cán bộ quản lý' },
    { ma: 'phu_huynh', nhan: 'Phụ huynh' },
  ]);
  const hopLe = (ma) => DANH_SACH.some((vaiTro) => vaiTro.ma === ma);
  const nguoiNghe = new Set();

  let hienTai = '';
  try {
    const daLuu = localStorage.getItem(KHOA) || '';
    hienTai = hopLe(daLuu) ? daLuu : '';
  } catch {
    hienTai = '';
  }

  function dat(ma) {
    const moi = hopLe(ma) ? ma : '';
    if (moi === hienTai) return;
    hienTai = moi;
    try {
      if (moi) localStorage.setItem(KHOA, moi);
      else localStorage.removeItem(KHOA);
    } catch {
      /* Không lưu được thì vẫn dùng được trong lượt này. */
    }
    for (const nghe of nguoiNghe) nghe(moi);
  }

  return {
    DANH_SACH,
    lay: () => hienTai,
    dat,
    khiDoi: (nghe) => nguoiNghe.add(nghe),
  };
})();
