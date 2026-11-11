from __future__ import annotations

from pathlib import Path
import io
import math
import warnings

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyRegressor


APP_DIR = Path(__file__).resolve().parent
DEFAULT_FILE = APP_DIR / "data" / "du_lieu_thuc_te_mau.xlsx"
DEFAULT_SHEET = "Du_Lieu_BTNC"
RANDOM_STATE = 42

st.set_page_config(
    page_title="Asphalt Cracking Prediction",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🛣️ ASPHALT CRACKING PREDICTION SYSTEM")
st.caption("Machine Learning cho dự đoán chỉ tiêu kháng nứt của bê tông nhựa chặt")

st.info(
    "Phiên bản đồ án học thuật. Mô hình chỉ học từ dữ liệu được cung cấp; kết quả không thay thế "
    "thí nghiệm, tiêu chuẩn thiết kế hoặc đánh giá của kỹ sư. Hãy xác minh nguồn dữ liệu, phương pháp "
    "thí nghiệm và đơn vị trước khi sử dụng kết quả."
)


def load_uploaded_file(uploaded_file) -> tuple[pd.DataFrame, str]:
    """Read an Excel or CSV upload and return its data plus the selected sheet name."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        # utf-8-sig handles common Excel-exported CSV files.
        try:
            return pd.read_csv(uploaded_file, encoding="utf-8-sig"), "CSV"
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding="cp1258"), "CSV"

    if name.endswith(('.xlsx', '.xls')):
        excel = pd.ExcelFile(uploaded_file)
        sheet_names = excel.sheet_names
        preferred = DEFAULT_SHEET if DEFAULT_SHEET in sheet_names else sheet_names[0]
        selected = st.sidebar.selectbox(
            "Sheet dữ liệu",
            options=sheet_names,
            index=sheet_names.index(preferred),
            help="Chọn sheet chứa bảng dữ liệu mẫu thí nghiệm.",
        )
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file, sheet_name=selected), selected

    raise ValueError("Định dạng chưa được hỗ trợ. Vui lòng chọn file .xlsx, .xls hoặc .csv.")


def load_default_data() -> tuple[pd.DataFrame, str, str]:
    if not DEFAULT_FILE.exists():
        raise FileNotFoundError("Không tìm thấy dữ liệu mẫu trong thư mục data/.")
    xl = pd.ExcelFile(DEFAULT_FILE)
    sheet = DEFAULT_SHEET if DEFAULT_SHEET in xl.sheet_names else xl.sheet_names[0]
    return pd.read_excel(DEFAULT_FILE, sheet_name=sheet), sheet, DEFAULT_FILE.name


def numeric_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Convert possible numeric text columns while preserving non-numeric columns."""
    result = df.copy()
    for col in result.columns:
        converted = pd.to_numeric(result[col], errors="coerce")
        # Convert only if at least one value becomes numeric.
        if converted.notna().any():
            result[col] = converted
    return result


def build_models() -> dict[str, Pipeline]:
    """Small, explainable model set suitable for an initial 300-row dataset."""
    return {
        "Ridge Regression": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=1.0)),
        ]),
        "Random Forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestRegressor(
                n_estimators=350,
                min_samples_leaf=2,
                max_features=1.0,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )),
        ]),
        "Extra Trees": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", ExtraTreesRegressor(
                n_estimators=400,
                min_samples_leaf=2,
                max_features=1.0,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )),
        ]),
        "Hist. Gradient Boosting": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", HistGradientBoostingRegressor(
                max_iter=180,
                learning_rate=0.05,
                max_leaf_nodes=15,
                l2_regularization=1.0,
                random_state=RANDOM_STATE,
            )),
        ]),
        "Baseline (Mean)": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", DummyRegressor(strategy="mean")),
        ]),
    }


