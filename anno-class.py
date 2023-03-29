import dataclasses
import datetime
import PySimpleGUI as sg
import argparse
import os
from PIL import Image as PILIM
from PIL import ImageTk
import io
import uuid

from playhouse.shortcuts import model_to_dict, dict_to_model

from peewee import *
from engine import PluginEngine
from model import Image, AnnotationAct, AnnotationAgent
from model.models import FilterConfigAct, ImageAnoCombo, FilterInstance, FilterAgent, Collection, ImageInCollection
import json

"""
Simple Image Browser based on PySimpleGUI
--------------------------------------------
There are some improvements compared to the PNG browser of the repository:
1. Paging is cyclic, i.e. automatically wraps around if file index is outside
2. Supports all file types that are valid PIL images
3. Limits the maximum form size to the physical screen
4. When selecting an image from the listbox, subsequent paging uses its index
5. Paging performance improved significantly because of using PIL
Dependecies
------------
Python3
PIL
"""


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


class FilterAgentConfigs:
    def __init__(self, name, configs):
        self.name = name
        self.configs = configs


class Backend():
    def __init__(self):
        self.db = SqliteDatabase("anno_class.db")
        self.CreateTables()
        self.pe = PluginEngine()
        self.pe.reload_plugins()

    def CreateTables(self):
        self.db.connect()
        self.db.create_tables([Image, AnnotationAct, AnnotationAgent,
                               FilterAgent, FilterConfigAct, FilterInstance, Collection, ImageInCollection])

    def FillImages(self, images):
        for i in images:
            try:
                Image.create(Path=i)
            except:
                continue

    def LoadAnnotations(self, images, annotations):
        self.plugins = annotations
        if len(self.plugins) == 0:
            self.plugins = [a.alias for a in AnnotationAgent.select()]
        for im in images:
            imPath = im
            if type(im) is Image:
                imPath = im.Path

            self.pe.start_annotations(imPath, self.plugins)
            for a in AnnotationAct.select().where(AnnotationAct.image == imPath):
                print(a.name, a.value)

    def ImagesFromDb(self, collection_name=None):
        if (collection_name == None):
            return [i.Path
                    for i in self.ImagesFromDb_Anno(collection_name)
                    ]
        collection = Collection.get(Collection.name == collection_name)
        images = [i.Path for i in Image.select().join(ImageInCollection).where(
            ImageInCollection.collection == collection.id)]
        return images

    def ImagesFromDb_Anno(self, collection_name=None):
        if (collection_name == None):
            return Image.select()

    def GetSelectedImagesInDb(self, images):
        return [Image.get(Image.Path == im) for im in images]

    def DeleteSelectedImagesInCollection(self, collection, images):
        dbImages = self.GetSelectedImagesInDb(images)
        col = Collection.get(Collection.name == collection)
        for i in dbImages:
            imInCol = ImageInCollection.get(
                ImageInCollection.collection == col, ImageInCollection.image == i)
            imInCol.delete_instance()

    def SaveImageListAsCollection(self, name, description, images):
        col = Collection.create(name=name, description=description)
        for i in images:
            ImageInCollection.create(collection=col, image=i)

    def ModifyCollection(self, collection: str, name: str, description: str) -> None:
        col: Collection
        col = Collection.get(Collection.name == collection)
        col.name = name
        col.description = description
        col.save()

    def StartFilter(self, images, filters):

        imAno: list[ImageAnoCombo]
        imAno = []
        im: Image
        for im in images:

            query = AnnotationAct.select().where(
                AnnotationAct.image == im.Path)
            combo = ImageAnoCombo(im.Path, list(query))

            imAno.append(combo)

        # isinstance = FilterInstance()
        # isinstance.configs = configs
        # isinstance.filter = FilterAgent.select().where(
        # FilterAgent.alias == "test-filter-agent")

        # print(imAno[1].path)

        filteredImages = self.pe.start_filters(imAno, filters)
        return filteredImages

    def CreateFilterConfigTemplate(self):
        config = FilterConfigAct()
        config.valType = "string"
        config.value = "avg_blue>200"

        config1 = FilterConfigAct()
        config1.valType = "string"
        config1.value = "avg_red>100"

        configs = []
        configs.append(model_to_dict(config))
        configs.append(model_to_dict(config1))

        filters = [FilterAgentConfigs("test-filter-agent", configs).__dict__,
                   FilterAgentConfigs("test-filter-agent", configs).__dict__]

        js = json.dumps(filters, indent=4)
        fileName = sg.PopupGetFile(
            message="Template location:", default_extension="*.json")
        with open(fileName, "w") as outfile:
            outfile.write(js)

        print(js)

    def LoadFilterConfigFromJson(self):

        fileName = sg.PopupGetFile(
            message="Filters configuration file:", default_extension="*.json")
        # try:
        with open(fileName, "r") as infile:
            filt = json.load(infile)

            print(filt)

            return self.ParseJsonForFilter(filt)
        # except:
        #     sg.Popup("File not selected or invalid.")

    def ParseJsonForFilter(self, json):
        filter_config = []

        for con in json:
            config = FilterAgentConfigs(**con)
            recreated = []
            for c in config.configs:
                recreated.append(dict_to_model(FilterConfigAct, c))

            filter_config.append(
                FilterAgentConfigs(config.name, recreated))

        return filter_config

    def DeleteCollection(self, name):
        col = Collection.get(Collection.name == name)
        col.deletedAt = datetime.datetime.now()
        col.save()
        print(col.name, col.deletedAt)

    def GetCollections(self):
        return [c.name for c in Collection.select().where(Collection.deletedAt == None)]


