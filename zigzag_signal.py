#!/usr/bin/env python3
"""
ZigZag PA Trader - Pine Script logika Python-ban
GitHub Actions futtatja 5 percenként
"""

import os
import sys
import json
import time
import math
import requests
import ccxt
from datetime import datetime, timezone

# ============================================================
# KONFIGURÁCIÓ - GitHub Secrets-ből
# ============================================================
CTRADER_CLIENT_ID     = os.environ.get("CTRADER_CLIENT_ID", "")
CTRADER_CLIENT_SECRET = os.environ.get("CTRADER_CLIENT_SECRET", "")
CTRADER_ACCOUNT_ID    = os.environ.get("CTRADER_ACCOUNT_ID", "")  # demo account ID
CTRADER_ACCESS_TOKEN  = os.environ.get("CTRADER_ACCESS_TOKEN", "")
TELEGRAM_TOKEN        = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID      = os.environ.get("TELEGRAM_CHAT_ID", "")

# Trading paraméterek
SYMBOL        = "BTCUSD"
TIMEFRAME     = "5m"
LOT_SIZE      = 0.01
FIB_EW        = 0.236
FIB_TP        = 0.618
FIB_SL        = -0.236
MIN_MOVE_PCT  = 0.2   # ZigZag minimum mozgás % (0.2 = finomabb, több jel)
CANDLES_LIMIT = 500   # hány gyertyát kérünk le

# cTrader API
CTRADER_API   = "https://api.tradelocker.com"  # vagy Pepperstone endpoint

# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram hiba: {e}")

# ============================================================
# ADATOK LETÖLTÉSE - CCXT + Bitstamp (mint a TV)
# ============================================================
def get_candles():
    exchange = ccxt.bitstamp()
    ohlcv = exchange.fetch_ohlcv("BTC/USD", TIMEFRAME, limit=CANDLES_LIMIT)
    # [timestamp, open, high, low, close, volume]
    candles = [{
        "ts":    c[0],
        "open":  c[1],
        "high":  c[2],
        "low":   c[3],
        "close": c[4],
        "vol":   c[5]
    } for c in ohlcv]
    print(f"Letöltve: {len(candles)} gyertya, utolso zárás: {candles[-1]['close']:.2f}")
    return candles

# ============================================================
# ZIGZAG - ZigZagTV_v2 logika Python-ban
# TV Pine Script: isUp = close >= open, irányváltás + min mozgás
# ============================================================
def build_zigzag(candles):
    zz = []
    direction = 0
    last_zz_price = 0

    for i in range(1, len(candles) - 1):  # utolso nyitott kihagyva
        c = candles[i]
        p = candles[i-1]

        is_up    = c["close"] >= c["open"]
        is_down  = c["close"] <= c["open"]
        prev_up  = p["close"] >= p["open"]
        prev_down= p["close"] <= p["open"]

        if prev_up and is_down and direction != -1:
            price = max(c["high"], p["high"])
            min_move = last_zz_price * MIN_MOVE_PCT / 100.0 if last_zz_price > 0 else 0
            if last_zz_price == 0 or abs(price - last_zz_price) >= min_move:
                add_zz_point(zz, price, True)
                last_zz_price = price
                direction = -1

        elif prev_down and is_up and direction != 1:
            price = min(c["low"], p["low"])
            min_move = last_zz_price * MIN_MOVE_PCT / 100.0 if last_zz_price > 0 else 0
            if last_zz_price == 0 or abs(price - last_zz_price) >= min_move:
                add_zz_point(zz, price, False)
                last_zz_price = price
                direction = 1

    print(f"ZigZag pontok: {len(zz)}")
    return zz

def add_zz_point(zz, price, is_high):
    if zz and zz[-1]["is_high"] == is_high:
        if (is_high and price > zz[-1]["price"]) or (not is_high and price < zz[-1]["price"]):
            zz[-1] = {"price": price, "is_high": is_high}
    else:
        zz.append({"price": price, "is_high": is_high})

# ============================================================
# FIBONACCI ARÁNYOK - Pine Script 1:1
# ============================================================
def calc_ratios(x, a, b, c, d):
    if abs(x-a) < 0.001 or abs(a-b) < 0.001 or abs(b-c) < 0.001:
        return None
    return {
        "xab": abs(b-a) / abs(x-a),
        "xad": abs(a-d) / abs(x-a),
        "abc": abs(b-c) / abs(a-b),
        "bcd": abs(c-d) / abs(b-c)
    }

def fib_level(d, c, rate):
    r = abs(d - c)
    return (d - r * rate) if d > c else (d + r * rate)

# ============================================================
# MINTA FELISMERÉS - Pine Script 1:1
# ============================================================
def is_bull(d, c): return d < c
def is_bear(d, c): return d > c

