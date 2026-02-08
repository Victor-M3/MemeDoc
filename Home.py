import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime

# ==================== 页面配置 ====================
st.set_page_config(page_title="MeMeDoc MVP", layout="wide", page_icon="🧠")

# ==================== Session State 初始化 ====================
defaults = {
    "ca": "",
    "token_data": None,
    "price_df_short": None,
    "price_df_long": None,
    "x": 50,
    "y": 50,
    "z": 50,
    "position": 10,
    "notes": "",
    "diagnosed": False,
    "last_fetch_time": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ==================== 数据获取 ====================
@st.cache_data(ttl=90, show_spinner=False)
def fetch_token_info(ca: str):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{ca.strip()}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "pairs" not in data or not data["pairs"]:
            return None
        # 按流动性排序，取最大的 pair（通常最活跃的）
        pairs = sorted(data["pairs"], key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)
        return pairs[0]
    except Exception as e:
        st.error(f"获取代币信息失败：{str(e)}")
        return None


# ==================== 更有 meme 风格的模拟价格序列 ====================
@st.cache_data(ttl=300)
def generate_meme_price_series(periods=50, initial_price=0.00042):
    np.random.seed(int(datetime.now().timestamp()) % 10000)  # 每次运行稍有不同
    prices = [initial_price]
    pump_prob = 0.08
    dump_prob = 0.12

    for _ in range(periods - 1):
        r = np.random.random()
        if r < pump_prob:
            change = np.random.uniform(0.4, 2.2)  # 大泵
        elif r < pump_prob + dump_prob:
            change = np.random.uniform(-0.65, -0.15)  # 大砸
        else:
            change = np.random.uniform(-0.12, 0.15)  # 正常抖动

        next_price = prices[-1] * (1 + change)
        prices.append(max(1e-9, next_price))  # 防止负数或0

    df = pd.DataFrame({"price": prices})
    df["time"] = pd.date_range(
        end=datetime.now(),
        periods=len(df),
        freq="2min" if periods <= 60 else "15min"
    )
    return df


# ==================== 核心风险评估逻辑 ====================
def calculate_risk_score(x, y, z, position_pct):
    x_norm = x / 100
    y_norm = y / 100
    z_norm = z / 100
    p_norm = position_pct / 100

    # 风险构成权重（可自行调整）
    risk = (
            y_norm * 0.35  # 情绪放大（FOMO/FUD）权重最高
            + z_norm * 0.28  # 当前价格位置（是否高位）
            + p_norm * 0.22  # 个人仓位占比
            + (1 - x_norm) * 0.15  # 叙事强度越弱越危险
    )
    return min(0.99, max(0.01, risk))


def risk_label_and_message(score):
    if score < 0.38:
        return "猎手 🦈", "你可能走在前面，但别太自信", "success"
    elif score < 0.68:
        return "观望 🧘", "现在不是很明确，等等别人先动", "warning"
    else:
        return "猎物 🐑", "情绪过热 + 仓位偏重，极易成为接盘侠", "error"


# ==================== 主界面 ====================
st.title("🧠 MeMeDoc MVP - Meme 情绪诊断小工具")
st.caption("仅供娱乐・不构成任何投资建议")

# ------------------- 输入区 + 刷新按钮 -------------------
col_ca, col_btn = st.columns([5, 1])
with col_ca:
    ca_input = st.text_input(
        "Solana 代币合约地址 (CA)",
        value=st.session_state.ca,
        placeholder="例: DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        help="目前仅支持 DexScreener 可查询的代币"
    )

with col_btn:
    st.write("")  # 占位对齐
    st.write("")
    if st.button("查询 / 刷新", type="primary", use_container_width=True):
        if ca_input.strip():
            with st.spinner("正在拉取最新信息..."):
                st.session_state.ca = ca_input.strip()
                st.session_state.token_data = fetch_token_info(ca_input)
                st.session_state.price_df_short = generate_meme_price_series(45)
                st.session_state.price_df_long = generate_meme_price_series(90)
                st.session_state.last_fetch_time = datetime.now()
                st.session_state.diagnosed = False
        else:
            st.warning("请输入合约地址")

if st.session_state.last_fetch_time:
    st.caption(f"最后更新：{st.session_state.last_fetch_time.strftime('%Y-%m-%d %H:%M:%S')}")

# ------------------- 代币基本信息 -------------------
if st.session_state.token_data:
    t = st.session_state.token_data

    st.subheader(f"{t['baseToken']['name']}  ({t['baseToken']['symbol']})")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("当前价格", f"${float(t.get('priceUsd', '—')):,.8f}")
    col2.metric("24h 涨跌幅", f"{t.get('priceChange', {}).get('h24', '—')}%")
    col3.metric("流动性", f"${int(t.get('liquidity', {}).get('usd', 0)):,}")
    col4.metric("24h 成交量", f"${int(t.get('volume', {}).get('h24', 0)):,}")

    age_min = (datetime.now() - datetime.fromtimestamp(t['pairCreatedAt'] / 1000)).total_seconds() / 60
    st.caption(
        f"交易对创建于：{datetime.fromtimestamp(t['pairCreatedAt'] / 1000).strftime('%Y-%m-%d %H:%M')}  　年龄约 {int(age_min // 60)}小时 {int(age_min % 60)}分钟")

# ------------------- 价格模拟图 -------------------
if st.session_state.price_df_short is not None:
    st.subheader("模拟价格走势（meme 风格随机生成,并非真实走向，你可以去大交易所看嘛）")

    tab1, tab2 = st.tabs(["近 1–2 小时", "更长周期"])

    with tab1:
        fig1 = px.line(st.session_state.price_df_short, x="time", y="price",
                       title="短周期（更剧烈波动）")
        fig1.update_layout(showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        fig2 = px.line(st.session_state.price_df_long, x="time", y="price",
                       title="较长周期")
        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

# ------------------- 情绪评估滑块 -------------------
st.subheader("你的主观情绪评估（XYZ）")

# ────────────────────────────────────────────────
# 颜色渐变辅助函数（0→100：绿 → 黄 → 红）
# ────────────────────────────────────────────────
def get_color_gradient(value):
    # value 0~100 → rgb 从 (0,200,0) → (255,200,0) → (200,0,0)
    if value <= 50:
        r = int(255 * (value / 50))
        g = 200
        b = 0
    else:
        r = 255
        g = int(200 * (1 - (value - 50) / 50))
        b = 0
    return f"#{r:02x}{g:02x}{b:02x}"

# ────────────────────────────────────────────────
# X 轴 - 叙事强度
# ────────────────────────────────────────────────
def get_x_desc(val):
    if val <= 20: return "几乎无共识"
    if val <= 40: return "有一定共识"
    if val <= 60: return "共识较强，地区型热点"
    if val <= 80: return "强赛道级热点"
    return "全球型顶级热点"

st.markdown("**X - 叙事强度**")
x_val = st.slider(
    label="X",
    min_value=0,
    max_value=100,
    value=st.session_state.get("x", 50),
    step=1,
    key="slider_x_color",
    label_visibility="collapsed"
)
st.session_state.x = x_val

x_color = get_color_gradient(x_val)
x_desc = get_x_desc(x_val)
st.markdown(
    f'<div style="color:{x_color}; font-weight:bold; font-size:1.1em; margin-top:-8px;">'
    f'当前层级：{x_desc}  ({x_val})'
    f'</div>',
    unsafe_allow_html=True
)
st.markdown("---")

# ────────────────────────────────────────────────
# Y 轴 - 影响力/喊单共识（颜色规则同 X，更高数值更红更危险）
# ────────────────────────────────────────────────
def get_y_desc(val):
    if val <= 20: return "小KOL或小社区或个人推荐"
    if val <= 40: return "中型KOL或社区或多个群体推荐"
    if val <= 60: return "顶级KOL或大量车头喊单"
    if val <= 80: return "大影响力者集体合力"
    return "顶级影响力实体喊单或上大所"

st.markdown("**Y - 影响力/喊单共识**")
y_val = st.slider(
    label="Y",
    min_value=0,
    max_value=100,
    value=st.session_state.get("y", 50),
    step=1,
    key="slider_y_color",
    label_visibility="collapsed"
)
st.session_state.y = y_val

y_color = get_color_gradient(y_val)
y_desc = get_y_desc(y_val)
st.markdown(
    f'<div style="color:{y_color}; font-weight:bold; font-size:1.1em; margin-top:-8px;">'
    f'当前层级：{y_desc}  ({y_val})'
    f'</div>',
    unsafe_allow_html=True
)
st.markdown("---")

# ────────────────────────────────────────────────
# Z 轴 - 当前价格相对位置（高位更红）
# ────────────────────────────────────────────────
st.markdown("**Z - 当前价格相对位置**")
z_val = st.slider(
    label="Z",
    min_value=0,
    max_value=100,
    value=st.session_state.get("z", 50),
    step=1,
    key="slider_z_color",
    label_visibility="collapsed"
)
st.session_state.z = z_val

z_color = get_color_gradient(z_val)
st.markdown(
    f'<div style="color:{z_color}; font-weight:bold; font-size:1.1em; margin-top:-8px;">'
    f'当前数值：{z_val} （0=极低位　100=极高位/泡沫区）'
    f'</div>',
    unsafe_allow_html=True
)
st.markdown("---")
st.session_state.z = z_val
st.markdown(f"**当前数值：** {z_val}  （0=极低位，100=极高位）")
st.markdown("---")
st.subheader("你的仓位情况")
st.session_state.position = st.slider("当前仓位占总资金比例（%）", 0, 100, st.session_state.position)

st.session_state.notes = st.text_area(
    "你的交易计划 / 心理预期 / 止损止盈想法（可选）",
    value=st.session_state.notes,
    height=90
)

# ------------------- 诊断按钮 & 结果 -------------------
if st.button("生成诊断报告", type="primary"):
    if not st.session_state.token_data:
        st.warning("请先查询一个有效的代币")
    else:
        st.session_state.diagnosed = True

if st.session_state.diagnosed:
    score = calculate_risk_score(
        st.session_state.x,
        st.session_state.y,
        st.session_state.z,
        st.session_state.position
    )
    label, message, level = risk_label_and_message(score)

    st.subheader("诊断结果")

    if level == "success":
        st.success(f"**{label}**  \n{message}  \n风险分数：**{score:.2f}**")
    elif level == "warning":
        st.warning(f"**{label}**  \n{message}  \n风险分数：**{score:.2f}**")
    else:
        st.error(f"**{label}**  \n{message}  \n风险分数：**{score:.2f}**")

    with st.expander("风险分数构成参考"):
        st.markdown(f"""
        - 情绪放大（Y）贡献：{st.session_state.y / 100 * 0.35:.2f}
        - 价格位置（Z）贡献：{st.session_state.z / 100 * 0.28:.2f}
        - 仓位占比（P）贡献：{st.session_state.position / 100 * 0.22:.2f}
        - 叙事弱势（1-X）贡献：{(1 - st.session_state.x / 100) * 0.15:.2f}
        """)

# ------------------- 页脚 -------------------
st.markdown("---")
st.caption("仅供娱乐与自我反省使用　・　Meme 市场极度高风险　・　请理性参与")