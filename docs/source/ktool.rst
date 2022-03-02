ktool Public API
---------------------------------

ktool
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the majority of use cases, this is the only module you should ever need to import. (solely 'import ktool')

These functions perform all of the heavy lifting of loading in a file and processing its metadata. 

This module also imports many classes from other files in this module you may need to use. 

.. py:function:: load_macho_file(fp: Union[BinaryIO, BytesIO], use_mmaped_io=True) -> MachOFile

   Takes a bare file or BytesIO object and loads it as a MachOFile.
   You likely dont need this unless you only care about loading info about basic slices;
   The MachOFile is still accessible from the `Image` class.

.. py:function:: load_image(fp: Union[BinaryIO, MachOFile, Slice, BytesIO], slice_index=0, load_symtab=True, load_imports=True, load_exports=True, use_mmaped_io=True) -> Image

   Take a bare file, MachOFile, BytesIO, or Slice, and load MachO/dyld metadata about that item

.. py:function:: macho_verify(fp: Union[BinaryIO, MachOFile, Slice, Image]) -> None

   Disable "ignore malformed" flag if set, then try loading the Image, throwing a MalformedMachOException if anything fails

.. py:function:: load_objc_metadata(image: Image) -> ObjCImage

   Load an ObjCImage object (containing the processed ObjC metadata) from an Image

.. py:function:: generate_headers(objc_image: ObjCImage, sort_items=False) -> Dict[str, Header]

   Generate a list of "Header Name" -> Header objects from an ObjC Image

.. py:function:: generate_text_based_stub(image: Image, compatibility=True) -> str

   Generate a Text-Based-Stub (.tbd) from a MachO

.. py:function:: macho_combine(slices: List[Slice]) -> BytesIO

   Create a Fat MachO from thin MachO slices, returned as a BytesIO in-memory representation



ktool.macho
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


MachOFile
=================================

The MachOFile is the early base responsible for loading super basic info about the MachO and populating the Slice objects.

These Slices handle actually reading/parsing data from the MachO once they've been loaded.

We from this point on essentially "ignore" the MachOFile, for the sake of not overcomplicating the File Offset -> Address translation, and make code more readable and less confusing.


.. py:class:: MachOFile(file: Union[BinaryIO, BytesIO], use_mmaped_io=True)

   Where file is a file pointer or BytesIO object. use_mmaped_io should be False when operating on BytesIO

   ktool.load_macho_file() should be used in place of manually initializing this.

.. py:attribute:: MachOFile.file: Union[mmap, BinaryIO]

   File object underlying functions should use to load data.

.. py:attribute:: MachOFile.slices: List[Slice]

   List of slices within this MachO file

.. py:attribute:: MachOFile.type: MachOFileType

   FAT or THIN filetype

.. py:attribute:: MachOFile.uses_mmaped_io: bool

   Whether the MachOFile should be operated on using mmaped IO (and whether .file is a mmap object)

.. py:attribute:: MachOFile.magic: bytes

   Magic at the beginning of the file (FAT_MAGIC/MH_MAGIC)


Slice
=================================

