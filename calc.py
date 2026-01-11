import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Unit Economics", layout="wide")

st.title("Экономика продукта: Расчет цены и прибыли")
st.markdown("---")

# --- ЛЕВАЯ КОЛОНКА: ВВОД ДАННЫХ ---
col_input, col_result = st.columns([1, 1.5], gap="medium")

with col_input:
    st.subheader("1. Прямые расходы (COGS)")
    
    # 1.1 МАТЕРИАЛЫ
    st.caption("Материалы на единицу")
    default_materials = pd.DataFrame([
        {"Материал": "Глазурь (осн.)", "Цена (₽)": 18.58},
        {"Материал": "Глазурь (декор)", "Цена (₽)": 21.18},
        {"Материал": "Глина (масса 1)", "Цена (₽)": 58.28},
        {"Материал": "Глина (масса 2)", "Цена (₽)": 18.67},
    ])
    materials_df = st.data_editor(default_materials, num_rows="dynamic", hide_index=True, use_container_width=True)
    mat_cost_unit = materials_df["Цена (₽)"].sum()

    # 1.2 ОПЕРАЦИИ
    st.caption("Работа и производство (на ед.)")
    labor_unit = st.number_input("ФОТ (сдельно)", value=150.0, step=50.0)
    firing_unit = st.number_input("Обжиг (печь)", value=20.0, step=5.0)
    pack_unit = st.number_input("Упаковка", value=30.0, step=5.0)

    # ИТОГО COGS
    cogs_unit = mat_cost_unit + labor_unit + firing_unit + pack_unit
    st.info(f"Прямая с/с (COGS): **{cogs_unit:.2f} ₽**")

    st.markdown("---")
    st.subheader("2. Параметры партии")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        batch_size = st.number_input("Партия (шт)", value=100, step=10)
    with col_p2:
        reject_rate = st.slider("Брак (%)", 0, 30, 5)
    
    sellable_units = int(batch_size * (1 - reject_rate / 100))
    if sellable_units == 0: sellable_units = 1
    
    fixed_batch_marketing = st.number_input("Расходы на партию (Маркетинг/Логистика)", value=0.0, step=500.0)

    st.markdown("---")
    st.subheader("3. Продажа")
    
    sell_price = st.number_input("Розничная цена (₽)", value=1200, step=50)
    
    c1, c2 = st.columns(2)
    with c1:
        mp_pct = st.number_input("Комиссия МП (%)", value=20.0, step=1.0)
    with c2:
        tax_pct = st.number_input("Налог (%)", value=6.0, step=0.5)

# --- ПРАВАЯ КОЛОНКА: РЕЗУЛЬТАТЫ ---
with col_result:
    st.subheader("Финансовый результат")

    # --- РАСЧЕТЫ (ЮНИТ) ---
    # 1. Производство (размазываем брак на выжившие изделия)
    # Формула: (Стоимость создания всей партии) / (Количество проданных)
    # Это честная себестоимость проданной единицы.
    u_prod = (cogs_unit * batch_size) / sellable_units
    
    # 2. Накладные (Маркетинг на единицу)
    u_mark = fixed_batch_marketing / sellable_units
    
    # 3. Комиссии и Налоги (с одной продажи)
    u_comm = sell_price * (mp_pct / 100)
    u_tax = sell_price * (tax_pct / 100)
    
    # 4. Итоги на единицу
    unit_full_cost = u_prod + u_mark + u_comm + u_tax
    unit_profit = sell_price - unit_full_cost
    unit_margin = (unit_profit / sell_price * 100)

    # --- РАСЧЕТЫ (ПАРТИЯ) ---
    # Реальные деньги, которые пройдут через счета
    total_revenue = sell_price * sellable_units             # Сколько всего получим денег
    b_prod_cost = cogs_unit * batch_size                    # Потратили на производство (даже брака)
    b_mark_cost = fixed_batch_marketing                     # Потратили на рекламу
    b_comm_cost = total_revenue * (mp_pct / 100)            # Отдали площадке
    b_tax_cost = total_revenue * (tax_pct / 100)            # Отдали налоговой
    
    total_profit = unit_profit * sellable_units             # Итого в карман

    # --- KPI КАРТОЧКИ ---
    k1, k2, k3 = st.columns(3)
    k1.metric("Прибыль (Партия)", f"{total_profit:,.0f} ₽", delta="Чистыми")
    k2.metric("Прибыль с 1 шт.", f"{unit_profit:.0f} ₽")
    k3.metric("Рентабельность", f"{unit_margin:.1f} %")

    st.markdown("---")

    # --- ДИАГРАММА (BAR CHART) ---
    st.write("##### Из чего состоит цена (Структура)")

    categories = ["Производство", "Маркетинг", "Комиссия МП", "Налог", "ЧИСТАЯ ПРИБЫЛЬ"]
    values = [u_prod, u_mark, u_comm, u_tax, unit_profit]
    
    bar_colors = ['#95A5A6', '#95A5A6', '#95A5A6', '#95A5A6', '#2ECC71']

    fig = go.Figure(go.Bar(
        x=categories,
        y=values,
        marker_color=bar_colors,
        text=[f"{v:.0f}" for v in values],
        textposition='auto',
    ))

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title=None,
        yaxis_title="Рубли (₽)",
        showlegend=False,
        height=400,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    
    fig.add_hline(y=sell_price, line_dash="dot", annotation_text=f"Цена продажи: {sell_price} ₽", annotation_position="top right")

    st.plotly_chart(fig, use_container_width=True)

    # --- ТАБЛИЦА (ОБНОВЛЕННАЯ С ДВУМЯ СТОЛБЦАМИ) ---
    with st.expander("Открыть детальную смету", expanded=True):
        
        # Собираем DataFrame с двумя колонками сумм
        df_details = pd.DataFrame({
            "Статья расходов": [
                "1. Производство (Мат + Труд + Брак)", 
                "2. Маркетинг и логистика", 
                "3. Комиссия площадки", 
                "4. Налоги", 
                "5. ЧИСТАЯ ПРИБЫЛЬ"
            ],
            "На всю партию (₽)": [  # Колонка 1: Общие суммы
                b_prod_cost,
                b_mark_cost,
                b_comm_cost,
                b_tax_cost,
                total_profit
            ],
            "На 1 шт. (₽)": [       # Колонка 2: Юнит-экономика
                u_prod,
                u_mark,
                u_comm,
                u_tax,
                unit_profit
            ],
            "Доля в цене": [
                u_prod/sell_price,
                u_mark/sell_price,
                u_comm/sell_price,
                u_tax/sell_price,
                unit_profit/sell_price
            ]
        })

        # Применяем форматирование ко всем колонкам
        st.dataframe(
            df_details.style.format({
                "На всю партию (₽)": "{:,.0f}", # Партию округляем до целых (без копеек) для чистоты
                "На 1 шт. (₽)": "{:,.2f}",      # Единицу с копейками
                "Доля в цене": "{:.1%}"
            }),
            use_container_width=True
        )