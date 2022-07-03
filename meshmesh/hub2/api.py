
api_custom_groups = {
    "baseGrp": 0x30,
    "weatherGrp": 0x32,
    'clima': 0x33
}

discovery_api_commands = {
    "reset": {"id": 0, "args": [
    ]},
    "count": {"id": 2, "args": [
    ]},
    "get": {"id": 4, "args": [
        {'name': 'index', 'len': 1, 'encode': 'B'},
    ]},
    "start": {"id": 6, "args": [
        {'name': 'mask', 'len': 1, 'encode': 'B'},
        {'name': 'filter', 'len': 1, 'encode': 'B'},
        {'name': 'slots', 'len': 1, 'encode': 'B'},
    ]}
}

entities_api_commands = {
    "countpref": {"id": 0, "args": [
        {'name': 'type', 'len': 1, 'encode': 'B'},
        {'name': 'hash', 'len': 2, 'encode': '<H'},
    ]},
    "getprefvalue": {"id": 2, "args": [
        {'name': 'type', 'len': 1, 'encode': 'B'},
        {'name': 'hash', 'len': 2, 'encode': '<H'},
        {'name': 'num', 'len': 2, 'encode': '<H'},
    ]},
    "setprefvalue": {"id": 4, "args": [
        {'name': 'type', 'len': 1, 'encode': 'B'},
        {'name': 'hash', 'len': 2, 'encode': '<H'},
        {'name': 'num', 'len': 2, 'encode': '<H'},
        {'name': 'value', 'len': 2, 'encode': '<H'},
    ]},
}

rssicheck_api_commands = {
    "startcheck": {"id": 2, "args": [
        {'name': 'target', 'len': 4, 'default': 0, 'encode': '>I'},
    ]},
    "roundtrip": {"id": 4, "args": [
    ]},
}

flash_grp_api_commands = {
    "getmd5": {"id": 1, "args": [
        {'name': 'address', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'length', 'len': 4, 'default': 0, 'encode': '<I'},
    ]},
    "erase": {"id": 2, "args": [
        {'name': 'address', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'length', 'len': 4, 'default': 0, 'encode': '<I'},
    ]},
    "write": {"id": 3, "args": [
        {'name': 'address', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'payload', 'len': 0, 'default': None},
    ]},
    "eboot": {"id": 4, "args": [
        {'name': 'address', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'length', 'len': 4, 'default': 0, 'encode': '<I'},
    ]},
}