.. py:class:: Slice(macho_file: MachOFile, arch_struct: fat_arch = None, offset = 0)

   This class, loaded by MachOFile, represents an underlying slice.

   MachOFile should handle loading it, and you shouldn't need to ever initialize it yourself.

   .. py:attribute:: macho_file

      Underlying MachO File this struct is located in

   .. py:attribute:: arch_struct

      If this slice was loaded from a fat_macho, the arch_struct representing it in the Fat Header

   .. py:attribute:: offset

      File offset for this slice

   .. py:attribute:: type

      `CPUType` of the Slice

   .. py:attribute:: subtype

      `CPUSubType` of the Slice

   .. py:attribute:: size

      Size of the slice

   .. py:attribute:: byte_order

      Byte Order ("little" or "big") of the Slice.

   .. py:method:: load_struct(address: int, struct_type: Struct, endian="little")

      Load a struct from `address`

   .. py:method:: get_int_at(addr: int, count: int, endian="little") -> int

      Load int from an address.

      The code for this method (and the rest of the `get_` methods) will either use mmapped or non-mmapped io based on the MachOFile's .use_mmaped_io attribute.

   .. py:method:: get_bytes_at(addr: int, count: int, endian="little") -> int

      Load `count` bytes from `address`

   .. py:method:: get_str_at(addr: int, count: int) -> str

      Load a fixed-length string from `address` with the size `length`.

   .. py:method:: get_cstr_at(addr: int, limit: int) -> str

      Load a null-terminated string from `address`, stopping after `limit` if `limit` is not 0

   .. py:method:: decode_uleb128(address: int) -> (value, new_address)

      Decode uleb from starting address, returning the value, and the end address of the leb128

   .. py:method:: patch(address: int, raw: bytes) -> None

      Patch Bytes in the slice


Segment
=================================

.. py:class:: Segment(image, cmd: Union[segment_command, segment_command_64])

   Object Representation of a MachO Segment

.. py:attribute:: Segment.name: str

   Segment Name

.. py:attribute:: Segment.sections: Dict[str, Section]

   Dictionary of Sections within this Segment.

   You can get a list of Sections using `my_segment.sections.values()`

.. py:attribute:: Segment.cmd

   Underlying segment_command (or segment_command_64)

.. py:attribute:: Segment.vm_address

   VM Address of the Segment

.. py:attribute:: Segment.file_address

   File address (in the Slice) of the Segment

.. py:attribute:: Segment.size

   Size of the segment


Section
=================================

