Quick-Start Guide
---------------------

This is documentation for getting started with the library as a component of other python projects.

Gonna try and speedrun this explanation so you can get up and running as soon as possible.

Basic Concepts to understand:
    * There are a lot of subfiles and a few modules, but :python:`import ktool` will import all of the stuff you most likely need.
    * My struct system emulates C's. Or if you don't know C, it's like someone smashed together python structs and namedtuples.

On the github, `src/ktool/ktool_script.py` is a fairly standard client for this library, and you can reference it to
figure out how to do a lot of the basic stuff this library is capable of.

Install The Library
=======================

`python3 -m pip install k2l`

To install new updates:

`python3 -m pip install --upgrade k2l`


Code Examples
=======================

Ideally this library is fairly intuitive to use, and things just work how you expect.

.. code-block:: python
   :caption: Load an image and dump the symbol list
   :emphasize-lines: 3

   import ktool

   image = ktool.load_image('my/file.dylib')
   for addr, symbol in image.symbols.items():
       print(f'{symbol.name} => {addr}')

.. code-block:: python
   :caption: Dump the classlist for an image
   :emphasize-lines: 4

   import ktool

   image = ktool.load_image('my/file.dylib')
   objc_image = ktool.load_objc_metadata(image)

   for objc_class in objc_image.classlist:
       print(f'{objc_class.name}')

.. code-block:: python
   :caption: Loading and iterating the Mach-O Header.
   :emphasize-lines: 3,4

   import ktool

   image = ktool.load_image('my/file.dylib')
   for load_command in image.macho_header:  # Using the MachOImageHeader __iter__ functionality
       if isinstance(load_command, dylinker_command):
           print('Dylinker cmd!')
       print(f'{load_command.render_indented(4)}')

   # OR, using the basic list iterator
   for load_command in image.macho_header.load_commands:
       if isinstance(load_command, dylinker_command):
           print('Dylinker cmd!')
       print(f'{load_command.render_indented(4)}')


