from utils import *
from PIL import Image
import PySimpleGUI as sg
from multiprocessing import Pool, Queue
import concurrent.futures
import os
import shutil
import json
import uuid
import time
import queue
from collections import namedtuple
import threading
mutex = threading.Lock()

sg.theme('Dark Blue')
sg.SetOptions(window_location=(-6, 0))


ImageUpdateRecord = namedtuple('ImageUpdateRecord', 'image, folder')
ImageKey = namedtuple('ImageKey', 'image, element')


class FolderData():
    """ Load, edit, save folder metadata """

    thumbsSubDir = '.t'
    backupsSubDir = '.b'
    allFolderDataPath = os.path.join('.metadata', 'all_folder_data.json')
    allFolderData = None

    def __init__(self):
        self.openFolderPath = None
        self.openFolderData = None
        self.settings = None
        if self.allFolderData is None:
            self.load_all_data()

    def load_all_data(self):
        try:
            with open(self.allFolderDataPath, encoding='utf-8') as file:
                self.allFolderData = json.load(file)
        except FileNotFoundError:
            self.allFolderData = {}

    def open_folder(self, folderPath, settings, windowManager):
        self.openFolderPath = folderPath
        self.settings = settings
        self.openFolderData = self.get_folder_data(self.openFolderPath)
        return True

    def get_folder_data(self, folderPath):
        if folderPath in self.allFolderData:
            return self.allFolderData[folderPath]
        return self.new_folder_data(folderPath)

    def new_folder_data(self, folderPath):
        new_uid = str(uuid.uuid4())
        folderData = {
            'path': folderPath,
            'uid':  new_uid,
            'thumbnailFolder': os.path.join('.metadata', new_uid, self.thumbsSubDir),
            'backupsFolder': os.path.join('.metadata', new_uid, self.backupsSubDir),
            'shortName': os.path.basename(folderPath),
            'imageData': {
                os.path.basename(img): self.new_image_data(img)
                for img in list_images_db(folderPath)
            },
        }
        # Make new dirs
        for newMetadataSubdir in (
            folderData['thumbnailFolder'],
            folderData['backupsFolder'],
        ):
            try:
                os.makedirs(newMetadataSubdir, exist_ok=False)
            except FileExistsError:
                pass
        self.update_save_folder_data(folderPath, folderData)
        return folderData

    def thumb_path(self, img):
        return os.path.join(
            self.openFolderData['thumbnailFolder'],
            f"{ self.settings['thumbSize'] }_{ os.path.splitext(img)[0] }.png",
        )

    def backup_path(self, img):
        return os.path.join(self.openFolderData['backupsFolder'], img)

    def update_save_folder_data(self, fpath=None, fdata=None):
        """ If fpath, fdata are None, update open folder entry """

        if fpath and fdata:
            self.allFolderData[fpath] = fdata
        elif not fpath and not fdata:
            self.allFolderData[self.openFolderPath] = self.openFolderData
        else:
            raise ValueError(
                'Cannot specify one of fpath, fdata without the other')
        with open(self.allFolderDataPath, 'w', encoding='utf-8') as f:
            json.dump(self.allFolderData, f)

    def new_image_data(self, img):
        return {
            'path': img,
            'name': os.path.basename(img),
            'rating': -1,
        }

    @property
    def folderShortName(self):
        return self.openFolderData['shortName'] if self.openFolderData else ''

    def thumbnail_paths(self):
        thumbnailFolder = self.openFolderData['thumbnailFolder']
        size = self.settings['thumbSize']
        return [
            os.path.join(
                thumbnailFolder,
                f'{ size }_{ os.path.splitext(img)[0] }.png',
            )
            for img in self.images()
        ]

    def images(self):
        return list_images_db(self.openFolderPath)

    def set_rating(self, image, rating):
        self.openFolderData['imageData'][image]['rating'] = rating

    def get_rating(self, image):
        return self.openFolderData['imageData'][image]['rating']

    def image_ratings(self):
        """ Return dict {img: rating} """

        return {
            img: self.openFolderData['imageData'][img]['rating']
            for img in list_images_db(self.openFolderPath)
        }

    def sorted_thumbs_names(self, sortByRating):
        """ Return (thumbs, names) optional sorted by rating """

        if sortByRating:
            thumbs = self.thumbnail_paths()
            imgRatingDict = self.image_ratings()
            sortedTriples = sorted(
                list(zip(thumbs, imgRatingDict.keys(), imgRatingDict.values())),
                key=lambda x: -x[-1]
            )
            return list(zip(*sortedTriples))[:2]  # magic unpacking
        else:
            return (self.thumbnail_paths(), self.images())