.. py:class:: Section(segment: Segment, Union[section, section_64]

   Section within a MachO Segment

.. py:attribute:: Section.name: str

   Name of the Section

.. py:attribute:: Section.vm_address: int

   VM Address of the Section

.. py:attribute:: Section.file_address: int

   File Address (within the Slice) of the Section

.. py:attribute:: Section.size: int

   Size of the Section


_VirtualMemoryMap
=================================

This is the translation table used by the Image class to translate VM addresses to their File counterparts

It's accessible via Image().vm . You shouldn't really ever need or use this directly unless you're working on ktool itself, but I cant tell you what to do :)

.. py:class:: _VirtualMemoryMap(macho_slice: Slice)

   VM Map. Initialization does nothing, you will need to populate it yourself with segments/sections

.. py:method:: _VirtualMemoryMap.vm_check(vm_address) -> bool

   Check whether a specified address is within the VM address ranges

.. py:method:: _VirtualMemoryMap.get_file_address(vm_address: int, segment_name: str=None) -> int

   Translate a vm address to a file address (if possible). Passing segment_name (if you are *sure* you know which segment it should be in,) will very fractionally speed up the translation. You typically dont need to worry about this, but when performing millions of translations while loading objC metadata, there's a noticeable speed difference.

.. py:method:: _VirtualMemoryMap.add_segment(segment: Segment)

   Add a segment (or its individual sections, if it has any) to the VM Mapping.

.. py:attribute:: _VirtualMemoryMap.map: Dict[str, vm_obj]

   Map of segment/section names to namedtuples representing their address ranges

.. py:attribute:: _VirtualMemoryMap.vm_base_addr

   "Base Address" of the file. Used primarily for function starts processing. If you're familiar with dyld source, it's the equivalent to this: https://github.com/apple-opensource/ld64/blob/e28c028b20af187a16a7161d89e91868a450cadc/src/other/dyldinfo.cpp#L156

.. py:attribute:: _VirtualMemoryMap.sorted_map

   VM Object Map sorted in order of addresses


ktool.dyld
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Image
=================================

This class represents the Mach-O Binary as a whole.

It's the root object in the massive tree of information we're going to build up about the binary

This class on its own does not handle populating its fields.
The Dyld class set is responsible for loading in and processing the raw values to it.

You should obtain an instance of this class using the public `ktool.load_image()` API

.. py:class:: Image(macho_slice: Slice)

   This class represents the Mach-O Binary as a whole.

   It can be initialized without a Slice if you are building a Mach-O Representation from runtime data.
   
   .. py:attribute:: macho_header
      :type: ImageHeader
   
      if Image was initialized with a macho_slice, this attribute will contain an ImageHeader with basic info loaded from the Mach-O Header
   
   .. py:attribute:: base_name
      :type: str
   
      "basename" of the Image's install name ("SpringBoard" for "/System/Library/Frameworks/SpringBoard.framework/SpringBoard")
   
   .. py:attribute:: install_name
      :type: str
   
      Install Name of the image (if it exists). "" if the library does not have one.
   
   .. py:attribute:: linked_images
      :type: List[ExternalDylib]
   
      List of `ExternalDylib`s this image links
   
   .. py:attribute:: segments
      :type: Dict[str, Segment]
   
      Dictionary mapping `segment_name` to `Segment`.
      You can obtain a list of segments from this using `segments.values()`
   
   .. py:attribute:: imports
      :type: List[Symbol]
   
      List of `Symbol` objects this image imports
   
   .. py:attribute:: exports
      :type: List[Symbol]
   
      List of `Symbol` objects this image exports
   
   .. py:attribute:: symbols
      :type: Dict[int, Symbol]
   
      Address -> Symbol map for symbols embedded within this image
   
   .. py:attribute:: import_table
      :type: Dict[int, Symbol]
   
      Address -> Symbol map for imported Symbols
   
   .. py:attribute:: export_table
      :type: Dict[int, Symbol]
   
      Address -> Symbol map for exported Symbols
   
   .. py:attribute:: function_starts
      :type: List[int]
   
      List of function start addresses
   
   .. py:attribute:: uuid
      :type: bytes
   
      Raw bytes representing the Image's UUID if it has one.
   
   .. py:attribute:: vm
      :type: _VirtualMemoryMap
   
      Reference to the VM translation table object the `Image` uses. You probably shouldn't use this, but it's here if you need it.
   
   .. py:attribute:: dylib
      :type: ExternalDylib
   
      ExternalDylib object that (admittedly, somewhat confusingly) actually represents this Image itself.
   
   .. py:method:: vm_check(address: int) -> bool
   
      Check if an address resolves within the VM translation table
   
   .. py:method:: get_int_at(address: int, length: int, vm=False, section_name=None) -> int
   
      Method that performs VM address translation if `vm` is true, then falls through to Slice().get_int_at(address, length)
   
   .. py:method:: get_bytes_at(address: int, length: int, vm=False, section_name=None) -> int
   
      Method that performs VM address translation if `vm` is true, then falls through to Slice().get_bytes_at(address, length)
   
   .. py:method:: load_struct(address: int, struct_type: Struct, vm=False, section_name=None, endian="little", force_reload=True) -> Struct
   
      Load a struct of `struct_type` from `address`, performing address translation if `vm`.
      This struct will be cached; if we need to for some reason reload the struct at this address, pass `force_reload=True`
   
   .. py:method:: get_str_at(address: int, length: int, vm=False, section_name=None) -> str
   
      Load a fixed-length string from `address` with the size `length`.
   
   .. py:method:: get_cstr_at(address: int, limit: int = 0, vm=False, section_name=None) -> str
   
      Load a null-terminated string from `address`, stopping after `limit` if `limit` is not 0
   
   .. py:method:: decode_uleb128(address: int) -> (value, new_address)
   
      Decode uleb from starting address, returning the value, and the end address of the leb128

ImageHeader
=================================

.. py:class:: ImageHeader

   the class method `from_image()` should be used for loading this class.

   .. py:classmethod:: from_image(macho_slice) -> ImageHeader

      Load an ImageHeader from a macho_slice

   .. py:attribute:: is64: bool 

      Is this image a 64 bit Mach-O? 

   .. py:attribute:: dyld_header: Union[dyld_header, dyld_header_64]

      Dyld Header struct 

   .. py:attribute:: filetype: MH_FILETYPE

      MachO Filetype 

   .. py:attribute:: flags: MH_FLAGS

      MachO File Flags 

   .. py:attribute:: load_commands: List[load_command]

      List of load command structs 


Dyld
=================================

.. py:class:: Dyld 

   Note: Do not use this! Use ktool.load_image()!!

   This class takes our initialized "Image" object, parses through the raw data behind it, and fills out its properties.

   .. py:classmethod:: load(macho_slice: Slice, load_symtab=True, load_imports=True, load_exports=True) -> Image

      Take a MachO Slice object and Load an image. 


LD64
=================================

.. py:class:: LD64 

   .. py:classmethod:: insert_load_cmd(image: Image, lc: LOAD_COMMAND, fields: List, index=-1)

      Insert a load command into the MachO header and patch the image in memory to reflect this.

      If index is -1, it will be inserted at the end. 

   .. py:classmethod:: insert_load_cmd_with_str(image: Image, lc: LOAD_COMMAND, fields: List, suffix: str, index=-1)

      Insert a load command which contains a string suffix (e.g LOAD_DYLIB commands)

   .. py:classmethod:: remove_load_command(image: Image, index)

      Remove Load Command at `index`


ExternalDylib
=================================

.. py:class:: ExternalDylib(image: Image, cmd)

   .. py:attribute:: install_name: str

      Full Install name of the image 

   .. py:attribute:: local: bool

      Whether this "ExternalDylib" is actually local (ID_DYLIB)


Symbol
=================================

.. py:class:: Symbol 

   Initializing this class should be done with either the `.from_image()` or `.from_values()` class methods

   .. py:classmethod:: from_image(image: Image, cmd: symtab_command, entry: NList32 or NList64 item)

      Generate a Symbol loaded from the Symbol Table. Any other method of loading symbols needs to use .from_values()

   .. py:classmethod:: from_values(fullname: str, address: int, external=False, ordinal=0)

      Create a symbol from preprocessed or custom values. 


SymbolTable
=================================
   
.. py:class:: SymbolTable(image: Image, cmd: symtab_command)

   Representation of the Symbol Table pointed to by the LC_SYMTAB command

   .. py:attribute:: ext: List[Symbol]

      List of external symbols 

   .. py:attribute:: table: List[Symbol]

      Entire list of symbols in the table 


ChainedFixups
=================================

Chained Fixup Processor class. 

.. py:class:: ChainedFixups 

   .. py:classmethod:: from_image(image: Image, chained_fixup_cmd: linkedit_data_command) -> ChainedFixups

      Load chained fixups from the relevant command
   
   .. py:attribute:: symbols: List[Symbol]

      Symbols loaded from within the chained fixups 


ExportTrie
=================================

Export Trie Processor class.

.. py:class:: ExportTrie 

   .. py:classmethod:: from_image(image: Image, export_start, export_size) -> ExportTrie

      Load chained fixups from the relevant command
   
   .. py:attribute:: symbols: List[Symbol]

      Symbols loaded from within the chained fixups 


BindingTable
=================================

Binding Table Processor

.. py:class:: BindingTable(image: Image, table_start: int, table_size: Int)

   .. py:attribute:: symbol_table: List[Symbol]



ktool.objc
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Everything in the ObjC module implements the "Constructable" Base class

This theoretically allows it to be used to generate headers from metadata dumped using ObjC Runtime Functions, and it has been tested and confirmed functional at doing that :)

