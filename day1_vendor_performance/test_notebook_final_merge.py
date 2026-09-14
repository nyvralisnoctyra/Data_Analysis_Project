import json
from pathlib import Path

import pandas as pd


def test_final_analysis_cell_merges_summary_dataframes():
    notebook = json.loads(Path("exploray_data_analysis.ipynb").read_text(encoding="utf-8"))
    cell = next(cell for cell in notebook["cells"] if cell.get("id") == "5c62d02c")
    namespace = {
        "pd": pd,
        "purchase_sum": pd.DataFrame(
            {
                "VendorNumber": [1],
                "VendorName": ["Vendor A"],
                "Brand": [101],
                "PurchasePrice": [10.0],
                "Actual_Price": [12.0],
                "Volume": [750],
                "Total_Purchase_Quantity": [5],
                "Total_Purchase_Dollars": [50.0],
            }
        ),
        "sales_sum": pd.DataFrame(
            {
                "VendorNo": [1],
                "Brand": [101],
                "Total_Sales_Quantity": [4],
                "Total_Sales_Dollars": [60.0],
                "Total_Excise_Tax": [2.4],
            }
        ),
        "freight_sum": pd.DataFrame({"VendorNumber": [1], "FreightCost": [3.0]}),
        "display": lambda _: None,
    }

    exec("".join(cell["source"]), namespace)

    result = namespace["finally_total"]
    assert result.loc[0, "FreightCost"] == 3.0
    assert result.loc[0, "Average_Sales_Price"] == 15.0
