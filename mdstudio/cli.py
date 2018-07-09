import requests
import zipfile
import io
import click
import tempfile
import shutil
import os
from git import Repo

def copy2_verbose(src, dst):
    print('Added {0}'.format(dst))
    shutil.copy2(src,dst)

@click.group()
def cli():
    pass

@cli.command()
@click.argument('directory', default=lambda: os.getcwd(), type=click.Path(file_okay=False,writable=True, resolve_path=True))
def init(directory):
    click.echo('Initialising MDStudio in "{}"'.format(directory))
    if os.path.isdir(directory):
        if os.listdir(directory):
            click.echo('Directory not empty, aborting init!')
            return -1
        else:
            os.rmdir(directory)

    r = requests.get('https://github.com/MD-Studio/Compose/archive/master.zip')
    zip_handle = zipfile.ZipFile(io.BytesIO(r.content))

    temporary = tempfile.mkdtemp()
    for z in zip_handle.infolist():
        zip_handle.extract(z, temporary)

    shutil.copytree(os.path.join(temporary, 'Compose-master'), directory, copy_function=copy2_verbose)

    mdstudio_lib = Repo.clone_from('https://github.com/MD-Studio/Library.git', os.path.join(directory, 'mdstudio'))