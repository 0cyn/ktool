Structs
---------------------

..
   I wrote a generator to make creating these struct field definition tables easier

..
   https://gist.github.com/KritantaDev/11e2d0acfaacf26e6cf6016fc7b146cd


MachO Structs
*********************

fat_header
=====================

Represents the first 8 bytes of a MachO File

.. list-table:: 
    :widths: 5 1 10

    * - Field
      - Size 
      - Description 
    * - magic 
      - 4 
      - File magic. For a fat file, will always be 0xCAFEBABE
    * - nfat_archs
      - 4
      - Number of fat_archs in the file


fat_arch
=====================

At the beginning of a MachO File, after the header, several fat_arch structs are located, containing information about the slices within the file.

.. list-table:: 
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cputype
     - 4
     - CPUType Item
   * - cpusubtype
     - 4
     - CPU Subtype Item
   * - offset 
     - 4
     - Offset in file of the slice 
   * - size 
     - 4 
     - Size in bytes of the slice 
   * - align 
     - 4 
     - Address alignment of struct, as a power of 2 (2^align).


Dyld Structs
*********************

dyld_header
=====================

First 32 bytes of a Slice/Thin MachO File

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - magic
     - 4
     - File magic (0xFEEDFACE/0xFEEDFACF)
   * - cputype
     - 4
     - CPU Type
   * - cpusubtype
     - 4
     - CPU Subtype
   * - filetype
     - 4
     - ?
   * - loadcnt
     - 4
     - Number of load commands
   * - loadsize
     - 4
     - Size of load commands
   * - flags
     - 4
     - ?
   * - void
     - 4
     - ?


Load commands
*********************

dylib_command
=====================

Command that represents a dylib

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load command
   * - cmdsize
     - 4
     - Size of load command (including string in dylib struct)
   * - dylib
     - 4
     - CPU Subtype
   * - filetype
     - 4
     - ?

dylib
^^^^^^^^^^^^^^^^^^^^^

Struct representing a dylib

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - name
     - 4
     - lc_str Offset of the load command string from the beginning of the dylib_command struct
   * - timestamp
     - 4
     - ?
   * - current_version
     - 4
     - ?
   * - compatibility_version
     - 4
     - ?

dylinker_command
=====================

Name of the dynamic linker (/bin/dyld)

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of Load Command
   * - name
     - 4
     - lc_str name of Linker (This will usually just be dyld)

entry_point_command
=====================

Command indicating the entry point of the binary

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of load command
   * - entryoff
     - 8
     - Offset of the entry point in the file
   * - stacksize
     - 8
     - ?

rpath_command
=====================

Specifies the runtime search path (think iOS Apps, with `./Frameworks` directories)

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of load command
   * - path
     - 4
     - lc_str Offset of the rpath string from the beginning of the load command


dyld_info_command
=====================

Contains the offsets of several dyld-related tables

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load command
   * - cmdsize
     - 4
     - Size of load command
   * - rebase_off
     - 4
     - Offset of rebase commands
   * - rebase_size
     - 4
     - Size of rebase commands
   * - bind_off
     - 4
     - Offset of Binding commands
   * - bind_size
     - 4
     - Size of Binding commands
   * - weak_bind_off
     - 4
     - Offset of weak binding commands
   * - weak_bind_size
     - 4
     - Size of weak binding commands
   * - lazy_bind_off
     - 4
     - Offset of lazy binding commands
   * - lazy_bind_size
     - 4
     - Size of lazy binding commands
   * - export_off
     - 4
     - Export table offset
   * - export_size
     - 4
     - Export table size


symtab_command
=====================

Holds offsets of the symbol table and the string table it uses.

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of load command
   * - symoff
     - 4
     - Offset of Symbol Table
   * - nsyms
     - 4
     - Number of entries in the symbol table
   * - stroff
     - 4
     - Offset of String Table
   * - strsize
     - 4
     - Size of String Table

dysymtab_command
=====================

TODO

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of Load Command
   * - ilocalsym
     - 4
     - ?
   * - nlocalsym
     - 4
     - ?
   * - iextdefsym
     - 4
     - ?
   * - nextdefsym
     - 4
     - ?
   * - tocoff
     - 4
     - ?
   * - ntoc
     - 4
     - ?
   * - modtaboff
     - 4
     - ?
   * - nmodtab
     - 4
     - ?
   * - extrefsymoff
     - 4
     - ?
   * - nextrefsyms
     - 4
     - ?
   * - indirectsymoff
     - 4
     - Offset of indirect symbol table
   * - nindirectsyms
     - 4
     - Number of indirect symbols in table
   * - extreloff
     - 4
     - ?
   * - nextrel
     - 4
     - ?
   * - locreloff
     - 4
     - ?
   * - nlocrel
     - 4
     - ?

uuid_command
=====================

Contains the UUID of the library

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of load command
   * - uuid
     - 16
     - UUID of the Library

build_version_command
=====================

Contains build version and versions of tools used to compile this library/bin

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of load command
   * - platform
     - 4
     - (Enum) platform the library was compiled for
   * - minos
     - 4
     - Hex XX YY ZZZZ Version of the OS (xx.yy.zzzz)
   * - sdk
     - 4
     - Hex XX YY ZZZZ Version of the SDK used to compile
   * - ntools
     - 4
     - Number of tool commands following this command

source_version_command
=====================

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load command
   * - cmdsize
     - 4
     - Size of load command
   * - version
     - 8
     - ?

sub_client_command
=====================

Libraries can specify subclients indicating which binaries are allowed to link to this library

A process not within this group will be killed if it tries to link this library

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of load command
   * - offset
     - 4
     - lc_str Offset of Name of subclient from beginning of load command


linkedit_data_command
=====================

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of load command
   * - dataoff
     - 4
     - Offset of LINKEDIT data
   * - datasize
     - 4
     - Size of LINKEDIT data


segment_command_64
=====================

Represents a segment in the mach-o file

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load Command
   * - cmdsize
     - 4
     - Size of load command including following segment_64 commands
   * - segname
     - 16
     - Null-byte terminated string within the struct, containing the name of the segment
   * - vmaddr
     - 8
     - Address in the virtual memory mapping of the segment
   * - vmsize
     - 8
     - Size of the segment in the Virtual Memory map
   * - fileoff
     - 8
     - Offset of the segment in the on-disk file
   * - filesize
     - 8
     - Size of the segment in the on-disk file
   * - maxprot
     - 4
     - ?
   * - initprot
     - 4
     - ?
   * - nsects
     - 4
     - Number of section_64 commands within this command
   * - flags
     - 4
     - ?

section_64
=====================

Represents a section in the segment

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - sectname
     - 16
     - null-terminated C string Name of the section
   * - segname
     - 16
     - null-terminated C string Name of the containing segment
   * - addr
     - 8
     - VM Address of the section
   * - size
     - 8
     - VM Size of the section
   * - offset
     - 4
     - File address of the section
   * - align
     - 4
     - ?
   * - reloff
     - 4
     - ?
   * - nreloc
     - 4
     - ?
   * - flags
     - 4
     - ?
   * - reserved1
     - 4
     - ?
   * - reserved2
     - 4
     - ?
   * - reserved3
     - 4
     - ?