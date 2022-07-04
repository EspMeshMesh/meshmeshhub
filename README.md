# MeshMeshHub

## Preparation

```sh
WORKSPACE=<your meshmesh workspace folder>
WORKSPACE=<your meshmesh workspace folder>

```

Clone the following projects:

```shell
git clone https://github.com/EspMeshMesh/esphome.git -b mm_2022.4.0
git clone https://github.com/EspMeshMesh/meshmeshhub.git
git clone https://github.com/EspMeshMesh/aioesphomeapi.git
```

```shell
cd ${WORKSPACE}/esphome
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

```shell
cd ${WORKSPACE}/esphome
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```



## Tutorial 1: Simple node test

### Load firmware on test nodes

Enter in the esphome project folder:

```shell
cd ${WORKSPACE}/esphome
```

Connect the **first** device (d1 mini or nodemcu) to the usb (/dev/ttyUSB0) port 
and flash the node01 configuration.

```shell
python -m esphome run --device /dev/ttyUSB0  ../meshmeshhub/configs/node01.yaml 
```

Connect the **second** device (d1 mini or nodemcu) to the usb (/dev/ttyUSB0) port 
and flash the node01 configuration.

```shell
python -m esphome run --device /dev/ttyUSB0  ../meshmeshhub/configs/node02.yaml 
```

Keep note of device mac address provided by the esptool: The netwrok address will be equal to the last three bytes of the mac address.

![image-20220704234703529](images/mac_address.png)

To be continued...
