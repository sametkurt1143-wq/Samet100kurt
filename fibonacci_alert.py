import os
import json
import time
import requests
import urllib.parse
import xml.etree.ElementTree as ET
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from bs4 import BeautifulSoup

# Optional: TradingView yedek kütüphanesi (Yüklü ise aktif olur)
try:
    from tvDatafeed import TvDatafeed, Interval
    TV_AVAILABLE = True
except ImportError:
    TV_AVAILABLE = False

# ==================== KURULUM ====================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "BURAYA_BOT_TOKENINI_YAZ")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "BURAYA_CHAT_ID_YAZ")

# --- YENI: FD/SNA orani en dusuk 8 hisseden eksik olan TRENJ ve ULKER eklendi ---

TICKERS = [
    # --- Önceki liste ---
    "ARCLK.IS", "ULKER.IS", "ASUZU.IS", "GOKNR.IS", "BERA.IS",
    "TTKOM.IS", "TMSN.IS", "ENPRA.IS", "KRPLS.IS", "NETAS.IS",
    "EKIM.IS", "BALSU.IS", "BKRGY.IS", "LILAK.IS", "ZERGY.IS",
    "MERCN.IS", "ENDAE.IS",

    # --- TEKNOLOJİ (XUTEK) ---
    "ALTNY.IS", "ARDYZ.IS", "ARENA.IS", "ASELS.IS", "ATATP.IS",
    "AZTEK.IS", "BINBN.IS", "DGATE.IS", "DESPC.IS", "DOFRB.IS",
    "EDATA.IS", "ESCOM.IS", "FONET.IS", "FORTE.IS", "HTTBT.IS",
    "INGRM.IS", "MIATK.IS", "MOBTL.IS", "OBASE.IS", "ODINE.IS",
    "ONRYT.IS", "PAPIL.IS", "PATEK.IS", "PENTA.IS", "PKART.IS",
    "SDTTR.IS", "SMART.IS", "VBTYZ.IS",

    # --- GAYRİMENKUL (XGMYO) ---
    "ADGYO.IS", "AAGYO.IS", "AHSGY.IS", "AKFGY.IS", "AKSGY.IS",
    "AKMGY.IS", "ALGYO.IS", "ASGYO.IS", "ATAGY.IS", "AGYO.IS",
    "AVGYO.IS", "AVPGY.IS", "BASGZ.IS", "BEGYO.IS", "DZGYO.IS",
    "DGGYO.IS", "EGEGY.IS", "EKGYO.IS", "EYGYO.IS", "FZLGY.IS",
    "HLGYO.IS", "IDGYO.IS", "ISGYO.IS", "KZBGY.IS", "KLGYO.IS",
    "KGYO.IS", "KRGYO.IS", "KZGYO.IS", "LXGYO.IS", "MRGYO.IS",
    "MHRGY.IS", "MSGYO.IS", "NUGYO.IS", "OZKGY.IS", "OZGYO.IS",
    "PAGYO.IS", "PSGYO.IS", "PEKGY.IS", "RYGYO.IS", "SVGYO.IS",
    "SRVGY.IS", "SNGYO.IS", "SURGY.IS", "SEGYO.IS", "TRGYO.IS",
    "TDGYO.IS", "TSGYO.IS", "VKGYO.IS", "VRGYO.IS", "YGGYO.IS",
    "ZGYO.IS", "ZRGYO.IS",

    # --- GIDA (XGIDA) ---
    "AVOD.IS", "AKHAN.IS", "ALKLC.IS", "AEFES.IS", "ARMGD.IS",
    "ATAKP.IS", "BANVT.IS", "BESLR.IS", "BORSK.IS", "CEMZY.IS",
    "CCOLA.IS", "DARDL.IS", "DMRGD.IS", "DURKN.IS", "EFOR.IS",
    "EKSUN.IS", "ELITE.IS", "ERSU.IS", "FADE.IS", "FRIGO.IS",
    "GOLDA.IS", "GUNDG.IS", "KAYSE.IS", "KRVGD.IS", "KRSTL.IS",
    "KTSKR.IS", "MERKO.IS", "MEYSU.IS", "OBAMS.IS", "OFSYM.IS",
    "ORCAY.IS", "OYLUM.IS", "PENGD.IS", "PETUN.IS", "PINSU.IS",
    "PNSUT.IS", "SEGMN.IS", "SELVA.IS", "SOKE.IS", "TATGD.IS",
    "TUKAS.IS", "TBORG.IS", "ULUUN.IS", "VANGD.IS", "YYLGD.IS",

    # --- ÇİMENTO / TAŞ-TOPRAK (XTAST) ---
    "AFYON.IS", "AKCNS.IS", "ALBTN.IS", "BTCIM.IS", "BSOKE.IS",
    "BIENY.IS", "BOBET.IS", "BUCIM.IS", "CGCAM.IS", "CMBTN.IS",
    "CIMSA.IS", "DOGUB.IS", "EGSER.IS", "GOLTS.IS", "ISVEA.IS",
    "KLKIM.IS", "KLSER.IS", "KONYA.IS", "KUTPO.IS", "LMKDC.IS",
    "NIBAS.IS", "NUHCM.IS", "OYAKC.IS", "QUAGR.IS", "SERNT.IS",
    "MARBL.IS", "USAK.IS",

    # --- TURİZM (XTRZM) ---
    "AYCES.IS", "AVTUR.IS", "BYDNR.IS", "BIGCH.IS", "DOCO.IS",
    "ETILR.IS", "MAALT.IS", "MARTI.IS", "MERIT.IS", "PKENT.IS",
    "TABGD.IS", "TEKTU.IS", "ULAS.IS",

    # --- ENERJİ (XELKT) ---
    "AHGAZ.IS", "AKENR.IS", "AKFYE.IS", "AKSEN.IS", "ALFAS.IS",
    "ARFYE.IS", "AYDEM.IS", "AYEN.IS", "BIOEN.IS", "BIGEN.IS",
    "CONSE.IS", "CWENE.IS", "CANTE.IS", "CATES.IS", "ARASE.IS",
    "ECOGR.IS", "ENJSA.IS", "ENERY.IS", "ESEN.IS", "IZENR.IS",
    "KLYPV.IS", "LYDYE.IS", "MOGAN.IS", "NTGAZ.IS", "NATEN.IS",
    "ODAS.IS", "PAMEL.IS", "SMRTG.IS", "TATEN.IS", "ZEDUR.IS",
    "ZOREN.IS", "MAGEN.IS",

    # --- MADENCİLİK (XMADN) ---
    "CVKMD.IS", "PRKME.IS", "RUZYE.IS", "TRMET.IS", "TRENJ.IS",
    "TRALT.IS", "VSNMD.IS", "KOZAA.IS", "KOZAL.IS",
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

# ==================== KREDILI ISLEM YASAGI (VBTS) ====================
# rotaborsa.com/tedbirli-hisseler/ sayfasi Borsa Istanbul'un VBTS
# (Volatilite Bazli Tedbir Sistemi) kapsaminda tedbirli/kredili islem
# yasagi olan hisseleri gunluk guncellenen bir tabloda listeliyor.
# Google News RSS'e (haber modulu) guvenmek yerine bu sayfayi DOGRUDAN
# cekiyoruz - cunku bir yasak haberi henuz indexlenmemis olabilir, ama
# bu tablo dogrudan kaynak.
MARGIN_BAN_URL = "https://rotaborsa.com/tedbirli-hisseler/"

# ===================================================


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
# KREDILI ISLEM YASAGI (VBTS TEDBIR) KONTROLU
# =========================================================

def fetch_margin_ban_list() -> dict:
    """rotaborsa.com/tedbirli-hisseler/ sayfasindaki 'Guncel tedbirli
    hisseler listesi' tablosunu ceker ve kredili islem/acika satis
    yasagi olan hisseleri {SEMBOL: bitis_tarihi} seklinde dondurur.
    Sayfa yapisi degisirse ya da erisim basarisiz olursa BOS SOZLUK
    doner - script bu durumda sessizce devam eder, hic kimseyi
    engellemez (feature'in kendisi opsiyonel bir ek bilgi katmanidir)."""
    banned = {}
    try:
        resp = requests.get(
            MARGIN_BAN_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[UYARI] Kredili islem yasagi sayfasi alinamadi: HTTP {resp.status_code}")
            return banned

        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 4:
                    continue
                ticker_cell = cells[0].get_text(strip=True)
                # Baslik satirlarini (BIST Kodu vs.) atla
                if not ticker_cell or not ticker_cell.isalpha() or len(ticker_cell) > 6:
                    continue

                end_date = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                margin_ban_cell = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                # Kredili islem/acik satis sutunu doluysa (bir isaret/checkmark
                # iceriyorsa) bu hisse kredili islem yasagi kapsaminda demektir.
                if margin_ban_cell:
                    banned[ticker_cell.upper()] = end_date

        if banned:
            print(f"[DEBUG] Kredili islem yasagi listesi cekildi: {len(banned)} hisse")
        else:
            print("[UYARI] Kredili islem yasagi tablosu bulundu ama hic satir okunamadi "
                  "(sayfa yapisi degismis olabilir)")

    except Exception as e:
        print(f"[UYARI] Kredili islem yasagi listesi cekilemedi: {type(e).__name__}: {e}")

    return banned


# =========================================================
# YEDEK VERI MOTORU (FALLBACK MECHANISM)
# =========================================================

def get_stock_history_with_fallback(ticker: str, period: str = "2y") -> pd.DataFrame:
    """
    Önce Yahoo Finance dener. Başarısız veya boş veri dönerse
    TradingView (tvDatafeed) veya diğer yedek yollara geçer.
    """
    try:
        data = yf.Ticker(ticker).history(period=period)
        if not data.empty and len(data) >= 30:
            return data
    except Exception as e:
        print(f"[YF UYARI] {ticker} Yahoo Finance verisi çekilemedi: {e}")

    if TV_AVAILABLE:
        try:
            symbol = ticker.replace(".IS", "")
            print(f"[YEDEK] {symbol} TradingView üzerinden çekiliyor...")
            tv = TvDatafeed()
            tv_data = tv.get_hist(symbol=symbol, exchange='BIST', interval=Interval.in_daily, n_bars=500)
            if tv_data is not None and not tv_data.empty:
                tv_data = tv_data.rename(columns={
                    "open": "Open", "high": "High",
                    "low": "Low", "close": "Close", "volume": "Volume"
                })
                return tv_data
        except Exception as e:
            print(f"[YEDEK HATA] TradingView verisi alınamadı ({ticker}): {e}")

    return pd.DataFrame()


# =========================================================
# GELİŞMİŞ HABER MODÜLÜ (GÖRSELLERDEKİ ÖZEL SİTELER ENTEGRELİ)
# =========================================================

def get_stock_news(symbol: str, max_items: int = 3) -> str:
    """
    Rota Borsa, Bloomberg HT, CNBC-e ve Midas haber kaynaklarını
    Google News altyapısı üzerinden öncelikli olarak tarar.
    Her başlık, Telegram'da tıklanabilir bir link olarak eklenir
    (HTML parse_mode <a href> destekler) - böylece kullanıcı
    başlığa dokunup haberin tamamını okuyabilir.
    """
    try:
        queries = [
            f"{symbol} site:rotaborsa.com OR site:bloomberght.com OR site:cnbce.com OR site:getmidas.com",
            f"{symbol} hisse haber KAP"
        ]

        news_list = []
        seen_titles = set()

        for q in queries:
            query_encoded = urllib.parse.quote(q)
            rss_url = f"https://news.google.com/rss/search?q={query_encoded}&hl=tr&gl=TR&ceid=TR:tr"

            response = requests.get(rss_url, timeout=5)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                items = root.findall(".//item")

                for item in items:
                    title_el = item.find("title")
                    link_el = item.find("link")
                    title = title_el.text if title_el is not None else ""
                    link = link_el.text if link_el is not None else ""

                    if title:
                        title_clean = title.rsplit(" - ", 1)[0] if " - " in title else title
                        if title_clean not in seen_titles:
                            seen_titles.add(title_clean)
                            if link:
                                # HTML ozel karakterlerini kacir (& her zaman
                                # Google News linklerinde gecer, Telegram HTML
                                # parse_mode bunu bozabilir)
                                safe_link = link.replace("&", "&amp;")
                                news_list.append(f'• <a href="{safe_link}">{title_clean}</a>')
                            else:
                                news_list.append(f"• {title_clean}")

                    if len(news_list) >= max_items:
                        break

            if len(news_list) >= max_items:
                break

        if not news_list:
            return "<i>Sirketle ilgili guncel haber bulunamadi.</i>"

        return "\n".join(news_list)

    except Exception as e:
        print(f"[HATA] Haber cekilemedi ({symbol}): {e}")
        return "<i>Haber servisi gecici olarak kullanilamiyor.</i>"


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
        criteria[f"Hacim patlamasi ({volume_ratio:.2f}x)"] = True
    elif volume_ratio >= RALLY_VOLUME_RATIO:
        score += 1
        criteria[f"Hacim artisi ({volume_ratio:.2f}x)"] = True
    else:
        criteria[f"Hacim yetersiz ({volume_ratio:.2f}x)"] = False

    if not pd.isna(rsi) and RALLY_RSI_MIN <= rsi <= RALLY_RSI_MAX:
        score += 1
        criteria[f"RSI saglikli momentum ({rsi:.1f})"] = True
    else:
        criteria[f"RSI aralik disi ({rsi:.1f})"] = False

    if not pd.isna(rsi) and rsi >= RALLY_OVERBOUGHT_RSI:
        score -= 2
        criteria[f"RSI asiri yuksek ({rsi:.1f})"] = False

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
        criteria[f"Boga mumu ({candle_info['formation']})"] = True
    else:
        criteria[f"Ayi mumu ({candle_info['formation']})"] = False

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
        return "🧐 IZLEME"
    else:
        return "⚪ ZAYIF"


def margin_ban_line(symbol: str, margin_banned: dict) -> str:
    """Hisse VBTS kapsaminda kredili islem yasagi listesindeyse
    mesaja eklenecek uyari satirini dondurur, degilse bos string."""
    if symbol in margin_banned:
        end_date = margin_banned[symbol]
        return (f"🚫 <b>DIKKAT:</b> Bu hisseye kredili islem/acik satis yasagi var "
                f"({end_date} tarihine kadar) - kaldirac kullanilamaz!\n")
    return ""


def check_rally_candidate(ticker: str, data: pd.DataFrame, state: dict, margin_banned: dict):
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

                news_text = get_stock_news(symbol)
                ban_line = margin_ban_line(symbol, margin_banned)

                msg = (
                    f"🚀 <b>{symbol} RALLI BASLADI</b>\n\n"
                    f"{ban_line}"
                    f"Guncel fiyat: {current_price:.2f}\n"
                    f"Kirilan seviye: {broken_name} = {broken_level:.2f} ✅\n"
                    f"Trend: {trend['trend_label']}\n"
                    f"EMA20 > EMA50: {'EVET ✅' if trend['ema20_above_50'] else 'HAYIR'}\n\n"
                    f"<b>Ralli skoru: {score}/10</b> - {rally_score_label(score)}\n\n"
                    f"🎯 ATR hedefi: {target:.2f} (+%{reward_pct:.2f})\n"
                    f"💔 Kirilim/ATR stop: {stop:.2f} (-%{risk_pct:.2f})\n"
                    f"⚖️ Risk/Odul: {rr:.2f}\n\n"
                    f"<b>Ralli kriterleri:</b>\n"
                    + "\n".join(f"{'✅' if v else '⬜'} {k}" for k, v in criteria.items())
                    + f"\n\n📰 <b>Son Haber Basliklari:</b>\n{news_text}\n\n"
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
                f"Trend: {trend['trend_label']}\n\n"
                f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"⚠️ Yatirim tavsiyesi degildir."
            )
            send_telegram_message(msg)
            tracking["previous_alert_high"] = float(current_price)

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

            news_text = get_stock_news(symbol)
            ban_line = margin_ban_line(symbol, margin_banned)

            msg = (
                f"🤑 <b>{symbol} RALLI ADAYI</b>\n\n"
                f"{ban_line}"
                f"Guncel fiyat: {current_price:.2f}\n"
                f"<b>Ralli skoru: {score}/10</b>\n\n"
                f"Trend: {trend['trend_label']}\n"
            )

            if nearest_level:
                msg += (
                    f"🚧 En yakin kirilim: {nearest_name} = {nearest_level:.2f}\n"
                    f"Kirilima mesafe: %{distance:.2f}\n\n"
                )

            msg += (
                f"<b>Kriterler:</b>\n"
                + "\n".join(f"{'✅' if v else '⬜'} {k}" for k, v in criteria.items())
                + f"\n\n📰 <b>Son Haber Basliklari:</b>\n{news_text}\n\n"
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
            f"🤕 <b>{symbol} RALLI ZAYIFLADI</b>\n\n"
            f"Kirilim seviyesi: {broken_level:.2f}\n"
            f"Guncel kapanis: {last_close:.2f}\n"
            f"Ralli baslangicindan: %{gain:.2f}\n\n"
            f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Yatirim tavsiyesi degildir."
        )
        send_telegram_message(msg)
        del state[key]


# =========================================================
# ANI DUSUS
# =========================================================


def check_sharp_drop(ticker: str):
    try:
        intraday = yf.Ticker(ticker).history(period="1d", interval="5m")
    except Exception:
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
            f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Yatirim tavsiyesi degildir."
        )
        send_telegram_message(msg)
        del state[setup_key]
        return

    if current_price >= target:
        gain_pct = (current_price - entry) / entry * 100
        msg = (
            f"✅ <b>{symbol} DONUS HEDEFE ULASTI</b>\n\n"
            f"Giris: {entry:.2f} | Hedef: {target:.2f}\n"
            f"Guncel fiyat: {current_price:.2f} (+%{gain_pct:.2f})\n\n"
            f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Yatirim tavsiyesi degildir."
        )
        send_telegram_message(msg)
        del state[setup_key]
        return


def classify_setup_type(near_support: bool, volume_spike: bool, macd_bullish: bool,
                         bullish_candle: bool, trend_label: str, current_rsi: float) -> str:
    is_momentum = (
        volume_spike and macd_bullish and bullish_candle
        and trend_label == "YUKSELIS"
        and not near_support
        and not pd.isna(current_rsi)
        and current_rsi > MOMENTUM_RSI_MIN
    )
    return "MOMENTUM" if is_momentum else "DONUS"


def analyze_ticker(ticker: str, state: dict, margin_banned: dict):
    data = get_stock_history_with_fallback(ticker, period="2y")

    if data.empty or len(data) < 120:
        return

    data = data.dropna(subset=["Close"])
    symbol = ticker.replace(".IS", "")
    current_price = float(data["Close"].iloc[-1])

    check_active_setup(ticker, current_price, state)

    # Ani Düşüş Kontrolü
    sharp_drop = check_sharp_drop(ticker)
    if sharp_drop and sharp_drop["triggered"]:
        msg = (
            f"🚨 <b>{symbol} ANI DUSUS</b>\n\n"
            f"Guncel fiyat: {sharp_drop['current_price']:.2f}\n"
            f"Son 1 saat: %{sharp_drop['drop_1h_pct']:.2f}\n"
            f"Gun ici tepeden: %{sharp_drop['drop_from_high_pct']:.2f}\n"
            f"Gun ici tepe: {sharp_drop['intraday_high']:.2f}\n\n"
            f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Yatirim tavsiyesi degildir."
        )
        send_telegram_message(msg)

    # Ralli Kontrolleri
    check_rally_status(ticker, data, state)
    check_rally_candidate(ticker, data, state, margin_banned)

    # Dönüş Kontrolleri
    peak, trough = find_trend_leg(data, TREND_LOOKBACK_DAYS)
    fib = calculate_all_fib_levels(peak, trough)
    support_levels = {k: v for k, v in fib.items() if k in ("0.618", "0.786", "1.0 (Dip)")}

    closest_name, closest_price, closest_distance = None, None, 999

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

    criteria = {
        f"Destek seviyesine yakin (fark %{closest_distance:.2f})": near_support,
        f"RSI asiri satim ({rsi:.1f})": oversold,
        f"Hacim artisi ({volume_ratio:.2f}x)": volume_spike,
        f"Boga mumu / cekic ({candle['formation']})": candle["is_bullish"],
        f"Guclu destek (test: {touches})": strong_support,
        f"MACD momentum yukari ({'POZITIF' if macd_bullish else 'NEGATIF'})": macd_bullish,
    }
    score = sum(1 for value in criteria.values() if value)

    min_score = MIN_SCORE_DOWNTREND if trend["trend_label"] == "DUSUS" else MIN_SCORE
    hard_volume = volume_ratio >= VOLUME_HARD_FILTER_RATIO

    last_252 = data.tail(252)
    high_52 = last_252["High"].max()
    low_52 = last_252["Low"].min()
    from_low = (current_price - low_52) / low_52 * 100
    from_high = (current_price - high_52) / high_52 * 100

    next_res_name, next_res_price = find_next_resistance(fib, current_price)
    upside = (next_res_price - current_price) / current_price * 100 if next_res_price else None
    next_support_name, next_support_price = find_next_support(fib, closest_price)

    previous = state.get(ticker, {})
    previous_price = previous.get("last_price")
    previous_score = previous.get("last_score")

    price_line = ""
    score_line = ""

    if previous_price:
        change = (current_price - previous_price) / previous_price * 100
        arrow_icon = "💲 🟢" if change > 0 else ("🔻 🔴" if change < 0 else "➡️")
        price_line = f"Onceki analize gore: {arrow_icon} %{change:+.2f}\n"

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

    if score >= min_score and hard_volume:
        stop = current_price - atr * 1.5 if not pd.isna(atr) else current_price * 0.97
        if next_support_price:
            stop = max(stop, next_support_price)

        min_stop = current_price * (1 - MIN_STOP_DISTANCE_PCT / 100)
        stop = min(stop, min_stop)

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
        atr_line = f"ATR: %{atr_pct:.2f}\n" if atr_pct else ""
        setup_type_line = f"Setup tipi: {setup_type}\n"
        ban_line = margin_ban_line(symbol, margin_banned)

        news_text = get_stock_news(symbol)

        msg = (
            f"{title_emoji} <b>{symbol} {title_text}</b>\n\n"
            f"{ban_line}"
            f"Guncel fiyat: {current_price:.2f}\n"
            f"{price_line}"
            f"{score_line}"
            f"{setup_type_line}"
            f"Trend: {trend['trend_label']}\n"
            f"En yakin destek: {closest_name} = {closest_price:.2f}\n"
            f"{support_line}"
            f"{resistance_line}"
            f"52 haftalik: dipten +%{from_low:.1f} | tepeden %{from_high:.1f}\n"
            f"{divergence_line}"
            f"{atr_line}\n"
            f"<b>Risk/Odul:</b>\n"
            f"🎯 Hedef: {target:.2f} (+%{reward_pct:.2f})\n"
            f"🛑 Stop: {stop:.2f} (-%{risk_pct:.2f})\n"
            f"⚖️ Risk/Odul: {rr:.2f} ({rr_label})\n\n"
            f"{limit_line}"
            f"<b>Donus kriterleri:</b>\n"
            + "\n".join(f"{'✅' if v else '⬜'} {k}" for k, v in criteria.items())
            + f"\n\n📰 <b>Son Haber Basliklari:</b>\n{news_text}\n\n"
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


def main():
    print("================================================")
    print("🇹🇷 BIST RALLI AVCISI & HABER ANALIZI v3.5")
    print(f"{datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("================================================")

    state = load_state()

    # --- YENI: kredili islem yasagi listesi TUM ticker donguleri icin
    # bir kez cekilir (her hisse icin ayri ayri cekmek gereksiz yuk olurdu) ---
    margin_banned = fetch_margin_ban_list()

    for ticker in TICKERS:
        try:
            analyze_ticker(ticker, state, margin_banned)
            time.sleep(0.3)
        except Exception as e:
            print(f"[HATA] {ticker}: {type(e).__name__}: {e}")

    save_state(state)

    print("================================================")
    print("Analiz tamamlandi.")
    print("================================================")


if __name__ == "__main__":
    main()
