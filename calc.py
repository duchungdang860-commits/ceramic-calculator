import streamlit as st
import pandas as pd

# Инициализируем хранилище в памяти, если его еще нет
if 'history' not in st.session_state:
    st.session_state.history = []

# Оформляем кнопку как в макете Stitch
st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: #00BA88;
        color: white;
        height: 3em;
        width: 100%;
        border-radius: 15px;
        border: none;
        font-weight: bold;
        box-shadow: 0 4px 15px rgba(0, 186, 136, 0.3);
    }
    </style>
""", unsafe_allow_html=True)

if st.button("📥 Save Calculation"):
    # Собираем данные текущего расчета в словарь
    new_record = {
        "Date": pd.Timestamp.now().strftime("%H:%M:%S"),
        "Profit": f"{total_profit:,.0f} ₽",
        "Margin": f"{margin:.1f}%",
        "Price": sell_price
    }
    # Добавляем в начало списка
    st.session_state.history.insert(0, new_record)
    st.success("Calculation saved to history!")

# Выводим историю расчетов (можно спрятать в expander)
if st.session_state.history:
    with st.expander("📜 History of calculations"):
        st.table(st.session_state.history)