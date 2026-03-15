#!/usr/bin/env python3
"""
ZigZag Harmonikus Minta Scanner - TELJES VERZIO
BTCUSD 30 perces - Telegram push ertesites
Mintak: Bat, AltBat, AntiBat, Butterfly, AntiButterfly,
        Gartley, AntiGartley, Crab, AntiCrab, Shark, AntiShark,
        ABCD, Wolf, 5-O, Head&Shoulders, ContrTriangle, ExpTriangle
"""

import os
import requests
import datetime

# KONFIGURÁCIÓ
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

LIMIT  = 720  # gyertyak szama
FIB_EW = 0.236
FIB_TP = 0.618
FIB_SL = -0.236


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, json=payload, timeout=10)
    if resp.ok:
        print("Telegram uzenet elkuldve!")
    else:
        print(f"Telegram hiba: {resp.text}")


def get_btc_candles():
    """Kraken API - nincs geo-blokk"""
    url = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": "XBTUSD", "interval": 30}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise Exception(f"Kraken hiba: {data['error']}")
    ohlc = data["result"].get("XXBTZUSD", [])
    candles = []
    for c in ohlc[:-1]:
        candles.append({
            "time":  datetime.datetime.fromtimestamp(int(c[0])),
            "high":  float(c[2]),
            "low":   float(c[3]),
            "close": float(c[4])
        })
    return candles


def compute_zigzag(candles, depth=12):
    """ZigZag csucsok es melypontok"""
    pivots = []
    i = depth
    while i < len(candles) - depth:
        is_high = all(candles[j]["high"] <= candles[i]["high"] for j in range(i-depth, i+depth+1) if j != i)
        is_low  = all(candles[j]["low"]  >= candles[i]["low"]  for j in range(i-depth, i+depth+1) if j != i)

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
    if abs(x-a) < 0.001 or abs(a-b) < 0.001 or abs(b-c) < 0.001:
        return None
    xab = abs(b-a) / abs(x-a)
    xad = abs(a-d) / abs(x-a)
    abc = abs(b-c) / abs(a-b)
    bcd = abs(c-d) / abs(b-c)
    return xab, abc, bcd, xad


def fib_level(c, d, rate):
    r = abs(d-c)
    return (d - r*rate) if d > c else (d + r*rate)


def detect_all_patterns(x, a, b, c, d):
    """Osszes harmonikus minta - pontosan mint a Pine Script"""
    ratios = calc_ratios(x, a, b, c, d)
    if not ratios:
        return []
    xab, abc, bcd, xad = ratios

    bull = d < c
    bear = d > c
    found = []

    # --- ABCD ---
    if (0.382 <= abc <= 0.886) and (1.13 <= bcd <= 2.618):
        if bull: found.append(("🟢 Bull AB=CD", "BUY"))
        if bear: found.append(("🔴 Bear AB=CD", "SELL"))

    # --- Bat ---
    if (0.382 <= xab <= 0.500) and (0.382 <= abc <= 0.886) and (1.618 <= bcd <= 2.618) and (xad <= 0.618):
        if bull: found.append(("🟢 Bull Bat", "BUY"))
        if bear: found.append(("🔴 Bear Bat", "SELL"))

    # --- Anti Bat ---
    if (0.500 <= xab <= 0.886) and (1.000 <= abc <= 2.618) and (1.618 <= bcd <= 2.618) and (0.886 <= xad <= 1.000):
        if bull: found.append(("🟢 Bull Anti Bat", "BUY"))
        if bear: found.append(("🔴 Bear Anti Bat", "SELL"))

    # --- Alt Bat ---
    if (xab <= 0.382) and (0.382 <= abc <= 0.886) and (2.0 <= bcd <= 3.618) and (xad <= 1.13):
        if bull: found.append(("🟢 Bull Alt Bat", "BUY"))
        if bear: found.append(("🔴 Bear Alt Bat", "SELL"))

    # --- Butterfly ---
    if (xab <= 0.786) and (0.382 <= abc <= 0.886) and (1.618 <= bcd <= 2.618) and (1.27 <= xad <= 1.618):
        if bull: found.append(("🟢 Bull Butterfly", "BUY"))
        if bear: found.append(("🔴 Bear Butterfly", "SELL"))

    # --- Anti Butterfly ---
    if (0.236 <= xab <= 0.886) and (1.130 <= abc <= 2.618) and (1.000 <= bcd <= 1.382) and (0.500 <= xad <= 0.886):
        if bull: found.append(("🟢 Bull Anti Butterfly", "BUY"))
        if bear: found.append(("🔴 Bear Anti Butterfly", "SELL"))

    # --- Gartley ---
    if (0.500 <= xab <= 0.618) and (0.382 <= abc <= 0.886) and (1.13 <= bcd <= 2.618) and (0.75 <= xad <= 0.875):
        if bull: found.append(("🟢 Bull Gartley", "BUY"))
        if bear: found.append(("🔴 Bear Gartley", "SELL"))

    # --- Anti Gartley ---
    if (0.500 <= xab <= 0.886) and (1.000 <= abc <= 2.618) and (1.500 <= bcd <= 5.000) and (1.000 <= xad <= 5.000):
        if bull: found.append(("🟢 Bull Anti Gartley", "BUY"))
        if bear: found.append(("🔴 Bear Anti Gartley", "SELL"))

    # --- Crab ---
    if (0.500 <= xab <= 0.875) and (0.382 <= abc <= 0.886) and (2.000 <= bcd <= 5.000) and (1.382 <= xad <= 5.000):
        if bull: found.append(("🟢 Bull Crab", "BUY"))
        if bear: found.append(("🔴 Bear Crab", "SELL"))

    # --- Anti Crab ---
    if (0.250 <= xab <= 0.500) and (1.130 <= abc <= 2.618) and (1.618 <= bcd <= 2.618) and (0.500 <= xad <= 0.750):
        if bull: found.append(("🟢 Bull Anti Crab", "BUY"))
        if bear: found.append(("🔴 Bear Anti Crab", "SELL"))

    # --- Shark ---
    if (0.500 <= xab <= 0.875) and (1.130 <= abc <= 1.618) and (1.270 <= bcd <= 2.240) and (0.886 <= xad <= 1.130):
        if bull: found.append(("🟢 Bull Shark", "BUY"))
        if bear: found.append(("🔴 Bear Shark", "SELL"))

    # --- Anti Shark ---
    if (0.382 <= xab <= 0.875) and (0.500 <= abc <= 1.000) and (1.250 <= bcd <= 2.618) and (0.500 <= xad <= 1.250):
        if bull: found.append(("🟢 Bull Anti Shark", "BUY"))
        if bear: found.append(("🔴 Bear Anti Shark", "SELL"))

    # --- 5-O ---
    if (1.13 <= xab <= 1.618) and (1.618 <= abc <= 2.24) and (0.5 <= bcd <= 0.625) and (0.0 <= xad <= 0.236):
        if bull: found.append(("🟢 Bull 5-O", "BUY"))
        if bear: found.append(("🔴 Bear 5-O", "SELL"))

    # --- Wolf Wave ---
    if (1.27 <= xab <= 1.618) and (0 <= abc <= 5) and (1.27 <= bcd <= 1.618) and (0 <= xad <= 5):
        if bull: found.append(("🟢 Bull Wolf Wave", "BUY"))
        if bear: found.append(("🔴 Bear Wolf Wave", "SELL"))

    # --- Head and Shoulders ---
    if (2.0 <= xab <= 10) and (0.90 <= abc <= 1.1) and (0.236 <= bcd <= 0.88) and (0.90 <= xad <= 1.1):
        if bull: found.append(("🟢 Bull Head & Shoulders", "BUY"))
        if bear: found.append(("🔴 Bear Head & Shoulders", "SELL"))

    # --- Contracting Triangle ---
    if (0.382 <= xab <= 0.618) and (0.382 <= abc <= 0.618) and (0.382 <= bcd <= 0.618) and (0.236 <= xad <= 0.764):
        if bull: found.append(("🟢 Bull Contracting Triangle", "BUY"))
        if bear: found.append(("🔴 Bear Contracting Triangle", "SELL"))

    # --- Expanding Triangle ---
    if (1.236 <= xab <= 1.618) and (1.000 <= abc <= 1.618) and (1.236 <= bcd <= 2.000) and (2.000 <= xad <= 2.236):
        if bull: found.append(("🟢 Bull Expanding Triangle", "BUY"))
        if bear: found.append(("🔴 Bear Expanding Triangle", "SELL"))

    return found


