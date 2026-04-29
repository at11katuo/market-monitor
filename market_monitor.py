#!/usr/bin/env python3
"""
VT 総悲観・高勝率シグナル監視スクリプト

以下4条件すべて成立時のみ LINE Notify で通知する（沈黙のルール）:
  1. RSI(14) <= 30
  2. 直近21営業日高値から -10% 以上下落
  3. VIX >= 30
  4. 現在価格 < 200日移動平均線
"""

import os
import sys

import pandas as pd
import requests
import yfinance as yf

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"


def fetch_close(ticker: str, period: str) -> pd.Series:
    data = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    if data.empty:
        raise ValueError(f"データ取得失敗: {ticker}")
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
    return close.dropna()


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(rsi.iloc[-1])


def send_line_notify(message: str) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("エラー: LINE_CHANNEL_ACCESS_TOKEN が未設定です", file=sys.stderr)
        sys.exit(1)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    body = {"messages": [{"type": "text", "text": message}]}
    resp = requests.post(
        LINE_BROADCAST_URL,
        headers=headers,
        json=body,
        timeout=10,
    )
    resp.raise_for_status()


def main() -> None:
    # ===== テストモード: 判定条件をすべてスキップして必ず通知する =====
    message = "【テスト通知】Messaging APIへの移行テストです。"
    send_line_notify(message)
    print("LINE Messaging API 送信完了（テストモード）")


if __name__ == "__main__":
    main()
