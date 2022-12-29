from robothub_depthai import RobotHubApplication


class TestRobotHubApplication:
    def test_init(self):
        app = RobotHubApplication()
        assert app is not None
        assert app.camera_manager is not None
        assert app.hub_cameras is not None
        assert app.hub_cameras[0].id == 0
        assert app.hub_cameras[0].device is not None

    def test_start(self):
        app = RobotHubApplication()
        app.start_execution()
        assert app.camera_manager.is_running

    def test_stop(self):
        app = RobotHubApplication()
        app.start_execution()
        app.on_stop()
        assert not app.camera_manager.is_running