ObjCImage
=================================

.. py:class:: ObjCImage 

   .. py:classmethod:: from_image(image: Image) -> ObjCImage

      Take an Image class and process its ObjC Metadata

   .. py:classmethod:: from_values(image: Image, name: str, classlist: List[Class], catlist: List[Category] protolist: List[Protocol], type_processor=None) -> ObjCImage

      Create an ObjCImage instance from somehow preloaded values 

   .. py:attribute:: image: Image 

   .. py:attribute:: name: str

      Image Install Base Name

   .. py:attribute:: classlist: List[Class]

   .. py:attribute:: catlist: List[Category]

   .. py:attribute:: protolist: List[Protocol]

   .. py:attribute:: class_map: Dict[int, Class]

      Map of Load addresses to Classes. Used as a cache.

   .. py:attribute:: cat_map: Dict[int, Category]

      Map of Load addresses to Categories. ''

   .. py:attribute:: prot_map: Dict[int, Protocol]

      Map of Load addresses to protocols 

   .. py:method:: vm_check(address: int) -> bool
   
      Check if an address resolves within the VM translation table
   
   .. py:method:: get_int_at(address: int, length: int, vm=False, section_name=None) -> int
   
      Method that performs VM address translation if `vm` is true, then falls through to Slice().get_int_at(address, length)
   
   .. py:method:: load_struct(address: int, struct_type: Struct, vm=True, section_name=None, endian="little", force_reload=True) -> Struct
   
      Load a struct of `struct_type` from `address`, performing address translation if `vm`.
      This struct will be cached; if we need to for some reason reload the struct at this address, pass `force_reload=True`
   
   .. py:method:: get_str_at(address: int, length: int, vm=True, section_name=None) -> str
   
      Load a fixed-length string from `address` with the size `length`.
   
   .. py:method:: get_cstr_at(address: int, limit: int = 0, vm=True, section_name=None) -> str
   
      Load a null-terminated string from `address`, stopping after `limit` if `limit` is set