backend = Backend()


def load_images_to_db():
    # Get the folder containin:g the images from the user
    folder = sg.popup_get_folder('Image folder to open', default_path='')

    try:
        # PIL supported image types
        img_types = (".png", ".jpg", "jpeg", ".tiff", ".bmp")

        # get list of files in folder
        flist0 = os.listdir(folder)

        # create sub list of image files (no sub folders, no wrong file types)
        fnames = [os.path.join(folder, f) for f in flist0 if os.path.isfile(
            os.path.join(folder, f)) and f.lower().endswith(img_types)]
        backend.FillImages(fnames)

        num_files = len(backend.ImagesFromDb(None))
        if num_files == 0:
            sg.popup('No files in folder')
            raise SystemExit()

        del flist0                             # no longer needed
    except:
        True
# ------------------------------------------------------------------------------
# use PIL to read data of one image
# ------------------------------------------------------------------------------


def get_img_data(f, maxsize=(1200, 850), first=False):
    """Generate image data using PIL
    """
    img = PILIM.open(f)
    img.thumbnail(maxsize)
    if first:                     # tkinter is inactive the first time
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        del img
        return bio.getvalue()
    return ImageTk.PhotoImage(img)
# ------------------------------------------------------------------------------


# make these 2 elements outside the layout as we want to "update" them later
# initialize to the first file in the list
class FilterWin:
    createTemplate_key = "Create_temp_key"
    uploadFilter_key = "upload_filter_key"
    applyFilter_key = "apply_filter_key"

    def __init__(self, images):
        self.filtersLayout = [[sg.Listbox(values=[a.alias for a in FilterAgent.select()], size=(40, 20))],
                              [sg.Button("Create template", key=self.createTemplate_key), sg.Button(
                                  "Upload filter config", key=self.uploadFilter_key)],
                              [sg.Button("Apply filter", key=self.applyFilter_key)]]
        self.images = images
        self.window = sg.Window("Filters", self.filtersLayout, location=(0, 0))
        self.applyFilter_key
        self.event = None
        self.values = None
        self.filter = None

    def open(self):
        while True:
            self.event, self.values = self.window.read()
            if self.event == sg.WIN_CLOSED:
                break
            elif self.event == self.createTemplate_key:
                backend.CreateFilterConfigTemplate()
            elif self.event == self.uploadFilter_key:
                self.filter = backend.LoadFilterConfigFromJson()
            elif self.event == self.applyFilter_key:
                self.filtered_images = backend.StartFilter(
                    self.images, self.filter)
                for i in self.filtered_images:
                    col_name = uuid.uuid4()
                    collection = Collection.create(name=uuid.uuid4())
                    for image in i:
                        ImageInCollection.create(
                            collection=collection, image=Image.get(Image.Path == image))
                print(self.filtered_images)
        self.window.close()


