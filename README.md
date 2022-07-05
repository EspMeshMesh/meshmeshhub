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



## Tutorial 1: Local node test

### Load firmware on HUB node

This tutrial is focused on flash and test the HUB node device.

Enter in the esphome project folder:

```shell
cd ${WORKSPACE}/esphome
```

Connect the **first** device (d1 mini or nodemcu) to the usb (/dev/ttyUSB0) port 
and flash the **node01** configuration.

```shell
python -m esphome run --device /dev/ttyUSB0  ../meshmeshhub/configs/node01.yaml 
```

Keep note of device mac address provided by the esptool: The network address inside the network will be equal to the last three bytes of the device mac address.

![image-20220704234703529](images/mac_address.png)

### Connect the python HUB software to the HUB node

```shell
cd ${WORKSPACE}/meshmeshhub
venv/bin/python -m meshmesh.hub2 -p unicast  -sp /dev/ttyUSB0 -br 460800 -eg 
```

![Hub Start](images/hub_start.png)

If you see something similar the above picture and the last three bytes of the mac address in the HUB software are  the same you see in after the esptool flash the step has been successful and the HUB software is correctly speaking with the HUB device.

## Tutorial 2: Test the HUB device with the test software

For this tutorial you must have a running HUB software (follow the Tutorial 1 in order to have a running HUB software).

To be continued...

## Tutorial 3: Flash and test a second node

Enter in the esphome project folder:

```shell
cd ${WORKSPACE}/esphome
```

Connect the **second** device (d1 mini or nodemcu) to the usb port (let's suppose that his serial port is /dev/ttyUSB1)  and flash the **node02** configuration.

```shell
python -m esphome run --device /dev/ttyUSB1  ../meshmeshhub/configs/node02.yaml 
```

To be continued...
