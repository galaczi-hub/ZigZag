#!/usr/bin/env python3
"""
ZigZag Harmonikus Minta Scanner
BTCUSD 30 perces - Telegram push ertesites
GitHub Actions-on fut minden 30 percben
"""

import os
import requests
import datetime
import math

# KONFIGURÁCIÓ
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Binance API - ingyenes, nincs API kulcs kell
SYMBOL    = "BTCUSDT"
INTERVAL  = "30m"
LIMIT     = 200  # 200 gyertya elegendo a ZigZag szamitashoz

# Fibonacci szintek
FIB_EW = 0.236
FIB_TP = 0.618
FIB_SL = -0.236


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    resp = requests.post(url, json=payload, timeout=10)
    if resp.ok:
        print("Telegram uzenet elkuldve!")
    else:
        print(f"Telegram hiba: {resp.text}")


def get_btc_candles():
    """Kraken API-rol lekeri a BTCUSD 30m gyertyakat (nincs geo-blokk)"""
    url = "https://api.kraken.com/0/public/OHLC"
    params = {
        "pair": "XBTUSD",
        "interval": 30,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        raise Exception(f"Kraken hiba: {data['error']}")

    ohlc = data["result"].get("XXBTZUSD", [])

    candles = []
    for c in ohlc[:-1]:  # utolso gyertya meg nem zart
        candles.append({
            "time":  datetime.datetime.fromtimestamp(int(c[0])),
            "open":  float(c[1]),
            "high":  float(c[2]),
            "low":   float(c[3]),
            "close": float(c[4])
        })
    return candles
    return candles


def compute_zigzag(candles, depth=12, deviation=5):
    """ZigZag csucsok es melypontok kiszamitasa"""
    pivots = []  # (index, price, direction: 'H' or 'L')

    i = depth
    while i < len(candles) - depth:
        # Magas pont ellenorzese
        is_high = True
        for j in range(i - depth, i + depth + 1):
            if j != i and candles[j]["high"] >= candles[i]["high"]:
                is_high = False
                break

        # Melypont ellenorzese
        is_low = True
        for j in range(i - depth, i + depth + 1):
            if j != i and candles[j]["low"] <= candles[i]["low"]:
                is_low = False
                break

        if is_high:
            if pivots and pivots[-1][2] == 'H':
                if candles[i]["high"] > pivots[-1][1]:
                    pivots[-1] = (i, candles[i]["high"], 'H')
            else:
                pivots.append((i, candles[i]["high"], 'H'))
        elif is_low:
            if pivots and pivots[-1][2] == 'L':
                if candles[i]["low"] < pivots[-1][1]:
                    pivots[-1] = (i, candles[i]["low"], 'L')
            else:
                pivots.append((i, candles[i]["low"], 'L'))
        i += 1

    return pivots


def calc_ratios(x, a, b, c, d):
    """Fibonacci aranyok kiszamitasa"""
    if abs(x - a) < 0.001 or abs(a - b) < 0.001 or abs(b - c) < 0.001:
        return None

    xab = abs(b - a) / abs(x - a)
    xad = abs(a - d) / abs(x - a)
    abc = abs(b - c) / abs(a - b)
    bcd = abs(c - d) / abs(b - c)

    return xab, abc, bcd, xad


def fib_level(c, d, rate):
    fib_range = abs(d - c)
    if d > c:
        return d - (fib_range * rate)
    else:
        return d + (fib_range * rate)


def detect_patterns(x, a, b, c, d):
    """Osszes harmonikus minta ellenorzese"""
    ratios = calc_ratios(x, a, b, c, d)
    if not ratios:
        return []

    xab, abc, bcd, xad = ratios
    bull = d < c
    bear = d > c

    found = []

    # ABCD
    if (0.382 <= abc <= 0.886) and (1.13 <= bcd <= 2.618):
        if bull: found.append("🟢 Bull ABCD")
        if bear: found.append("🔴 Bear ABCD")

    # Bat
    if (0.382 <= xab <= 0.500) and (0.382 <= abc <= 0.886) and (1.618 <= bcd <= 2.618) and (xad <= 0.618):
        if bull: found.append("🟢 Bull Bat")
        if bear: found.append("🔴 Bear Bat")

    # Alt Bat
    if (xab <= 0.382) and (0.382 <= abc <= 0.886) and (2.0 <= bcd <= 3.618) and (xad <= 1.13):
        if bull: found.append("🟢 Bull Alt Bat")
        if bear: found.append("🔴 Bear Alt Bat")

    # Butterfly
    if (xab <= 0.786) and (0.382 <= abc <= 0.886) and (1.618 <= bcd <= 2.618) and (1.27 <= xad <= 1.618):
        if bull: found.append("🟢 Bull Butterfly")
        if bear: found.append("🔴 Bear Butterfly")

    # Gartley
    if (0.500 <= xab <= 0.618) and (0.382 <= abc <= 0.886) and (1.13 <= bcd <= 2.618) and (0.75 <= xad <= 0.875):
        if bull: found.append("🟢 Bull Gartley")
        if bear: found.append("🔴 Bear Gartley")

    # Crab
    if (0.500 <= xab <= 0.875) and (0.382 <= abc <= 0.886) and (2.000 <= bcd <= 5.000) and (1.382 <= xad <= 5.000):
        if bull: found.append("🟢 Bull Crab")
        if bear: found.append("🔴 Bear Crab")

    # Shark
    if (0.500 <= xab <= 0.875) and (1.130 <= abc <= 1.618) and (1.270 <= bcd <= 2.240) and (0.886 <= xad <= 1.130):
        if bull: found.append("🟢 Bull Shark")
        if bear: found.append("🔴 Bear Shark")

    # Wolf Wave
    if (1.27 <= xab <= 1.618) and (1.27 <= bcd <= 1.618):
        if bull: found.append("🟢 Bull Wolf Wave")
        if bear: found.append("🔴 Bear Wolf Wave")

    return found


def run():
    print(f"ZigZag scanner indul: {datetime.datetime.now()}")

    # Gyertyak letoltese
    candles = get_btc_candles()
    print(f"{len(candles)} gyertya letoltve")

    # ZigZag kiszamitasa
    pivots = compute_zigzag(candles)
    print(f"{len(pivots)} ZigZag pont talalt")

    if len(pivots) < 5:
        print("Nincs eleg ZigZag pont, kilepes")
        return

    # Utolso 5 pont: x, a, b, c, d
    x = pivots[-5][1]
    a = pivots[-4][1]
    b = pivots[-3][1]
    c = pivots[-2][1]
    d = pivots[-1][1]

    current_price = candles[-1]["close"]
    current_time  = candles[-1]["time"].strftime("%Y-%m-%d %H:%M")

    print(f"XABCD: x={x:.2f} a={a:.2f} b={b:.2f} c={c:.2f} d={d:.2f}")
    print(f"Jelenlegi ar: {current_price:.2f}")

    # Minta felismerese
    patterns = detect_patterns(x, a, b, c, d)

    if not patterns:
        print("Nincs minta - nincs uzenet")
        return

    # Fibonacci szintek
    ew = fib_level(c, d, FIB_EW)
    tp = fib_level(c, d, FIB_TP)
    sl = fib_level(c, d, FIB_SL)

    # BUY jel: bull minta es az ar az entry window-ban van
    bull_patterns = [p for p in patterns if "Bull" in p]
    bear_patterns = [p for p in patterns if "Bear" in p]

    signal = None
    if bull_patterns and current_price <= ew:
        signal = "BUY"
        signal_patterns = bull_patterns
    elif bear_patterns and current_price >= ew:
        signal = "SELL"
        signal_patterns = bear_patterns

    if not signal:
        print(f"Minta talalt de az ar nincs az entry window-ban (EW={ew:.2f}, ar={current_price:.2f})")
        return

    # Telegram uzenet
    direction = "📈 LONG (BUY)" if signal == "BUY" else "📉 SHORT (SELL)"
    message = f"""⚡ <b>BTCUSD JEL - {direction}</b>

🕐 Ido: {current_time} (30m)
💰 Jelenlegi ar: <b>${current_price:,.2f}</b>

📐 Mintak:
{chr(10).join(signal_patterns)}

🎯 Szintek:
• Entry Window: ${ew:,.2f}
• Take Profit: ${tp:,.2f}
• Stop Loss: ${sl:,.2f}

📊 XABCD pontok:
X={x:.2f} → A={a:.2f} → B={b:.2f} → C={c:.2f} → D={d:.2f}

⚠️ Csak tajekoztatas - kereskedj felelos!"""

    send_telegram(message)
    print(f"Jel kuldve: {signal} - {signal_patterns}")


if __name__ == "__main__":
    run()
