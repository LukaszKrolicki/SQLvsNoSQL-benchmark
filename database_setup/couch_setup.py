import random
from datetime import datetime, timedelta
import pandas as pd
import os
import couchdb
import json

# CouchDB configuration
COUCHDB_CONFIG = {
    "host": "http://localhost:5984/",
    "username": "admin",
    "password": "admin"
}

# CSV file paths
CSV_DIR = '../data'
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
        if isinstance(value, str):
            corrected_datetime = datetime.fromisoformat(value)
        else:
            timestamp = int(float(value) / 1000)
            corrected_datetime = datetime.fromtimestamp(timestamp)
        return corrected_datetime.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OverflowError):
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2020, 12, 31)
        random_date = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
        return random_date.strftime('%Y-%m-%d %H:%M:%S')

# Function to import CSV to CouchDB
def import_csv_to_couchdb(db, file_path):
    print(f"Importing data from {file_path} to CouchDB database {db.name}...")
    file_path = os.path.join(CSV_DIR, file_path)
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist!")
        return

    df = pd.read_csv(file_path, low_memory=False)
    print(f"Importing {db.name}...")

    if 'time_recorded' in df.columns:
        df['time_recorded'] = df['time_recorded'].apply(correct_datetime)

    datetime_columns = ['original_listed_time', 'expiry', 'closed_time', 'listed_time']
    for col in datetime_columns:
        if col in df.columns:
            df[col] = df[col].apply(correct_datetime)

    int_columns = ['company_id', 'views', 'applies', 'remote_allowed', 'sponsored']
    for col in int_columns:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype('int')

    if 'zip_code' in df.columns:
        df['zip_code'] = df['zip_code'].astype(str)

    # Use bulk document operations for faster upload
    docs = []
    for _, row in df.iterrows():
        row = row.where(pd.notnull(row), None)  # Replace NaN values with None
        doc = row.to_dict()
        docs.append(doc)

    try:
        db.update(docs)
    except couchdb.http.ResourceConflict:
        print(f"Conflict error: Some documents already exist in {db.name}.")
    except Exception as e:
        print(f"Error updating documents: {e}")

    print(f"Imported {len(df)} records into CouchDB database {db.name}!")

# Connect to CouchDB and import data
def main():
    print("Test:")
    try:
        print("Connecting:")
        couch = couchdb.Server(COUCHDB_CONFIG['host'])
        couch.resource.credentials = (COUCHDB_CONFIG['username'], COUCHDB_CONFIG['password'])
        print("Connected to CouchDB successfully!")
    except Exception as e:
        print(f"Connection error: {e}")
        return

    for table, file_path in FILES.items():
        if table in couch:
            db = couch[table]
        else:
            db = couch.create(table)
        import_csv_to_couchdb(db, file_path)

if __name__ == "__main__":
    main()