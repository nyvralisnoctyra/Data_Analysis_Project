import pandas as pd
import os
from sqlalchemy import create_engine
import logging
import time

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)


# Configure logging
logging.basicConfig(
    filename="logs/ingesting_db.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a",
)


# Create SQLite database connection
engine = create_engine("sqlite:///inventory.db")


def ingest_db(df, table_name, engine):
    """Ingest a DataFrame into a database table."""
    df.to_sql(table_name, con=engine, if_exists="replace", index=False)


def load_raw_data():
    """Load CSV files from the data folder and ingest them into the database."""

    start = time.time()
    ingested_files_count = 0

    if os.path.exists("data"):

        for file in os.listdir("data"):

            if file.endswith(".csv"):

                file_path = os.path.join("data", file)

                df = pd.read_csv(file_path)

                logging.info(f"Ingesting {file} into database")

                table_name = os.path.splitext(file)[0]

                ingest_db(df, table_name, engine)

                ingested_files_count += 1

    else:
        logging.warning("'data' directory not found.")

    end = time.time()

    total_time = (end - start) / 60

    if ingested_files_count > 0:
        logging.info(
            f"Successfully ingested "
            f"{ingested_files_count} CSV file(s) into the database."
        )
    else:
        logging.info("No CSV files were found or ingested.")

    logging.info(f"Total time taken: {total_time:.2f} minutes")


if __name__ == "__main__":
    load_raw_data()
