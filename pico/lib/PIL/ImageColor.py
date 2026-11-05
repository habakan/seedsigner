from PIL import Image as _Image


def getrgb(color):
    return _Image.rgba(color)[:3]
