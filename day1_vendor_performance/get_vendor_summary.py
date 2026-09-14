import sqlite3
import pandas as pd
import logging

from ingestion_db import ingest_db

# Logging Configuration
logging.basicConfig(
    filename="logs/get_vendor_summary.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a",
)


# Create Vendor Summary
def create_vendor_summary(conn):
    """
    Merge purchase, sales, pricing, and freight data
    to create a consolidated vendor performance summary.
    """

    vendor_sales_summary = pd.read_sql_query(
        """
        WITH FreightSummary AS (

            SELECT
                VendorNumber,
                SUM(Freight) AS FreightCost

            FROM vendor_invoice

            GROUP BY VendorNumber
        ),

        PurchaseSummary AS (

            SELECT
                p.VendorNumber,
                p.VendorName,
                p.Brand,
                p.Description,
                p.PurchasePrice,
                pp.Price AS ActualPrice,
                pp.Volume,

                SUM(p.Quantity) AS TotalPurchaseQuantity,
                SUM(p.Dollars) AS TotalPurchaseDollars

            FROM purchases AS p

            INNER JOIN purchase_prices AS pp
                ON p.Brand = pp.Brand
                AND p.VendorNumber = pp.VendorNumber

            WHERE p.PurchasePrice > 0

            GROUP BY
                p.VendorNumber,
                p.VendorName,
                p.Brand,
                p.Description,
                p.PurchasePrice,
                pp.Price,
                pp.Volume
        ),

        SalesSummary AS (

            SELECT
                VendorNo,
                Brand,

                SUM(SalesQuantity) AS TotalSalesQuantity,
                SUM(SalesDollars) AS TotalSalesDollars,
                SUM(SalesPrice) AS TotalSalesPrice,
                SUM(ExciseTax) AS TotalExciseTax

            FROM sales

            GROUP BY
                VendorNo,
                Brand
        )

        SELECT
            ps.VendorNumber,
            ps.VendorName,
            ps.Brand,
            ps.Description,
            ps.PurchasePrice,
            ps.ActualPrice,
            ps.Volume,

            ps.TotalPurchaseQuantity,
            ps.TotalPurchaseDollars,

            ss.TotalSalesQuantity,
            ss.TotalSalesDollars,
            ss.TotalSalesPrice,
            ss.TotalExciseTax,

            fs.FreightCost

        FROM PurchaseSummary AS ps

        LEFT JOIN SalesSummary AS ss
            ON ps.VendorNumber = ss.VendorNo
            AND ps.Brand = ss.Brand

        LEFT JOIN FreightSummary AS fs
            ON ps.VendorNumber = fs.VendorNumber

        ORDER BY
            ps.TotalPurchaseDollars DESC
        """,
        conn,
    )

    return vendor_sales_summary


# Clean and Transform Data
def clean_data(df):
    """
    Clean the vendor summary data and create
    derived business performance metrics.
    """

    # Convert Volume to numeric
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")

    # Convert sales quantity to numeric
    df["TotalSalesQuantity"] = (
        pd.to_numeric(df["TotalSalesQuantity"], errors="coerce")
        .fillna(0)
        .astype("int64")
    )

    # Handle missing values
    df.fillna(0, inplace=True)

    # Remove unnecessary whitespace
    df["VendorName"] = df["VendorName"].str.strip()
    df["Description"] = df["Description"].str.strip()

    # -- Derived Business Metrics --

    # Gross Profit
    df["GrossProfit"] = df["TotalSalesDollars"] - df["TotalPurchaseDollars"]

    # Profit Margin
    df["ProfitMargin"] = (df["GrossProfit"] / df["TotalSalesDollars"]) * 100

    # Stock Turnover
    df["StockTurnOver"] = df["TotalSalesQuantity"] / df["TotalPurchaseQuantity"]

    # Sales-to-Purchase Ratio
    df["SalesToPurchaseRatio"] = df["TotalSalesDollars"] / df["TotalPurchaseDollars"]

    return df


# Main Execution
if __name__ == "__main__":

    # Create database connection
    conn = sqlite3.connect("inventory.db")

    logging.info("Creating vendor summary table...")

    summary_df = create_vendor_summary(conn)

    logging.info("Vendor summary created successfully.")

    logging.info(summary_df.head().to_string())

    logging.info("Cleaning vendor summary data...")

    clean_df = clean_data(summary_df)

    logging.info("Vendor summary data cleaned successfully.")

    logging.info(clean_df.head().to_string())

    logging.info("Ingesting vendor summary into database...")

    ingest_db(clean_df, "vendor_sales_summary", conn)

    logging.info("Vendor summary ingestion completed successfully.")

    print("vendor_sales_summary created and ingested successfully.")

    conn.close()
