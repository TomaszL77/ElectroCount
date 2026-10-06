"""JSON boundaries preserve NumPy values as numbers, never diagnostic strings."""
import json as _json
import numpy as np


def numpy_value(value):
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,np.ndarray):return value.tolist()
    raise TypeError(f'Object of type {type(value).__name__} is not JSON serializable')


def dumps(value,**kwargs):
    kwargs.setdefault('default',numpy_value)
    return _json.dumps(value,**kwargs)
