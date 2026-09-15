"""Build a reproducible editorial PDF from the SQLite vendor summary."""

import math
import os
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from scipy.stats import spearmanr, ttest_ind

ROOT = Path(__file__).parent
OUTPUT = ROOT / "portfolio_case_study_vendor_performance.pdf"
ASSETS = ROOT / "report_assets"
CRIMSON = "#B3122D"
INK = HexColor("#121212")
RED = HexColor(CRIMSON)
MUTED = HexColor("#666666")
PAPER = HexColor("#F7F5F2")
W, H = A4


def money(value):
    return f"${value / 1_000_000:.2f}M" if abs(value) >= 1_000_000 else f"${value:,.0f}"


def pct(value, places=1):
    return f"{value * 100:.{places}f}%"


def calculate_metrics(connection):
    df = pd.read_sql_query("SELECT * FROM vendor_sales_summary", connection)
    for col in df.select_dtypes(include="number"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    sales = df.groupby(["VendorNumber", "VendorName"], as_index=False).agg(
        TotalSalesDollars=("TotalSalesDollars", "sum"),
        TotalPurchaseDollars=("TotalPurchaseDollars", "sum"),
        GrossProfit=("GrossProfit", "sum"),
        TotalSalesQuantity=("TotalSalesQuantity", "sum"),
        TotalPurchaseQuantity=("TotalPurchaseQuantity", "sum"),
    )
    sales["Margin"] = sales.GrossProfit / sales.TotalSalesDollars
    sales["Turnover"] = sales.TotalSalesQuantity / sales.TotalPurchaseQuantity
    sales = sales.replace([np.inf, -np.inf], np.nan)
    brands = df.groupby(["Brand", "Description"], as_index=False).agg(
        TotalSalesDollars=("TotalSalesDollars", "sum"),
        GrossProfit=("GrossProfit", "sum"),
        TotalSalesQuantity=("TotalSalesQuantity", "sum"),
        TotalPurchaseQuantity=("TotalPurchaseQuantity", "sum"),
    )
    brands["Margin"] = brands.GrossProfit / brands.TotalSalesDollars
    brands["Turnover"] = brands.TotalSalesQuantity / brands.TotalPurchaseQuantity
    brands = brands.replace([np.inf, -np.inf], np.nan)
    active = df[(df.TotalSalesDollars > 0) & np.isfinite(df.ProfitMargin)].copy()
    median_sales = active.TotalSalesDollars.median()
    hi = active.loc[active.TotalSalesDollars >= median_sales, "ProfitMargin"]
    lo = active.loc[active.TotalSalesDollars < median_sales, "ProfitMargin"]
    ttest = ttest_ind(hi, lo, equal_var=False, nan_policy="omit")
    bulk = df[(df.TotalPurchaseQuantity > 0) & (df.PurchasePrice > 0)].dropna(
        subset=["TotalPurchaseQuantity", "PurchasePrice"]
    )
    rho, rho_p = spearmanr(bulk.TotalPurchaseQuantity, bulk.PurchasePrice)
    sorted_sales = sales.sort_values("TotalSalesDollars", ascending=False).reset_index(
        drop=True
    )
    top10 = sorted_sales.head(10)
    total_sales = float(df.TotalSalesDollars.sum())
    total_purchase = float(df.TotalPurchaseDollars.sum())
    low_turn = sales[(sales.TotalPurchaseQuantity > 0) & (sales.Turnover < 0.5)]
    return {
        "df": df,
        "vendors": sales,
        "brands": brands,
        "top_vendors": sorted_sales,
        "record_count": len(df),
        "vendor_count": len(sales),
        "brand_count": len(brands),
        "total_sales": total_sales,
        "total_purchase": total_purchase,
        "total_gross_profit": float(df.GrossProfit.sum()),
        "vendor_sales_total": float(sales.TotalSalesDollars.sum()),
        "overall_margin": float(df.GrossProfit.sum() / total_sales),
        "active_count": len(active),
        "zero_sales_count": int((df.TotalSalesDollars == 0).sum()),
        "negative_profit_count": int((df.GrossProfit < 0).sum()),
        "pareto_top_10_share": float(top10.TotalSalesDollars.sum() / total_sales),
        "pareto_top_20_share": float(
            sorted_sales.head(20).TotalSalesDollars.sum() / total_sales
        ),
        "top_vendor": top10.iloc[0].to_dict(),
        "top_brand": brands.nlargest(1, "TotalSalesDollars").iloc[0].to_dict(),
        "low_turn_count": len(low_turn),
        "low_turn_purchase": float(low_turn.TotalPurchaseDollars.sum()),
        "median_turnover": float(sales.Turnover.median()),
        "bulk_rho": float(rho),
        "bulk_pvalue": float(rho_p),
        "margin_ttest_stat": float(ttest.statistic),
        "margin_ttest_pvalue": float(ttest.pvalue),
        "hi_margin": float(hi.mean() / 100),
        "lo_margin": float(lo.mean() / 100),
        "median_sales": float(median_sales),
    }


def make_charts(m):
    ASSETS.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titleweight": "bold"})
    vendors = m["top_vendors"].copy()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    top = vendors.head(15).iloc[::-1]
    ax.barh(top.VendorName.str.slice(0, 28), top.TotalSalesDollars / 1e6, color=CRIMSON)
    ax.set(title="Top vendors by sales", xlabel="Sales ($M)")
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(ASSETS / "vendor_sales.png", dpi=220, transparent=False)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    vendors["cum"] = (
        vendors.TotalSalesDollars.cumsum() / vendors.TotalSalesDollars.sum()
    )
    ax.bar(
        range(1, len(vendors) + 1),
        vendors.TotalSalesDollars / 1e6,
        color="#D9D5D0",
        width=1,
    )
    ax2 = ax.twinx()
    ax2.plot(range(1, len(vendors) + 1), vendors.cum, color=CRIMSON, linewidth=2.5)
    ax.set(
        title="Revenue concentration: vendor Pareto",
        xlabel="Vendors ranked by sales",
        ylabel="Sales ($M)",
    )
    ax2.set_ylabel("Cumulative share")
    ax2.yaxis.set_major_formatter(PercentFormatter(1))
    ax2.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(ASSETS / "pareto.png", dpi=220)
    plt.close(fig)

    clean = vendors.dropna(subset=["Margin", "Turnover"])
    fig, ax = plt.subplots(figsize=(10, 5.5))
    size = np.clip(
        clean.TotalPurchaseQuantity / clean.TotalPurchaseQuantity.quantile(0.95) * 45,
        8,
        80,
    )
    ax.scatter(
        clean.TotalSalesDollars / 1e6,
        clean.Margin,
        s=size,
        alpha=0.65,
        color=CRIMSON,
        edgecolors="white",
        linewidth=0.4,
    )
    ax.axhline(clean.Margin.median(), color="#444", lw=0.8, ls="--")
    ax.axvline(clean.TotalSalesDollars.median() / 1e6, color="#444", lw=0.8, ls="--")
    ax.set(
        title="Vendor sales and gross-margin profile",
        xlabel="Sales ($M)",
        ylabel="Gross margin",
    )
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    fig.tight_layout()
    fig.savefig(ASSETS / "margin_scatter.png", dpi=220)
    plt.close(fig)

    df = m["df"].copy()
    df = df[(df.TotalPurchaseQuantity > 0) & (df.PurchasePrice > 0)]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.scatter(
        np.log10(df.TotalPurchaseQuantity),
        df.PurchasePrice,
        s=8,
        alpha=0.24,
        color=CRIMSON,
    )
    ax.set(
        title="Purchase quantity versus unit purchase price",
        xlabel="log10(total purchase quantity)",
        ylabel="Unit purchase price ($)",
    )
    fig.tight_layout()
    fig.savefig(ASSETS / "bulk.png", dpi=220)
    plt.close(fig)

    turn = clean.Turnover.clip(upper=3)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.hist(turn, bins=35, color=CRIMSON, edgecolor="white")
    ax.axvline(0.5, color="#111", ls="--", lw=1.4, label="0.5 turnover screen")
    ax.set(
        title="Vendor turnover distribution (capped at 3× for readability)",
        xlabel="Sales quantity / purchase quantity",
        ylabel="Vendor count",
    )
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(ASSETS / "turnover.png", dpi=220)
    plt.close(fig)


def wrap(c, text, x, y, width, size=10, leading=None, color=INK, font="Helvetica"):
    c.setFont(font, size)
    c.setFillColor(color)
    leading = leading or size * 1.4
    words, line, lines = text.split(), "", []
    for word in words:
        trial = (line + " " + word).strip()
        if c.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def header(c, number, title, kicker="ANALYTICAL CASE STUDY"):
    c.setFillColor(INK)
    c.rect(0, H - 28, W, 28, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(36, H - 18, kicker)
    c.setFont("Helvetica", 7)
    c.drawRightString(W - 36, H - 18, f"{number:02d} / 22")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 25)
    c.drawString(36, H - 72, title)
    c.setFillColor(RED)
    c.rect(36, H - 82, 62, 3, fill=1, stroke=0)


def footer(c):
    c.setStrokeColor(HexColor("#D8D4CF"))
    c.line(36, 27, W - 36, 27)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawString(36, 16, "Vendor Performance Analysis  |  Portfolio case study")
    c.drawRightString(W - 36, 16, "Evidence from local SQLite pipeline")


def result_block(c, m, y, result, interpretation, implication, limitation):
    c.setFillColor(PAPER)
    c.roundRect(36, y - 92, W - 72, 92, 5, fill=1, stroke=0)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(50, y - 18, "VERIFIED RESULT")
    c.setFillColor(INK)
    y2 = wrap(c, result, 50, y - 34, W - 100, 12, 16, INK, "Helvetica-Bold")
    columns = [
        (36, "INTERPRETATION", interpretation),
        (218, "BUSINESS IMPLICATION", implication),
        (400, "LIMITATION", limitation),
    ]
    for x, label, text in columns:
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x, y - 118, label)
        wrap(c, text, x, y - 132, 150, 8.2, 11, INK)
    return y - 202


