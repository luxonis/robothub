
from depthai_sdk import OakCamera
from depthai_sdk.components import CameraComponent, NNComponent

from application import BaseCameraDataProcessor, CameraDataProcessors, RobothubCameraApplication, LiveView, send_robothub_image_event


class PeopleCounter(BaseCameraDataProcessor):

    def camera_data_callback(self, packets: dict):
        # its quite unclear what the dictionary keys are. This is probably confusing but should be fixed on the depthai_sdk side
        # we could do a wrapper, but I think fixing it on sdk side is a better solution. At least I am always confused what the keys are
        # going to be for a new pipeline.
        rgb = packets["1_bitstream"]
        nn_output = packets["some_name"]
        for detection in nn_output.detections:
            if detection.confidence > 0.5:
                detection_bounding_box = detection.xmin, detection.ymin, detection.xmax, detection.ymax
                LiveView.get_live_view("rgb_stream").draw_rectangle(rectangle=detection_bounding_box, label="person")
                send_robothub_image_event(image=rgb, device_id="1234", title="important_event", metadata={"color": "red", "status": "crossed_line"})


class MyApp(RobothubCameraApplication):

    def create_camera_data_processors(self) -> CameraDataProcessors:
        people_counter = PeopleCounter()
        return {"people_counter": people_counter}

    def create_pipeline(self, oak: OakCamera, camera_data_processors: CameraDataProcessors):
        rgb: CameraComponent = oak.create_camera(source="color", fps=self.config["fps"], resolution="1080p", encode="mjpeg")
        nn: NNComponent = oak.create_nn(model='mobilenet-ssd', input=rgb)

        self.create_live_view(oak=oak, component=rgb, title="rgb stream")  # oak would be redundant if CameraComponent saves the pipline in a class variable
        people_counter: BaseCameraDataProcessor = camera_data_processors["people_counter"]

        oak.sync([rgb.out.main, nn.out.main], people_counter.camera_data_callback)
