__all__ = ['try_or_default']


def try_or_default(func, default=None):
    try:
        return func()
    except:
        return default
