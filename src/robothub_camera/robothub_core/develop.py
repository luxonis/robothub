"""TBD"""
__all__ = ['Develop', 'DEVELOP']


class Develop:
    """One-time visualization"""
    def __init__(self):
        pass

    def _bind_app_(self, app):
        self._app = app

    def visualize(self, image_data):
        """
        Sends an image over WebRTC to the frontend server.

        @param image_data: encoded image bytes
        @type image_data: bytes | bytearray
        """

DEVELOP = Develop()
