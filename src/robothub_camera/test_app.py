
from depthai_sdk import OakCamera
from depthai_sdk.components import CameraComponent, NNComponent

from application import RobothubCameraApplication, LiveView, send_robothub_image_event


class PeopleCounter:
    """Just a class that is used to fetch the camera data, ie oak.callback or oak.sync will use one of the methods of this class as the callback."""

    def __init__(self):
        self.people_counter = 0

    def camera_data_callback(self, packets: dict):
        # its quite unclear what the dictionary keys are. This is probably confusing but should be fixed on the depthai_sdk side
        # we could do a wrapper, but I think fixing it on sdk side is a better solution. At least I am always confused what the keys are
        # going to be for a new pipeline.
        rgb = packets["1_bitstream"]
        nn_output = packets["some_name"]
        for detection in nn_output.detections:
            if detection.confidence > 0.5:
                self.people_counter += 1
                detection_bounding_box = detection.xmin, detection.ymin, detection.xmax, detection.ymax
                LiveView.get_live_view("rgb_stream").draw_rectangle(rectangle=detection_bounding_box, label="person")
                send_robothub_image_event(image=rgb, device_id="1234", title="important_event", metadata={"color": "red", "status": "crossed_line"})


class MyApp(RobothubCameraApplication):

    people_counter: PeopleCounter
    people_count: int

    def on_application_start(self) -> None:
        # advanced user
        self.people_counter = PeopleCounter()
        # basic user
        self.people_count = 0

    def create_pipeline(self, oak: OakCamera):
        rgb: CameraComponent = oak.create_camera(source="color", fps=self.config["fps"], resolution="1080p", encode="mjpeg")
        nn: NNComponent = oak.create_nn(model='mobilenet-ssd', input=rgb)

        self.create_live_view(oak=oak, component=rgb, title="rgb stream")  # oak would be redundant if CameraComponent would save the pipline in a class variable

        # advanced user will use this
        oak.sync([rgb.out.main, nn.out.main], self.people_counter.camera_data_callback)
        # basic user will use this - and this can be promoted in our examples
        oak.sync([rgb.out.main, nn.out.main], self.callback)

    def callback(self, packets: dict):
        rgb = packets["1_bitstream"]
        nn_output = packets["some_name"]
        for detection in nn_output.detections:
            if detection.confidence > 0.5:
                self.people_counter += 1
                detection_bounding_box = detection.xmin, detection.ymin, detection.xmax, detection.ymax
                LiveView.get_live_view("rgb_stream").draw_rectangle(rectangle=detection_bounding_box, label="person")
                send_robothub_image_event(image=rgb, device_id="1234", title="important_event", metadata={"color": "red", "status": "crossed_line"})
