server_port = 8000
base_url = f"http://localhost:{server_port}"

APP_CONFIG = {
    "upload_folder_dataset": "data/images/dataset",
    "upload_folder_product": "data/images/product",
    "upload_folder_inspection": "data/images/inspection",
}

DB = {
    "driver": "mysql+mysqlconnector",
    "host": "db",
    "user": "testUser",
    "password": "testP@ssw0rd",
    "database": "testDB",
    "echo": False,
    # "client_flags": [mysql.connector.ClientFlag.SSL],
    # "ssl_ca": "<path-to-SSL-cert>/DigiCertGlobalRootG2.crt.pem",
}
