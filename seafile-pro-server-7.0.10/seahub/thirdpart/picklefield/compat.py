# python 3.x does not have cPickle module
try:
    # cpython 2.x
    from cPickle import loads, dumps  # noqa
except ImportError:
    from pickle import loads, dumps  # noqa
