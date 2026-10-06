/* ============================================================
   QUẢN LÝ TỪ NGỮ CẤM (chỉ quản trị viên)
   ============================================================
   Thêm từ chửi thề, tục tĩu, 18+ mới gặp mà không phải sửa mã nguồn; xoá từ
   đã thêm. Danh sách có sẵn trong loc_tu_ngu.py chỉ xem được ở đây - nó có
   test chốt chặn chặn nhầm nên muốn đổi thì sửa mã kèm test.

   Thêm một từ đi qua hai bước: xem trước (máy chủ thử từ đó trên các câu hỏi
   gần đây) rồi mới lưu. Từ chặn trúng câu hỏi cũ nào thì phải xác nhận lần
   nữa: từ cấm thêm nhầm ("cac") chặn cả "các môn học", và người bị chặn chỉ
   thấy bị nhắc vô cớ chứ không biết vì sao.
   ============================================================ */
(() => {
  const $id = (id) => document.getElementById(id);
  const tn = {
    hop: $id('tnDialog'),
    dong: $id('tnDong'),
    form: $id('tnForm'),
    tu: $id('tnTu'),
    nhom: $id('tnNhom'),
    them: $id('tnThem'),
    xemTruoc: $id('tnXemTruoc'),
    thuCau: $id('tnThuCau'),
    ketQuaThu: $id('tnKetQuaThu'),
    tabs: $id('tnTabs'),
    tomTat: $id('tnTomTat'),
    tim: $id('tnTim'),
    timO: $id('tnTimO'),
    danhSach: $id('tnDanhSach'),
  };
  if (!tn.hop) return;

  let nhanNhom = {};
  let tuThem = [];
  let tuCoSan = [];
  let loc = 'them';
  let henThu = null;
  let lanThu = 0;
  let soNgayThongKe = 30;
  let lanTaiThongKe = 0;

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

  const moTaDau = (khongDau) => (khongDau
    ? 'không dấu: chỉ chặn khi người dùng gõ không dấu'
    : 'có dấu: chỉ chặn khi người dùng gõ đúng dấu này');

  // ---------- Danh sách ----------
  function nguonHienTai() {
    const tuKhoa = tn.tim.value.trim().toLocaleLowerCase('vi-VN');
    const nguon = loc === 'them' ? tuThem : tuCoSan;
    return nguon.filter((muc) => muc.tu.includes(tuKhoa));
  }

  function ve() {
    for (const o of tn.tabs.querySelectorAll('[data-dem]')) {
      o.textContent = String(o.dataset.dem === 'them' ? tuThem.length : tuCoSan.length);
    }
    tn.timO.classList.toggle('hidden', loc === 'thong-ke');
    if (loc === 'thong-ke') {
      taiThongKe();
      return;
    }
    tn.tomTat.textContent = loc === 'them'
      ? 'Từ quản trị viên thêm, có hiệu lực ngay. Xoá là bỏ chặn ngay.'
      : 'Danh sách viết trong loc_tu_ngu.py, chỉ xem được ở đây. Muốn đổi thì sửa mã kèm test.';
    const nguon = nguonHienTai();
    tn.danhSach.replaceChildren();
    if (!nguon.length) {
      const trong = document.createElement('div');
      trong.className = 'document-empty';
      trong.textContent = tn.tim.value.trim()
        ? 'Không tìm thấy từ phù hợp.'
        : (loc === 'them' ? 'Chưa thêm từ nào. Bộ lọc đang dùng danh sách có sẵn.' : 'Danh sách trống.');
      tn.danhSach.append(trong);
      return;
    }
    for (const muc of nguon) tn.danhSach.append(veHang(muc));
  }

  function veHang(muc) {
    const hang = document.createElement('div');
    hang.className = 'document-row kho-hang qltk-hang';

    const avatar = document.createElement('span');
    avatar.className = 'avatar-tk qltk-avatar';
    avatar.textContent = muc.tu.charAt(0).toLocaleUpperCase('vi-VN');

    const info = document.createElement('span');
    info.className = 'document-info';
    const dong1 = document.createElement('span');
    dong1.className = 'qltk-dong-ten';
    const ten = document.createElement('strong');
    ten.textContent = muc.tu;
    ten.title = muc.tu;
    dong1.append(ten, nhan(nhanNhom[muc.nhom] || muc.nhom, 'nhom'));
    if (muc.khong_dau) dong1.append(nhan('Không dấu', 'toi'));
    const phu = document.createElement('small');
    phu.textContent = [
      moTaDau(muc.khong_dau),
      muc.tao_luc ? `thêm bởi ${muc.tao_boi} lúc ${dinhDangNgay(muc.tao_luc)}` : '',
    ].filter(Boolean).join(' · ');
    phu.title = phu.textContent;
    info.append(dong1, phu);

    const nut = document.createElement('span');
    nut.className = 'kho-hanh-dong';
    if (muc.id) {
      const xoa = document.createElement('button');
      xoa.type = 'button';
      xoa.className = 'kho-nut phu';
      xoa.textContent = 'Xoá';
      xoa.addEventListener('click', async () => {
        xoa.disabled = true;
        try {
          await xoaTu(muc);
        } catch (error) {
          showToast(error.message || 'Không xoá được');
        } finally {
          xoa.disabled = false;
        }
      });
      nut.append(xoa);
    }
    hang.append(avatar, info, nut);
    return hang;
  }

  // ---------- Thống kê ----------
  const KY_THONG_KE = [[7, '7 ngày'], [30, '30 ngày'], [365, '1 năm']];

  function tenVaiTro(ma) {
    if (!ma) return 'Chưa chọn vai trò';
    return window.vaiTroNguoiDung?.DANH_SACH.find((v) => v.ma === ma)?.nhan || ma;
  }

  async function taiThongKe() {
    const lan = ++lanTaiThongKe;
    tn.tomTat.textContent = 'Đang tải thống kê…';
    try {
      const kq = await goi(`/api/quan-ly/tu-ngu/thong-ke?so_ngay=${soNgayThongKe}`);
      if (lan !== lanTaiThongKe || loc !== 'thong-ke') return;
      veThongKe(kq);
    } catch (error) {
      if (lan !== lanTaiThongKe) return;
      tn.tomTat.textContent = '';
      const loi = document.createElement('div');
      loi.className = 'document-empty error';
      loi.textContent = error.message || 'Không tải được thống kê.';
      tn.danhSach.replaceChildren(loi);
    }
  }

  function veThongKe(kq) {
    tn.tomTat.textContent = 'Đếm cả câu bị chặn ngay ở ô nhập lẫn câu lên tới máy chủ mới bị chặn. '
      + 'Chỉ đếm nhóm vi phạm, không lưu nội dung câu.';
    const khung = document.createElement('div');
    khung.className = 'tn-thong-ke';

    const ky = document.createElement('div');
    ky.className = 'tn-ky';
    ky.setAttribute('role', 'group');
    ky.setAttribute('aria-label', 'Khoảng thời gian');
    for (const [soNgay, nhanKy] of KY_THONG_KE) {
      const nut = document.createElement('button');
      nut.type = 'button';
      nut.className = 'kho-nut';
      nut.textContent = nhanKy;
      nut.setAttribute('aria-pressed', String(soNgay === soNgayThongKe));
      nut.addEventListener('click', () => {
        soNgayThongKe = soNgay;
        taiThongKe();
      });
      ky.append(nut);
    }

    const tong = document.createElement('div');
    tong.className = 'tn-tong';
    const so = document.createElement('strong');
    so.textContent = kq.so_lan.toLocaleString('vi-VN');
    const moTa = document.createElement('span');
    moTa.textContent = kq.so_lan
      ? `lần bị chặn trong ${kq.so_ngay} ngày qua · ${kq.theo_nguon.giao_dien} ở ô nhập, ${kq.theo_nguon.may_chu} ở máy chủ`
      : `Chưa có câu nào bị chặn trong ${kq.so_ngay} ngày qua.`;
    tong.append(so, moTa);
    khung.append(ky, tong);

    if (kq.so_lan) {
      const tieuDe = document.createElement('p');
      tieuDe.className = 'tn-tieu-de-bieu-do';
      tieuDe.textContent = 'Số lần bị chặn theo nhóm';
      const ds = document.createElement('ul');
      ds.className = 'tn-thanh-ds';
      const lonNhat = Math.max(1, ...kq.theo_nhom.map((n) => n.so_lan));
      for (const n of kq.theo_nhom) {
        const ten = nhanNhom[n.nhom] || n.nhom;
        const chiTiet = `${ten}: ${n.so_lan} lần (ô nhập ${n.giao_dien}, máy chủ ${n.may_chu})`;
        const hang = document.createElement('li');
        hang.className = 'tn-thanh-hang';
        hang.title = chiTiet;
        hang.setAttribute('aria-label', chiTiet);
        const nhanHang = document.createElement('span');
        nhanHang.className = 'tn-thanh-nhan';
        nhanHang.textContent = ten;
        const ray = document.createElement('span');
        ray.className = 'tn-thanh-ray';
        const thanh = document.createElement('span');
        thanh.className = 'tn-thanh';
        thanh.style.width = `${(n.so_lan / lonNhat) * 100}%`;
        // 0 lần thì không vẽ gì: vạch tối thiểu 2px nhìn như có số liệu.
        if (n.so_lan) ray.append(thanh);
        const giaTri = document.createElement('span');
        giaTri.className = 'tn-thanh-so';
        giaTri.textContent = n.so_lan.toLocaleString('vi-VN');
        hang.append(nhanHang, ray, giaTri);
        ds.append(hang);
      }
      const ghiChu = document.createElement('p');
      ghiChu.className = 'tn-ghi-chu';
      ghiChu.textContent = 'Một câu vi phạm nhiều nhóm được tính ở mỗi nhóm. Rê chuột vào thanh để xem số ở ô nhập và ở máy chủ.';
      khung.append(tieuDe, ds, ghiChu);

      if (kq.theo_vai_tro.length) {
        const vaiTro = document.createElement('p');
        vaiTro.className = 'tn-ghi-chu';
        vaiTro.textContent = `Theo vai trò người hỏi: ${kq.theo_vai_tro
          .map((v) => `${tenVaiTro(v.vai_tro)} ${v.so_lan}`).join(' · ')}`;
        khung.append(vaiTro);
      }
    }
    tn.danhSach.replaceChildren(khung);
  }

  function chonLoc(moi) {
    loc = moi;
    for (const nut of tn.tabs.querySelectorAll('[data-loc]')) {
      nut.setAttribute('aria-selected', String(nut.dataset.loc === moi));
    }
    ve();
  }

  // Sau khi thêm/xoá: nạp lại bộ lọc phía giao diện của chính trang này, để
  // quản trị viên thử gõ ngay ở ô hỏi đáp cũng thấy kết quả mới.
  function capNhatBoLocGiaoDien() {
    window.locTuNgu?.taiLai?.();
    if (tn.thuCau.value.trim()) thuCau();
  }

  async function xoaTu(muc) {
    const dongY = await hoiXacNhan({
      tieuDe: `Bỏ chặn "${muc.tu}"?`,
      moTa: 'Câu hỏi có từ này sẽ không còn bị chặn nữa, có hiệu lực ngay.',
      nhanDongY: 'Bỏ chặn',
    });
    if (!dongY) return;
    await goi(`/api/quan-ly/tu-ngu/${encodeURIComponent(muc.id)}`, {
      method: 'DELETE', hanhDong: 'xoa-tu-ngu',
    });
    tuThem = tuThem.filter((m) => m.id !== muc.id);
    ve();
    capNhatBoLocGiaoDien();
    showToast(`Đã bỏ chặn "${muc.tu}"`, 2600);
  }

  // ---------- Thêm từ ----------
  function veXemTruoc(kq) {
    tn.xemTruoc.replaceChildren();
    tn.xemTruoc.classList.remove('hidden');
    tn.xemTruoc.classList.toggle('canh-bao', kq.so_cau_bi_chan > 0);
    const dong = document.createElement('div');
    const dam = document.createElement('strong');
    dam.textContent = `"${kq.tu}"`;
    dong.append(dam, ` · ${nhanNhom[kq.nhom] || kq.nhom} · ${moTaDau(kq.khong_dau)}.`);
    const tacDong = document.createElement('div');
    tacDong.textContent = kq.so_cau_xet
      ? (kq.so_cau_bi_chan
        ? `Sẽ chặn ${kq.so_cau_bi_chan} trong ${kq.so_cau_xet} câu hỏi gần đây. Hãy chắc đây không phải câu hỏi học tập bình thường:`
        : `Không chặn câu nào trong ${kq.so_cau_xet} câu hỏi gần đây.`)
      : 'Chưa có câu hỏi nào trong lịch sử để thử.';
    tn.xemTruoc.append(dong, tacDong);
    if (kq.vi_du?.length) {
      const ds = document.createElement('ul');
      for (const cau of kq.vi_du) {
        const li = document.createElement('li');
        li.textContent = cau;
        ds.append(li);
      }
      tn.xemTruoc.append(ds);
    }
  }

  function baoLoiXemTruoc(thongBao) {
    tn.xemTruoc.classList.remove('hidden');
    tn.xemTruoc.classList.add('canh-bao');
    tn.xemTruoc.textContent = thongBao;
  }

  async function themTu(event) {
    event.preventDefault();
    const tu = tn.tu.value.trim();
    if (!tu) return;
    const nhom = tn.nhom.value;
    tn.them.disabled = true;
    try {
      const kq = await goi('/api/quan-ly/tu-ngu/xem-truoc', {
        method: 'POST', than: { tu, nhom },
      });
      veXemTruoc(kq);
      if (kq.da_co) {
        baoLoiXemTruoc(`"${kq.tu}" đã có trong danh sách.`);
        return;
      }
      if (kq.so_cau_bi_chan > 0) {
        const dongY = await hoiXacNhan({
          tieuDe: `Vẫn thêm "${kq.tu}"?`,
          moTa: `Từ này chặn ${kq.so_cau_bi_chan} trong ${kq.so_cau_xet} câu hỏi gần đây (xem ví dụ dưới ô nhập). Nếu đó là câu hỏi bình thường thì từ này sẽ chặn nhầm người dùng.`,
          nhanDongY: 'Vẫn thêm',
        });
        if (!dongY) return;
      }
      const { tu_ngu: moi } = await goi('/api/quan-ly/tu-ngu', {
        method: 'POST', hanhDong: 'them-tu-ngu', than: { tu, nhom },
      });
      tuThem = [moi, ...tuThem];
      tn.tu.value = '';
      chonLoc('them');
      capNhatBoLocGiaoDien();
      showToast(`Đã chặn "${moi.tu}"`, 2600);
    } catch (error) {
      baoLoiXemTruoc(error.message || 'Không thêm được');
    } finally {
      tn.them.disabled = false;
    }
  }

  // ---------- Thử một câu ----------
  async function thuCau() {
    const cau = tn.thuCau.value.trim();
    const lan = ++lanThu;
    tn.ketQuaThu.className = 'tn-ket-qua-thu';
    if (!cau) {
      tn.ketQuaThu.textContent = '';
      return;
    }
    try {
      const kq = await goi('/api/quan-ly/tu-ngu/thu-cau', { method: 'POST', than: { cau } });
      if (lan !== lanThu) return; // đã gõ tiếp, kết quả này cũ rồi
      tn.ketQuaThu.classList.add(kq.vi_pham ? 'chan' : 'qua');
      tn.ketQuaThu.textContent = kq.vi_pham
        ? `Bị chặn · khớp "${kq.tu_khop.join('", "')}"`
        : 'Không bị chặn';
      tn.ketQuaThu.title = tn.ketQuaThu.textContent;
    } catch (error) {
      if (lan === lanThu) tn.ketQuaThu.textContent = error.message || 'Không thử được';
    }
  }

  // ---------- Mở hộp ----------
  async function mo() {
    tn.tim.value = '';
    tn.tu.value = '';
    tn.thuCau.value = '';
    tn.ketQuaThu.textContent = '';
    tn.xemTruoc.classList.add('hidden');
    chonLoc('them');
    tn.tomTat.textContent = 'Đang tải danh sách từ…';
    tn.danhSach.replaceChildren();
    if (!tn.hop.open) tn.hop.showModal();
    try {
      const kq = await goi('/api/quan-ly/tu-ngu');
      nhanNhom = Object.fromEntries(kq.nhom.map((n) => [n.ma, n.nhan]));
      tn.nhom.replaceChildren(...kq.nhom.map((n) => new Option(n.nhan, n.ma)));
      tuThem = kq.them || [];
      tuCoSan = [];
      for (const [bo, khongDau] of [[kq.co_san.co_dau, false], [kq.co_san.khong_dau, true]]) {
        for (const [nhom, cacTu] of Object.entries(bo)) {
          for (const tu of cacTu) tuCoSan.push({ tu, nhom, khong_dau: khongDau });
        }
      }
      ve();
      if (!kq.bat) tn.tomTat.textContent = 'Bộ lọc đang tắt (RAG_LOC_TU_NGU=0): từ thêm vào được lưu nhưng chưa chặn gì.';
      tn.tu.focus();
    } catch (error) {
      tn.tomTat.textContent = '';
      const loi = document.createElement('div');
      loi.className = 'document-empty error';
      loi.textContent = error.message || 'Không tải được danh sách từ.';
      tn.danhSach.replaceChildren(loi);
    }
  }

  tn.form.addEventListener('submit', themTu);
  tn.tu.addEventListener('input', () => tn.xemTruoc.classList.add('hidden'));
  tn.thuCau.addEventListener('input', () => {
    window.clearTimeout(henThu);
    henThu = window.setTimeout(thuCau, 300);
  });
  tn.tabs.addEventListener('click', (event) => {
    const nut = event.target.closest('[data-loc]');
    if (nut) chonLoc(nut.dataset.loc);
  });
  tn.tim.addEventListener('input', ve);
  tn.dong.addEventListener('click', () => tn.hop.close());
  tn.hop.addEventListener('click', (event) => {
    if (event.target === tn.hop) tn.hop.close();
  });

  window.quanLyTuNgu = { mo };
})();
