@echo off
rem ============================================================
rem  MAU DAT KHOA GOOGLE DRIVE API
rem ============================================================
rem  1. Copy file nay thanh: khoa_api.bat
rem  2. Thay DAN_KHOA_VAO_DAY bang khoa that (dang AIzaSy...)
rem  3. Chay lai start_ui.bat
rem
rem  KHONG gui file khoa_api.bat cho ai, khong dua len Drive/GitHub.
rem ============================================================

set "RAG_DRIVE_API_KEY=DAN_KHOA_VAO_DAY"

rem ------------------------------------------------------------
rem  GUI MA XAC MINH EMAIL (tuy chon)
rem ------------------------------------------------------------
rem  Dung mot hop Gmail de gui ma 6 so khi nguoi dung xac minh email:
rem   1. Bat "Xac minh 2 buoc" cho hop Gmail do.
rem   2. Tao "Mat khau ung dung" tai https://myaccount.google.com/apppasswords
rem   3. Dan dia chi Gmail va mat khau ung dung (16 ky tu) vao hai dong duoi.
rem  Bo trong thi giao dien an nut "Xac minh email".
rem ------------------------------------------------------------
set "RAG_SMTP_TAI_KHOAN="
set "RAG_SMTP_MAT_KHAU="
