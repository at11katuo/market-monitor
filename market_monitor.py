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

LINE_NOTIFY_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN", "")
LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"


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
    if not LINE_NOTIFY_TOKEN:
        print("エラー: LINE_NOTIFY_TOKEN が未設定です", file=sys.stderr)
        sys.exit(1)
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    resp = requests.post(
        LINE_NOTIFY_URL,
        headers=headers,
        data={"message": message},
        timeout=10,
    )
    resp.raise_for_status()


def main() -> None:
    # 200SMA算出のため2年分、VIXは直近のみ取得
    vt_close = fetch_close("VT", "2y")
    vix_close = fetch_close("^VIX", "10d")

    if len(vt_close) < 200:
        print("データ不足: 200SMA を計算できません", file=sys.stderr)
        sys.exit(1)

    current_price = float(vt_close.iloc[-1])
    current_vix = float(vix_close.iloc[-1])

    rsi = calculate_rsi(vt_close, period=14)
    high_21d = float(vt_close.iloc[-21:].max())
    drawdown = (current_price - high_21d) / high_21d
    sma200 = float(vt_close.rolling(200).mean().iloc[-1])

    cond_rsi = rsi <= 30.0
    cond_drawdown = drawdown <= -0.10
    cond_vix = current_vix >= 30.0
    cond_sma = current_price < sma200

    # 沈黙のルール: 4条件すべて成立しなければ何もせず終了
    if not (cond_rsi and cond_drawdown and cond_vix and cond_sma):
        sys.exit(0)

    message = (
        "\n"
        "【VT 総悲観・高勝率シグナル 検知】\n"
        f"現在価格  : ${current_price:.2f}\n"
        f"RSI(14)   : {rsi:.1f}  (<=30 ✅)\n"
        f"21日高値比: {drawdown * 100:.1f}%  (<=-10% ✅)\n"
        f"VIX       : {current_vix:.1f}  (>=30 ✅)\n"
        f"200SMA    : ${sma200:.2f}  (現在価格が下回り ✅)\n"
        "-> 全条件クリア。買い検討を推奨します。"
    )

    send_line_notify(message)
    print("LINE Notify 送信完了")


if __name__ == "__main__":
    main()
