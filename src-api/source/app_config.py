server_port = 8000
base_url = f"http://localhost:{server_port}"

APP_CONFIG = {
    "folder_inspection": "data/inspections",
    "log_file_folder": "log",
    "log_backup_count": 7,
}

DB = {"driver": "sqlite:///data/sqlite.db", "echo": False}
