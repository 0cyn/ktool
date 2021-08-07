class TapiYAMLWriter:

    @staticmethod
    def write_out(tapi_dict: dict):
        text = []
        text.append("---")
        text.append("archs:".ljust(23) + TapiYAMLWriter.serialize_list(tapi_dict['archs']))
        text.append("platform:".ljust(23) + tapi_dict['platform'])
        text.append("install-name:".ljust(23) + tapi_dict['install-name'])
        text.append("current-version:".ljust(23) + str(tapi_dict['current-version']))
        text.append("compatibility-version: " + str(tapi_dict['compatibility-version']))
        text.append("exports:")
        for arch in tapi_dict['exports']:
            text.append(TapiYAMLWriter.serialize_export_arch(arch))
        text.append('...')
        return '\n'.join(text)

    @staticmethod
    def serialize_export_arch(export_dict):
        text = []
        text.append('  - ' + 'archs:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['archs']))
        if 'allowed-clients' in export_dict:
            text.append \
                ('    ' + 'allowed-clients:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['allowed-clients']))
        if 'symbols' in export_dict:
            text.append('    ' + 'symbols:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['symbols']))
        if 'objc-classes' in export_dict:
            text.append('    ' + 'objc-classes:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['objc-classes']))
        if 'objc-ivars' in export_dict:
            text.append('    ' + 'objc-ivars:'.ljust(22) + TapiYAMLWriter.serialize_list(export_dict['objc-ivars']))
        return '\n'.join(text)

    @staticmethod
    def serialize_list(slist):
        text = "[ "
        wraplen = 55
        lpad = 28
        stack = []
        for item in slist:
            if len(', '.join(stack)) + len(item) > wraplen and len(stack) > 0:
                text += ', '.join(stack) + ',\n' + ''.ljust(lpad)
                stack = []
            stack.append(item)
        text += ', '.join(stack) + " ]"
        return text
