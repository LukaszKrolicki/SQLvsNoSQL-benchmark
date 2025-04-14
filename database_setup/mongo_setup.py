import pymongo
import pandas as pd
import os
from datetime import datetime

# MongoDB configuration
MONGO_CONFIG = {
    "host": "localhost",
    "port": 27017,
    "username": "user",
    "password": "password",
    "database": "testdb"
}

# CSV file paths
CSV_DIR = "../data"
FILES = {
    "companies": "companies/companies.csv",
    "company_industries": "companies/company_industries.csv",
    "company_specialities": "companies/company_specialities.csv",
    "employee_counts": "companies/employee_counts.csv",
    "benefits": "jobs/benefits.csv",
    "job_industries": "jobs/job_industries.csv",
    "job_skills": "jobs/job_skills.csv",
    "salaries": "jobs/salaries.csv",
    "industries": "mappings/industries.csv",
    "skills": "mappings/skills.csv",
    "postings": "postings.csv"
}

# Function to correct datetime values
def correct_datetime(value):
    try:
        # Convert the value to an integer timestamp
        timestamp = int(float(value) / 1000)
        # Convert the timestamp to a datetime object
        corrected_datetime = datetime.fromtimestamp(timestamp)
        return corrected_datetime
    except (ValueError, OverflowError):
        # Return a default datetime value if conversion fails
        return datetime(1970, 1, 1)

# Function to import CSV to MongoDB
def import_csv_to_mongo(collection_name, file_path):
    print(f"Importing data from {file_path} to {collection_name}...")
    file_path = os.path.join(CSV_DIR, file_path)
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist!")
        return

    df = pd.read_csv(file_path, low_memory=False)
    print(f"Importing {collection_name}...")

    # Correct datetime values in the 'time_recorded' column
    if 'time_recorded' in df.columns:
        df['time_recorded'] = df['time_recorded'].apply(correct_datetime)

    # Correct datetime values in other datetime columns
    datetime_columns = ['original_listed_time', 'expiry', 'closed_time', 'listed_time']
    for col in datetime_columns:
        if col in df.columns:
            df[col] = df[col].apply(correct_datetime)

    client = pymongo.MongoClient(
        host=MONGO_CONFIG["host"],
        port=MONGO_CONFIG["port"],
        username=MONGO_CONFIG["username"],
        password=MONGO_CONFIG["password"]
    )
    db = client[MONGO_CONFIG["database"]]
    collection = db[collection_name]

    records = df.to_dict(orient='records')
    collection.insert_many(records)
    print(f"Imported {len(records)} records into {collection_name}!")

# Connect to MongoDB and import data
def main():
    print("Test:")
    try:
        print("Connecting:")
        client = pymongo.MongoClient(
            host=MONGO_CONFIG["host"],
            port=MONGO_CONFIG["port"],
            username=MONGO_CONFIG["username"],
            password=MONGO_CONFIG["password"],
            serverSelectionTimeoutMS=30000
        )
        client.server_info()  # Force connection on a request as the connect=True parameter of MongoClient seems to be useless here
        print("Connected to MongoDB successfully!")
    except Exception as e:
        print(f"Connection error: {e}")
        return

    # Ensure the collections are created in the specified order
    collection_order = [
        # 'companies', 'postings',
        # 'company_industries', 'company_specialities', 'employee_counts', 'industries', 'skills',
        # 'job_industries', 'benefits', 'salaries',
        'job_skills',
    ]

    for collection in collection_order:
        import_csv_to_mongo(collection, FILES[collection])

if __name__ == "__main__":
    main()