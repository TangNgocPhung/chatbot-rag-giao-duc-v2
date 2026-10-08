/* ============================================================
   ĐỒ THỊ QUAN HỆ VĂN BẢN (chỉ quản trị viên)
   ============================================================
   Vẽ đồ thị đọc từ CSDL quan_he_van_ban.db qua /api/quan-ly/do-thi: nút là
   văn bản (màu = tình trạng hiệu lực), cạnh là quan hệ thay thế / sửa đổi /
   bãi bỏ / hướng dẫn / kèm theo; nét đứt là cạnh máy tự đọc từ nội dung,
   nét liền là cạnh sổ tay. Bấm một nút để xem chi tiết và mở tệp, bấm đúp
   để chỉ xem vùng quanh văn bản đó.
   Thư viện vis-network (MIT/Apache-2.0) chỉ tải khi mở trang này lần đầu.
   ============================================================ */
(() => {
  const $id = (id) => document.getElementById(id);
  const dt = {
    hop: $id('dtDialog'),
    dong: $id('dtDong'),
    tim: $id('dtTim'),
    danhSach: $id('dtDanhSach'),
    buoc: $id('dtBuoc'),
    caDoThi: $id('dtCaDoThi'),
    tomTat: $id('dtTomTat'),
    khung: $id('dtKhung'),
    chiTiet: $id('dtChiTiet'),
    chuGiai: $id('dtChuGiai'),
  };
  if (!dt.hop) return;

  const TEN_TINH_TRANG = {
    con_hieu_luc: 'Còn hiệu lực',
    da_sua_doi: 'Đã được sửa đổi',
    het_mot_phan: 'Hết hiệu lực một phần',
    sap_het_hieu_luc: 'Sắp hết hiệu lực',
    chua_hieu_luc: 'Chưa có hiệu lực',
    het_hieu_luc: 'Hết hiệu lực',
  };
  // Màu lấy từ biến CSS lúc vẽ để theo giao diện sáng/tối.
  const BIEN_TINH_TRANG = {
    con_hieu_luc: '--ok',
    da_sua_doi: '--warn',
    het_mot_phan: '--coral',
    sap_het_hieu_luc: '--purple',
    chua_hieu_luc: '--ink-faint',
    het_hieu_luc: '--danger',
  };
  const BIEN_LOAI = {
    thay_the: '--danger',
    sua_doi: '--blue',
    bai_bo_mot_phan: '--purple',
    huong_dan: '--ok',
    kem_theo: '--ink-mute',
  };

  let mang = null;
  let duLieu = null;
  let gocHienTai = [];
  let henThuVien = null;
  let lanTai = 0;

  const mau = (bien) => getComputedStyle(document.documentElement).getPropertyValue(bien).trim() || '#888888';

  function the(loai, lop, chu) {
    const o = document.createElement(loai);
    if (lop) o.className = lop;
    if (chu !== undefined) o.textContent = chu;
    return o;
  }

  function ngayVN(iso) {
    if (!iso) return '';
    const [nam, thang, ngay] = iso.split('-');
    return `${Number(ngay)}/${Number(thang)}/${nam}`;
  }

  function napThuVien() {
    if (window.vis?.Network) return Promise.resolve();
    henThuVien ||= new Promise((xong, loi) => {
      const s = document.createElement('script');
      s.src = './vendor/vis-network-9.1.2.min.js';
      s.onload = xong;
      s.onerror = () => {
        henThuVien = null;
        loi(new Error('Không tải được thư viện vẽ đồ thị.'));
      };
      document.head.append(s);
    });
    return henThuVien;
  }

  async function taiDuLieu(goc) {
    const thamSo = new URLSearchParams({ goc: goc.join(','), buoc: dt.buoc.value });
    const phanHoi = await fetch(`/api/quan-ly/do-thi?${thamSo}`, { cache: 'no-store' });
    const noiDung = await phanHoi.json().catch(() => ({}));
    if (!phanHoi.ok) throw new Error(loiMayChu(noiDung, `Máy chủ trả về lỗi ${phanHoi.status}.`));
    return noiDung;
  }

  // ---------- Tìm văn bản ----------
  function dienDanhSach(tatCa) {
    const tuyChon = [];
    for (const vb of tatCa) {
      const o = document.createElement('option');
      o.value = vb.so_hieu;
      o.label = vb.tep.length ? `${vb.nhan} · ${vb.tep[0]}` : vb.nhan;
      tuyChon.push(o);
    }
    dt.danhSach.replaceChildren(...tuyChon);
  }

  /** Số hiệu ứng với chữ đã gõ: đủ số hiệu, tên tệp, hoặc phần đầu số hiệu
   *  chỉ khớp đúng một văn bản ("43/2019"). */
  function timSoHieu(chu) {
    const tatCa = duLieu?.tat_ca || [];
    const gon = chu.trim().toLowerCase();
    if (!gon) return null;
    const dung = tatCa.find((vb) => vb.so_hieu.toLowerCase() === gon
      || vb.tep.some((t) => t.toLowerCase() === gon));
    if (dung) return dung.so_hieu;
    const dau = tatCa.filter((vb) => vb.so_hieu.toLowerCase().startsWith(gon)
      || vb.tep.some((t) => t.toLowerCase().includes(gon)));
    return dau.length === 1 ? dau[0].so_hieu : null;
  }

  function xemQuanh(soHieu) {
    dt.tim.value = soHieu;
    hienThi([soHieu]);
  }

  // ---------- Chi tiết bên phải ----------
  function moTep(ten) {
    const url = `/api/source?name=${encodeURIComponent(ten)}`;
    const taiLieu = window.khongGianHoc?.tuDuongDan(url, ten);
    if (taiLieu) {
      dt.hop.close();
      window.khongGianHoc.moTaiLieu(taiLieu);
    } else {
      window.open(url, '_blank', 'noopener');
    }
  }

  function goiYBanDau() {
    const khoi = the('div', 'dt-goi-y');
    khoi.append(
      the('p', '', 'Bấm vào một văn bản để xem tình trạng, tệp trong kho và các quan hệ của nó.'),
      the('p', '', 'Bấm đúp để chỉ xem vùng quanh văn bản đó. Cuộn chuột để phóng to, kéo để di chuyển.'),
    );
    dt.chiTiet.replaceChildren(khoi);
  }

  function chiTietNut(soHieu) {
    const nut = duLieu.nut.find((n) => n.so_hieu === soHieu);
    if (!nut) return goiYBanDau();
    const khoi = [];
    khoi.push(the('h3', 'dt-ten', nut.nhan));
    const trangThai = the('p', 'dt-trang-thai');
    const nhan = the('span', `dt-nhan tt-${nut.tinh_trang}`, TEN_TINH_TRANG[nut.tinh_trang] || nut.tinh_trang);
    trangThai.append(nhan);
    if (nut.tu_ngay) trangThai.append(` từ ${ngayVN(nut.tu_ngay)}`);
    khoi.push(trangThai);
    if (nut.ngay_hieu_luc) khoi.push(the('p', 'dt-phu', `Hiệu lực từ ${ngayVN(nut.ngay_hieu_luc)}`));

    khoi.push(the('h4', 'dt-muc', 'Tệp trong kho'));
    if (nut.tep.length) {
      const ds = the('ul', 'dt-ds-tep');
      for (const ten of nut.tep) {
        const nutTep = the('button', 'dt-tep', ten);
        nutTep.type = 'button';
        nutTep.title = 'Mở tệp';
        nutTep.addEventListener('click', () => moTep(ten));
        const li = the('li');
        li.append(nutTep);
        ds.append(li);
      }
      khoi.push(ds);
    } else {
      khoi.push(the('p', 'dt-phu', 'Không có trong kho - chỉ được văn bản khác nhắc tới.'));
    }

    const lienQuan = duLieu.canh.filter((c) => c.tu === soHieu || c.den === soHieu);
    khoi.push(the('h4', 'dt-muc', `Quan hệ (${lienQuan.length})`));
    const ds = the('ul', 'dt-ds-quan-he');
    for (const c of lienQuan) {
      const ra = c.tu === soHieu;
      const kia = ra ? c.den : c.tu;
      const ten = (duLieu.loai_quan_he[c.loai] || [c.ten, c.ten])[ra ? 0 : 1];
      const li = the('li');
      li.style.setProperty('--mau-canh', mau(BIEN_LOAI[c.loai]));
      const nutKia = the('button', 'dt-lien-ket', kia);
      nutKia.type = 'button';
      nutKia.addEventListener('click', () => chonNut(kia));
      li.append(the('span', 'dt-loai', ten), ' ', nutKia);
      if (c.nguon === 'tu_dong') li.append(the('span', 'dt-nguon', 'máy đọc'));
      if (c.can_cu) li.title = c.can_cu;
      ds.append(li);
    }
    if (lienQuan.length) khoi.push(ds);

    if (!(gocHienTai.length === 1 && gocHienTai[0] === soHieu)) {
      const nutQuanh = the('button', 'dt-nut dt-nut-chinh', 'Chỉ xem vùng quanh văn bản này');
      nutQuanh.type = 'button';
      nutQuanh.addEventListener('click', () => xemQuanh(soHieu));
      khoi.push(nutQuanh);
    }
    dt.chiTiet.replaceChildren(...khoi);
  }

  function chiTietCanh(maCanh) {
    const c = duLieu.canh[Number(maCanh)];
    if (!c) return goiYBanDau();
    const nhanCua = (s) => duLieu.nut.find((n) => n.so_hieu === s)?.nhan || s;
    const khoi = [the('h3', 'dt-ten', c.ten)];
    const p = the('p', 'dt-cau-canh');
    const nutTu = the('button', 'dt-lien-ket', nhanCua(c.tu));
    nutTu.type = 'button';
    nutTu.addEventListener('click', () => chonNut(c.tu));
    const nutDen = the('button', 'dt-lien-ket', nhanCua(c.den));
    nutDen.type = 'button';
    nutDen.addEventListener('click', () => chonNut(c.den));
    p.append(nutTu, ` ${c.ten.toLowerCase()} `, nutDen);
    khoi.push(p);
    khoi.push(the('p', 'dt-phu', c.nguon === 'so_tay'
      ? 'Nguồn: sổ tay (người nhập, đã xác nhận)'
      : 'Nguồn: máy tự đọc từ nội dung văn bản - sai thì chặn bằng "loai_bo" trong so_quan_he_van_ban.json'));
    if (c.can_cu) {
      khoi.push(the('h4', 'dt-muc', 'Căn cứ'), the('p', 'dt-phu', c.can_cu));
    }
    dt.chiTiet.replaceChildren(...khoi);
  }

  function chonNut(soHieu) {
    if (!mang) return;
    if (!duLieu.nut.some((n) => n.so_hieu === soHieu)) {
      xemQuanh(soHieu);
      return;
    }
    mang.selectNodes([soHieu]);
    mang.focus(soHieu, { scale: Math.max(mang.getScale(), 0.9), animation: { duration: 400 } });
    chiTietNut(soHieu);
  }

  // ---------- Vẽ ----------
  function veChuGiai() {
    const khoi = [];
    for (const [ma, bien] of Object.entries(BIEN_TINH_TRANG)) {
      const muc = the('span', 'dt-chu-giai-muc');
      const cham = the('i', 'dt-cham');
      cham.style.background = mau(bien);
      muc.append(cham, TEN_TINH_TRANG[ma]);
      khoi.push(muc);
    }
    for (const [ma, ten] of Object.entries(duLieu.loai_quan_he || {})) {
      const muc = the('span', 'dt-chu-giai-muc');
      const vach = the('i', 'dt-vach');
      vach.style.background = mau(BIEN_LOAI[ma]);
      muc.append(vach, ten[0]);
      khoi.push(muc);
    }
    const net = the('span', 'dt-chu-giai-muc');
    net.append(the('i', 'dt-vach dt-vach-dut'), 'máy đọc (nét liền: sổ tay)');
    khoi.push(net);
    dt.chuGiai.replaceChildren(...khoi);
  }

  function ve() {
    const chu = mau('--ink');
    const nen = mau('--surface');
    const nodes = duLieu.nut.map((n) => {
      const mauNut = mau(BIEN_TINH_TRANG[n.tinh_trang] || '--ink-faint');
      const trongKho = n.tep.length > 0;
      return {
        id: n.so_hieu,
        label: n.so_hieu,
        shape: n.goc ? 'star' : 'dot',
        size: n.goc ? 22 : (trongKho ? 11 : 7),
        borderWidth: trongKho ? 1 : 2,
        color: {
          background: trongKho ? mauNut : nen,
          border: mauNut,
          highlight: { background: mauNut, border: chu },
          hover: { background: mauNut, border: chu },
        },
        font: { color: chu, size: n.goc ? 15 : 12, strokeWidth: 3, strokeColor: nen },
      };
    });
    const edges = duLieu.canh.map((c, i) => ({
      id: String(i),
      from: c.tu,
      to: c.den,
      arrows: { to: { enabled: true, scaleFactor: 0.6 } },
      dashes: c.nguon === 'tu_dong',
      color: { color: mau(BIEN_LOAI[c.loai]), highlight: mau(BIEN_LOAI[c.loai]), opacity: 0.85 },
      width: 1.4,
      selectionWidth: 1.5,
    }));
    const tuyChon = {
      autoResize: true,
      interaction: { hover: true, tooltipDelay: 150, navigationButtons: false, keyboard: false },
      physics: {
        solver: 'forceAtlas2Based',
        forceAtlas2Based: { gravitationalConstant: -45, springLength: 90, avoidOverlap: 0.4 },
        stabilization: { iterations: 300, fit: true },
      },
      nodes: { scaling: { label: { drawThreshold: 4 } } },
      edges: { smooth: { type: 'continuous' } },
    };
    if (mang) mang.destroy();
    mang = new window.vis.Network(dt.khung, { nodes, edges }, tuyChon);
    // Đứng yên sau khi xếp xong: kéo một nút không làm cả đồ thị trôi theo.
    mang.once('stabilizationIterationsDone', () => mang.setOptions({ physics: false }));
    mang.on('click', (su) => {
      if (su.nodes.length) chiTietNut(su.nodes[0]);
      else if (su.edges.length) chiTietCanh(su.edges[0]);
      else goiYBanDau();
    });
    mang.on('doubleClick', (su) => {
      if (su.nodes.length) xemQuanh(su.nodes[0]);
    });
  }

  async function hienThi(goc) {
    const lan = ++lanTai;
    dt.tomTat.textContent = 'Đang tải đồ thị...';
    try {
      const [kq] = await Promise.all([taiDuLieu(goc), napThuVien()]);
      if (lan !== lanTai) return;
      duLieu = kq;
      gocHienTai = kq.goc;
      if (!dt.danhSach.childElementCount) dienDanhSach(kq.tat_ca);
      const vung = goc.length
        ? `Quanh ${goc.join(', ')} (${dt.buoc.value} bước) · `
        : 'Cả kho, chỉ văn bản có quan hệ · ';
      dt.tomTat.textContent = `${vung}${kq.nut.length} văn bản · ${kq.canh.length} quan hệ`
        + (kq.ngay_tinh ? ` · tình trạng tính ngày ${ngayVN(kq.ngay_tinh)}` : '');
      if (goc.length && !kq.nut.length) {
        dt.tomTat.textContent = `Không thấy ${goc.join(', ')} trong CSDL quan hệ.`;
      }
      veChuGiai();
      ve();
      if (gocHienTai.length === 1) chiTietNut(gocHienTai[0]);
      else goiYBanDau();
    } catch (error) {
      if (lan === lanTai) dt.tomTat.textContent = error.message || 'Không tải được đồ thị.';
    }
  }

  async function mo(soHieu) {
    if (!dt.hop.open) dt.hop.showModal();
    if (soHieu) xemQuanh(soHieu);
    else if (!duLieu) hienThi([]);
  }

  dt.tim.addEventListener('change', () => {
    const chu = dt.tim.value;
    if (!chu.trim()) return;
    const soHieu = timSoHieu(chu);
    if (soHieu) xemQuanh(soHieu);
    else dt.tomTat.textContent = `Không thấy văn bản nào khớp "${chu.trim()}" - gõ đủ số hiệu (vd 43/2019/QH14) hoặc chọn trong danh sách.`;
  });
  dt.buoc.addEventListener('change', () => {
    if (gocHienTai.length) hienThi(gocHienTai);
  });
  dt.caDoThi.addEventListener('click', () => {
    dt.tim.value = '';
    hienThi([]);
  });
  dt.dong.addEventListener('click', () => dt.hop.close());
  dt.hop.addEventListener('click', (event) => {
    if (event.target === dt.hop) dt.hop.close();
  });

  window.doThiQuanHe = { mo };
})();
