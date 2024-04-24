import logging
import json
import importlib
import pkgutil

# We need to import the target library here

import {{package_name}}

logger = logging.getLogger(__name__)

def get_docstrings(module):
    result = {}
    prefix = module.__name__ + "."

    for importer, modname, ispkg in pkgutil.walk_packages(module.__path__, prefix):
        try:
            # Load the submodule
            submodule = importlib.import_module(modname)
            # Process the submodule
            for attribute_name in dir(submodule):
                if attribute_name.startswith('_'):
                    continue

                attribute = getattr(submodule, attribute_name)
                full_name = f"{modname}.{attribute_name}"

                if hasattr(attribute, '__doc__'):
                        if attribute.__doc__:
                            result[full_name] = attribute.__doc__
        except Exception as e:
            # Skip modules that can't be imported
            continue

    return result

# Get docstrings for package and its submodules
# Note we need to pass the library in here
# if '.' in f'{{package_name}}':
_result = get_docstrings({{package_name}})
with open('/tmp/info.json', 'w') as _f:
    _f.write(json.dumps(_result))