def check_patterns(x, a, b, c, d):
    r = calc_ratios(x, a, b, c, d)
    if not r:
        return None, None

    xab, xad, abc, bcd = r["xab"], r["xad"], r["abc"], r["bcd"]
    bull = is_bull(d, c)
    bear = is_bear(d, c)

    patterns = {
        "ABCD":          lambda: (0.382<=abc<=0.886) and (1.13<=bcd<=2.618),
        "Bat":           lambda: (0.382<=xab<=0.500) and (0.382<=abc<=0.886) and (1.618<=bcd<=2.618) and xad<=0.618,
        "AltBat":        lambda: (xab<=0.382) and (0.382<=abc<=0.886) and (2.0<=bcd<=3.618) and xad<=1.13,
        "AntiBat":       lambda: (0.500<=xab<=0.886) and (1.000<=abc<=2.618) and (1.618<=bcd<=2.618) and (0.886<=xad<=1.000),
        "Butterfly":     lambda: (xab<=0.786) and (0.382<=abc<=0.886) and (1.618<=bcd<=2.618) and (1.27<=xad<=1.618),
        "AntiButterfly": lambda: (0.236<=xab<=0.886) and (1.130<=abc<=2.618) and (1.000<=bcd<=1.382) and (0.500<=xad<=0.886),
        "Gartley":       lambda: (0.500<=xab<=0.618) and (0.382<=abc<=0.886) and (1.13<=bcd<=2.618) and (0.75<=xad<=0.875),
        "AntiGartley":   lambda: (0.500<=xab<=0.886) and (1.000<=abc<=2.618) and (1.500<=bcd<=5.000) and (1.000<=xad<=5.000),
        "Crab":          lambda: (0.500<=xab<=0.875) and (0.382<=abc<=0.886) and (2.000<=bcd<=5.000) and (1.382<=xad<=5.000),
        "AntiCrab":      lambda: (0.250<=xab<=0.500) and (1.130<=abc<=2.618) and (1.618<=bcd<=2.618) and (0.500<=xad<=0.750),
        "Shark":         lambda: (0.500<=xab<=0.875) and (1.130<=abc<=1.618) and (1.270<=bcd<=2.240) and (0.886<=xad<=1.130),
        "AntiShark":     lambda: (0.382<=xab<=0.875) and (0.500<=abc<=1.000) and (1.250<=bcd<=2.618) and (0.500<=xad<=1.250),
        "5-O":           lambda: (1.13<=xab<=1.618) and (1.618<=abc<=2.24) and (0.5<=bcd<=0.625) and (0.0<=xad<=0.236),
        "Wolf":          lambda: (1.27<=xab<=1.618) and (1.27<=bcd<=1.618),
        "HnS":           lambda: (2.0<=xab<=10) and (0.90<=abc<=1.1) and (0.236<=bcd<=0.88) and (0.90<=xad<=1.1),
        "ConTria":       lambda: (0.382<=xab<=0.618) and (0.382<=abc<=0.618) and (0.382<=bcd<=0.618) and (0.236<=xad<=0.764),
        "ExpTria":       lambda: (1.236<=xab<=1.618) and (1.000<=abc<=1.618) and (1.236<=bcd<=2.000) and (2.000<=xad<=2.236),
    }

    for name, check in patterns.items():
        if check():
            if bull: return "BUY", name
            if bear: return "SELL", name

    return None, None

# ============================================================
# CTRADER API - Pepperstone demo
# ============================================================
def get_ctrader_token():
    """Access token visszaadasa - kozvetlenul hasznaljuk"""
    if CTRADER_ACCESS_TOKEN:
        print("Access token hasznalata")
        return CTRADER_ACCESS_TOKEN
    print("HIBA: CTRADER_ACCESS_TOKEN hiányzik!")
    return ""

def get_open_positions(token):
    """Nyitott pozíciók lekérése"""
    try:
        resp = requests.get(
            f"https://connect.spotware.com/apps/v2/webapi/accounts/{CTRADER_ACCOUNT_ID}/positions",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print(f"Poziciok: {resp.status_code}")
        return resp.json().get("position", []) if resp.status_code == 200 else []
    except Exception as e:
        print(f"Pozíció lekérés hiba: {e}")
        return []

def open_position(token, direction, volume, label):
    """Pozíció nyitás"""
    try:
        side = "BUY" if direction == "BUY" else "SELL"
        resp = requests.post(
            f"https://connect.spotware.com/apps/v2/webapi/accounts/{CTRADER_ACCOUNT_ID}/orders",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "symbolName": SYMBOL,
                "orderType": "MARKET",
                "tradeSide": side,
                "volume": int(volume * 1000000),  # cTrader: 1 lot BTC = 1,000,000 units
                "label": label
            },
            timeout=10
        )
        return resp.json()
    except Exception as e:
        print(f"Pozíció nyitás hiba: {e}")
        return None