api_commands = {
    "echo": {"id": 0, "args": [
        {'name': 'echo', 'len': 0, 'default': None},
    ]},
    "firm": {"id": 2, "args": [
    ]},
    "nodeId": {"id": 4, "args": [
    ]},
    #"analogIn": {"id": 6, "args": [
    #]},
    #"analogOut": {"id": 8, "args": [
    #    {'name': 'channel', 'len': 1, 'default': 0, 'encode': 'B'},
    #    {'name': 'value', 'len': 2, 'default': 0, 'encode': '<H'},
    #]},
    "nodetag": {"id": 6, "args": [
    ]},
    "nodetagSet": {"id": 8, "args": [
        {'name': 'tag', 'len': 0}
    ]},
    "updateStart": {"id": 10, "args": [
        {'name': 'size', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'md5', 'len': 0, 'default': None},
    ]},
    "updateChunk": {"id": 12, "args": [
        {'name': 'chunk', 'len': 0, 'default': None},
    ]},
    "updateDigest": {"id": 14, "args": [
        {'name': 'options', 'len': 1, 'default': 0, 'encode': 'B'},
    ]},
    "updateMemMD5": {"id": 16, "args": [
        {'name': 'size', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'md5', 'len': 0, 'default': None},
    ]},
    "logDestination": {"id": 18, "args": [
    ]},
    "setLogDestination": {"id": 20, "args": [
        {'name': 'target', 'len': 4, 'default': 0, 'encode': '<I'},
    ]},
    "flashWrite": {"id": 12, "args": [
        {'name': 'address', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'payload', 'len': 0}
    ]},
    "flashDigest": {"id": 14, "args": [
        {'name': 'address', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'lenght', 'len': 2, 'default': 0, 'encode': '<H'}
    ]},
    "flashRboot": {"id": 16, "args": [
        {'name': 'rom', 'len': 1, 'default': 0, 'encode': 'B'},
        {'name': 'lenght', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'digest', 'len': 0, 'default': None}
    ]},
    "custom": {"id": 22, "args": [
        {'name': 'payload', 'len': 0}
    ]},
    "reboot": {"id": 24, "args": [
    ]},

    "discovery": {"id": 26, "submenu": discovery_api_commands},

    "rssicheck": {"id": 28, "submenu": rssicheck_api_commands},

    "spiflash": {"id": 30, "submenu": flash_grp_api_commands, "args": [
        {'name': 'group', 'len': 1, 'encode': 'B'},
        {'name': 'payload', 'len': 0}
    ]},
    "filterGroups": {"id": 32, "args": [
    ]},
    "setFilterGroups": {"id": 34, "args": [
        {'name': 'target', 'len': 4, 'default': 0, 'encode': '<I'},
    ]},
    "readSensor": {"id": 34, "args": [
        {'name': 'type', 'len': 1, 'encode': 'B'}
    ] },
    "readBinarySensor": {"id": 36, "args": [
        {'name': 'hash', 'len': 2, 'encode': '<H'}
    ]},
    "serviceEntitiesCount": {"id": 38, "args": [
    ]},
    "serviceEntityHash": {"id": 40, "args": [
        {'name': 'service', 'len': 1, 'encode': 'B'},
        {'name': 'index', 'len': 1, 'encode': 'B'}
    ]},
    "serviceEntityState": {"id": 42, "args": [
        {'name': 'type', 'len': 1, 'encode': 'B'},
        {'name': 'hash', 'len': 2, 'encode': '<H'},
    ]},
    "serviceEntityStateSet": {"id": 44, "args": [
        {'name': 'type', 'len': 1, 'encode': 'B'},
        {'name': 'hash', 'len': 2, 'encode': '<H'},
        {'name': 'value', 'len': 2, 'encode': '<H'},
    ]},
    "serviceEntityPrefsSet": {"id": 46, "args": [
        {'name': 'type', 'len': 1, 'encode': 'B'},
        {'name': 'hash', 'len': 2, 'encode': '<H'},
        {'name': 'num', 'len': 2, 'encode': '<H'},
        {'name': 'value', 'len': 2, 'encode': '<H'},
    ]},

    "entities": {"id": 48, "submenu": entities_api_commands},

    "broadcast": {"id": 112, "args": [
        {'name': 'payload', 'len': 0},
    ]},
    "unicast": {"id": 114, "args": [
        {'name': 'target', 'len': 4, 'encode': '<I'},
        {'name': 'payload', 'len': 0},
    ]},
    "beacons": {"id": 116, "args": [
        {'name': 'mask', 'len': 1, 'default': 0, 'encode': 'B'},
        {'name': 'filter', 'len': 1, 'default': 0, 'encode': 'B'}
    ]},
    "multipath": {"id": 118, "args": [
        {'name': 'target', 'len': 4, 'default': 0, 'encode': '<I'},
        {'name': 'pathlen', 'len': 1, 'default': 0, 'encode': 'B'},
        {'name': 'path', 'len': 4, 'default': [], 'encode': '<I'},
        {'name': 'payload', 'len': 0},
    ]},
    "polite": {"id": 120, "args": [
        {'name': 'target', 'len': 4, 'encode': '<I'},
        {'name': 'payload', 'len': 0},
    ]},
    "filter": {"id": 124, "args": [
        {'name': 'target', 'len': 4, 'encode': '<I'},
        {'name': 'payload', 'len': 0},
    ]},
}

discovery_api_replies = {
    "1": {"id": "reset", "structure": [
    ]},
    "3": {"id": "count", "structure": [
        {'name': 'size', 'len': 1, 'decode': 'B'},
    ]},
    "5": {"id": "get", "structure": [
        {'name': 'index', 'len': 1, 'decode': 'B'},
        {'name': 'serial', 'len': 4, 'decode': '<I'},
        {'name': 'rssi1', 'len': 2, 'decode': '<h'},
        {'name': 'rssi2', 'len': 2, 'decode': '<h'},
        {'name': 'flags', 'len': 2, 'decode': '<H'}
    ]},
    "7": {"id": "start", "structure": [
    ]}
}

entities_api_replies = {
    "1": {"id": "countpref", "structure": [
        {'name': 'value', 'len': 2, 'decode': '<H'},
    ]},
    "3": {"id": "getprefvalue", "structure": [
        {'name': 'value', 'len': 2, 'decode': '<H'},
    ]},
    "5": {"id": "setprefvalue", "structure": [
    ]},
}

rssicheck_api_replies = {
    "3": {"id": "startcheck", "structure": [
        {'name': 'remote', 'len': 2, 'decode': '<h'},
        {'name': 'local', 'len': 2, 'decode': '<h'},
    ]},
    "5": {"id": "roundtrip", "structure": [
        {'name': 'rssi', 'len': 2, 'decode': '<h'},
    ]},
}

flash_grp_api_replies = {
    "1": {"id": "getmd5", "structure": [
        {'name': 'erased', 'len': 1, 'deocde': '<B'},
        {'name': 'md5', 'len': None},
    ]},
    "2": {"id": "erase", "structure": [
        {'name': 'result', 'len': 1, 'decode': '<B'},
    ]},
    "3": {"id": "write", "structure": [
        {'name': 'error', 'len': 1, 'decode': '<B'},
    ]},
    "4": {"id": "eboot", "structure": [
    ]},
}

