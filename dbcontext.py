from peewee import *
from engine import PluginEngine
from model import Image, AnnotationAct, AnnotationAgent
from model.models import FilterConfigAct, ImageAnoCombo, FilterInstance, FilterAgent
from boolean_parser import parse
from typing import List

db = SqliteDatabase("test.db")


db.connect()
db.drop_tables([FilterAgent])
db.create_tables([Image, AnnotationAct, AnnotationAgent,
                 FilterAgent, FilterConfigAct, FilterInstance])


config = FilterConfigAct()
config.valType = "string"
config.value = "avg_blue>200 and (avg_green>1 or avg_blue<230)"

ano = AnnotationAct()
ano.value = 2
ano.name = "avg_blue"

configs = []
configs.append(config)

avg_green = 0
myVars = locals()
myVars.__setitem__(ano.name, ano.value)

res = parse(config.value)

if (eval(config.value)):
    print(True)

print(res)
# Configuration JSON/YAML filtravimu agentu nuotraukas grąžinamos turi būti iš filtrų List of List[Image]

# img = Image(
#     Path="C:\\Users\\JustasPuodzius\\Downloads\\90907080_3303912362956825_7483158134416998400_n.jpg")
# img.save()
# Image.create(Path="C:\\Users\\JustasPuodzius\\Downloads\\download (3).jpg")
# Image.create(Path="C:\\Users\\JustasPuodzius\\Downloads\\download (2).jpg")
# Image.create(Path="C:\\Users\\JustasPuodzius\\Downloads\\download (1).jpg")
# Image.create(Path="C:\\Users\\JustasPuodzius\\Downloads\\download.jpg")
# Image.create(
#     Path="C:\\Users\\JustasPuodzius\\Downloads\\_123881559_02.jpg")
pe = PluginEngine()

plugins = ["test-agent"]
images = Image.select()
pe.reload_plugins()
for im in images:
    pe.start_annotations(im.Path, plugins)
    for a in AnnotationAct.select().where(AnnotationAct.image == im.Path):
        print(a.name, a.value)

config = FilterConfigAct()
config.valType = "string"
config.value = "avg_blue>200"

config1 = FilterConfigAct()
config1.valType = "string"
config1.value = "avg_red>100"

imAno: list[ImageAnoCombo]
imAno = []

im: Image
for im in Image.select():

    query = AnnotationAct.select().where(
        AnnotationAct.image == im.Path)
    combo = ImageAnoCombo(im.Path, list(query))

    imAno.append(combo)

configs = []
configs.append(config)
configs.append(config1)

isinstance = FilterInstance()
isinstance.configs = configs
# isinstance.filter = FilterAgent.select().where(
# FilterAgent.alias == "test-filter-agent")

print(imAno[1].path)

filters = {"test-filter-agent": configs, "test-filter-agent": configs}

filteredImages = pe.start_filters(imAno, filters)

print(filteredImages)
