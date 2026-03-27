#!/usr/bin/env python3
"""
ZigZag PA Trader - Pine Script logika Python-ban
GitHub Actions futtatja 5 percenként
ctrader-sdk alapú order kezelés
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
CTRADER_ACCOUNT_ID    = os.environ.get("CTRADER_ACCOUNT_ID", "")
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
MIN_MOVE_PCT  = 0.2
CANDLES_LIMIT = 500

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
# ADATOK LETÖLTÉSE - CCXT + Bitstamp
# ============================================================
def get_candles():
    exchange = ccxt.bitstamp()
    ohlcv = exchange.fetch_ohlcv("BTC/USD", TIMEFRAME, limit=CANDLES_LIMIT)
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
# ZIGZAG
# ============================================================
def build_zigzag(candles):
    zz = []
    direction = 0
    last_zz_price = 0

    for i in range(1, len(candles) - 1):
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
# FIBONACCI
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
# MINTA FELISMERÉS
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
# CTRADER-SDK ALAPÚ TRADING
# ============================================================
def get_bot():
    """CTraderBot példány létrehozása"""
    try:
        from ctrader_sdk import CTraderBot
        bot = CTraderBot(
            CTRADER_CLIENT_ID,
            CTRADER_CLIENT_SECRET,
            CTRADER_ACCESS_TOKEN,
            int(CTRADER_ACCOUNT_ID)
        )
        print("cTrader bot inicializálva")
        return bot
    except Exception as e:
        print(f"Bot init hiba: {e}")
        return None

def get_open_positions(bot):
    """Nyitott pozíciók lekérése"""
    try:
        positions = bot.get_positions()
        print(f"Poziciok: {len(positions) if positions else 0} db")
        return positions if positions else []
    except Exception as e:
        print(f"Pozíció lekérés hiba: {e}")
        return []

def open_position(bot, direction, volume, tp, sl):
    """Pozíció nyitás TP és SL szintekkel"""
    try:
        # ctrader-sdk: volume = lots * 100 (BTCUSD esetén 1 lot = 1 BTC)
        # 0.01 lot = 1000 unit (cTrader egység)
        result = bot.place_order(
            symbol=SYMBOL,
            volume=int(volume * 100000),  # 0.01 lot → 1000 unit
            direction=direction,
            order_type="MARKET",
            take_profit=round(tp, 2),
            stop_loss=round(sl, 2)
        )
        print(f"Order eredmény: {result}")
        return result
    except Exception as e:
        print(f"Pozíció nyitás hiba: {e}")
        return None

def close_all_positions(bot, positions):
    """Összes pozíció zárása"""
    for pos in positions:
        try:
            pos_id = pos.get("positionId") or pos.get("id")
            if pos_id:
                bot.close_position(pos_id)
                print(f"Pozíció zárva: {pos_id}")
        except Exception as e:
            print(f"Zárás hiba: {e}")

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

    # 3. XABCD pontok
    d = zz[-1]["price"]
    c = zz[-2]["price"]
    b = zz[-3]["price"]
    a = zz[-4]["price"]
    x = zz[-5]["price"]

    print(f"X={x:.0f} A={a:.0f} B={b:.0f} C={c:.0f} D={d:.0f}")

    # 4. Fibonacci szintek
    ew = fib_level(d, c, FIB_EW)
    tp = fib_level(d, c, FIB_TP)
    sl = fib_level(d, c, FIB_SL)

    # 5. Minta felismerés
    signal, pattern = check_patterns(x, a, b, c, d)
    close_price = candles[-2]["close"]

    # Debug
    r = calc_ratios(x, a, b, c, d)
    if r:
        print(f"XAB={r['xab']:.3f} ABC={r['abc']:.3f} BCD={r['bcd']:.3f} XAD={r['xad']:.3f}")
    print(f"D>C: {d>c} (bear) D<C: {d<c} (bull)")
    print(f"Minta: {pattern} | Jel: {signal}")
    print(f"EW={ew:.2f} TP={tp:.2f} SL={sl:.2f} | close={close_price:.2f}")

    # 6. Belépési feltétel
    entry_buy  = signal == "BUY"  and close_price <= ew
    entry_sell = signal == "SELL" and close_price >= ew

    print(f"EntryBuy={entry_buy} EntrySell={entry_sell}")

    if not entry_buy and not entry_sell:
        print("Nincs belépési jel")
        return

    direction = "BUY" if entry_buy else "SELL"

    # 7. Csak Telegram ha nincs cTrader konfig
    if not CTRADER_CLIENT_ID or not CTRADER_ACCESS_TOKEN:
        print("cTrader credentials hiányoznak - csak Telegram jel")
        msg = f"⚡ <b>{SYMBOL} {direction}</b>\n📊 {pattern}\n💰 {close_price:.2f}\n🎯 TP={tp:.2f} 🛑 SL={sl:.2f}"
        send_telegram(msg)
        return

    # 8. cTrader trading
    bot = get_bot()
    if not bot:
        print("Bot inicializálás sikertelen")
        return

    positions = get_open_positions(bot)
    our_pos = [p for p in positions if p.get("label") == "ZZpy"]

    # Ellentétes pozíció zárása
    for pos in our_pos:
        pos_side = pos.get("tradeSide", "").upper()
        if (entry_buy and pos_side == "SELL") or (entry_sell and pos_side == "BUY"):
            close_all_positions(bot, [pos])
            send_telegram(f"🔴 <b>{SYMBOL} ZARVA</b>\nEllentétes jel")

    # Frissített pozíciólist
    positions = get_open_positions(bot)
    our_pos = [p for p in positions if p.get("label") == "ZZpy"]

    # Új pozíció nyitása ha nincs
    if not our_pos:
        result = open_position(bot, direction, LOT_SIZE, tp, sl)
        if result:
            print(f"✅ Pozíció nyitva: {direction} @ {close_price:.2f}")
            msg = (
                f"⚡ <b>{SYMBOL} {direction}</b>\n"
                f"📊 Minta: {pattern}\n"
                f"💰 Belépés: {close_price:.2f}\n"
                f"🎯 TP: {tp:.2f}\n"
                f"🛑 SL: {sl:.2f}"
                f" ZigZag-github: {sl:.2f}"
            )
            send_telegram(msg)
        else:
            print("❌ Pozíció nyitás sikertelen")
            send_telegram(f"❌ <b>{SYMBOL} {direction} SIKERTELEN</b>\n{pattern} @ {close_price:.2f}")
    else:
        print(f"ℹ️ Már van nyitott pozíció: {len(our_pos)} db")

if __name__ == "__main__":
    main()
