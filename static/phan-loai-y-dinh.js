/* ============================================================
   PHÂN LOẠI Ý ĐỊNH CÂU HỎI - KNN (chỉ quản trị viên)
   ============================================================
   Xem mô hình học máy đang chạy: kết quả lần đánh giá gần nhất (độ chính xác
   từng loại, ma trận nhầm lẫn, ngưỡng tự chặn, so sánh với mô hình khác),
   câu hỏi gần đây được xếp vào loại nào, và thử ngay một câu bất kỳ.
   Số liệu đánh giá sinh bởi `python phan_loai_y_dinh.py danh_gia`.
   ============================================================ */
(() => {
  const $id = (id) => document.getElementById(id);
  const yd = {
    hop: $id('ydDialog'),
    dong: $id('ydDong'),
    thuCau: $id('ydThuCau'),
    ketQuaThu: $id('ydKetQuaThu'),
    noiDung: $id('ydNoiDung'),
  };
  if (!yd.hop) return;

  let tenNhan = {};
  let henThu = null;
  let lanThu = 0;

  const so = (x, chuSo = 3) => Number(x || 0).toFixed(chuSo).replace('.', ',');
  const phanTram = (x) => `${Math.round((x || 0) * 100)}%`;
  const ten = (nhan) => tenNhan[nhan] || nhan;

  async function goi(duongDan, than) {
    const phanHoi = await fetch(duongDan, {
      method: than ? 'POST' : 'GET',
      headers: than ? { 'Content-Type': 'application/json' } : {},
      body: than ? JSON.stringify(than) : undefined,
      cache: 'no-store',
    });
    const noiDung = await phanHoi.json().catch(() => ({}));
    if (!phanHoi.ok) throw new Error(loiMayChu(noiDung, `Máy chủ trả về lỗi ${phanHoi.status}.`));
    return noiDung;
  }

  function the(loai, lop, chu) {
    const o = document.createElement(loai);
    if (lop) o.className = lop;
    if (chu !== undefined) o.textContent = chu;
    return o;
  }

  function bang(tieuDe, hang) {
    const t = the('table', 'yd-bang');
    const dau = t.createTHead().insertRow();
    for (const chu of tieuDe) dau.append(the('th', '', chu));
    const than = t.createTBody();
    for (const dong of hang) {
      const tr = than.insertRow();
      for (const o of dong) {
        const td = tr.insertCell();
        if (o instanceof Node) td.append(o);
        else td.textContent = o;
      }
    }
    return t;
  }

  function muc(tieuDe, ...con) {
    const khoi = the('section', 'yd-muc');
    khoi.append(the('h3', 'tn-tieu-de-bieu-do', tieuDe), ...con);
    return khoi;
  }

  // ---------- Thử một câu ----------
  const moTaHanhDong = {
    ngoai_pham_vi: 'Sẽ từ chối ngay, không truy hồi và không gọi mô hình ngôn ngữ',
    chao_hoi: 'Sẽ đáp lời chào ngay kèm câu gợi ý',
  };

  async function thuCau() {
    const cau = yd.thuCau.value.trim();
    const lan = ++lanThu;
    if (!cau) {
      yd.ketQuaThu.replaceChildren();
      return;
    }
    yd.ketQuaThu.textContent = 'Đang phân loại...';
    try {
      const kq = await goi('/api/quan-ly/y-dinh/thu-cau', { cau });
      if (lan !== lanThu) return;
      const dau = the('p', 'yd-thu-nhan');
      dau.append(the('strong', '', kq.ten_nhan), ` · ${phanTram(kq.do_tin_cay)} phiếu (k=${kq.k})`);
      const viec = the('p', 'tn-ghi-chu', moTaHanhDong[kq.hanh_dong]
        || 'Đi đường thường: công cụ tính nếu nhận ra, không thì truy hồi + mô hình ngôn ngữ.');
      const ds = the('ul', 'yd-lang-gieng');
      for (const lg of kq.lang_gieng || []) {
        ds.append(the('li', '', `${lg.cau_hoi} - ${lg.ten_nhan || ten(lg.nhan)}, giống ${so(lg.do_giong)}`));
      }
      yd.ketQuaThu.replaceChildren(dau, viec, the('p', 'tn-ghi-chu', 'Câu mẫu gần nhất:'), ds);
    } catch (error) {
      if (lan === lanThu) yd.ketQuaThu.textContent = error.message || 'Không phân loại được.';
    }
  }

  // ---------- Tổng quan ----------
  function veThongKe(thongKe) {
    if (!thongKe?.length) {
      return the('p', 'tn-ghi-chu', 'Chưa có lượt hỏi nào được phân loại trong 30 ngày qua.');
    }
    const lonNhat = Math.max(...thongKe.map((d) => d.so_luot));
    const ds = the('ul', 'tn-thanh-ds');
    for (const d of thongKe) {
      const hang = the('li', 'tn-thanh-hang yd-thanh-hang');
      const ray = the('span', 'tn-thanh-ray');
      const thanh = the('span', 'tn-thanh');
      thanh.style.width = `${(d.so_luot / lonNhat) * 100}%`;
      ray.append(thanh);
      hang.append(the('span', 'tn-thanh-nhan', ten(d.nhan)), ray, the('span', 'tn-thanh-so', String(d.so_luot)));
      ds.append(hang);
    }
    return ds;
  }

  function veDanhGia(dg) {
    if (!dg) {
      return [the('p', 'tn-ghi-chu', 'Chưa có kết quả đánh giá. Chạy: python phan_loai_y_dinh.py danh_gia')];
    }
    const cacNhan = Object.keys(tenNhan).filter((n) => dg.test.tung_lop[n]?.so_cau);
    const tong = the('div', 'tn-tong');
    tong.append(
      the('strong', '', so(dg.test.accuracy)),
      the('span', '', `accuracy · macro-F1 ${so(dg.test.macro_f1)} · ${dg.so_cau_test} câu test thật, `
        + `${dg.so_cau_train} câu train · đo lúc ${dg.thoi_diem}`),
    );

    const tungLop = bang(['Loại', 'Precision', 'Recall', 'F1', 'Số câu'], cacNhan.map((n) => {
      const m = dg.test.tung_lop[n];
      return [ten(n), so(m.precision), so(m.recall), so(m.f1), String(m.so_cau)];
    }));

    const maTran = bang(['Thật \\ Đoán', ...cacNhan.map(ten)], cacNhan.map((that) => [
      ten(that),
      ...cacNhan.map((doan) => {
        const giaTri = dg.test.ma_tran_nham_lan[that]?.[doan] || 0;
        const o = the('span', giaTri ? (that === doan ? 'yd-o dung' : 'yd-o sai') : 'yd-o', String(giaTri));
        return o;
      }),
    ]));

    const chonK = bang(['k', ...Object.keys(dg.kiem_dinh_cheo_bo_mot)], [[
      'macro-F1', ...Object.values(dg.kiem_dinh_cheo_bo_mot).map((v) => so(v)),
    ]]);

    const nguong = bang(
      ['Ngưỡng', 'Chặn ngoài phạm vi đúng', 'Chặn nhầm', 'Đáp lời chào đúng', 'Đáp nhầm'],
      Object.entries(dg.nguong_hanh_dong).map(([t, v]) => {
        const sao = (nhan) => (Number(t) === dg.nguong_dang_dung?.[nhan] ? ' *' : '');
        return [
          String(t).replace('.', ','),
          `${v.ngoai_pham_vi.bat_dung}/${v.ngoai_pham_vi.tren_tong}${sao('ngoai_pham_vi')}`,
          String(v.ngoai_pham_vi.bat_nham),
          `${v.chao_hoi.bat_dung}/${v.chao_hoi.tren_tong}${sao('chao_hoi')}`,
          String(v.chao_hoi.bat_nham),
        ];
      }),
    );

    const soSanh = bang(['Mô hình', 'Accuracy', 'macro-F1'],
      Object.entries(dg.so_sanh_mo_hinh).map(([tenMh, m]) => [tenMh, so(m.accuracy), so(m.macro_f1)]));

    return [
      tong,
      muc('Từng loại câu hỏi (tập test)', tungLop),
      muc('Ma trận nhầm lẫn', maTran),
      muc('Chọn k - kiểm định chéo bỏ-một trên tập train', chonK),
      muc('Ngưỡng tự hành động', nguong, the('p', 'tn-ghi-chu',
        'Câu đoán là ngoài phạm vi / chào hỏi với tỉ lệ phiếu từ ngưỡng trở lên thì được trả lời ngay. '
        + 'Cột "nhầm" là câu lẽ ra phải đi đường thường mà bị chặn - cần bằng 0. Dấu * là ngưỡng đang dùng.')),
      muc('So sánh với mô hình khác (cùng tập train/test)', soSanh),
    ];
  }

  async function mo() {
    yd.hop.showModal();
    yd.noiDung.replaceChildren(the('div', 'document-empty', 'Đang tải...'));
    try {
      const kq = await goi('/api/quan-ly/y-dinh');
      tenNhan = kq.ten_nhan || {};
      const trangThai = {
        san_sang: `Đang chạy · k=${kq.k} · ${kq.so_cau_mau} câu mẫu · ngưỡng chặn ${so(kq.nguong?.ngoai_pham_vi, 2)}, chào ${so(kq.nguong?.chao_hoi, 2)}`,
        dang_train: 'Đang train (nhúng câu mẫu bằng bge-m3)...',
        chua_nap: 'Chưa nạp - đợi chỉ mục khởi động xong',
        tat: 'Đang tắt (RAG_PHAN_LOAI_Y_DINH=0)',
        loi: 'Lỗi khi chuẩn bị mô hình - xem nhật ký máy chủ',
      }[kq.trang_thai] || kq.trang_thai;
      yd.noiDung.replaceChildren(
        the('p', 'document-summary yd-trang-thai', trangThai),
        ...veDanhGia(kq.danh_gia),
        muc('Câu hỏi 30 ngày qua theo loại', veThongKe(kq.thong_ke)),
      );
      yd.thuCau.focus();
    } catch (error) {
      yd.noiDung.replaceChildren(the('div', 'document-empty error', error.message || 'Không tải được.'));
    }
  }

  yd.thuCau.addEventListener('input', () => {
    window.clearTimeout(henThu);
    henThu = window.setTimeout(thuCau, 400);
  });
  yd.dong.addEventListener('click', () => yd.hop.close());
  yd.hop.addEventListener('click', (event) => {
    if (event.target === yd.hop) yd.hop.close();
  });

  window.phanLoaiYDinh = { mo };
})();
