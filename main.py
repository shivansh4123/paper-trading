import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, time as dt_time
import pytz
import time

# --- CONFIGURATION & STYLING ---
st.set_page_config(page_title="ProTrade India | Ultimate", layout="wide", page_icon="📈")

# Professional Dark Theme CSS
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    /* Buttons */
    div.stButton > button { background-color: #262730; color: white; border: 1px solid #4B4B4B; border-radius: 6px; }
    div.stButton > button:hover { border-color: #00CC96; color: #00CC96; box-shadow: 0 0 8px rgba(0, 204, 150, 0.4); }
    /* Inputs */
    .stTextInput > div > div > input { background-color: #1E1E1E; color: white; }
    /* Tables */
    thead tr th:first-child { display:none }
    tbody th { display:none }
    /* Status Labels */
    .status-open { color: #00CC96; font-weight: 800; letter-spacing: 1px; }
    .status-closed { color: #EF553B; font-weight: 800; letter-spacing: 1px; }
    /* Small Text */
    .small-font { font-size: 0.85em; color: #A0A0A0; }
</style>
""", unsafe_allow_html=True)

# --- GLOBAL SETTINGS ---
IST = pytz.timezone('Asia/Kolkata')

# --- INITIALIZE SESSION STATE ---
if 'balance' not in st.session_state:
    st.session_state.balance = 1000000.0
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'realized_pnl' not in st.session_state:
    st.session_state.realized_pnl = 0.0
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS']
if 'active_symbol' not in st.session_state:
    st.session_state.active_symbol = 'RELIANCE.NS'

# --- HELPER FUNCTIONS ---

def is_market_open():
    """Checks NSE Market Hours (09:15 - 15:30 IST)."""
    now_utc = datetime.now(pytz.utc)
    now_ist = now_utc.astimezone(IST)
    if now_ist.weekday() >= 5: return False, "WEEKEND"
    
    current_time = now_ist.time()
    if dt_time(9, 15) <= current_time <= dt_time(15, 30):
        return True, "MARKET OPEN"
    return False, "MARKET CLOSED"

@st.cache_data(ttl=30)
def get_live_price(ticker):
    """Fetches real-time price efficiently."""
    try:
        # Fast fetch
        data = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not data.empty:
            return float(data['Close'].iloc[-1])
        # Fallback for closed market/illiquid
        hist = yf.Ticker(ticker).history(period="5d")
        return float(hist['Close'].iloc[-1]) if not hist.empty else None
    except:
        return None

def get_stock_fundamentals(ticker):
    """Fetches company info."""
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

def calculate_taxes(turnover, transaction_type="Buy", mode="Delivery"):
    """Estimates Taxes: Brokerage, STT, Exchange Txn, GST, Stamp Duty."""
    brokerage = min(20, 0.0003 * turnover) if mode == "Intraday" else 0
    stt = 0.1 * turnover / 100 if mode == "Delivery" else (0.025 * turnover / 100 if transaction_type == "Sell" else 0)
    exchange_txn = 0.00345 * turnover / 100
    sebi = 0.0001 * turnover / 100
    stamp = 0.003 * turnover / 100 if transaction_type == "Buy" else 0
    gst = 0.18 * (brokerage + exchange_txn + sebi)
    return brokerage + stt + exchange_txn + sebi + stamp + gst

def smart_search(query):
    """Formats user input to NSE ticker."""
    if not query: return "RELIANCE.NS"
    clean = query.strip().upper().replace(" ", "").replace("-", "")
    if not clean.endswith(".NS") and not clean.endswith(".BO"):
        clean += ".NS"
    return clean

# --- SIDEBAR: ACCOUNT & WATCHLIST ---
with st.sidebar:
    st.title("📊 My Account")
    
    # 1. Live Account Stats
    total_invested = 0
    total_current_val = 0
    for pos in st.session_state.portfolio:
        lp = get_live_price(pos['symbol'])
        lp = lp if lp else pos['avg_price']
        total_invested += pos['qty'] * pos['avg_price']
        total_current_val += pos['qty'] * lp
        
    unrealized = total_current_val - total_invested
    net_worth = st.session_state.balance + total_current_val
    
    st.metric("Total Net Worth", f"₹{net_worth:,.0f}")
    st.metric("Available Cash", f"₹{st.session_state.balance:,.0f}")
    st.divider()
    st.metric("Realized P&L", f"₹{st.session_state.realized_pnl:,.2f}")
    st.metric("Unrealized P&L", f"₹{unrealized:,.2f}", delta=unrealized)
    
    if st.button("🔴 Reset Account"):
        st.session_state.balance = 1000000.0
        st.session_state.portfolio = []
        st.session_state.trade_history = []
        st.session_state.realized_pnl = 0.0
        st.rerun()

    st.markdown("---")
    
    # 2. RESTORED WATCHLIST
    st.subheader("👀 Watchlist")
    wl_input = st.text_input("Add Symbol", placeholder="e.g. TATASTEEL")
    if st.button("Add to Watchlist"):
        clean_wl = smart_search(wl_input)
        if clean_wl not in st.session_state.watchlist:
            if get_live_price(clean_wl):
                st.session_state.watchlist.append(clean_wl)
                st.rerun()
            else:
                st.error("Invalid Symbol")

    # Display Watchlist Items
    for ticker in st.session_state.watchlist:
        wl_price = get_live_price(ticker)
        if wl_price:
            c1, c2, c3 = st.columns([2, 1.5, 1])
            c1.markdown(f"**{ticker.replace('.NS','')}**")
            c2.markdown(f"₹{wl_price:.1f}")
            if c3.button("➤", key=f"trade_{ticker}"):
                st.session_state.active_symbol = ticker
                st.rerun()
        st.markdown("<hr style='margin: 5px 0; border-color: #333;'>", unsafe_allow_html=True)

# --- MAIN DASHBOARD ---
st.title("ProTrade India 🇮🇳 Terminal")

# Market Status Banner
is_open, status_msg = is_market_open()
st.markdown(f"**Status:** <span class='{'status-open' if is_open else 'status-closed'}'>{status_msg}</span>", unsafe_allow_html=True)

# Search Bar (Updates active_symbol)
col_search, col_price = st.columns([3, 1])
with col_search:
    search_input = st.text_input("🔍 Search Stock", value=st.session_state.active_symbol.replace(".NS",""), placeholder="Type stock name...")
    # Update session state only if input changes
    formatted_search = smart_search(search_input)
    if formatted_search != st.session_state.active_symbol:
         st.session_state.active_symbol = formatted_search

active_symbol = st.session_state.active_symbol

# Fetch Main Data
try:
    ticker_obj = yf.Ticker(active_symbol)
    df = ticker_obj.history(period="1d", interval="1m")
    if df.empty:
        df = ticker_obj.history(period="5d")
    
    current_price = df['Close'].iloc[-1]
    prev_close = ticker_obj.info.get('previousClose', df['Open'].iloc[0])
    change_pct = ((current_price - prev_close) / prev_close) * 100
    
    with col_price:
        st.metric(active_symbol.replace(".NS", ""), f"₹{current_price:,.2f}", f"{change_pct:.2f}%")

except:
    st.error(f"Could not find data for '{active_symbol}'.")
    st.stop()

# --- TABS ---
tab_chart, tab_trade, tab_pf, tab_info, tab_hist = st.tabs(["📈 Chart", "⚡ Order Panel", "💼 Portfolio", "🏢 Deep Dive", "📜 History"])

# 1. CHART TAB
with tab_chart:
    chart_col1, chart_col2 = st.columns([1, 6])
    with chart_col1:
        c_period = st.selectbox("Period", ["1D", "5D", "1M", "6M", "1Y"], index=0)
    
    p_map = {"1D": "1d", "5D": "5d", "1M": "1mo", "6M": "6mo", "1Y": "1y"}
    i_map = {"1D": "5m", "5D": "15m", "1M": "1d", "6M": "1d", "1Y": "1d"}
    
    df_chart = ticker_obj.history(period=p_map[c_period], interval=i_map[c_period])
    
    fig = go.Figure(data=[go.Candlestick(x=df_chart.index,
                open=df_chart['Open'], high=df_chart['High'],
                low=df_chart['Low'], close=df_chart['Close'], name=active_symbol)])
    
    fig.update_layout(height=500, template="plotly_dark", margin=dict(l=0, r=0, t=20, b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# 2. ORDER PANEL
with tab_trade:
    st.subheader(f"Trade {active_symbol}")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        side = st.radio("Side", ["Buy", "Sell"], horizontal=True)
        qty = st.number_input("Quantity", min_value=1, value=10)
    with c2:
        order_type = st.radio("Order Type", ["Market", "Limit"], horizontal=True)
        limit_price = st.number_input("Limit Price (₹)", value=float(current_price)) if order_type == "Limit" else current_price
    with c3:
        product = st.selectbox("Product", ["Delivery (CNC)", "Intraday (MIS)"])
    
    st.markdown("---")
    st.write("**Risk Management (Optional)**")
    r1, r2 = st.columns(2)
    with r1:
        stop_loss = st.number_input("🛑 Stop Loss (0=Disable)", min_value=0.0, value=0.0, step=0.5, format="%.2f")
    with r2:
        target_price = st.number_input("🎯 Target (0=Disable)", min_value=0.0, value=0.0, step=0.5, format="%.2f")
        
    trade_val = limit_price * qty
    taxes = calculate_taxes(trade_val, side, "Intraday" if "Intraday" in product else "Delivery")
    total_req = trade_val + taxes
    
    st.info(f"**Est. Margin:** ₹{trade_val:,.2f}  |  **Taxes:** ₹{taxes:,.2f}  |  **Total:** ₹{total_req:,.2f}")
    
    disabled_state = not is_open
    
    if st.button(f"CONFIRM {side.upper()}", use_container_width=True, type="primary", disabled=disabled_state):
        if side == "Buy":
            if st.session_state.balance >= total_req:
                st.session_state.balance -= total_req
                
                # Consolidation Logic
                existing_pos = next((p for p in st.session_state.portfolio if p['symbol'] == active_symbol), None)
                if existing_pos:
                    total_old = existing_pos['qty'] * existing_pos['avg_price']
                    total_new = qty * limit_price
                    existing_pos['qty'] += qty
                    existing_pos['avg_price'] = (total_old + total_new) / existing_pos['qty']
                    existing_pos['sl'] = stop_loss 
                    existing_pos['tgt'] = target_price
                else:
                    st.session_state.portfolio.append({
                        "symbol": active_symbol, "qty": qty, "avg_price": limit_price, 
                        "mode": product, "sl": stop_loss, "tgt": target_price
                    })
                
                st.success("Order Executed!")
                st.rerun()
            else:
                st.error("Insufficient Funds")
        
        elif side == "Sell":
            existing_pos = next((p for p in st.session_state.portfolio if p['symbol'] == active_symbol), None)
            if existing_pos and existing_pos['qty'] >= qty:
                sale_val = qty * limit_price
                sell_taxes = calculate_taxes(sale_val, "Sell", existing_pos['mode'])
                
                st.session_state.balance += (sale_val - sell_taxes)
                
                # P&L Logic
                buy_cost = qty * existing_pos['avg_price']
                net_pnl = (sale_val - sell_taxes) - buy_cost
                
                st.session_state.realized_pnl += net_pnl
                st.session_state.trade_history.append({
                    "symbol": active_symbol, "action": "SELL", "qty": qty, "price": limit_price, "pnl": net_pnl, "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                
                existing_pos['qty'] -= qty
                if existing_pos['qty'] == 0:
                    st.session_state.portfolio.remove(existing_pos)
                
                st.success(f"Sold. Net P&L: ₹{net_pnl:.2f}")
                st.rerun()
            else:
                st.error("Insufficient Holdings.")
    
    if not is_open:
        st.warning("⚠️ Market is Closed. Orders disabled.")

# 3. PORTFOLIO TAB
with tab_pf:
    st.subheader("💼 Consolidated Holdings")
    if not st.session_state.portfolio:
        st.info("No active positions.")
    else:
        # Metrics
        total_inv = sum(p['qty'] * p['avg_price'] for p in st.session_state.portfolio)
        total_cur = 0
        total_net_pnl = 0
        
        portfolio_rows = []
        for i, p in enumerate(st.session_state.portfolio):
            ltp = get_live_price(p['symbol']) or p['avg_price']
            cur_val = p['qty'] * ltp
            total_cur += cur_val
            
            # Tax if exited now
            est_tax = calculate_taxes(cur_val, "Sell", p['mode'])
            gross_pnl = cur_val - (p['qty'] * p['avg_price'])
            net_pnl = gross_pnl - est_tax
            total_net_pnl += net_pnl
            
            status = ""
            if p['sl'] > 0 and ltp <= p['sl']: status = "🛑 SL HIT"
            if p['tgt'] > 0 and ltp >= p['tgt']: status = "🎯 TGT HIT"
            
            portfolio_rows.append({
                "Symbol": p['symbol'].replace(".NS",""), "Qty": p['qty'], 
                "Avg": p['avg_price'], "LTP": ltp, "Net P&L": net_pnl, 
                "Status": status, "idx": i
            })

        c1, c2, c3 = st.columns(3)
        c1.metric("Invested Capital", f"₹{total_inv:,.0f}")
        c2.metric("Current Value", f"₹{total_cur:,.0f}")
        c3.metric("Net P&L (Post-Tax)", f"₹{total_net_pnl:,.2f}", delta=total_net_pnl)
        
        st.divider()
        
        # Portfolio Table
        h1, h2, h3, h4, h5, h6 = st.columns([2, 1, 1.5, 1.5, 2, 1])
        h1.write("**Symbol**")
        h2.write("**Qty**")
        h3.write("**Avg**")
        h4.write("**LTP**")
        h5.write("**Net P&L**")
        h6.write("**Exit**")
        
        for row in portfolio_rows:
            with st.container():
                c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 1.5, 1.5, 2, 1])
                c1.write(f"**{row['Symbol']}**")
                c1.caption(row['Status'])
                c2.write(str(row['Qty']))
                c3.write(f"₹{row['Avg']:.1f}")
                c4.write(f"₹{row['LTP']:.1f}")
                
                color = "green" if row['Net P&L'] >= 0 else "red"
                c5.markdown(f":{color}[₹{row['Net P&L']:.1f}]")
                
                if c6.button("EXIT", key=f"ex_{row['idx']}"):
                    pos = st.session_state.portfolio[row['idx']]
                    sell_val = pos['qty'] * row['LTP']
                    tax = calculate_taxes(sell_val, "Sell", pos['mode'])
                    
                    st.session_state.balance += (sell_val - tax)
                    st.session_state.realized_pnl += row['Net P&L']
                    
                    st.session_state.trade_history.append({
                        "symbol": pos['symbol'], "action": "EXIT", "price": row['LTP'], 
                        "pnl": row['Net P&L'], "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    st.session_state.portfolio.pop(row['idx'])
                    st.rerun()
                st.markdown("<hr style='margin: 5px 0; border-color: #333;'>", unsafe_allow_html=True)
        
        if st.button("Check Auto-Exit (SL/Target)"):
            triggered = False
            for i in range(len(st.session_state.portfolio) - 1, -1, -1):
                p = st.session_state.portfolio[i]
                ltp = get_live_price(p['symbol']) or p['avg_price']
                if (p['sl'] > 0 and ltp <= p['sl']) or (p['tgt'] > 0 and ltp >= p['tgt']):
                    # Auto sell logic
                    val = p['qty'] * ltp
                    tax = calculate_taxes(val, "Sell", p['mode'])
                    net = val - tax - (p['qty'] * p['avg_price'])
                    st.session_state.balance += (val - tax)
                    st.session_state.realized_pnl += net
                    st.session_state.trade_history.append({"symbol": p['symbol'], "action": "AUTO-EXIT", "price": ltp, "pnl": net, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
                    st.session_state.portfolio.pop(i)
                    triggered = True
            if triggered: st.success("SL/Targets executed!")
            else: st.info("No triggers hit.")

# 4. RESTORED INFO TAB
with tab_info:
    st.subheader(f"🏢 Fundamentals: {active_symbol}")
    if st.button("Fetch Deep Financials"):
        info = get_stock_fundamentals(active_symbol)
        if info:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("#### 💰 Valuation")
                st.write(f"**Market Cap:** ₹{info.get('marketCap', 0)/1e7:,.0f} Cr")
                st.write(f"**Trailing P/E:** {info.get('trailingPE', '-')}")
                st.write(f"**Price/Book:** {info.get('priceToBook', '-')}")
            with col2:
                st.markdown("#### 📈 Profitability")
                st.write(f"**ROE:** {info.get('returnOnEquity', 0)*100:.2f}%")
                st.write(f"**Profit Margin:** {info.get('profitMargins', 0)*100:.2f}%")
                st.write(f"**Debt/Equity:** {info.get('debtToEquity', '-')}")
            with col3:
                st.markdown("#### 📊 Technicals")
                st.write(f"**52W High:** ₹{info.get('fiftyTwoWeekHigh', '-')}")
                st.write(f"**52W Low:** ₹{info.get('fiftyTwoWeekLow', '-')}")
                st.write(f"**Volume:** {info.get('volume', 0):,}")
            
            st.markdown("---")
            st.caption(f"**Business Summary:** {info.get('longBusinessSummary', 'No data available.')}")
        else:
            st.error("Data unavailable.")

# 5. HISTORY TAB
with tab_hist:
    st.subheader("📜 Trade Log")
    if st.session_state.trade_history:
        st.dataframe(pd.DataFrame(st.session_state.trade_history))
    else:
        st.info("No trades yet.")
