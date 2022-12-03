import logging as log

import robothub

from robohub_depthai.manager import HubCameraManager

log.basicConfig(format='%(levelname)s | %(funcName)s:%(lineno)s => %(message)s', level=log.INFO)


class ExampleApplication(robothub.RobotHubApplication):
    def __init__(self):
        super().__init__()
        self.camera_manager = HubCameraManager(self.app, robothub.DEVICES)

    def on_start(self):
        for camera in self.hub_cameras:
            color = camera.create_camera('color', resolution='1080p', fps=30)
            # nn = camera.create_nn('person-detection-retail-0013', input=color)

            # It will automatically create a stream and assign matching callback based on Component type
            camera.create_stream(component=color, name='color', description='Color stream')

    def start_execution(self):
        self.camera_manager.start()

    def on_stop(self):
        self.camera_manager.stop()

    def on_detection_uploaded(self, detection: robothub.UploadedDetection):
        log.debug(f'Detection with id "{detection.detection_id}" has been uploaded')
        log.debug(f'Uploaded detection: {str(detection.to_str())}')

    # def on_start(self):
    #     log.debug('START')
    #     mxid_list = []
    #
    #     for device in robothub.DEVICES:
    #         mxid_list.append(device.oak.get('serialNumber'))
    #     log.info(f'Assigned devices: {mxid_list}')
    #
    #     for device in robothub.DEVICES:
    #         device_id = device.oak.get('serialNumber')
    #         oak_dai_device = robothub.DaiDevice(self, robothub.STREAMS, device_id)
    #         self.dai_device_objects.append(oak_dai_device)
    #
    #         oak_dai_device.get_cameras()
    #         log.info(f'Device {device_id} connected, detected cameras: {str(oak_dai_device.cameras)}')
    #         oak_dai_device.initialize_person_detection_stream(resolution='400p', fps=30,
    #                                                           id=f'stream_{len(self.dai_device_objects)}',
    #                                                           name=f'Person Detection-{len(self.dai_device_objects)}')
    #         # oak_dai_device.initialize_color_stream(resolution = '400p', fps = 30, id = f'stream_{len(self.dai_device_objects)}', name = f'RGB-{len(self.dai_device_objects)}')
    #
    #     log.info('Starting streams...')
    #     self.run_device_report_thread = Thread(target=self.device_report_thread, name="DeviceReportThread",
    #                                            daemon=False)
    #     self.run_device_report_thread.start()
    #
    #     self.run_polling_thread = Thread(target=self.polling_thread, name="PollingThread", daemon=False)
    #     self.run_detection_thread = Thread(target=self.detection_thread, name="DetectionThread", daemon=False)
    #     log.debug('EXIT')
    #
    # def start_execution(self):
    #     log.debug('Starting looping threads')
    #     with open(os.devnull, 'w') as devnull:
    #         with contextlib.redirect_stdout(devnull):
    #             for device in self.dai_device_objects:
    #                 device.start()
    #
    #     self.run_detection_thread.start()
    #     self.run_polling_thread.start()
    #
    # def device_report_thread(self):
    #     log.debug('Starting device report loop')
    #     while not self.stop_event.is_set():
    #         for device in self.dai_device_objects:
    #             device_info = device._device_info_report()
    #             device_stats = device._device_stats_report()
    #             robothub.AGENT.publish_device_info(device_info)
    #             robothub.AGENT.publish_device_stats(device_stats)
    #         self.stop_event.wait(timeout=self.DEVICE_REPORT_INTERVAL)
    #     log.debug('EXIT')
    #
    # def detection_thread(self):
    #     log.debug('Starting detection sending loop')
    #     while not self.stop_event.is_set():
    #         # One way of sending a detection is building it manually:
    #         detection = robothub.DETECTIONS.prepare()
    #         detection.set_title('Detection with 10 files')
    #         for i in range(10):
    #             detection.add_file(bytes([randint(0, 255) for j in range(100)]), name='File with 100 random bytes')
    #         detection.add_video(bytes([randint(0, 255) for i in range(1_000_000)]))
    #         detection.set_tags(['100 files', 'mock detection'])
    #         # And then sending the complete detection
    #         robothub.DETECTIONS.upload(detection)
    #         self.stop_event.wait(timeout=self.MESSAGE_INTERVAL)
    #
    #         # Another way is to use built-in functions from the SDK
    #         detection_text = 'some_text_detection'
    #         robothub.DETECTIONS.send_text_file_detection(text=detection_text,
    #                                                      title='Text detection number 1',
    #                                                      tags=['text', 'detection'],
    #                                                      metadata={})
    #         self.stop_event.wait(timeout=self.MESSAGE_INTERVAL)
    #
    #         binary_file = bytes([randint(0, 255) for i in range(200)])
    #         robothub.DETECTIONS.send_binary_file_detection(binary_file=binary_file,
    #                                                        title='Binary file detection number 1',
    #                                                        tags=['binary', 'detection'],
    #                                                        metadata={})
    #         self.stop_event.wait(timeout=self.MESSAGE_INTERVAL)
    #
    #         video = bytes([randint(0, 255) for i in range(2_000_000)])
    #         robothub.DETECTIONS.send_video_detection(video=video,
    #                                                  title='Video detection number 1',
    #                                                  tags=['video', 'detection'],
    #                                                  metadata={})
    #         self.stop_event.wait(timeout=self.MESSAGE_INTERVAL)
    #
    #         frame = np.random.randint(0, 256, size=100_000, dtype=np.uint8)
    #         robothub.DETECTIONS.send_frame_detection(imagedata=frame,
    #                                                  title='Frame detection number 1',
    #                                                  camera_serial='some_mxId',
    #                                                  tags=['frame', 'detection'],
    #                                                  metadata={})
    #         self.stop_event.wait(timeout=self.MESSAGE_INTERVAL)
    #     log.debug('EXIT')
    #
    # def polling_thread(self):
    #     log.debug('START')
    #     log.debug('Starting device polling loop')
    #     while not self.stop_event.is_set():
    #         for device in self.dai_device_objects:
    #             try:
    #                 device.oak.poll()
    #             except BaseException as e:
    #                 log.error(f'device {device.id} poll failed with {e}, exiting')
    #                 self._stop()
    #         time.sleep(0.002)
    #     log.debug('EXIT')
    #
    # def on_detection_uploaded(self, detection: robothub.UploadedDetection):
    #     log.debug(f'Detection with id "{detection.detection_id}" has been uploaded')
    #     log.debug(f'Uploaded detection: {str(detection.to_str())}')
    #
    # def on_stop(self):
    #     # Called by self.stop()
    #     log.info('STOPPING APP')
    #     self.stop_event.set()
    #     try:
    #         robothub.AGENT.shutdown()
    #     except BaseException as e:
    #         log.debug(f'Agent shutdown excepted with {e}')
    #
    #     try:
    #         while self.run_device_report_thread.is_alive():
    #             time.sleep(0.1)
    #         log.debug('device report thread joined')
    #     except BaseException as e:
    #         log.debug(f'device report thread join excepted with: {e}')
    #     try:
    #         while self.run_polling_thread.is_alive():
    #             time.sleep(0.1)
    #         log.debug('polling thread joined')
    #     except BaseException as e:
    #         log.debug(f'polling thread join excepted with: {e}')
    #     try:
    #         while self.run_detection_thread.is_alive():
    #             time.sleep(0.1)
    #         log.debug('detection thread joined')
    #     except BaseException as e:
    #         log.debug(f'detection thread join excepted with: {e}')
    #     try:
    #         robothub.STREAMS.destroy_all_streams()
    #
    #     except BaseException as e:
    #         raise Exception(f'Destroy all streams excepted with: {e}')
    #     for device in self.dai_device_objects:
    #         try:
    #             if device.state != robothub.DeviceState.DISCONNECTED:
    #                 device.oak.__exit__(Exception, 'Device disconnected - app shutting down', None)
    #         except BaseException as e:
    #             raise Exception(f'Could not exit device error: {e}')
    #     log.info('APP STOPPED')
    #     time.sleep(1)
