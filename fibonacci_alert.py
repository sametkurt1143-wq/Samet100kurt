"""
BIST RALLI AVCISI + DONUS NOKTASI + TELEGRAM BOTU v3.1
=========================================================
v3.1 (v3.0 uzerine duzeltmeler):
1) KRITIK BUG DUZELTILDI: DONUS NOKTASI mesajinda ATR satirinin
   f-string birlestirmesi yanlis parantezlenmisti. `if atr_pct else ""`
   kosulu, sadece ATR satirina degil, o satira kadarki TUM mesaja
   (baslik, fiyat, trend, destek, direnc, RSI, hacim satirlari dahil)
   uygulaniyordu. atr_pct bos/None/0 oldugunda mesaj SESSIZCE bos
   gidiyor, Telegram'a sadece yarim bir mesaj (Mum + Risk/Odul +
   kriterler) ulasiyordu. ATR satiri artik ayri bir degiskene
   (`atr_line`) alinip mesaja normal sekilde ekleniyor - diger
   satirlar (limit_line, divergence_line, resistance_line) zaten
   bu desende dogru yazilmisti.
2) ANI DUSUS mesajina eksik olan "Yatirim tavsiyesi degildir"
   uyarisi eklendi (diger mesajlarla tutarlilik icin).

v3.0 OZET:
1) DONUS sistemi korunur.
2) RALLI sistemi ayri puanlanir: 0-10.
3) 20/50/100 gunluk zirve kirilimi kontrol edilir.
4) Hacim kirilimi onaylar.
5) RSI + MACD + EMA trendi ralli puanina dahil edilir.
6) RALLI ADAYI / RALLI BASLADI / RALLI GUCLENIYOR ayrimi yapilir.
7) Kirilim sonrasi kirilim seviyesinin altinda kapanis takip edilir.
8) ATR bazli hedef ve stop hesaplanir.
9) Ani dusus ve tavana yaklasma uyarilari korunur.
10) State dosyasi ile ayni alarm tekrar tekrar gonderilmez.

NOT:
Bu arac yatirim tavsiyesi vermez. Teknik gostergeler gelecegi garanti etmez.
"""

import os
import json
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# ==================== KURULUM ====================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "BURAYA_BOT_TOKENINI_YAZ")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "BURAYA_CHAT_ID_YAZ")

TICKERS = [
    "ARCLK.IS", "ULKER.IS", "ASUZU.IS", "GOKNR.IS", "BERA.IS",
    "TTKOM.IS", "TMSN.IS", "ENPRA.IS", "KRPLS.IS", "NETAS.IS",
    "EKIM.IS", "BALSU.IS", "BKRGY.IS", "LILAK.IS", "ZERGY.IS",
    "MERCN.IS", "ENDAE.IS"
]

STATE_FILE = "state.json"

# ==================== DONUS AYARLARI ====================

TREND_LOOKBACK_DAYS = 180
STRENGTH_LOOKBACK_DAYS = 150

TOLERANCE_PCT = 2.0
STRENGTH_TOLERANCE_PCT = 1.5

MIN_TOUCHES_FOR_STRONG = 2

RSI_OVERSOLD = 35
VOLUME_SPIKE_RATIO = 1.3

MIN_SCORE = 4
MIN_SCORE_DOWNTREND = 5

VOLUME_HARD_FILTER_RATIO = 0.7
MIN_STOP_DISTANCE_PCT = 2.5

DIVERGENCE_LOOKBACK_DAYS = 60

# --- YENI: momentum/donus ayrimi icin esikler ---
# Fiyat destege yakin DEGILKEN, hacim/MACD/mum guclu ve RSI yuksekse
# bu bir "destek testi" degil, devam eden bir kirilim/momentum hareketidir.
# Boyle durumlarda hedef, yakin fib direncine degil ATR bazli genisletilmis
# bir hedefe gore hesaplanir - aksi halde MIATK/PETKM gibi hareketler
# yakin dirence cok yakin oldugu icin yapay "ZAYIF" R/O etiketi yiyordu.
MOMENTUM_RSI_MIN = 60
MOMENTUM_ATR_TARGET_MULT = 3.0

# ==================== RALLI AYARLARI ====================

RALLY_MIN_SCORE = 5

RALLY_VOLUME_RATIO = 1.5
RALLY_STRONG_VOLUME_RATIO = 2.0

RALLY_RSI_MIN = 55
RALLY_RSI_MAX = 75

RALLY_OVERBOUGHT_RSI = 80

RALLY_LOOKBACK_20 = 20
RALLY_LOOKBACK_50 = 50
RALLY_LOOKBACK_100 = 100

RALLY_BREAK_TOLERANCE_PCT = 0.20

RALLY_ATR_TARGET_MULT = 3.0
RALLY_ATR_STOP_MULT = 1.5

RALLY_MAX_DISTANCE_FROM_20EMA_PCT = 12.0

