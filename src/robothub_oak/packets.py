import warnings

try:
    import cv2
except ImportError:
    cv2 = None

import robothub

__all__ = ['HubPacket', 'DetectionPacket', 'TrackerPacket', 'DepthPacket', 'IMUPacket']


class HubPacket:
    """
    Base class for all packets. Represents a packet containing a frame.
    """

    def __init__(self, device: 'Device', packet):
        self.device = device
        self.depthai_sdk_packet = packet

        self.frame = self.depthai_sdk_packet.frame
        self.msg = self.depthai_sdk_packet.msg
        self.visualizer = self.depthai_sdk_packet.visualizer

    def upload_as_event(self, title: str):
        try:
            # convert numpy array to jpg
            frame_bytes = cv2.imencode('.jpg', self.depthai_sdk_packet.frame)[1].tobytes()
            robothub.DETECTIONS.send_frame_event(imagedata=frame_bytes, title=title, camera_serial=self.device.mxid)
        except Exception as e:
            warnings.warn(f'Could not upload detection with error: {e}')


class DepthPacket(HubPacket):
    def __init__(self, device: 'Device', packet):
        super().__init__(device, packet)

    def upload_as_event(self, title):
        raise NotImplementedError('Not implemented yet')


class DetectionPacket(HubPacket):
    def __init__(self, device: 'Device', packet):
        super().__init__(device, packet)
        self.detections = packet.detections
        try:
            self.nn_data = packet.nnData
        except AttributeError:
            self.nn_data = None

    def upload_as_detection(self, title: str):
        try:
            # convert numpy array to jpg
            frame_bytes = cv2.imencode('.jpg', self.depthai_sdk_packet.frame)[1].tobytes()

            # TODO add metadata
            robothub.DETECTIONS.send_frame_event(imagedata=frame_bytes, title=title, camera_serial=self.device.mxid)
        except Exception as e:
            warnings.warn(f'Could not upload detection with error: {e}')

    def upload_as_event(self, title):
        raise NotImplementedError('Not implemented yet')


class TrackerPacket(DetectionPacket):
    def __init__(self, device: 'Device', packet):
        super().__init__(device, packet)
        self.tracklets = packet.daiTracklets.tracklets

    def upload_as_event(self, title):
        raise NotImplementedError('Not implemented yet')


class IMUPacket:
    def __init__(self, device: 'Device', packet):
        self.device = device
        self._packet = packet
        # TODO add parsed data
