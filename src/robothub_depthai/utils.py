def try_or_default(func, default=None):
    try:
        return func()
    except:
        return default
