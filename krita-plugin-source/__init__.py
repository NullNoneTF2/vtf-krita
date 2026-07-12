from krita import Krita
from .vtf_extension import VTFExtension

Krita.instance().addExtension(VTFExtension(Krita.instance()))
