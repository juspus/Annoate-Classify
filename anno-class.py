import dataclasses
import datetime
import PySimpleGUI as sg
import argparse
import os
from PIL import Image as PILIM
from PIL import ImageTk
import io
import uuid
import shutil

from playhouse.shortcuts import model_to_dict, dict_to_model

from peewee import *
from engine import PluginEngine
from model import Image, AnnotationAct, AnnotationAgent
from model.models import FilterAgentRequiredAnnotationAgent, FilterConfigAct, ImageAnoCombo, FilterInstance, FilterAgent, Collection, ImageInCollection
import json
from tendo import singleton

me = singleton.SingleInstance()  # will sys.exit(-1) if other instance is running


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
        self.ReloadAgents()

    def ReloadAgents(self):
        try:
            self.pe.reload_plugins()
        except Exception as e:
            sg.PopupError(e)

    def CreateTables(self):
        self.db.connect()
        self.db.create_tables([Image, AnnotationAct, AnnotationAgent,
                               FilterAgent, FilterConfigAct, FilterInstance, Collection, ImageInCollection, FilterAgentRequiredAnnotationAgent])

    def FillImages(self, images, folderName):
        foundImages = []
        im = None
        if images == None:
            sg.PopupOk("No images found in folder.")
            return
        for i in images:
            im, created = Image.get_or_create(Path=i)
            foundImages.append(im)

        self.SaveImageListAsCollection(
            f"{folderName}", "Loaded images.", foundImages)

    def LoadAnnotations(self, images, annotations, override=False, annotations_progress=None):
        self.plugins = annotations
        if len(self.plugins) == 0:
            self.plugins = [a.alias for a in AnnotationAgent.select()]
        count = 0
        if annotations_progress != None:
            annotations_progress.update(count, len(images), visible=True)
        for im in images:
            imPath = im
            if type(im) is Image:
                imPath = im.Path

            self.pe.start_annotations(imPath, self.plugins, override=override)
            for a in AnnotationAct.select().where(AnnotationAct.image == imPath):
                print(a.name, a.value)

            count += 1
            if annotations_progress != None:
                annotations_progress.update(count, len(images), visible=True)

        if annotations_progress != None:
            sg.Popup("Annotation complete.")

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

        ans = sg.PopupYesNo(
            "Do want to delete the selected images from the database aswell?")
        if collection != None:
            col = Collection.get(Collection.name == collection)
            for i in dbImages:
                try:
                    imInCol = ImageInCollection.get(
                        ImageInCollection.collection == col, ImageInCollection.image == i)
                    imInCol.delete_instance()
                except Exception as e:
                    print(e)
        if ans == "Yes":
            for i in dbImages:
                i.delete_instance()

    def SaveImageListAsCollection(self, name, description, images):
        col, created = Collection.get_or_create(
            name=name, description=description)
        col.deletedAt = None
        col.modifiedAt = datetime.datetime.now()
        col.save()
        for i in images:
            ImageInCollection.create(collection=col, image=i)

    def ModifyCollection(self, collection: str, name: str, description: str) -> None:
        col: Collection
        col = Collection.get(Collection.name == collection)
        col.name = name
        col.description = description
        col.save()

    def ExportCollection(self, collection, location) -> None:
        col: Collection
        col = Collection.get(Collection.name == collection)
        images = Image.select().join(ImageInCollection).where(
            ImageInCollection.collection == col.id)
        for i in images:
            iPath = i.Path
            iName = os.path.basename(iPath)
            iDir = os.path.dirname(iPath)
            iNewPath = os.path.join(location, iName)
            print(iPath, iNewPath)
            shutil.copy2(iPath, iNewPath)

    def StartFilter(self, images, filters):

        imAno: list[ImageAnoCombo]
        imAno = []
        im: Image
        for im in images:

            query = self.GetImageAnnotations(im)
            combo = ImageAnoCombo(im.Path, list(query))

            imAno.append(combo)

        filteredImages = self.pe.start_filters(imAno, filters)
        return filteredImages

    def GetImageAnnotations(self, image):
        return AnnotationAct.select().where(AnnotationAct.image == image.Path)

    def GetImageAnnotationsForDisplay(self, imPath):
        image = Image.get(Image.Path == imPath)

        return [[a.name, a.value] for a in self.GetImageAnnotations(image)]

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
        if fileName == None:
            return None

        with open(fileName, "w") as outfile:
            outfile.write(js)

        print(js)

    def LoadFilterConfigFromJson(self):

        fileName = sg.PopupGetFile(
            message="Filters configuration file:", default_extension="*.json")

        if fileName == None:
            return None
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
        ImageInCollection.delete().where(
            ImageInCollection.collection == col).execute()
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

        backend.FillImages(fnames, folder)

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


def get_img_data(f, maxsize=(800, 420), first=False):
    """Generate image data using PIL
    """
    img = PILIM.open(f)
    img.thumbnail(maxsize)
    if first:                     # tkinter is inactivep the first time
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
                if self.images == None:
                    sg.Popup("No images loaded")
                    break
                if self.filter == None:
                    sg.Popup("No filter selected, upload json configuration")
                    break
                self.filtered_images = backend.StartFilter(
                    self.images, self.filter)

                if self.filtered_images == None or len(self.filtered_images) == 0:
                    sg.Popup("No images found for this filter")
                    break
                for i in self.filtered_images:
                    col_name = uuid.uuid4()
                    collection = Collection.create(name=uuid.uuid4())
                    for image in i:
                        ImageInCollection.create(
                            collection=collection, image=Image.get(Image.Path == image))
                print(self.filtered_images)
                break
        self.window.close()


