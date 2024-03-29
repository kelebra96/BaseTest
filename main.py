import streamlit as st
import requests
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime, timedelta

# Configurações iniciais
st.set_page_config(
    page_title="Crypto Monitor with Bollinger Bands and Moving Average",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

import sqlite3

# Conectar ao banco de dados SQLite (será criado se não existir)
conn = sqlite3.connect("trades.db")
c = conn.cursor()

# Criar a tabela de trades (se não existir)
c.execute(
    """
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY,
        buy_price REAL,
        sell_price REAL,
        profit_loss REAL
    )
"""
)
conn.commit()


# Definir função para obter dados da Binance para o gráfico de candlestick
def get_candle_data(crypto_symbol, interval, lookback):
    base_url = f"https://api.binance.com/api/v3/klines"
    params = {"symbol": crypto_symbol, "interval": interval, "limit": lookback}
    response = requests.get(base_url, params=params)
    data = response.json()
    df = pd.DataFrame(data)
    df.columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base_asset_volume",
        "taker_buy_quote_asset_volume",
        "ignore",
    ]
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    df = df.astype(
        {
            "open": "float",
            "high": "float",
            "low": "float",
            "close": "float",
            "volume": "float",
        }
    )

    # Cálculo das Bandas de Bollinger e Média Móvel
    df["MA20"] = df["close"].rolling(window=20).mean()  # Média Móvel de 20 períodos
    df["STD20"] = df["close"].rolling(window=20).std()  # Desvio Padrão de 20 períodos
    df["Upper"] = df["MA20"] + (df["STD20"] * 2)  # Banda Superior
    df["Lower"] = df["MA20"] - (df["STD20"] * 2)  # Banda Inferior

    return df


# Título da aplicação
st.title(":Trading Simulator")

# Entrada do usuário para o símbolo da criptomoeda e intervalo de tempo para o gráfico de candlestick
crypto_symbol = st.sidebar.selectbox(
    "Selecione o símbolo criptográfico:",
    options=["BTCUSDT", "ETHUSDT", "DOGEUSDT"],
    index=0,
)
interval = st.sidebar.selectbox(
    "Selecione o intervalo para o gráfico de velas:",
    options=["1m", "5m", "15m", "1h", "1d"],
    index=0,
)

# Inputs para ordens de compra e venda
st.sidebar.header("Trading Simulator")
buy_price = st.sidebar.number_input("Preço de compra:", min_value=0, value=0, step=1000)
sell_price = st.sidebar.number_input("Preço de venda:", min_value=0, value=0, step=1000)
st.sidebar.text("Enter 0 in any field to ignore that order.")

# Inicializar o estado para armazenar ordens e lucro/perda
if "orders" not in st.session_state:
    st.session_state["orders"] = []
if "profit" not in st.session_state:
    st.session_state["profit"] = 0.0

