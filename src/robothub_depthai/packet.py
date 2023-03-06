import robothub


class HubPacket:
    def __init__(self, device: 'Device', packet):
        self.device = device
        self.packet = packet

    def upload_as_detection(self, title: str):
        frame_bytes = self.packet.imgFrame.getData()
        # TODO add metadata
        robothub.DETECTIONS.send_frame_detection(imagedata=frame_bytes, title=title, camera_serial=self.device.mxid)

    def upload_as_event(self, title):
        raise NotImplementedError('Not implemented yet')
