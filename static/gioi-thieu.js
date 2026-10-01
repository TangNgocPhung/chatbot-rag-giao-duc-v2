/* ============================================================
   GIỚI THIỆU NHANH
   ============================================================
   Hộp thoại năm bước tự mở ở lần đầu vào trang, thay cho việc bắt người mới
   đọc cả HUONG_DAN_SU_DUNG.md. Bước đầu hỏi người dùng là ai (vai-tro.js) để
   màn hình chào gợi ý câu hỏi hợp với họ; không chọn cũng đi tiếp được. Đã mở một lần (dù xem hết hay bấm Bỏ qua) là
   ghi nhớ trong trình duyệt, lần sau không hiện nữa; bản đầy đủ vẫn ở nút
   "Hướng dẫn" trên thanh trên cùng. Nội dung các bước nằm trong index.html.
   ============================================================ */
(() => {
  const $id = (id) => document.getElementById(id);
  const gt = {
    hop: $id('gioiThieuDialog'),
    nhanBuoc: $id('gioiThieuBuoc'),
    cham: document.querySelector('#gioiThieuDialog .gt-cham'),
    dong: $id('gioiThieuDong'),
    boQua: $id('gioiThieuBoQua'),
    dayDu: $id('gioiThieuDayDu'),
    lui: $id('gioiThieuLui'),
    tiep: $id('gioiThieuTiep'),
    vaiTro: $id('gioiThieuVaiTro'),
  };
  if (!gt.hop) return;

  const KHOA_DA_XEM = 'rag-giao-duc-da-xem-gioi-thieu-v1';
  // Lịch sử khách do app.js lưu: có rồi nghĩa là người cũ, không phải lần đầu.
  const KHOA_LICH_SU = 'rag-giao-duc-history-v1';
  let cacBuoc = [];
  let buoc = 0;

  // ---------- Bước chọn vai trò ----------
  const vaiTro = window.vaiTroNguoiDung;
  function danhDauVaiTro(ma) {
    for (const nut of gt.vaiTro?.children || []) {
      nut.setAttribute('aria-pressed', String(nut.dataset.vaiTro === ma));
    }
  }
  if (gt.vaiTro && vaiTro) {
    gt.vaiTro.replaceChildren(...vaiTro.DANH_SACH.map(({ ma, nhan }) => {
      const nut = document.createElement('button');
      nut.type = 'button';
      nut.dataset.vaiTro = ma;
      nut.textContent = nhan;
      // Chọn xong tự sang bước sau, chậm một nhịp để kịp thấy nút được chọn.
      nut.addEventListener('click', () => {
        vaiTro.dat(ma);
        window.setTimeout(() => { if (buoc === 0) hienBuoc(1); }, 180);
      });
      return nut;
    }));
    danhDauVaiTro(vaiTro.lay());
    vaiTro.khiDoi(danhDauVaiTro);
  } else {
    // vai-tro.js không tải được thì bỏ hẳn bước này, bốn bước sau vẫn dùng được.
    gt.vaiTro?.closest('[data-buoc]')?.remove();
  }
  cacBuoc = [...gt.hop.querySelectorAll('[data-buoc]')];
  gt.cham.replaceChildren(...cacBuoc.map(() => document.createElement('span')));

  function hienBuoc(moi) {
    buoc = Math.max(0, Math.min(moi, cacBuoc.length - 1));
    const cuoi = buoc === cacBuoc.length - 1;
    cacBuoc.forEach((phan, i) => { phan.hidden = i !== buoc; });
    [...gt.cham.children].forEach((cham, i) => cham.classList.toggle('dang-xem', i === buoc));
    gt.nhanBuoc.textContent = `BƯỚC ${buoc + 1}/${cacBuoc.length}`;
    gt.lui.classList.toggle('hidden', buoc === 0);
    gt.boQua.classList.toggle('hidden', cuoi);
    gt.dayDu.classList.toggle('hidden', !cuoi);
    gt.tiep.textContent = cuoi ? 'Bắt đầu hỏi' : 'Tiếp';
  }

  function mo() {
    hienBuoc(0);
    if (!gt.hop.open) gt.hop.showModal();
    gt.tiep.focus();
  }

  function dong() {
    gt.hop.close();
  }

  gt.tiep.addEventListener('click', () => {
    if (buoc < cacBuoc.length - 1) {
      hienBuoc(buoc + 1);
      return;
    }
    dong();
    $id('questionInput')?.focus();
  });
  gt.lui.addEventListener('click', () => hienBuoc(buoc - 1));
  gt.dong.addEventListener('click', dong);
  gt.boQua.addEventListener('click', dong);
  gt.dayDu.addEventListener('click', () => {
    dong();
    window.huongDanGiaoDien?.mo();
  });
  gt.hop.addEventListener('click', (event) => {
    if (event.target === gt.hop) dong();
  });
  gt.hop.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowRight') hienBuoc(buoc + 1);
    else if (event.key === 'ArrowLeft') hienBuoc(buoc - 1);
  });

  // ---------- Chỉ lần đầu ----------
  function laLanDau() {
    try {
      if (localStorage.getItem(KHOA_DA_XEM)) return false;
      const lichSu = JSON.parse(localStorage.getItem(KHOA_LICH_SU) || '[]');
      if (Array.isArray(lichSu) && lichSu.length) {
        localStorage.setItem(KHOA_DA_XEM, '1');
        return false;
      }
      localStorage.setItem(KHOA_DA_XEM, '1');
      return true;
    } catch {
      // Trình duyệt chặn lưu trữ thì không nhớ được đã xem: thà không hiện
      // còn hơn lần nào tải trang cũng bật lên.
      return false;
    }
  }

  // Chờ trang dựng xong một nhịp cho người dùng thấy giao diện phía sau; nếu
  // lúc đó đang có hộp thoại khác (đăng nhập, kho tài liệu…) thì nhường.
  setTimeout(() => {
    if (document.querySelector('dialog[open]')) return;
    if (laLanDau()) mo();
  }, 600);

  window.gioiThieuNhanh = { mo };
})();
