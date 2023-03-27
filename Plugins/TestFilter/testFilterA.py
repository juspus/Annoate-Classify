from engine import FilterPluginCore
from model import Meta, AnnotationAct, FilterConfigAct, ImageAnoCombo
from boolean_parser import parse
from peewee import *

from model.models import Image


class TestFilterAgent(FilterPluginCore):

    def __init__(self) -> None:

        self.meta = Meta(
            name='test-filter-agent',
            description='Test filter agent used for testing.',
            version='0.0.1'
        )

    @staticmethod
    def filterPhotos(images: list[ImageAnoCombo], configurations: list[FilterConfigAct]) -> list[(str, int)]:
        configCount = 0
        imageCollection: list[(str, int)]
        imageCollection = []
        for conf in configurations:
            res = parse(conf.value)

            allParams: list[str]
            allParams = []
            try:
                allParams = res.params
            except:
                allParams.append(res.name)
            vars = locals()
            image: ImageAnoCombo
            for image in images:
                for p in allParams:
                    ano: AnnotationAct
                    for ano in image.annotations:
                        if ano.name == p:
                            vars.__setitem__(
                                ano.name, eval("float")(ano.value))

                if eval(conf.value):
                    imageCollection.append((image.path, configCount))

            configCount += 1

        return imageCollection

    def invoke(self, images: list[ImageAnoCombo], configurations: list[FilterConfigAct]) -> list[(str, int)]:
        analysis = self.filterPhotos(images, configurations)
        return analysis


#agent = TestFilterAgent()


# agent.readConfigurations()
