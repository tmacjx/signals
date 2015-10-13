import shutil
from signals.generators.base.base_template import BaseTemplate
from signals.generators.ios.conversion import sanitize_field_name, get_proper_name
from signals.generators.ios.parameters import SwiftParameter
from signals.generators.ios.ios_template_methods import iOSTemplateMethods
from signals.parser.api import GetAPI
from signals.parser.fields import Field


class SwiftTemplate(BaseTemplate):
    def __init__(self, project_name, schema, data_models_path, jinja2_environment, build_dir):
        super(SwiftTemplate, self).__init__(project_name, schema, data_models_path, jinja2_environment)
        # File Paths
        self.data_model_file = "{}/{}DataModel.swift".format(build_dir, project_name)

    def process(self):
        self.create_data_model_file()
        self.copy_data_models()

    def create_data_model_file(self):
        self.process_template('data_model.swift.j2', self.data_model_file, SwiftTemplateMethods, {
            'project_name': self.project_name,
            'VIDEO_FIELD': Field.VIDEO,
            'IMAGE_FIELD': Field.IMAGE,
            'request_objects': self.get_request_objects(self.schema.data_objects),
            'sanitize_field_name': sanitize_field_name
        })

    def copy_data_models(self):
        shutil.copyfile(self.data_model_file, "{}/DataModel.swift".format(self.data_models_path))


class SwiftTemplateMethods(iOSTemplateMethods):
    @staticmethod
    def method_parameters(api):
        parameters = []

        # Create request object parameters
        request_object = iOSTemplateMethods.get_api_request_object(api)
        if request_object:
            parameters.extend(SwiftParameter.generate_field_parameters(request_object))
            parameters.extend(SwiftParameter.generate_relationship_parameters(request_object))

        # Add id parameter if we need it
        id_parameter = SwiftParameter.create_id_parameter(api.url_path, request_object)
        if id_parameter:
            parameters.append(id_parameter)

        # Add required RestKit parameters
        parameters.extend([
            SwiftParameter(name="success",
                           swift_type="RestKitSuccess"),

            SwiftParameter(name="failure",
                           swift_type="RestKitError")
        ])

        return SwiftTemplateMethods.create_parameter_signature(parameters)

    @staticmethod
    def key_path(api):
        key_path_string = 'nil'
        if hasattr(api, 'resource_type'):
            key_path_string = 'nil' if api.resource_type == GetAPI.RESOURCE_DETAIL else '"results"'
        elif isinstance(api, GetAPI) and ':id' not in api.url_path:
            # Get requests with an ID only return 1 object, not a list of results
            key_path_string = '"results"'
        return key_path_string

    @staticmethod
    def attribute_mappings(fields):
        attribute_mapping_string = ""
        for index, field in enumerate(fields):
            leading_comma = '' if index == 0 else ', '
            swift_variable_name = get_proper_name(field.name)
            attribute_mapping_string += '{}"{}": "{}"'.format(leading_comma, field.name, swift_variable_name)
        return attribute_mapping_string

    @staticmethod
    def create_parameter_signature(parameters):
        method_parts = []
        for index, method_field in enumerate(parameters):
            swift_variable_name = get_proper_name(method_field.name)
            parameter_signature = "{}: {}".format(swift_variable_name, method_field.swift_type)

            method_parts.append(parameter_signature)

        return ", ".join(method_parts)
