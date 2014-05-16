import cv2, time
import urllib2, base64
import numpy as np
import glob
import time
import re

class ipCamera(object):

    def __init__(self,url, user = None, password = None):
        self.url = url
        auth_encoded = base64.encodestring('%s:%s' % (user, password))[:-1]

        self.req = urllib2.Request(self.url)
        self.req.add_header('Authorization', 'Basic %s' % auth_encoded)

    def get_frame(self):
        response = urllib2.urlopen(self.req)
        img_array = np.asarray(bytearray(response.read()), dtype=np.uint8)
        frame = cv2.imdecode(img_array, 1)
        return (frame, time.time())

class Camera(object):

    def __init__(self, camera = 0):
        self.cam = cv2.VideoCapture(camera)
        if not self.cam:
            raise Exception("Camera not accessible")

        (frame, frame_time) = self.get_frame()
        self.shape = frame.shape

    def get_frame(self):
        _,frame = self.cam.read()
        return (frame, time.time())

    def release(self):
        self.cam.release()

class Stream(object):

    def __init__(self, dir = None):
        self.current_photo_index = 0
        self.photos = glob.glob(dir)

    def get_frame(self):
        if self.current_photo_index >= len(self.photos):
            return (None, None)
        next_photo = self.photos[self.current_photo_index]
        self.current_photo_index += 1
        frame_time = re.findall('\d+\.\d+', )
        return (cv2.imread(next_photo, 1), float(frame_time[0]))
