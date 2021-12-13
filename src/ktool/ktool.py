#
#  ktool | ktool
#  ktool.py
#
#  Outward facing API
#
#  Some of these functions are only one line long, but the point is to standardize an outward facing API that allows
#   me to refactor and change things internally without breaking others' scripts.
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

from typing import Dict, Union, BinaryIO, List
from io import BytesIO

from .dyld import Dyld, Image
from .generator import TBDGenerator, FatMachOGenerator
from .headers import HeaderGenerator
from .macho import Slice, MachOFile
from .objc import ObjCImage
from .util import TapiYAMLWriter, ignore, log


def load_macho_file(fp: BinaryIO, use_mmaped_io=True) -> MachOFile:
    """
    This function takes a bare file and loads it as a MachOFile.

    File should be opened with 'rb'

    :param fp: BinaryIO object
    :param use_mmaped_io: Should the MachOFile be loaded with a mmaped-io-backend? Leaving this enabled massively
                            improves load time and IO performance, only disable if your system doesn't support it
    :return:
    """
    return MachOFile(fp, use_mmaped_io=use_mmaped_io)


def reload_image(image: Image) -> Image:
    """
    Reload an image (properly updates internal representations after patches)

    :param image:
    :return:
    """
    # This is going to be horribly slow. Dyld class needs refactored to have a better way to do this or ideally just
    #   not fuck things up and require a reload every time we make a patch.
    return load_image(image.slice)


def load_image(fp: Union[BinaryIO, MachOFile, Slice], slice_index=0, load_symtab=True, load_imports=True,
               load_exports=True, use_mmaped_io=True) -> Image:
    """
    Take a bare file, MachOFile, or Slice, and load MachO/dyld metadata about that item

    :param fp: a bare file, MachOFile, or Slice to load.
    :param slice_index: If a Slice is not being passed, and a file or MachOFile is a Fat MachO, which slice should be loaded?
    :param use_mmaped_io: If a bare file is being passed, load it with mmaped IO?
    :param load_symtab: Load the symbol table if one exists. This can be disabled for targeted loads, for speed.
    :param load_imports: Load imports if they exist. This can be disabled for targeted loads, for speed.
    :param load_exports: Load exports if they exist. This can be disabled for targeted loads, for speed.
    :return: Returns a loaded Image object
    :rtype: Image
    """
    if isinstance(fp, MachOFile):
        macho_file = fp
        macho_slice: Slice = macho_file.slices[slice_index]
    elif isinstance(fp, Slice):
        macho_slice = fp
    else:
        macho_file = load_macho_file(fp, use_mmaped_io=use_mmaped_io)
        macho_slice: Slice = macho_file.slices[slice_index]

    return Dyld.load(macho_slice, load_symtab=load_symtab, load_imports=load_imports, load_exports=load_exports)


def macho_verify(fp: Union[BinaryIO, MachOFile, Slice, Image]) -> None:
    """
    This function takes a variety of MachO-based objects, and loads them with malformation exceptions fully enabled.

    This can be used to verify patch code did not damage or improperly modify a MachO.

    :param fp: One of: BinaryIO, MachOFile, Slice, or Image, to load and verify
    :return:
    :raises: MalformedMachOException
    """
    should_ignore = ignore.MALFORMED

    log.info("Verifying MachO Integrity")
    ignore.MALFORMED = False

    if isinstance(fp, Image):
        load_image(fp.slice)
    elif isinstance(fp, MachOFile) or isinstance(fp, BinaryIO):
        if isinstance(fp, MachOFile):
            slices = fp.slices
        else:
            slices = load_macho_file(fp)
        for macho_slice in slices:
            load_image(macho_slice)
    else:
        load_image(fp)

    ignore.MALFORMED = should_ignore


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


def macho_combine(slices: List[Slice]) -> BytesIO:
    fat_generator = FatMachOGenerator(slices)

    fat_file = BytesIO()
    fat_file.write(fat_generator.fat_head)
    for arch in fat_generator.fat_archs:
        fat_file.seek(arch.offset)
        fat_file.write(arch.slice.full_bytes_for_slice())

    fat_file.seek(0)
    return fat_file