class ThreadedThumbApp(threading.Thread):
    """ Retrieve thumbnails in a thread parallel to main window thread """

    def __init__(self, windowManager, src, dest, images):
        super().__init__()
        self._stop_event = threading.Event()
        self.wm = windowManager
        self.src = src
        self.dest = dest
        self.images = images

    def run(self):
        for img in self.images:
            try:
                Image.open(self.wm.folderData.thumb_path(img))
                print('Thumb exists:', img)
            except:
                thumbnails((os.path.join(self.src, img), self.dest))
                print('Create thumb:', img)
            record = ImageUpdateRecord(
                image=img, folder=self.wm.folderData.openFolderPath
            )
            self.wm.put_image_update(record)

    def stop(self):
        self._stop_event.set()


class ThreadedResizeApp(threading.Thread):
    """ Resize images in a thread parallel to main window thread 
        (Also, remake thumbnails for resized images)
    """

    def __init__(self, windowManager, folder, images, size, backupFolder, thumbFolder):
        super().__init__()
        self._stop_event = threading.Event()
        self.wm = windowManager
        self.folder = folder
        self.images = images
        self.size = size
        self.backupFolder = backupFolder
        self.thumbFolder = thumbFolder

    def run(self):
        for img in self.images:
            print('Resize:', img)
            imagePath = os.path.join(self.folder, img)
            backup_and_resize(imagePath, self.folder,
                              self.backupFolder, self.size)
            thumbnails((imagePath, self.thumbFolder))
            record = ImageUpdateRecord(
                image=img, folder=self.wm.folderData.openFolderPath
            )
            self.wm.put_image_update(record)

    def stop(self):
        self._stop_event.set()