Class 
=================================

.. py:class:: Class

   .. py:classmethod:: from_image(image: Image, class_ptr: int, meta=False) -> Class

      Take a location of a pointer to a class (For example, the location of an entry in the __objc_classlist section) and process its metadata

   .. py:classmethod:: from_values(name, superclass_name, methods: List[Method], properties: List['Property'], ivars: List['Ivar'],protocols: List['Protocol'], load_errors=None, structs=None) -> Class

      Create a Class instance from somehow preloaded values 

   .. py:attribute:: name: str 

      Classname 
   
   .. py:attribute:: meta: bool 

      Whether this method is a MetaClass (these hold "class methods")

   .. py:attribute:: superclass: str 

      Name of the superclass 

   .. py:attribute:: load_errors: List[str]

      List of errors encountered while loading metadata 

   .. py:attribute:: struct_list: List[Struct_Representation]

      List of structs embedded in this class. Will eventually be used for header specific struct resolution 

   .. py:attribute:: methods: List[Method]

   .. py:attribute:: properties: List[Property] 

   .. py:attribute:: protocols: List[Protocol]

   .. py:attribute:: ivars: List[Ivar]


Method
=================================
.. py:class:: Method

   .. py:classmethod:: from_image(objc_image: ObjCImage, sel_addr, types_addr, is_meta, vm_addr, rms, rms_are_direct)

   .. py:classmethod:: from_values(name, type_encoding, type_processor=None)

   .. py:attribute:: meta: bool 

      Class method instead of Instance method 

   .. py:attribute:: sel: str 

      Selector 

   .. py:attribute:: type_string 

      Unparsed Type String 

   .. py:attribute:: types: List[Type]

      List of types 

   .. py:attribute:: return_string: str 

      Type of the return value 

   .. py:attribute:: arguments: List[str] 

      List of the types of arguments 

   .. py:attribute:: signature: str

      Fully built method signature

Property
=================================

.. py:class:: Property 

   .. py:classmethod:: from_image(objc_image: ObjCImage, property: objc2_prop)

   .. py:classmethod:: from_values(name, attr_string, type_processor=None)

   .. py:attribute:: name: str
   
   .. py:attribute:: type: str

   .. py:attribute:: is_id: bool 

      Is the type an ObjC class 

   .. py:attribute:: attributes 

      Property Attributes (e.g. nonatomic, readonly, weak)

   .. py:attribute:: ivarname 

      Name of the ivar backing this property 

