import importlib
import inspect



def resolve_circe_import(imports, key):

    key_parts = key.split('.')
    try:
        key_obj = imports[key_parts[0]]

        for sub in key_parts[1:]:
            _ = list(filter(lambda _:_[0] == sub, inspect.getmembers(key_obj)))
            if not _:
                break
            key_obj = _[0][1]

        return key_obj

    except (KeyError):
        return key

def parse_circe_object(imports: dict, objects: dict, obj: dict):

    result = {}

    assert type(obj) is dict
    o = obj.copy()
    name, typ, params = o.pop('name'), o.pop('type'), o.pop('params', {})

    typ = resolve_circe_import(imports, typ)

    children = params.pop('children', None)
    if children:
        child_objects = {}
        for child in children:
            #can be a string or a dict
            try:
                child_objects.update(parse_circe_object(imports, child_objects, child))
            except (AssertionError):
                child_objects[child] = objects[child]
            except (KeyError):
                raise Exception('child object {} missing required param'.format(child))

        params['children'] = child_objects

    for key in params.keys():
        if key in objects:
            params[key] = objects[key]


    assert callable(typ)

    try:
        return {
            name: typ(**params)
        }
    except:
        raise Exception('Failed to initialise {} with params {}'.format(typ, params))

def parse_circe_structure(structure: dict):

    assert type(structure) is dict
    s=structure.copy()

    imports = {
        i:importlib.import_module(i)
        for i in s.pop('imports', [])
    }

    objects = {}
    # create the objects in the order they are defined. any references to another object must be defined first
    for obj in s.pop('objects', []):
        objects.update(parse_circe_object(imports, objects, obj))

    return objects


