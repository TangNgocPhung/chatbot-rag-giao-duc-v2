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
    menuAnh: $id('menuTaiKhoanAnh'),
    menuNhan: $id('menuTaiKhoanXacMinh'),
    menuXacMinh: $id('menuXacMinh'),
    menuDoiAnhChu: $id('menuDoiAnhChu'),
    menuXoaAnh: $id('menuXoaAnh'),
    tepAnh: $id('anhDaiDienTep'),
    oMa: $id('authMaField'),
    ma: $id('authMa'),
    oMatKhau: $id('authMatKhauField'),
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
    suaEmailDong: $id('authSuaEmailDong'),
    suaEmail: $id('authSuaEmail'),
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
    'sua-thong-tin': {
      tieuDe: 'Sửa thông tin tài khoản',
      moTa: 'Đổi email thì cần mật khẩu hiện tại, và email mới phải xác minh lại.',
      gui: 'Lưu thay đổi',
      nhanMatKhau: 'Mật khẩu hiện tại (chỉ cần khi đổi email)',
      goiY: '',
      tuDien: 'current-password',
    },
    'xac-minh': {
      tieuDe: 'Xác minh email',
      moTa: 'Đang gửi mã…',
      gui: 'Xác minh',
      chuyenChu: 'Chưa nhận được thư?',
      chuyenNut: 'Gửi lại mã',
      ghiChu: 'Không thấy thư? Hãy xem cả thư mục Spam hoặc Quảng cáo.',
    },
  };
  const GHI_CHU_DANG_NHAP = tk.ghiChu.textContent;
  let cheDo = 'dang-nhap';
  // Máy chủ có gửi được thư không (lấy từ /api/tai-khoan/toi).
  let guiThu = false;
  let demNguoc = 0;
  let henDemNguoc = null;

  function datCheDo(moi) {
    cheDo = moi;
    const nd = CHE_DO[moi];
    const xacMinh = moi === 'xac-minh';
    tk.tieuDe.textContent = nd.tieuDe;
    tk.moTa.textContent = nd.moTa;
    tk.gui.textContent = nd.gui;
    if (nd.nhanMatKhau) tk.nhanMatKhau.textContent = nd.nhanMatKhau;
    tk.goiY.textContent = nd.goiY || '';
    tk.goiY.classList.toggle('hidden', !nd.goiY);
    if (nd.tuDien) tk.matKhau.autocomplete = nd.tuDien;
    const laSuaThongTin = moi === 'sua-thong-tin';
    tk.oTen.classList.toggle('hidden', moi !== 'dang-ky' && !laSuaThongTin);
    tk.oEmail.classList.toggle('hidden', moi === 'doi-mat-khau' || xacMinh);
    tk.oMatKhauCu.classList.toggle('hidden', moi !== 'doi-mat-khau');
    tk.oMatKhau.classList.toggle('hidden', xacMinh);
    tk.oMa.classList.toggle('hidden', !xacMinh);
    tk.chuyen.classList.toggle('hidden', moi === 'doi-mat-khau' || laSuaThongTin);
    tk.suaEmailDong.classList.toggle('hidden', !xacMinh);
    tk.ghiChu.textContent = nd.ghiChu || GHI_CHU_DANG_NHAP;
    tk.ghiChu.classList.toggle('hidden', moi !== 'dang-nhap' && !xacMinh);
    if (nd.chuyenChu) {
      tk.chuyenChu.textContent = nd.chuyenChu;
      tk.chuyenNut.textContent = nd.chuyenNut;
    }
    if (!xacMinh) datDemNguoc(0);
    baoLoi('');
  }

  // Nút "Gửi lại mã" khoá 60 giây giữa hai lần gửi, khớp giới hạn phía máy chủ.
  function datDemNguoc(giay) {
    demNguoc = giay;
    clearInterval(henDemNguoc);
    const hienNut = () => {
      if (cheDo !== 'xac-minh') return;
      tk.chuyenNut.disabled = demNguoc > 0;
      tk.chuyenNut.textContent = demNguoc > 0 ? `Gửi lại mã (${demNguoc}s)` : 'Gửi lại mã';
    };
    hienNut();
    if (giay > 0) {
      henDemNguoc = setInterval(() => {
        demNguoc -= 1;
        hienNut();
        if (demNguoc <= 0) clearInterval(henDemNguoc);
      }, 1000);
    }
    if (giay <= 0) tk.chuyenNut.disabled = false;
  }

  async function guiMaXacMinh() {
    baoLoi('');
    tk.chuyenNut.disabled = true;
    tk.moTa.textContent = 'Đang gửi mã…';
    try {
      const { email, phut } = await goi('/api/tai-khoan/gui-ma-xac-minh', {});
      tk.moTa.textContent = `Đã gửi mã 6 số tới ${email}. Mã có hiệu lực trong ${phut} phút.`;
      datDemNguoc(60);
    } catch (error) {
      tk.moTa.textContent = `Mã sẽ được gửi tới ${nguoiDung?.email || 'email của bạn'}.`;
      baoLoi(error.message);
      const giay = /(\d+) giây/.exec(error.message || '');
      datDemNguoc(giay ? Number(giay[1]) : 0);
    }
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
    if (moi === 'sua-thong-tin' && nguoiDung) {
      tk.ten.value = nguoiDung.ten || '';
      tk.email.value = nguoiDung.email || '';
    }
    if (!tk.hop.open) tk.hop.showModal();
    const dau = { 'dang-ky': tk.ten, 'doi-mat-khau': tk.matKhauCu, 'xac-minh': tk.ma, 'sua-thong-tin': tk.ten }[moi] || tk.email;
    dau.focus();
    if (moi === 'xac-minh') guiMaXacMinh();
  }

  function datMatKhauHien(hien) {
    for (const o of [tk.matKhau, tk.matKhauCu]) o.type = hien ? 'text' : 'password';
    tk.hien.textContent = hien ? 'Ẩn' : 'Hiện';
    tk.hien.setAttribute('aria-pressed', String(hien));
  }

  tk.hien.addEventListener('click', () => datMatKhauHien(tk.matKhau.type === 'password'));
  tk.suaEmail.addEventListener('click', () => {
    moHop('sua-thong-tin');
    tk.email.focus();
    tk.email.select();
  });
  tk.dong.addEventListener('click', () => tk.hop.close());
  tk.hop.addEventListener('click', (event) => {
    if (event.target === tk.hop) tk.hop.close();
  });
  tk.chuyenNut.addEventListener('click', () => {
    if (cheDo === 'xac-minh') {
      guiMaXacMinh();
      tk.ma.focus();
      return;
    }
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

  // Dán cả "Mã: 123 456" từ thư cũng được: chỉ giữ chữ số; đủ 6 số thì tự gửi.
  tk.ma.addEventListener('input', () => {
    const so = tk.ma.value.replace(/\D/g, '').slice(0, 6);
    if (tk.ma.value !== so) tk.ma.value = so;
    if (so.length === 6 && !tk.gui.disabled) tk.form.requestSubmit();
  });

  async function xacMinh() {
    const ma = tk.ma.value.replace(/\D/g, '');
    if (ma.length !== 6) {
      baoLoi('Mã xác minh gồm 6 chữ số.');
      tk.ma.focus();
      return;
    }
    const { nguoi_dung: nd } = await goi('/api/tai-khoan/xac-minh', { ma });
    tk.hop.close();
    await capNhatNguoiDung(nd);
    showToast('Đã xác minh email');
  }

  // Nhập sai email lúc đăng ký thì sửa được ngay, rồi xác minh email mới.
  async function suaThongTin() {
    const ten = tk.ten.value.trim();
    const email = tk.email.value.trim().toLowerCase();
    if (!ten) {
      baoLoi('Hãy nhập tên hiển thị.');
      tk.ten.focus();
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email)) {
      baoLoi('Email không hợp lệ.');
      tk.email.focus();
      return;
    }
    const doiEmail = email !== (nguoiDung?.email || '');
    if (doiEmail && !tk.matKhau.value) {
      baoLoi('Đổi email cần nhập mật khẩu hiện tại.');
      tk.matKhau.focus();
      return;
    }
    const { nguoi_dung: nd } = await goi('/api/tai-khoan/thong-tin', {
      ten, email, mat_khau: doiEmail ? tk.matKhau.value : '',
    });
    tk.hop.close();
    await capNhatNguoiDung(nd);
    showToast(doiEmail ? `Đã đổi email thành ${nd.email}` : 'Đã lưu thông tin');
    if (doiEmail && guiThu && !nd.da_xac_minh) moHop('xac-minh');
  }

  tk.form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (cheDo === 'xac-minh') {
      tk.gui.disabled = true;
      try {
        await xacMinh();
      } catch (error) {
        baoLoi(error.message || 'Không xác minh được, hãy thử lại.');
        tk.ma.select();
      } finally {
        tk.gui.disabled = false;
      }
      return;
    }
    if (cheDo === 'sua-thong-tin') {
      tk.gui.disabled = true;
      try {
        await suaThongTin();
      } catch (error) {
        baoLoi(error.message || 'Không lưu được, hãy thử lại.');
      } finally {
        tk.gui.disabled = false;
      }
      return;
    }
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
      // Như phần lớn trang web: đăng ký xong mời xác minh email luôn (bỏ qua được).
      if (dangKy && guiThu && !nd.da_xac_minh) moHop('xac-minh');
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
    veAvatar(avatar);
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
    veAvatar(tk.menuAnh);
    // Máy chủ không gửi được thư thì không ai xác minh nổi: đừng treo nhãn
    // "Chưa xác minh" mà không cho cách gỡ.
    const daXacMinh = Boolean(nguoiDung.da_xac_minh);
    tk.menuNhan.classList.toggle('hidden', !daXacMinh && !guiThu);
    tk.menuNhan.classList.toggle('da', daXacMinh);
    tk.menuNhan.textContent = daXacMinh ? 'Đã xác minh' : 'Chưa xác minh';
    tk.menuXacMinh.classList.toggle('hidden', daXacMinh || !guiThu);
    tk.menuDoiAnhChu.textContent = nguoiDung.anh ? 'Đổi ảnh đại diện' : 'Tải ảnh đại diện';
    tk.menuXoaAnh.classList.toggle('hidden', !nguoiDung.anh);
  }

  // Ảnh đại diện nếu có, không thì chữ cái đầu trên nền màu cố định theo tài khoản.
  function veAvatar(o) {
    o.className = `avatar-tk${o === tk.menuAnh ? ' lon' : ''}`;
    o.replaceChildren();
    o.style.background = mauTheoMa(nguoiDung.id);
    o.textContent = (nguoiDung.ten || nguoiDung.email).trim().charAt(0).toLocaleUpperCase('vi-VN');
    if (!nguoiDung.anh) return;
    const anh = new Image();
    anh.alt = '';
    anh.decoding = 'async';
    // Ảnh hỏng (vd. vừa bị gỡ ở máy khác) thì giữ chữ cái.
    anh.addEventListener('load', () => {
      o.textContent = '';
      o.append(anh);
      o.classList.add('co-anh');
    }, { once: true });
    anh.src = nguoiDung.anh;
  }

  // Cập nhật thông tin tài khoản mà không đổi người dùng (xác minh, đổi ảnh).
  // Xác minh có thể mở quyền quản trị: khi đó nạp lại như lúc đăng nhập.
  async function capNhatNguoiDung(nd) {
    if (Boolean(nd.quan_tri) !== Boolean(nguoiDung?.quan_tri)) {
      await doiNguoiDung(nd, { lamMoi: false });
      return;
    }
    nguoiDung = nd;
    ve();
  }

  // Thu ảnh về tối đa 768 px trước khi gửi: ảnh điện thoại 5-10 MB thành vài
  // trăm KB. Máy chủ vẫn tự cắt vuông và nén lại, nên thu nhỏ hỏng thì gửi nguyên.
  async function thuNhoAnh(tep) {
    try {
      const bmp = await createImageBitmap(tep, { imageOrientation: 'from-image' });
      const tile = Math.min(1, 768 / Math.max(bmp.width, bmp.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(bmp.width * tile));
      canvas.height = Math.max(1, Math.round(bmp.height * tile));
      canvas.getContext('2d').drawImage(bmp, 0, 0, canvas.width, canvas.height);
      bmp.close?.();
      const blob = await new Promise((xong) => canvas.toBlob(xong, 'image/webp', 0.9));
      return blob && blob.size < tep.size ? blob : tep;
    } catch {
      return tep;
    }
  }

  async function doiAnh(tep) {
    if (!tep.type.startsWith('image/')) {
      showToast('Hãy chọn một tệp ảnh');
      return;
    }
    showToast('Đang tải ảnh lên…');
    try {
      const anh = await thuNhoAnh(tep);
      const phanHoi = await fetch('/api/tai-khoan/anh-dai-dien', {
        method: 'PUT',
        headers: { 'Content-Type': anh.type || 'application/octet-stream', 'X-RAG-Action': 'avatar' },
        body: anh,
      });
      const noiDung = await phanHoi.json().catch(() => ({}));
      if (!phanHoi.ok) throw new Error(loiMayChu(noiDung, `Máy chủ trả về lỗi ${phanHoi.status}.`));
      await capNhatNguoiDung(noiDung.nguoi_dung);
      showToast('Đã đổi ảnh đại diện');
    } catch (error) {
      showToast(error.message || 'Không tải được ảnh lên');
    }
  }

  async function goAnh() {
    try {
      const phanHoi = await fetch('/api/tai-khoan/anh-dai-dien', { method: 'DELETE' });
      const noiDung = await phanHoi.json().catch(() => ({}));
      if (!phanHoi.ok) throw new Error(loiMayChu(noiDung, `Máy chủ trả về lỗi ${phanHoi.status}.`));
      await capNhatNguoiDung(noiDung.nguoi_dung);
      showToast('Đã gỡ ảnh đại diện');
    } catch (error) {
      showToast(error.message || 'Không gỡ được ảnh');
    }
  }

  tk.tepAnh.addEventListener('change', () => {
    const tep = tk.tepAnh.files?.[0];
    tk.tepAnh.value = '';
    if (tep) doiAnh(tep);
  });

  function moMenu(nut) {
    const khung = nut.getBoundingClientRect();
    tk.menu.classList.remove('hidden');
    tk.menu.style.left = `${Math.max(8, khung.left)}px`;
    tk.menu.style.width = `${Math.max(220, khung.width)}px`;
    tk.menu.style.bottom = `${window.innerHeight - khung.top + 6}px`;
    nut.setAttribute('aria-expanded', 'true');
    tk.menu.querySelector('button[data-tk]:not(.menu-tai-khoan-anh):not(.hidden)')?.focus();
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
    const viec = nut.dataset.tk;
    if (viec === 'doi-mat-khau' || viec === 'xac-minh' || viec === 'sua-thong-tin') {
      moHop(viec);
      return;
    }
    if (viec === 'doi-anh') {
      tk.tepAnh.click();
      return;
    }
    if (viec === 'xoa-anh') {
      await goAnh();
      return;
    }
    if (viec === 'quan-ly-tai-khoan') {
      closeSidebar();
      window.quanLyTaiKhoan?.mo();
      return;
    }
    if (viec !== 'dang-xuat') return;
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
      const { nguoi_dung: nd, khoa_quan_tri: khoa, gui_thu: coThu } = await phanHoi.json();
      khoaQuanTri = khoa !== false;
      guiThu = Boolean(coThu);
      if (nd) await doiNguoiDung(nd, { lamMoi: false });
      else capNhatQuyenQuanTri();
    } catch {
      capNhatQuyenQuanTri();
    }
  })();
})();
