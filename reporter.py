# ============================================================
# REPORTER — Performance statistics and chart generation
# ============================================================

import os
import math
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")   # headless rendering — no display needed
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
from backtest_engine import Trade
import config as cfg


def compute_stats(trades: list[Trade], account_size: float = None) -> dict:
    """
    Compute comprehensive performance statistics from a list of completed trades.
    """
    if account_size is None:
        account_size = cfg.ACCOUNT_SIZE

    if not trades:
        return {"error": "No trades to analyze."}

    stats = {}
    stats["total_trades"] = len(trades)

    # Split by win/loss
    winners = [t for t in trades if t.pnl > 0]
    losers  = [t for t in trades if t.pnl <= 0]

    stats["winners"] = len(winners)
    stats["losers"]  = len(losers)
    stats["win_rate_pct"] = round(len(winners) / len(trades) * 100, 1)

    # Average W/L in % terms
    avg_win_pct  = np.mean([t.pnl_pct for t in winners]) * 100 if winners else 0
    avg_loss_pct = np.mean([t.pnl_pct for t in losers])  * 100 if losers  else 0
    stats["avg_win_pct"]  = round(avg_win_pct, 2)
    stats["avg_loss_pct"] = round(avg_loss_pct, 2)

    # R-multiple stats
    r_multiples = [t.r_multiple for t in trades]
    stats["avg_r"]         = round(np.mean(r_multiples), 3)
    stats["median_r"]      = round(np.median(r_multiples), 3)
    stats["best_trade_r"]  = round(max(r_multiples), 2)
    stats["worst_trade_r"] = round(min(r_multiples), 2)

    # Expectancy: (win_rate * avg_win_R) + (loss_rate * avg_loss_R)
    win_rate  = len(winners) / len(trades)
    loss_rate = 1 - win_rate
    avg_win_r  = np.mean([t.r_multiple for t in winners]) if winners else 0
    avg_loss_r = np.mean([t.r_multiple for t in losers])  if losers  else 0
    expectancy = (win_rate * avg_win_r) + (loss_rate * avg_loss_r)
    stats["expectancy_r"] = round(expectancy, 3)

    # Profit factor
    gross_profit = sum(t.pnl for t in winners) if winners else 0
    gross_loss   = abs(sum(t.pnl for t in losers)) if losers else 0
    stats["profit_factor"] = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf")

    # Total P&L
    total_pnl = sum(t.pnl for t in trades)
    stats["total_pnl_dollars"] = round(total_pnl, 2)
    stats["total_return_pct"]  = round(total_pnl / account_size * 100, 2)

    # Holding period
    hold_days = [t.hold_days for t in trades]
    stats["avg_hold_days"]  = round(np.mean(hold_days), 1)
    stats["median_hold_days"] = round(np.median(hold_days), 1)

    # CAGR
    if trades:
        start_date = min(t.entry_date for t in trades)
        end_date   = max(t.exit_date  for t in trades)
        years = max((end_date - start_date).days / 365.25, 0.1)
        final_value = account_size + total_pnl
        if final_value > 0:
            cagr = (final_value / account_size) ** (1 / years) - 1
        else:
            cagr = -1.0
        stats["cagr_pct"] = round(cagr * 100, 2)
        stats["backtest_years"] = round(years, 2)

    # By pattern type
    for pattern in ("BREAKOUT", "EP"):
        pt = [t for t in trades if t.pattern == pattern]
        if pt:
            pt_winners = [t for t in pt if t.pnl > 0]
            stats[f"{pattern.lower()}_trades"]  = len(pt)
            stats[f"{pattern.lower()}_win_rate"] = round(len(pt_winners) / len(pt) * 100, 1)
            stats[f"{pattern.lower()}_avg_r"]    = round(np.mean([t.r_multiple for t in pt]), 3)

    # Exit reason breakdown
    for reason in ("STOP", "TRAIL_EMA", "MAX_HOLD", "END_DATA"):
        count = sum(1 for t in trades if t.exit_reason == reason)
        stats[f"exit_{reason.lower()}"] = count

    return stats


def compute_drawdown(equity_curve: pd.Series) -> pd.Series:
    """Return a series of drawdown percentages from peak."""
    if equity_curve.empty:
        return pd.Series(dtype=float)
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max * 100
    return drawdown


def compute_max_drawdown(equity_curve: pd.Series) -> float:
    """Return the maximum drawdown as a positive percentage."""
    dd = compute_drawdown(equity_curve)
    return round(abs(dd.min()), 2) if not dd.empty else 0.0


