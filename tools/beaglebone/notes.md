## General
sudo apt install unzip

## Meshmesh
cp /home/debian/meshmesh-hub-1.0.1.zip
sudo systemctl enable meshmesh@debian.service

## pin-config
```bash
cp /home/debian/pin-config.sh
cp /etc/systemd/system/pin-config.service
sudo systemctl enable pin-config.service
sudo systemctl start pin-config.service
sudo systemctl status pin-config.service
```

## Openvpn
```bash
sudo apt install openvpn
cd /etc/openvpn
sudo wget https://net.siralab.com/download/lightmaster0X.zip
unzip lightmaster0X.zip
sudo mv lightmaster0X.ovpn lightmaster0X.conf
sudo systemctl enable openvpn@lightmaster0X.service
sudo systemctl start openvpn@lightmaster0X.service
```