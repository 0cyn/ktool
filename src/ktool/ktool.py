#
#  ktool | ktool
#  ktool.py
#
#  Outward facing API
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

from typing import Dict, Union, BinaryIO

from .generator import TBDGenerator
from .headers import HeaderGenerator
from .objc import ObjCImage
from .dyld import Dyld, Image
from .macho import Slice, MachOFile
from .util import TapiYAMLWriter


def load_macho_file(fp) -> MachOFile:
    return MachOFile(fp)


def load_image(fp: Union[BinaryIO, MachOFile], slice_index=0, load_symtab=True, load_imports=True, load_exports=True) -> Image:

    if not isinstance(fp, MachOFile):
        macho_file = MachOFile(fp)
    else:
        macho_file = fp
    macho_slice: Slice = macho_file.slices[slice_index]

    return Dyld.load(macho_slice, load_symtab=load_symtab, load_imports=load_imports, load_exports=load_exports)


def load_objc_metadata(image: Image) -> ObjCImage:
    return ObjCImage(image)


def generate_headers(objc_image: ObjCImage, sort_items=False) -> Dict[str, str]:
    out = {}

    if sort_items:
        for objc_class in objc_image.classlist:
            objc_class.methods.sort(key=lambda h: h.signature)
            objc_class.properties.sort(key=lambda h: h.name)
            if objc_class.metaclass is not None:
                objc_class.metaclass.methods.sort(key=lambda h: h.signature)

        for objc_proto in objc_image.protolist:
            objc_proto.methods.sort(key=lambda h: h.signature)
            objc_proto.opt_methods.sort(key=lambda h: h.signature)

    for header_name, header in HeaderGenerator(objc_image).headers.items():
        out[header_name] = str(header)

    return out


def generate_text_based_stub(image: Image, compatibility=True) -> str:
    generator = TBDGenerator(image, compatibility)
    return TapiYAMLWriter.write_out(generator.dict)