def run():
    print(f"ZigZag scanner indul: {datetime.datetime.now()}")

    candles = get_btc_candles()
    print(f"{len(candles)} gyertya letoltve")

    pivots = compute_zigzag(candles)
    print(f"{len(pivots)} ZigZag pont talalt")

    if len(pivots) < 5:
        print("Nincs eleg ZigZag pont, kilepes")
        return

    x = pivots[-5][1]
    a = pivots[-4][1]
    b = pivots[-3][1]
    c = pivots[-2][1]
    d = pivots[-1][1]

    current_price = candles[-1]["close"]
    current_time  = candles[-1]["time"].strftime("%Y-%m-%d %H:%M")

    print(f"XABCD: x={x:.2f} a={a:.2f} b={b:.2f} c={c:.2f} d={d:.2f}")
    print(f"Jelenlegi ar: {current_price:.2f}")

    patterns = detect_all_patterns(x, a, b, c, d)

    if not patterns:
        print("Nincs minta - nincs uzenet")
        return

    ew = fib_level(c, d, FIB_EW)
    tp = fib_level(c, d, FIB_TP)
    sl = fib_level(c, d, FIB_SL)

    # BUY jelek: bull minta es ar <= entry window
    buy_patterns = [p[0] for p in patterns if p[1] == "BUY" and current_price <= ew]
    # SELL jelek: bear minta es ar >= entry window
    sell_patterns = [p[0] for p in patterns if p[1] == "SELL" and current_price >= ew]

    if not buy_patterns and not sell_patterns:
        all_patterns = [p[0] for p in patterns]
        print(f"Minta talalt ({', '.join(all_patterns)}) de ar nincs EW-ban (EW={ew:.2f}, ar={current_price:.2f})")
        return

    signal_patterns = buy_patterns if buy_patterns else sell_patterns
    signal = "BUY" if buy_patterns else "SELL"
    direction = "📈 LONG (BUY)" if signal == "BUY" else "📉 SHORT (SELL)"

    message = f"""⚡ <b>BTCUSD JEL - {direction}</b>

🕐 Ido: {current_time} (30m)
💰 Jelenlegi ar: <b>${current_price:,.2f}</b>

📐 Mintak:
{chr(10).join(signal_patterns)}

🎯 Szintek:
• Entry Window: ${ew:,.2f}
• Take Profit:  ${tp:,.2f}
• Stop Loss:    ${sl:,.2f}

📊 XABCD:
X={x:.2f} → A={a:.2f} → B={b:.2f} → C={c:.2f} → D={d:.2f}

⚠️ Csak tajekoztatas - kereskedj felelos!"""

    send_telegram(message)
    print(f"Jel kuldve: {signal} - {signal_patterns}")


if __name__ == "__main__":
    run()
