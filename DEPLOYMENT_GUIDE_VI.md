# Hướng dẫn đưa ASPHALT CRACKING PREDICTION SYSTEM lên Streamlit Community Cloud

## Cấu trúc cần có trong GitHub repository

```text
asphalt_cracking_ai_project/
├── app.py
├── requirements.txt
├── README.md
├── DEPLOYMENT_GUIDE_VI.md
├── .gitignore
└── data/
    └── du_lieu_thuc_te_mau.xlsx
```

**Quan trọng:** `app.py`, `requirements.txt` và thư mục `data/` phải nằm ở gốc repository. Không upload cả file ZIP như một file đơn lẻ. Giải nén trước, rồi upload các tệp/thư mục bên trong.

## 1. Kiểm tra quyền chia sẻ dữ liệu

Ứng dụng mặc định đọc `data/du_lieu_thuc_te_mau.xlsx`. Nếu repository đặt Public, file Excel này cũng công khai và bất kỳ ai cũng có thể tải từ GitHub. Chỉ đặt repository Public nếu bạn có quyền công bố dữ liệu. Nếu chưa chắc, chọn Private và chỉ mời giảng viên/người cần xem qua quyền chia sẻ của Streamlit.

## 2. Tạo GitHub repository

1. Đăng nhập GitHub tại https://github.com/.
2. Mở https://github.com/new.
3. Đặt tên, ví dụ `asphalt-cracking-prediction`.
4. Chọn **Private** nếu dữ liệu chưa được phép công khai; chỉ chọn **Public** nếu được phép chia sẻ dữ liệu.
5. Không cần tick tạo README, `.gitignore` hay license vì dự án đã có các file này.
6. Nhấn **Create repository**.

## 3. Upload source code

1. Trong repository vừa tạo, chọn **Add file → Upload files**.
2. Mở thư mục `asphalt_cracking_ai_project` trên máy tính.
3. Kéo thả `app.py`, `requirements.txt`, `README.md`, `DEPLOYMENT_GUIDE_VI.md`, `.gitignore` và thư mục `data` vào vùng upload của GitHub. Có thể chọn upload folder hoặc kéo-thả folder theo giao diện GitHub.
4. Kiểm tra cấu trúc ở gốc repository có `app.py`, `requirements.txt`, `data/du_lieu_thuc_te_mau.xlsx`.
5. Nhập commit message, ví dụ `Upload asphalt cracking prediction app`, rồi nhấn **Commit changes**.

## 4. Deploy trên Streamlit Community Cloud

1. Mở https://share.streamlit.io/.
2. Chọn đăng nhập bằng GitHub và cấp quyền truy cập repository vừa tạo khi được yêu cầu.
3. Tại workspace, chọn **Create app**.
4. Chọn **Yup, I have an app**.
5. Chọn đúng Repository `asphalt-cracking-prediction`, Branch `main`, Main file path `app.py`.
6. Trong **Advanced settings**, chọn Python **3.12** (bản phát hành ổn định; không chọn bản prerelease như `3.12.0rc2`).
7. Có thể đặt App URL dạng `asphalt-cracking-prediction-...` nếu tên còn trống.
8. Nhấn **Deploy** và theo dõi log đến khi ứng dụng chạy xong.

## 5. Chia sẻ link

Sau khi deploy, Streamlit cấp một URL dạng `https://<ten-app>.streamlit.app`.

- Nếu app/repository Private: chỉ người được cấp quyền mới xem được. Mời giảng viên/người xem trong mục Share/Sharing của app; họ có thể cần đăng nhập.
- Nếu muốn bất kỳ ai có link đều mở được: chuyển app sang Public trong phần Sharing. Trước khi làm vậy, xác nhận dữ liệu trong repository được phép công khai. Repository Public cũng làm mã nguồn và file Excel công khai.

## 6. Khi cập nhật phần mềm

Sửa file trong GitHub rồi commit thay đổi. Streamlit Community Cloud sẽ tự phát hiện và cập nhật app. Nếu sửa `requirements.txt`, môi trường sẽ cài lại thư viện.

## 7. Lỗi thường gặp

- **ModuleNotFoundError:** kiểm tra tên/thư mục `requirements.txt`, đúng gốc repository, và log deploy.
- **Không tìm thấy file dữ liệu:** bảo đảm file nằm chính xác tại `data/du_lieu_thuc_te_mau.xlsx` và đã commit lên GitHub.
- **Deploy lỗi:** mở mục Manage app/Logs trên Streamlit, sao chép phần traceback cuối để kiểm tra.
- **App đang ngủ hoặc khởi động chậm:** mở URL và đợi dịch vụ khởi động; nếu vẫn lỗi, xem log trên dashboard.

Không gửi mật khẩu GitHub, mã xác thực hoặc thông tin đăng nhập cho bất kỳ ai.
