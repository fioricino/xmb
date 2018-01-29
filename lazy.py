class Lazy:
    def __init__(self, func: callable, params: ()):
        self._func = func
        self._params = params
        self._initialized = False
        self._value = None

    def value(self):
        if self._initialized:
            return self._value
        self._value = self._func(*self._params)
        self._initialized = True
        return self._value
