import argparse
import asyncio
import locale
import logging
import os
import signal
import sys
import serial
import serial_asyncio

from configparser import ConfigParser
from logging.handlers import RotatingFileHandler

from .network import GraphNetwork
from .serialprotocol import SerialProtocol
from .connectedpath import connectedpath_setup, connectedpath_pre_run
from .xmlrpcserver import xmlrpcserver_setup
from .esphomeapi import esphomeapi_setup, esphomeapi_shutdown
from .frame import APIFrame
from .direct import DirectBase

setup_done = True
local_node_serial = 0
local_node_firm = ''


def config_default(config):
    # type: (ConfigParser) -> None
    if 'serial' not in config:
        config['serial'] = {
            'port': '/dev/ttyUSB0',
            'baud': 115200
        }
    if 'server' not in config:
        config['server'] = {
            'bind_ip': 'localhost',
            'bind_port': 8801
        }


async def setup():
    global setup_done, local_node_serial, local_node_firm
    serprot = SerialProtocol.get()  # type: SerialProtocol
    buffer = DirectBase.build_command('echo', echo=b'CIAO')
    frame = APIFrame(buffer, escaped=True)
    serprot.send_api_frame(frame)
    buffer = await serprot.rx_frames.get()
    frame = DirectBase.split_response(buffer)
    if frame['id'] != 'echo' or frame['echo'] != b'CIAO':
        setup_done = False

    buffer = DirectBase.build_command('nodeId')
    frame = APIFrame(buffer, escaped=True)
    serprot.send_api_frame(frame)
    buffer = await serprot.rx_frames.get()
    frame = DirectBase.split_response(buffer)
    if frame['id'] != 'nodeId' or 'serial' not in frame:
        setup_done = False
    else:
        local_node_serial = frame['serial']
        GraphNetwork.instance().local_node_id = local_node_serial
    buffer = DirectBase.build_command('firm')
    frame = APIFrame(buffer, escaped=True)
    serprot.send_api_frame(frame)
    buffer = await serprot.rx_frames.get()
    frame = DirectBase.split_response(buffer)
    if frame['id'] != 'firm' or 'revision' not in frame:
        setup_done = False
    else:
        local_node_firm = frame['revision']


async def shutdown(loop, signal_=None):
    """Cleanup tasks tied to the service's shutdown."""
    if signal_:
        print(f"Received exit signal {signal_.name}...")
    esphomeapi_shutdown()
    await asyncio.sleep(1)
    loop.stop()
    print("Shutdown complete ...")


def handle_exception(loop, context):
    # context["message"] will always be there; but context["exception"] may not
    print(context['source_traceback'])
    msg = context.get("exception", context["message"])
    print(f"Caught exception: {msg}")
    print("Shutting down...")
    asyncio.create_task(shutdown(loop))


def main(_args=None):
    locale.setlocale(locale.LC_ALL, 'C')

    conf = ConfigParser()
    config_default(conf)
    conf.read("meshmeshhub.ini")
    if not os.path.exists("meshmeshhub.ini"):
        with open('meshmeshhub.ini', 'w') as configfile:
            conf.write(configfile)

    handler = logging.handlers.RotatingFileHandler("/dev/shm/hub2.log", maxBytes=256 * 1024, backupCount=7)
    handler2 = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
        handlers=(handler, handler2),
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logging.getLogger('matplotlib.font_manager').disabled = True

    loop = asyncio.get_event_loop()
    loop.set_debug(False)
    # loop.set_exception_handler(handle_exception)
    for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, lambda _s=s: asyncio.create_task(shutdown(loop, signal_=_s)))
    coro = serial_asyncio.create_serial_connection(loop, SerialProtocol, conf['serial']['port'], baudrate=conf['serial']['baud'])
    # coro = SerialProtocolW.create_serial_connection(conf['serial']['port'], baudrate=conf['serial']['baud'])

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--protocol", type=str, choices=['unicast', 'multipath', 'polite', 'connpath'], default=None,
                        help="Select default protocol")
    parser.add_argument("-eg", "--empty-graph", action='store_true', help='start with empty grpah. Coordinator only')
    args = parser.parse_args()
    if args.protocol:
        pass

    if args.empty_graph:
        GraphNetwork.instance().init_empty()
    else:
        GraphNetwork.instance().load_network('meshmesh.graphml')

    try:
        loop.run_until_complete(coro)
        loop.run_until_complete(setup())
        if not setup_done:
            print('Can\'t setup comunication with local node...')
            return
        connectedpath_setup()
        print('serialconnection Setup phase completed... local node is 0x%08X firmware (%s)' % (local_node_serial, local_node_firm))
        xmlrpcserver_setup(loop, args.protocol)
        print('xmlrpcserver Setup phase completed...')
        esphomeapi_setup(loop)
        print('esphomeapi_setup Setup phase completed. Starting main loop')
        # loop.set_exception_handler(handle_exception)
        connectedpath_pre_run(loop)
        loop.run_forever()
    except serial.SerialException as ex:
        print(ex)


if __name__ == "__main__":
    main()