class Main:

    collectionSelectedKey = 'collection_key'

    collections = backend.GetCollections()
    collection = None
    prev_collection = None
    images = backend.ImagesFromDb(collection)
    num_files = len(images)

    filename = ""
    image_elem = sg.Image(size=(800, 600))
    if num_files > 0:
        filename = images[0]
        image_elem = sg.Image(data=get_img_data(
            filename, first=True), size=(800, 620))

    filename_display_elem = sg.Text(filename, size=(80, 1))

    imagesList = sg.Listbox(values=images, enable_events=True,
                            size=(60, 25), key='listbox_images', select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED, expand_y=True)

    collections_list = sg.Listbox(values=collections, select_mode=sg.LISTBOX_SELECT_MODE_BROWSE, size=(
        20, 25), key=collectionSelectedKey, enable_events=True, expand_y=True)
    # define layout, show and read the form
    col_collections = [[sg.Button('Open folder', size=(16, 1), key='open_folder_btn', enable_events=True)],
                       [sg.Text('Collections', size=(10, 1))],
                       [collections_list],
                       [sg.Button("Modify collection", size=(8, 2)),
                        sg.Button("Delete collection", size=(8, 2))],
                       [sg.Button("Export collection to folder", size=(16, 2), key='export_collection_btn', enable_events=True)]]

    imagesAnnotationsTable = sg.Table(values=[['', '']], headings=[
                                      "Annotation", "Value"], auto_size_columns=False, col_widths=200, num_rows=10, key='imagesAnnotationsTable', enable_events=True, max_col_width=200, expand_x=True)
    col = [[image_elem]]

    col_files = [[sg.Button('Save as', size=(8, 1), key='save_as_btn', enable_events=True), sg.Button('Clear selection (select all)', size=(20, 1), key='clear_selection_btn', enable_events=True), sg.Button("Delete", size=(8, 1), enable_events=True), filename_display_elem],
                 [sg.Text('Images', size=(10, 1))],
                 [imagesList],
                 [sg.Button('Annotate', size=(8, 2)),
                 sg.Button('Filter/Classify', size=(10, 2))]]

    mainLayout = [[sg.Column(col_collections, size=(200, 650)),
                   sg.Column(col_files, size=(400, 650)), sg.Column(col, size=(800, 650))]]

    layout = [[sg.Column(mainLayout, size=(1400, 650))],
              [imagesAnnotationsTable]]

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
        annotations_progress = sg.ProgressBar(0, orientation='h', size=(20, 20),
                                              key='annotations_progress', visible=False)
        annotations_list = sg.Listbox(values=[a.alias for a in AnnotationAgent.select()], change_submits=True,
                                      size=(60, 30), key='annotations_list', select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED, enable_events=True)

        apply_button = sg.Button("Apply", size=(8, 2))

        override_checkbox = sg.Checkbox("Re-annotate", key="override_checkbox")

        layout = [[annotations_list],
                  [apply_button, override_checkbox],
                  [annotations_progress]]

        window = sg.Window("Apply annotations", layout=layout, location=(0, 0))

        while True:
            event, values = window.read()
            if event == sg.WIN_CLOSED:
                break
            elif event == "Apply":
                backend.LoadAnnotations(
                    images, values["annotations_list"], override=values["override_checkbox"], annotations_progress=annotations_progress)
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
                self.collections_list.update(backend.GetCollections())
                if len(self.images) > 0:
                    self.filename = self.images[0]
                self.i = 0
            elif event == 'save_as_btn':
                self.openCollectionCreateWindow(
                    backend.GetSelectedImagesInDb(self.GetSelectedImages(values)))
                self.UpdateCollections()
            elif event == self.collectionSelectedKey:
                self.UpdateImagesList(values)
            elif event == "Delete collection":
                if len(values[self.collectionSelectedKey]) == 0:
                    sg.popup("Select a collection first.", title="Error")
                    continue
                backend.DeleteCollection(values[self.collectionSelectedKey][0])
                self.UpdateCollections()
            elif event == "Modify collection":
                if self.collection == None:
                    sg.popup("Select a collection first.", title="Error")
                    continue
                self.openCollectionModifyWindow(self.collection)
                self.UpdateCollections()
            elif event == "Delete":
                backend.DeleteSelectedImagesInCollection(self.collection,
                                                         self.GetSelectedImages(values))
                self.UpdateImagesList(values)
            elif event == "Load agents":
                backend.ReloadAgents()
            elif event == "export_collection_btn":
                location = sg.popup_get_folder(
                    "Select folder to export collection to.")
                if (location == None):
                    continue
                backend.ExportCollection(self.collection, location)
            else:
                if len(self.images) > 0:
                    self.filename = self.images[self.i]

            # update window with new image
            try:
                self.image_elem.update(
                    data=get_img_data(self.filename, first=True))
                # update window with filename
                self.filename_display_elem.update(self.filename)
                self.imagesAnnotationsTable.update(
                    values=backend.GetImageAnnotationsForDisplay(self.filename))
                # update page display
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
