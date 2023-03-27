import PyInstaller.__main__

PyInstaller.__main__.run([
    'my_script.py',
    '--onefile',
    '--windowed'
])

pyinstaller gallery_v2.py -D --paths=util --paths usecase -p model -p engine