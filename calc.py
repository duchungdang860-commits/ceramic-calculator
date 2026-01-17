import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import base64
import os
import uuid
from io import BytesIO
from datetime import datetime

# Optional persistent storage (Supabase). The app keeps working without it.
try:
    from supabase import create_client  # type: ignore
except Exception:
    create_client = None  # type: ignore


def _now_iso_amsterdam() -> str:
    """ISO timestamp in Europe/Amsterdam (fallback: UTC)."""
    try:
        from zoneinfo import ZoneInfo  # py3.9+

        return datetime.now(ZoneInfo("Europe/Amsterdam")).replace(microsecond=0).isoformat()
    except Exception:
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@st.cache_resource
def _get_supabase_client():
    """Returns a Supabase client or None if not configured."""
    if create_client is None:
        return None
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None


def _pt_sans_path() -> str:
    # Put the font here to embed Cyrillic in PDF:
    # assets/fonts/PTSans-Regular.ttf
    return os.path.join("assets", "fonts", "PTSans-Regular.ttf")


def build_pdf_bytes(snapshot: dict) -> bytes:
    """Generate a simple one-page PDF with embedded PT Sans if available."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception as e:
        raise RuntimeError(
            "PDF generator is not available. Add 'reportlab' to requirements.txt"
        ) from e

    buf = BytesIO()
    # Уменьшаем поля (margins), чтобы всё влезло на одну страницу
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Unit-economics", 
                            topMargin=30, bottomMargin=30, leftMargin=40, rightMargin=40)
    styles = getSampleStyleSheet()

    font_name = "Helvetica"
    font_path = _pt_sans_path()
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("PTSans", font_path))
            font_name = "PTSans"
        except Exception:
            font_name = "Helvetica"

    # Настройка стилей шрифтов
    styles["Normal"].fontName = font_name
    styles["Title"].fontName = font_name
    
    # Кастомный стиль для заголовков секций
    styles.add(ParagraphStyle(name='SectionHeader', parent=styles['Normal'], fontSize=12, spaceAfter=6, fontName=font_name, leading=14))

    story = []
    
    # --- ЗАГОЛОВОК С РАЗМЕРОМ ПАРТИИ ---
    base_title = snapshot.get("title") or "Экономика продукта"
    # Получаем размер партии из inputs, если его нет - ставим 0
    batch_sz = snapshot.get("inputs", {}).get("batch_size", 0)
    
    # Формируем заголовок: "Название, X шт."
    full_title = f"{base_title}, {batch_sz} шт." if batch_sz else base_title

    story.append(Paragraph(full_title, styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Время сохранения: {snapshot.get('saved_at','')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # --- 1. KEY METRICS ---
    metrics = snapshot.get("metrics", {})
    sell_price = metrics.get("sell_price", 0)
    sellable_u = metrics.get("sellable_u", 0)

    data_main = [
        ["Цена за 1 шт, ₽", f"{sell_price}"],
        ["Прибыль с 1 шт, ₽", f"{metrics.get('unit_profit', 0):.2f}"],
        ["Прибыль партии, ₽", f"{metrics.get('total_profit', 0):.0f}"],
        ["Рентабельность, %", f"{metrics.get('margin', 0):.1f}"],
        ["Годных изделий, шт", f"{sellable_u}"],
    ]

    # Ширина колонок увеличена до суммы 420 (250+170), чтобы совпасть со второй таблицей
    tbl_main = Table(data_main, colWidths=[250, 170], hAlign='LEFT')
    tbl_main.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke), # Первый столбец серый
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(Paragraph("<b>Ключевые показатели</b>", styles["SectionHeader"]))
    story.append(tbl_main)
    story.append(Spacer(1, 12))

    # --- 2. DETAILED BREAKDOWN (NEW SECTION) ---
    # Извлекаем детальные метрики
    u_prod = metrics.get("u_prod", 0)
    u_mark = metrics.get("u_mark", 0)
    u_comm = metrics.get("u_comm", 0)
    u_tax  = metrics.get("u_tax", 0)
    u_prof = metrics.get("unit_profit", 0)
    
    # Выручка партии (Сумма продажи) = Цена * Годные изделия
    total_revenue = sell_price * sellable_u
    
    # Вспомогательная функция для %
    def get_pct(val, total):
        return f"{(val / total * 100):.1f}%" if total > 0 else "0%"

    story.append(Paragraph("<b>Детальная структура цены (Смета)</b>", styles["SectionHeader"]))
    
    # Формируем таблицу. Первая строка данных - СУММА ПРОДАЖИ
    data_details = [
        ["Статья расходов / Доходов", "На 1 шт (₽)", "На партию (₽)", "Доля"],
        # Строка Выручки
        ["Сумма продажи (Выручка)", f"{sell_price:.2f}", f"{total_revenue:.0f}", "100%"],
        # Расходы
        ["Производство (с уч. брака)", f"{u_prod:.2f}", f"{u_prod * sellable_u:.0f}", get_pct(u_prod, sell_price)],
        ["Маркетинг и логистика", f"{u_mark:.2f}", f"{u_mark * sellable_u:.0f}", get_pct(u_mark, sell_price)],
        ["Комиссия площадки", f"{u_comm:.2f}", f"{u_comm * sellable_u:.0f}", get_pct(u_comm, sell_price)],
        ["Налоги", f"{u_tax:.2f}", f"{u_tax * sellable_u:.0f}", get_pct(u_tax, sell_price)],
        ["ЧИСТАЯ ПРИБЫЛЬ", f"{u_prof:.2f}", f"{metrics.get('total_profit', 0):.0f}", get_pct(u_prof, sell_price)],
    ]

    # Ширина второй таблицы: 180+80+100+60 = 420
    tbl_details = Table(data_details, colWidths=[180, 80, 100, 60], hAlign='LEFT')
    tbl_details.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),      # Заголовок
                ("BACKGROUND", (0, 1), (-1, 1), colors.whitesmoke),     # Строка Выручки (светлая)
                ("FONTNAME", (0, 1), (-1, 1), font_name),               # Выручка обычным шрифтом
                ("BACKGROUND", (0, -1), (-1, -1), "#E6F4EA"),          # Строка прибыли (зеленоватая)
                ("PADDING", (0, 0), (-1, -1), 5),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),                   # Выравнивание цифр вправо
            ]
        )
    )
    story.append(tbl_details)
    story.append(Spacer(1, 12))

    # --- 3. MATERIALS ---
    mats = snapshot.get("materials", [])
    if mats:
        story.append(Paragraph("<b>Материалы (входят в производство)</b>", styles["SectionHeader"]))
        mats_rows = [["Материал", "Цена (₽)"]] + [[m.get("Материал", ""), str(m.get("Цена (₽)", ""))] for m in mats]
        
        # Ширина колонок увеличена до суммы 420 (300+120), чтобы совпасть со второй таблицей
        mats_tbl = Table(mats_rows, colWidths=[300, 120], hAlign='LEFT')
        mats_tbl.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(mats_tbl)

    doc.build(story)
    return buf.getvalue()


def _save_to_supabase(snapshot: dict, pdf_bytes: bytes) -> str | None:
    """Returns inserted row id or None (if Supabase not configured)."""
    sb = _get_supabase_client()
    if sb is None:
        return None
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    row = {
        "title": snapshot.get("title") or "",
        "snapshot": snapshot,
        "pdf_base64": pdf_b64,
    }
    resp = sb.table("calculations").insert(row).execute()
    try:
        return resp.data[0]["id"]
    except Exception:
        return None


def _fetch_history(limit: int = 50) -> list[dict]:
    sb = _get_supabase_client()
    if sb is None:
        return []
    resp = (
        sb.table("calculations")
        .select("id, created_at, title, snapshot")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def _fetch_pdf(calc_id: str) -> bytes | None:
    sb = _get_supabase_client()
    if sb is None:
        return None
    resp = sb.table("calculations").select("pdf_base64").eq("id", calc_id).single().execute()
    try:
        b64 = resp.data["pdf_base64"]
        return base64.b64decode(b64.encode("utf-8"))
    except Exception:
        return None

# --- 0. CALLBACK-ФУНКЦИЯ ДЛЯ ЗАГРУЗКИ ---
def load_calculation(snapshot_data):
    """Loads snapshot data into session state widgets."""
    inputs = snapshot_data.get("inputs", {})
    mats = snapshot_data.get("materials", [])
    
    st.session_state.calc_title = snapshot_data.get("title", "")
    st.session_state.labor_unit = float(inputs.get("labor_unit", st.session_state.labor_unit))
    st.session_state.firing_unit = float(inputs.get("firing_unit", st.session_state.firing_unit))
    st.session_state.pack_unit = float(inputs.get("pack_unit", st.session_state.pack_unit))
    st.session_state.batch_size = int(inputs.get("batch_size", st.session_state.batch_size))
    st.session_state.reject_rate = int(inputs.get("reject_rate", st.session_state.reject_rate))
    st.session_state.marketing_total = float(inputs.get("marketing_total", st.session_state.marketing_total))
    st.session_state.sell_price = float(inputs.get("sell_price", st.session_state.sell_price))
    st.session_state.tax_pct = int(inputs.get("tax_pct", st.session_state.tax_pct))
    st.session_state.mp_pct = int(inputs.get("mp_pct", st.session_state.mp_pct))
    
    if mats:
        st.session_state.materials_df = pd.DataFrame(mats)
        # Сбрасываем кэш виджета редактора
        if "materials_editor" in st.session_state:
            del st.session_state["materials_editor"]
            
    st.toast("Данные загружены из истории!", icon="✅")


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

    /* Зеленая кнопка (акцентная).
       Применяем и к stButton (обычные), и к stDownloadButton (скачивание),
       чтобы они были идентичны.
    */
    div.stButton > button, div.stDownloadButton > button {
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


# --- 4.1 ИНИЦИАЛИЗАЦИЯ ДЕФОЛТОВ ДЛЯ ВИДЖЕТОВ (нужно для загрузки из истории) ---
if "materials_df" not in st.session_state:
    st.session_state.materials_df = pd.DataFrame(
        [
            {"Материал": "Глазурь (осн.)", "Цена (₽)": 18.58},
            {"Материал": "Глазурь (декор)", "Цена (₽)": 21.18},
            {"Материал": "Глина (масса 1)", "Цена (₽)": 58.28},
            {"Материал": "Глина (масса 2)", "Цена (₽)": 18.67},
        ]
    )

st.session_state.setdefault("labor_unit", 150.0)
st.session_state.setdefault("firing_unit", 20.0)
st.session_state.setdefault("pack_unit", 30.0)
st.session_state.setdefault("batch_size", 100)
st.session_state.setdefault("reject_rate", 5)
st.session_state.setdefault("marketing_total", 5000)
st.session_state.setdefault("sell_price", 1200)
st.session_state.setdefault("tax_pct", 6)
st.session_state.setdefault("mp_pct", 20)
st.session_state.setdefault("calc_title", "")

# --- 5. ЛОГИКА РАСЧЕТА (вынесена вверх для работы кнопки и метрик) ---
# Мы используем значения по умолчанию для первого запуска
def calculate_metrics(mat_df, labor, firing, pack, b_size, reject, mktg, price, tax, comm):
    mat_cost = mat_df["Цена (₽)"].sum()
    cogs_unit = mat_cost + labor + firing + pack
    
    sellable = int(b_size * (1 - reject / 100)) or 1
    
    # Юнит-экономика (учитываем брак: расходы на всю партию делим на годные изделия)
    u_prod = (cogs_unit * b_size) / sellable
    u_mark = mktg / sellable
    u_comm = price * (comm / 100.0)
    u_tax = price * (tax / 100.0)
    
    u_profit = price - (u_prod + u_mark + u_comm + u_tax)
    t_profit = u_profit * sellable
    margin_val = (u_profit / price * 100) if price > 0 else 0
    
    return cogs_unit, sellable, u_prod, u_mark, u_comm, u_tax, u_profit, t_profit, margin_val

# --- 6. ИНТЕРФЕЙС: ВВОД ДАННЫХ ---

# КНОПКА СОХРАНЕНИЯ ВВЕРХУ
col_title, col_save_btn = st.columns([2, 1])

with col_title:
    st.text_input(
        "Название расчёта (необязательно)",
        key="calc_title",
        placeholder="Напр. Кружка 350 мл, серия 01",
    )
# Кнопка будет срабатывать в конце после сбора всех данных через форму или виджеты

# БЛОК 1: Прямые расходы
with st.container():
    st.markdown("### 1️⃣ Прямые расходы (COGS)")

    materials_df = st.data_editor(
        st.session_state.materials_df,
        key="materials_editor",
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
    )
    # keep latest edits available for saving/loading
    st.session_state.materials_df = materials_df

    col_a, col_b, col_c = st.columns(3)
    labor_unit = col_a.number_input("Работа (₽)", key="labor_unit", value=float(st.session_state.labor_unit), step=10.0)
    firing_unit = col_b.number_input("Обжиг (₽)", key="firing_unit", value=float(st.session_state.firing_unit), step=5.0)
    pack_unit = col_c.number_input("Упаковка (₽)", key="pack_unit", value=float(st.session_state.pack_unit), step=5.0)

# БЛОК 2: Параметры партии
with st.container():
    st.markdown("### 2️⃣ Параметры партии")
    b_col1, b_col2 = st.columns(2)
    batch_size = b_col1.number_input("Размер партии (шт)", key="batch_size", value=int(st.session_state.batch_size), step=10)
    reject_rate = b_col2.slider("Брак (%)", 0, 30, int(st.session_state.reject_rate), key="reject_rate")
    marketing_total = st.number_input(
        "Маркетинг и логистика на партию (₽)",
        key="marketing_total",
        value=int(st.session_state.marketing_total),
        step=500,
    )

# БЛОК 3: Продажа
with st.container():
    st.markdown("### 3️⃣ Цена и комиссии")
    sell_price = st.number_input("Розничная цена за 1 шт (₽)", key="sell_price", value=int(st.session_state.sell_price), step=50)
    
    # Слайдеры теперь int
    c1, c2 = st.columns(2)
    tax_pct = c1.slider("Налог (%)", 0, 20, int(st.session_state.tax_pct), key="tax_pct")
    mp_pct = c2.slider("Комиссия площадки (%)", 0, 30, int(st.session_state.mp_pct), key="mp_pct")

# --- ВЫПОЛНЕНИЕ РАСЧЕТОВ ---
cogs_u, sellable_u, u_prod, u_mark, u_comm, u_tax, unit_profit, total_profit, margin = calculate_metrics(
    materials_df, labor_unit, firing_unit, pack_unit, batch_size, reject_rate, marketing_total, sell_price, tax_pct, mp_pct
)

# РАЗМЕЩЕНИЕ КНОПКИ СОХРАНЕНИЯ (логически после расчетов)
with col_save_btn:
    if st.button("💾 Сохранить расчет"):
        snapshot = {
            "schema": 1,
            "saved_at": _now_iso_amsterdam(),
            "title": st.session_state.get("calc_title", ""),
            "inputs": {
                "labor_unit": float(labor_unit),
                "firing_unit": float(firing_unit),
                "pack_unit": float(pack_unit),
                "batch_size": int(batch_size),
                "reject_rate": int(reject_rate),
                "marketing_total": float(marketing_total),
                "sell_price": float(sell_price),
                "tax_pct": int(tax_pct),
                "mp_pct": int(mp_pct),
            },
            "materials": materials_df.to_dict("records"),
            "metrics": {
                "sell_price": float(sell_price),
                "cogs_u": float(cogs_u),
                "sellable_u": int(sellable_u),
                "unit_profit": float(unit_profit),
                "total_profit": float(total_profit),
                "margin": float(margin),
                "u_prod": float(u_prod),
                "u_mark": float(u_mark),
                "u_comm": float(u_comm),
                "u_tax": float(u_tax),
            },
        }

        # PDF (always generated)
        try:
            pdf_bytes = build_pdf_bytes(snapshot)
            st.session_state.last_pdf = (str(uuid.uuid4()), pdf_bytes)
        except Exception as e:
            st.session_state.last_pdf = None
            st.error(f"Не удалось сформировать PDF: {e}")
            pdf_bytes = None

        # Persist to Supabase if configured
        saved_id = None
        if pdf_bytes is not None:
            saved_id = _save_to_supabase(snapshot, pdf_bytes)

        # Local (session) history fallback
        st.session_state.history.insert(
            0,
            {
                "Время": pd.Timestamp.now().strftime("%H:%M:%S"),
                "Прибыль (Партия)": f"{total_profit:,.0f} ₽",
                "Рентабельность": f"{margin:.1f}%",
                "Цена": f"{sell_price} ₽",
            },
        )

        if saved_id:
            st.toast("Расчет сохранён в историю и PDF записан.", icon="✅")
        else:
            st.toast(
                "PDF сформирован. Для постоянной истории подключи Supabase через secrets.",
                icon="ℹ️",
            )


# Persistent download button (keeps showing until next save)
if st.session_state.get("last_pdf"):
    calc_id, pdf_data = st.session_state.last_pdf
    st.download_button(
        "⬇️ Скачать PDF последнего расчёта",
        data=pdf_data,
        file_name=f"calc_{calc_id}.pdf",
        mime="application/pdf",
    )

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

# Расчет общей выручки для таблицы
total_revenue_calc = sell_price * sellable_u

df_details = pd.DataFrame({
    "Статья расходов / Доходов": [
        "Сумма продажи (Выручка)", 
        "Производство (с учетом брака)", 
        "Маркетинг и логистика", 
        "Комиссия площадки", 
        "Налоги", 
        "ЧИСТАЯ ПРИБЫЛЬ"
    ],
    "На 1 шт. (₽)": [
        sell_price, 
        u_prod, 
        u_mark, 
        u_comm, 
        u_tax, 
        unit_profit
    ],
    "На партию (₽)": [
        total_revenue_calc, 
        u_prod * sellable_u, 
        u_mark * sellable_u, 
        u_comm * sellable_u, 
        u_tax * sellable_u, 
        total_profit
    ],
    "Доля в цене": [
        1.0, 
        u_prod/sell_price if sell_price else 0, 
        u_mark/sell_price if sell_price else 0, 
        u_comm/sell_price if sell_price else 0, 
        u_tax/sell_price if sell_price else 0, 
        unit_profit/sell_price if sell_price else 0
    ]
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
sb_enabled = _get_supabase_client() is not None

with st.expander("📜 История расчетов"):
    if sb_enabled:
        history_rows = _fetch_history(limit=50)
        if not history_rows:
            st.info("История пока пустая. Нажми «Сохранить расчет», чтобы добавить запись.")
        else:
            dfh = pd.DataFrame(
                [
                    {
                        "created_at": r.get("created_at"),
                        "title": r.get("title") or "",
                        "price": r.get("snapshot", {}).get("metrics", {}).get("sell_price"),
                        "profit_total": r.get("snapshot", {}).get("metrics", {}).get("total_profit"),
                        "margin": r.get("snapshot", {}).get("metrics", {}).get("margin"),
                        "id": r.get("id"),
                        "_snapshot": r.get("snapshot"),
                    }
                    for r in history_rows
                ]
            )

            st.dataframe(
                dfh[["created_at", "title", "price", "profit_total", "margin"]].rename(
                    columns={
                        "created_at": "Время",
                        "title": "Название",
                        "price": "Цена, ₽",
                        "profit_total": "Прибыль партии, ₽",
                        "margin": "Рентабельность, %",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            def _format_label(_id: str) -> str:
                row = dfh.loc[dfh["id"] == _id].iloc[0]
                created = str(row.get("created_at") or "")
                title = str(row.get("title") or "").strip()
                return created + (f"  ·  {title}" if title else "")

            picked = st.selectbox(
                "Выбери сохранённый расчёт",
                options=dfh["id"].tolist(),
                format_func=_format_label,
            )

            if picked:
                # ИЗМЕНЕНИЕ: Используем use_container_width=True для обеих кнопок
                c1, c2 = st.columns(2)
                with c1:
                    pdf_bytes = _fetch_pdf(picked)
                    if pdf_bytes:
                        st.download_button(
                            "⬇️ Скачать PDF",
                            data=pdf_bytes,
                            file_name=f"calc_{picked}.pdf",
                            mime="application/pdf",
                            use_container_width=True  # Растягиваем на всю ширину
                        )
                    else:
                        st.info("PDF не найден")
                with c2:
                    snap = dfh.loc[dfh["id"] == picked, "_snapshot"].iloc[0] or {}
                    st.button("↩️ Загрузить в форму", 
                              key=f"load_{picked}", 
                              on_click=load_calculation, 
                              args=(snap,),
                              use_container_width=True  # Растягиваем на всю ширину
                    )
    else:
        if st.session_state.history:
            st.caption("Сейчас история хранится только в текущей сессии. Чтобы история сохранялась навсегда — подключи Supabase через secrets.")
            st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True, hide_index=True)
        else:
            st.info("История пока пустая. Нажми «Сохранить расчет», чтобы добавить запись.")
