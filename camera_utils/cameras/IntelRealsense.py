import numpy as np
from camera_utils.cameras.CameraInterface import Camera
import pyrealsense2 as rs

class IntelRealsense(Camera):

    def __init__(self, rgb_resolution=Camera.Resolution.HD, depth_resolution=Camera.Resolution.HD, fps=30,
                 serial_number="", depth_in_meters=False):

        self.camera_name = "Intel Realsense"
        Camera.__init__(self, rgb_resolution, depth_resolution, fps, serial_number)

        # start camera
        self.pipeline = rs.pipeline()
        config = rs.config()

        if self.serial_number != "":
            config.enable_device(self.serial_number)

        # set resolutions
        config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, self.fps)  # max 1280x720 at 90 fps        
        if self.rgb_resolution == Camera.Resolution.HD: # max 1920x1080 at 30 fps
            config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, self.fps)  # max 1920x1080 at 30 fps
        else:
            config.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, self.fps)  # max 1920x1080 at 30 fps
        
        # Start streaming
        try:
            cfg = self.pipeline.start(config)
        except RuntimeError:
            print("\n\033[1;31;40mError during camera initialization.\nMake sure to have set the right RGB camera resolution. Some cameras doesn't have FullHD resolution (e.g. Intel Realsense D455).\nIf you have connected more cameras make sure to insert the serial numbers to distinguish cameras during initialization.\033[0m\n")
            exit(1)

        profile = cfg.get_stream(rs.stream.color)
        intr = profile.as_video_stream_profile().get_intrinsics()
        self.intr = {'fx': intr.fx, 'fy': intr.fy, 'px': intr.ppx, 'py': intr.ppy, 'width': intr.width, 'height': intr.height}

        if depth_in_meters:
            self.mm2m_conversion = 1000
        else:
            self.mm2m_conversion = 1

        print("%s %s camera configured.\n" % (self.camera_name, self.serial_number))

    def __del__(self):
        try:
            self.pipeline.stop()
            print("%s %s camera closed" % (self.camera_name, self.serial_number))
        except RuntimeError as ex:
            print("\033[0;33;40mException (%s): %s\033[0m" % (type(ex).__name__, ex))
        

    def get_rgb(self):
        '''
        :return: An rgb image as numpy array
        '''
        color_frame = None
        while not color_frame:
            frames = self.pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()

        color_frame = np.asanyarray(color_frame.get_data())
        return color_frame

    def get_depth(self):
        '''
        :return: A depth image (1 channel) as numpy array
        '''
        depth_frame = None
        while not depth_frame:
            frames = self.pipeline.wait_for_frames()
            depth_frame = frames.get_depth_frame()
        depth_frame = np.asanyarray(depth_frame.get_data(), dtype=np.uint16) 
        return np.asanyarray(depth_frame / self.mm2m_conversion, dtype=np.uint16)

    def get_frames(self):
        '''
        :return: rgb, depth images as numpy arrays
        '''
        depth_frame_cam, color_frame_cam = None, None
        while not color_frame_cam or not depth_frame_cam:
            frames = self.pipeline.wait_for_frames()
            depth_frame_cam = frames.get_depth_frame()
            color_frame_cam = frames.get_color_frame()
        depth_frame = np.asanyarray(depth_frame_cam.get_data()) / self.mm2m_conversion
        color_frame = np.asanyarray(color_frame_cam.get_data())

        return color_frame, np.asanyarray(depth_frame / self.mm2m_conversion, dtype=np.uint16)

    def get_aligned_frames(self):
        '''
        :return: rgb, depth images aligned with post-processing as numpy arrays
        '''
        depth_frame_cam, color_frame_cam = None, None
        while not color_frame_cam or not depth_frame_cam:
            frames = self.pipeline.wait_for_frames()
            align = rs.align(rs.stream.color)
            aligned_frames = align.process(frames)
            color_frame_cam = aligned_frames.first(rs.stream.color)
            depth_frame_cam = aligned_frames.get_depth_frame()
        depth_frame = np.asanyarray(depth_frame_cam.get_data()) / self.mm2m_conversion
        color_frame = np.asanyarray(color_frame_cam.get_data())

        return color_frame, np.asanyarray(depth_frame / self.mm2m_conversion, dtype=np.uint16)
        
    def set_option(self, option, value):
        '''
        :param option: the option to be set (rs.option.OPTION_NAME)
        :param value: the value of the option
        '''
        option_name = str(option)
        try:
            sensor = self.pipeline.get_active_profile().get_device().query_sensors()[1]
            sensor.set_option(option, value)
            option_name = str(option).replace('option.', '').upper()
            print("Option %s changed to value: %d" % (option_name, int(value)))
        except TypeError as ex:
            print("\033[0;33;40m Exception (%s): the option %s has NOT been set." % (type(ex).__name__, option_name))

    def get_option(self, option):
        '''
        :param option: the option to be got (rs.option.OPTION_NAME)
        '''
        option_name = str(option).replace('option.', '').upper()
        try:
            sensor = self.pipeline.get_active_profile().get_device().query_sensors()[1]
            value = sensor.get_option(option)
            print("Option %s value: %d" % (option_name, int(value)))
        except TypeError as ex:
            print("\033[1;33;40m Exception (%s): the option %s has NOT been set." % (type(ex).__name__, option_name))