# Botão para buscar dados da criptomoeda
if (
    st.sidebar.button("Get Data") or True
):  # Remova 'or True' para desabilitar a atualização automática
    # Quantidade de  candlestick no gráfico
    lookback = st.sidebar.selectbox(
        "Selecione o número de candles:",
        options=[5, 10, 20, 50, 100, 150, 200],
        index=0,
    )
    candle_data = get_candle_data(
        crypto_symbol, interval, lookback
    )  # Obter os últimos candlesticks selecionados

    # Criar o gráfico de candlestick
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=candle_data["open_time"],
                open=candle_data["open"],
                high=candle_data["high"],
                low=candle_data["low"],
                close=candle_data["close"],
            )
        ]
    )

    # Adicionar Bandas de Bollinger e Média Móvel ao gráfico
    fig.add_trace(
        go.Scatter(
            x=candle_data["open_time"],
            y=candle_data["Upper"],
            name="Banda Superior",
            line=dict(color="rgba(250, 0, 0, 0.50)"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=candle_data["open_time"],
            y=candle_data["Lower"],
            name="Banda Inferior",
            line=dict(color="rgba(0, 0, 250, 0.50)"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=candle_data["open_time"],
            y=candle_data["MA20"],
            name="Média Móvel (20)",
            line=dict(color="rgba(0, 255, 0, 0.50)"),
        )
    )

    # Plotar ordens no gráfico
    for order in st.session_state["orders"]:
        fig.add_annotation(
            x=order["time"],
            y=order["price"],
            text=f"Trade {order['type']} at {order['price']}",
            showarrow=True,
            arrowhead=1,
            ax=0,
            ay=-40,
        )
        fig.add_trace(
            go.Scatter(
                x=[order["time"]],
                y=[order["price"]],
                mode="markers",
                marker=dict(
                    size=10, color="green" if order["type"] == "buy" else "red"
                ),
                name=f"{order['type'].capitalize()} at {order['price']}",
            )
        )

    # Exibir o gráfico
    fig.update_layout(
        title=f"{crypto_symbol} Gráfico de velas com bandas de Bollinger e média móvel ({interval})",
        xaxis_title="Time",
        yaxis_title="Preço (USDT)",
        xaxis_rangeslider_visible=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Lógica para lidar com ordens de compra e venda
last_price = candle_data.iloc[-1]["close"]

# Inicializar o lucro/perda total
total_profit_loss = 0.0

# Processar ordens de compra
if buy_price > 0 and last_price <= buy_price:
    # Registrar ordem de compra
    st.session_state["orders"].append(
        {
            "type": "buy",
            "price": buy_price,
            "time": candle_data.iloc[-1]["open_time"],
        }
    )
    st.success(f"Comprei em {buy_price}")  # Valor da compra!!!!

# Processar ordens de venda
if sell_price > 0 and last_price >= sell_price:
    # Registrar ordem de venda
    st.session_state["orders"].append(
        {
            "type": "sell",
            "price": sell_price,
            "time": candle_data.iloc[-1]["open_time"],
        }
    )
    st.success(f"Vendido em {sell_price}")  # Valor da venda!!!!

# Calcular lucro/perda total
for order in st.session_state["orders"]:
    if order["type"] == "buy":
        total_profit_loss -= order["price"]  # Dinheiro gasto na compra
    elif order["type"] == "sell":
        total_profit_loss += order["price"]  # Dinheiro recebido na venda

# Adicionar/subtrair o valor do último preço para compras não vendidas
unrealized_profit_loss = 0
if (
    len(st.session_state["orders"]) > 0
    and st.session_state["orders"][-1]["type"] == "buy"
):
    unrealized_profit_loss = last_price - st.session_state["orders"][-1]["price"]

# Exibir o lucro/perda total (realizado + não realizado)
st.metric(
    label="Total Profit/Loss",
    value=f"{total_profit_loss - unrealized_profit_loss} {crypto_symbol[-4:]}",
)

# Adicionar botão para finalizar trade
finalize_trade = st.sidebar.button("Finalizar Trade")

# Lógica para lidar com ordens de compra e venda
last_price = candle_data.iloc[-1]["close"]

# Processar ordens de compra
if (
    buy_price > 0
    and last_price <= buy_price
    and not any(order["type"] == "buy" for order in st.session_state["orders"])
):
    # Registrar ordem de compra
    st.session_state["orders"].append(
        {
            "type": "buy",
            "price": buy_price,
            "time": candle_data.iloc[-1]["open_time"],
        }
    )
    st.success(f"Comprei em {buy_price}")  # Valor da compra!!!!

# Processar ordens de venda
if (
    sell_price > 0
    and last_price >= sell_price
    and not any(order["type"] == "sell" for order in st.session_state["orders"])
):
    # Registrar ordem de venda
    st.session_state["orders"].append(
        {
            "type": "sell",
            "price": sell_price,
            "time": candle_data.iloc[-1]["open_time"],
        }
    )
    st.success(f"Vendido em {sell_price}")  # Valor da venda!!!!

# Se o usuário clicar em "Finalizar Trade", calcular o lucro/perda
if finalize_trade and len(st.session_state["orders"]) > 0:
    # Calcular lucro/perda total
    total_profit_loss = 0.0
    for order in st.session_state["orders"]:
        if order["type"] == "buy":
            total_profit_loss -= order["price"]  # Dinheiro gasto na compra
        elif order["type"] == "sell":
            total_profit_loss += order["price"]  # Dinheiro recebido na venda

    # Exibir o lucro/perda total
    st.metric(
        label="Total Profit/Loss", value=f"{total_profit_loss} {crypto_symbol[-4:]}"
    )

    # Resetar ordens
    st.session_state["orders"] = []

# Exibir o último preço
st.success(f"O último preço de fechamento de {crypto_symbol} é {last_price}")

# Se o usuário clicar em "Finalizar Trade", registrar o trade no banco de dados
if finalize_trade and len(st.session_state["orders"]) > 0:
    # Calcular lucro/perda total
    total_profit_loss = 0.0
    for order in st.session_state["orders"]:
        if order["type"] == "buy":
            total_profit_loss -= order["price"]  # Dinheiro gasto na compra
        elif order["type"] == "sell":
            total_profit_loss += order["price"]  # Dinheiro recebido na venda

    # Inserir detalhes do trade no banco de dados
    c.execute(
        "INSERT INTO trades (buy_price, sell_price, profit_loss) VALUES (?, ?, ?)",
        (buy_price, sell_price, total_profit_loss),
    )
    conn.commit()

    # Exibir o lucro/perda total
    st.metric(
        label="Total Profit/Loss", value=f"{total_profit_loss} {crypto_symbol[-4:]}"
    )

    # Resetar ordens
    st.session_state["orders"] = []


# Consultar e exibir trades do banco de dados
c.execute("SELECT * FROM trades")
trades = c.fetchall()
df_trades = pd.DataFrame(
    trades, columns=["ID", "Buy Price", "Sell Price", "Profit/Loss"]
)
st.dataframe(df_trades)


# Identificar e exibir sinais de compra
last_row = candle_data.iloc[-1]
if last_row["close"] <= last_row["Lower"]:
    st.warning(
        "Possível sinal de COMPRA (o preço está igual ou abaixo da faixa inferior de Bollinger)."
    )
    # Identificar e exibir sinais de venda
    if last_row["close"] >= last_row["Upper"]:
        st.warning(
            "Possível sinal de VENDA (o preço está igual ou acima da faixa superior de Bollinger)."
        )
# Atualizar automaticamente a cada minuto
st_autorefresh = st.sidebar.checkbox("Atualização automática a cada minuto", value=True)
if st_autorefresh:
    refresh_interval = 60 * 1000  # 60 segundos em milissegundos
    st.experimental_rerun()

# Instruções
st.sidebar.write("1. Enter the crypto symbol in the input box.")
st.sidebar.write("2. Select the interval for the candlestick chart.")
st.sidebar.write("3. Click on 'Get Data' to fetch the latest data.")
st.sidebar.write("4. Check 'Auto-refresh every minute' for live updates.")
st.sidebar.write(
    "5. Enter buy/sell prices in the Trading Simulator section to simulate trades."
)
