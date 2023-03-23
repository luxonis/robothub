import warnings

try:
    import cv2
except ImportError:
    cv2 = None

import robothub


class HubPacket:
    def __init__(self, device: 'Device', packet):
        self.device = device
        self.packet = packet
        self.__dict__.update(self.packet.__dict__)

    def upload_as_detection(self, title: str):
        try:
            # convert numpy array to jpg
            frame_bytes = cv2.imencode('.jpg', self.packet.frame)[1].tobytes()

            # TODO add metadata
            robothub.DETECTIONS.send_frame_detection(imagedata=frame_bytes, title=title, camera_serial=self.device.mxid)
        except Exception as e:
            warnings.warn(f'Could not upload detection with error: {e}')

    def upload_as_event(self, title):
        raise NotImplementedError('Not implemented yet')
