from logging import Logger
from typing import Optional, List

from model import Meta, PluginConfig
from model.models import AnnotationAct, FilterConfigAct, ImageAnoCombo


class IPluginRegistry(type):
    plugin_registries: List[type] = list()

    def __init__(cls, name, bases, attrs):
        super().__init__(cls)
        if name != 'PluginCore':
            IPluginRegistry.plugin_registries.append(cls)


class AnnotationPluginCore(object, metaclass=IPluginRegistry):
    """
    Plugin core class
    """

    meta: Optional[Meta]

    def __init__(self) -> None:
        """
        Entry init block for plugins
        :param logger: logger that plugins can make use of
        """

    def invoke(self, image_path: str) -> List[AnnotationAct]:
        """
        Starts main plugin flow
        :param args: possible arguments for the plugin
        :return: a device for the plugin
        """
        pass


class FilterPluginCore(object, metaclass=IPluginRegistry):
    """
    Plugin core class
    """

    meta: Optional[Meta]

    def __init__(self) -> None:
        """
        Entry init block for plugins
        :param logger: logger that plugins can make use of
        """

    def invoke(self, images_paths: List[ImageAnoCombo], configuration: List[FilterConfigAct]) -> List[List[str]]:
        """
        Starts main plugin flow
        :param args: possible arguments for the plugin
        :return: a device for the plugin
        """
        pass
