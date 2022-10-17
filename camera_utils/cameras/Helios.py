import numpy as np
from camera_utils.cameras.CameraInterface import Camera
from arena_api.system import system
from arena_api.buffer import BufferFactory
import cv2

class Helios(Camera):

    def __init__(self, rgb_resolution=Camera.Resolution.HD, depth_resolution=Camera.Resolution.HD, fps=30,
                 serial_number="", depth_in_meters=False):

        import time

        self.camera_name = "LucidVision Helios"
        Camera.__init__(self, rgb_resolution, depth_resolution, fps, serial_number)

        tries = 0
        tries_max = 6
        sleep_time_secs = 3
        while tries < tries_max:  # Wait for device
            devices = system.create_device()
            if not devices:
                print(f'Try {tries+1} of {tries_max}: waiting for {sleep_time_secs} '
                      f'secs for a device to be connected!'
                )
                for sec_count in range(sleep_time_secs):
                    time.sleep(1)
                    print(f'{sec_count + 1 } seconds passed ',
                        '.' * sec_count, end='\r'
                    )
                tries += 1
            else:
                print(f'Created {len(devices)} device(s)')
                break
        else:
            raise Exception('No device found! Please connect a device and run the example again.')

        self.pipeline = devices[0]

        nodemap = self.pipeline.nodemap
        nodes = nodemap.get_node(['Width', 'Height', 'PixelFormat'])

        # CAMERA INTRINSICS
        intr = {}
        intr["fx"] = self.pipeline.nodemap["CalibFocalLengthX"].value
        intr["fy"] = self.pipeline.nodemap["CalibFocalLengthY"].value
        intr["ppx"] = self.pipeline.nodemap["CalibOpticalCenterX"].value
        intr["ppy"] = self.pipeline.nodemap["CalibOpticalCenterY"].value
        intr["width"] = nodes['Width'].value
        intr["height"] = nodes['Height'].value

        self.serial_number = self.pipeline.nodemap["DeviceSerialNumber"].value

        self.intr = {'fx': intr["fx"], 'fy': intr["fy"], 'px': intr["ppx"], 'py': intr["ppy"], 'width': intr["width"], 'height': intr["height"]}

        # if true makes black where the confidence is not high
        nodemap["Scan3dConfidenceThresholdEnable"].value = False 
        nodemap["Scan3dAmplitudeGain"].value = 5.0

        nodes['PixelFormat'].value = 'Coord3D_ABCY16'

        # Stream nodemap
        tl_stream_nodemap = self.pipeline.tl_stream_nodemap

        tl_stream_nodemap["StreamBufferHandlingMode"].value = "NewestOnly"
        tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True
        tl_stream_nodemap['StreamPacketResendEnable'].value = True

        nodemap["Scan3dCoordinateSelector"].value = "CoordinateA"
        self.scale_A = nodemap["Scan3dCoordinateScale"].value
        self.offset_A = nodemap["Scan3dCoordinateOffset"].value
        nodemap["Scan3dCoordinateSelector"].value = "CoordinateB"
        self.scale_B = nodemap["Scan3dCoordinateScale"].value
        self.offset_B = nodemap["Scan3dCoordinateOffset"].value
        nodemap["Scan3dCoordinateSelector"].value = "CoordinateC"
        self.scale_C = nodemap["Scan3dCoordinateScale"].value
        self.offset_C = nodemap["Scan3dCoordinateOffset"].value

        self.pipeline.start_stream()

        print("%s %s camera configured.\n" % (self.camera_name, self.serial_number))

    def __del__(self):
        try:
            system.destroy_device()
            print("%s %s camera closed" % (self.camera_name, self.serial_number))
        except RuntimeError as ex:
            print("\033[0;33;40mException (%s): %s\033[0m" % (type(ex).__name__, ex))
        

    def get_rgb(self):
        '''
        :return: An rgb image as numpy array
        '''
        buffer = self.pipeline.get_buffer()
        item = BufferFactory.copy(buffer)
        self.pipeline.requeue_buffer(buffer)

        npndarray = np.ctypeslib.as_array(item.pdata, shape=(item.height, item.width, int(item.bits_per_pixel / 8))).view(np.uint16)
        intensity = np.array(npndarray[:,:,3], dtype=np.uint16)
        cv2.normalize(intensity, intensity, 0, 255, cv2.NORM_MINMAX)
        intensity = np.uint8(intensity)

        return intensity


    def get_depth(self):
        '''
        :return: A depth image (1 channel) as numpy array
        '''
        buffer = self.pipeline.get_buffer()
        item = BufferFactory.copy(buffer)
        self.pipeline.requeue_buffer(buffer)

        npndarray = np.ctypeslib.as_array(item.pdata, shape=(item.height, item.width, int(item.bits_per_pixel / 8))).view(np.uint16)
        npndarray[:,:,2] = npndarray[:,:,2] * self.scale_C + self.offset_C # z * scale + offset
        depth = np.array(npndarray[:,:,2], dtype=np.uint16)

        return depth
        

    def get_frames(self):
        '''
        :return: rgb, depth images as numpy arrays
        '''
        buffer = self.pipeline.get_buffer()
        item = BufferFactory.copy(buffer)
        self.pipeline.requeue_buffer(buffer)

        npndarray = np.ctypeslib.as_array(item.pdata, shape=(item.height, item.width, int(item.bits_per_pixel / 8))).view(np.uint16)
        npndarray[:,:,2] = npndarray[:,:,2]*self.scale_C + self.offset_C # z * scale + offset
        
        depth = np.array(npndarray[:,:,2], dtype=np.uint16)
        intensity = np.array(npndarray[:,:,3], dtype=np.uint16)
        cv2.normalize(intensity, intensity, 0, 255, cv2.NORM_MINMAX)
        intensity = np.uint8(intensity)

        return intensity, depth


    def get_aligned_frames(self):
        '''
        :return: rgb, depth images aligned with post-processing as numpy arrays
        '''
        return self.get_frames()
        

    # def get_pcd(self):
    #     buffer = self.pipeline.get_buffer()
    #     item = BufferFactory.copy(buffer)
    #     self.pipeline.requeue_buffer(buffer)

    #     npndarray = np.ctypeslib.as_array(item.pdata, shape=(item.height, item.width, int(item.bits_per_pixel / 8))).view(np.uint16)
    #     npndarray[:,:,0] = npndarray[:,:,0] * self.scale_A + self.offset_A # x * scale + offset
    #     npndarray[:,:,1] = npndarray[:,:,1] * self.scale_B + self.offset_B # y * scale + offset
    #     npndarray[:,:,2] = npndarray[:,:,2] * self.scale_C + self.offset_C # z * scale + offset

    #     npndarray = np.array(npndarray, dtype=np.uint16)

    #     return npndarray[:,:,:3]

    # def set_option(self, option, value):
    #     '''
    #     :param option: the option to be set (rs.option.OPTION_NAME)
    #     :param value: the value of the option
    #     '''
    #     pass

    # def get_option(self, option):
    #     '''
    #     :param option: the option to be got (rs.option.OPTION_NAME)
    #     '''
    #     pass