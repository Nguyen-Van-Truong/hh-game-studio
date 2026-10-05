"""Publication eligibility over the already bounded, byte-validated envelope.

This does not parse GDScript/Variant syntax, infer dependencies or sandbox code.
Godot still validates syntax/types inside the executor. The host independently
excludes editor scripts and serialized executable resources before dispatch;
candidate-controlled engine output cannot grant this eligibility. Diagnostic
byte admission remains separate so hostile fixtures can still be exercised.
"""
from __future__ import annotations


class PublicationEligibilityError(ValueError):
    pass


def _reject(code):
    raise PublicationEligibilityError(code)


def _script(text):
    # Only lexical boundaries are needed: annotations are literal identifiers,
    # never escape-decoded. Raw strings share the same delimiter boundaries.
    index = 0
    while index < len(text):
        char = text[index]
        if char == '#':
            end = text.find('\n', index)
            index = len(text) if end < 0 else end + 1
        elif char in "\"'":
            delimiter = char * (3 if text.startswith(char * 3, index) else 1)
            index += len(delimiter)
            while index < len(text) and not text.startswith(delimiter, index):
                index += 2 if text[index] == '\\' else 1
            if index >= len(text):
                _reject('GAMEPLAY_PUBLICATION_UNTERMINATED_STRING')
            index += len(delimiter)
        elif text.startswith('@tool', index):
            end = index + 5
            if end == len(text) or not ('a' + text[end]).isidentifier():
                _reject('GAMEPLAY_PUBLICATION_TOOL_SCRIPT')
            index = end
        else:
            index += 1


def _scene_string(text, start):
    """Decode just a quoted text-resource token, without evaluating Variants.

    VariantParser accepts u + four / U + six hex digits and escaped literals.
    Inspecting decoded tokens prevents escaped type/property spellings from
    bypassing the same publication rule as their ordinary serialized form.
    """
    index = start + 1
    value = []
    escapes = {'b': '\b', 't': '\t', 'n': '\n', 'f': '\f', 'r': '\r'}
    while index < len(text):
        char = text[index]
        index += 1
        if char == '"':
            return ''.join(value), index
        if char == '\\':
            if index >= len(text):
                break
            char = text[index]
            index += 1
            if char in ('u', 'U'):
                width = 4 if char == 'u' else 6
                digits = text[index:index + width]
                if len(digits) != width or any(c not in '0123456789abcdefABCDEF' for c in digits):
                    _reject('GAMEPLAY_PUBLICATION_SCENE_ESCAPE')
                number = int(digits, 16)
                if number > 0x10ffff:
                    _reject('GAMEPLAY_PUBLICATION_SCENE_ESCAPE')
                char = chr(number)
                index += width
            else:
                char = escapes.get(char, char)
        value.append(char)
    _reject('GAMEPLAY_PUBLICATION_UNTERMINATED_STRING')


def _scene_tokens(text):
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
        elif char == ';':
            end = text.find('\n', index)
            index = len(text) if end < 0 else end + 1
        elif char == '"':
            value, index = _scene_string(text, index)
            yield ('string', value)
        elif char.isalnum() or char in '_/' or char == '\\':
            start = index
            value = []
            while index < len(text) and (text[index].isalnum() or text[index] in '_/'
                                          or text[index] == '\\'):
                if text[index] != '\\':
                    value.append(text[index])
                    index += 1
                    continue
                digits = text[index + 2:index + 6] if index + 1 < len(text) and text[index + 1] == 'u' else None
                if digits is None or len(digits) != 4 or any(c not in '0123456789abcdefABCDEF' for c in digits):
                    _reject('GAMEPLAY_PUBLICATION_SCENE_ESCAPE')
                value.append(chr(int(digits, 16)))
                index += 6
            yield ('word', ''.join(value))
        else:
            index += 1
            yield ('symbol', char)


def _scene(text):
    tokens = list(_scene_tokens(text))
    tag = None
    # Godot's text-resource parser consumes an assignment key as the bytes
    # before '=' (whitespace may occur between identifier/path characters).
    # Reject the two executable-source keys even when split across tokens.
    for index in range(len(tokens)):
        values = [kind_value[1] for kind_value in tokens[index:index + 4]]
        kinds = [kind_value[0] for kind_value in tokens[index:index + 4]]
        if (values == ['script', '/', 'source', '=']
                or values == ['source', '_', 'code', '=']):
            _reject('GAMEPLAY_PUBLICATION_EMBEDDED_SCRIPT')
    for index, (kind, value) in enumerate(tokens):
        following = tokens[index + 1:index + 3]
        if kind == 'symbol' and value == '[':
            tag = following[0][1] if following and following[0][0] == 'word' else None
        elif kind == 'symbol' and value == ']':
            tag = None
        if kind in ('word', 'string') and following and following[0] == ('symbol', '='):
            if value in ('script/source', 'source_code'):
                _reject('GAMEPLAY_PUBLICATION_EMBEDDED_SCRIPT')
            if value == 'type' and len(following) == 2:
                resource_type = following[1][1]
                if resource_type in ('GDScript', 'CSharpScript', 'NativeScript', 'GDExtension'):
                    _reject('GAMEPLAY_PUBLICATION_EXECUTABLE_RESOURCE')
                if resource_type == 'Script' and tag != 'ext_resource':
                    _reject('GAMEPLAY_PUBLICATION_EXECUTABLE_RESOURCE')
        if (kind == 'word' and value == 'Object' and following
                and following[0] == ('symbol', '(')):
            _reject('GAMEPLAY_PUBLICATION_OBJECT_CONSTRUCTOR')


def validate_publication_sources(files):
    """Check every submitted file; preserves custom scenes and data resources.

    The source-only publication candidate admits .gd under scripts and .tscn
    under scenes. Embedded scripts/native modules need a separately supported
    profile. This is not a claim that arbitrary code has no dynamic behavior.
    """
    for name, raw in files.items():
        if name.startswith('scripts/') and name.endswith('.gd'):
            _script(raw.decode('utf-8'))
        elif name.startswith('scenes/') and name.endswith('.tscn'):
            _scene(raw.decode('utf-8'))
        elif name in ('assets/avatar.glb', 'assets/sprite_sheet.png'):
            # Binary validation is performed by gameplay_source_profile;
            # eligibility only keeps the publication path closed to all other
            # asset kinds. Native import/readback remains a later requirement.
            continue
        else:
            _reject('GAMEPLAY_PUBLICATION_FILE_KIND')
