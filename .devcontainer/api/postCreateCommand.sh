sudo apt update
sudo apt install -y --no-install-recommends default-mysql-client-core
# # Timezone 設定用
# sudo cp /usr/share/zoneinfo/Asia/Tokyo /etc/localtime

# imageのサイズを小さくするためにキャッシュ削除
sudo apt clean
sudo rm -rf /var/lib/apt/lists/*

pip install -r ./requirements.txt
