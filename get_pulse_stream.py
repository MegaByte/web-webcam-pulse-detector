from lib.device import Stream, Camera
from lib.processors import findFaceGetPulse
from lib.interface import plotXY, imshow, waitKey,destroyWindow, moveWindow, resize
import numpy as np
import sys, time, urllib, urllib2, re
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import datetime
import argparse
import thread

class getPulseApp(object):
    """
    Python application that finds a face in a webcam stream, then isolates the
    forehead.

    Then the average green-light intensity in the forehead region is gathered
    over time, and the detected person's pulse is estimated.
    """
    def __init__(self, dir):
        #Imaging device - must be a connected stream (not an ip camera or mjpeg
        #stream)

        if dir:
            self.camera = None
            self.stream = Stream(dir)
            self.workout_slot_id = self.get_slot_id(dir)
        else:
            self.camera = Camera(camera=0) #first camera by default
            self.stream = None
            self.pressed = 0

        self.w,self.h = 0,0

        #Containerized analysis of recieved image frames (an openMDAO assembly)
        #is defined next.

        #This assembly is designed to handle all image & signal analysis,
        #such as face detection, forehead isolation, time series collection,
        #heart-beat detection, etc.

        #Basically, everything that isn't communication
        #to the camera device or part of the GUI
        self.processor = findFaceGetPulse(bpm_limits = [50,160],
                                          data_spike_limit = 25.,
                                          face_detector_smoothness = 10.)

        #Init parameters for the cardiac data plot
        self.bpm_plot = False
        self.plot_title = "Cardiac info - raw signal, filtered signal, and PSD"

        #Maps keystrokes to specified methods
        #(A GUI window must have focus for these to work)
        self.key_controls = {"s" : self.toggle_search,
                             "d" : self.toggle_display_plot,
                             "f" : self.write_csv}

        self.bpm = 0

        self.last_time = datetime.datetime.now()

    def write_csv(self):
        """
        Writes current data to a csv file
        """
        bpm = " " + str(int(self.processor.measure_heart.bpm))
        fn = str(datetime.datetime.now()).split(".")[0] + bpm + " BPM.csv"

        data = np.array([self.processor.fft.times,
                         self.processor.fft.samples]).T
        np.savetxt(fn, data, delimiter=',')

    def get_slot_id(self, dir):
      pattern = "(\d+)"
      matcher = re.compile(pattern)
      match   = matcher.search(dir)

      if match <> None:
        return match.group()
      return 1

    def toggle_search(self):
        """
        Toggles a motion lock on the processor's face detection component.

        Locking the forehead location in place significantly improves
        data quality, once a forehead has been sucessfully isolated.
        """
        state = self.processor.find_faces.toggle()
        print "face detection lock =",not state

    def toggle_display_plot(self):
        """
        Toggles the data display.
        """
        if self.bpm_plot:
            print "bpm plot disabled"
            self.bpm_plot = False
            destroyWindow(self.plot_title)
        else:
            print "bpm plot enabled"
            self.bpm_plot = True
            self.make_bpm_plot()
            moveWindow(self.plot_title, self.w,0)

    def make_bpm_plot(self):
        """
        Creates and/or updates the data display
        """
        plotXY([[self.processor.fft.times,
                 self.processor.fft.samples],
            [self.processor.fft.even_times[4:-4],
             self.processor.measure_heart.filtered[4:-4]],
                [self.processor.measure_heart.freqs,
                 self.processor.measure_heart.fft]],
               labels = [False, False, True],
               showmax = [False,False, "bpm"],
               label_ndigits = [0,0,0],
               showmax_digits = [0,0,1],
               skip = [3,3,4],
               name = self.plot_title,
               bg = self.processor.grab_faces.slices[0])

    def key_handler(self):
        """
        Handle keystrokes, as set at the bottom of __init__()

        A plotting or camera frame window must have focus for keypresses to be
        detected.
        """
        pressed = waitKey(10) & 255 #wait for keypress for 10 ms
        if pressed == 27: #exit program on 'esc'
            quit()
        for key in self.key_controls.keys():
            if chr(pressed) == key:
                self.key_controls[key]()

    def print_data(self):
        return "{0}".format(self.processor.fft.samples)

    def main_loop(self, skip):
        """
        Single iteration of the application's main loop.
        """
        if self.camera:
            if datetime.datetime.now() - self.last_time < datetime.timedelta(microseconds = skip):
                return
            self.last_time = datetime.datetime.now()
            (frame, frame_time) = self.camera.get_frame()
        else:
            # Get current image frame from the camera
            (frame, frame_time) = self.stream.get_frame()
        if frame is None:
            return False
        self.h,self.w,_c = frame.shape

        #display unaltered frame
        #imshow("Original",frame)

        #set current image frame to the processor's input
        self.processor.frame_in = frame
        self.processor.time_in = frame_time
        #process the image frame to perform all needed analysis
        self.processor.run()
        #collect the output frame for display
        output_frame = self.processor.frame_out

        #show the processed/annotated output frame

        # output_frame = resize(output_frame, (640,480))
        # imshow("Processed",output_frame)

        #create and/or update the raw data display if needed
        # if self.bpm_plot:
        #     self.make_bpm_plot()
        self.bpm = self.processor.fft.samples[-1]
        print str(self.processor.time_in) + '\t' + str(self.bpm)

        return True

class MyHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.process_and_return()

    def do_POST(self):
        path = self.path.split('/')
        ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
        if ctype == 'multipart/form-data':
            postvars = cgi.parse_multipart(self.rfile, pdict)
        elif ctype == 'application/x-www-form-urlencoded':
            length = int(self.headers.getheader('content-length'))
            postvars = cgi.parse_qs(self.rfile.read(length), keep_blank_values=1)
        else:
            postvars = {}
        self.process_and_return()
        # dump image into processing directory?

    def process_and_return(self):
        self.send_response(200)
        if self.path == '/crossdomain.xml':
            self.send_header('Content-type', 'text/xml')
            self.end_headers()
            self.wfile.write('<cross-domain-policy><site-control permitted-cross-domain-policies="master-only"/><allow-access-from domain="*"/><allow-http-request-headers-from domain="*" headers="*"/></cross-domain-policy>')
        elif self.path == '/favicon.ico':
            return
        else:
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            path = self.path.split('/')
            workout = path[1]
            if workout == '':
                if not args.path and not args.local:
                    self.wfile.write("No workout specified!")
                    return
                elif args.local:
                    workout = '0'
                else:
                    workout = args.path
            if not unicode(workout).isnumeric():
                self.wfile.write("Invalid workout specified!")
                return
            if float(workout) > 0:
                if not workout in App:
                    suffix = "/*.png"
                    App[workout] = getPulseApp(basedir + workout + suffix)
                thread.start_new_thread(run_main_loop_non_local, (workout,))

            if len(path) > 2:
                if path[2] == 'history':
                    self.wfile.write(App[workout].print_data())
                else:
                    # JSON-P callback
                    pattern = "callback=([^&]+)"
                    matcher = re.compile(pattern, re.IGNORECASE)
                    match   = matcher.search(self.path)
                    callback_method = 'callback'
                    if match <> None:
                      callback_method = match.group(1)

                    self.wfile.write(callback_method + "({bpm: " + str(App[workout].bpm) + "})")
            else:
                self.wfile.write(str(App[workout].bpm))

def run_main_loop():
    while True:
        App['0'].main_loop(skip)
        time.sleep(0.001)

def run_main_loop_non_local(workout):
    while App[workout].main_loop(0):
        url = "http://localhost:3000/train/pulse_data"
        values = dict(bpm=App[workout].bpm, captured_at=App[workout].processor.time_in, workout_slot_id=App[workout].workout_slot_id)
        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        rsp = urllib2.urlopen(req)
        content = rsp.read()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--rate", help="Frames per second", type=float)
    parser.add_argument("-l", "--local", help="Process local camera", nargs="*")
    parser.add_argument("-b", "--base", help="Base directory")
    parser.add_argument("-p", "--path", help="Process local path")
    args = parser.parse_args()
    skip = 1000000 / 100
    if args.rate:
        skip = 1000000 / args.rate

    App = {}
    basedir = '/tmp/'
    if args.base:
        basedir = args.base
    if args.local:
        App['0'] = getPulseApp(None)
        thread.start_new_thread(run_main_loop, ())
    try:
        server = HTTPServer(('', 3001), MyHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        if args.path and args.path in App:
            print App[args.path].print_data()
        server.socket.close()