api_replies = {
    "1": {"id": "echo", "structure": [
        {'name': 'echo', 'len': None}
    ]},
    "3": {"id": "firm", "structure": [
        {'name': 'revision', 'len': None}
    ]},
    "5": {"id": "nodeId", "structure": [
        {'name': 'serial', 'len': 4, 'decode': '<I'}
    ]},
    "7": {"id": "nodetag", "structure": [
        {'name': 'tag', 'len': None}
    ]},
    "9": {"id": "nodetagSet", "structure": [
    ]},
    #"7": {"id": "analogIn", "structure": [
    #    {'name': 'value', 'len': 2, 'decode': '<H'}
    #]},
    #"9": {"id": "analogOut", "structure": [
    #    {'name': 'channel', 'len': 1, 'decode': 'B'},
    #    {'name': 'value', 'len': 2, 'decode': '<H'}
    #]},
    "11": {"id": "updateStart", "structure": [
        {'name': 'error', 'len': 1, 'decode': '<B'},
    ]},
    "13": {"id": "updateChunk", "structure": [
        {'name': 'error', 'len': 1, 'decode': 'B'},
        {'name': 'remaining', 'len': 4, 'decode': '<I'},
        {'name': 'progress', 'len': 4, 'decode': '<I'},
        {'name': 'bufferlen', 'len': 4, 'decode': '<I'}
    ]},
    "15": {"id": "updateDigest", "structure": [
        {'name': 'error', 'len': 1, 'decode': '<B'},
    ]},
    "17": {"id": "updateMemMD5", "structure": [
        {'name': 'result', 'len': 1, 'decode': '<B'},
        {'name': 'remaining', 'len': 4, 'decode': '<I'},
        {'name': 'progress', 'len': 4, 'decode': '<I'},
        {'name': 'bufferlen', 'len': 4, 'decode': '<I'}
    ]},
    "19": {"id": "logDestination", "structure": [
        {'name': 'serial', 'len': 4, 'decode': '<I'},
    ]},
    "21": {"id": "setLogDestination", "structure": [
    ]},
    "23": {"id": "custom", "structure": [
        {'name': 'payload', 'len': None}
    ]},
    "25": {"id": "reboot", "structure": [
    ]},

    "27": {"id": "discovery", "submenu": discovery_api_replies},

    "29": {"id": "rssicheck", "submenu": rssicheck_api_replies},

    "31": {"id": "spiflash", "submenu": flash_grp_api_replies},

    "33": {"id": "filterGroups", "structure": [
        {'name': 'serial', 'len': 4, 'decode': '<I'},
    ]},
    "35": {"id": "setFilterGroups", "structure": []},
    "39": [
        {
            "id": "serviceEntitiesCount", "structure": [
                {"name": "all", "len": 1, "decode": "B"},
                {"name": "sensors", "len": 1, "decode": "B"},
                {"name": "binaries", "len": 1, "decode": "B"},
                {"name": "switches", "len": 1, "decode": "B"},
                {"name": "lights", "len": 1, "decode": "B"},
            ],
        },
        {
            "id": "serviceEntitiesCount", "structure": [
                {"name": "all", "len": 1, "decode": "B"},
                {"name": "sensors", "len": 1, "decode": "B"},
                {"name": "binaries", "len": 1, "decode": "B"},
                {"name": "switches", "len": 1, "decode": "B"},
                {"name": "lights", "len": 1, "decode": "B"},
                {"name": "texts", "len": 1, "decode": "B"},
            ]
        }
    ],
    "41": {
        "id": "serviceEntityHash", "structure": [
            {"name": "hash", "len": 2, "decode": "<H"},
            {"name": "info", "len": None},
        ]
    },
    "43": [
        {
            "id": "serviceEntityState", "structure": [
                {"name": "value", "len": 2, "decode": "<h"},
            ]
        }, {
            "id": "serviceEntityState", "structure": [
            {"name": "type", "len": 1, "decode": "B"},
            {"name": "value", "len": None},
        ]
        },
    ],
    "45": {
        "id": "serviceEntityStateSet", "structure": [
        ]
    },
    "47": {
        "id": "serviceEntityPrefsSet", "structure": [
        ]
    },

    "49": {"id": "entities", "submenu": entities_api_replies},

    "57": {
        "id": "logevent", "structure": [
            {"name": "level", "len": 2, "decode": "<H"},
            {"name": "from", "len": 4, "decode": "<I"},
            {"name": "line", "len": None}
        ]
    },
    "117": {"id": "beacons", "structure": [
        {'name': 'serial', 'len': 4, 'decode': '<I'},
        {'name': 'rssi', 'len': 2, 'decode': '<h'}
    ]},
    "127": {"id": "error", "structure": [
        {'name': 'data', 'len': None}
    ]}
}


