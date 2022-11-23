# Multihash stub
# https://github.com/multiformats/multihash
# https://multiformats.readthedocs.io/en/latest/api/multiformats.multihash.html

MULTIHASH_BY_NAME = {
    'sha2-256': {'code': 0x12, 'len': 0x20, 'varint': [0x12]},
    'sha2-512': {'code': 0x13, 'len': 0x40, 'varint': [0x13]},
    'blake2s-256': {'code': 0xb220, 'len': 0x20, 'varint': [0xe0, 0xe4, 0x02]},
    'blake2b-512': {'code': 0xb240, 'len': 0x40, 'varint': [0xc0, 0xe4, 0x02]}
}


def wrap(name, value):
    hash_byname = MULTIHASH_BY_NAME[name]
    if hash_byname is None:
        raise Exception("Unknown")
    hash_value = bytearray(hash_byname['varint']) + bytearray([hash_byname['len']]) + bytearray(value)
    return hash_value


def unwrap(value):
    for (key, val_mh) in MULTIHASH_BY_NAME.items():
        varint = bytearray(val_mh['varint'])
        value_key = bytearray(value[0:len(varint)])
        if value_key == varint:
            len_header = len(varint) + 1
            return (key, value[len_header:])

    return None

