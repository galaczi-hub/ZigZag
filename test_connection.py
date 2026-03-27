"""
cTrader kapcsolat teszt - minimális pozíció nyitás/zárás
Manuálisan indítható workflow_dispatch-csel
"""

import os
import sys
import requests

CTRADER_CLIENT_ID     = os.environ.get("CTRADER_CLIENT_ID", "")
CTRADER_CLIENT_SECRET = os.environ.get("CTRADER_CLIENT_SECRET", "")
CTRADER_ACCOUNT_ID    = os.environ.get("CTRADER_ACCOUNT_ID", "")
CTRADER_ACCESS_TOKEN  = os.environ.get("CTRADER_ACCESS_TOKEN", "")

print("=" * 50)
print("cTrader kapcsolat teszt")
print("=" * 50)

# 1. Secrets ellenőrzés
print("\n[1] Secrets ellenőrzés:")
print(f"  CLIENT_ID:     {'✅ megvan' if CTRADER_CLIENT_ID else '❌ HIÁNYZIK'}")
print(f"  CLIENT_SECRET: {'✅ megvan' if CTRADER_CLIENT_SECRET else '❌ HIÁNYZIK'}")
print(f"  ACCOUNT_ID:    {'✅ megvan' if CTRADER_ACCOUNT_ID else '❌ HIÁNYZIK'}")
print(f"  ACCESS_TOKEN:  {'✅ megvan' if CTRADER_ACCESS_TOKEN else '❌ HIÁNYZIK'}")

if not all([CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET, CTRADER_ACCOUNT_ID, CTRADER_ACCESS_TOKEN]):
    print("\n❌ Hiányzó secrets! Állítsd be a GitHub Secrets-ben.")
    sys.exit(1)

# 2. ctrader-sdk import teszt
print("\n[2] ctrader-sdk import:")
try:
    from ctrader_sdk import CTraderBot
    print("  ✅ ctrader-sdk importálva")
except ImportError as e:
    print(f"  ❌ Import hiba: {e}")
    print("  → Ellenőrizd hogy a workflow-ban benne van-e: pip install ctrader-sdk")
    sys.exit(1)

# 3. Bot inicializálás
print("\n[3] Bot inicializálás:")
try:
    bot = CTraderBot(
        CTRADER_CLIENT_ID,
        CTRADER_CLIENT_SECRET,
        CTRADER_ACCESS_TOKEN,
        int(CTRADER_ACCOUNT_ID)
    )
    print("  ✅ Bot létrehozva")
except Exception as e:
    print(f"  ❌ Bot init hiba: {e}")
    sys.exit(1)

# 4. Pozíciók lekérése
print("\n[4] Nyitott pozíciók lekérése:")
try:
    positions = bot.get_positions()
    print(f"  ✅ Válasz megérkezett: {len(positions) if positions else 0} nyitott pozíció")
    if positions:
        for p in positions:
            print(f"     → {p}")
except Exception as e:
    print(f"  ❌ Pozíció lekérés hiba: {e}")

# 5. Teszt order - minimális méret
print("\n[5] Teszt BUY order (0.01 lot BTCUSD):")
try:
    result = bot.place_order(
        symbol="BTCUSD",
        volume=1000,        # 0.01 lot = 1000 unit cTrader-ben
        direction="BUY",
        order_type="MARKET"
    )
    print(f"  ✅ Order leadva: {result}")

    # 6. Azonnal zárjuk is be
    print("\n[6] Teszt pozíció zárása:")
    positions = bot.get_positions()
    if positions:
        for p in positions:
            pos_id = p.get("positionId") or p.get("id")
            if pos_id:
                close_result = bot.close_position(pos_id)
                print(f"  ✅ Pozíció zárva: {pos_id} → {close_result}")
    else:
        print("  ℹ️ Nincs pozíció amit zárni kellene")

except Exception as e:
    print(f"  ❌ Order hiba: {e}")

print("\n" + "=" * 50)
print("Teszt befejezve")
print("=" * 50)
