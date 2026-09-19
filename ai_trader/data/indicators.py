"""Technical indicator computations on OHLCV data."""
from __future__ import annotations

import numpy as np
import pandas as pd


def to_frame(ohlcv: list[list]) -> pd.DataFrame:
    """Convert ccxt-style OHLCV `[[ts, o, h, l, c, vol], ...]` to a DataFrame."""
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.set_index("timestamp")


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out.fillna(50.0)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def bollinger(series: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    return pd.DataFrame(
        {
            "upper": mid + num_std * std,
            "mid": mid,
            "lower": mid - num_std * std,
        }
    )


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range via Wilder smoothing."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Augment an OHLCV DataFrame with all indicators.

    Returns the last completed row as the current feature snapshot.
    """
    out = df.copy()
    out["sma_20"] = sma(out["close"], 20)
    out["sma_50"] = sma(out["close"], 50)
    out["ema_12"] = ema(out["close"], 12)
    out["ema_26"] = ema(out["close"], 26)
    out["rsi_14"] = rsi(out["close"], 14)
    macd_df = macd(out["close"])
    out["macd"] = macd_df["macd"]
    out["macd_signal"] = macd_df["signal"]
    out["macd_hist"] = macd_df["hist"]
    bb = bollinger(out["close"])
    out["bb_upper"] = bb["upper"]
    out["bb_lower"] = bb["lower"]
    out["bb_mid"] = bb["mid"]
    out["atr_14"] = atr(out, 14)
    return out


def latest_features(df: pd.DataFrame) -> dict:
    """Return the newest, fully-populated feature row as a dict."""
    full = df.dropna()
    if full.empty:
        return {}
    row = full.iloc[-1]
    return {
        key: (round(float(value), 6) if isinstance(value, (int, float, np.floating)) else None)
        for key, value in row.items()
        if key not in {"open", "high", "low", "volume"}
    }