def generate_equity_curve_chart(equity_curve: pd.Series, output_dir: str) -> None:
    """Save equity curve + drawdown chart to output/equity_curve.png."""
    if equity_curve.empty:
        return

    eq = equity_curve.dropna()
    dd = compute_drawdown(eq)

    fig = plt.figure(figsize=(14, 8))
    gs  = gridspec.GridSpec(2, 1, height_ratios=[3, 1], hspace=0.1)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    # Equity curve
    ax1.plot(eq.index, eq.values, color="#00c49a", linewidth=1.8, label="Portfolio Value")
    ax1.fill_between(eq.index, cfg.ACCOUNT_SIZE, eq.values,
                     where=eq.values >= cfg.ACCOUNT_SIZE,
                     color="#00c49a", alpha=0.15)
    ax1.fill_between(eq.index, cfg.ACCOUNT_SIZE, eq.values,
                     where=eq.values < cfg.ACCOUNT_SIZE,
                     color="#ff4d4d", alpha=0.20)
    ax1.axhline(cfg.ACCOUNT_SIZE, color="white", linewidth=0.8, linestyle="--", alpha=0.4)
    ax1.set_ylabel("Portfolio Value ($)", color="white")
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax1.set_facecolor("#1a1a2e")
    ax1.tick_params(colors="white")
    ax1.legend(facecolor="#1a1a2e", labelcolor="white")
    ax1.grid(True, alpha=0.15)

    # Drawdown
    ax2.fill_between(dd.index, 0, dd.values, color="#ff4d4d", alpha=0.6)
    ax2.plot(dd.index, dd.values, color="#ff4d4d", linewidth=0.8)
    ax2.set_ylabel("Drawdown (%)", color="white")
    ax2.set_facecolor("#1a1a2e")
    ax2.tick_params(colors="white")
    ax2.grid(True, alpha=0.15)

    fig.patch.set_facecolor("#1a1a2e")
    plt.suptitle("Qullamaggie-Style Backtest — Equity Curve", color="white", fontsize=14)

    plt.savefig(os.path.join(output_dir, "equity_curve.png"), dpi=150, bbox_inches="tight",
                facecolor="#1a1a2e")
    plt.close()
    print(f"  Chart saved: {output_dir}/equity_curve.png")


def generate_monthly_returns_chart(trades: list[Trade], output_dir: str) -> None:
    """Save a monthly returns heatmap table to output/monthly_returns.png."""
    if not trades:
        return

    # Build monthly PnL series
    monthly = {}
    for t in trades:
        key = (t.exit_date.year, t.exit_date.month)
        monthly[key] = monthly.get(key, 0) + t.pnl

    if not monthly:
        return

    years  = sorted(set(k[0] for k in monthly))
    months = list(range(1, 13))
    month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    data = []
    for year in years:
        row = []
        for m in months:
            pnl = monthly.get((year, m), None)
            if pnl is not None:
                row.append(round(pnl / cfg.ACCOUNT_SIZE * 100, 1))
            else:
                row.append(None)
        data.append(row)

    fig, ax = plt.subplots(figsize=(14, max(3, len(years) * 0.8 + 1)))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")
    ax.set_xlim(0, 12)
    ax.set_ylim(0, len(years))
    ax.set_xticks([i + 0.5 for i in range(12)])
    ax.set_xticklabels(month_labels, color="white")
    ax.set_yticks([i + 0.5 for i in range(len(years))])
    ax.set_yticklabels(years[::-1], color="white")
    ax.tick_params(length=0)

    for row_i, year in enumerate(reversed(years)):
        for col_i, m in enumerate(months):
            val = data[years.index(year)][col_i]
            if val is None:
                color = "#2a2a3e"
                text = ""
            elif val > 0:
                intensity = min(val / 20, 1.0)
                color = (0, intensity * 0.77 + 0.15, intensity * 0.60 + 0.10)
                text = f"+{val:.1f}%"
            else:
                intensity = min(abs(val) / 15, 1.0)
                color = (intensity * 0.80 + 0.15, 0.10, 0.10)
                text = f"{val:.1f}%"

            rect = plt.Rectangle((col_i, row_i), 1, 1, color=color, ec="#1a1a2e", lw=1)
            ax.add_patch(rect)
            if text:
                ax.text(col_i + 0.5, row_i + 0.5, text,
                        ha="center", va="center", fontsize=8, color="white", fontweight="bold")

    ax.set_title("Monthly Returns (%)", color="white", fontsize=12, pad=10)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "monthly_returns.png"), dpi=150, bbox_inches="tight",
                facecolor="#1a1a2e")
    plt.close()
    print(f"  Chart saved: {output_dir}/monthly_returns.png")


