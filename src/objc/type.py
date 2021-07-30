from enum import Enum

type_encodings = {
    "c": "char",
    "i": "int",
    "s": "short",
    "l": "long",
    "q": "NSInteger",
    "C": "unsigned char",
    "I": "unsigned int",
    "S": "unsigned short",
    "L": "unsigned long",
    "Q": "NSUInteger",
    "f": "float",
    "d": "CGFloat",
    "b": "BOOL",
    "@": "id",
    "B": "bool",
    "v": "void",
    "*": "char *",
    "#": "Class",
    ":": "SEL",
    "?": "unk",
}


class Struct:
    def __init__(self, processor, type_str: str):
        # {name=dd}

        # Remove the outer {}, then get everything to the left of the equal sign
        self.name = type_str[1:-1].split('=')[0]

        # Remove the outer {},
        # get everything after the first = sign,
        # Process that via the processor
        # Save the resulting list to self.fields
        self.fields = processor.process(type_str[1:-1].split('=', 1)[1])

    def __str__(self):
        ret = "typedef struct " + self.name + " {\n"
        for i, field in enumerate(self.fields):
            if isinstance(field.value, Struct):
                field = field.value.name
            else:
                field = field.value
            ret += "    " + field + ' field' + str(i) + ';\n'
        ret += '} ' + self.name + ';'
        if len(self.fields) == 0:
            ret += " // Empty Struct"
        return ret


class EncodingType(Enum):
    METHOD = 0
    PROPERTY = 1
    IVAR = 2


class EncodedType(Enum):
    STRUCT = 0
    NAMED = 1
    ID = 2
    NORMAL = 3


class Type:
    def __init__(self, processor, typestr, pc=0):
        start = typestr[0]
        self.child = None
        self.pointer_count = pc

        if start in type_encodings.keys():
            self.type = EncodedType.NORMAL
            self.value = type_encodings[start]
            return

        elif start == '"':
            self.type = EncodedType.NAMED
            self.value = typestr[1:-1]
            return

        elif start == '{':
            self.type = EncodedType.STRUCT
            self.value = Struct(processor, typestr)
            return
        raise ValueError(f'Struct with type {start} not found')

    def __str__(self):
        pref = ""
        for i in range(0, self.pointer_count):
            pref += "*"
        return pref + str(self.value)


class TypeProcessor:
    def __init__(self):
        self.structs = {}

    def save_struct(self, struct: Struct):
        if struct.name not in self.structs.keys():
            self.structs[struct.name] = struct

    def process(self, type: str):
        try:
            tokens = self.tokenize(type)
            types = []
            pc = 0
            for i, token in enumerate(tokens):
                if token == "^":
                    pc += 1
                else:
                    typee = Type(self, token, pc)
                    types.append(typee)
                    if typee.type == EncodedType.STRUCT:
                        self.save_struct(typee.value)
                    pc = 0
            return types
        except:
            raise AssertionError(type)

    @staticmethod
    def tokenize(type: str):
        # ^Idd^{structZero=dd{structName={innerStructName=dd}}{structName2=dd}}

        # This took way too long to write
        # Apologies for lack of readability, it splits up the string into a list
        # Makes every character a token, except root structs
        #   which it compiles into a full string with the contents and tacks onto said list
        toks = []
        b = False
        bc = 0
        bu = ""
        for c in type:
            if b:
                bu += c
                if c == "{":
                    bc += 1
                elif c == "}":
                    bc -= 1
                    if bc == 0:
                        toks.append(bu)
                        b = False
                        bu = ""
            elif c in type_encodings or c == "^":
                toks.append(c)
            elif c == "{":
                bu += "{"
                b = True
                bc += 1
            elif c == '"':
                try:
                    toks = [type.split('@', 1)[1]]
                except:
                    # Named fields ;_;
                    return []
                break
        return toks

