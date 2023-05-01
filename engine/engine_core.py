from engine.engine_contract import AnnotationPluginCore
from model.models import FilterConfigAct, ImageAnoCombo
from usecase import PluginUseCase
from model import Image, AnnotationAct
from PySimpleGUI import PySimpleGUI as sg


class PluginEngine:

    def __init__(self, **args) -> None:
        self.use_case = PluginUseCase()
        print("sd")

    def start_annotations(self, image: str, plugins: list[str], override=False) -> None:
        self.used_plugins_annotation = plugins
        print("Annotating ", image)
        self.__invoke_on_annotation_plugins(image, override=override)

    def reload_plugins(self) -> None:
        self.__reload_plugins()

    def start_filters(self, images: list[ImageAnoCombo], plugins: dict[str, FilterConfigAct]) -> None:
        self.used_plugins_filter = plugins
        self.__invoke_on_filter_plugins(images)
        return self.filtered_image_collections

    def __reload_plugins(self) -> None:
        """Reset the list of all plugins and initiate the walk over the main
        provided plugin package to load all available plugins
        """
        self.use_case.discover_plugins(True)

    def __invoke_on_annotation_plugins(self, image, override=False):
        """Apply all of the plugins on the argument supplied to this function
        """
        for module in self.use_case.annotation_modules:
            plugin = self.use_case.register_plugin_annotation(module)

            if plugin.meta.name in self.used_plugins_annotation:
                if self.__is_annotated_by_plugin(image, plugin) and override == False:
                    continue
                delegate = self.use_case.hook_plugin_annotation(plugin)
                analysis = delegate(image)
                if override:
                    AnnotationAct.delete().where((AnnotationAct.agent == plugin.meta.name)
                                                 & (AnnotationAct.image == image)).execute()
                if analysis is None:
                    print("No analysis returned from plugin " +
                          plugin.meta.name + "on image " + image + ".")
                    continue
                for a in analysis:
                    a.agent = plugin.meta.name
                    a.image = image
                    a.save()
                print(analysis)

    def __is_annotated_by_plugin(self, image: str, plugin: AnnotationPluginCore) -> bool:
        count = AnnotationAct.select().where((AnnotationAct.agent == plugin.meta.name)
                                             & (AnnotationAct.image == image)).count()
        return count > 0

    def __invoke_on_filter_plugins(self, images: list[ImageAnoCombo]):
        """Apply all of the plugins on the argument supplied to this function
        """
        self.filtered_image_collections = []
        plugins = []
        for module in self.use_case.filter_modules:
            plugins.append(self.use_case.register_plugin_filter(module))

        self.__recursive_img_filter(images, plugins)

    def __recursive_img_filter(self, images: list[ImageAnoCombo], plugins):
        plugin = [obj for obj in plugins if obj.meta.name == list(i.name for i in self.used_plugins_filter)[
            0]][0]

        delegate = self.use_case.hook_plugin_filter(plugin)
        try:
            filtered = delegate(images, self.used_plugins_filter[0].configs)
        except:
            sg.PopupError("Error in plugin " + plugin.meta.name +
                          ". Please check the plugin's documentation and make sure all required annotations are present.")
            return

        self.used_plugins_filter.pop(0)

        separated_values = {}

        # iterate through the list of tuples
        for tuple in filtered:
            # get the value of the item we want to separate by
            value = tuple[1]
            # check if this value is already in the dictionary
            if value in separated_values:
                # if it is, append the tuple to the list of tuples for this value
                separated_values[value].append(tuple[0])
            else:
                # if it isn't, create a new list with this tuple and add it to the dictionary
                separated_values[value] = [tuple[0]]

        for ims in separated_values.values():
            if len(ims) == 0:
                continue
            if len(self.used_plugins_filter) == 0:
                self.filtered_image_collections.append(ims)
                continue
            im = self.__prepare_for_rerun(ims, images)
            self.__recursive_img_filter(im, plugins)

    def __prepare_for_rerun(self, filtered, images):
        ims = [obj for obj in images if obj.path in filtered]
        return ims
