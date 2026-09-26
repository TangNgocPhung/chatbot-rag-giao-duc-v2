# Huong dan cho Claude Code

## Git

- Khong them trailer `Co-Authored-By` hay `Claude-Session` vao commit message.
- Tac gia commit phai la chu repo, khong phai Claude. Truoc khi commit lan dau
  trong moi phien, dat cau hinh cho repo nay:

  ```bash
  git config user.name "TangNgocPhung"
  git config user.email "tangphung126@gmail.com"
  ```

- Kiem tra truoc khi push: `git log -1 --format='%an <%ae>%n%B'` khong duoc
  chua `Claude` hay `noreply@anthropic.com`.