class Main:

    collectionSelectedKey = 'collection_key'

    collections = backend.GetCollections()
    collection = None
    prev_collection = None
    images = backend.ImagesFromDb(collection)
    num_files = len(images)

    filename = ""
    image_elem = sg.Image()
    if num_files > 0:
        filename = images[0]
        image_elem = sg.Image(data=get_img_data(filename, first=True))

    filename_display_elem = sg.Text(filename, size=(80, 3))
    file_num_display_elem = sg.Text(
        'File 1 of {}'.format(num_files), size=(15, 1))

    imagesList = sg.Listbox(values=images, change_submits=True,
                            size=(60, 30), key='listbox_images', select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED)

    collections_list = sg.Listbox(values=collections, select_mode=sg.LISTBOX_SELECT_MODE_BROWSE, size=(
        20, 30), key=collectionSelectedKey, enable_events=True)
    # define layout, show and read the form
    col_collections = [[sg.Text('Collections', size=(10, 1)), sg.Button('Save as', size=(8, 1), key='save_as_btn')],
                       [collections_list],
                       [sg.Button('Annotate', size=(8, 2)),
                        sg.Button('Filter/Classify', size=(10, 2))],
                       [sg.Button("Load agents", size=(16, 2))],
                       [sg.Button("Modify collection", size=(8, 2)), sg.Button("Delete collection", size=(8, 2))]]

    col = [[sg.Button("Delete", size=(8, 2)), filename_display_elem],
           [image_elem]]

    col_files = [[sg.Button('Open folder', size=(16, 1), key='open_folder_btn', enable_events=True), sg.Button('Clear selection', size=(16, 1), key='clear_selection_btn', enable_events=True)],
                 [imagesList],
                 [sg.Button('Next', size=(8, 2)), sg.Button('Prev', size=(8, 2)), file_num_display_elem]]

    layout = [[sg.Column(col_collections),
               sg.Column(col_files), sg.Column(col)]]

    window = sg.Window('AnnoClass', layout, return_keyboard_events=True,
                       location=(0, 0), use_default_focus=False, text_justification="top", auto_size_buttons=True)

    def openCollectionCreateWindow(self, images):
        col_layout = [[sg.Text("Name: "), sg.InputText(key="name_field")],
                      [sg.Text("Description:")],
                      [sg.InputText(key="description_field")],
                      [sg.Button("Save")]]

        col_window = sg.Window("Create Collection",
                               col_layout, location=(0, 0))

        while True:
            col_event, col_values = col_window.read()
            if col_event == sg.WIN_CLOSED:
                break
            elif col_event == "Save":
                backend.SaveImageListAsCollection(
                    col_values["name_field"], col_values["description_field"], images)
                break

        col_window.close()

    def openCollectionModifyWindow(self, collection):

        col = Collection.get(Collection.name == collection)

        col_layout = [[sg.Text("Name: "), sg.InputText(default_text=col.name, key="name_field")],
                      [sg.Text("Description:")],
                      [sg.InputText(default_text=col.description,
                                    key="description_field")],
                      [sg.Button("Save")]]

        col_window = sg.Window("Update Collection",
                               col_layout, location=(0, 0))

        while True:
            col_event, col_values = col_window.read()
            if col_event == sg.WIN_CLOSED:
                break
            elif col_event == "Save":
                backend.ModifyCollection(
                    collection, col_values["name_field"], col_values["description_field"])
                break

        col_window.close()

    def openAnnotationWindow(self, images):
        annotations_list = sg.Listbox(values=[a.alias for a in AnnotationAgent.select()], change_submits=True,
                                      size=(60, 30), key='annotations_list', select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED, enable_events=True)

        apply_button = sg.Button("Apply", size=(8, 2))

        layout = [[annotations_list],
                  [apply_button]]

        window = sg.Window("Apply annotations", layout=layout, location=(0, 0))

        while True:
            event, values = window.read()
            if event == sg.WIN_CLOSED:
                break
            elif event == "Apply":
                backend.LoadAnnotations(images, values["annotations_list"])
                break
        window.close()

    def UpdateImagesList(self, vals):
        self.collection = None
        if len(vals[self.collectionSelectedKey]) > 0:
            self.collection = vals[self.collectionSelectedKey][0]
        if self.collection != self.prev_collection:

            self.prev_collection = self.collection
            self.images = backend.ImagesFromDb(self.collection)
            self.imagesList.update(self.images)
            self.num_files = len(self.images)
            if self.num_files > 0:
                self.filename = self.images[0]

        self.i = 0

    # loop reading the user input and displaying image, filename
    i = 0

    def GetSelectedImages(self, vals):
        ims_to_anno = vals["listbox_images"]
        if len(ims_to_anno) == 0:
            ims_to_anno = self.images
        return ims_to_anno

    def Clear(self, vals):
        self.imagesList.set_value([])
        self.collections_list.set_value([])
        vals[self.collectionSelectedKey] = []
        self.UpdateImagesList(vals)

    def UpdateCollections(self):
        self.collections = backend.GetCollections()
        self.collections_list.update(self.collections)

    def Run(self):

        while True:

            # read the form
            event, values = self.window.read()
            print(event, values)
            # perform button and keyboard operations
            if event == sg.WIN_CLOSED:
                break
            elif event in ('Next', 'MouseWheel:Down', 'Down:40', 'Next:34'):
                self.i += 1
                if self.i >= self.num_files:
                    self.i -= self.num_files
                self.filename = self.images[self.i]
            elif event in ('Prev', 'MouseWheel:Up', 'Up:38', 'Prior:33'):
                self.i -= 1
                if self.i < 0:
                    self.i = self.num_files + self.i
                self.filename = self.images[self.i]
            elif event == 'listbox_images':            # something from the listbox
                if len(values["listbox_images"]) > 0:
                    # selected filename
                    f = values["listbox_images"][0]
                    self.filename = f  # read this file
                    self.i = self.images.index(
                        f)                 # update running index
            elif event == 'Annotate':
                self.openAnnotationWindow(
                    backend.GetSelectedImagesInDb(self.GetSelectedImages(values)))
            elif event == 'Filter/Classify':
                FilterWin(backend.GetSelectedImagesInDb(
                    self.GetSelectedImages(values))).open()
                self.UpdateCollections()
            elif event == 'clear_selection_btn':
                self.Clear(values)
            elif event == 'open_folder_btn':
                load_images_to_db()
                self.images = backend.ImagesFromDb(self.collection)
                self.imagesList.update(self.images)
                self.filename = self.images[0]
                self.i = 0
            elif event == 'save_as_btn':
                self.openCollectionCreateWindow(
                    backend.GetSelectedImagesInDb(self.GetSelectedImages(values)))
                self.UpdateCollections()
            elif event == self.collectionSelectedKey:
                self.UpdateImagesList(values)
            elif event == "Delete collection":
                backend.DeleteCollection(values[self.collectionSelectedKey][0])
                self.UpdateCollections()
            elif event == "Modify collection":
                self.openCollectionModifyWindow(self.collection)
                self.UpdateCollections()
            elif event == "Delete":
                backend.DeleteSelectedImagesInCollection(self.collection,
                                                         self.GetSelectedImages(values))
                self.UpdateImagesList(values)
            else:
                self.filename = self.images[self.i]

            # update window with new image
            try:
                self.image_elem.update(
                    data=get_img_data(self.filename, first=True))
                # update window with filename
                self.filename_display_elem.update(self.filename)
                # update page display
                self.file_num_display_elem.update(
                    'File {} of {}'.format(self.i+1, self.num_files))
            except:
                sg.popup("Image is missing or unavailable.", title="Error")

        self.window.close()