# ==================== TAVAN / ANI DUSUS ====================

APPROACHING_LIMIT_PCT = 7.0
DAILY_LIMIT_PCT = 9.9

SHARP_DROP_THRESHOLD_PCT = 3.0
SHARP_DROP_FROM_HIGH_PCT = 4.0

EMA_PERIODS = [20, 50, 200]

# =========================================================


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or "BURAYA" in TELEGRAM_BOT_TOKEN:
        print("[UYARI] TELEGRAM_BOT_TOKEN ayarlanmamis.")
        return

    if not TELEGRAM_CHAT_ID or "BURAYA" in TELEGRAM_CHAT_ID:
        print("[UYARI] TELEGRAM_CHAT_ID ayarlanmamis.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}

    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print(f"[HATA] Telegram gonderim basarisiz: {r.text}")
    except Exception as e:
        print(f"[HATA] Telegram baglanti hatasi: {e}")


# =========================================================
# TEKNIK HESAPLAMALAR
# =========================================================


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_ema(close: pd.Series, period: int):
    return close.ewm(span=period, adjust=False).mean()


def calculate_atr(data: pd.DataFrame, period: int = 14):
    high = data["High"]
    low = data["Low"]
    close = data["Close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def calculate_all_fib_levels(high: float, low: float):
    diff = high - low
    return {
        "0.0 (Tepe)": high,
        "0.236": high - 0.236 * diff,
        "0.382": high - 0.382 * diff,
        "0.5": high - 0.5 * diff,
        "0.618": high - 0.618 * diff,
        "0.786": high - 0.786 * diff,
        "1.0 (Dip)": low,
    }


def find_trend_leg(data: pd.DataFrame, lookback_days: int):
    window = data.tail(lookback_days)
    peak_idx = window["Close"].idxmax()
    peak_price = window["Close"].loc[peak_idx]
    after_peak = window.loc[peak_idx:]
    trough_idx = after_peak["Close"].idxmin()
    trough_price = after_peak["Close"].loc[trough_idx]
    return peak_price, trough_price


def find_next_resistance(all_levels: dict, current_price: float):
    candidates = [(name, price) for name, price in all_levels.items() if price > current_price]
    if not candidates:
        return None, None
    return min(candidates, key=lambda x: x[1])


def find_next_support(all_levels: dict, current_price: float):
    candidates = [(name, price) for name, price in all_levels.items() if price < current_price]
    if not candidates:
        return None, None
    return max(candidates, key=lambda x: x[1])


def support_strength(data: pd.DataFrame, level_price: float, lookback_days: int, tolerance_pct: float):
    window = data.tail(lookback_days)
    diffs_pct = (abs(window["Low"] - level_price) / level_price) * 100
    return int((diffs_pct <= tolerance_pct).sum())


def classify_break_risk(touches: int):
    if touches <= 1:
        return "BELIRSIZ"
    elif touches <= 5:
        return "DUSUK"
    else:
        return "DIKKAT - yorulmus olabilir"


def detailed_candle_info(data: pd.DataFrame):
    last = data.iloc[-1]
    open_p, close_p, high_p, low_p = last["Open"], last["Close"], last["High"], last["Low"]

    body = abs(close_p - open_p)
    lower_wick = min(open_p, close_p) - low_p
    total_range = high_p - low_p if high_p != low_p else 0.0001

    is_bullish = close_p > open_p
    body_ratio = body / total_range
    lower_wick_ratio = lower_wick / body if body > 0 else 0

    if body_ratio < 0.15:
        formation = "Doji (kararsizlik)"
    elif lower_wick_ratio > 2 and body_ratio < 0.4:
        formation = "Hammer (cekic)"
    elif is_bullish and body_ratio > 0.6:
        formation = "Guclu boga mumu"
    elif is_bullish:
        formation = "Boga mumu"
    else:
        formation = "Ayi mumu"

    return {
        "formation": formation,
        "body_ratio": body_ratio,
        "lower_wick_ratio": lower_wick_ratio,
        "is_bullish": is_bullish,
    }


def check_bullish_candle(data: pd.DataFrame):
    return detailed_candle_info(data)["is_bullish"]


def detect_bullish_divergence(data: pd.DataFrame, rsi_series: pd.Series, lookback_days: int):
    window_close = data["Close"].tail(lookback_days)
    window_rsi = rsi_series.tail(lookback_days)

    if len(window_close) < 10:
        return False

    mid = len(window_close) // 2
    first_half = window_close.iloc[:mid]
    second_half = window_close.iloc[mid:]

    if first_half.empty or second_half.empty:
        return False

    low1_idx = first_half.idxmin()
    low2_idx = second_half.idxmin()
    price_low1 = first_half.loc[low1_idx]
    price_low2 = second_half.loc[low2_idx]
    rsi_low1 = window_rsi.loc[low1_idx]
    rsi_low2 = window_rsi.loc[low2_idx]

    if pd.isna(rsi_low1) or pd.isna(rsi_low2):
        return False

    return bool(price_low2 < price_low1 and rsi_low2 > rsi_low1)


def determine_trend(data: pd.DataFrame):
    close = data["Close"]
    current_price = close.iloc[-1]

    ema20 = calculate_ema(close, 20).iloc[-1]
    ema50 = calculate_ema(close, 50).iloc[-1]
    ema200 = calculate_ema(close, 200).iloc[-1] if len(close) >= 200 else np.nan

    above20 = current_price > ema20
    above50 = current_price > ema50
    above200 = current_price > ema200 if not pd.isna(ema200) else False
    ema20_above50 = ema20 > ema50

    bullish_count = sum([above20, above50, above200, ema20_above50])

    if bullish_count >= 3:
        label = "YUKSELIS"
    elif bullish_count <= 1:
        label = "DUSUS"
    else:
        label = "YATAY"

    return {
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "above_20": above20,
        "above_50": above50,
        "above_200": above200,
        "ema20_above_50": ema20_above50,
        "trend_label": label,
    }


# =========================================================
# RALLI MOTORU
# =========================================================


def get_breakout_levels(data: pd.DataFrame):
    result = {}
    for period in [RALLY_LOOKBACK_20, RALLY_LOOKBACK_50, RALLY_LOOKBACK_100]:
        if len(data) <= period:
            continue
        previous_data = data.iloc[-(period + 1):-1]
        level = previous_data["High"].max()
        result[f"{period} Gunluk Zirve"] = float(level)
    return result


def detect_breakout(data: pd.DataFrame, current_price: float):
    levels = get_breakout_levels(data)
    if len(data) < 3:
        return None

    previous_close = data["Close"].iloc[-2]
    broken = []

    for name, level in levels.items():
        tolerance = level * (RALLY_BREAK_TOLERANCE_PCT / 100)
        if previous_close <= level and current_price > level + tolerance:
            broken.append((name, level))

    if not broken:
        return None

    broken.sort(key=lambda x: x[1], reverse=True)
    return broken[0]


def calculate_rally_score(data: pd.DataFrame, trend: dict, rsi: float, macd_bullish: bool,
                           volume_ratio: float, candle_info: dict, current_price: float):
    score = 0
    criteria = {}

    levels = get_breakout_levels(data)

    breakout_20 = False
    breakout_50 = False
    breakout_100 = False

    for name, level in levels.items():
        if current_price > level:
            if "20 Gunluk" in name:
                breakout_20 = True
            elif "50 Gunluk" in name:
                breakout_50 = True
            elif "100 Gunluk" in name:
                breakout_100 = True

    if breakout_20:
        score += 2
        criteria["20 gunluk zirve kirildi"] = True
    else:
        criteria["20 gunluk zirve kirildi"] = False

    if breakout_50:
        score += 2
        criteria["50 gunluk zirve kirildi"] = True
    else:
        criteria["50 gunluk zirve kirildi"] = False

    if breakout_100:
        score += 1
        criteria["100 gunluk zirve kirildi"] = True
    else:
        criteria["100 gunluk zirve kirildi"] = False

    if volume_ratio >= RALLY_STRONG_VOLUME_RATIO:
        score += 2
        criteria["Hacim patlamasi"] = True
    elif volume_ratio >= RALLY_VOLUME_RATIO:
        score += 1
        criteria["Hacim artisi"] = True
    else:
        criteria["Hacim onayi"] = False

    if not pd.isna(rsi) and RALLY_RSI_MIN <= rsi <= RALLY_RSI_MAX:
        score += 1
        criteria["RSI saglikli momentum"] = True
    else:
        criteria["RSI saglikli momentum"] = False

    if not pd.isna(rsi) and rsi >= RALLY_OVERBOUGHT_RSI:
        score -= 2
        criteria["RSI asiri yuksek"] = False

    if macd_bullish:
        score += 1
        criteria["MACD pozitif"] = True
    else:
        criteria["MACD pozitif"] = False

    if trend["trend_label"] == "YUKSELIS":
        score += 1
        criteria["Trend yukselis"] = True
    else:
        criteria["Trend yukselis"] = False

    if trend["ema20_above_50"]:
        score += 1
        criteria["EMA20 > EMA50"] = True
    else:
        criteria["EMA20 > EMA50"] = False

    if candle_info["is_bullish"]:
        score += 1
        criteria["Boga mumu"] = True
    else:
        criteria["Boga mumu"] = False

    if trend["ema20"]:
        distance_ema20 = (current_price - trend["ema20"]) / trend["ema20"] * 100
        if distance_ema20 > RALLY_MAX_DISTANCE_FROM_20EMA_PCT:
            score -= 1
            criteria["EMA20'den asiri uzak"] = False

    breakout = detect_breakout(data, current_price)
    return score, criteria, breakout


def rally_score_label(score: int):
    if score >= 9:
        return "🚀 COK GUCLU RALLI ADAYI"
    elif score >= 7:
        return "🚀 RALLI ADAYI"
    elif score >= 5:
        return "🟡 IZLEME"
    else:
        return "⚪ ZAYIF"


def check_rally_candidate(ticker: str, data: pd.DataFrame, state: dict):
    symbol = ticker.replace(".IS", "")
    current_price = float(data["Close"].iloc[-1])

    rsi_series = calculate_rsi(data["Close"])
    current_rsi = float(rsi_series.iloc[-1])

    macd_line, macd_signal, histogram = calculate_macd(data["Close"])
    macd_bullish = bool(macd_line.iloc[-1] > macd_signal.iloc[-1])

    avg_volume = data["Volume"].tail(20).mean()
    current_volume = data["Volume"].iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

    trend = determine_trend(data)
    candle_info = detailed_candle_info(data)

    score, criteria, breakout = calculate_rally_score(
        data, trend, current_rsi, macd_bullish, volume_ratio, candle_info, current_price
    )

    # --- YENI (debug): her calistirmada ralli skorunu ve kirilim
    # durumunu goster - "mesaj neden gelmedi" sorusunu cevaplamak icin
    print(f"   [RALLI] {symbol}: skor={score}/10  esik={RALLY_MIN_SCORE}  "
          f"kirilim={'VAR' if breakout else 'YOK'}  hacim={volume_ratio:.2f}x  "
          f"trend={trend['trend_label']}  RSI={current_rsi:.1f}")

    # =====================================================
    # GERCEK KIRILIM -> RALLI BASLADI
    # =====================================================

    if breakout:
        broken_name, broken_level = breakout

        if volume_ratio >= RALLY_VOLUME_RATIO and trend["trend_label"] in ("YUKSELIS", "YATAY"):
            key = f"{ticker}_confirmed_{broken_name}"

            if not state.get(key):
                atr_series = calculate_atr(data)
                atr = atr_series.iloc[-1]
                if pd.isna(atr):
                    atr = current_price * 0.03

                target = max(current_price + atr * RALLY_ATR_TARGET_MULT, current_price * 1.08)
                stop = max(broken_level, current_price - atr * RALLY_ATR_STOP_MULT)

                risk_pct = (current_price - stop) / current_price * 100
                reward_pct = (target - current_price) / current_price * 100
                rr = reward_pct / risk_pct if risk_pct > 0 else 0

                msg = (
                    f"🚀 <b>{symbol} RALLI BASLADI</b>\n\n"
                    f"Guncel fiyat: {current_price:.2f}\n"
                    f"Kirilan seviye: {broken_name} = {broken_level:.2f} ✅\n"
                    f"Hacim: {volume_ratio:.2f}x 🔥\n"
                    f"RSI(14): {current_rsi:.1f}\n"
                    f"MACD: {'POZITIF ✅' if macd_bullish else 'NEGATIF'}\n"
                    f"Trend: {trend['trend_label']}\n"
                    f"EMA20 > EMA50: {'EVET ✅' if trend['ema20_above_50'] else 'HAYIR'}\n\n"
                    f"<b>Ralli skoru: {score}/10</b> - {rally_score_label(score)}\n\n"
                    f"🎯 ATR hedefi: {target:.2f} (+%{reward_pct:.2f})\n"
                    f"🛑 Kirilim/ATR stop: {stop:.2f} (-%{risk_pct:.2f})\n"
                    f"⚖️ Risk/Odul: {rr:.2f}\n\n"
                    f"<b>Ralli kriterleri:</b>\n"
                    + "\n".join(f"{'✅' if v else '⬜'} {k}" for k, v in criteria.items())
                    + "\n\n"
                    f"⚠️ Direnc kirildi ancak hareketin devam edecegi garanti degildir.\n\n"
                    f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"⚠️ Yatirim tavsiyesi degildir."
                )
                send_telegram_message(msg)

                state[key] = True
                state[f"{ticker}_rally_tracking"] = {
                    "broken_name": broken_name,
                    "broken_level": float(broken_level),
                    "entry": float(current_price),
                    "highest": float(current_price),
                    "score": int(score),
                    "started": datetime.now().strftime("%d.%m.%Y %H:%M"),
                }
                print(f"   🚀 {symbol}: RALLI BASLADI ({broken_name})")

    # =====================================================
    # RALLI GUCLENIYOR
    # =====================================================

    tracking_key = f"{ticker}_rally_tracking"
    tracking = state.get(tracking_key)

    if tracking:
        entry = tracking["entry"]
        highest = max(tracking.get("highest", entry), current_price)
        tracking["highest"] = float(highest)

        gain = (current_price - entry) / entry * 100
        previous_high = tracking.get("previous_alert_high", entry)

        if current_price > previous_high * 1.02 and score >= RALLY_MIN_SCORE:
            msg = (
                f"🔥 <b>{symbol} RALLI GUCLENIYOR</b>\n\n"
                f"Guncel fiyat: {current_price:.2f}\n"
                f"Ralli baslangicindan: +%{gain:.2f} 🚀\n"
                f"Yeni zirve: {highest:.2f}\n"
                f"Ralli skoru: {score}/10\n"
                f"RSI: {current_rsi:.1f}\n"
                f"Hacim: {volume_ratio:.2f}x\n"
                f"Trend: {trend['trend_label']}\n\n"
                f"Yukselis yapisi su an korunuyor.\n\n"
                f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"⚠️ Yatirim tavsiyesi degildir."
            )
            send_telegram_message(msg)
            tracking["previous_alert_high"] = float(current_price)

    # =====================================================
    # RALLI ADAYI (henuz kirilim yok ama puan yuksek)
    # =====================================================

    if score >= RALLY_MIN_SCORE and not breakout and volume_ratio >= 1.2:
        candidate_key = f"{ticker}_rally_candidate"
        old_score = state.get(candidate_key)

        if old_score is None or score > old_score:
            levels = get_breakout_levels(data)
            nearest_level = None
            nearest_name = None

            for name, level in levels.items():
                if level > current_price:
                    if nearest_level is None or level < nearest_level:
                        nearest_level = level
                        nearest_name = name

            distance = (
                (nearest_level - current_price) / current_price * 100
                if nearest_level else None
            )

            msg = (
                f"🟡 <b>{symbol} RALLI ADAYI</b>\n\n"
                f"Guncel fiyat: {current_price:.2f}\n"
                f"<b>Ralli skoru: {score}/10</b>\n\n"
                f"Trend: {trend['trend_label']}\n"
                f"RSI(14): {current_rsi:.1f}\n"
                f"MACD: {'POZITIF ✅' if macd_bullish else 'NEGATIF'}\n"
                f"Hacim: {volume_ratio:.2f}x\n\n"
            )

            if nearest_level:
                msg += (
                    f"🚧 En yakin kirilim: {nearest_name} = {nearest_level:.2f}\n"
                    f"Kirilima mesafe: %{distance:.2f}\n\n"
                )

            msg += (
                f"<b>Kriterler:</b>\n"
                + "\n".join(f"{'✅' if v else '⬜'} {k}" for k, v in criteria.items())
                + "\n\n"
                f"⚠️ Henuz kesin ralli teyidi yok. Hacimli direnç kirilimi bekleniyor.\n\n"
                f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"⚠️ Yatirim tavsiyesi degildir."
            )
            send_telegram_message(msg)
            state[candidate_key] = int(score)
    else:
        state[f"{ticker}_rally_candidate"] = int(score)


def check_rally_status(ticker: str, data: pd.DataFrame, state: dict):
    symbol = ticker.replace(".IS", "")
    key = f"{ticker}_rally_tracking"
    tracking = state.get(key)

    if not tracking:
        return

    last_close = float(data["Close"].iloc[-1])
    broken_level = tracking["broken_level"]
    entry = tracking["entry"]
    gain = (last_close - entry) / entry * 100

    if last_close < broken_level:
        msg = (
            f"🟠 <b>{symbol} RALLI ZAYIFLADI</b>\n\n"
            f"Kirilim seviyesi: {broken_level:.2f}\n"
            f"Guncel kapanis: {last_close:.2f}\n"
            f"Ralli baslangicindan: %{gain:.2f}\n\n"
            f"Fiyat kirilan seviyenin altinda kapanis yapti.\n"
            f"Bu durum sahte kirilim veya geri cekilme olabilir.\n\n"
            f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Yatirim tavsiyesi degildir."
        )
        send_telegram_message(msg)
        del state[key]
        print(f"   🟠 {symbol}: RALLI ZAYIFLADI")
    else:
        print(f"   🔥 {symbol}: RALLI TAKIPTE - {last_close:.2f} > {broken_level:.2f}")


# =========================================================
# ANI DUSUS
# =========================================================


def check_sharp_drop(ticker: str):
    try:
        intraday = yf.Ticker(ticker).history(period="1d", interval="5m")
    except Exception as e:
        print(f"[Ani dusus kontrolu atlandi] {ticker}: {e}")
        return None

    if intraday.empty or len(intraday) < 13:
        return None

    current = intraday["Close"].iloc[-1]
    one_hour = intraday["Close"].iloc[-13]
    high = intraday["High"].max()

    drop_1h = (current - one_hour) / one_hour * 100
    drop_high = (current - high) / high * 100

    triggered = drop_1h <= -SHARP_DROP_THRESHOLD_PCT or drop_high <= -SHARP_DROP_FROM_HIGH_PCT

    return {
        "current_price": current,
        "drop_1h_pct": drop_1h,
        "drop_from_high_pct": drop_high,
        "intraday_high": high,
        "triggered": triggered,
    }


# =========================================================
# ANA ANALIZ
# =========================================================


def check_active_setup(ticker: str, current_price: float, state: dict):
    """Daha once acilmis bir DONUS setup'i varsa, stop ya da hedefe
    ulasilip ulasilmadigini kontrol eder. Ulasildiysa kaydi siler,
    boylece bir sonraki uygun sinyal tekrar gonderilebilir.
    NOT: Bu fonksiyon olmadan `state[setup_key]` kalici kaliyor ve
    o ticker icin bir daha ASLA yeni DONUS mesaji gonderilmiyordu."""
    symbol = ticker.replace(".IS", "")
    setup_key = f"{ticker}_active_setup"
    setup = state.get(setup_key)

    if not setup:
        return

    entry = setup["entry"]
    stop = setup["stop"]
    target = setup["target"]

    if current_price <= stop:
        msg = (
            f"🔴 <b>{symbol} DONUS BASARISIZ OLDU</b>\n\n"
            f"Giris: {entry:.2f} | Stop: {stop:.2f} kirildi\n"
            f"Guncel fiyat: {current_price:.2f}\n\n"
            f"Bu sinyal takibi sona erdi.\n\n"
            f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Yatirim tavsiyesi degildir."
        )
        send_telegram_message(msg)
        del state[setup_key]
        print(f"   [SETUP] {symbol}: BASARISIZ - stop kirildi, kayit silindi")
        return

    if current_price >= target:
        gain_pct = (current_price - entry) / entry * 100
        msg = (
            f"✅ <b>{symbol} DONUS HEDEFE ULASTI</b>\n\n"
            f"Giris: {entry:.2f} | Hedef: {target:.2f}\n"
            f"Guncel fiyat: {current_price:.2f} (+%{gain_pct:.2f})\n\n"
            f"Bu sinyal takibi sona erdi.\n\n"
            f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Yatirim tavsiyesi degildir."
        )
        send_telegram_message(msg)
        del state[setup_key]
        print(f"   [SETUP] {symbol}: HEDEFE ULASTI, kayit silindi")
        return

    print(f"   [SETUP] {symbol}: takip ediliyor (giris={entry:.2f} stop={stop:.2f} hedef={target:.2f})")


def classify_setup_type(near_support: bool, volume_spike: bool, macd_bullish: bool,
                         bullish_candle: bool, trend_label: str, current_rsi: float) -> str:
    """DONUS kriterlerinin altinda yatan durumu ikiye ayirir:
    - DONUS: fiyat gercekten bir destege yakin, klasik geri donus adayi
    - MOMENTUM: destekten uzak ama hacim/MACD/mum guclu, RSI yuksek -
      bu aslinda devam eden bir kirilim/ivmelenme, "destek testi" degil.
    Ayrim, hedef fiyatin dogru secilmesi (fib direnci mi, ATR bazli
    genisletilmis hedef mi) icin kullanilir."""
    is_momentum = (
        volume_spike and macd_bullish and bullish_candle
        and trend_label == "YUKSELIS"
        and not near_support
        and not pd.isna(current_rsi)
        and current_rsi > MOMENTUM_RSI_MIN
    )
    return "MOMENTUM" if is_momentum else "DONUS"


def analyze_ticker(ticker: str, state: dict):
    try:
        data = yf.Ticker(ticker).history(period="2y")
        print(f"[DEBUG] {ticker}: {len(data)} satir veri")
    except Exception as e:
        print(f"[HATA] {ticker}: {e}")
        return

    if data.empty:
        return

    # Yahoo bazen son satira NaN Close'lu bir yer tutucu ekliyor - temizle
    data = data.dropna(subset=["Close"])

    if len(data) < 120:
        print(f"[UYARI] {ticker}: yetersiz veri")
        return

    symbol = ticker.replace(".IS", "")
    current_price = float(data["Close"].iloc[-1])

    # --- YENI: onceki DONUS setup'i varsa once onu kontrol et
    # (stop/hedef vurulduysa kaydi temizler, boylece yeni sinyal
    # tekrar gonderilebilir) ---
    check_active_setup(ticker, current_price, state)

    # =====================================================
    # ANI DUSUS
    # =====================================================

    sharp_drop = check_sharp_drop(ticker)
    if sharp_drop and sharp_drop["triggered"]:
        msg = (
            f"🔴 <b>{symbol} ANI DUSUS</b>\n\n"
            f"Guncel fiyat: {sharp_drop['current_price']:.2f}\n"
            f"Son 1 saat: %{sharp_drop['drop_1h_pct']:.2f}\n"
            f"Gun ici tepeden: %{sharp_drop['drop_from_high_pct']:.2f}\n"
            f"Gun ici tepe: {sharp_drop['intraday_high']:.2f}\n\n"
            f"Fiyat hareketi normalden hizli.\n\n"
            f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Yatirim tavsiyesi degildir."
        )
        send_telegram_message(msg)

    # =====================================================
    # RALLI MOTORU
    # =====================================================

    check_rally_status(ticker, data, state)
    check_rally_candidate(ticker, data, state)

    # =====================================================
    # DONUS MOTORU
    # =====================================================

    peak, trough = find_trend_leg(data, TREND_LOOKBACK_DAYS)
    fib = calculate_all_fib_levels(peak, trough)

    support_levels = {k: v for k, v in fib.items() if k in ("0.618", "0.786", "1.0 (Dip)")}

    closest_name = None
    closest_price = None
    closest_distance = 999

    # DUZELTME: sadece fiyatin ALTINDAKI seviyeler gercek "destek" sayilir.
    # Onceki halde yon kontrolu yoktu; fiyat bir dirence yaklastiginda o
    # seviye yanlislikla "en yakin destek" olarak secilebiliyor, bu da
    # hedefin (= ayni seviye) girisin hemen ustunde cikmasina ve yapay
    # "Risk/Odul ZAYIF" etiketine yol aciyordu (MIATK ornegi).
    for name, price in support_levels.items():
        if price >= current_price:
            continue
        distance = abs(current_price - price) / price * 100
        if distance < closest_distance:
            closest_name, closest_price, closest_distance = name, price, distance

    if closest_price is None:
        return

    near_support = closest_distance <= TOLERANCE_PCT

    rsi_series = calculate_rsi(data["Close"])
    rsi = rsi_series.iloc[-1]
    oversold = bool(rsi < RSI_OVERSOLD) if not pd.isna(rsi) else False

    avg_volume = data["Volume"].tail(20).mean()
    current_volume = data["Volume"].iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
    volume_spike = volume_ratio >= VOLUME_SPIKE_RATIO

    macd, signal, histogram = calculate_macd(data["Close"])
    macd_bullish = bool(macd.iloc[-1] > signal.iloc[-1])

    candle = detailed_candle_info(data)
    trend = determine_trend(data)

    atr_series = calculate_atr(data)
    atr = atr_series.iloc[-1]
    atr_pct = atr / current_price * 100 if not pd.isna(atr) else None

    touches = support_strength(data, closest_price, STRENGTH_LOOKBACK_DAYS, STRENGTH_TOLERANCE_PCT)
    strong_support = touches >= MIN_TOUCHES_FOR_STRONG

    divergence = detect_bullish_divergence(data, rsi_series, DIVERGENCE_LOOKBACK_DAYS)

    # =====================================================
    # DONUS PUANI
    # =====================================================

    criteria = {
        "Destek seviyesine yakin": near_support,
        "RSI asiri satim": oversold,
        "Hacim artisi": volume_spike,
        "Boga mumu / cekic": candle["is_bullish"],
        "Guclu destek": strong_support,
        "MACD momentum yukari": macd_bullish,
    }
    score = sum(1 for value in criteria.values() if value)

    min_score = MIN_SCORE_DOWNTREND if trend["trend_label"] == "DUSUS" else MIN_SCORE
    hard_volume = volume_ratio >= VOLUME_HARD_FILTER_RATIO

    # --- YENI (debug): donus skorunu goster ---
    print(f"   [DONUS] {symbol}: skor={score}/6  esik={min_score}  "
          f"hacimFiltre={'GECTI' if hard_volume else 'GECMEDI'}  "
          f"destekFark=%{closest_distance:.2f}")

    # =====================================================
    # 52 HAFTALIK
    # =====================================================

    last_252 = data.tail(252)
    high_52 = last_252["High"].max()
    low_52 = last_252["Low"].min()
    from_low = (current_price - low_52) / low_52 * 100
    from_high = (current_price - high_52) / high_52 * 100

    # =====================================================
    # DIRENC / DESTEK
    # =====================================================

    next_res_name, next_res_price = find_next_resistance(fib, current_price)
    upside = (next_res_price - current_price) / current_price * 100 if next_res_price else None
    next_support_name, next_support_price = find_next_support(fib, closest_price)

    # =====================================================
    # STATE (onceki calistirmaya gore yon)
    # =====================================================

    previous = state.get(ticker, {})
    previous_price = previous.get("last_price")
    previous_score = previous.get("last_score")

    price_line = ""
    score_line = ""

    if previous_price:
        change = (current_price - previous_price) / previous_price * 100
        arrow = "▲" if change > 0 else ("▼" if change < 0 else "→")
        price_line = f"Onceki analize gore: {arrow} %{abs(change):.2f}\n"

    if previous_score is not None:
        if score > previous_score:
            score_line = f"Donus puani guclendi: {previous_score}/6 -> {score}/6 📈\n"
        elif score < previous_score:
            score_line = f"Donus puani zayifladi: {previous_score}/6 -> {score}/6 📉\n"
        else:
            score_line = f"Donus puani degismedi: {score}/6\n"

    state[ticker] = {
        "last_price": float(current_price),
        "last_score": int(score),
        "last_update": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }

    # =====================================================
    # DONUS SINYALI
    # =====================================================

    if score >= min_score and hard_volume:
        stop = current_price - atr * 1.5 if not pd.isna(atr) else current_price * 0.97
        if next_support_price:
            stop = max(stop, next_support_price)

        min_stop = current_price * (1 - MIN_STOP_DISTANCE_PCT / 100)
        stop = min(stop, min_stop)

        # --- YENI: setup tipine gore hedef secimi ---
        setup_type = classify_setup_type(
            near_support, volume_spike, macd_bullish, candle["is_bullish"],
            trend["trend_label"], rsi
        )

        if setup_type == "MOMENTUM":
            atr_for_target = atr if not pd.isna(atr) else current_price * 0.03
            atr_target = current_price + (MOMENTUM_ATR_TARGET_MULT * atr_for_target)
            target = max(atr_target, next_res_price) if next_res_price else atr_target
            title_text = "MOMENTUM / KIRILIM DEVAM EDIYOR"
            title_emoji = "🚀"
        else:
            target = next_res_price if next_res_price else current_price * 1.05
            title_text = "DONUS NOKTASI"
            title_emoji = "🟢"

        risk_pct = (current_price - stop) / current_price * 100
        reward_pct = (target - current_price) / current_price * 100
        rr = reward_pct / risk_pct if risk_pct > 0 else 0
        rr_label = "UYGUN ✅" if rr >= 1.5 else "ZAYIF ⚠️"

        daily_change = (
            (current_price - data["Close"].iloc[-2]) / data["Close"].iloc[-2] * 100
        )

        # --- YENI/DUZELTME (v3.1): her satir kendi degiskeninde,
        # kosullu satirlar mesajin tamamini SILMEZ ---
        limit_line = (
            f"⚠️ Gunluk degisim +%{daily_change:.2f} - tavana yaklasiyor!\n"
            if daily_change >= APPROACHING_LIMIT_PCT else ""
        )
        divergence_line = "RSI pozitif uyumsuzluk: VAR 🟢\n" if divergence else ""
        resistance_line = (
            f"Bir sonraki direnc: {next_res_name} = {next_res_price:.2f} (+%{upside:.2f})\n"
            if next_res_price else ""
        )
        support_line = (
            f"Kirilirsa sonraki destek: {next_support_name} = {next_support_price:.2f}\n"
            if next_support_price else ""
        )
        # DUZELTME: ATR satiri artik ayri degiskende - bos oldugunda
        # sadece bu satir kayboluyor, mesajin geri kalani ETKILENMIYOR.
        atr_line = f"ATR: {atr_pct:.2f}%\n" if atr_pct else ""

        setup_type_line = f"Setup tipi: {setup_type}\n"

        msg = (
            f"{title_emoji} <b>{symbol} {title_text}</b>\n\n"
            f"Guncel fiyat: {current_price:.2f}\n"
            f"{price_line}"
            f"{score_line}"
            f"{setup_type_line}"
            f"Trend: {trend['trend_label']}\n"
            f"En yakin destek: {closest_name} = {closest_price:.2f} (fark %{closest_distance:.2f})\n"
            f"Destek test sayisi: {touches}\n"
            f"{support_line}"
            f"{resistance_line}"
            f"52 haftalik: dipten +%{from_low:.1f} / tepeden %{from_high:.1f}\n"
            f"RSI(14): {rsi:.1f}\n"
            f"{divergence_line}"
            f"Hacim: {volume_ratio:.2f}x\n"
            f"{atr_line}"
            f"Mum: {candle['formation']}\n\n"
            f"<b>Risk/Odul:</b>\n"
            f"Giris: {current_price:.2f}\n"
            f"Stop: {stop:.2f} (-%{risk_pct:.2f})\n"
            f"Hedef: {target:.2f} (+%{reward_pct:.2f})\n"
            f"Risk/Odul: {rr:.2f} - {rr_label}\n\n"
            f"{limit_line}"
            f"<b>Donus kriterleri:</b>\n"
            + "\n".join(f"{'✅' if v else '⬜'} {k}" for k, v in criteria.items())
            + "\n\n"
            f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Yatirim tavsiyesi degildir."
        )

        setup_key = f"{ticker}_active_setup"
        if setup_key not in state:
            state[setup_key] = {
                "entry": float(current_price),
                "stop": float(stop),
                "target": float(target),
                "setup_type": setup_type,
                "opened": datetime.now().strftime("%d.%m.%Y %H:%M"),
            }
            send_telegram_message(msg)
            print(f"   🟢 {symbol}: DONUS SINYALI")


def main():
    print("================================================")
    print("🚀 BIST RALLI AVCISI v3.1")
    print(f"{datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("================================================")

    state = load_state()

    for ticker in TICKERS:
        try:
            analyze_ticker(ticker, state)
        except Exception as e:
            print(f"[HATA] {ticker}: {type(e).__name__}: {e}")

    save_state(state)

    print("================================================")
    print("Analiz tamamlandi.")
    print("================================================")


if __name__ == "__main__":
    main()