def text_page(c, n, title, blocks, m):
    header(c, n, title)
    y = H - 112
    for block in blocks:
        y = result_block(c, m, y, *block)
    footer(c)
    c.showPage()


def chart_page(c, n, title, path, caption, block, m):
    header(c, n, title)
    c.drawImage(str(path), 36, 255, W - 72, 270, preserveAspectRatio=True, anchor="c")
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 8)
    wrap(c, caption, 36, 240, W - 72, 8, 10, MUTED, "Helvetica-Oblique")
    result_block(c, m, 190, *block)
    footer(c)
    c.showPage()


def build_report():
    with sqlite3.connect(ROOT / "inventory.db") as connection:
        m = calculate_metrics(connection)
    make_charts(m)
    c = canvas.Canvas(str(OUTPUT), pagesize=A4, pageCompression=1)
    # 1 Cover
    c.setFillColor(INK)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(RED)
    c.rect(0, 0, 18, H, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(46, H - 70, "DATA SCIENCE PORTFOLIO  /  2026")
    c.setFont("Helvetica-Bold", 38)
    c.drawString(46, H - 175, "Vendor")
    c.drawString(46, H - 220, "Performance")
    c.drawString(46, H - 265, "Analysis")
    c.setFillColor(HexColor("#D8D4CF"))
    wrap(
        c,
        "An evidence-led case study of sales concentration, brand economics, purchase behaviour, and inventory signals.",
        48,
        H - 320,
        390,
        14,
        20,
        HexColor("#D8D4CF"),
    )
    c.setFillColor(RED)
    c.rect(46, 100, 130, 3, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica", 10)
    c.drawString(46, 75, "SQLite  •  Python  •  pandas  •  SciPy  •  Matplotlib")
    c.showPage()
    # 2 Executive summary
    header(c, 2, "Executive summary")
    values = [
        ("SALES", money(m["total_sales"])),
        ("GROSS PROFIT", money(m["total_gross_profit"])),
        ("GROSS MARGIN", pct(m["overall_margin"])),
        ("VENDORS", f"{m['vendor_count']:,}"),
    ]
    x = 36
    for label, value in values:
        c.setFillColor(PAPER)
        c.roundRect(x, H - 170, 122, 78, 5, fill=1, stroke=0)
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 12, H - 115, label)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(x + 12, H - 145, value)
        x += 130
    y = H - 210
    y = wrap(
        c,
        f"The pipeline consolidates {m['record_count']:,} vendor–brand purchase records into a decision-ready view. Revenue is concentrated: the ten largest vendors account for {pct(m['pareto_top_10_share'])} of recorded sales. At the record level, {m['negative_profit_count']:,} observations carry negative gross profit and {m['zero_sales_count']:,} have no sales dollars.",
        36,
        y,
        W - 72,
        12,
        18,
    )
    wrap(
        c,
        "Portfolio framing: this is an analytical decision-support product, not an accounting close. Freight is attached at vendor level in the source pipeline and is intentionally excluded from product-level gross-profit aggregation.",
        36,
        y - 50,
        W - 72,
        10,
        15,
        MUTED,
        "Helvetica-Oblique",
    )
    footer(c)
    c.showPage()
    text_page(
        c,
        3,
        "Business question",
        [
            (
                "Which suppliers and products merit attention?",
                "The project combines transactions, product pricing and vendor freight into a unified analytical table.",
                "Prioritize commercial action by revenue, margin and movement rather than viewing transactions in isolation.",
                "The period boundary and operational service levels are not specified in the source data.",
            )
        ],
        m,
    )
    text_page(
        c,
        4,
        "From raw files to decisions",
        [
            (
                "Six operational extracts become one 18-column summary table.",
                "CSV extracts are ingested into SQLite; SQL aggregates purchases, sales and freight; pandas derives margin, turnover and sales-to-purchase ratios.",
                "A local, repeatable workflow keeps analysis portable and makes each calculation inspectable.",
                "A vendor-level freight total is joined to every vendor–brand record and must not be summed across brands.",
            )
        ],
        m,
    )
    text_page(
        c,
        5,
        "Data profile & quality",
        [
            (
                f"{m['record_count']:,} summary rows, {m['vendor_count']:,} vendors and {m['brand_count']:,} brands were analysed.",
                f"The stored main notebook confirms the 18-column summary shape. Zero sales rows are retained by the left join, preserving possible slow-moving inventory signals.",
                "Preserve no-sale items for replenishment review; do not silently filter them out of operational monitoring.",
                "Zero filling enables ratios but cannot distinguish a true zero from every upstream reason for missing sales.",
            )
        ],
        m,
    )
    chart_page(
        c,
        6,
        "EDA: vendor sales landscape",
        ASSETS / "vendor_sales.png",
        "Additional chart generated directly from vendor_sales_summary; bars show aggregate sales by vendor.",
        (
            f"{m['top_vendor']['VendorName']} is the largest recorded vendor by sales at {money(m['top_vendor']['TotalSalesDollars'])}.",
            "The sales distribution is visibly long-tailed, so averages alone mask where commercial exposure sits.",
            "Use vendor segmentation to focus relationship management and forecasting effort.",
            "Sales identifies scale, not net profitability after fully allocated operating costs.",
        ),
        m,
    )
    text_page(
        c,
        7,
        "KPI scorecard",
        [
            (
                f"Recorded sales are {money(m['total_sales'])} against {money(m['total_purchase'])} of purchase dollars, yielding a {pct(m['overall_margin'])} gross margin.",
                "The KPI is calculated as total sales less recorded purchase dollars divided by sales.",
                "Use this as a directional commercial margin screen and pair it with cost-to-serve before pricing decisions.",
                "Freight, tax treatment, overhead and timing effects are not allocated at product level.",
            )
        ],
        m,
    )
    chart_page(
        c,
        8,
        "Vendor economics",
        ASSETS / "margin_scatter.png",
        "Bubble size reflects purchase quantity; dashed lines mark median vendor sales and aggregate margin.",
        (
            "The vendor portfolio spans distinct sales and gross-margin positions.",
            "High-scale, low-margin vendors and smaller, higher-margin vendors require different commercial interventions.",
            "Set account plans by quadrant: protect profitable scale; investigate large low-margin exposure.",
            "The visual is descriptive; it does not establish that vendor choice causes margin outcomes.",
        ),
        m,
    )
    chart_page(
        c,
        9,
        "Existing project visual",
        ROOT / "assets" / "top-vendors-and-brands-by-sales.png",
        "Reused project chart: top ten vendors and brands ranked by sales.",
        (
            f"The leading brand is {m['top_brand']['Description']} at {money(m['top_brand']['TotalSalesDollars'])} in recorded sales.",
            "Product concentration accompanies vendor concentration, increasing exposure to a small number of commercial levers.",
            "Protect availability and pricing discipline for sales-leading brands while checking their margin contribution.",
            "The original figure ranks sales only; it does not include returns, stock-outs or customer demand elasticity.",
        ),
        m,
    )
    text_page(
        c,
        10,
        "Brand portfolio",
        [
            (
                f"The summary contains {m['brand_count']:,} brands; the top brand contributes {money(m['top_brand']['TotalSalesDollars'])} in sales.",
                "Brand totals are aggregated from the same vendor–brand summary grain used throughout this study.",
                "Pair sales rank with margin and turnover before promotional investment; a sales leader may still be economically weak.",
                "Brand descriptions may recur across vendors and are aggregated by Brand plus Description.",
            )
        ],
        m,
    )
    chart_page(
        c,
        11,
        "Pareto: concentration is actionable",
        ASSETS / "pareto.png",
        "Cumulative curve is calculated from vendors sorted by recorded sales.",
        (
            f"The top 10 vendors produce {pct(m['pareto_top_10_share'])} of sales; the top 20 produce {pct(m['pareto_top_20_share'])}.",
            "A relatively small supplier cohort carries a large share of revenue exposure.",
            "Prioritize forecast reviews, supply risk checks and commercial negotiations for this cohort.",
            "A Pareto curve does not reveal substitutability, contract terms or supplier lead times.",
        ),
        m,
    )
    chart_page(
        c,
        12,
        "Bulk purchasing signal",
        ASSETS / "bulk.png",
        "Scatter uses log-scaled purchase quantity for readability; each point is a summary record.",
        (
            f"Spearman ρ = {m['bulk_rho']:.3f} (p = {m['bulk_pvalue']:.3g}) between purchase quantity and unit purchase price.",
            "The rank correlation measures monotonic association without assuming a linear price curve.",
            "Treat observed volume-price patterns as a negotiation hypothesis; test matched products and contract terms before changing order sizes.",
            "Mixed products, package sizes and vendor effects confound a pooled correlation; it is not causal evidence of a bulk discount.",
        ),
        m,
    )
    chart_page(
        c,
        13,
        "Inventory movement screen",
        ASSETS / "turnover.png",
        "Turnover equals total sales quantity divided by total purchase quantity; chart is capped at 3× only for visual readability.",
        (
            f"{m['low_turn_count']:,} vendors fall below a 0.5 turnover screen, representing {money(m['low_turn_purchase'])} of recorded purchase dollars; median vendor turnover is {m['median_turnover']:.2f}×.",
            "Low turnover may indicate slow movement, overbuying, timing mismatch or incomplete sales matching.",
            "Review the largest low-turnover exposures first and pause replenishment pending item-level validation.",
            "This is not days-of-supply: no inventory dates, on-hand balance reconciliation or demand seasonality is applied.",
        ),
        m,
    )
    text_page(
        c,
        14,
        "Statistical comparison",
        [
            (
                f"High-sales records average {pct(m['hi_margin'])} margin versus {pct(m['lo_margin'])} for lower-sales records; Welch t = {m['margin_ttest_stat']:.2f}, p = {m['margin_ttest_pvalue']:.3g}.",
                f"Groups split at median record-level sales of {money(m['median_sales'])}; Welch’s test compares mean margins while allowing unequal variances.",
                "The result supports prioritizing a margin review by sales tier, not a blanket assumption that scale guarantees economics.",
                "Rows are not independent commercial experiments; skew, repeated vendors and product mix limit causal or population inference.",
            )
        ],
        m,
    )
    text_page(
        c,
        15,
        "Decision matrix",
        [
            (
                "Use four views together: scale, margin, turnover and concentration.",
                "A vendor can be a sales leader yet weak on gross margin; a high-margin brand can be slow moving.",
                "Create a weekly exception list: high sales/low margin, low turnover/high purchase dollars, and concentrated critical suppliers.",
                "Thresholds shown here are analytical screens, not approved business policy or service-level targets.",
            )
        ],
        m,
    )
    text_page(
        c,
        16,
        "Recommendation: protect profitable scale",
        [
            (
                f"Focus account governance on the top-10 cohort that drives {pct(m['pareto_top_10_share'])} of sales.",
                "Concentration makes service disruption and pricing decisions consequential.",
                "Assign executive ownership, forecast checks and margin guardrails to strategic vendors and brands.",
                "The data lacks contract, fill-rate and supplier-risk fields needed to operationalize a complete vendor scorecard.",
            )
        ],
        m,
    )
    text_page(
        c,
        17,
        "Recommendation: buy with evidence",
        [
            (
                f"The observed quantity–price association is ρ = {m['bulk_rho']:.3f}, not a causal estimate.",
                "Pooled data suggests a pattern worth testing but cannot isolate product, pack size or negotiated terms.",
                "Run controlled, SKU-matched quote comparisons before committing to bulk-buy changes.",
                "A correlation cannot quantify an expected savings rate or support a specific order-size recommendation.",
            )
        ],
        m,
    )
    text_page(
        c,
        18,
        "Recommendation: manage movement",
        [
            (
                f"Start with {m['low_turn_count']:,} low-turnover vendor screens, then drill to items with the largest purchase-dollar exposure.",
                "Quantity turnover identifies mismatch between recorded purchasing and sales movement.",
                "Freeze or reduce replenishment only after validating on-hand stock, seasonality and recent sell-through.",
                "No inventory-age or stock-on-hand reconciliation is available in the summary table.",
            )
        ],
        m,
    )
    text_page(
        c,
        19,
        "Metric definitions",
        [
            (
                "Gross profit = sales dollars − purchase dollars; gross margin = gross profit / sales dollars.",
                "Turnover = sales quantity / purchase quantity; sales-to-purchase = sales dollars / purchase dollars.",
                "These formulas make the model transparent and reproducible from the SQLite summary.",
                "They are decision-support indicators, not final accounting measures; ratios can become undefined when denominators are zero.",
            )
        ],
        m,
    )
    text_page(
        c,
        20,
        "Limitations & future work",
        [
            (
                "Freight is vendor-level, sales may be zero-filled after joins, and the source has no dated inventory-aging or service-level lens.",
                "These constraints limit product-level profitability and inventory conclusions.",
                "Next: allocate landed cost, add inventory snapshots/age, returns, lead time, promotion flags and customer demand data.",
                "Future enrichments require source-system validation and a documented allocation methodology.",
            )
        ],
        m,
    )
    text_page(
        c,
        21,
        "Technical stack & structure",
        [
            (
                "SQLite + SQL build the consolidated table; Python/pandas calculate derived metrics; SciPy performs statistical tests; Matplotlib produces charts; ReportLab renders this PDF.",
                "The project is deliberately local and inspectable: raw CSV → SQLite tables → vendor_sales_summary → notebook/report.",
                "The workflow can run on a laptop and can be version-controlled with the analytical code.",
                "The source database is large and local; refresh time and source-file availability affect reproducibility.",
            )
        ],
        m,
    )
    text_page(
        c,
        22,
        "Reproducibility appendix",
        [
            (
                "Run ingestion_db.py, then get_vendor_summary.py, then build_case_study.py; run python -m unittest test_notebook_final_merge.py test_report_metrics.py for regression checks.",
                "The report reads inventory.db / vendor_sales_summary and regenerates each added chart into report_assets/.",
                "This report was built from the local SQLite snapshot present at render time; all displayed calculated figures are dynamically inserted.",
                "The notebooks are exploratory artifacts; their saved output may not contain all later analytical sections described in the README.",
            )
        ],
        m,
    )
    c.save()
    return OUTPUT


if __name__ == "__main__":
    print(build_report())
