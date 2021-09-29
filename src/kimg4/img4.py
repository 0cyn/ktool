#
#  ktool | kimg4
#  img4.py
#
#  This file contains functions for working with img4 files using pyaes and asn1
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

import sys
import os
import kimg4.asn1 as asn1
import random
import pyaes
import string


def asn1_serialize(input_stream, parent=None):
    """
    This is a serializer for the output of python-asn1.
    It's specifically designed for IMG4 format ASN1/DER/BER format.

    I really dont trust it, it's not very well designed, but it should work well enough.

    :param input_stream: Input asn1 decoder
    :param parent: unused element during recursion. would make things smarter.
    :return:
    """
    vals = []
    while not input_stream.eof():
        tag = input_stream.peek()
        if tag.typ == asn1.Types.Primitive:
            tag, value = input_stream.read()
            vals.append(value)
        elif tag.typ == asn1.Types.Constructed:
            input_stream.enter()
            items = asn1_serialize(input_stream, parent=asn1.Types.Constructed)
            input_stream.leave()
            vals.append(items)
    return vals


def get_keybags(fp):
    """
    Dump keybags from an IM4P file.

    This function is not smart and only supports standard img4 IM4P format files.

    :param fp:
    :return:
    """
    return_keybags = []
    im4p_decoder = asn1.Decoder()
    im4p_decoder.start(fp.read())
    kbag = asn1_serialize(im4p_decoder)[0][4]
    kbag_decoder = asn1.Decoder()
    kbag_decoder.start(kbag)
    keybags = asn1_serialize(kbag_decoder)[0]
    for keybag in keybags:
        keybag_concat = keybag[1] + keybag[2]
        keybag_hex = keybag_concat.hex().upper()
        return_keybags.append(keybag_hex)
    return return_keybags


def aes_decrypt(fp, key: str, iv: str, out):
    """
    Grabs the payload from an im4p and dumps the decrypted output to `out`

    :param fp: Input file pointer
    :param key: STRING-HEX repr of AES 256 bit key
    :param iv: STRING-HEX repr of AES 64 bit initialization vector
    :param out: Output file pointer
    :return:
    """
    iv = bytes.fromhex(iv)
    key = bytes.fromhex(key)
    decoder = asn1.Decoder()
    decoder.start(fp.read())

    # location of the raw encrypted cyphertext in the img4, probably?
    cipher = asn1_serialize(decoder)[0][3]

    # doing this is lazy
    temp_filename = '.temp_' + ''.join(random.choice(string.ascii_lowercase) for i in range(10))

    with open(temp_filename, 'wb') as outf:
        outf.write(cipher)

    # img4 are encrypted with Cipher-Block Chaining mode
    mode = pyaes.AESModeOfOperationCBC(key, iv=iv)

    file_in = open(temp_filename, 'rb')

    pyaes.decrypt_stream(mode, file_in, out)
    file_in.close()
    os.remove(temp_filename)
