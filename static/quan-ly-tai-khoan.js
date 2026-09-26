/* ============================================================
   QUẢN LÝ TÀI KHOẢN (chỉ quản trị viên)
   ============================================================
   Xem mọi tài khoản, lọc tài khoản chưa xác minh email hay đang bị khoá,
   khoá / mở khoá và xoá hẳn. Máy chủ tự chặn việc khoá hay xoá chính mình
   và tài khoản quản trị khác; ở đây chỉ ẩn nút cho khỏi bấm nhầm.
   ============================================================ */
(() => {
  const $id = (id) => document.getElementById(id);
  const ql = {
    hop: $id('qltkDialog'),
    dong: $id('qltkDong'),
    tabs: $id('qltkTabs'),
    tomTat: $id('qltkTomTat'),
    tim: $id('qltkTim'),
    danhSach: $id('qltkDanhSach'),
  };
  if (!ql.hop) return;

  let taiKhoan = [];
  let guiThu = false;
  let loc = 'tat-ca';

  const LOC = {
    'tat-ca': () => true,
    'chua-xac-minh': (tk) => !tk.da_xac_minh,
    'bi-khoa': (tk) => tk.bi_cam,
  };
  const TRONG = {
    'tat-ca': 'Chưa có tài khoản nào.',
    'chua-xac-minh': 'Mọi tài khoản đều đã xác minh email.',
    'bi-khoa': 'Không có tài khoản nào bị khoá.',
  };

  async function goi(duongDan, { method = 'GET', hanhDong, than } = {}) {
    const headers = {};
    if (hanhDong) headers['X-RAG-Action'] = hanhDong;
    if (than) headers['Content-Type'] = 'application/json';
    const phanHoi = await fetch(duongDan, {
      method,
      headers,
      body: than ? JSON.stringify(than) : undefined,
      cache: 'no-store',
    });
    const noiDung = await phanHoi.json().catch(() => ({}));
    if (!phanHoi.ok) throw new Error(loiMayChu(noiDung, `Máy chủ trả về lỗi ${phanHoi.status}.`));
    return noiDung;
  }

  function nhan(chu, lop) {
    const o = document.createElement('span');
    o.className = `qltk-nhan ${lop}`;
    o.textContent = chu;
    return o;
  }

  function taoNut(chu, lop, khiBam) {
    const nut = document.createElement('button');
    nut.type = 'button';
    nut.className = `kho-nut ${lop}`.trim();
    nut.textContent = chu;
    nut.addEventListener('click', async () => {
      nut.disabled = true;
      try {
        await khiBam();
      } catch (error) {
        showToast(error.message || 'Không thực hiện được');
      } finally {
        nut.disabled = false;
      }
    });
    return nut;
  }

  function veDem() {
    for (const o of ql.tabs.querySelectorAll('[data-dem]')) {
      o.textContent = String(taiKhoan.filter(LOC[o.dataset.dem]).length);
    }
    const chuaXacMinh = taiKhoan.filter(LOC['chua-xac-minh']).length;
    const biKhoa = taiKhoan.filter(LOC['bi-khoa']).length;
    ql.tomTat.textContent = [
      `${taiKhoan.length} tài khoản`,
      `${chuaXacMinh} chưa xác minh email`,
      `${biKhoa} bị khoá`,
      guiThu ? '' : 'máy chủ chưa cấu hình gửi thư nên người dùng chưa tự xác minh được',
    ].filter(Boolean).join(' · ');
  }

  function ve() {
    veDem();
    const tuKhoa = ql.tim.value.trim().toLocaleLowerCase('vi-VN');
    const nguon = taiKhoan.filter((tk) => LOC[loc](tk)
      && `${tk.ten} ${tk.email}`.toLocaleLowerCase('vi-VN').includes(tuKhoa));
    ql.danhSach.replaceChildren();
    if (!nguon.length) {
      const trong = document.createElement('div');
      trong.className = 'document-empty';
      trong.textContent = tuKhoa ? 'Không tìm thấy tài khoản phù hợp.' : TRONG[loc];
      ql.danhSach.append(trong);
      return;
    }
    for (const tk of nguon) ql.danhSach.append(veHang(tk));
  }

  function veHang(tk) {
    const hang = document.createElement('div');
    hang.className = `document-row kho-hang qltk-hang${tk.bi_cam ? ' bi-khoa' : ''}`;

    const avatar = document.createElement('span');
    avatar.className = 'avatar-tk qltk-avatar';
    avatar.textContent = (tk.ten || tk.email).trim().charAt(0).toLocaleUpperCase('vi-VN');

    const info = document.createElement('span');
    info.className = 'document-info';
    const dong1 = document.createElement('span');
    dong1.className = 'qltk-dong-ten';
    const ten = document.createElement('strong');
    ten.textContent = tk.ten;
    ten.title = tk.ten;
    dong1.append(ten);
    if (tk.la_toi) dong1.append(nhan('Bạn', 'toi'));
    if (tk.quan_tri) dong1.append(nhan('Quản trị', 'quan-tri'));
    if (tk.bi_cam) dong1.append(nhan('Bị khoá', 'khoa'));
    else if (!tk.da_xac_minh) dong1.append(nhan('Chưa xác minh', 'chua'));
    const phu = document.createElement('small');
    phu.textContent = [
      tk.email,
      `tạo ${dinhDangNgay(tk.tao_luc)}`,
      tk.bi_cam
        ? `khoá bởi ${tk.cam_boi || 'quản trị viên'} lúc ${dinhDangNgay(tk.cam_luc)}`
        : (tk.dang_nhap_luc ? `đăng nhập ${dinhDangNgay(tk.dang_nhap_luc)}` : 'chưa đăng nhập lần nào'),
    ].join(' · ');
    phu.title = phu.textContent;
    info.append(dong1, phu);

    const nut = document.createElement('span');
    nut.className = 'kho-hanh-dong';
    if (!tk.la_toi && !tk.quan_tri) {
      nut.append(
        tk.bi_cam
          ? taoNut('Mở khoá', 'chinh', () => khoa(tk, false))
          : taoNut('Khoá', '', () => khoa(tk, true)),
        taoNut('Xoá', 'phu', () => xoa(tk)),
      );
    }
    hang.append(avatar, info, nut);
    return hang;
  }

  function thay(tkMoi) {
    taiKhoan = taiKhoan.map((tk) => (tk.id === tkMoi.id ? { ...tkMoi, la_toi: tk.la_toi } : tk));
    ve();
  }

  async function khoa(tk, khoaLai) {
    if (khoaLai) {
      const dongY = await hoiXacNhan({
        tieuDe: `Khoá tài khoản ${tk.email}?`,
        moTa: 'Người này bị đăng xuất khỏi mọi thiết bị và không đăng nhập lại được, cũng không đăng ký lại bằng email này được. Lịch sử trò chuyện và sổ tay vẫn giữ nguyên; mở khoá là dùng lại như cũ.',
        nhanDongY: 'Khoá',
      });
      if (!dongY) return;
    }
    const { tai_khoan: moi } = await goi(`/api/quan-ly/tai-khoan/${encodeURIComponent(tk.id)}/khoa`, {
      method: 'POST', hanhDong: 'khoa-tai-khoan', than: { khoa: khoaLai },
    });
    thay(moi);
    showToast(khoaLai ? `Đã khoá ${tk.email}` : `Đã mở khoá ${tk.email}`, 2600);
  }

  async function xoa(tk) {
    const dongY = await hoiXacNhan({
      tieuDe: `Xoá vĩnh viễn ${tk.email}?`,
      moTa: 'Tài khoản bị xoá cùng toàn bộ lịch sử trò chuyện, sổ tay và ảnh đại diện, không hoàn tác được. Email được giải phóng nên người này vẫn đăng ký lại được - muốn chặn hẳn thì chọn Khoá.',
      nhanDongY: 'Xoá vĩnh viễn',
    });
    if (!dongY) return;
    const kq = await goi(`/api/quan-ly/tai-khoan/${encodeURIComponent(tk.id)}`, {
      method: 'DELETE', hanhDong: 'xoa-tai-khoan',
    });
    taiKhoan = taiKhoan.filter((muc) => muc.id !== tk.id);
    ve();
    showToast(kq.so_hoi_thoai
      ? `Đã xoá ${kq.email} và ${kq.so_hoi_thoai} cuộc trò chuyện`
      : `Đã xoá ${kq.email}`, 2600);
  }

  function chonLoc(moi) {
    loc = moi;
    for (const nut of ql.tabs.querySelectorAll('[data-loc]')) {
      nut.setAttribute('aria-selected', String(nut.dataset.loc === moi));
    }
    ve();
  }

  async function mo() {
    ql.tim.value = '';
    chonLoc('tat-ca');
    ql.tomTat.textContent = 'Đang tải danh sách tài khoản…';
    ql.danhSach.replaceChildren();
    if (!ql.hop.open) ql.hop.showModal();
    try {
      const kq = await goi('/api/quan-ly/tai-khoan');
      taiKhoan = kq.tai_khoan || [];
      guiThu = Boolean(kq.gui_thu);
      ve();
    } catch (error) {
      ql.tomTat.textContent = '';
      const loi = document.createElement('div');
      loi.className = 'document-empty error';
      loi.textContent = error.message || 'Không tải được danh sách tài khoản.';
      ql.danhSach.replaceChildren(loi);
    }
  }

  ql.tabs.addEventListener('click', (event) => {
    const nut = event.target.closest('[data-loc]');
    if (nut) chonLoc(nut.dataset.loc);
  });
  ql.tim.addEventListener('input', ve);
  ql.dong.addEventListener('click', () => ql.hop.close());
  ql.hop.addEventListener('click', (event) => {
    if (event.target === ql.hop) ql.hop.close();
  });

  window.quanLyTaiKhoan = { mo };
})();
