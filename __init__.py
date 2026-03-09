def classFactory(iface):
    import os, sys, site
    _here = os.path.dirname(__file__)
    _libs = os.path.join(_here, "libs")

    try: sys.path.remove(_libs)
    except ValueError: pass
    sys.path.insert(0, _libs)

    site.addsitedir(_libs)

    try: sys.path.remove(_libs)
    except ValueError: pass
    sys.path.insert(0, _libs)

    from .mainPlugin import MainPlugin
    return MainPlugin(iface)