import inspect
import contextlib, contextvars



class Circe(contextlib.ContextDecorator):

    @staticmethod
    def circe_class_wrapper(parent, cls):
        def _wrapper(*args, **kwargs):
            kwargs['parent'] = parent
            return cls(*args, **kwargs)
        return _wrapper()

    def __enter__(self):
        self.__tokens = {}

        for child in getattr(self, '_CIRCE_CHILDREN', []):
            if child.__name__ not in globals():
                globals()[child.__name__] = contextvars.ContextVar(child.__name__)
            self.__tokens[child.__name__] = globals()[child.__name__].set(self.circe_class_wrapper(self, child))


        assert 'VirtualPin' in globals()


        return self

    def __exit__(self, *exc):
        for name, token in self.__tokens.items():
            globals()[name].reset(token)

        return False



