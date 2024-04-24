# -*- coding: utf-8 -*-
import types
import json
import logging
import pickle

logger = logging.getLogger(__name__)

_out={}
_out['user_vars'] = {}
_out['imported_modules']=[]
_not_allowed=['local_vars','open','quit','exit','In','Out',
             'get_ipython','local_imported_modules','logger','__builtins__']
_uvars = globals().copy()
for _var_name in list(_uvars.keys()):
    _var_value = _uvars[_var_name]
    # Exclude built-in variables and functions
    if not _var_name.startswith('__') and not callable(_var_value) and not _var_name.startswith('_') and _var_name not in _not_allowed and not isinstance(_var_value, types.ModuleType):
        _out['user_vars'][_var_name] = _var_value
    if not _var_name.startswith('__') and not callable(_var_value) and not _var_name.startswith('_') and _var_name not in _not_allowed and isinstance(_var_value, types.ModuleType):
        _out['imported_modules'].append(_var_name)
# _out['_ih'].append(_uvars['_ih'])
# _out['_ih'].append(_uvars['_ih'])

with open('/tmp/jupyter_state.pkl', 'wb') as _f:
    pickle.dump(_out, _f)

