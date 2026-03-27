"""
cTrader Open API - WebSocket + JSON alapú teszt
Demo szerver: demo.ctraderapi.com:5035
"""

import os
import sys
import json
import time
import threading
import websocket

CTRADER_CLIENT_ID     = os.environ.get("CTRADER_CLIENT_ID", "")
CTRADER_CLIENT_SECRET = os.environ.get("CTRADER_CLIENT_SECRET", "")
CTRADER_ACCOUNT_ID    = int(os.environ.get("CTRADER_ACCOUNT_ID", "0"))
CTRADER_ACCESS_TOKEN  = os.environ.get("CTRADER_ACCESS_TOKEN", "")

DEMO_URL = "wss://demo.ctraderapi.com:5035"

# Állapot
state = {
    "app_authed": False,
    "acc_authed": False,
    "order_sent": False,
    "done": False,
    "error": None
}

def send(ws, payload_type, payload):
    msg = json.dumps({
        "clientMsgId": f"msg_{payload_type}",
        "payloadType": payload_type,
        "payload": payload
    })
    print(f"  → Küldés [{payload_type}]: {msg[:120]}")
    ws.send(msg)

def on_open(ws):
    print("\n[1] WebSocket kapcsolat megnyitva")
    print("[2] App autentikáció...")
    send(ws, 2100, {
        "clientId": CTRADER_CLIENT_ID,
        "clientSecret": CTRADER_CLIENT_SECRET
    })

def on_message(ws, message):
    data = json.loads(message)
    ptype = data.get("payloadType")
    payload = data.get("payload", {})

    print(f"  ← Válasz [{ptype}]: {str(payload)[:150]}")

    # App auth válasz
    if ptype == 2101:
        print("  ✅ App autentikálva")
        state["app_authed"] = True
        print("[3] Account autentikáció...")
        send(ws, 2102, {
            "accessToken": CTRADER_ACCESS_TOKEN,
            "ctidTraderAccountId": CTRADER_ACCOUNT_ID
        })

    # Account auth válasz
    elif ptype == 2103:
        print("  ✅ Account autentikálva")
        state["acc_authed"] = True
        print("[4] Teszt BUY order küldése (0.01 lot BTCUSD)...")
        send(ws, 2106, {
            "ctidTraderAccountId": CTRADER_ACCOUNT_ID,
            "symbolName": "BTCUSD",
            "orderType": "MARKET",
            "tradeSide": "BUY",
            "volume": 1000,  # 0.01 lot = 1000 unit
            "label": "ZZtest"
        })
        state["order_sent"] = True

    # Execution event (order eredmény)
    elif ptype == 2126:
        print("  ✅ Order végrehajtva!")
        pos_id = payload.get("position", {}).get("positionId")
        if pos_id:
            print(f"[5] Pozíció zárása: {pos_id}")
            time.sleep(2)
            send(ws, 2116, {
                "ctidTraderAccountId": CTRADER_ACCOUNT_ID,
                "positionId": pos_id,
                "volume": 1000
            })
        else:
            state["done"] = True

    # Pozíció zárva
    elif ptype == 2126 and state["order_sent"]:
        print("  ✅ Pozíció zárva")
        state["done"] = True

    # Hiba
    elif ptype == 2142 or ptype == 50:
        err = payload.get("description") or payload.get("errorCode") or str(payload)
        print(f"  ❌ API hiba: {err}")
        state["error"] = err
        state["done"] = True

def on_error(ws, error):
    print(f"\n❌ WebSocket hiba: {error}")
    state["error"] = str(error)
    state["done"] = True

def on_close(ws, code, msg):
    print(f"\nWebSocket lezárva: {code} {msg}")
    state["done"] = True

def heartbeat(ws):
    """Heartbeat küldése 10 másodpercenként"""
    while not state["done"]:
        time.sleep(10)
        if not state["done"]:
            try:
                send(ws, 51, {})  # ProtoHeartbeatEvent
            except:
                break

def main():
    print("=" * 50)
    print("cTrader WebSocket kapcsolat teszt")
    print("=" * 50)

    # Secrets check
    print("\n[0] Secrets ellenőrzés:")
    print(f"  CLIENT_ID:     {'✅' if CTRADER_CLIENT_ID else '❌ HIÁNYZIK'}")
    print(f"  CLIENT_SECRET: {'✅' if CTRADER_CLIENT_SECRET else '❌ HIÁNYZIK'}")
    print(f"  ACCOUNT_ID:    {'✅' if CTRADER_ACCOUNT_ID else '❌ HIÁNYZIK'}")
    print(f"  ACCESS_TOKEN:  {'✅' if CTRADER_ACCESS_TOKEN else '❌ HIÁNYZIK'}")

    if not all([CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET, CTRADER_ACCOUNT_ID, CTRADER_ACCESS_TOKEN]):
        print("\n❌ Hiányzó secrets!")
        sys.exit(1)

    print(f"\nCsatlakozás: {DEMO_URL}")

    ws = websocket.WebSocketApp(
        DEMO_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    # Heartbeat thread
    hb = threading.Thread(target=heartbeat, args=(ws,), daemon=True)
    hb.start()

    # Timeout thread
    def timeout():
        time.sleep(30)
        if not state["done"]:
            print("\n⏰ Timeout - 30 másodperc eltelt")
            state["done"] = True
            ws.close()

    t = threading.Thread(target=timeout, daemon=True)
    t.start()

    ws.run_forever(sslopt={"cert_reqs": 0})

    print("\n" + "=" * 50)
    if state["error"]:
        print(f"❌ Teszt sikertelen: {state['error']}")
    elif state["acc_authed"] and state["order_sent"]:
        print("✅ Teszt SIKERES - API kapcsolat és order működik!")
    elif state["app_authed"]:
        print("⚠️ App auth OK, de account auth vagy order sikertelen")
    else:
        print("❌ Kapcsolat nem sikerült")
    print("=" * 50)

if __name__ == "__main__":
    main()