def close_position(token, position_id):
    """Pozíció zárás"""
    try:
        resp = requests.delete(
            f"https://connect.spotware.com/apps/v2/webapi/accounts/{CTRADER_ACCOUNT_ID}/positions/{position_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        return resp.json()
    except Exception as e:
        print(f"Pozíció zárás hiba: {e}")
        return None

# ============================================================
# FŐ LOGIKA
# ============================================================
def main():
    print(f"\n{'='*50}")
    print(f"ZigZag PA Trader - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}")

    # 1. Gyertyaadatok letöltése
    try:
        candles = get_candles()
    except Exception as e:
        print(f"CCXT hiba: {e}")
        sys.exit(1)

    # 2. ZigZag számítás
    zz = build_zigzag(candles)
    if len(zz) < 5:
        print("Nincs elég ZigZag pont")
        return

    # 3. XABCD pontok - Pine Script: valuewhen(sz,sz,4..0)
    d = zz[-1]["price"]
    c = zz[-2]["price"]
    b = zz[-3]["price"]
    a = zz[-4]["price"]
    x = zz[-5]["price"]

    print(f"X={x:.0f} A={a:.0f} B={b:.0f} C={c:.0f} D={d:.0f}")

    # 4. Fibonacci szintek - Pine Script 1:1
    ew = fib_level(d, c, FIB_EW)
    tp = fib_level(d, c, FIB_TP)
    sl = fib_level(d, c, FIB_SL)

    # 5. Minta felismerés
    signal, pattern = check_patterns(x, a, b, c, d)
    close_price = candles[-2]["close"]  # utolso lezart gyertya

    # Ratios debug
    r = calc_ratios(x, a, b, c, d)
    if r:
        print(f"XAB={r['xab']:.3f} ABC={r['abc']:.3f} BCD={r['bcd']:.3f} XAD={r['xad']:.3f}")
    print(f"D>C: {d>c} (bear) D<C: {d<c} (bull)")
    print(f"Minta: {pattern} | Jel: {signal}")
    print(f"EW={ew:.2f} TP={tp:.2f} SL={sl:.2f} | close={close_price:.2f}")

    # 6. Belépési feltétel - Pine Script 1:1
    # target01_buy_entry = (buy_patterns) and close <= f_last_fib(ew_rate)
    # target01_sel_entry = (sel_patterns) and close >= f_last_fib(ew_rate)
    entry_buy  = signal == "BUY"  and close_price <= ew
    entry_sell = signal == "SELL" and close_price >= ew

    print(f"EntryBuy={entry_buy} EntrySell={entry_sell}")

    if not entry_buy and not entry_sell:
        print("Nincs belépési jel")
        return

    # 7. cTrader API - pozíció kezelés
    if not CTRADER_CLIENT_ID:
        print("cTrader credentials hiányoznak - csak Telegram jel küldés")
        direction = "BUY" if entry_buy else "SELL"
        msg = f"⚡ <b>{SYMBOL} {direction}</b>\n📊 {pattern}\n💰 {close_price:.2f}\n🎯 TP={tp:.2f} 🛑 SL={sl:.2f}"
        send_telegram(msg)
        return

    token = get_ctrader_token()
    if not token:
        print("Token hiba")
        return

    positions = get_open_positions(token)
    our_pos = [p for p in positions if p.get("label") == "ZZpy"]

    # Pozíció zárása ha ellentétes irány
    for pos in our_pos:
        pos_side = pos.get("tradeSide", "")
        if (entry_buy and pos_side == "SELL") or (entry_sell and pos_side == "BUY"):
            result = close_position(token, pos["positionId"])
            print(f"Pozíció zárva: {pos['positionId']}")
            send_telegram(f"🔴 <b>{SYMBOL} ZARVA</b>\nEllentétes jel")

    # Új pozíció nyitása ha nincs nyitott
    our_pos = [p for p in get_open_positions(token) if p.get("label") == "ZZpy"]
    if not our_pos:
        direction = "BUY" if entry_buy else "SELL"
        result = open_position(token, direction, LOT_SIZE, "ZZpy")
        if result:
            print(f"Pozíció nyitva: {direction} @ {close_price:.2f}")
            msg = f"⚡ <b>{SYMBOL} {direction}</b>\n📊 {pattern}\n💰 {close_price:.2f}\n🎯 TP={tp:.2f} 🛑 SL={sl:.2f}"
            send_telegram(msg)
        else:
            print("Pozíció nyitás sikertelen")
    else:
        print(f"Már van nyitott pozíció: {len(our_pos)} db")

if __name__ == "__main__":
    main()
