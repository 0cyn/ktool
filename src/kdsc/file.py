#
#  ktool | kdsc
#  file.py
#
#
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2022.
#
from typing import BinaryIO
import mmap

class MemoryCappedBufferedFileReader:
    """
    File reader that is optimistically capped at a 50mb cache
    """
    def __init__(self, fp: BinaryIO, mbs=50):
        fp.close()
        fp = open(fp.name, 'rb')
        self.filename = fp.name
        self.fp = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_COPY)
        self.chunks = []
        self.chunk_cache = {}

        self.chunk_limit = mbs

        self.chunk_size = 0x100000
        self.chunk_size_bits = (self.chunk_size - 1).bit_length()

    def __del__(self):
        self.fp.close()

    def read_null_term_string(self, address):
        self.fp.seek(address)
        val = ''.join(iter(lambda: self.fp.read(1).decode('ascii'), '\x00'))
        self.fp.seek(0)
        return val

    def read(self, address, length):
        return self.fp[address:address+length]
        return d
        page_offset = address & self.chunk_size - 1
        orig_length = length
        if self.chunk_size - page_offset < length:
            data = bytearray()
            first_page_cap = self.chunk_size - page_offset
            data += self._read(address, first_page_cap)
            length -= first_page_cap
            address += first_page_cap
            while length > self.chunk_size:
                data += self._read(address, self.chunk_size)
                address += self.chunk_size
                length -= self.chunk_size
            data += self._read(address, length)
            assert len(data) == orig_length
            return data
        else:
            return self._read(address, length)

    def _read(self, address, length) -> bytearray:
        if length == 0:
            return bytearray()

        page_offset = address & self.chunk_size - 1
        page_location = address >> self.chunk_size_bits

        try:
            data = self.chunk_cache[page_location]
        except KeyError:
            self.fp.seek(page_location)
            data = self.fp.read(self.chunk_size)
            if len(self.chunks) >= self.chunk_limit:
                del self.chunk_cache[self.chunks[0]]
                del self.chunks[0]
            self.chunk_cache[page_location] = data
            self.chunks.append(page_location)

        out = data[page_offset:page_offset+length]
        assert len(out) == length
        return out


