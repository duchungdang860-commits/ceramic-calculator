import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Экономика продукта", layout="centered")

# --- 2. ИНИЦИАЛИЗАЦИЯ ИСТОРИИ (Session State) ---
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 3. КАСТОМНЫЙ CSS (ДИЗАЙН STITCH) ---
st.markdown("""
    <style>
    /* Фон и шрифты */
    .main { background-color: #F7F8FA; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; color: #1A1A1B; }
    
    /* Карточки метрик */
    [data-testid="stMetric"] {
        background-color: white;
        padding: 20px;
        border-radius: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        border: 1px solid #F0F0F0;
    }
    
    /* Белые карточки для блоков ввода */
    div[data-testid="stVerticalBlock"] > div.element-container:has(.stMarkdown) + div {
        background-color: white;
        padding: 25px;
        border-radius: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }

    /* Зеленая кнопка Сохранить (акцентная) */
    div.stButton > button {
        background-color: #00BA88 !important;
        color: white !important;
        height: 3.5em !important;
        width: 100% !important;
        border-radius: 15px !important;
        border: none !important;
        font-weight: bold !important;
        font-size: 1.1rem !important;
        box-shadow: 0 4px 15px rgba(0, 186, 136, 0.3) !important;
        margin-bottom: 20px;
    }
    
    .total-cogs-box {
        background-color: #F0F7FF;
        padding: 15px;
        border-radius: 12px;
        color: #007AFF;
        font-weight: 600;
        text-align: center;
        margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. ШАПКА ---
st.title("Экономика продукта")
st.caption("Расчет цены и прибыли проекта")

# --- 5. ЛОГИКА РАСЧЕТА (вынесена вверх для работы кнопки и метрик) ---
# Мы используем значения по умолчанию для первого запуска
def calculate_metrics(mat_df, labor, firing, pack, b_size, reject, mktg, price, tax, comm):
    mat_cost = mat_df["Цена (₽)"].sum()
    cogs_unit = mat_cost + labor + firing + pack
    
    sellable = int(b_size * (1 - reject / 100)) or 1
    
    # Юнит-экономика (учитываем брак: расходы на всю партию делим на годные изделия)
    u_prod = (cogs_unit * b_size) / sellable
    u_mark = mktg / sellable
    u_comm = price * (comm / 100)
    u_tax = price * (tax / 100)
    
    u_profit = price - (u_prod + u_mark + u_comm + u_tax)
    t_profit = u_profit * sellable
    margin_val = (u_profit / price * 100) if price > 0 else 0
    
    return cogs_unit, sellable, u_prod, u_mark, u_comm, u_tax, u_profit, t_profit, margin_val

# --- 6. ИНТЕРФЕЙС: ВВОД ДАННЫХ ---

# КНОПКА СОХРАНЕНИЯ ВВЕРХУ
col_save_btn, _ = st.columns([1, 1])
# Кнопка будет срабатывать в конце после сбора всех данных через форму или виджеты

# БЛОК 1: Прямые расходы
with st.container():
    st.markdown("### 1️⃣ Прямые расходы (COGS)")
    
    default_materials = pd.DataFrame([
        {"Материал": "Глазурь (осн.)", "Цена (₽)": 18.58},
        {"Материал": "Глазурь (декор)", "Цена (₽)": 21.18},
        {"Материал": "Глина (масса 1)", "Цена (₽)": 58.28},
        {"Материал": "Глина (масса 2)", "Цена (₽)": 18.67},
    ])
    materials_df = st.data_editor(default_materials, num_rows="dynamic", hide_index=True, use_container_width=True)

    col_a, col_b, col_c = st.columns(3)
    labor_unit = col_a.number_input("Работа (₽)", value=150.0, step=10.0)
    firing_unit = col_b.number_input("Обжиг (₽)", value=20.0, step=5.0)
    pack_unit = col_c.number_input("Упаковка (₽)", value=30.0, step=5.0)

# БЛОК 2: Параметры партии
with st.container():
    st.markdown("### 2️⃣ Параметры партии")
    b_col1, b_col2 = st.columns(2)
    batch_size = b_col1.number_input("Размер партии (шт)", value=100, step=10)
    reject_rate = b_col2.slider("Брак (%)", 0, 30, 5)
    marketing_total = st.number_input("Маркетинг и логистика на партию (₽)", value=5000, step=500)

# БЛОК 3: Продажа
with st.container():
    st.markdown("### 3️⃣ Цена и комиссии")
    sell_price = st.number_input("Розничная цена за 1 шт (₽)", value=1200, step=50)
    
    c1, c2 = st.columns(2)
    tax_pct = c1.slider("Налог (%)", 0.0, 20.0, 6.0)
    mp_pct = c2.slider("Комиссия площадки (%)", 0.0, 30.0, 20.0)

# --- ВЫПОЛНЕНИЕ РАСЧЕТОВ ---
cogs_u, sellable_u, u_prod, u_mark, u_comm, u_tax, unit_profit, total_profit, margin = calculate_metrics(
    materials_df, labor_unit, firing_unit, pack_unit, batch_size, reject_rate, marketing_total, sell_price, tax_pct, mp_pct
)

# РАЗМЕЩЕНИЕ КНОПКИ СОХРАНЕНИЯ (логически после расчетов)
with col_save_btn:
    if st.button("💾 Сохранить расчет"):
        st.session_state.history.insert(0, {
            "Время": pd.Timestamp.now().strftime("%H:%M:%S"),
            "Прибыль (Партия)": f"{total_profit:,.0f} ₽",
            "Рентабельность": f"{margin:.1f}%",
            "Цена": f"{sell_price} ₽"
        })
        st.toast("Расчет успешно сохранен!", icon="✅")

# --- 7. РЕЗУЛЬТАТЫ ---
st.markdown("---")
res_col1, res_col2 = st.columns([1.5, 1])

with res_col1:
    k1, k2 = st.columns(2)
    k1.metric("Прибыль (Партия)", f"{total_profit:,.0f} ₽")
    k2.metric("Рентабельность", f"{margin:.1f}%")
    
    # График
    categories = ["Произв.", "Марк.", "Коммис.", "Налог", "ЧИСТАЯ"]
    values = [u_prod, u_mark, u_comm, u_tax, max(0, unit_profit)]
    fig = go.Figure(go.Bar(
        x=categories, 
        y=values, 
        marker_color=['#D1D5DB','#D1D5DB','#D1D5DB','#D1D5DB','#00BA88'],
        text=[f"{v:.0f}" for v in values],
        textposition='auto'
    ))
    fig.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

with res_col2:
    st.metric("Прибыль с 1 шт", f"{unit_profit:,.2f} ₽")
    st.markdown(f"<div class='total-cogs-box'>Себестоимость (COGS):<br>{cogs_u:.2f} ₽</div>", unsafe_allow_html=True)

# --- 8. ДЕТАЛЬНАЯ СМЕТА (ОБНОВЛЕННАЯ) ---
st.markdown("### 📊 Детальная смета")
df_details = pd.DataFrame({
    "Статья расходов": ["Производство (с учетом брака)", "Маркетинг и логистика", "Комиссия площадки", "Налоги", "ЧИСТАЯ ПРИБЫЛЬ"],
    "На 1 шт. (₽)": [u_prod, u_mark, u_comm, u_tax, unit_profit],
    "На партию (₽)": [u_prod * sellable_u, u_mark * sellable_u, u_comm * sellable_u, u_tax * sellable_u, total_profit],
    "Доля в цене": [u_prod/sell_price, u_mark/sell_price, u_comm/sell_price, u_tax/sell_price, unit_profit/sell_price]
})

st.dataframe(
    df_details.style.format({
        "На 1 шт. (₽)": "{:,.2f}",
        "На партию (₽)": "{:,.0f}",
        "Доля в цене": "{:.1%}"
    }),
    use_container_width=True,
    hide_index=True
)

# --- 9. ИСТОРИЯ ---
if st.session_state.history:
    with st.expander("📜 История последних расчетов"):
        st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True, hide_index=True)