def get_vfb_quality_check(df: pd.DataFrame) -> dict | None:
    """Compare VFB to the common volumetric relationship as a data-QC flag only."""
    needed = {"VMA", "Air_Voids", "VFB"}
    if not needed.issubset(df.columns):
        return None
    temp = df[["VMA", "Air_Voids", "VFB"]].apply(pd.to_numeric, errors="coerce").dropna()
    temp = temp[temp["VMA"] > 0]
    if temp.empty:
        return None
    calculated = (temp["VMA"] - temp["Air_Voids"]) / temp["VMA"] * 100
    difference = temp["VFB"] - calculated
    return {
        "n": int(len(temp)),
        "over_5": int((difference.abs() > 5).sum()),
        "mean_abs_difference": float(difference.abs().mean()),
        "mean_difference": float(difference.mean()),
        "observed": temp["VFB"],
        "calculated": calculated,
    }


def train_and_evaluate(df: pd.DataFrame, features: list[str], target: str, test_size: float):
    work = df[features + [target]].copy()
    for col in work.columns:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.replace([np.inf, -np.inf], np.nan)
    work = work.dropna(subset=[target])

    # Keep rows with missing predictors: the pipelines impute them using training-fold medians.
    X = work[features]
    y = work[target]

    if len(work) < 30:
        raise ValueError("Cần tối thiểu 30 dòng hợp lệ để chia tập và so sánh mô hình ở mức cơ bản.")
    if y.nunique() < 2:
        raise ValueError("Cột mục tiêu cần có ít nhất hai giá trị khác nhau.")
    usable_features = [c for c in features if X[c].notna().any() and X[c].nunique(dropna=True) > 1]
    if not usable_features:
        raise ValueError("Không có biến đầu vào hợp lệ (cột rỗng hoặc chỉ có một giá trị).")
    X = X[usable_features]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=RANDOM_STATE
    )
    n_splits = min(5, max(2, len(X_train) // 10))
    cv = KFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)

    model_scores = []
    fitted_models = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, estimator in build_models().items():
            scores = cross_val_score(
                estimator,
                X_train,
                y_train,
                cv=cv,
                scoring="neg_root_mean_squared_error",
                n_jobs=1,
            )
            rmse_scores = -scores
            fitted = clone(estimator)
            fitted.fit(X_train, y_train)
            fitted_models[name] = fitted
            model_scores.append({
                "Mô hình": name,
                "CV RMSE trung bình": float(np.mean(rmse_scores)),
                "Độ lệch CV RMSE": float(np.std(rmse_scores, ddof=1)) if len(rmse_scores) > 1 else 0.0,
            })

    comparison = pd.DataFrame(model_scores).sort_values("CV RMSE trung bình", ascending=True)
    best_name = str(comparison.iloc[0]["Mô hình"])
    best_model = fitted_models[best_name]
    predictions = best_model.predict(X_test)
    metrics = {
        "R² (tập kiểm tra)": float(r2_score(y_test, predictions)),
        "MAE": float(mean_absolute_error(y_test, predictions)),
        "RMSE": float(math.sqrt(mean_squared_error(y_test, predictions))),
        "Số mẫu huấn luyện": int(len(X_train)),
        "Số mẫu kiểm tra": int(len(X_test)),
        "Số biến đầu vào": int(len(usable_features)),
        "Số fold CV": int(n_splits),
    }
    pred_df = pd.DataFrame({
        "Gia_tri_thuc_te": y_test.to_numpy(),
        "Gia_tri_du_doan": predictions,
        "Sai_so": y_test.to_numpy() - predictions,
    }, index=y_test.index).sort_index()
    return {
        "model": best_model,
        "model_name": best_name,
        "comparison": comparison.reset_index(drop=True),
        "metrics": metrics,
        "predictions": pred_df,
        "features": usable_features,
        "target": target,
        "n_rows": int(len(work)),
        "test_index": list(X_test.index),
    }


# ---------------- Sidebar: data source ----------------
st.sidebar.header("1. Nguồn dữ liệu")
uploaded = st.sidebar.file_uploader(
    "Tải dữ liệu Excel hoặc CSV",
    type=["xlsx", "xls", "csv"],
    help="Nếu không tải file mới, website sẽ dùng file dữ liệu mẫu đi kèm dự án.",
)

try:
    if uploaded is None:
        data, sheet_name, source_name = load_default_data()
        st.sidebar.success(f"Đang dùng dữ liệu mặc định: {source_name}")
    else:
        data, sheet_name = load_uploaded_file(uploaded)
        source_name = uploaded.name
        st.sidebar.success(f"Đã đọc: {source_name}")
except Exception as exc:
    st.error(f"Không thể đọc dữ liệu: {exc}")
    st.stop()

if data.empty:
    st.error("Sheet/file không có dữ liệu.")
    st.stop()

data = numeric_dataframe(data)
# Remove unnamed empty columns commonly produced by spreadsheets.
data = data.loc[:, ~data.columns.astype(str).str.match(r"^Unnamed")]

numeric_cols = [c for c in data.columns if pd.api.types.is_numeric_dtype(data[c]) and data[c].notna().any()]
data_fingerprint = f"{source_name}|{sheet_name}|{data.shape}|{tuple(data.columns)}|{int(pd.util.hash_pandas_object(data, index=True).sum())}"
if len(numeric_cols) < 2:
    st.error("Cần ít nhất hai cột dạng số: một cột đầu vào và một cột mục tiêu.")
    st.stop()

st.sidebar.header("2. Thiết lập bài toán")
def_target = "CT_Index" if "CT_Index" in numeric_cols else numeric_cols[-1]
target = st.sidebar.selectbox("Biến mục tiêu cần dự đoán", numeric_cols, index=numeric_cols.index(def_target))
default_features = [c for c in numeric_cols if c != target]
features = st.sidebar.multiselect(
    "Các biến đầu vào",
    [c for c in numeric_cols if c != target],
    default=default_features,
    help="Không chọn cột mục tiêu làm biến đầu vào để tránh rò rỉ dữ liệu.",
)
test_size_pct = st.sidebar.slider("Tỷ lệ tập kiểm tra (%)", min_value=10, max_value=35, value=20, step=5)
method = st.sidebar.selectbox(
    "Phương pháp thí nghiệm (ghi chú)",
    ["Chưa xác định", "IDEAL-CT", "SCB", "I-FIT", "DCT", "Phương pháp khác"],
    index=0,
    help="Chỉ là thông tin mô tả; không được suy ra chỉ từ tên cột CT_Index.",
)

# ---------------- Main overview ----------------
tab_overview, tab_quality, tab_model, tab_predict, tab_about = st.tabs([
    "📊 Tổng quan dữ liệu",
    "🧪 Kiểm tra dữ liệu",
    "🤖 Huấn luyện AI",
    "🎯 Dự đoán",
    "ℹ️ Hướng dẫn",
])

with tab_overview:
    st.subheader("Tổng quan bộ dữ liệu")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Số dòng", f"{len(data):,}")
    c2.metric("Số cột", f"{len(data.columns)}")
    c3.metric("Cột số", f"{len(numeric_cols)}")
    c4.metric("Nguồn", source_name[:24] + ("…" if len(source_name) > 24 else ""))

    with st.expander("Xem dữ liệu", expanded=True):
        st.dataframe(data, use_container_width=True, height=330)

    st.markdown("#### Thống kê mô tả")
    st.dataframe(data[numeric_cols].describe().T.rename(columns={
        "count": "Số lượng", "mean": "Trung bình", "std": "Độ lệch chuẩn",
        "min": "Nhỏ nhất", "25%": "Q1", "50%": "Trung vị", "75%": "Q3", "max": "Lớn nhất",
    }).round(3), use_container_width=True)

    if target in numeric_cols:
        left, right = st.columns(2)
        with left:
            fig = px.histogram(data, x=target, nbins=25, title=f"Phân bố {target}", marginal="box")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            corr_data = data[numeric_cols].corr(numeric_only=True)
            fig = px.imshow(corr_data, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r",
                            zmin=-1, zmax=1, title="Ma trận tương quan Pearson")
            st.plotly_chart(fig, use_container_width=True)

with tab_quality:
    st.subheader("Kiểm tra chất lượng dữ liệu")
    missing = data.isna().sum()
    duplicates = int(data.duplicated().sum())
    q1, q2, q3 = st.columns(3)
    q1.metric("Ô trống", f"{int(missing.sum())}")
    q2.metric("Dòng trùng lặp", f"{duplicates}")
    q3.metric("Dòng có mục tiêu", f"{int(data[target].notna().sum()) if target in data else 0}")

    if missing.sum() == 0:
        st.success("Không phát hiện ô trống trong bảng dữ liệu hiện tại.")
    else:
        st.warning("Có ô trống. Khi huấn luyện, giá trị thiếu ở biến đầu vào sẽ được điền bằng trung vị trong từng fold huấn luyện; dòng thiếu biến mục tiêu sẽ bị loại.")
        st.dataframe(missing.rename("Số ô trống").to_frame(), use_container_width=True)

    st.markdown("#### Kiểm tra quan hệ VFB – VMA – Air Voids")
    vfb_check = get_vfb_quality_check(data)
    if vfb_check is None:
        st.info("Không đủ ba cột VFB, VMA và Air_Voids để thực hiện kiểm tra công thức.")
    else:
        st.warning(
            "Đây là phép kiểm tra sàng lọc theo quan hệ thể tích thường dùng, không tự động kết luận dữ liệu sai. "
            "Cần xác minh định nghĩa, cách tính và nguồn đo của từng cột trước khi sửa dữ liệu."
        )
        a, b, c = st.columns(3)
        a.metric("Số mẫu kiểm tra", vfb_check["n"])
        b.metric("Chênh lệch tuyệt đối > 5 điểm %", f"{vfb_check['over_5']} / {vfb_check['n']}")
        c.metric("Sai khác tuyệt đối trung bình", f"{vfb_check['mean_abs_difference']:.2f} điểm %")
        compare = pd.DataFrame({
            "VFB trong file": vfb_check["observed"],
            "VFB tính theo (VMA - Va)/VMA": vfb_check["calculated"],
        })
        fig = px.scatter(compare, x="VFB tính theo (VMA - Va)/VMA", y="VFB trong file",
                         title="So sánh VFB ghi trong file và VFB tính theo quan hệ thể tích")
        fig.add_shape(type="line", x0=0, y0=0, x1=100, y1=100, line=dict(dash="dash"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Không chỉnh sửa hay loại mẫu tự động. Hãy đối chiếu với sổ thí nghiệm/tiêu chuẩn áp dụng.")

    st.markdown("#### Khoảng giá trị các biến")
    range_df = pd.DataFrame({
        "Cột": numeric_cols,
        "Nhỏ nhất": [data[c].min() for c in numeric_cols],
        "Lớn nhất": [data[c].max() for c in numeric_cols],
        "Trung bình": [data[c].mean() for c in numeric_cols],
        "Độ lệch chuẩn": [data[c].std() for c in numeric_cols],
    }).round(3)
    st.dataframe(range_df, use_container_width=True)

with tab_model:
    st.subheader("Huấn luyện và đánh giá mô hình hồi quy")
    st.write(f"**Biến mục tiêu:** `{target}`  |  **Biến đầu vào:** {', '.join(features) if features else 'Chưa chọn'}")
    st.write(f"**Phương pháp thí nghiệm được ghi chú:** {method}")
    st.caption("Các mô hình được so sánh bằng RMSE trung bình của cross-validation trên tập huấn luyện. Tập kiểm tra được giữ riêng để đánh giá mô hình được chọn.")

    if not features:
        st.warning("Vui lòng chọn ít nhất một biến đầu vào ở thanh bên trái.")
    elif target in features:
        st.error("Biến mục tiêu không được xuất hiện trong danh sách biến đầu vào.")
    else:
        if st.button("🚀 Huấn luyện và đánh giá mô hình", type="primary", use_container_width=True):
            try:
                with st.spinner("Đang huấn luyện và so sánh mô hình..."):
                    results = train_and_evaluate(data, features, target, test_size_pct / 100)
                    results["method"] = method
                    results["source"] = source_name
                    results["selected_features"] = list(features)
                    results["data_fingerprint"] = data_fingerprint
                    st.session_state["model_results"] = results
                st.success(f"Đã huấn luyện xong. Mô hình được chọn theo CV: {results['model_name']}.")
            except Exception as exc:
                st.error(f"Không thể huấn luyện: {exc}")

    results = st.session_state.get("model_results")
    if results is not None:
        if (results.get("target") != target
                or tuple(results.get("selected_features", [])) != tuple(features)
                or results.get("data_fingerprint") != data_fingerprint):
            st.warning("Dữ liệu hoặc thiết lập mục tiêu/biến đầu vào đã thay đổi. Hãy huấn luyện lại để cập nhật mô hình.")
        else:
            st.markdown("#### So sánh mô hình bằng cross-validation")
            st.dataframe(results["comparison"].round(4), use_container_width=True, hide_index=True)
            st.markdown(f"#### Kết quả tập kiểm tra — {results['model_name']}")
            m = results["metrics"]
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("R²", f"{m['R² (tập kiểm tra)']:.3f}")
            mc2.metric("MAE", f"{m['MAE']:.3f}")
            mc3.metric("RMSE", f"{m['RMSE']:.3f}")
            st.caption(f"Train: {m['Số mẫu huấn luyện']} mẫu | Test: {m['Số mẫu kiểm tra']} mẫu | CV: {m['Số fold CV']} folds")

            pred_df = results["predictions"]
            left, right = st.columns(2)
            with left:
                fig = px.scatter(pred_df, x="Gia_tri_thuc_te", y="Gia_tri_du_doan",
                                 title="Giá trị thực tế và dự đoán",
                                 labels={"Gia_tri_thuc_te": "Giá trị thực tế", "Gia_tri_du_doan": "Giá trị dự đoán"})
                lo = min(pred_df.min().min(), 0)
                hi = max(pred_df.max().max(), 1)
                fig.add_shape(type="line", x0=lo, y0=lo, x1=hi, y1=hi, line=dict(dash="dash"))
                st.plotly_chart(fig, use_container_width=True)
            with right:
                fig = px.scatter(pred_df, x="Gia_tri_du_doan", y="Sai_so", title="Sai số dự đoán",
                                 labels={"Gia_tri_du_doan": "Giá trị dự đoán", "Sai_so": "Thực tế − Dự đoán"})
                fig.add_hline(y=0, line_dash="dash")
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Bảng dự đoán trên tập kiểm tra")
            st.dataframe(pred_df.round(4), use_container_width=True)
            csv_bytes = pred_df.to_csv(index=True).encode("utf-8-sig")
            st.download_button("⬇️ Tải kết quả kiểm tra (CSV)", csv_bytes,
                               file_name="ket_qua_du_doan_test.csv", mime="text/csv")
            st.caption("R², MAE và RMSE chỉ phản ánh hiệu năng trên cách chia dữ liệu hiện tại; nên chạy lại với nhiều seed hoặc xác nhận chéo ngoài mẫu trước khi kết luận.")

with tab_predict:
    st.subheader("Dự đoán cho một mẫu bê tông nhựa mới")
    results = st.session_state.get("model_results")
    if results is None:
        st.info("Hãy sang tab **Huấn luyện AI** và huấn luyện mô hình trước khi dự đoán.")
    elif (results.get("target") != target
          or tuple(results.get("selected_features", [])) != tuple(features)
          or results.get("data_fingerprint") != data_fingerprint):
        st.warning("Dữ liệu hoặc thiết lập hiện tại khác với mô hình đã huấn luyện. Hãy huấn luyện lại trước khi dự đoán.")
    else:
        st.write(f"Mô hình đang sử dụng: **{results['model_name']}** | Biến mục tiêu: **{results['target']}**")
        st.caption("Giá trị khởi tạo là trung vị của bộ dữ liệu hiện tại. Hãy thay bằng thông số thí nghiệm của mẫu cần dự đoán.")
        defaults = data[results["features"]].median(numeric_only=True)
        input_values = {}
        cols = st.columns(2)
        with st.form("prediction_form"):
            for idx, feature in enumerate(results["features"]):
                with cols[idx % 2]:
                    default_value = float(defaults[feature]) if pd.notna(defaults[feature]) else 0.0
                    input_values[feature] = st.number_input(
                        feature,
                        value=default_value,
                        format="%.4f",
                        help=f"Khoảng dữ liệu quan sát: {data[feature].min():.3f} đến {data[feature].max():.3f}",
                    )
            submitted = st.form_submit_button("Dự đoán chỉ tiêu kháng nứt", type="primary", use_container_width=True)
        if submitted:
            new_sample = pd.DataFrame([input_values], columns=results["features"])
            prediction = float(results["model"].predict(new_sample)[0])
            st.success("Đã tạo dự đoán từ mô hình đã huấn luyện.")
            st.metric(f"Giá trị dự đoán — {results['target']}", f"{prediction:.3f}")
            in_range = all(
                data[f].min() <= input_values[f] <= data[f].max()
                for f in results["features"] if data[f].notna().any()
            )
            if not in_range:
                st.warning("Có ít nhất một thông số nằm ngoài khoảng dữ liệu huấn luyện. Đây là ngoại suy; kết quả có độ tin cậy thấp hơn và cần kiểm chứng bằng thí nghiệm.")
            else:
                st.info("Các thông số đầu vào nằm trong khoảng quan sát của bộ dữ liệu. Điều này không đảm bảo độ chính xác cho từng mẫu.")
            single = pd.DataFrame([{**input_values, f"Du_doan_{results['target']}": prediction}])
            st.download_button("⬇️ Tải kết quả mẫu này (CSV)", single.to_csv(index=False).encode("utf-8-sig"),
                               file_name="du_doan_mau_moi.csv", mime="text/csv")

with tab_about:
    st.subheader("Hướng dẫn sử dụng")
    st.markdown(
        """
        1. **Tải dữ liệu:** dùng file mẫu có sẵn hoặc tải Excel/CSV của bạn ở thanh bên trái.
        2. **Chọn biến mục tiêu:** mặc định là `CT_Index` nếu cột này có trong file.
        3. **Chọn biến đầu vào:** chọn các thông số cấp phối/thể tích có ý nghĩa kỹ thuật; không chọn cột mục tiêu.
        4. **Kiểm tra dữ liệu:** xem ô trống, dòng lặp, khoảng giá trị và cảnh báo VFB.
        5. **Huấn luyện:** chạy so sánh Ridge, Random Forest, Extra Trees, HistGradientBoosting và mô hình baseline.
        6. **Đánh giá:** đọc CV RMSE, R², MAE, RMSE và các biểu đồ sai số.
        7. **Dự đoán:** nhập thông số của mẫu mới trong tab Dự đoán.

        **Giải thích chỉ số:**
        - **R²:** mức độ giải thích biến thiên của kết quả; có thể âm khi mô hình dự đoán kém hơn dự đoán bằng trung bình.
        - **MAE:** sai số tuyệt đối trung bình, cùng đơn vị với biến mục tiêu.
        - **RMSE:** căn bậc hai của sai số bình phương trung bình, nhạy hơn với sai số lớn.
        - **CV RMSE:** RMSE trung bình qua các fold trên tập huấn luyện, dùng để chọn mô hình ban đầu.

        **Giới hạn:** đây là mô hình hồi quy thực nghiệm học từ dữ liệu cung cấp. Mô hình không chứng minh quan hệ nhân quả, không tự xác định được phương pháp thử, và không nên dùng để thay thế thí nghiệm hoặc tiêu chuẩn kỹ thuật.
        """
    )
    st.markdown("#### Thông tin cấu hình hiện tại")
    st.json({
        "data_source": source_name,
        "sheet": sheet_name,
        "target": target,
        "features": features,
        "test_size": test_size_pct / 100,
        "random_state": RANDOM_STATE,
        "test_method_note": method,
    })

st.sidebar.divider()
st.sidebar.caption("Đồ án Machine Learning – Bê tông nhựa chặt | Phiên bản 1.0")
