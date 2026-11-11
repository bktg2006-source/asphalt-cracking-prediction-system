# ASPHALT CRACKING PREDICTION SYSTEM

Website hỗ trợ đồ án Machine Learning dự đoán chỉ tiêu kháng nứt của bê tông nhựa chặt. Phiên bản này đi kèm file Excel mẫu đã được người dùng cung cấp.

## 1. Chức năng

- Đọc dữ liệu Excel (`.xlsx`, `.xls`) hoặc CSV.
- Xem dữ liệu và thống kê mô tả.
- Kiểm tra giá trị thiếu, dòng trùng lặp và cảnh báo quan hệ VFB–VMA–Air Voids.
- Chọn biến đầu vào và biến mục tiêu (mặc định `CT_Index`).
- So sánh Ridge Regression, Random Forest, Extra Trees, HistGradientBoosting và baseline bằng cross-validation.
- Đánh giá mô hình được chọn trên tập kiểm tra bằng R², MAE và RMSE.
- Nhập thông số mẫu mới để dự đoán; tải kết quả CSV.

## 2. Cài đặt trên Windows

Cài Python 3.10 hoặc mới hơn, sau đó mở Command Prompt tại thư mục dự án và chạy:

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Trình duyệt sẽ mở website tại địa chỉ mặc định `http://localhost:8501`.

Có thể chạy nhanh bằng cách nhấp đúp `run_windows.bat` sau khi đã cài dependencies.

## 3. Dữ liệu mẫu

File dữ liệu mẫu nằm tại:

```text
data/du_lieu_thuc_te_mau.xlsx
```

Ứng dụng mặc định đọc sheet `Du_Lieu_BTNC`. Khi tải file Excel khác, hãy chọn đúng sheet ở thanh bên.

## 4. Các cột của dữ liệu mẫu

| Cột | Ý nghĩa | Vai trò mặc định |
|---|---|---|
| `AC_percent` | Hàm lượng nhựa (%) | Đầu vào |
| `Air_Voids` | Độ rỗng dư (%) | Đầu vào |
| `VMA` | Độ rỗng cốt liệu (%) | Đầu vào |
| `VFB` | Độ rỗng lấp đầy nhựa (%) | Đầu vào |
| `Passing_4_75` | Lượng lọt sàng 4,75 mm (%) | Đầu vào |
| `Passing_2_36` | Lượng lọt sàng 2,36 mm (%) | Đầu vào |
| `CT_Index` | Chỉ số kháng nứt ghi trong file | Mục tiêu |

**Lưu ý quan trọng:** tên cột `CT_Index` gợi ý chỉ số CT Index nhưng không đủ để khẳng định phương pháp thí nghiệm. Cần đối chiếu sổ thí nghiệm, tiêu chuẩn, đơn vị và quy trình thử.

Trong bộ dữ liệu ban đầu, có nhiều giá trị VFB không khớp với phép kiểm tra nhanh theo công thức thường dùng `VFB = (VMA - Air_Voids) / VMA * 100`. Ứng dụng chỉ cảnh báo, không tự ý sửa hoặc xóa dữ liệu. Hãy xác minh định nghĩa và nguồn dữ liệu với tài liệu thí nghiệm trước khi đưa ra kết luận.

## 5. Cấu trúc thư mục

```text
asphalt_cracking_ai_project/
├── app.py
├── requirements.txt
├── README.md
├── run_windows.bat
└── data/
    └── du_lieu_thuc_te_mau.xlsx
```

## 6. Ghi chú học thuật

- Dữ liệu được chia thành tập huấn luyện và tập kiểm tra; cross-validation dùng trên tập huấn luyện để xếp hạng mô hình.
- Các giá trị thiếu ở biến đầu vào được điền bằng trung vị bên trong pipeline nhằm tránh rò rỉ dữ liệu giữa các fold.
- Chưa tự động loại ngoại lệ; cần đánh giá kỹ thuật trước khi xử lý.
- R², MAE, RMSE phụ thuộc vào tập dữ liệu và cách chia mẫu. Không có bảo đảm độ chính xác trước khi thực sự huấn luyện và kiểm chứng.
- Website là công cụ hỗ trợ học tập/nghiên cứu, không thay thế phép thử tiêu chuẩn hay quyết định thiết kế.