Ivar
=================================

.. py:class:: Ivar 

   .. py:classmethod:: from_image(objc_image: ObjCImage, ivar: objc2_ivar)

   .. py:classmethod:: from_values(name, type_encoding, type_processor=None)

   .. py:attribute:: name: str 

   .. py:attribute:: is_id: bool 

      Whether Ivar type is an ObjC Class

   .. py:attribute:: type: str 

      Renderable type

Category 
=================================

.. py:class:: Category 

   .. py:classmethod:: from_image(objc_image: ObjCImage, category_ptr)

   .. py:classmethod:: from_values(classname, name, methods, properties, load_errors=None, struct_list=None)

   .. py:attribute:: name 

      Category Name (e.g., if you defined a category as "UIColor+MyAdditions", it would be "MyAdditions")

   .. py:attribute:: classname

      Original class being extended ("UIColor" in "UIColor+MyAdditions")

   .. py:attribute:: load_errors: List[str]

      List of errors encountered while loading metadata 

   .. py:attribute:: struct_list: List[Struct_Representation]

      List of structs embedded in this category. Will eventually be used for header specific struct resolution 

   .. py:attribute:: methods: List[Method]

   .. py:attribute:: properties: List[Property] 

   .. py:attribute:: protocols: List[Protocol]

   
Protocol 
=================================

.. py:class:: Protocol

   .. py:classmethod:: from_image(objc_image: ObjCImage, category_ptr)

   .. py:classmethod:: from_values(classname, name, methods, properties, load_errors=None, struct_list=None)

   .. py:attribute:: name 

      Category Name (e.g., if you defined a category as "UIColor+MyAdditions", it would be "MyAdditions")

   .. py:attribute:: classname

      Original class being extended ("UIColor" in "UIColor+MyAdditions")

   .. py:attribute:: load_errors: List[str]

      List of errors encountered while loading metadata 

   .. py:attribute:: struct_list: List[Struct_Representation]

      List of structs embedded in this protocol. Will eventually be used for header specific struct resolution 

   .. py:attribute:: methods: List[Method]

   .. py:attribute:: opt_methods: List[Method]

      Methods that may (but are not required to) be implemented by classes conforming to this protocol

   .. py:attribute:: properties: List[Property] 


Type Processing / Encoding
=================================

.. py:class:: TypeProcessor()

   Responsible for cacheing loaded structs (for dumping) and types, and for processing them as well. 

   .. py:attribute:: structs: Dict[str, Struct_Representation]

      Dictionary of Struct Name -> Struct Representations stored for dumping 
   
   .. py:attribute:: type_cache: Dict[str, List[Type]]

      Cache of processed typestrings (to avoid re-parsing identical typestrings)

   .. py:method:: process(type_to_process: str) -> List[Type]

      Process a typestring, returning a list of types embedded in it. 
      

.. py:class:: Type(processor: TypeProcessor, type_string, pointer_count=0)

   For parsing and saving a specific type encoding. 

   Calling str(a_type_instance) will render the type as it appears in headers. 

   .. py:attribute:: type: EncodedType

      Enum containing either NORMAL, NAMED, or STRUCT 
   
   .. py:attribute:: value: Union[str, Struct_Representation]

      Renderable text representing the type 

.. py:class:: Struct_Representation(processor: TypeProcessor, type_string)

   Can be embedded in Type().value for representing a struct embedded in a type string. 

   Calling str(instance) will generate renderable text for headers. 

   .. py:attribute:: name: str
   
   .. py:attribute:: fields: List[str]

      Encoded Field Types 
   
   .. py:attribute:: field_names: List[str]

      Field names (if they were embedded also, they aren't always)