parser = argparse.ArgumentParser(description="",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-a", "--annotate", action="store_true",
                    help="annotate images")
parser.add_argument("-c", "--classify", action="store_true",
                    help="classify images")
parser.add_argument("-e", "--export", action="store_true",
                    help="classify images")
parser.add_argument("-src", help="json config")
parser.add_argument("-out", help="output json location", )
parser.add_argument("-aa", "--allannotators", action="store_true")

args = parser.parse_args()
config = vars(args)


class ImageAnnotations:
    def __init__(self, image, annotations) -> None:
        self.Image = image
        self.Annotations = annotations


if config["annotate"]:
    src = config["src"]
    f = open(src, "r")
    content = f.read()

    contentJson = json.loads(content)
    backend.LoadAnnotations(contentJson["images"], contentJson["annotations"])

    if config["export"]:
        anodict = []
        for im in contentJson["images"]:
            annotations = AnnotationAct.select().where(AnnotationAct.image == im)

            annos = []
            for a in annotations:
                annos.append((a.name, a.value, a.valType))
            anodict.append((im, annos))

        anoJson = json.dumps(anodict)

        out = config["out"]
        fw = open(out, "w")
        fw.write(anoJson)

elif config["classify"]:
    src = config["src"]

    f = open(src, "r")
    content = f.read()

    contentJson = json.loads(content)
    ims = []
    for img in contentJson["images"]:
        im = Image()
        im.Path = img
        ims.append(im)
    filters = backend.ParseJsonForFilter(contentJson["classifiers"])

    filteredImages = backend.StartFilter(ims, filters)
    if config["export"]:
        out = config["out"]
        fw = open(out, "w")
        fw.write(json.dumps(filteredImages))

elif config["allannotators"]:
    agents = AnnotationAgent.select()
    agentList = []
    for a in agents:
        agentList.append(a.alias)

    out = config["out"]
    fw = open(out, "w")
    fw.write(json.dumps(agentList))

else:
    main = Main()
    main.Run()