class WindowManager():
    """ Keep track of when we need to remake the window """

    selectFolderKey = 'select_folder'
    resizeInputKey = 'resize_input'
    resizeButtonKey = 'resize_button'
    sortRatingButtonKey = 'sort_rating_button'
    sortNameButtonKey = 'sort_name_button'
    copyButtonKey = 'copy_button'
    copyInputKey = 'copy_input'
    thumbSize = 'S'
    imgDim = THUMBNAIL_SIZES[thumbSize]
    loadingThumbPath = THUMBNAIL_LOAD_PATHS[thumbSize]
    screenWidth, _ = sg.Window.get_screen_size()
    scrollBarWidth = 20
    frameExcessWidth = 28
    gridCols = max(1, math.floor(
        (screenWidth - scrollBarWidth)/(imgDim + frameExcessWidth)))
    folderData = FolderData()
    folderSettings = {
        'thumbSize': thumbSize,
    }
    imageUpdateQueue = Queue()

    def __init__(self, cols=None):
        self.folder = None
        self.window = None
        if cols:
            self.gridCols = cols
        self.sortByRating = False

    @property
    def folderShortName(self):
        return self.folderData.folderShortName if self.folder else ''

    def put_image_update(self, img):
        self.imageUpdateQueue.put(img)

    def window_event_loop(self):
        while True:
            event, values = self.window.read(timeout=100)
            # if event and event != '__TIMEOUT__':
            #     print('-- Event:\n', event, values)

            # Handle events
            if event is None:
                # Event: close main window
                self.folderData.update_save_folder_data()
                return event
            if event == self.selectFolderKey:
                # Event: close folder select window
                if not values[self.selectFolderKey]:
                    continue
                self.folder = self.folderData.open_folder(
                    folderPath=values[self.selectFolderKey],
                    settings=self.folderSettings,
                    windowManager=self,
                )
                self.sortByRating = False
                self.kickoff_thumb_threads()
                return event
            if isinstance(event, ImageKey):
                # Event: user clicked part of an image frame
                if event.element[:4] == 'star':
                    rating = int(event.element[-1])
                    self.folderData.set_rating(event.image, rating)
                    self.update_star_display(event.image)
                if event.element == 'img':
                    self.toggle_check(event.image)
                if event.element == 'open':
                    self.open_image(event.image)
            if event == self.sortRatingButtonKey:
                if self.folder:
                    self.sortByRating = True
                    self.kickoff_thumb_threads()
                    return event
            if event == self.sortNameButtonKey:
                if self.folder:
                    self.sortByRating = False
                    self.kickoff_thumb_threads()
                    return event
            if event == self.resizeButtonKey:
                if self.folder:
                    self.kickoff_resize_threads()
            if event == self.copyButtonKey:
                if self.folder and values[self.copyInputKey]:
                    self.copy_to_subfolder(dest=values[self.copyInputKey])

            # Poll queue and update images
            records = self.batch_poll_img_queue(batchSize=8)
            for record in records:
                self.update_image(record)

            # Place at very end of event loop for debug window
            if event == sg.TIMEOUT_KEY:
                continue

    def batch_poll_img_queue(self, batchSize=4):
        """ Return batch of image update records from queue """

        records = []
        for i in range(batchSize):
            try:
                records.append(self.imageUpdateQueue.get(block=False))
            except queue.Empty:
                break
        return records

    def get_selected_images(self):
        return [
            img for img in self.folderData.images()
            if self.window[ImageKey(img, 'check')].get()
        ]

    def kickoff_thumb_threads(self):
        print('Kick off thumbnail thread')
        src = self.folderData.openFolderPath
        dest = self.folderData.openFolderData['thumbnailFolder']
        ThreadedThumbApp(self, src, dest, list_images_db(src)).start()

    def kickoff_resize_threads(self):
        print('Kick off resize thread')
        src = self.folderData.openFolderPath
        selected = self.get_selected_images()
        newSize = self.window[self.resizeInputKey].get()
        try:
            newSize = float(newSize)
            assert newSize > 0
        except:
            sg.Popup('Please enter a valid percent to resize',
                     title='Cannot resize')
            print('Invalid resize text, no action taken')
        else:
            ThreadedResizeApp(
                windowManager=self, folder=src, images=selected, size=newSize,
                backupFolder=self.folderData.openFolderData['backupsFolder'],
                thumbFolder=self.folderData.openFolderData['thumbnailFolder'],
            ).start()

    def update_image(self, imageUpdateRecord):
        image, folder = imageUpdateRecord
        if folder != self.folderData.openFolderPath:
            print('Folder no longer open:', folder)
            return
        key = ImageKey(image, 'img')
        thumb = self.folderData.thumb_path(image)
        elem = self.window[key]
        if not elem:
            print('Image not found:', image)
            pass
        else:
            print('Updated:', thumb)
            self.window[key].update(thumb)

    def update_star_display(self, image):
        rating = self.folderData.get_rating(image)
        for i in range(4):
            ik = ImageKey(image, f'star{ i }')
            if rating >= i:
                self.window[ik].update('imgs/full_star.png')
            else:
                self.window[ik].update('imgs/empty_star.png')

    def toggle_check(self, image):
        ik = ImageKey(image, 'check')
        self.window[ik].update(not self.window[ik].get())

    def open_image(self, image):
        try:
            open_image(os.path.join(self.folderData.openFolderPath, image))
        except KeyError:
            sg.Popup('Cannot open images on this OS', title='Unsupported OS')
            print('Invalid platform, no action taken')

    def copy_to_subfolder(self, dest):
        """ Copy selected images to subfolder dest in gallery dir """

        src = self.folderData.openFolderPath
        selected = self.get_selected_images()
        if not selected:
            sg.Popup('No images selected', title='None selected')
            return
        newSubfolder = os.path.join(src, dest)
        try:
            os.makedirs(newSubfolder, exist_ok=True)
        except Exception as e:
            sg.popup(
                'Failed to make subfolder. Perhaps the name is invalid on your OS?',
                title='New subfolder failed',
            )
            print('Exception while making subfolder:')
            print(e)
            return
        try:
            for img in selected:
                shutil.copy2(os.path.join(src, img), newSubfolder)
        except Exception as e:
            sg.popup(
                'Unable to copy files. This may be due to permission errors or OS errors.',
                title='Copy failed',
            )
            print('Exception while copying files:')
            print(e)
            return
        sg.popup(
            f'Copied { len(selected) } { "file" if len(selected) == 1 else "files" }',
            title='Success!'
        )

    def menu_layout(self):
        resizeFrame = sg.Frame(
            'Resize',
            [[
                sg.Button('Resize:', key=self.resizeButtonKey,
                          enable_events=True),
                sg.InputText('100', key=self.resizeInputKey,
                             size=(6, 1), enable_events=False),
                sg.Text('%', size=(2, 1), enable_events=False),
            ]]
        )
        sortFrame = sg.Frame(
            'Sort',
            [[
                sg.Button('By Rating', key=self.sortRatingButtonKey,
                          enable_events=True),
                sg.Button('By Name', key=self.sortNameButtonKey,
                          enable_events=True),
            ]]
        )
        moveFrame = sg.Frame(
            'Copy to subfolder',
            [[
                sg.Button('Copy to:', key=self.copyButtonKey,
                          enable_events=True),
                sg.InputText('', key=self.copyInputKey,
                             size=(12, 1), enable_events=False),
            ]]
        )
        openGalleryFrame = sg.Frame(
            'Open gallery',
            [[
                sg.FolderBrowse('Open gallery', target=self.selectFolderKey),
                sg.Text(f'Folder: { self.folderShortName }', size=(60, 1)),
            ]]
        )
        return [
            resizeFrame, sortFrame, moveFrame, openGalleryFrame,
            sg.InputText(key=self.selectFolderKey,
                         enable_events=True, visible=False),
        ]

    def gallery_element(self, elemData):
        image = os.path.basename(elemData['img'])
        title = image
        # imgSize = image_size(elemData['thumb'])
        rating = self.folderData.get_rating(image)
        if rating is None:
            rating = -1
        # xPad = (self.imgDim - imgSize[0])//2
        # yPad = (self.imgDim - imgSize[1])//2
        check = [
            sg.Check('',
                     enable_events=True,
                     pad=(30, 0),
                     key=ImageKey(image, element='check'),
                     )
        ]
        ratingStars = [
            sg.Image(
                'imgs/full_star.png' if i <= rating else 'imgs/empty_star.png',
                enable_events=True,
                pad=(2, 0),
                key=ImageKey(image, element=f'star{ i }'),
            )
            for i in range(4)
        ]
        openIcon = [
            sg.Image(
                'imgs/open_icon.png',
                enable_events=True,
                pad=(30, 0),
                key=ImageKey(image, element=f'open'),
            )
        ]
        layout = [
            check + ratingStars + openIcon,
            [
                sg.Image(
                    elemData['thumb'],
                    # pad=(xPad, yPad),
                    enable_events=True,
                    key=ImageKey(image, element='img'),
                )
            ],
        ]
        if len(title) > 50:
            title = '...' + title[-47:]
        return sg.Frame(
            title, layout,
            element_justification='center'
        )

    def gallery_row_element(self, rowData):
        return [
            self.gallery_element(elemData={
                'row': rowData['row'],
                'col': col,
                'img': data['name'],
                'thumb': self.loadingThumbPath,  # data['thumb'],
            })
            for col, data in enumerate(rowData['imageDatas'])
            if data
        ]

    def image_data_grid(self, thumbs, imgNames):
        return to_grid(
            arr=[{'thumb': t, 'name': n} for t, n in zip(thumbs, imgNames)],
            numCols=self.gridCols,
        )

    def gallery_layout(self):
        if self.folder:
            thumbs, names = self.folderData.sorted_thumbs_names(
                self.sortByRating)
            imgDataGrid = self.image_data_grid(thumbs=thumbs, imgNames=names)
            rowDataDicts = [
                {'row': row, 'imageDatas': imageDatas}
                for row, imageDatas in enumerate(imgDataGrid)
            ]
            return [
                self.gallery_row_element(rowData)
                for row, rowData in enumerate(rowDataDicts)
            ]
        else:
            return [[sg.Text('', size=(100, 40))]]

    def layout(self):
        return [
            self.menu_layout(),
            [sg.Column(
                self.gallery_layout(),
                size=(
                    self.gridCols*(self.imgDim + 30),
                    sg.Window.get_screen_size()[1]-100
                ),
                pad=(0, 0),
                scrollable=True,
                vertical_scroll_only=True,
            )],
            # [sg.Debug()],
        ]

    def remake_window(self):
        newWindow = sg.Window('Gallery', self.layout())

    def close_window(self):
        if self.window:
            self.window.close()
            del self.window

    def run_window(self):
        eventLoopResult = True
        while eventLoopResult:
            newWindow = sg.Window('Gallery', self.layout())
            self.close_window()
            self.window = newWindow
            eventLoopResult = self.window_event_loop()


if __name__ == '__main__':
    wm = WindowManager()
    wm.run_window()
