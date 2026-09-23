/* ============================================================
   ĐĂNG NHẬP / ĐĂNG KÝ
   ============================================================
   Giống ChatGPT: không bắt buộc đăng nhập. Khách vẫn hỏi được, lịch sử nằm
   trong trình duyệt; đăng nhập thì lịch sử và sổ tay theo tài khoản, máy nào
   cũng thấy. Tệp này chỉ lo phần giao diện; việc đổi nguồn lịch sử nằm ở
   doiNguoiDung() trong app.js, việc đổi kho sổ tay nằm trong so-tay.js.
   ============================================================ */
(() => {
  const $id = (id) => document.getElementById(id);
  const tk = {
    khoi: $id('taiKhoanKhoi'),
    nutTren: $id('topDangNhap'),
    menu: $id('menuTaiKhoan'),
    menuTen: $id('menuTaiKhoanTen'),
    menuEmail: $id('menuTaiKhoanEmail'),
    hop: $id('authDialog'),
    form: $id('authForm'),
    dong: $id('authClose'),
    tieuDe: $id('authTitle'),
    moTa: $id('authSub'),
    oTen: $id('authTenField'),
    ten: $id('authTen'),
    oEmail: $id('authEmailField'),
    email: $id('authEmail'),
    oMatKhauCu: $id('authMatKhauCuField'),
    matKhauCu: $id('authMatKhauCu'),
    nhanMatKhau: $id('authMatKhauNhan'),
    matKhau: $id('authMatKhau'),
    hien: $id('authShow'),
    goiY: $id('authHint'),
    loi: $id('authError'),
    gui: $id('authSubmit'),
    chuyen: $id('authSwitch'),
    chuyenChu: $id('authSwitchText'),
    chuyenNut: $id('authSwitchButton'),
    ghiChu: $id('authNote'),
  };
  if (!tk.hop) return;

  const CHE_DO = {
    'dang-nhap': {
      tieuDe: 'Chào mừng trở lại',
      moTa: 'Đăng nhập để lưu lịch sử trò chuyện và sổ tay trên mọi thiết bị.',
      gui: 'Đăng nhập',
      chuyenChu: 'Chưa có tài khoản?',
      chuyenNut: 'Đăng ký',
      nhanMatKhau: 'Mật khẩu',
      goiY: '',
      tuDien: 'current-password',
    },
    'dang-ky': {
      tieuDe: 'Tạo tài khoản',
      moTa: 'Lịch sử trò chuyện và sổ tay sẽ lưu theo tài khoản - mở máy nào cũng thấy. Những gì bạn vừa hỏi cũng được giữ lại.',
      gui: 'Tạo tài khoản',
      chuyenChu: 'Đã có tài khoản?',
      chuyenNut: 'Đăng nhập',
      nhanMatKhau: 'Mật khẩu',
      goiY: 'Ít nhất 8 ký tự.',
      tuDien: 'new-password',
    },
    'doi-mat-khau': {
      tieuDe: 'Đổi mật khẩu',
      moTa: 'Các thiết bị khác đang đăng nhập tài khoản này sẽ bị đăng xuất.',
      gui: 'Đổi mật khẩu',
      nhanMatKhau: 'Mật khẩu mới',
      goiY: 'Ít nhất 8 ký tự.',
      tuDien: 'new-password',
    },
  };
  let cheDo = 'dang-nhap';

  function datCheDo(moi) {
    cheDo = moi;
    const nd = CHE_DO[moi];
    tk.tieuDe.textContent = nd.tieuDe;
    tk.moTa.textContent = nd.moTa;
    tk.gui.textContent = nd.gui;
    tk.nhanMatKhau.textContent = nd.nhanMatKhau;
    tk.goiY.textContent = nd.goiY;
    tk.goiY.classList.toggle('hidden', !nd.goiY);
    tk.matKhau.autocomplete = nd.tuDien;
    tk.oTen.classList.toggle('hidden', moi !== 'dang-ky');
    tk.oEmail.classList.toggle('hidden', moi === 'doi-mat-khau');
    tk.oMatKhauCu.classList.toggle('hidden', moi !== 'doi-mat-khau');
    tk.chuyen.classList.toggle('hidden', moi === 'doi-mat-khau');
    tk.ghiChu.classList.toggle('hidden', moi !== 'dang-nhap');
    if (nd.chuyenChu) {
      tk.chuyenChu.textContent = nd.chuyenChu;
      tk.chuyenNut.textContent = nd.chuyenNut;
    }
    baoLoi('');
  }

  function baoLoi(thongBao) {
    tk.loi.textContent = thongBao;
    tk.loi.classList.toggle('hidden', !thongBao);
  }

  function moHop(moi = 'dang-nhap') {
    dongMenu();
    closeSidebar();
    tk.form.reset();
    datMatKhauHien(false);
    datCheDo(moi);
    if (!tk.hop.open) tk.hop.showModal();
    const dau = moi === 'dang-ky' ? tk.ten : moi === 'doi-mat-khau' ? tk.matKhauCu : tk.email;
    dau.focus();
  }

  function datMatKhauHien(hien) {
    for (const o of [tk.matKhau, tk.matKhauCu]) o.type = hien ? 'text' : 'password';
    tk.hien.textContent = hien ? 'Ẩn' : 'Hiện';
    tk.hien.setAttribute('aria-pressed', String(hien));
  }

  tk.hien.addEventListener('click', () => datMatKhauHien(tk.matKhau.type === 'password'));
  tk.dong.addEventListener('click', () => tk.hop.close());
  tk.hop.addEventListener('click', (event) => {
    if (event.target === tk.hop) tk.hop.close();
  });
  tk.chuyenNut.addEventListener('click', () => {
    datCheDo(cheDo === 'dang-nhap' ? 'dang-ky' : 'dang-nhap');
    (cheDo === 'dang-ky' ? tk.ten : tk.email).focus();
  });

  async function goi(duongDan, than) {
    const phanHoi = await fetch(duongDan, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-RAG-Client': maTrinhDuyet() },
      body: JSON.stringify(than),
    });
    const noiDung = await phanHoi.json().catch(() => ({}));
    if (!phanHoi.ok) {
      const chiTiet = Array.isArray(noiDung.detail) ? 'Thông tin chưa hợp lệ.' : noiDung.detail;
      throw new Error(chiTiet || `Máy chủ trả về lỗi ${phanHoi.status}.`);
    }
    return noiDung;
  }

  tk.form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const email = tk.email.value.trim();
    const matKhau = tk.matKhau.value;
    if (cheDo !== 'doi-mat-khau' && !/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email)) {
      baoLoi('Email không hợp lệ.');
      tk.email.focus();
      return;
    }
    if (cheDo !== 'dang-nhap' && matKhau.length < 8) {
      baoLoi('Mật khẩu cần ít nhất 8 ký tự.');
      tk.matKhau.focus();
      return;
    }
    if (!matKhau) {
      baoLoi('Hãy nhập mật khẩu.');
      tk.matKhau.focus();
      return;
    }
    baoLoi('');
    tk.gui.disabled = true;
    try {
      if (cheDo === 'doi-mat-khau') {
        await goi('/api/tai-khoan/doi-mat-khau', { mat_khau_cu: tk.matKhauCu.value, mat_khau_moi: matKhau });
        tk.hop.close();
        showToast('Đã đổi mật khẩu');
        return;
      }
      const dangKy = cheDo === 'dang-ky';
      const cuocDangMo = currentChat?.id || null;
      const { nguoi_dung: nd } = await goi(
        dangKy ? '/api/tai-khoan/dang-ky' : '/api/tai-khoan/dang-nhap',
        dangKy ? { email, mat_khau: matKhau, ten: tk.ten.value.trim() } : { email, mat_khau: matKhau },
      );
      tk.hop.close();
      // doiNguoiDung lưu nốt sổ đang mở vào kho của khách trước khi đổi kho,
      // nên phải chuyển sổ khách lên máy chủ SAU bước này mới không sót.
      await doiNguoiDung(nd);
      if (dangKy) {
        // Máy chủ đã chuyển hội thoại của khách sang tài khoản; chuyển nốt sổ
        // tay rồi bỏ bản trong trình duyệt để khỏi thấy hai lần.
        await window.khongGianHoc?.chuyenSoKhachLenTaiKhoan();
        try {
          localStorage.removeItem(STORAGE_KEY);
          localStorage.removeItem(LEGACY_STORAGE_KEY);
        } catch {
          /* không xóa được thì chỉ còn bản sao trong trình duyệt */
        }
      }
      // Đăng ký giữa chừng thì mở lại đúng cuộc trò chuyện đang dở.
      const cuocCu = dangKy && cuocDangMo && loadHistory().find((chat) => chat.id === cuocDangMo);
      if (cuocCu) await openChat(cuocCu);
      showToast(dangKy ? `Đã tạo tài khoản. Chào ${nd.ten}!` : `Xin chào, ${nd.ten}`);
    } catch (error) {
      baoLoi(error.message || 'Không thực hiện được, hãy thử lại.');
    } finally {
      tk.gui.disabled = false;
    }
  });

  // ------------------------------------------------------------
  // KHU TÀI KHOẢN Ở CUỐI THANH BÊN + MENU
  // ------------------------------------------------------------
  const MAU_AVATAR = ['#315fad', '#2f8669', '#c2553f', '#76569b', '#b07a1f', '#1f7a8c'];

  function mauTheoMa(ma) {
    let tong = 0;
    for (const kyTu of ma) tong = (tong * 31 + kyTu.charCodeAt(0)) >>> 0;
    return MAU_AVATAR[tong % MAU_AVATAR.length];
  }

  function taoNut(chu, lop, khiBam) {
    const nut = document.createElement('button');
    nut.type = 'button';
    nut.className = lop;
    nut.textContent = chu;
    nut.addEventListener('click', khiBam);
    return nut;
  }

  function ve() {
    tk.khoi.replaceChildren();
    tk.nutTren.classList.toggle('hidden', Boolean(nguoiDung));
    if (!nguoiDung) {
      const moi = document.createElement('p');
      moi.className = 'tai-khoan-moi';
      moi.textContent = 'Đăng nhập để lưu lịch sử và sổ tay trên mọi thiết bị.';
      const hang = document.createElement('div');
      hang.className = 'tai-khoan-nut';
      hang.append(
        taoNut('Đăng ký', 'chinh', () => moHop('dang-ky')),
        taoNut('Đăng nhập', '', () => moHop('dang-nhap')),
      );
      tk.khoi.append(moi, hang);
      return;
    }
    const nut = document.createElement('button');
    nut.type = 'button';
    nut.className = 'tai-khoan-toi';
    nut.setAttribute('aria-haspopup', 'menu');
    nut.setAttribute('aria-expanded', 'false');
    nut.setAttribute('aria-controls', 'menuTaiKhoan');
    const avatar = document.createElement('span');
    avatar.className = 'avatar-tk';
    avatar.style.background = mauTheoMa(nguoiDung.id);
    avatar.textContent = (nguoiDung.ten || nguoiDung.email).trim().charAt(0).toLocaleUpperCase('vi-VN');
    const chu = document.createElement('span');
    chu.className = 'tai-khoan-chu';
    const ten = document.createElement('strong');
    ten.textContent = nguoiDung.ten;
    const phu = document.createElement('small');
    phu.textContent = nguoiDung.quan_tri ? 'Quản trị viên' : nguoiDung.email;
    chu.append(ten, phu);
    nut.append(avatar, chu);
    nut.insertAdjacentHTML('beforeend', '<svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 15 5-5 5 5"/></svg>');
    nut.addEventListener('click', (event) => {
      event.stopPropagation();
      if (tk.menu.classList.contains('hidden')) moMenu(nut);
      else dongMenu();
    });
    tk.khoi.append(nut);
    tk.menuTen.textContent = nguoiDung.ten;
    tk.menuEmail.textContent = nguoiDung.email;
  }

  function moMenu(nut) {
    const khung = nut.getBoundingClientRect();
    tk.menu.classList.remove('hidden');
    tk.menu.style.left = `${Math.max(8, khung.left)}px`;
    tk.menu.style.width = `${Math.max(220, khung.width)}px`;
    tk.menu.style.bottom = `${window.innerHeight - khung.top + 6}px`;
    nut.setAttribute('aria-expanded', 'true');
    tk.menu.querySelector('button')?.focus();
  }

  function dongMenu() {
    tk.menu.classList.add('hidden');
    tk.khoi.querySelector('.tai-khoan-toi')?.setAttribute('aria-expanded', 'false');
  }

  document.addEventListener('click', (event) => {
    if (!tk.menu.contains(event.target)) dongMenu();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') dongMenu();
  });
  tk.menu.addEventListener('click', async (event) => {
    const nut = event.target.closest('button[data-tk]');
    if (!nut) return;
    dongMenu();
    if (nut.dataset.tk === 'doi-mat-khau') {
      moHop('doi-mat-khau');
      return;
    }
    try {
      await fetch('/api/tai-khoan/dang-xuat', { method: 'POST' });
    } catch {
      /* mất mạng: vẫn đăng xuất phía giao diện, cookie hết hạn sau */
    }
    await doiNguoiDung(null);
    showToast('Đã đăng xuất');
  });
  tk.nutTren.addEventListener('click', () => moHop('dang-nhap'));

  window.taiKhoanGiaoDien = { ve, moHop };

  // Khởi động: hỏi máy chủ xem trình duyệt này đang đăng nhập ai.
  (async () => {
    ve();
    try {
      const phanHoi = await fetch('/api/tai-khoan/toi', { cache: 'no-store' });
      if (!phanHoi.ok) throw new Error();
      const { nguoi_dung: nd, khoa_quan_tri: khoa } = await phanHoi.json();
      khoaQuanTri = khoa !== false;
      if (nd) await doiNguoiDung(nd, { lamMoi: false });
      else capNhatQuyenQuanTri();
    } catch {
      capNhatQuyenQuanTri();
    }
  })();
})();
