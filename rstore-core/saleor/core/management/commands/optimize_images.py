import os
import glob
from time import time
from sys import stdout
from django.core.management.base import BaseCommand
from django.conf import settings 
from PIL import Image

QUALITY = 60
SIZE = (1000,1000)

image_scanned = []
image_optimized = []

def convert_bytes(num):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0: 
            return "%3.1f %s" % (num, x)
        num /= 1024.0

def file_size(file_path):
    if os.path.isfile(file_path):
        file_info = os.stat(file_path)
        return convert_bytes(file_info.st_size)

def resize_compress(img_path, quality=QUALITY, size=SIZE ):
    with Image.open(img_path) as img:
        if img.width< size[0] or  img.height < size[1]:
             stdout.write("-----Skipping-- optimization\n")
        else:
            file_info = os.stat(img_path)
            before = file_info.st_size
            
            img.thumbnail(size=size)
            img.save(img_path, optimize=True, quality=quality)
            
            image_optimized.append(img_path)  
            file_info = os.stat(img_path)
            after = file_info.st_size
            
            change_percent = abs(100*((after-before)/before)) 

            stdout.write(f'Optimized {img_path}|before>>{convert_bytes(before)}\
                 after>>{convert_bytes(after)} saved>{round(change_percent)}%\n')
            

class Command(BaseCommand):
    help = 'Optimize all Image of specific directory by resizing and compressing'

    def add_arguments(self, parser):
    
        parser.add_argument(
            '-p', '--path',
            type=str,
            dest="path",
            help='path of the Image Directory, default static document root'
            )
        
        parser.add_argument(
            '-q', '--quality',
            type=int,
            dest="quality",
            help='quality range 10-100 , default is 60'
            )
        
        parser.add_argument(
            '-W', '--width',
            type=int,
            dest="width",
            help='Set Image width, default 1000px'
            )  
        
        parser.add_argument(
            '-H', '--height',
            dest="height",
            type=int,
            help='Set image Height default 1000px'
        )
        
        parser.add_argument(
            '-r', '--recursive', 
            action='store_true',
            dest="recursive",
            default=False,
            help='Recursively find images from subdir also'
        )


    def handle(self, *args, **options):
        path = options['path'] or  settings.MEDIA_ROOT 
        quality = options['quality'] or QUALITY
        width = options['width'] or SIZE[0]
        height = options['height'] or SIZE[1]
        recursive = options ['recursive']
        size = (width, height)
       
        if (quality >100 or quality<20):
            stdout.errors("Quality must be between 20-100")
            exit(1)
        
        if (width < 400):
            stdout.errors("Width or Height  must be between > 400")
            exit(1)
   
        start = time()
        for file in glob.glob(path+'/**/*.jpg',recursive=recursive):
            resize_compress(file, quality, size)
            image_scanned.append(file)

        stdout.write(f'\n\tTotal image:{len(image_scanned)}\n\
            Total optimized :{len(image_optimized)}\n')

        stdout.write(f"Runtime of the program is\
             {time() - start} seconds")
