import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Product Economics", layout="centered")

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

    /* Зеленая кнопка Save из Stitch */
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
        transition: 0.3s;
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 186, 136, 0.4) !important;
    }
    
    /* Итоговая полоска COGS */
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
st.title("Product Economics")
st.caption("Price and profit calculation")

# --- 5. ВВОД ДАННЫХ (ИНТЕРФЕЙС) ---

# БЛОК 1: Прямые расходы
with st.container():
    st.markdown("### 1️⃣ Direct Costs (COGS)")
    
    default_materials = pd.DataFrame([
        {"Материал": "Глазурь (осн.)", "Цена (₽)": 18.58},
        {"Материал": "Глазурь (декор)", "Цена (₽)": 21.18},
        {"Материал": "Глина (масса 1)", "Цена (₽)": 58.28},
        {"Материал": "Глина (масса 2)", "Цена (₽)": 18.67},
    ])
    materials_df = st.data_editor(default_materials, num_rows="dynamic", hide_index=True, use_container_width=True)
    mat_cost_unit = materials_df["Цена (₽)"].sum()

    col_a, col_b, col_c = st.columns(3)
    labor_unit = col_a.number_input("Labor (₽)", value=150.0, step=10.0)
    firing_unit = col_b.number_input("Firing (₽)", value=20.0, step=5.0)
    pack_unit = col_c.number_input("Packaging (₽)", value=30.0, step=5.0)
    
    cogs_unit = mat_cost_unit + labor_unit + firing_unit + pack_unit
    st.markdown(f"<div class='total-cogs-box'>Total Direct COGS: {cogs_unit:.2f} ₽</div>", unsafe_allow_html=True)

# БЛОК 2: Партия
with st.container():
    st.markdown("### 2️⃣ Batch Parameters")
    b_col1, b_col2 = st.columns(2)
    batch_size = b_col1.number_input("Batch Size (units)", value=100, step=10)
    reject_rate = b_col2.slider("Defect Rate (%)", 0, 30, 5)
    
    sellable_units = int(batch_size * (1 - reject_rate / 100)) or 1
    marketing = st.number_input("Batch Marketing Costs (₽)", value=5000, step=500)

# БЛОК 3: Продажа
with st.container():
    st.markdown("### 3️⃣ Sale Price")
    sell_price = st.number_input("Retail Price per unit (₽)", value=1200, step=50)
    
    c1, c2 = st.columns(2)
    tax_pct = c1.slider("Tax (%)", 0.0, 20.0, 6.0)
    mp_pct = c2.slider("Marketplace Comm (%)", 0.0, 30.0, 20.0)

# --- 6. РАСЧЕТЫ ---
u_prod = (cogs_unit * batch_size) / sellable_units
u_mark = marketing / sellable_units
u_comm = sell_price * (mp_pct / 100)
u_tax = sell_price * (tax_pct / 100)

unit_full_cost = u_prod + u_mark + u_comm + u_tax
unit_profit = sell_price - unit_full_cost
total_profit = unit_profit * sellable_units
margin = (unit_profit / sell_price) * 100

# --- 7. РЕЗУЛЬТАТЫ (МЕТРИКИ И ГРАФИК) ---
st.markdown("---")
res_col1, res_col2 = st.columns([1.5, 1])

with res_col1:
    k1, k2 = st.columns(2)
    k1.metric("Total Profit (Batch)", f"{total_profit:,.0f} ₽")
    k2.metric("Margin", f"{margin:.1f}%")
    
    # График структуры цены
    categories = ["Prod", "Mktg", "Comm", "Tax", "Net"]
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
    st.metric("Profit per Unit", f"{unit_profit:,.2f} ₽")
    
    # КНОПКА СОХРАНЕНИЯ
    if st.button("💾 Save Calculation"):
        new_record = {
            "Time": pd.Timestamp.now().strftime("%H:%M:%S"),
            "Profit (Total)": f"{total_profit:,.0f} ₽",
            "Margin": f"{margin:.1f}%",
            "Unit Price": f"{sell_price} ₽"
        }
        st.session_state.history.insert(0, new_record)
        st.toast("Calculation saved to history!", icon="✅")

# --- 8. ТАБЛИЦА ИСТОРИИ ---
if st.session_state.history:
    st.markdown("### 📜 History")
    st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True, hide_index=True)

# Экспандер с деталями (как в старом коде)
with st.expander("Show Detailed Breakdown"):
    st.write(f"Sellable units: {sellable_units}")
    st.write(f"Full unit cost: {unit_full_cost:.2f} ₽")