def save_trades_csv(trades: list[Trade], output_dir: str) -> None:
    """Export all trades to a CSV file."""
    if not trades:
        return

    rows = []
    for t in trades:
        rows.append({
            "ticker":        t.ticker,
            "pattern":       t.pattern,
            "entry_date":    t.entry_date.strftime("%Y-%m-%d"),
            "entry_price":   round(t.entry_price, 4),
            "stop_price":    round(t.stop_price, 4),
            "exit_date":     t.exit_date.strftime("%Y-%m-%d") if t.exit_date else "",
            "exit_price":    round(t.exit_price, 4),
            "exit_reason":   t.exit_reason,
            "shares":        t.shares,
            "risk_dollars":  round(t.risk_dollars, 2),
            "pnl":           round(t.pnl, 2),
            "pnl_pct":       round(t.pnl_pct * 100, 2),
            "r_multiple":    round(t.r_multiple, 3),
            "hold_days":     t.hold_days,
        })

    df = pd.DataFrame(rows)
    path = os.path.join(output_dir, "backtest_trades.csv")
    df.to_csv(path, index=False)
    print(f"  Trades CSV saved: {path}")


def save_summary_txt(stats: dict, max_drawdown: float, output_dir: str) -> None:
    """Save a human-readable summary to backtest_summary.txt."""
    lines = [
        "=" * 55,
        "  QULLAMAGGIE SWING TRADING - BACKTEST SUMMARY",
        "=" * 55,
        "",
        f"  Account Size:           {cfg.CURRENCY_SYMBOL}{cfg.ACCOUNT_SIZE:>12,.0f}",
        f"  Risk Per Trade:         {cfg.RISK_PER_TRADE * 100:.1f}%",
        f"  Backtest Period:        {stats.get('backtest_years', '?')} years",
        "",
        "-- PERFORMANCE " + "-" * 40,
        f"  Total Trades:           {stats.get('total_trades', 0):>6}",
        f"  Winners:                {stats.get('winners', 0):>6}",
        f"  Losers:                 {stats.get('losers', 0):>6}",
        f"  Win Rate:               {stats.get('win_rate_pct', 0):>5.1f}%",
        f"  Avg Win:                {stats.get('avg_win_pct', 0):>+6.2f}%",
        f"  Avg Loss:               {stats.get('avg_loss_pct', 0):>+6.2f}%",
        f"  Profit Factor:          {stats.get('profit_factor', 0):>6.2f}",
        f"  Expectancy (R):         {stats.get('expectancy_r', 0):>+6.3f}R",
        f"  Avg R per Trade:        {stats.get('avg_r', 0):>+6.3f}R",
        "",
        "-- RETURNS " + "-" * 44,
        f"  Total P&L:              {cfg.CURRENCY_SYMBOL}{stats.get('total_pnl_dollars', 0):>+12,.2f}",
        f"  Total Return:           {stats.get('total_return_pct', 0):>+6.2f}%",
        f"  CAGR:                   {stats.get('cagr_pct', 0):>+6.2f}%",
        f"  Max Drawdown:           {max_drawdown:>6.2f}%",
        "",
        "-- TRADE DETAILS " + "-" * 38,
        f"  Best Trade:             {stats.get('best_trade_r', 0):>+6.2f}R",
        f"  Worst Trade:            {stats.get('worst_trade_r', 0):>+6.2f}R",
        f"  Avg Hold (days):        {stats.get('avg_hold_days', 0):>6.1f}",
        f"  Median Hold (days):     {stats.get('median_hold_days', 0):>6.1f}",
        "",
        "-- BY PATTERN " + "-" * 41,
        f"  Breakout Trades:        {stats.get('breakout_trades', 0):>6}  |  "
        f"WR: {stats.get('breakout_win_rate', 0):>5.1f}%  |  "
        f"Avg R: {stats.get('breakout_avg_r', 0):>+.3f}R",
        f"  EP Trades:              {stats.get('ep_trades', 0):>6}  |  "
        f"WR: {stats.get('ep_win_rate', 0):>5.1f}%  |  "
        f"Avg R: {stats.get('ep_avg_r', 0):>+.3f}R",
        "",
        "-- EXIT REASONS " + "-" * 39,
        f"  Stopped Out:            {stats.get('exit_stop', 0):>6}",
        f"  10-EMA Trail:           {stats.get('exit_trail_ema', 0):>6}",
        f"  Max Hold Reached:       {stats.get('exit_max_hold', 0):>6}",
        f"  End of Data:            {stats.get('exit_end_data', 0):>6}",
        "",
        "=" * 55,
    ]

    path = os.path.join(output_dir, "backtest_summary.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Summary saved: {path}")
    print("\n" + "\n".join(lines))


def generate_report(
    trades: list[Trade],
    equity_curve: pd.Series,
    output_dir: str,
) -> dict:
    """
    Generate all report outputs:
    - backtest_trades.csv
    - backtest_summary.txt
    - equity_curve.png
    - monthly_returns.png
    Returns the stats dict.
    """
    os.makedirs(output_dir, exist_ok=True)

    stats = compute_stats(trades)
    max_dd = compute_max_drawdown(equity_curve)
    stats["max_drawdown_pct"] = max_dd

    save_trades_csv(trades, output_dir)
    save_summary_txt(stats, max_dd, output_dir)
    generate_equity_curve_chart(equity_curve, output_dir)
    generate_monthly_returns_chart(trades, output_dir)

    return stats
